"""
Scalping Trading Engine

Main orchestration engine for fast momentum scalping.
Implements all critical scalping requirements from SCALPING_STRATEGY_ANALYSIS.md
"""

import os
import time
import threading
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from logging_config import setup_file_logging

from scalping_config import ScalpingConfig
from agent_data_logger import (
    AgentDataLogger,
    AnalysisSession,
    MarketSnapshot,
    IndicatorValues,
    AgentResponse,
    JudgeDecision
)
from scalping_indicators import ScalpingIndicators
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
from ig_client import IGClient
from ig_token_refresh import auto_refresh_ig_token

# Load environment variables
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path)

# Setup logging
logger = setup_file_logging("scalping_engine", console_output=False)


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
    deal_id: Optional[str] = None  # IG deal ID for closing position
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

    def __init__(self, config: ScalpingConfig = None, ig_client: Optional[IGClient] = None):
        """Initialize the scalping engine."""
        self.config = config or ScalpingConfig()

        # Validate config
        self.config.validate()

        # Initialize IG client for live trading
        self.account_currency = None
        if ig_client:
            self.ig_client = ig_client
            logger.info(f"✅ Using provided IG client")
            # Try to get account currency
            try:
                account_info = self.ig_client.get_account()
                accounts = account_info.get("accounts", [])
                if accounts:
                    self.account_currency = accounts[0].get("currency", "GBP")
                    logger.info(f"   Account currency: {self.account_currency}")
            except Exception as e:
                logger.warning(f"⚠️  Could not fetch account currency: {e}")
                self.account_currency = "GBP"  # Default fallback
        else:
            # Initialize from environment variables
            api_key = os.getenv("IG_API_KEY")
            username = os.getenv("IG_USERNAME")
            password = os.getenv("IG_PASSWORD")
            is_demo = os.getenv("IG_DEMO", "true").lower() == "true"

            if api_key and username and password:
                base_url = "https://demo-api.ig.com/gateway/deal" if is_demo else "https://api.ig.com/gateway/deal"
                self.ig_client = IGClient(api_key=api_key, base_url=base_url)

                # Login
                try:
                    self.ig_client.create_session(username=username, password=password)
                    mode = "DEMO" if is_demo else "LIVE"
                    logger.info(f"✅ Logged into IG Markets ({mode} mode)")

                    # Fetch account currency
                    try:
                        account_info = self.ig_client.get_account()
                        accounts = account_info.get("accounts", [])
                        if accounts:
                            self.account_currency = accounts[0].get("currency", "GBP")
                            logger.info(f"   Account currency: {self.account_currency}")
                    except Exception as e:
                        logger.warning(f"⚠️  Could not fetch account currency: {e}")
                        self.account_currency = "GBP"  # Default fallback

                except Exception as e:
                    logger.warning(f"⚠️  Failed to login to IG: {e}")
                    logger.warning(f"⚠️  Trading will be paper-only mode")
                    self.ig_client = None
            else:
                logger.warning(f"⚠️  IG credentials not found in .env.scalper")
                logger.warning(f"⚠️  Trading will be paper-only mode")
                self.ig_client = None

        # Initialize agents
        logger.info(f"Initializing scalping agents...")
        self.agents = create_scalping_agents(self.config)

        # Trading state
        self.active_trades: Dict[str, ActiveTrade] = {}
        self.trade_history: List[Dict] = []  # Historical trades for performance stats
        self.daily_stats: DailyStats = DailyStats(date=datetime.now().strftime("%Y-%m-%d"))
        self.running: bool = False
        self.paused: bool = False

        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None

        # Data fetcher (will be injected)
        self.data_fetcher = None

        # Agent data logger (optional - captures all analysis data)
        self.agent_data_logger = None
        self._init_agent_data_logger()

        logger.info(f"✅ Scalping Engine initialized")
        self.config.display()

    def set_data_fetcher(self, fetcher):
        """Inject data fetcher (forex_data or similar)."""
        self.data_fetcher = fetcher

    def _init_agent_data_logger(self):
        """Initialize agent data logger if database is available."""
        try:
            from database_manager import DatabaseManager
            db = DatabaseManager()
            self.agent_data_logger = AgentDataLogger(db.conn_string)
            logger.info("✅ Agent data logger enabled (capturing all analysis data)")
        except Exception as e:
            logger.warning(f"⚠️  Agent data logger disabled: {e}")
            self.agent_data_logger = None

    @property
    def open_trades(self) -> Dict[str, ActiveTrade]:
        """Alias for active_trades (for dashboard compatibility)."""
        return self.active_trades

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
            logger.info(f"⏰ Outside trading hours: {current_hour} (trade: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} GMT)")

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
            logger.warning(f"⚠️  No data fetcher available, assuming spread = 1.0 pips")
            return 1.0

        try:
            spread = self.data_fetcher.get_spread(pair)

            # Handle None spread (data not available yet)
            if spread is None:
                logger.warning(f"⚠️  Spread not available for {pair}, skipping...")
                return None

            if spread > self.config.MAX_SPREAD_PIPS:
                logger.error(f"❌ Spread too wide for {pair}: {spread:.1f} pips > {self.config.MAX_SPREAD_PIPS} max")
                return spread

            if spread > self.config.SPREAD_PENALTY_THRESHOLD:
                logger.warning(f"⚠️  High spread for {pair}: {spread:.1f} pips (will reduce position size)")

            return spread
        except Exception as e:
            logger.warning(f"⚠️  Error checking spread for {pair}: {e}")
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
            logger.info(f"\n📅 New trading day: {today}")
            self.daily_stats = DailyStats(date=today)

        # Check if paused due to consecutive losses
        if self.daily_stats.paused_until:
            if datetime.now() < self.daily_stats.paused_until:
                remaining = (self.daily_stats.paused_until - datetime.now()).seconds // 60
                if remaining % 5 == 0:  # Log every 5 minutes
                    logger.warning(f"⏸️  Paused due to consecutive losses. Resume in {remaining} minutes")
                return False
            else:
                logger.info(f"▶️  Resume trading after pause")
                self.daily_stats.paused_until = None
                self.daily_stats.consecutive_losses = 0

        # Check max trades per day
        if self.daily_stats.trades_taken >= self.config.MAX_TRADES_PER_DAY:
            logger.warning(f"🛑 Daily trade limit reached: {self.daily_stats.trades_taken}/{self.config.MAX_TRADES_PER_DAY}")
            return False

        # Check max open positions
        if len(self.active_trades) >= self.config.MAX_OPEN_POSITIONS:
            logger.warning(f"🛑 Max open positions: {len(self.active_trades)}/{self.config.MAX_OPEN_POSITIONS}")
            return False

        # Check daily loss limit
        if self.daily_stats.total_pnl <= -self.config.MAX_DAILY_LOSS_PERCENT:
            logger.warning(f"🛑 Daily loss limit hit: {self.daily_stats.total_pnl:.2f}% <= -{self.config.MAX_DAILY_LOSS_PERCENT}%")
            return False

        # Check consecutive losses
        if self.daily_stats.consecutive_losses >= self.config.MAX_CONSECUTIVE_LOSSES:
            pause_until = datetime.now() + timedelta(minutes=self.config.PAUSE_AFTER_LOSSES_MINUTES)
            self.daily_stats.paused_until = pause_until
            logger.warning(f"⏸️  Pausing for {self.config.PAUSE_AFTER_LOSSES_MINUTES} min after {self.daily_stats.consecutive_losses} losses")
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
            logger.warning(f"⚠️  No data fetcher for {pair}")
            return None

        try:
            # Use UnifiedDataFetcher (aggregates all sources)
            if hasattr(self.data_fetcher, 'fetch_market_data'):
                # New unified fetcher
                # Request 60 bars (minimum for ATR calculation in pre-trade gates)
                # UnifiedDataFetcher requires 50% of bars minimum, so 60 * 0.5 = 30 bars minimum
                market_data = self.data_fetcher.fetch_market_data(pair, timeframe="1m", bars=60)

                if not market_data or market_data.get('candles') is None:
                    logger.warning(f"⚠️  No candle data for {pair} (0/30 candles - need 30 more)")
                    return None

                data = market_data['candles']

                # We request 60 bars, but UnifiedDataFetcher minimum is 30 (50% of 60)
                # Pre-trade ATR gate needs 60 bars ideally, but will work with 30+
                min_required = 30

                if len(data) < min_required:
                    need_more = min_required - len(data)
                    logger.warning(f"⚠️  Insufficient data for {pair} ({len(data)}/{min_required} candles - need {need_more} more)")
                    return None

                # Store additional market data
                self._current_spread = market_data.get('spread')
                self._current_ta = market_data.get('ta_consensus')
                self._current_patterns = market_data.get('patterns')

            else:
                # Legacy fetcher (old format)
                # Request 60 bars (minimum for ATR calculation in pre-trade gates)
                data = self.data_fetcher.fetch_data(pair, timeframe="1m", bars=60)

                min_required = 30
                if not data or len(data) < min_required:
                    current_count = len(data) if data is not None else 0
                    need_more = min_required - current_count
                    logger.warning(f"⚠️  Insufficient data for {pair} ({current_count}/{min_required} candles - need {need_more} more)")
                    return None

            current_price = data['close'].iloc[-1]

            # Calculate ALL indicators using ScalpingIndicators class
            # OPTIMIZED INDICATORS (from indicator research)
            # EMA Ribbon (3, 6, 12) NOT (5, 10, 20)
            data = ScalpingIndicators.calculate_ema_ribbon(
                data,
                periods=ScalpingConfig.INDICATOR_PARAMS['ema_ribbon']['periods']
            )

            # VWAP with bands (institutional anchor)
            # NOTE: Using tick volume (not real volume) - this is TWAP, not true VWAP
            # Real volume available from DataBento futures (6E, 6B, 6J) - TODO: integrate
            try:
                data = ScalpingIndicators.calculate_vwap(
                    data,
                    session_start_hour=ScalpingConfig.INDICATOR_PARAMS['vwap']['session_start_hour']
                )
            except Exception as e:
                logger.warning(f"VWAP calculation failed (no volume?): {e}")
                # Add dummy VWAP columns if missing
                data['vwap'] = data['close']
                data['above_vwap'] = True
                data['below_vwap'] = False

            # Donchian Channel (15-period breakout)
            data = ScalpingIndicators.calculate_donchian_channel(
                data,
                period=ScalpingConfig.INDICATOR_PARAMS['donchian']['period']
            )

            # RSI(7) NOT RSI(14) - for fast scalping
            data = ScalpingIndicators.calculate_rsi(
                data,
                period=ScalpingConfig.INDICATOR_PARAMS['rsi']['period']
            )

            # ADX(7) for trend strength
            data = ScalpingIndicators.calculate_adx(
                data,
                period=ScalpingConfig.INDICATOR_PARAMS['adx']['period']
            )

            # SuperTrend for trailing stops
            data = ScalpingIndicators.calculate_supertrend(
                data,
                atr_period=ScalpingConfig.INDICATOR_PARAMS['supertrend']['atr_period'],
                multiplier=ScalpingConfig.INDICATOR_PARAMS['supertrend']['multiplier']
            )

            # Bollinger Band Squeeze
            data = ScalpingIndicators.calculate_bollinger_squeeze(data)

            # Volume analysis (TODO: implement if needed)
            # data = ScalpingIndicators.calculate_volume_indicators(data)

            # PROFESSIONAL SCALPING TECHNIQUES
            # 1. Opening Range Breakout (ORB)
            london_orb = ScalpingIndicators.calculate_opening_range(
                data,
                session_start_hour=ScalpingConfig.INDICATOR_PARAMS['opening_range']['london_start'],
                range_minutes=ScalpingConfig.INDICATOR_PARAMS['opening_range']['range_minutes']
            )
            ny_orb = ScalpingIndicators.calculate_opening_range(
                data,
                session_start_hour=ScalpingConfig.INDICATOR_PARAMS['opening_range']['ny_start'],
                range_minutes=ScalpingConfig.INDICATOR_PARAMS['opening_range']['range_minutes']
            )

            # 2. Liquidity Sweep / SFP Detection
            data = ScalpingIndicators.detect_liquidity_sweep(
                data,
                lookback=ScalpingConfig.INDICATOR_PARAMS['liquidity_sweep']['lookback']
            )

            # 3. Inside Bar / Compression
            data = ScalpingIndicators.detect_inside_bars(
                data,
                min_bars=ScalpingConfig.INDICATOR_PARAMS['inside_bar']['min_bars']
            )
            data = ScalpingIndicators.detect_narrow_range(data)

            # 4. Impulse Move Detection
            data = ScalpingIndicators.detect_impulse_move(
                data,
                atr_multiplier=ScalpingConfig.INDICATOR_PARAMS['impulse']['atr_multiplier']
            )

            # 5. First Pullback After Impulse (TODO: implement if needed)
            # data = ScalpingIndicators.detect_first_pullback_after_impulse(data)

            # 6. Floor Pivot Points (from previous day)
            if len(data) >= 1440:  # Need at least 1 day of 1m data
                prev_day_data = data.iloc[-1440:-1]
                pivot_points = ScalpingIndicators.calculate_floor_pivots(
                    prev_high=prev_day_data['high'].max(),
                    prev_low=prev_day_data['low'].min(),
                    prev_close=prev_day_data['close'].iloc[-1]
                )
            else:
                # Fallback if not enough data
                pivot_points = {
                    'PP': current_price,
                    'R1': current_price * 1.001,
                    'S1': current_price * 0.999,
                    'R2': current_price * 1.002,
                    'S2': current_price * 0.998
                }

            # 7. Big Figure Levels
            big_figures = ScalpingIndicators.calculate_big_figures(
                current_price,
                levels=ScalpingConfig.INDICATOR_PARAMS['big_figures']['levels_count']
            )

            # 8. ADR (Average Daily Range) - need daily data
            adr = ScalpingIndicators.calculate_adr(data, period=20)
            current_range = data['high'].iloc[-1] - data['low'].iloc[-1]
            adr_pct_used = (current_range / adr * 100) if adr > 0 else 50

            # 9. London Fix Window Detection
            fix_window_status = ScalpingIndicators.is_fix_window(datetime.now())

            # 10. VWAP Mean Reversion (for choppy markets)
            # Calculate z-score safely (handle None/NaN)
            vwap_std = data['vwap_std'].iloc[-1] if 'vwap_std' in data else None
            if vwap_std and vwap_std > 0 and not pd.isna(vwap_std):
                vwap_z_score = (current_price - data['vwap'].iloc[-1]) / vwap_std
            else:
                vwap_z_score = 0

            # Get thresholds safely
            z_threshold = ScalpingConfig.INDICATOR_PARAMS['vwap_reversion'].get('z_score_threshold', 2.0)
            adx_max = ScalpingConfig.INDICATOR_PARAMS['vwap_reversion'].get('adx_max', 18)
            current_adx = data['adx'].iloc[-1]

            # Check reversion signals with None guards
            vwap_reversion_long = (
                z_threshold is not None and
                adx_max is not None and
                current_adx is not None and
                not pd.isna(current_adx) and
                vwap_z_score < -z_threshold and
                current_adx < adx_max
            )
            vwap_reversion_short = (
                z_threshold is not None and
                adx_max is not None and
                current_adx is not None and
                not pd.isna(current_adx) and
                vwap_z_score > z_threshold and
                current_adx < adx_max
            )

            # Build comprehensive indicators dict
            indicators = {
                # Optimized Momentum Indicators
                "ema_3": data['ema_3'].iloc[-1],
                "ema_6": data['ema_6'].iloc[-1],
                "ema_12": data['ema_12'].iloc[-1],
                "ema_ribbon_bullish": data['ema_ribbon_bullish'].iloc[-1],
                "ema_ribbon_bearish": data['ema_ribbon_bearish'].iloc[-1],
                "vwap": data['vwap'].iloc[-1],
                "above_vwap": data['above_vwap'].iloc[-1],
                "vwap_z_score": vwap_z_score,
                "donchian_upper": data['donchian_upper'].iloc[-1],
                "donchian_lower": data['donchian_lower'].iloc[-1],
                "donchian_breakout_long": data['donchian_breakout_long'].iloc[-1],
                "donchian_breakout_short": data['donchian_breakout_short'].iloc[-1],
                "rsi": data['rsi'].iloc[-1],
                "rsi_bullish": data['rsi_bullish'].iloc[-1],
                "rsi_bearish": data['rsi_bearish'].iloc[-1],
                "adx": data['adx'].iloc[-1],
                "adx_trending": data['adx_trending'].iloc[-1],
                "di_bullish": data['di_bullish'].iloc[-1],
                "di_bearish": data['di_bearish'].iloc[-1],
                "volume_spike": data['volume_spike'].iloc[-1] if 'volume_spike' in data.columns else False,
                "squeeze_on": data['squeeze_on'].iloc[-1] if 'squeeze_on' in data else False,
                "squeeze_off": data['squeeze_off'].iloc[-1] if 'squeeze_off' in data else False,
                "supertrend_direction": data['supertrend_direction'].iloc[-1],

                # Professional Scalping Techniques
                # Handle None values from OR calculations (use 'or' to fallback to current_price)
                "orb_breakout_long": current_price > (london_orb.get('OR_high') or current_price) or current_price > (ny_orb.get('OR_high') or current_price),
                "orb_breakout_short": current_price < (london_orb.get('OR_low') or current_price) or current_price < (ny_orb.get('OR_low') or current_price),
                "in_orb_window": datetime.now().hour in [8, 9, 13, 14],  # London/NY open hours
                "OR_high": max(london_orb.get('OR_high') or current_price, ny_orb.get('OR_high') or current_price),
                "OR_low": min(london_orb.get('OR_low') or current_price, ny_orb.get('OR_low') or current_price),
                "long_sweep_detected": data['long_sweep_detected'].iloc[-1] if 'long_sweep_detected' in data else False,
                "short_sweep_detected": data['short_sweep_detected'].iloc[-1] if 'short_sweep_detected' in data else False,
                "inside_bar_compression": data['inside_bar_compression'].iloc[-1] if 'inside_bar_compression' in data else False,
                "nr_bars": data['nr_bars'].iloc[-1] if 'nr_bars' in data else 0,
                "is_impulse": data['is_impulse'].iloc[-1] if 'is_impulse' in data else False,
                "impulse_direction": data['impulse_direction'].iloc[-1] if 'impulse_direction' in data else 0,
                "first_pullback_detected": data['first_pullback_detected'].iloc[-1] if 'first_pullback_detected' in data else False,
                "pivot_PP": pivot_points['PP'],
                "pivot_R1": pivot_points['R1'],
                "pivot_S1": pivot_points['S1'],
                "pivot_R2": pivot_points['R2'],
                "pivot_S2": pivot_points['S2'],
                "nearest_big_figure": min(big_figures, key=lambda x: abs(x - current_price)),
                "adr_pct_used": adr_pct_used,
                "in_fix_window": fix_window_status['in_fix_window'],
                "fix_type": fix_window_status['fix_type'],
                "vwap_reversion_long": vwap_reversion_long,
                "vwap_reversion_short": vwap_reversion_short,
            }

            # Support/Resistance (simple high/low for backward compatibility)
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
            import traceback
            logger.error(f"❌ Error fetching data for {pair}: {e}")
            logger.info(f"📍 Full traceback:")
            traceback.print_exc()
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
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 Analyzing {pair} at {datetime.now().strftime('%H:%M:%S')}")
        logger.info(f"{'='*80}")

        # Generate unique session ID for this analysis
        session_id = f"{pair}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # Fetch data
        market_data = self.fetch_market_data(pair)
        if not market_data:
            return None

        # Log analysis session start
        if self.agent_data_logger:
            try:
                self.agent_data_logger.log_analysis_session(
                    AnalysisSession(
                        session_id=session_id,
                        pair=pair,
                        timestamp=datetime.now(),
                        current_price=market_data.get('current_price', 0),
                        spread_pips=market_data.get('spread', 0),
                        trading_hours=self.is_trading_hours(),
                        can_trade=self.check_daily_limits()
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to log session: {e}")

        # Log market snapshot
        if self.agent_data_logger:
            try:
                data = market_data.get('data')
                if data is not None:
                    # Convert last 50 candles to JSON
                    candles_df = data[['open', 'high', 'low', 'close', 'volume']].tail(50)
                    candles_json = candles_df.to_json(orient='records')

                    self.agent_data_logger.log_market_snapshot(
                        MarketSnapshot(
                            session_id=session_id,
                            pair=pair,
                            timestamp=datetime.now(),
                            candles_json=candles_json,
                            current_price=market_data.get('current_price', 0),
                            bid=market_data.get('current_price', 0) - market_data.get('spread', 0) / 2,
                            ask=market_data.get('current_price', 0) + market_data.get('spread', 0) / 2,
                            spread=market_data.get('spread', 0),
                            nearest_support=market_data.get('nearest_support'),
                            nearest_resistance=market_data.get('nearest_resistance')
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to log market snapshot: {e}")

        # Log all indicators
        if self.agent_data_logger:
            try:
                data = market_data.get('data')
                if data is not None and len(data) > 0:
                    # Extract latest indicator values
                    last_row = data.iloc[-1]

                    self.agent_data_logger.log_indicators(
                        IndicatorValues(
                            session_id=session_id,
                            pair=pair,
                            timestamp=datetime.now(),
                            # EMA Ribbon
                            ema_3=float(last_row.get('ema_3')) if 'ema_3' in last_row else None,
                            ema_6=float(last_row.get('ema_6')) if 'ema_6' in last_row else None,
                            ema_12=float(last_row.get('ema_12')) if 'ema_12' in last_row else None,
                            ema_alignment=market_data.get('ema_alignment'),
                            # RSI
                            rsi=float(last_row.get('rsi')) if 'rsi' in last_row else None,
                            rsi_zone=market_data.get('rsi_zone'),
                            # MACD
                            macd=float(last_row.get('macd')) if 'macd' in last_row else None,
                            macd_signal=float(last_row.get('macd_signal')) if 'macd_signal' in last_row else None,
                            macd_histogram=float(last_row.get('macd_histogram')) if 'macd_histogram' in last_row else None,
                            macd_cross=market_data.get('macd_cross'),
                            # Bollinger Bands
                            bb_upper=float(last_row.get('bb_upper')) if 'bb_upper' in last_row else None,
                            bb_middle=float(last_row.get('bb_middle')) if 'bb_middle' in last_row else None,
                            bb_lower=float(last_row.get('bb_lower')) if 'bb_lower' in last_row else None,
                            bb_width=float(last_row.get('bb_width')) if 'bb_width' in last_row else None,
                            price_position=market_data.get('price_position'),
                            # Volume
                            volume_ma=float(last_row.get('volume_ma')) if 'volume_ma' in last_row else None,
                            volume_surge=market_data.get('volume_surge'),
                            # Momentum
                            momentum_strength=market_data.get('momentum_strength'),
                            momentum_direction=market_data.get('momentum_direction'),
                            # ATR
                            atr=float(last_row.get('atr')) if 'atr' in last_row else None,
                            atr_pips=market_data.get('atr_pips')
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to log indicators: {e}")

        # Run agents with timeout handling
        logger.info(f"\n🚀 Fast Momentum Agent analyzing...")
        start_time = time.time()
        try:
            momentum_analysis = self.agents["momentum"].analyze(market_data)
            logger.info(f"   Result: {momentum_analysis.get('setup_type', 'NONE')} - {momentum_analysis.get('direction', 'NONE')}")
        except Exception as e:
            logger.info(f"   ⚠️  Timeout/Error: {str(e)[:100]}")
            # Fallback: neutral momentum analysis
            momentum_analysis = {
                "setup_type": "NONE",
                "direction": "NONE",
                "strength": 0.0,
                "reasoning": f"Agent timeout: {str(e)[:50]}"
            }
        execution_time = (time.time() - start_time) * 1000

        # Log Fast Momentum Agent response
        if self.agent_data_logger:
            try:
                self.agent_data_logger.log_agent_response(
                    AgentResponse(
                        session_id=session_id,
                        agent_name="fast_momentum",
                        timestamp=datetime.now(),
                        response_json=json.dumps(momentum_analysis),
                        recommendation=momentum_analysis.get('setup_type'),
                        confidence=momentum_analysis.get('strength'),
                        reasoning=momentum_analysis.get('reasoning'),
                        execution_time_ms=execution_time
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to log momentum agent: {e}")

        logger.info(f"\n🔧 Technical Agent analyzing...")
        start_time = time.time()
        try:
            technical_analysis = self.agents["technical"].analyze(market_data)
            logger.info(f"   Result: {'Supports' if technical_analysis.get('supports_trade') else 'Rejects'} trade")
        except Exception as e:
            logger.info(f"   ⚠️  Timeout/Error: {str(e)[:100]}")
            # Fallback: reject trade
            technical_analysis = {
                "supports_trade": False,
                "reasoning": f"Agent timeout: {str(e)[:50]}"
            }
        execution_time = (time.time() - start_time) * 1000

        # Log Technical Agent response
        if self.agent_data_logger:
            try:
                self.agent_data_logger.log_agent_response(
                    AgentResponse(
                        session_id=session_id,
                        agent_name="technical",
                        timestamp=datetime.now(),
                        response_json=json.dumps(technical_analysis),
                        recommendation="SUPPORT" if technical_analysis.get('supports_trade') else "REJECT",
                        confidence=technical_analysis.get('confidence'),
                        reasoning=technical_analysis.get('reasoning'),
                        execution_time_ms=execution_time
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to log technical agent: {e}")

        logger.info(f"\n⚖️  Scalp Validator (Judge) deciding...")
        start_time = time.time()
        try:
            scalp_setup = self.agents["validator"].validate(momentum_analysis, technical_analysis, market_data)
        except Exception as e:
            logger.info(f"   ⚠️  Timeout/Error: {str(e)[:100]}")
            # Fallback: create rejected setup
            from scalping_agents import ScalpSetup
            scalp_setup = ScalpSetup(
                pair=pair,
                direction="NONE",
                entry_price=market_data.get('current_price', 0),
                take_profit=0,
                stop_loss=0,
                confidence=0.0,
                reasoning=[f"Validator timeout: {str(e)[:50]}"],
                indicators={},
                spread=market_data.get('spread', 1.0),
                risk_tier=3,
                approved=False
            )
        execution_time = (time.time() - start_time) * 1000

        if scalp_setup.approved:
            logger.info(f"   ✅ APPROVED: {scalp_setup.direction} {scalp_setup.pair}")
            logger.info(f"   Confidence: {scalp_setup.confidence*100:.0f}%, Tier: {scalp_setup.risk_tier}")
        else:
            logger.info(f"   ❌ REJECTED: {scalp_setup.reasoning[0] if scalp_setup.reasoning else 'No reason'}")

        # Log Scalp Validator decision
        if self.agent_data_logger:
            try:
                from dataclasses import asdict
                self.agent_data_logger.log_judge_decision(
                    JudgeDecision(
                        session_id=session_id,
                        judge_name="scalp_validator",
                        timestamp=datetime.now(),
                        approved=scalp_setup.approved,
                        decision_json=json.dumps(asdict(scalp_setup), default=str),
                        direction=scalp_setup.direction,
                        entry_price=scalp_setup.entry_price,
                        take_profit=scalp_setup.take_profit,
                        stop_loss=scalp_setup.stop_loss,
                        position_size=None,  # Set by Risk Manager
                        confidence=scalp_setup.confidence,
                        risk_tier=scalp_setup.risk_tier,
                        reasoning='; '.join(scalp_setup.reasoning) if scalp_setup.reasoning else None,
                        execution_time_ms=execution_time
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to log validator decision: {e}")

        # Store session_id for risk management logging
        if scalp_setup.approved:
            scalp_setup.session_id = session_id  # Add session_id to scalp_setup

        return scalp_setup if scalp_setup.approved else None

    def run_risk_management(self, scalp_setup: ScalpSetup) -> tuple[bool, float]:
        """
        Run risk management debate (Aggressive vs Conservative → Risk Manager).

        Returns:
            Tuple of (execute: bool, position_size: float)
        """
        logger.info(f"\n{'='*80}")
        logger.warning(f"⚠️  RISK MANAGEMENT DEBATE")
        logger.info(f"{'='*80}")

        account_state = {
            "trades_today": self.daily_stats.trades_taken,
            "open_positions": len(self.active_trades),
            "daily_pnl": self.daily_stats.total_pnl,
            "consecutive_losses": self.daily_stats.consecutive_losses
        }

        # Get session_id from scalp_setup (added during validation)
        session_id = getattr(scalp_setup, 'session_id', None)

        logger.info(f"\n💪 Aggressive Risk Agent analyzing...")
        start_time = time.time()
        aggressive = self.agents["aggressive_risk"].analyze(scalp_setup, account_state)
        logger.info(f"   Recommendation: {aggressive.get('recommendation')}")
        execution_time = (time.time() - start_time) * 1000

        # Log Aggressive Risk Agent
        if self.agent_data_logger and session_id:
            try:
                self.agent_data_logger.log_agent_response(
                    AgentResponse(
                        session_id=session_id,
                        agent_name="aggressive_risk",
                        timestamp=datetime.now(),
                        response_json=json.dumps(aggressive),
                        recommendation=aggressive.get('recommendation'),
                        confidence=aggressive.get('confidence'),
                        reasoning=aggressive.get('reasoning'),
                        execution_time_ms=execution_time
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to log aggressive risk agent: {e}")

        logger.info(f"\n🛡️  Conservative Risk Agent analyzing...")
        start_time = time.time()
        conservative = self.agents["conservative_risk"].analyze(scalp_setup, account_state)
        logger.info(f"   Recommendation: {conservative.get('recommendation')}")
        execution_time = (time.time() - start_time) * 1000

        # Log Conservative Risk Agent
        if self.agent_data_logger and session_id:
            try:
                self.agent_data_logger.log_agent_response(
                    AgentResponse(
                        session_id=session_id,
                        agent_name="conservative_risk",
                        timestamp=datetime.now(),
                        response_json=json.dumps(conservative),
                        recommendation=conservative.get('recommendation'),
                        confidence=conservative.get('confidence'),
                        reasoning=conservative.get('reasoning'),
                        execution_time_ms=execution_time
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to log conservative risk agent: {e}")

        logger.info(f"\n⚖️  Risk Manager (Judge) deciding...")
        start_time = time.time()
        execute, position_size = self.agents["risk_manager"].decide(
            scalp_setup, aggressive, conservative, account_state
        )
        execution_time = (time.time() - start_time) * 1000

        # Log Risk Manager decision
        if self.agent_data_logger and session_id:
            try:
                self.agent_data_logger.log_judge_decision(
                    JudgeDecision(
                        session_id=session_id,
                        judge_name="risk_manager",
                        timestamp=datetime.now(),
                        approved=execute,
                        decision_json=json.dumps({
                            'execute': execute,
                            'position_size': position_size,
                            'aggressive': aggressive,
                            'conservative': conservative
                        }),
                        direction=scalp_setup.direction,
                        entry_price=scalp_setup.entry_price,
                        take_profit=scalp_setup.take_profit,
                        stop_loss=scalp_setup.stop_loss,
                        position_size=position_size if execute else 0,
                        confidence=scalp_setup.confidence,
                        risk_tier=scalp_setup.risk_tier,
                        reasoning=f"Execute: {execute}, Size: {position_size:.2f} lots",
                        execution_time_ms=execution_time
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to log risk manager decision: {e}")

        return execute, position_size

    # ========================================================================
    # TRADE EXECUTION & MONITORING
    # ========================================================================

    @auto_refresh_ig_token(max_retries=3, retry_delay=2)
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

        # Get IG epic code
        epic = self.config.IG_EPIC_MAP.get(scalp_setup.pair)
        if not epic:
            logger.warning(f"⚠️  No IG epic found for {scalp_setup.pair}")
            return False

        deal_id = None

        # Execute on IG if client is available
        if self.ig_client:
            try:
                logger.info(f"\n📤 Sending order to IG Markets...")
                logger.info(f"   Epic: {epic}")
                logger.info(f"   Direction: {scalp_setup.direction}")
                logger.info(f"   Size: {position_size} lots")

                # Calculate pip distances correctly
                # JPY pairs: 2 decimals (0.01 = 1 pip), Others: 4 decimals (0.0001 = 1 pip)
                pip_multiplier = 100 if 'JPY' in scalp_setup.pair else 10000

                limit_pips = abs(scalp_setup.take_profit - scalp_setup.entry_price) * pip_multiplier
                stop_pips = abs(scalp_setup.entry_price - scalp_setup.stop_loss) * pip_multiplier

                logger.info(f"   TP Distance: {limit_pips:.1f} pips")
                logger.info(f"   SL Distance: {stop_pips:.1f} pips")
                logger.info(f"   Currency: {self.account_currency or 'GBP'}")

                # Create position on IG
                response = self.ig_client.create_position(
                    epic=epic,
                    direction=scalp_setup.direction,
                    size=position_size,
                    order_type="MARKET",
                    limit_distance=limit_pips,
                    stop_distance=stop_pips,
                    guaranteed_stop=False,  # Must be explicitly False (not None)
                    force_open=True,
                    currency_code=self.account_currency or "GBP",  # Required by IG API
                    deal_reference=trade_id
                )

                deal_id = response.get("dealReference") or response.get("dealId")
                logger.info(f"✅ IG Order Accepted!")
                logger.info(f"   Deal ID: {deal_id}")

            except Exception as e:
                logger.error(f"❌ IG Order Failed: {e}")
                logger.warning(f"⚠️  Falling back to paper trading")
                deal_id = None
        else:
            logger.info(f"\n📝 Paper Trading Mode (No IG client)")

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
            spread_at_entry=scalp_setup.spread,
            deal_id=deal_id  # Store IG deal ID
        )

        # Store trade
        self.active_trades[trade_id] = trade

        # Update daily stats
        self.daily_stats.trades_taken += 1
        self.daily_stats.last_trade_time = datetime.now()

        mode = "LIVE" if deal_id else "PAPER"
        logger.info(f"\n✅ TRADE EXECUTED ({mode}): {trade_id}")
        logger.info(f"   {trade.direction} {trade.pair} @ {trade.entry_price:.5f}")
        logger.info(f"   TP: {trade.take_profit:.5f} | SL: {trade.stop_loss:.5f}")
        logger.info(f"   Size: {trade.position_size:.2f} lots")
        if deal_id:
            logger.info(f"   IG Deal ID: {deal_id}")
        logger.info(f"   Max Duration: {self.config.MAX_TRADE_DURATION_MINUTES} minutes")

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
                        logger.info(f"\n⏰ 20-MINUTE LIMIT: Force-closing {trade_id}")
                        self.close_trade(trade_id, "MAX_DURATION")
                        continue

                    # Fetch current price
                    current_price = self._get_current_price(trade.pair)
                    if current_price is None:
                        continue

                    # Check TP/SL
                    if trade.direction == "BUY":
                        if current_price >= trade.take_profit:
                            logger.info(f"\n🎯 TAKE PROFIT HIT: {trade_id}")
                            self.close_trade(trade_id, "TAKE_PROFIT", current_price)
                        elif current_price <= trade.stop_loss:
                            logger.info(f"\n🛑 STOP LOSS HIT: {trade_id}")
                            self.close_trade(trade_id, "STOP_LOSS", current_price)
                    else:  # SELL
                        if current_price <= trade.take_profit:
                            logger.info(f"\n🎯 TAKE PROFIT HIT: {trade_id}")
                            self.close_trade(trade_id, "TAKE_PROFIT", current_price)
                        elif current_price >= trade.stop_loss:
                            logger.info(f"\n🛑 STOP LOSS HIT: {trade_id}")
                            self.close_trade(trade_id, "STOP_LOSS", current_price)

                # Sleep for check interval
                time.sleep(self.config.AUTO_CLOSE_CHECK_INTERVAL_SECONDS)

            except Exception as e:
                logger.error(f"❌ Error in trade monitor: {e}")
                time.sleep(5)

    @auto_refresh_ig_token(max_retries=3, retry_delay=2)
    def close_trade(self, trade_id: str, reason: str, exit_price: Optional[float] = None):
        """Close an active trade and update stats."""
        if trade_id not in self.active_trades:
            return

        trade = self.active_trades[trade_id]

        # Close on IG if we have a deal_id
        if trade.deal_id and self.ig_client:
            try:
                logger.info(f"\n📤 Closing position on IG Markets...")
                logger.info(f"   Deal ID: {trade.deal_id}")
                logger.info(f"   Reason: {reason}")

                # Close the position (use opposite direction)
                close_direction = "SELL" if trade.direction == "BUY" else "BUY"

                response = self.ig_client.close_position(
                    deal_id=trade.deal_id,
                    size=trade.position_size,
                    direction=close_direction,
                    order_type="MARKET"
                )

                logger.info(f"✅ IG Position Closed!")
                logger.info(f"   Deal Reference: {response.get('dealReference')}")

            except Exception as e:
                logger.warning(f"⚠️  IG close failed: {e}")
                logger.info(f"   (Trade will still be closed locally)")

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

        logger.info(f"\n{result_emoji} TRADE CLOSED: {trade_id}")
        logger.info(f"   Reason: {reason}")
        logger.info(f"   P&L: {pnl_pips:+.1f} pips (${pnl_dollars:+.2f})")
        logger.info(f"   Duration: {duration_minutes:.1f} minutes")
        logger.info(f"   Daily Stats: {self.daily_stats.trades_won}W / {self.daily_stats.trades_lost}L")

        # Add to trade history for performance stats
        self.trade_history.append({
            'trade_id': trade_id,
            'pair': trade.pair,
            'direction': trade.direction,
            'entry_price': trade.entry_price,
            'exit_price': exit_price,
            'entry_time': trade.entry_time,
            'exit_time': trade.exit_time,
            'pnl': pnl_dollars,
            'pnl_pips': pnl_pips,
            'reason': reason,
            'duration_minutes': duration_minutes
        })

        # Remove from active trades (open_trades is a property alias, no need to delete separately)
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
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 SCALPING ENGINE STARTED")
        logger.info(f"{'='*80}\n")

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
                        logger.error(f"❌ Error analyzing {pair}: {e}")

                # Wait for next analysis cycle
                logger.info(f"\n⏳ Next scan in {self.config.ANALYSIS_INTERVAL_SECONDS}s...")
                time.sleep(self.config.ANALYSIS_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info(f"\n\n⏹️  Stopping scalping engine...")
        finally:
            self.stop()

    def stop(self):
        """Stop the scalping engine."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        logger.info(f"\n{'='*80}")
        logger.info(f"📊 DAILY SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Trades: {self.daily_stats.trades_taken}")
        logger.info(f"Wins: {self.daily_stats.trades_won}")
        logger.info(f"Losses: {self.daily_stats.trades_lost}")
        win_rate = (self.daily_stats.trades_won / self.daily_stats.trades_taken * 100) if self.daily_stats.trades_taken > 0 else 0
        logger.info(f"Win Rate: {win_rate:.1f}%")
        logger.info(f"Total P&L: {self.daily_stats.total_pnl:+.2f}%")
        logger.info(f"{'='*80}\n")

    # ========================================================================
    # DASHBOARD API METHODS
    # ========================================================================

    def get_performance_stats(self) -> Dict:
        """Get current performance statistics for dashboard."""
        stats = {
            'total_trades': len(self.trade_history),
            'open_positions': len(self.open_trades),
            'daily_pnl': sum([t['pnl'] for t in self.trade_history]),
            'profit_factor': 0.0,
            'win_rate': 0.0,
            'avg_trade_duration_minutes': 0.0,
        }

        if len(self.trade_history) > 0:
            wins = [t for t in self.trade_history if t['pnl'] > 0]
            losses = [t for t in self.trade_history if t['pnl'] < 0]

            stats['win_rate'] = (len(wins) / len(self.trade_history)) * 100

            total_wins = sum([t['pnl'] for t in wins])
            total_losses = abs(sum([t['pnl'] for t in losses]))

            if total_losses > 0:
                stats['profit_factor'] = total_wins / total_losses

            durations = [(t['exit_time'] - t['entry_time']).total_seconds() / 60
                        for t in self.trade_history]
            stats['avg_trade_duration_minutes'] = sum(durations) / len(durations)

        return stats

    def get_current_spread(self, pair: str) -> float:
        """Get current spread for a pair (mock for now)."""
        # TODO: Integrate with actual IG API spread data
        # For now, return realistic spreads
        spreads = {
            'EUR_USD': 0.8,
            'GBP_USD': 1.2,
            'USD_JPY': 0.9,
        }
        return spreads.get(pair, 1.5)

    def get_open_positions(self) -> List[Dict]:
        """Get list of currently open positions for dashboard."""
        positions = []
        for trade in self.open_trades:
            # Calculate current P&L (mock for now)
            current_price = trade['entry_price'] * 1.0001  # Mock price movement
            pips_move = (current_price - trade['entry_price']) * 10000

            if trade['direction'] == 'SHORT':
                pips_move = -pips_move

            current_pnl = pips_move * 10  # $10 per pip for 1.0 lot

            positions.append({
                'pair': trade['pair'],
                'direction': trade['direction'],
                'entry_price': trade['entry_price'],
                'take_profit': trade['take_profit'],
                'stop_loss': trade['stop_loss'],
                'entry_time': trade['entry_time'],
                'current_pnl': current_pnl,
                'pips_pnl': pips_move,
            })

        return positions

    def get_recent_debates(self) -> List[Dict]:
        """Get recent agent debates for dashboard display."""
        # Return stored debates (if we implement debate storage)
        # For now, return empty list
        return []

    def get_trade_history(self) -> List[Dict]:
        """Get completed trade history."""
        return self.trade_history


if __name__ == "__main__":
    # Test engine initialization
    engine = ScalpingEngine()
    logger.info(f"\n✅ Scalping engine ready")
    logger.info(f"\nTo run:")
    logger.info(f"  engine.set_data_fetcher(your_data_source)")
    logger.info(f"  engine.run()")
