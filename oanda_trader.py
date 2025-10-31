"""
Oanda Auto-Trading Integration

Connects to Oanda v20 REST API for automated trade execution.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import os
from forex_config import ForexConfig
from forex_data import ForexSignal


@dataclass
class OandaPosition:
    """Represents an open Oanda position."""
    trade_id: str
    pair: str
    side: str  # 'long' or 'short'
    units: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    unrealized_pl: float
    timestamp: datetime


@dataclass
class TradeHistory:
    """Completed trade record."""
    trade_id: str
    pair: str
    side: str
    units: float
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    exit_time: datetime
    realized_pl: float
    exit_reason: str  # 'TP', 'SL', 'MANUAL'


class OandaTrader:
    """Automated trading with Oanda v20 API."""

    def __init__(self, account_id: str, api_token: str, environment: str = "practice"):
        """
        Initialize Oanda trader.

        Args:
            account_id: Oanda account ID
            api_token: Oanda API token
            environment: 'practice' or 'live'
        """
        self.account_id = account_id
        self.api_token = api_token
        self.environment = environment

        # API endpoints
        if environment == "practice":
            self.api_url = "https://api-fxpractice.oanda.com"
            self.stream_url = "https://stream-fxpractice.oanda.com"
        else:
            self.api_url = "https://api-fxtrade.oanda.com"
            self.stream_url = "https://stream-fxtrade.oanda.com"

        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        # Trading parameters
        self.account_balance = 50000.0  # €50,000 budget
        self.risk_per_trade = 0.01  # 1% risk per trade
        self.max_positions = 5  # Max concurrent positions
        self.max_daily_loss = 0.05  # 5% max daily loss

        # Track positions and trades
        self.open_positions: Dict[str, OandaPosition] = {}
        self.trade_history: List[TradeHistory] = []
        self.daily_pnl = 0.0

    def get_account_info(self) -> Dict:
        """Get account information."""
        url = f"{self.api_url}/v3/accounts/{self.account_id}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get account info: {response.text}")

    def get_current_positions(self) -> List[OandaPosition]:
        """Get all open positions."""
        url = f"{self.api_url}/v3/accounts/{self.account_id}/openPositions"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            positions = []

            for pos in data.get('positions', []):
                instrument = pos['instrument']
                long_units = float(pos['long']['units'])
                short_units = float(pos['short']['units'])

                if long_units != 0:
                    positions.append(OandaPosition(
                        trade_id=pos['long']['tradeIDs'][0] if pos['long'].get('tradeIDs') else '',
                        pair=instrument.replace('_', '/'),
                        side='long',
                        units=long_units,
                        entry_price=float(pos['long']['averagePrice']),
                        current_price=0.0,  # Updated separately
                        stop_loss=0.0,
                        take_profit=0.0,
                        unrealized_pl=float(pos['long']['unrealizedPL']),
                        timestamp=datetime.now()
                    ))

                if short_units != 0:
                    positions.append(OandaPosition(
                        trade_id=pos['short']['tradeIDs'][0] if pos['short'].get('tradeIDs') else '',
                        pair=instrument.replace('_', '/'),
                        side='short',
                        units=abs(short_units),
                        entry_price=float(pos['short']['averagePrice']),
                        current_price=0.0,
                        stop_loss=0.0,
                        take_profit=0.0,
                        unrealized_pl=float(pos['short']['unrealizedPL']),
                        timestamp=datetime.now()
                    ))

            self.open_positions = {p.trade_id: p for p in positions}
            return positions
        else:
            raise Exception(f"Failed to get positions: {response.text}")

    def calculate_position_size(self, signal: ForexSignal) -> int:
        """
        Calculate position size based on risk management.

        Args:
            signal: Trading signal with SL/TP

        Returns:
            Position size in units
        """
        # Calculate risk amount
        risk_amount = self.account_balance * self.risk_per_trade

        # Calculate pip value (for EUR account)
        pip_size = 0.01 if 'JPY' in signal.pair else 0.0001

        # Calculate risk in pips
        risk_pips = signal.pips_risk

        # Position size = Risk Amount / (Risk in Pips * Pip Value)
        # For EUR/USD: 1 standard lot (100,000 units) = €10 per pip
        # For micro lot (1,000 units) = €0.10 per pip

        # Calculate units
        pip_value_per_unit = pip_size * 10  # Approximate for EUR pairs
        units = int(risk_amount / (risk_pips * pip_value_per_unit))

        # Ensure minimum 1000 units (micro lot)
        units = max(1000, units)

        # Ensure not too large (max 100,000 = 1 standard lot per trade)
        units = min(100000, units)

        return units

    def place_order(self, signal: ForexSignal, auto_execute: bool = True) -> Optional[Dict]:
        """
        Place market order based on trading signal.

        Args:
            signal: Trading signal
            auto_execute: If False, just return order details without executing

        Returns:
            Order response or None
        """
        # Safety checks
        if len(self.open_positions) >= self.max_positions:
            print(f"⚠️ Max positions reached ({self.max_positions})")
            return None

        if self.daily_pnl < -self.account_balance * self.max_daily_loss:
            print(f"⚠️ Max daily loss reached ({self.max_daily_loss*100}%)")
            return None

        # Calculate position size
        units = self.calculate_position_size(signal)

        # Convert pair format
        instrument = signal.pair.replace('/', '_')

        # Determine direction
        if signal.signal == 'BUY':
            units_str = str(units)
        else:  # SELL
            units_str = str(-units)

        # Prepare order
        order_data = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": units_str,
                "timeInForce": "FOK",  # Fill or Kill
                "positionFill": "DEFAULT",
                "stopLossOnFill": {
                    "price": str(round(signal.stop_loss, 5))
                },
                "takeProfitOnFill": {
                    "price": str(round(signal.take_profit, 5))
                }
            }
        }

        if not auto_execute:
            return order_data

        # Execute order
        url = f"{self.api_url}/v3/accounts/{self.account_id}/orders"
        response = requests.post(url, headers=self.headers, data=json.dumps(order_data))

        if response.status_code == 201:
            result = response.json()
            print(f"✅ Order placed: {signal.pair} {signal.signal} {units} units")
            print(f"   Entry: {signal.entry_price:.5f} | SL: {signal.stop_loss:.5f} | TP: {signal.take_profit:.5f}")
            return result
        else:
            print(f"❌ Order failed: {response.text}")
            return None

    def close_position(self, trade_id: str, reason: str = "MANUAL") -> Optional[Dict]:
        """Close an open position."""
        url = f"{self.api_url}/v3/accounts/{self.account_id}/trades/{trade_id}/close"
        response = requests.put(url, headers=self.headers)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Position closed: {trade_id} ({reason})")
            return result
        else:
            print(f"❌ Failed to close position: {response.text}")
            return None

    def get_pricing(self, instruments: List[str]) -> Dict[str, float]:
        """Get current pricing for instruments."""
        instruments_str = ",".join(instruments)
        url = f"{self.api_url}/v3/accounts/{self.account_id}/pricing"
        params = {"instruments": instruments_str}

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            data = response.json()
            prices = {}
            for price in data.get('prices', []):
                instrument = price['instrument'].replace('_', '/')
                mid_price = (float(price['bids'][0]['price']) + float(price['asks'][0]['price'])) / 2
                prices[instrument] = mid_price
            return prices
        else:
            return {}

    def update_positions_pnl(self):
        """Update P&L for all open positions."""
        if not self.open_positions:
            return

        # Get instruments
        instruments = [p.pair.replace('/', '_') for p in self.open_positions.values()]
        prices = self.get_pricing(instruments)

        # Update each position
        for trade_id, position in self.open_positions.items():
            if position.pair in prices:
                position.current_price = prices[position.pair]

                # Calculate unrealized P&L
                if position.side == 'long':
                    pnl = (position.current_price - position.entry_price) * position.units
                else:  # short
                    pnl = (position.entry_price - position.current_price) * position.units

                position.unrealized_pl = pnl

    def get_total_pnl(self) -> Tuple[float, float]:
        """
        Get total P&L.

        Returns:
            (unrealized_pnl, realized_pnl)
        """
        unrealized = sum(p.unrealized_pl for p in self.open_positions.values())
        realized = sum(t.realized_pl for t in self.trade_history)
        return unrealized, realized

    def save_trade_history(self, filepath: str = "./trades_history.json"):
        """Save trade history to file."""
        data = {
            'account_balance': self.account_balance,
            'daily_pnl': self.daily_pnl,
            'open_positions': [asdict(p) for p in self.open_positions.values()],
            'trade_history': [asdict(t) for t in self.trade_history],
            'timestamp': datetime.now().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def load_trade_history(self, filepath: str = "./trades_history.json"):
        """Load trade history from file."""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)

            self.account_balance = data.get('account_balance', 50000.0)
            self.daily_pnl = data.get('daily_pnl', 0.0)

            # Load open positions
            for p_data in data.get('open_positions', []):
                p_data['timestamp'] = datetime.fromisoformat(p_data['timestamp'])
                position = OandaPosition(**p_data)
                self.open_positions[position.trade_id] = position

            # Load trade history
            for t_data in data.get('trade_history', []):
                t_data['entry_time'] = datetime.fromisoformat(t_data['entry_time'])
                t_data['exit_time'] = datetime.fromisoformat(t_data['exit_time'])
                trade = TradeHistory(**t_data)
                self.trade_history.append(trade)


def test_oanda_connection():
    """Test Oanda API connection."""
    print("Testing Oanda API Connection...")
    print("="*60)

    # Get credentials from environment
    account_id = os.getenv("OANDA_ACCOUNT_ID", "")
    api_token = os.getenv("OANDA_API_TOKEN", "")

    if not account_id or not api_token:
        print("❌ Please set OANDA_ACCOUNT_ID and OANDA_API_TOKEN in .env file")
        return

    try:
        trader = OandaTrader(account_id, api_token, environment="practice")

        # Get account info
        print("\n📊 Account Information:")
        account_info = trader.get_account_info()
        print(f"Account ID: {account_info['account']['id']}")
        print(f"Balance: €{float(account_info['account']['balance']):.2f}")
        print(f"Currency: {account_info['account']['currency']}")
        print(f"Unrealized P&L: €{float(account_info['account']['unrealizedPL']):.2f}")

        # Get open positions
        print("\n📈 Open Positions:")
        positions = trader.get_current_positions()
        if positions:
            for pos in positions:
                print(f"  {pos.pair} {pos.side.upper()}: {pos.units} units @ {pos.entry_price:.5f}")
                print(f"    Unrealized P&L: €{pos.unrealized_pl:.2f}")
        else:
            print("  No open positions")

        print("\n✓ Oanda API connection successful!")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_oanda_connection()
