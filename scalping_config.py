"""
Scalping Strategy Configuration

10-20 minute "Fast Momentum" scalping strategy
Optimized for high-frequency trading on EUR/USD, GBP/USD, USD/JPY
"""

import os
from typing import List, Dict
from datetime import time
from pathlib import Path
from dotenv import load_dotenv

# Load scalping-specific environment variables
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path)


class ScalpingConfig:
    """Configuration for scalping trading system."""

    # ============================================================================
    # STRATEGY PARAMETERS (Critical for Scalping)
    # ============================================================================

    # Trade Duration
    MAX_TRADE_DURATION_MINUTES: int = 20  # Force-close after 20 minutes
    MIN_TRADE_DURATION_SECONDS: int = 30  # Minimum hold time before exit

    # Profit/Loss Targets (SCALPING OPTIMIZED)
    TAKE_PROFIT_PIPS: float = 10.0  # 10 pip target (conservative scalping)
    STOP_LOSS_PIPS: float = 6.0     # 6 pip stop (1.67:1 R:R)
    RISK_REWARD_RATIO: float = 1.67  # Minimum acceptable R:R

    # Alternative aggressive settings (user can switch)
    AGGRESSIVE_TP_PIPS: float = 8.0
    AGGRESSIVE_SL_PIPS: float = 5.0

    # ============================================================================
    # DYNAMIC SL/TP CONFIGURATION (Research-Backed)
    # ============================================================================

    # Toggle dynamic SL/TP (set to True to use ATR-based dynamic levels)
    DYNAMIC_SLTP_ENABLED: bool = True

    # ATR-Based Volatility Scaling Parameters
    # Based on academic research: Kaminski & Lo (2014), Moreira & Muir (2017)
    ATR_PERIOD: int = 14                    # Bars to calculate ATR
    ATR_MULTIPLIER_SL: float = 0.8          # SL = 0.8 × ATR (conservative)
    ATR_MULTIPLIER_TP: float = 1.2          # TP = 1.2 × ATR (1.5:1 R:R)
    ATR_MULTIPLIER_TRAIL: float = 1.0       # Trailing = 1.0 × ATR

    # Buffer Parameters (avoid stop-hunting)
    BUFFER_SPREAD_MULT: float = 1.5         # Buffer = 1.5 × spread
    BUFFER_ATR_MULT: float = 0.1            # Buffer += 0.1 × ATR

    # Time-Based Governance (alpha decay exits)
    TIMEOUT_MINUTES: int = 12               # Hard timeout for scalps
    TIME_DECAY_LAMBDA: float = 1.2          # Stop-tightening rate

    # Break-Even Trigger
    BREAKEVEN_TRIGGER: float = 0.6          # Move to BE after 0.6 × ATR profit

    # Market Structure Analysis
    USE_MARKET_STRUCTURE: bool = True       # Consider swings/pivots
    SWING_LOOKBACK_BARS: int = 20           # Bars to find swing levels

    # Dynamic SL/TP Range Constraints (safety limits)
    MIN_SL_PIPS: float = 4.0                # Minimum stop loss
    MAX_SL_PIPS: float = 12.0               # Maximum stop loss
    MIN_TP_PIPS: float = 6.0                # Minimum take profit
    MAX_TP_PIPS: float = 20.0               # Maximum take profit

    # Spread Limits (CRITICAL for scalping profitability)
    MAX_SPREAD_PIPS: float = 1.2    # Reject trades if spread > 1.2 pips
    IDEAL_SPREAD_PIPS: float = 0.8  # Ideal spread for full position size
    SPREAD_PENALTY_THRESHOLD: float = 1.0  # Reduce size if spread > 1.0

    # ============================================================================
    # PAIRS & TIMEFRAME (Scalping-Optimized)
    # ============================================================================

    # Only trade 3 lowest-spread pairs
    SCALPING_PAIRS: List[str] = [
        "EUR_USD",  # Primary (spread: 0.6-1.0 pips)
        "GBP_USD",  # Secondary (spread: 0.8-1.5 pips)
        "USD_JPY",  # Tertiary (spread: 0.6-1.2 pips)
    ]

    # Timeframe
    PRIMARY_TIMEFRAME: str = "1m"    # 1-minute candles for scalping
    ANALYSIS_INTERVAL_SECONDS: int = 60  # Analyze every 60 seconds

    # ============================================================================
    # TRADING HOURS (London/NY Sessions Only)
    # ============================================================================

    TRADING_START_TIME: time = time(8, 0)   # 08:00 GMT (London open)
    TRADING_END_TIME: time = time(20, 0)    # 20:00 GMT (NY close)

    # Best trading windows (tightest spreads, highest volume)
    PRIME_HOURS: List[Dict[str, time]] = [
        {"start": time(8, 0), "end": time(12, 0), "name": "London Session"},
        {"start": time(12, 0), "end": time(16, 0), "name": "London/NY Overlap ⭐"},  # BEST
        {"start": time(16, 0), "end": time(20, 0), "name": "NY Session"},
    ]

    # ============================================================================
    # POSITION SIZING (Tiered for Scalping)
    # ============================================================================

    # Position sizes based on setup quality
    TIER1_SIZE: float = 0.2      # 100% size for highest confidence
    TIER2_SIZE: float = 0.15     # 75% size for moderate confidence
    TIER3_SIZE: float = 0.0      # Don't trade weak setups in scalping

    # Spread-adjusted sizing
    REDUCE_SIZE_HIGH_SPREAD: bool = True  # Reduce size when spread 1.0-1.2 pips

    # ============================================================================
    # RISK MANAGEMENT (Daily Limits)
    # ============================================================================

    MAX_TRADES_PER_DAY: int = 40        # Maximum scalps per day
    MAX_OPEN_POSITIONS: int = 2         # Maximum simultaneous positions
    MAX_DAILY_LOSS_PERCENT: float = 1.5 # Stop trading at -1.5% daily loss
    MAX_CONSECUTIVE_LOSSES: int = 5     # Pause 30 min after 5 losses
    PAUSE_AFTER_LOSSES_MINUTES: int = 30

    # ============================================================================
    # INDICATORS (Optimized for 1-Minute Scalping)
    # ============================================================================

    # Indicators based on GPT-5 analysis and academic research
    # Optimized for 10-20 minute holds on 1-minute charts

    ENABLED_INDICATORS: List[str] = [
        # Trend/Bias (Fast EMA Ribbon)
        "ema_3",          # Ultra-fast trend (replaces ema_5)
        "ema_6",          # Fast trend (replaces ema_10)
        "ema_12",         # Medium trend (replaces ema_20)

        # Institutional Anchor
        "vwap",           # Session VWAP (critical for intraday)
        "vwap_bands",     # ±1σ and ±2σ deviation bands

        # Breakout Structure
        "donchian_15",    # Donchian Channel (micro-range breakout)
        "bb_squeeze",     # Bollinger vs Keltner squeeze detection

        # Momentum/Strength
        "rsi_7",          # Fast RSI for scalping (NOT 14)
        "adx_7",          # Trend strength filter (fast version)

        # Volatility/Risk
        "atr_5",          # ATR for stop/sizing validation
        "supertrend",     # ATR-based trailing stop

        # Volume
        "volume",         # Tick volume confirmation
        "volume_spike",   # 2x average volume trigger
    ]

    # Indicator Parameters (1-minute optimized)
    INDICATOR_PARAMS: Dict[str, Dict[str, any]] = {
        "ema_ribbon": {"periods": [3, 6, 12]},  # Fast ribbon
        "rsi": {"period": 7, "overbought": 70, "oversold": 30, "momentum_level": 50},
        "adx": {"period": 7, "threshold": 18},  # >18 and rising = trend
        "vwap": {"session_start_hour": 8},  # Anchor at 08:00 GMT (London)
        "vwap_bands": {"std_devs": [1.0, 2.0]},  # ±1σ, ±2σ
        "vwap_reversion": {"z_score_threshold": 2.0, "adx_max": 18},  # Mean reversion when ADX < 18
        "donchian": {"period": 15},  # 15-bar high/low (approx hold horizon)
        "bb_squeeze": {"bb_period": 20, "bb_std": 2.0, "kc_period": 20, "kc_mult": 1.5},
        "supertrend": {"atr_period": 7, "multiplier": 1.5},
        "atr": {"period": 5},
        "volume_spike": {"multiplier": 2.0},  # 2x average volume
        # NEW: Professional techniques
        "opening_range": {"range_minutes": 15, "london_start": 8, "ny_start": 13},
        "liquidity_sweep": {"lookback": 2},  # Check 2 candles for close back inside
        "inside_bar": {"min_bars": 3},  # Min 3 consecutive inside bars
        "narrow_range": {"period": 4},  # NR4 pattern
        "impulse": {"atr_multiplier": 1.5},  # Candle ≥ 1.5x ATR
        "adr": {"period": 20},  # 20-day average daily range
        "big_figures": {"levels_count": 5},  # Generate 5 levels above/below
    }

    # Remove slow/lagging indicators for scalping
    DISABLED_INDICATORS: List[str] = [
        "macd",           # Too slow for 1-minute (12,26,9)
        "sma_50",         # Irrelevant for 10-20 min trades
        "sma_200",        # Irrelevant for 10-20 min trades
        "rsi_14",         # Too slow, use RSI(7) instead
        "ema_20",         # Too slow, use EMA(12) instead
        "ichimoku",       # Too slow and complex
        "divergence",     # Takes too long to develop
        "fvg",            # Macro structure, not scalping
        "vpvr",           # Too complex for 10-min trades
        "bollinger_mean_reversion",  # Counter-trend is risky in momentum scalping
    ]

    # ============================================================================
    # ENTRY SIGNALS (Fast Momentum Triggers - Optimized)
    # ============================================================================

    # Entry logic based on GPT-5 + research recommendations
    ENTRY_TRIGGERS: Dict[str, bool] = {
        # Original triggers
        "ema_ribbon_aligned": True,     # EMA 3>6>12 (long) or 3<6<12 (short)
        "above_vwap": True,             # Price above VWAP (long) / below (short)
        "donchian_breakout": True,      # Close outside Donchian channel
        "bb_squeeze_release": True,     # Squeeze → expansion
        "rsi_momentum": True,           # RSI(7) > 55 (long) or < 45 (short)
        "adx_trending": True,           # ADX(7) > 18 and rising
        "volume_spike": True,           # 2x average volume

        # NEW: Professional techniques
        "opening_range_breakout": True,  # ORB at London/NY opens
        "liquidity_sweep_fade": True,    # Fade stop-run reversals (SFP)
        "pivot_bounce": True,            # Bounce off S1/R1 levels
        "pivot_break_retest": True,      # Break and retest S1/R1
        "big_figure_bounce": True,       # Bounce at 00/25/50/75
        "big_figure_break": True,        # Break through big figures
        "inside_bar_breakout": True,     # Compression → expansion
        "impulse_pullback": True,        # First pullback after impulse
        "vwap_z_reversion": True,        # Mean reversion at 2σ (when ADX < 18)
        "adr_extreme_fade": True,        # Fade when day's range > 1.2x ADR
        "fix_flow_drift": False,         # Pre-fix drift (15:40-15:55) - RISKY
        "fix_flow_fade": True,           # Post-fix fade (16:00-16:10)
    }

    # Entry template (original + new techniques):
    # TIER 1 LONG: Price > VWAP, EMA 3>6>12 (rising), ADX>18, RSI>55, Donchian breakout, Volume spike
    # TIER 1 ORB LONG: Price > OR_high, Price > VWAP, ADX > 20, within 20min of London/NY open
    # TIER 1 SFP LONG: Liquidity sweep below Donchian, close back inside, RSI divergence
    # TIER 1 PIVOT LONG: Price bounces at S1, VWAP distance > 1.5σ, RSI < 30, target PP/VWAP

    # Minimum confirmations required
    MIN_ENTRY_CONFIRMATIONS: int = 3  # Need 3+ signals (reduced from 4 due to more signal types)

    # ============================================================================
    # EXIT RULES (Critical for Scalping)
    # ============================================================================

    EXIT_CONDITIONS: Dict[str, bool] = {
        "take_profit_hit": True,         # TP reached (10 pips)
        "stop_loss_hit": True,           # SL hit (6 pips)
        "max_duration": True,            # 20-minute force close
        "trailing_stop": True,           # Lock profits with trailing stop
        "momentum_reversal": True,       # Exit on momentum shift
    }

    # Trailing stop settings
    TRAILING_STOP_ENABLED: bool = True
    TRAILING_STOP_ACTIVATION_PIPS: float = 6.0  # Activate after 6 pips profit
    TRAILING_STOP_DISTANCE_PIPS: float = 4.0    # Trail 4 pips behind price

    # ============================================================================
    # CLAUDE VALIDATOR (Background Mode for Scalping)
    # ============================================================================

    # Don't validate individual trades (too slow)
    # Instead, Claude pre-approves market conditions
    CLAUDE_MODE: str = "background"  # Options: "per_trade", "background", "disabled"
    CLAUDE_VALIDATION_INTERVAL_SECONDS: int = 120  # Check market every 2 minutes
    CLAUDE_TIMEOUT_SECONDS: int = 3  # Fast timeout for scalping

    # ============================================================================
    # MONITORING & ALERTS
    # ============================================================================

    AUTO_CLOSE_CHECK_INTERVAL_SECONDS: int = 30  # Check for 20-min timeout every 30s
    SPREAD_CHECK_BEFORE_TRADE: bool = True       # Always verify spread before entry

    # Performance tracking
    TRACK_METRICS: List[str] = [
        "win_rate",
        "profit_factor",
        "avg_trade_duration",
        "spread_cost_percentage",
        "trades_per_hour",
        "best_trading_hours",
    ]

    # ============================================================================
    # API CONFIGURATION
    # ============================================================================

    # IG API
    IG_API_KEY: str = os.getenv("IG_API_KEY", "")
    IG_USERNAME: str = os.getenv("IG_USERNAME", "")
    IG_PASSWORD: str = os.getenv("IG_PASSWORD", "")
    IG_ACC_NUMBER: str = os.getenv("IG_ACC_NUMBER", "")
    IG_DEMO: bool = os.getenv("IG_DEMO", "true").lower() == "true"

    # OpenAI for agents
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # LangSmith Tracing
    LANGSMITH_TRACING: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    LANGSMITH_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "scalping-engine")

    # ============================================================================
    # IG EPIC MAPPING (for scalping pairs only)
    # ============================================================================

    IG_EPIC_MAP: Dict[str, str] = {
        "EUR_USD": "CS.D.EURUSD.MINI.IP",  # Spread: 0.6-1.0 pips
        "GBP_USD": "CS.D.GBPUSD.MINI.IP",  # Spread: 0.8-1.5 pips
        "USD_JPY": "CS.D.USDJPY.MINI.IP",  # Spread: 0.6-1.2 pips
    }

    # ============================================================================
    # REALISTIC EXPECTATIONS (Documentation)
    # ============================================================================

    EXPECTED_PERFORMANCE: Dict[str, any] = {
        "min_win_rate_required": 0.60,  # 60% minimum to be profitable
        "profit_per_win_0_1_lot": 6.50,  # $6.50 per winning trade (after spread)
        "loss_per_loss_0_1_lot": -6.50,  # -$6.50 per losing trade
        "daily_profit_target_40_trades": 65.0,  # $65/day at 60% win rate
        "monthly_profit_target": 1300.0,  # $1,300/month (20 trading days)
        "spread_cost_percentage": 15.0,  # Spread eats 15% of gross profits
    }

    # ============================================================================
    # LOGGING & DEBUGGING
    # ============================================================================

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TRADES: bool = True
    LOG_SPREAD_CHECKS: bool = True
    LOG_AGENT_DECISIONS: bool = True

    # ============================================================================
    # VALIDATION
    # ============================================================================

    @classmethod
    def validate(cls):
        """Validate configuration."""
        errors = []

        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY not set")

        if cls.TAKE_PROFIT_PIPS / cls.STOP_LOSS_PIPS < 1.5:
            errors.append(f"Risk:Reward too low: {cls.TAKE_PROFIT_PIPS}/{cls.STOP_LOSS_PIPS} = {cls.TAKE_PROFIT_PIPS/cls.STOP_LOSS_PIPS:.2f}")

        if cls.MAX_SPREAD_PIPS > 1.5:
            errors.append(f"Max spread too wide for scalping: {cls.MAX_SPREAD_PIPS} pips")

        if cls.ANALYSIS_INTERVAL_SECONDS > 120:
            errors.append(f"Analysis interval too slow for scalping: {cls.ANALYSIS_INTERVAL_SECONDS}s")

        if len(cls.SCALPING_PAIRS) > 5:
            errors.append(f"Too many pairs for scalping: {len(cls.SCALPING_PAIRS)} (recommended: 3-4)")

        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

        return True

    @classmethod
    def display(cls):
        """Display current configuration."""
        print("="*80)
        print("SCALPING ENGINE CONFIGURATION")
        print("="*80)
        print(f"\nStrategy: Fast Momentum Scalping (10-20 minute holds)")
        print(f"Pairs: {', '.join(cls.SCALPING_PAIRS)}")
        print(f"Timeframe: {cls.PRIMARY_TIMEFRAME} (every {cls.ANALYSIS_INTERVAL_SECONDS}s)")
        print(f"\nTargets:")
        print(f"  Take Profit: {cls.TAKE_PROFIT_PIPS} pips")
        print(f"  Stop Loss: {cls.STOP_LOSS_PIPS} pips")
        print(f"  Risk:Reward: {cls.RISK_REWARD_RATIO}:1")
        print(f"  Max Duration: {cls.MAX_TRADE_DURATION_MINUTES} minutes")
        print(f"\nSpread Limits:")
        print(f"  Maximum: {cls.MAX_SPREAD_PIPS} pips (reject above this)")
        print(f"  Ideal: {cls.IDEAL_SPREAD_PIPS} pips (full position size)")
        print(f"\nTrading Hours: {cls.TRADING_START_TIME.strftime('%H:%M')} - {cls.TRADING_END_TIME.strftime('%H:%M')} GMT")
        print(f"\nRisk Management:")
        print(f"  Max trades/day: {cls.MAX_TRADES_PER_DAY}")
        print(f"  Max open positions: {cls.MAX_OPEN_POSITIONS}")
        print(f"  Max daily loss: {cls.MAX_DAILY_LOSS_PERCENT}%")
        print(f"  Pause after {cls.MAX_CONSECUTIVE_LOSSES} consecutive losses")
        print(f"\nClaude Validator: {cls.CLAUDE_MODE.upper()} mode")
        print("="*80)


if __name__ == "__main__":
    # Test configuration
    ScalpingConfig.display()
    ScalpingConfig.validate()
    print("\n✅ Configuration valid")
