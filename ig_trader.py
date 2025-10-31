"""
IG Real Trader

Executes REAL trades on IG demo/live account using REST API.
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime
from trading_ig import IGService
from forex_config import ForexConfig
from ig_rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class IGTrader:
    """
    Real trader for IG Markets.

    Executes actual trades on IG platform (demo or live).
    """

    def __init__(self, api_key: str = None, username: str = None, password: str = None,
                 acc_number: str = None):
        """
        Initialize IG trader.

        Args:
            api_key: IG API key
            username: IG username
            password: IG password
            acc_number: IG account number
        """
        self.api_key = api_key or ForexConfig.IG_API_KEY
        self.username = username or ForexConfig.IG_USERNAME
        self.password = password or ForexConfig.IG_PASSWORD
        self.acc_number = acc_number or ForexConfig.IG_ACC_NUMBER
        self.acc_type = "DEMO" if ForexConfig.IG_DEMO else "LIVE"

        # Create IG service
        self.ig_service = IGService(
            username=self.username,
            password=self.password,
            api_key=self.api_key,
            acc_type=self.acc_type,
            acc_number=self.acc_number
        )

        # Create session
        try:
            self.ig_service.create_session(version="2")
            logger.info(f"✅ IG trader session created ({self.acc_type})")
        except Exception as e:
            logger.error(f"❌ IG authentication failed: {e}")
            raise

    def _get_epic(self, pair: str) -> str:
        """Convert pair to EPIC."""
        if pair in ForexConfig.IG_EPIC_MAP:
            return ForexConfig.IG_EPIC_MAP[pair]

        # Fallback
        clean_pair = pair.replace("_", "")
        return f"CS.D.{clean_pair}.TODAY.IP"

    def open_position(self, pair: str, direction: str, size: float,
                      stop_loss_pips: Optional[float] = None,
                      take_profit_pips: Optional[float] = None) -> Dict:
        """
        Open a new position.

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            direction: 'BUY' or 'SELL'
            size: Position size in lots (e.g., 0.01 = micro lot)
            stop_loss_pips: Optional stop loss in pips
            take_profit_pips: Optional take profit in pips

        Returns:
            Dict with deal reference and confirmation
        """
        try:
            # Wait for rate limiter (trading request)
            rate_limiter = get_rate_limiter()
            rate_limiter.wait_if_needed(is_account_request=True)
            epic = self._get_epic(pair)

            # Convert direction to IG format
            ig_direction = "BUY" if direction.upper() == "BUY" else "SELL"

            # Get market info and dealing rules
            rate_limiter.wait_if_needed(is_account_request=True)
            market_info = self.ig_service.fetch_market_by_epic(epic)

            snapshot = market_info.get('snapshot', {})
            dealing_rules = market_info.get('dealingRules', {})
            instrument = market_info.get('instrument', {})

            # Check market is tradeable
            market_status = snapshot.get('marketStatus')
            if market_status != 'TRADEABLE':
                raise ValueError(f"Market {pair} is not tradeable: {market_status}")

            # Get current prices
            current_bid = snapshot.get('bid')
            current_offer = snapshot.get('offer')

            if not current_bid or not current_offer:
                raise ValueError(f"Could not get current price for {pair}")

            # Use offer for BUY, bid for SELL
            current_price = current_offer if ig_direction == "BUY" else current_bid

            logger.info(f"Market: {pair} ({ig_direction})")
            logger.info(f"  Bid: {current_bid}, Offer: {current_offer}")
            logger.info(f"  Using: {current_price}")

            # Calculate distances in POINTS (always positive!)
            # For MINI markets: 1 pip = 10 points (EUR/USD quoted to 5dp)
            # IG applies direction automatically:
            #   BUY: stop below, limit above
            #   SELL: stop above, limit below

            # CRITICAL: JPY pairs have different pip calculation!
            # JPY pairs: 1 pip = 1 point (quoted to 2dp: 110.50)
            # Other pairs: 1 pip = 10 points (quoted to 5dp: 1.10500)
            points_per_pip = 1 if 'JPY' in pair else 10

            min_distance = dealing_rules.get('minNormalStopOrLimitDistance', {}).get('value', 20)
            logger.info(f"  Min stop/limit distance: {min_distance} points")

            # Get minimum deal size for this market
            min_deal_size = dealing_rules.get('minDealSize', {}).get('value', 0.1)
            logger.info(f"  Min deal size: {min_deal_size} lots")

            # Ensure position size meets minimum
            if size < min_deal_size:
                logger.warning(f"  Position size {size} < minimum {min_deal_size}, using minimum")
                size = min_deal_size

            # Calculate stop and limit distances (ALWAYS POSITIVE)
            stop_distance = None
            limit_distance = None

            if stop_loss_pips:
                stop_distance = int(stop_loss_pips * points_per_pip)
                stop_distance = max(stop_distance, int(min_distance))  # Respect minimum
                logger.info(f"  Stop distance: {stop_distance} points ({stop_loss_pips} pips)")

            if take_profit_pips:
                limit_distance = int(take_profit_pips * points_per_pip)
                limit_distance = max(limit_distance, int(min_distance))  # Respect minimum
                logger.info(f"  Limit distance: {limit_distance} points ({take_profit_pips} pips)")

            # Prepare parameters for create_open_position
            # Get supported currencies from instrument, or use account currency
            currencies = instrument.get('currencies', [])
            if currencies and len(currencies) > 0:
                # Use first supported currency
                currency_code = currencies[0].get('code', 'EUR')
                logger.info(f"  Using currency: {currency_code} (from instrument)")
            else:
                # Fall back to EUR (account currency)
                currency_code = 'EUR'
                logger.info(f"  Using currency: {currency_code} (account default)")
            expiry = "-"  # DFB markets
            force_open = True
            guaranteed_stop = False
            level = None  # Market order - IG uses current price
            order_type = "MARKET"
            quote_id = None
            trailing_stop = None
            trailing_stop_increment = None
            stop_level = None  # Use distance, not level
            limit_level = None  # Use distance, not level

            # Execute trade via IG API (positional arguments in correct order)
            response = self.ig_service.create_open_position(
                currency_code,
                ig_direction,
                epic,
                expiry,
                force_open,
                guaranteed_stop,
                level,
                limit_distance,
                limit_level,
                order_type,
                quote_id,
                size,
                stop_distance,
                stop_level,
                trailing_stop,
                trailing_stop_increment
            )

            logger.info(f"✅ Opened {direction} position: {pair} ({size} lots)")
            logger.info(f"   Deal reference: {response.get('dealReference')}")

            return {
                'success': True,
                'deal_reference': response.get('dealReference'),
                'pair': pair,
                'direction': direction,
                'size': size,
                'response': response
            }

        except Exception as e:
            logger.error(f"❌ Failed to open {direction} position for {pair}: {e}")
            return {
                'success': False,
                'error': str(e),
                'pair': pair,
                'direction': direction
            }

    def close_position(self, deal_id: str, size: Optional[float] = None) -> Dict:
        """
        Close an open position.

        Args:
            deal_id: IG deal ID
            size: Optional size to close (None = close all)

        Returns:
            Dict with confirmation
        """
        try:
            # Close position via IG API
            response = self.ig_service.close_open_position(
                deal_id=deal_id,
                direction="SELL",  # Opposite of open direction
                order_type="MARKET",
                size=size
            )

            logger.info(f"✅ Closed position: {deal_id}")

            return {
                'success': True,
                'deal_reference': response.get('dealReference'),
                'deal_id': deal_id,
                'response': response
            }

        except Exception as e:
            logger.error(f"❌ Failed to close position {deal_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'deal_id': deal_id
            }

    def get_open_positions(self) -> List[Dict]:
        """
        Get all open positions.

        Returns:
            List of open positions
        """
        try:
            # Wait for rate limiter
            rate_limiter = get_rate_limiter()
            rate_limiter.wait_if_needed(is_account_request=True)
            response = self.ig_service.fetch_open_positions()

            # trading-ig returns DataFrame, check if empty
            import pandas as pd
            if response is None or (isinstance(response, pd.DataFrame) and response.empty):
                return []

            # If it's a DataFrame, convert to dict
            if isinstance(response, pd.DataFrame):
                positions_list = response.to_dict('records')
            else:
                positions_list = response.get('positions', [])

            positions = []
            for pos in positions_list:
                # Handle different response formats
                if 'market' in pos:
                    market = pos.get('market', {})
                    position = pos.get('position', {})
                else:
                    # Flat structure
                    market = {'epic': pos.get('epic', '')}
                    position = pos

                positions.append({
                    'deal_id': position.get('dealId') or position.get('deal_id'),
                    'pair': self._epic_to_pair(market.get('epic', '')),
                    'epic': market.get('epic'),
                    'direction': position.get('direction'),
                    'size': position.get('size') or position.get('deal_size'),
                    'level': position.get('level') or position.get('open_level'),  # Open price
                    'currency': position.get('currency'),
                    'created_date': position.get('createdDate') or position.get('created_date'),
                    'profit_loss': position.get('profit') or position.get('profit_loss'),
                    'stop_level': position.get('stopLevel') or position.get('stop_level'),
                    'limit_level': position.get('limitLevel') or position.get('limit_level'),
                })

            logger.info(f"📊 Open positions: {len(positions)}")
            return positions

        except Exception as e:
            logger.error(f"❌ Failed to fetch positions: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def _epic_to_pair(self, epic: str) -> Optional[str]:
        """Convert EPIC to pair name."""
        for pair, pair_epic in ForexConfig.IG_EPIC_MAP.items():
            if pair_epic == epic:
                return pair
        return epic

    def get_account_info(self) -> Dict:
        """
        Get account information.

        Returns:
            Dict with balance, equity, margin, etc.
        """
        try:
            # Wait for rate limiter
            rate_limiter = get_rate_limiter()
            rate_limiter.wait_if_needed(is_account_request=True)
            response = self.ig_service.fetch_accounts()

            # trading-ig returns DataFrame
            import pandas as pd
            if response is None or (isinstance(response, pd.DataFrame) and response.empty):
                return {}

            # Convert DataFrame to dict if needed
            if isinstance(response, pd.DataFrame):
                accounts = response.to_dict('records')
            else:
                accounts = response.get('accounts', [])

            if not accounts:
                return {}

            # Get first account (or match acc_number)
            for account in accounts:
                account_id = account.get('accountId') or account.get('account_id')
                if account_id == self.acc_number:
                    balance_info = account.get('balance', {})
                    return {
                        'account_id': account_id,
                        'account_name': account.get('accountName') or account.get('account_name'),
                        'balance': balance_info.get('balance') if isinstance(balance_info, dict) else account.get('balance'),
                        'deposit': balance_info.get('deposit') if isinstance(balance_info, dict) else account.get('deposit'),
                        'profit_loss': balance_info.get('profitLoss') if isinstance(balance_info, dict) else account.get('profit_loss'),
                        'available': balance_info.get('available') if isinstance(balance_info, dict) else account.get('available'),
                        'currency': account.get('currency'),
                    }

            # If no match, return first account
            account = accounts[0]
            balance_info = account.get('balance', {})
            return {
                'account_id': account.get('accountId') or account.get('account_id'),
                'account_name': account.get('accountName') or account.get('account_name'),
                'balance': balance_info.get('balance') if isinstance(balance_info, dict) else account.get('balance'),
                'deposit': balance_info.get('deposit') if isinstance(balance_info, dict) else account.get('deposit'),
                'profit_loss': balance_info.get('profitLoss') if isinstance(balance_info, dict) else account.get('profit_loss'),
                'available': balance_info.get('available') if isinstance(balance_info, dict) else account.get('available'),
                'currency': account.get('currency'),
            }

        except Exception as e:
            logger.error(f"❌ Failed to fetch account info: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

    def calculate_position_size(self, account_balance: float, risk_percent: float,
                                stop_loss_pips: float, pair: str) -> float:
        """
        Calculate position size based on risk management.

        Args:
            account_balance: Account balance in EUR
            risk_percent: Risk per trade (e.g., 1.0 = 1%)
            stop_loss_pips: Stop loss in pips
            pair: Currency pair

        Returns:
            Position size in lots (minimum 0.1 for MINI markets)
        """
        # Risk amount in EUR
        risk_amount = account_balance * (risk_percent / 100)

        # For MINI markets: 1 lot = 10,000 units
        # Pip value for 0.1 lot MINI = ~€1 per pip for EUR/USD
        # (More accurate: 0.1 lot = 1,000 EUR, pip = 0.0001, so 1,000 * 0.0001 = €0.10)
        pip_value_per_mini_lot = 1.0  # €1 per pip for 0.1 lot on EUR pairs

        # Calculate size
        position_size = risk_amount / (stop_loss_pips * pip_value_per_mini_lot)

        # Round to 1 decimal (MINI lots are 0.1, 0.2, 0.3, etc.)
        position_size = round(position_size, 1)

        # Clamp to reasonable limits
        # Min: 0.1 lot (IG MINI market minimum)
        # Max: configurable (default 10.0 lots = 100,000 EUR exposure)
        position_size = max(0.1, min(position_size, ForexConfig.MAX_POSITION_SIZE))

        return position_size


# Test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    print("="*80)
    print("IG REAL TRADER TEST")
    print("="*80)

    # Create trader
    trader = IGTrader()

    # Get account info
    print("\n📊 Account Information:")
    account = trader.get_account_info()
    for key, value in account.items():
        print(f"   {key}: {value}")

    # Get open positions
    print("\n📈 Open Positions:")
    positions = trader.get_open_positions()
    if positions:
        for pos in positions:
            print(f"   {pos['pair']} {pos['direction']} {pos['size']} lots")
            print(f"      P&L: {pos['profit_loss']}")
    else:
        print("   No open positions")

    # Test position sizing
    print("\n💰 Position Sizing (1% risk, 20 pip SL):")
    balance = account.get('balance', 10000)
    size = trader.calculate_position_size(
        account_balance=balance,
        risk_percent=1.0,
        stop_loss_pips=20,
        pair="EUR_USD"
    )
    print(f"   Account balance: €{balance}")
    print(f"   Recommended size: {size} lots")

    # NOTE: Uncomment to test REAL trading (use with caution!)
    # print("\n⚠️  TEST TRADE (COMMENT OUT IF NOT TESTING)")
    # result = trader.open_position(
    #     pair="EUR_USD",
    #     direction="BUY",
    #     size=0.01,
    #     stop_loss_pips=20,
    #     take_profit_pips=40
    # )
    # print(f"   Result: {result}")

    print("\n" + "="*80)
