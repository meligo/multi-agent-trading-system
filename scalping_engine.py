"""
Scalping Trading Engine

Main orchestration engine for fast momentum scalping.
Implements all critical scalping requirements from SCALPING_STRATEGY_ANALYSIS.md
"""

import time
import threading
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path

from scalping_config import ScalpingConfig
from scalping_agents import (
    create_scalping_agents,
    ScalpSetup,
    FastMomentumAgent,
    TechnicalAgent,
    ScalpValidator,
    AggressiveRiskAgent,
    ConservativeRiskAgent,
    RiskManager
)


@dataclass
class ActiveTrade:
    """Represents an active scalping trade."""
    trade_id: str
    pair: str
    direction: str
    entry_price: float
    take_profit: float
    stop_loss: float
    entry_time: datetime
    position_size: float
    spread_at_entry: float
    status: str = "OPEN"  # OPEN, CLOSED, EXPIRED
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    pnl_pips: Optional[float] = None
    pnl_dollars: Optional[float] = None


@dataclass
class DailyStats:
    """Tracks daily trading statistics."""
    date: str
    trades_taken: int = 0
    trades_won: int = 0
    trades_lost: int = 0
    total_pnl: float = 0.0
    consecutive_losses: int = 0
    last_trade_time: Optional[datetime] = None
    paused_until: Optional[datetime] = None
    spread_costs: float = 0.0


class ScalpingEngine:
    """
    Main scalping engine.

    Responsibilities:
    1. Analyzes pairs every 60 seconds
    2. Runs 2-agent + judge system for entries
    3. Monitors trades with 20-minute auto-close
    4. Enforces spread limits and trading hours
    5. Tracks daily limits and risk controls
    """

    def __init__(self, config: ScalpingConfig = None):
        """Initialize the scalping engine."""
        self.config = config or ScalpingConfig()

        # Validate config
        self.config.validate()

        # Initialize agents
        print("Initializing scalping agents...")
        self.agents = create_scalping_agents(self.config)

        # Trading state
        self.active_trades: Dict[str, ActiveTrade] = {}
        self.daily_stats: DailyStats = DailyStats(date=datetime.now().strftime("%Y-%m-%d"))
        self.running: bool = False
        self.paused: bool = False

        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None

        # Data fetcher (will be injected)
        self.data_fetcher = None

        print("✅ Scalping Engine initialized")
        self.config.display()

    def set_data_fetcher(self, fetcher):
        """Inject data fetcher (forex_data or similar)."""
        self.data_fetcher = fetcher

    # ========================================================================
    # TRADING HOURS CHECK
    # ========================================================================

    def is_trading_hours(self) -> bool:
        """Check if current time is within trading hours (08:00-20:00 GMT)."""
        now = datetime.utcnow().time()

        start_time = self.config.TRADING_START_TIME
        end_time = self.config.TRADING_END_TIME

        is_hours = start_time <= now <= end_time

        if not is_hours:
            current_hour = datetime.utcnow().strftime("%H:%M GMT")
            print(f"⏰ Outside trading hours: {current_hour} (trade: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} GMT)")

        return is_hours

    # ========================================================================
    # SPREAD CHECKING
    # ========================================================================

    def check_spread(self, pair: str) -> Optional[float]:
        """
        Check current spread for a pair.

        Returns:
            Spread in pips, or None if unable to fetch
        """
        if not self.data_fetcher:
            print("⚠️  No data fetcher available, assuming spread = 1.0 pips")
            return 1.0

        try:
            spread = self.data_fetcher.get_current_spread(pair)

            if spread > self.config.MAX_SPREAD_PIPS:
                print(f"❌ Spread too wide for {pair}: {spread:.1f} pips > {self.config.MAX_SPREAD_PIPS} max")
                return spread

            if spread > self.config.SPREAD_PENALTY_THRESHOLD:
                print(f"⚠️  High spread for {pair}: {spread:.1f} pips (will reduce position size)")

            return spread
        except Exception as e:
            print(f"⚠️  Error checking spread for {pair}: {e}")
            return None

    # ========================================================================
    # DAILY LIMITS CHECKING
    # ========================================================================

    def check_daily_limits(self) -> bool:
        """
        Check if daily limits allow trading.

        Returns:
            True if can trade, False if limits exceeded
        """
        # Reset daily stats if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if self.daily_stats.date != today:
            print(f"\n📅 New trading day: {today}")
            self.daily_stats = DailyStats(date=today)

        # Check if paused due to consecutive losses
        if self.daily_stats.paused_until:
            if datetime.now() < self.daily_stats.paused_until:
                remaining = (self.daily_stats.paused_until - datetime.now()).seconds // 60
                if remaining % 5 == 0:  # Log every 5 minutes
                    print(f"⏸️  Paused due to consecutive losses. Resume in {remaining} minutes")
                return False
            else:
                print(f"▶️  Resume trading after pause")
                self.daily_stats.paused_until = None
                self.daily_stats.consecutive_losses = 0

        # Check max trades per day
        if self.daily_stats.trades_taken >= self.config.MAX_TRADES_PER_DAY:
            print(f"🛑 Daily trade limit reached: {self.daily_stats.trades_taken}/{self.config.MAX_TRADES_PER_DAY}")
            return False

        # Check max open positions
        if len(self.active_trades) >= self.config.MAX_OPEN_POSITIONS:
            print(f"🛑 Max open positions: {len(self.active_trades)}/{self.config.MAX_OPEN_POSITIONS}")
            return False

        # Check daily loss limit
        if self.daily_stats.total_pnl <= -self.config.MAX_DAILY_LOSS_PERCENT:
            print(f"🛑 Daily loss limit hit: {self.daily_stats.total_pnl:.2f}% <= -{self.config.MAX_DAILY_LOSS_PERCENT}%")
            return False

        # Check consecutive losses
        if self.daily_stats.consecutive_losses >= self.config.MAX_CONSECUTIVE_LOSSES:
            pause_until = datetime.now() + timedelta(minutes=self.config.PAUSE_AFTER_LOSSES_MINUTES)
            self.daily_stats.paused_until = pause_until
            print(f"⏸️  Pausing for {self.config.PAUSE_AFTER_LOSSES_MINUTES} min after {self.daily_stats.consecutive_losses} losses")
            return False

        return True

    # ========================================================================
    # MARKET DATA PREPARATION
    # ========================================================================

    def fetch_market_data(self, pair: str) -> Optional[Dict]:
        """
        Fetch current market data for a pair.

        Returns:
            Dict with market data, or None if unable to fetch
        """
        if not self.data_fetcher:
            print(f"⚠️  No data fetcher for {pair}")
            return None

        try:
            # Fetch 1-minute data
            data = self.data_fetcher.fetch_data(pair, timeframe="1m", bars=50)

            if not data or len(data) < 20:
                print(f"⚠️  Insufficient data for {pair}")
                return None

            current_price = data['close'].iloc[-1]

            # Calculate simplified indicators for scalping
            indicators = {
                "ema_5": data['close'].ewm(span=5).mean().iloc[-1],
                "ema_10": data['close'].ewm(span=10).mean().iloc[-1],
                "ema_20": data['close'].ewm(span=20).mean().iloc[-1],
                "rsi_14": self._calculate_rsi(data['close'], 14),
                "volume": data['volume'].iloc[-1] if 'volume' in data else 0,
                "volume_avg": data['volume'].rolling(20).mean().iloc[-1] if 'volume' in data else 0,
            }

            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            sma = data['close'].rolling(bb_period).mean().iloc[-1]
            std = data['close'].rolling(bb_period).std().iloc[-1]
            indicators["bb_upper"] = sma + (bb_std * std)
            indicators["bb_lower"] = sma - (bb_std * std)
            indicators["bb_middle"] = sma

            # Support/Resistance (simple high/low)
            recent_high = data['high'].rolling(20).max().iloc[-1]
            recent_low = data['low'].rolling(20).min().iloc[-1]

            # Check spread
            spread = self.check_spread(pair)
            if spread is None:
                return None

            return {
                "pair": pair,
                "current_price": current_price,
                "indicators": indicators,
                "nearest_support": recent_low,
                "nearest_resistance": recent_high,
                "spread": spread,
                "data": data
            }

        except Exception as e:
            print(f"❌ Error fetching data for {pair}: {e}")
            return None

    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator."""
        deltas = prices.diff()
        gain = (deltas.where(deltas > 0, 0)).rolling(window=period).mean()
        loss = (-deltas.where(deltas < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    # ========================================================================
    # AGENT ANALYSIS PIPELINE
    # ========================================================================

    def analyze_pair(self, pair: str) -> Optional[ScalpSetup]:
        """
        Run full agent analysis pipeline for a pair.

        Pipeline:
        1. Fetch market data
        2. Fast Momentum Agent analyzes
        3. Technical Agent analyzes
        4. Scalp Validator (Judge) makes final decision

        Returns:
            ScalpSetup if approved, None otherwise
        """
        print(f"\n{'='*80}")
        print(f"📊 Analyzing {pair} at {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*80}")

        # Fetch data
        market_data = self.fetch_market_data(pair)
        if not market_data:
            return None

        # Run agents
        print(f"\n🚀 Fast Momentum Agent analyzing...")
        momentum_analysis = self.agents["momentum"].analyze(market_data)
        print(f"   Result: {momentum_analysis.get('setup_type', 'NONE')} - {momentum_analysis.get('direction', 'NONE')}")

        print(f"\n🔧 Technical Agent analyzing...")
        technical_analysis = self.agents["technical"].analyze(market_data)
        print(f"   Result: {'Supports' if technical_analysis.get('supports_trade') else 'Rejects'} trade")

        print(f"\n⚖️  Scalp Validator (Judge) deciding...")
        scalp_setup = self.agents["validator"].validate(momentum_analysis, technical_analysis, market_data)

        if scalp_setup.approved:
            print(f"   ✅ APPROVED: {scalp_setup.direction} {scalp_setup.pair}")
            print(f"   Confidence: {scalp_setup.confidence*100:.0f}%, Tier: {scalp_setup.risk_tier}")
        else:
            print(f"   ❌ REJECTED: {scalp_setup.reasoning[0] if scalp_setup.reasoning else 'No reason'}")

        return scalp_setup if scalp_setup.approved else None

    def run_risk_management(self, scalp_setup: ScalpSetup) -> tuple[bool, float]:
        """
        Run risk management debate (Aggressive vs Conservative → Risk Manager).

        Returns:
            Tuple of (execute: bool, position_size: float)
        """
        print(f"\n{'='*80}")
        print(f"⚠️  RISK MANAGEMENT DEBATE")
        print(f"{'='*80}")

        account_state = {
            "trades_today": self.daily_stats.trades_taken,
            "open_positions": len(self.active_trades),
            "daily_pnl": self.daily_stats.total_pnl,
            "consecutive_losses": self.daily_stats.consecutive_losses
        }

        print(f"\n💪 Aggressive Risk Agent analyzing...")
        aggressive = self.agents["aggressive_risk"].analyze(scalp_setup, account_state)
        print(f"   Recommendation: {aggressive.get('recommendation')}")

        print(f"\n🛡️  Conservative Risk Agent analyzing...")
        conservative = self.agents["conservative_risk"].analyze(scalp_setup, account_state)
        print(f"   Recommendation: {conservative.get('recommendation')}")

        print(f"\n⚖️  Risk Manager (Judge) deciding...")
        execute, position_size = self.agents["risk_manager"].decide(
            scalp_setup, aggressive, conservative, account_state
        )

        return execute, position_size

    # ========================================================================
    # TRADE EXECUTION & MONITORING
    # ========================================================================

    def execute_trade(self, scalp_setup: ScalpSetup, position_size: float) -> bool:
        """
        Execute a scalp trade.

        Args:
            scalp_setup: Approved scalp setup
            position_size: Position size in lots

        Returns:
            True if executed successfully
        """
        # Generate trade ID
        trade_id = f"{scalp_setup.pair}_{datetime.now().strftime('%H%M%S')}"

        # Create active trade record
        trade = ActiveTrade(
            trade_id=trade_id,
            pair=scalp_setup.pair,
            direction=scalp_setup.direction,
            entry_price=scalp_setup.entry_price,
            take_profit=scalp_setup.take_profit,
            stop_loss=scalp_setup.stop_loss,
            entry_time=datetime.now(),
            position_size=position_size,
            spread_at_entry=scalp_setup.spread
        )

        # Store trade
        self.active_trades[trade_id] = trade

        # Update daily stats
        self.daily_stats.trades_taken += 1
        self.daily_stats.last_trade_time = datetime.now()

        print(f"\n✅ TRADE EXECUTED: {trade_id}")
        print(f"   {trade.direction} {trade.pair} @ {trade.entry_price:.5f}")
        print(f"   TP: {trade.take_profit:.5f} | SL: {trade.stop_loss:.5f}")
        print(f"   Size: {trade.position_size:.2f} lots")
        print(f"   Max Duration: {self.config.MAX_TRADE_DURATION_MINUTES} minutes")

        return True

    def monitor_trades(self):
        """
        Monitor active trades for exits.

        Checks every 30 seconds:
        1. TP/SL hit
        2. 20-minute duration exceeded
        3. Trailing stop conditions
        """
        while self.running:
            try:
                now = datetime.now()

                for trade_id, trade in list(self.active_trades.items()):
                    if trade.status != "OPEN":
                        continue

                    # Check 20-minute max duration
                    duration = (now - trade.entry_time).total_seconds() / 60

                    if duration >= self.config.MAX_TRADE_DURATION_MINUTES:
                        print(f"\n⏰ 20-MINUTE LIMIT: Force-closing {trade_id}")
                        self.close_trade(trade_id, "MAX_DURATION")
                        continue

                    # Fetch current price
                    current_price = self._get_current_price(trade.pair)
                    if current_price is None:
                        continue

                    # Check TP/SL
                    if trade.direction == "BUY":
                        if current_price >= trade.take_profit:
                            print(f"\n🎯 TAKE PROFIT HIT: {trade_id}")
                            self.close_trade(trade_id, "TAKE_PROFIT", current_price)
                        elif current_price <= trade.stop_loss:
                            print(f"\n🛑 STOP LOSS HIT: {trade_id}")
                            self.close_trade(trade_id, "STOP_LOSS", current_price)
                    else:  # SELL
                        if current_price <= trade.take_profit:
                            print(f"\n🎯 TAKE PROFIT HIT: {trade_id}")
                            self.close_trade(trade_id, "TAKE_PROFIT", current_price)
                        elif current_price >= trade.stop_loss:
                            print(f"\n🛑 STOP LOSS HIT: {trade_id}")
                            self.close_trade(trade_id, "STOP_LOSS", current_price)

                # Sleep for check interval
                time.sleep(self.config.AUTO_CLOSE_CHECK_INTERVAL_SECONDS)

            except Exception as e:
                print(f"❌ Error in trade monitor: {e}")
                time.sleep(5)

    def close_trade(self, trade_id: str, reason: str, exit_price: Optional[float] = None):
        """Close an active trade and update stats."""
        if trade_id not in self.active_trades:
            return

        trade = self.active_trades[trade_id]

        # Get exit price
        if exit_price is None:
            exit_price = self._get_current_price(trade.pair) or trade.entry_price

        # Calculate P&L
        pip_value = 0.0001 if 'JPY' not in trade.pair else 0.01
        if trade.direction == "BUY":
            pnl_pips = (exit_price - trade.entry_price) / pip_value
        else:
            pnl_pips = (trade.entry_price - exit_price) / pip_value

        # Rough P&L in dollars (assuming $10 per pip for 0.1 lot)
        pnl_dollars = pnl_pips * (trade.position_size / 0.1) * 10

        # Update trade
        trade.status = "CLOSED"
        trade.exit_price = exit_price
        trade.exit_time = datetime.now()
        trade.exit_reason = reason
        trade.pnl_pips = pnl_pips
        trade.pnl_dollars = pnl_dollars

        # Update daily stats
        self.daily_stats.total_pnl += (pnl_dollars / 10000) * 100  # Rough % calculation

        if pnl_pips > 0:
            self.daily_stats.trades_won += 1
            self.daily_stats.consecutive_losses = 0
            result_emoji = "✅"
        else:
            self.daily_stats.trades_lost += 1
            self.daily_stats.consecutive_losses += 1
            result_emoji = "❌"

        duration_minutes = (trade.exit_time - trade.entry_time).total_seconds() / 60

        print(f"\n{result_emoji} TRADE CLOSED: {trade_id}")
        print(f"   Reason: {reason}")
        print(f"   P&L: {pnl_pips:+.1f} pips (${pnl_dollars:+.2f})")
        print(f"   Duration: {duration_minutes:.1f} minutes")
        print(f"   Daily Stats: {self.daily_stats.trades_won}W / {self.daily_stats.trades_lost}L")

        # Remove from active trades
        del self.active_trades[trade_id]

    def _get_current_price(self, pair: str) -> Optional[float]:
        """Get current price for a pair."""
        if not self.data_fetcher:
            return None
        try:
            data = self.data_fetcher.fetch_data(pair, timeframe="1m", bars=1)
            return data['close'].iloc[-1] if data is not None and len(data) > 0 else None
        except:
            return None

    # ========================================================================
    # MAIN LOOP
    # ========================================================================

    def run(self):
        """
        Main scalping loop.

        1. Check trading hours
        2. Check daily limits
        3. Analyze each scalping pair
        4. Execute approved scalps
        5. Monitor active trades
        """
        print(f"\n{'='*80}")
        print(f"🚀 SCALPING ENGINE STARTED")
        print(f"{'='*80}\n")

        self.running = True

        # Start trade monitor thread
        self.monitor_thread = threading.Thread(target=self.monitor_trades, daemon=True)
        self.monitor_thread.start()

        try:
            while self.running:
                # Check trading hours
                if not self.is_trading_hours():
                    time.sleep(60)
                    continue

                # Check daily limits
                if not self.check_daily_limits():
                    time.sleep(60)
                    continue

                # Analyze each pair
                for pair in self.config.SCALPING_PAIRS:
                    if not self.running:
                        break

                    try:
                        # Run analysis
                        scalp_setup = self.analyze_pair(pair)

                        if scalp_setup:
                            # Run risk management
                            execute, position_size = self.run_risk_management(scalp_setup)

                            if execute and position_size > 0:
                                self.execute_trade(scalp_setup, position_size)

                    except Exception as e:
                        print(f"❌ Error analyzing {pair}: {e}")

                # Wait for next analysis cycle
                print(f"\n⏳ Next scan in {self.config.ANALYSIS_INTERVAL_SECONDS}s...")
                time.sleep(self.config.ANALYSIS_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print(f"\n\n⏹️  Stopping scalping engine...")
        finally:
            self.stop()

    def stop(self):
        """Stop the scalping engine."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        print(f"\n{'='*80}")
        print(f"📊 DAILY SUMMARY")
        print(f"{'='*80}")
        print(f"Trades: {self.daily_stats.trades_taken}")
        print(f"Wins: {self.daily_stats.trades_won}")
        print(f"Losses: {self.daily_stats.trades_lost}")
        win_rate = (self.daily_stats.trades_won / self.daily_stats.trades_taken * 100) if self.daily_stats.trades_taken > 0 else 0
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Total P&L: {self.daily_stats.total_pnl:+.2f}%")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    # Test engine initialization
    engine = ScalpingEngine()
    print("\n✅ Scalping engine ready")
    print("\nTo run:")
    print("  engine.set_data_fetcher(your_data_source)")
    print("  engine.run()")
