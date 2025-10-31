"""
Paper Trading Module with Live 1-Minute Candle Monitoring

Simulates real trading with live market data, tracking positions and P&L in real-time.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import threading
from forex_data import ForexSignal, ForexDataFetcher
from forex_config import ForexConfig
from trading_database import get_database
from realistic_forex_calculations import (
    apply_spread, get_entry_price, get_mark_price,
    calculate_unrealized_pnl, calculate_realized_pnl,
    calculate_position_size_risk_based, calculate_margin_required,
    get_realistic_entry_price, get_realistic_exit_price,
    get_conversion_rate,
    BidAsk
)


@dataclass
class PaperPosition:
    """Represents an open paper trading position."""
    position_id: str
    pair: str
    side: str  # 'BUY' or 'SELL'
    units: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    current_price: float
    unrealized_pl: float
    signal_confidence: float
    signal_reasoning: List[str]

    def to_dict(self):
        d = asdict(self)
        d['entry_time'] = d['entry_time'].isoformat()
        return d


@dataclass
class PaperTrade:
    """Completed paper trade record."""
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
    realized_pl_pips: float
    exit_reason: str  # 'TP', 'SL', 'MANUAL'
    signal_confidence: float
    signal_reasoning: List[str]

    def to_dict(self):
        d = asdict(self)
        d['entry_time'] = d['entry_time'].isoformat()
        d['exit_time'] = d['exit_time'].isoformat()
        return d


class PaperTrader:
    """
    Paper trading engine with live 1-minute candle monitoring.

    Simulates real trading without actual money:
    - Tracks positions with entry, SL, TP
    - Monitors positions with live 1-min candles
    - Auto-closes when SL or TP hit
    - Calculates real-time P&L
    - Maintains complete trade history
    """

    def __init__(self, initial_balance: float = 50000.0, use_database: bool = True):
        """
        Initialize paper trader.

        Args:
            initial_balance: Starting balance in euros
            use_database: If True, use SQLite database for persistence
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance

        # Risk management
        self.risk_per_trade = 0.01  # 1% risk per trade
        self.max_positions = 5
        self.max_daily_loss = 0.05  # 5% max daily loss
        self.leverage = 50  # 50:1 leverage (typical for forex retail accounts)
        self.account_currency = 'EUR'  # Account currency

        # Realistic execution settings
        self.use_slippage = True  # Enable slippage modeling
        self.use_dynamic_spreads = True  # Enable dynamic spreads (wider during news/rollover)

        # Position tracking
        self.open_positions: Dict[str, PaperPosition] = {}
        self.trade_history: List[PaperTrade] = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0

        # Equity curve tracking
        self.equity_snapshots = []  # List of (timestamp, equity, balance, unrealized_pl)
        self.last_snapshot_time = datetime.now()

        # Data fetcher for live candles
        self.data_fetcher = ForexDataFetcher(ForexConfig.IG_API_KEY)

        # Database integration
        self.use_database = use_database
        if use_database:
            self.db = get_database()
            # Load existing state from database
            self.load_state_from_db()

        # Monitoring thread
        self.monitoring = False
        self.monitor_thread = None

        # Load existing history if available
        self.load_state()

    def calculate_position_size(self, signal: ForexSignal) -> int:
        """
        Calculate position size based on risk management using realistic forex calculations.

        Uses professional risk-based position sizing that accounts for:
        - Currency conversion
        - Stop loss distance
        - Account equity

        Args:
            signal: Trading signal with SL/TP

        Returns:
            Position size in units
        """
        # Use realistic risk-based position sizing
        units = calculate_position_size_risk_based(
            equity_account=self.equity,
            risk_pct=self.risk_per_trade,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            pair=signal.pair,
            account_currency=self.account_currency
        )

        return units

    def open_position(self, signal: ForexSignal) -> Optional[str]:
        """
        Open a new paper trading position.

        Args:
            signal: Trading signal from AI agents

        Returns:
            Position ID if successful, None otherwise
        """
        # Safety checks
        if len(self.open_positions) >= self.max_positions:
            print(f"⚠️ Max positions reached ({self.max_positions})")
            return None

        if self.daily_pnl < -self.balance * self.max_daily_loss:
            print(f"⚠️ Max daily loss reached ({self.max_daily_loss*100}%)")
            return None

        # Calculate position size
        units = self.calculate_position_size(signal)

        # Get ATR from signal indicators if available
        atr = signal.indicators.get('atr', None) if hasattr(signal, 'indicators') and signal.indicators else None

        # Get realistic entry price with spread and slippage
        if self.use_slippage:
            entry_price, entry_details = get_realistic_entry_price(
                side=signal.signal,
                mid_price=signal.entry_price,
                pair=signal.pair,
                atr=atr,
                use_dynamic_spread=self.use_dynamic_spreads
            )
            # Log execution details
            print(f"   Execution: Spread {entry_details['spread_pips']:.1f} pips | "
                  f"Slippage {entry_details['slippage_pips']:.2f} pips")
        else:
            # Simple entry without slippage
            bid_ask = apply_spread(signal.entry_price, signal.pair)
            entry_price = get_entry_price(signal.signal, bid_ask)
            entry_details = None

        # Create position ID
        position_id = f"{signal.pair}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create position
        position = PaperPosition(
            position_id=position_id,
            pair=signal.pair,
            side=signal.signal,
            units=units,
            entry_price=entry_price,  # Realistic entry price with spread
            entry_time=datetime.now(),
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            current_price=entry_price,  # Start at entry price
            unrealized_pl=0.0,
            signal_confidence=signal.confidence,
            signal_reasoning=signal.reasoning
        )

        # Add to open positions
        self.open_positions[position_id] = position

        # Start monitoring if not already running
        if not self.monitoring:
            self.start_monitoring()

        print(f"✅ Opened {signal.signal} position: {signal.pair}")
        print(f"   Mid: {signal.entry_price:.5f} | Entry: {entry_price:.5f} ({signal.signal} at {'ASK' if signal.signal == 'BUY' else 'BID'})")
        print(f"   SL: {signal.stop_loss:.5f} | TP: {signal.take_profit:.5f}")
        print(f"   Units: {units:,} | Risk: €{self.equity * self.risk_per_trade:.2f}")

        # Record equity snapshot
        self.record_equity_snapshot()

        # Save state
        self.save_state()

        return position_id

    def close_position(self, position_id: str, reason: str = "MANUAL",
                      exit_price: Optional[float] = None) -> Optional[PaperTrade]:
        """
        Close a paper trading position.

        Args:
            position_id: ID of position to close
            reason: Closure reason ('TP', 'SL', 'MANUAL')
            exit_price: Exit price (if None, uses current price)

        Returns:
            Completed trade record
        """
        if position_id not in self.open_positions:
            print(f"❌ Position {position_id} not found")
            return None

        position = self.open_positions[position_id]

        # Use provided exit price or current price
        if exit_price is None:
            exit_price = position.current_price

        # Extract quote currency
        quote_currency = position.pair.split('_')[1]

        # Determine if this is a stop loss hit
        is_stop_loss = (reason == 'SL')

        # Get realistic exit price with spread and slippage
        if self.use_slippage:
            # Get ATR (try to estimate from position if not available)
            atr = None  # Could be stored with position in future

            actual_exit_price, exit_details = get_realistic_exit_price(
                side=position.side,
                mid_price=exit_price,
                pair=position.pair,
                atr=atr,
                is_stop_loss=is_stop_loss,
                use_dynamic_spread=self.use_dynamic_spreads
            )

            # Calculate P&L with realistic exit price
            exit_bid_ask = apply_spread(exit_price, position.pair)
            pl, pips = calculate_realized_pnl(
                side=position.side,
                units=position.units,
                entry_price=position.entry_price,
                exit_bid_ask=exit_bid_ask,
                quote_currency=quote_currency,
                account_currency=self.account_currency
            )

            # Adjust P&L for slippage
            slippage_cost = (actual_exit_price - get_mark_price(position.side, exit_bid_ask)) * position.units
            slippage_cost_eur = slippage_cost * get_conversion_rate(quote_currency, self.account_currency, exit_price)
            pl += slippage_cost_eur if position.side == 'BUY' else -slippage_cost_eur

        else:
            # Simple exit without slippage
            exit_bid_ask = apply_spread(exit_price, position.pair)
            pl, pips = calculate_realized_pnl(
                side=position.side,
                units=position.units,
                entry_price=position.entry_price,
                exit_bid_ask=exit_bid_ask,
                quote_currency=quote_currency,
                account_currency=self.account_currency
            )
            actual_exit_price = get_mark_price(position.side, exit_bid_ask)
            exit_details = None

        # Create trade record
        trade = PaperTrade(
            trade_id=position.position_id,
            pair=position.pair,
            side=position.side,
            units=position.units,
            entry_price=position.entry_price,
            exit_price=actual_exit_price,  # Realistic exit price (BID for long, ASK for short)
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            entry_time=position.entry_time,
            exit_time=datetime.now(),
            realized_pl=pl,
            realized_pl_pips=pips,
            exit_reason=reason,
            signal_confidence=position.signal_confidence,
            signal_reasoning=position.signal_reasoning
        )

        # Update balance and P&L
        self.balance += pl
        self.equity = self.balance + self.get_unrealized_pnl()
        self.daily_pnl += pl
        self.total_pnl += pl

        # Add to history
        self.trade_history.append(trade)

        # Save trade to database
        if self.use_database:
            try:
                self.db.save_trade({
                    'trade_id': trade.trade_id,
                    'pair': trade.pair,
                    'side': trade.side,
                    'units': trade.units,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.exit_price,
                    'stop_loss': trade.stop_loss,
                    'take_profit': trade.take_profit,
                    'entry_time': trade.entry_time.isoformat(),
                    'exit_time': trade.exit_time.isoformat(),
                    'realized_pl': trade.realized_pl,
                    'realized_pl_pips': trade.realized_pl_pips,
                    'exit_reason': trade.exit_reason,
                    'signal_confidence': trade.signal_confidence,
                    'signal_reasoning': trade.signal_reasoning
                })
                # Mark position as closed in database
                self.db.close_position(position_id)
            except Exception as e:
                print(f"⚠️ Error saving trade to database: {e}")

        # Remove from open positions
        del self.open_positions[position_id]

        # Stop monitoring if no positions
        if not self.open_positions and self.monitoring:
            self.stop_monitoring()

        emoji = "🟢" if pl > 0 else "🔴"
        print(f"{emoji} Closed {position.side} {position.pair}: {reason}")
        print(f"   P&L: €{pl:.2f} ({pips:.1f} pips)")
        print(f"   Balance: €{self.balance:,.2f}")

        # Record equity snapshot
        self.record_equity_snapshot()

        # Save state
        self.save_state()

        return trade

    def update_positions(self):
        """
        Update all open positions with live 1-minute candles.
        Automatically closes positions if SL or TP hit.
        """
        if not self.open_positions:
            return

        # Get unique pairs
        pairs = list(set(pos.pair for pos in self.open_positions.values()))

        for pair in pairs:
            try:
                # Fetch latest 1-minute candle
                df = self.data_fetcher.get_candles(pair, '1', count=1)

                if df.empty:
                    continue

                # Get current price (last close - this is mid price)
                current_mid = float(df['close'].iloc[-1])
                high = float(df['high'].iloc[-1])
                low = float(df['low'].iloc[-1])

                # Convert to bid/ask
                current_bid_ask = apply_spread(current_mid, pair)

                # Update all positions for this pair
                positions_to_close = []

                for position_id, position in self.open_positions.items():
                    if position.pair != pair:
                        continue

                    # Update current price (mark price: BID for long, ASK for short)
                    position.current_price = get_mark_price(position.side, current_bid_ask)

                    # Calculate realistic unrealized P&L
                    quote_currency = pair.split('_')[1]
                    position.unrealized_pl = calculate_unrealized_pnl(
                        side=position.side,
                        units=position.units,
                        entry_price=position.entry_price,
                        current_bid_ask=current_bid_ask,
                        quote_currency=quote_currency,
                        account_currency=self.account_currency
                    )

                    # Check if stop loss hit (use candle low/high for accuracy)
                    if position.side == 'BUY':
                        if low <= position.stop_loss:
                            positions_to_close.append((position_id, 'SL', position.stop_loss))
                        elif high >= position.take_profit:
                            positions_to_close.append((position_id, 'TP', position.take_profit))
                    else:  # SELL
                        if high >= position.stop_loss:
                            positions_to_close.append((position_id, 'SL', position.stop_loss))
                        elif low <= position.take_profit:
                            positions_to_close.append((position_id, 'TP', position.take_profit))

                # Close positions that hit SL/TP
                for position_id, reason, exit_price in positions_to_close:
                    self.close_position(position_id, reason, exit_price)

            except Exception as e:
                print(f"⚠️ Error updating {pair}: {e}")

        # Update equity
        self.equity = self.balance + self.get_unrealized_pnl()

        # Record equity snapshot
        self.record_equity_snapshot()

    def monitor_positions(self):
        """Background thread that monitors positions every minute."""
        while self.monitoring:
            try:
                self.update_positions()
                time.sleep(60)  # Check every minute
            except Exception as e:
                print(f"⚠️ Monitor error: {e}")
                time.sleep(60)

    def start_monitoring(self):
        """Start the position monitoring thread."""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_positions, daemon=True)
            self.monitor_thread.start()
            print("🔄 Started position monitoring (1-min candles)")

    def stop_monitoring(self):
        """Stop the position monitoring thread."""
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=2)
            print("⏹️ Stopped position monitoring")

    def get_unrealized_pnl(self) -> float:
        """Get total unrealized P&L from all open positions."""
        return sum(pos.unrealized_pl for pos in self.open_positions.values())

    def get_total_pnl(self) -> float:
        """Get total P&L (realized + unrealized)."""
        realized = sum(trade.realized_pl for trade in self.trade_history)
        unrealized = self.get_unrealized_pnl()
        return realized + unrealized

    def record_equity_snapshot(self):
        """Record current equity for equity curve tracking."""
        now = datetime.now()

        # Only record if enough time has passed (avoid too many snapshots)
        time_diff = (now - self.last_snapshot_time).total_seconds()
        if time_diff < 60 and len(self.equity_snapshots) > 0:  # Min 1 minute between snapshots
            return

        unrealized_pl = self.get_unrealized_pnl()
        snapshot = {
            'timestamp': now,
            'equity': self.equity,
            'balance': self.balance,
            'unrealized_pl': unrealized_pl,
            'open_positions': len(self.open_positions),
            'total_trades': len(self.trade_history)
        }

        self.equity_snapshots.append(snapshot)
        self.last_snapshot_time = now

        # Keep last 10,000 snapshots (enough for weeks of trading)
        if len(self.equity_snapshots) > 10000:
            self.equity_snapshots = self.equity_snapshots[-10000:]

    def get_statistics(self) -> Dict:
        """Get trading statistics."""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'total_pnl': self.get_total_pnl(),
                'roi': 0.0
            }

        wins = [t for t in self.trade_history if t.realized_pl > 0]
        losses = [t for t in self.trade_history if t.realized_pl < 0]

        total_wins = sum(t.realized_pl for t in wins)
        total_losses = abs(sum(t.realized_pl for t in losses))

        return {
            'total_trades': len(self.trade_history),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(self.trade_history) * 100,
            'avg_win': total_wins / len(wins) if wins else 0.0,
            'avg_loss': total_losses / len(losses) if losses else 0.0,
            'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
            'total_pnl': self.get_total_pnl(),
            'roi': (self.balance - self.initial_balance) / self.initial_balance * 100
        }

    def save_state_to_db(self):
        """Save current state to database."""
        if not self.use_database:
            return

        try:
            # Save all open positions
            for position in self.open_positions.values():
                self.db.save_position({
                    'position_id': position.position_id,
                    'pair': position.pair,
                    'side': position.side,
                    'units': position.units,
                    'entry_price': position.entry_price,
                    'entry_time': position.entry_time.isoformat(),
                    'stop_loss': position.stop_loss,
                    'take_profit': position.take_profit,
                    'current_price': position.current_price,
                    'unrealized_pl': position.unrealized_pl,
                    'status': 'OPEN',
                    'signal_confidence': position.signal_confidence
                })

            # Save performance metrics
            stats = self.get_statistics()
            self.db.save_performance_metrics({
                'balance': self.balance,
                'equity': self.equity,
                'unrealized_pl': self.get_unrealized_pnl(),
                'realized_pl_today': self.daily_pnl,
                'open_positions': len(self.open_positions),
                'total_trades': len(self.trade_history),
                'win_rate': stats['win_rate'],
                'profit_factor': stats['profit_factor'],
                'timestamp': datetime.now()
            })

        except Exception as e:
            print(f"⚠️ Error saving state to database: {e}")

    def load_state_from_db(self):
        """Load state from database."""
        if not self.use_database:
            return

        try:
            # Load open positions
            positions = self.db.get_open_positions()
            for pos_data in positions:
                position = PaperPosition(
                    position_id=pos_data['position_id'],
                    pair=pos_data['pair'],
                    side=pos_data['side'],
                    units=pos_data['units'],
                    entry_price=pos_data['entry_price'],
                    entry_time=datetime.fromisoformat(pos_data['entry_time']),
                    stop_loss=pos_data['stop_loss'],
                    take_profit=pos_data['take_profit'],
                    current_price=pos_data.get('current_price', pos_data['entry_price']),
                    unrealized_pl=pos_data.get('unrealized_pl', 0.0),
                    signal_confidence=pos_data.get('signal_confidence', 0.0),
                    signal_reasoning=[]
                )
                self.open_positions[position.position_id] = position

            # Load recent trades
            trades = self.db.get_trades(limit=100)
            for trade_data in trades:
                trade = PaperTrade(
                    trade_id=trade_data['trade_id'],
                    pair=trade_data['pair'],
                    side=trade_data['side'],
                    units=trade_data['units'],
                    entry_price=trade_data['entry_price'],
                    exit_price=trade_data['exit_price'],
                    stop_loss=trade_data['stop_loss'],
                    take_profit=trade_data['take_profit'],
                    entry_time=datetime.fromisoformat(trade_data['entry_time']),
                    exit_time=datetime.fromisoformat(trade_data['exit_time']),
                    realized_pl=trade_data['realized_pl'],
                    realized_pl_pips=trade_data['realized_pl_pips'],
                    exit_reason=trade_data['exit_reason'],
                    signal_confidence=trade_data.get('signal_confidence', 0.0),
                    signal_reasoning=trade_data.get('signal_reasoning', [])
                )
                self.trade_history.append(trade)

            # Calculate balance from trades
            if trades:
                total_realized_pl = sum(t['realized_pl'] for t in trades)
                self.balance = self.initial_balance + total_realized_pl
                self.total_pnl = total_realized_pl

            # Start monitoring if there are open positions
            if self.open_positions:
                self.start_monitoring()

            print(f"✅ Loaded from database: {len(self.open_positions)} open, {len(self.trade_history)} trades")

        except Exception as e:
            print(f"⚠️ Error loading state from database: {e}")

    def save_state(self, filepath: str = "./paper_trading_state.json"):
        """Save current state to file and database."""
        # Save to database if enabled
        if self.use_database:
            self.save_state_to_db()

        # Also save to JSON for backup
        state = {
            'initial_balance': self.initial_balance,
            'balance': self.balance,
            'equity': self.equity,
            'daily_pnl': self.daily_pnl,
            'total_pnl': self.total_pnl,
            'open_positions': [pos.to_dict() for pos in self.open_positions.values()],
            'trade_history': [trade.to_dict() for trade in self.trade_history],
            'timestamp': datetime.now().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)

    def load_state(self, filepath: str = "./paper_trading_state.json"):
        """Load state from file."""
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)

            self.initial_balance = state.get('initial_balance', self.initial_balance)
            self.balance = state.get('balance', self.balance)
            self.equity = state.get('equity', self.equity)
            self.daily_pnl = state.get('daily_pnl', 0.0)
            self.total_pnl = state.get('total_pnl', 0.0)

            # Load open positions
            for pos_data in state.get('open_positions', []):
                pos_data['entry_time'] = datetime.fromisoformat(pos_data['entry_time'])
                position = PaperPosition(**pos_data)
                self.open_positions[position.position_id] = position

            # Load trade history
            for trade_data in state.get('trade_history', []):
                trade_data['entry_time'] = datetime.fromisoformat(trade_data['entry_time'])
                trade_data['exit_time'] = datetime.fromisoformat(trade_data['exit_time'])
                trade = PaperTrade(**trade_data)
                self.trade_history.append(trade)

            # Restart monitoring if there are open positions
            if self.open_positions:
                self.start_monitoring()

            print(f"✅ Loaded paper trading state: {len(self.open_positions)} open, {len(self.trade_history)} closed")

        except FileNotFoundError:
            print("ℹ️ No previous paper trading state found, starting fresh")
        except Exception as e:
            print(f"⚠️ Error loading state: {e}")


def test_paper_trader():
    """Test the paper trading system."""
    print("Testing Paper Trader...")
    print("="*60)

    # Create trader
    trader = PaperTrader(initial_balance=50000.0)

    print(f"\n💰 Initial Balance: €{trader.balance:,.2f}")
    print(f"📊 Max Positions: {trader.max_positions}")
    print(f"🛡️ Risk Per Trade: {trader.risk_per_trade*100}%")

    # Create a test signal
    from forex_data import ForexSignal

    test_signal = ForexSignal(
        pair='EUR_USD',
        timeframe='5',
        signal='BUY',
        confidence=0.75,
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
        risk_reward_ratio=2.0,
        pips_risk=50.0,
        pips_reward=100.0,
        reasoning=["Test signal", "Paper trading demo"],
        indicators={},
        timestamp=datetime.now()
    )

    print("\n📊 Test Signal:")
    print(f"   {test_signal}")

    # Open position
    print("\n🔄 Opening position...")
    position_id = trader.open_position(test_signal)

    if position_id:
        print(f"\n📈 Open Positions: {len(trader.open_positions)}")
        print(f"💶 Balance: €{trader.balance:,.2f}")
        print(f"💎 Equity: €{trader.equity:,.2f}")

        # Update once
        print("\n🔄 Updating position with live data...")
        trader.update_positions()

        # Show statistics
        stats = trader.get_statistics()
        print("\n📊 Statistics:")
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.2f}")
            else:
                print(f"   {key}: {value}")

    print("\n✓ Paper trader test complete!")
    print("="*60)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_paper_trader()
