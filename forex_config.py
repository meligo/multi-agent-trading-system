"""
Forex Trading System Configuration

Real-time forex trading with 1m/5m timeframes using IG API.
"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# ============================================================================
# LANGSMITH TRACING SETUP
# ============================================================================
def setup_langsmith_tracing():
    """
    Configure LangSmith tracing for full observability of agent interactions.

    This enables:
    - Detailed traces of all LLM calls
    - Agent decision flows
    - Token usage tracking
    - Performance monitoring
    - Debugging capabilities

    View traces at: https://smith.langchain.com/
    """
    # Check both old (LANGSMITH_) and new (LANGCHAIN_) environment variable names
    langsmith_enabled = (
        os.getenv("LANGSMITH_TRACING", "false").lower() == "true" or
        os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    )

    if langsmith_enabled:
        # Set both LANGSMITH_ (deprecated) and LANGCHAIN_ (correct) environment variables
        api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY", "")
        project = os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT", "forex-trading-system")

        # Set LANGCHAIN_ variables (correct)
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = project
        os.environ["LANGCHAIN_API_KEY"] = api_key

        # Also set LANGSMITH_ variables (backwards compatibility)
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = project
        os.environ["LANGSMITH_API_KEY"] = api_key

        if api_key:
            print("✅ LangSmith tracing enabled")
            print(f"   Project: {project}")
            print(f"   View traces at: https://smith.langchain.com/")
        else:
            print("⚠️  LangSmith tracing enabled but no API key found")
    else:
        print("ℹ️  LangSmith tracing disabled (set LANGCHAIN_TRACING_V2=true to enable)")

# Setup LangSmith tracing
setup_langsmith_tracing()

class ForexConfig:
    """Configuration for forex trading system."""

    # ============================================================================
    # API CONFIGURATION
    # ============================================================================
    # IG API Configuration
    IG_API_KEY: str = os.getenv("IG_API_KEY", "2f6287777a79dfb0c6f2a47c86a6f7d0b07ecef8")
    IG_USERNAME: str = os.getenv("IG_USERNAME", "")
    IG_PASSWORD: str = os.getenv("IG_PASSWORD", "")
    IG_ACC_NUMBER: str = os.getenv("IG_ACC_NUMBER", "Z64WQT")
    IG_DEMO: bool = os.getenv("IG_DEMO", "true").lower() == "true"

    # OpenAI for agents
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # LangSmith Tracing & Observability
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_TRACING: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "forex-trading-system")

    # ============================================================================
    # CURRENCY PAIRS (28 Major Forex Pairs - IG Trading)
    # ============================================================================
    FOREX_PAIRS: List[str] = [
        # Major Pairs (7)
        "EUR_USD",  # 1. Euro / US Dollar (The Euro)
        "USD_JPY",  # 2. US Dollar / Japanese Yen
        "GBP_USD",  # 3. British Pound / US Dollar (Cable)
        "AUD_USD",  # 4. Australian Dollar / US Dollar (Aussie)
        "USD_CAD",  # 5. US Dollar / Canadian Dollar (Loonie)
        "USD_CHF",  # 6. US Dollar / Swiss Franc (Swissie)
        "NZD_USD",  # 7. New Zealand Dollar / US Dollar (Kiwi)

        # EUR Cross Pairs (6)
        "EUR_GBP",  # 8. Euro / British Pound
        "EUR_JPY",  # 9. Euro / Japanese Yen
        "EUR_AUD",  # 10. Euro / Australian Dollar
        "EUR_CAD",  # 11. Euro / Canadian Dollar
        "EUR_CHF",  # 12. Euro / Swiss Franc
        "EUR_NZD",  # 13. Euro / New Zealand Dollar

        # GBP Cross Pairs (6)
        "GBP_JPY",  # 14. British Pound / Japanese Yen (Gopher)
        "GBP_AUD",  # 15. British Pound / Australian Dollar
        "GBP_CAD",  # 16. British Pound / Canadian Dollar
        "GBP_CHF",  # 17. British Pound / Swiss Franc
        "GBP_NZD",  # 18. British Pound / New Zealand Dollar

        # AUD Cross Pairs (4)
        "AUD_JPY",  # 19. Australian Dollar / Japanese Yen
        "AUD_CAD",  # 20. Australian Dollar / Canadian Dollar
        "AUD_CHF",  # 21. Australian Dollar / Swiss Franc
        "AUD_NZD",  # 22. Australian Dollar / New Zealand Dollar

        # CAD Cross Pairs (3)
        "CAD_JPY",  # 23. Canadian Dollar / Japanese Yen
        "CAD_CHF",  # 24. Canadian Dollar / Swiss Franc
        "CAD_NZD",  # 25. Canadian Dollar / New Zealand Dollar

        # CHF Cross Pairs (2)
        "CHF_JPY",  # 26. Swiss Franc / Japanese Yen
        "CHF_NZD",  # 27. Swiss Franc / New Zealand Dollar

        # NZD Cross Pairs (1)
        "NZD_JPY",  # 28. New Zealand Dollar / Japanese Yen
    ]

    # ============================================================================
    # COMMODITY PAIRS (Available on IG demo/live CFD accounts)
    # ============================================================================
    COMMODITY_PAIRS: List[str] = [
        # Energy (VERIFIED WORKING) ✅
        "OIL_CRUDE",     # WTI Crude Oil (US) - highest liquidity oil
        "OIL_BRENT",     # Brent Crude Oil - Europe/global benchmark

        # Precious Metals (VERIFIED WORKING) ✅
        "XAU_USD",       # Spot Gold (EPIC: CS.D.CFDGOLD.CFDGC.IP)
        "XAG_USD",       # Spot Silver (EPIC: CS.D.CFDSILVER.CFDSI.IP)

        # Available but not added yet:
        # "COPPER",      # Spot Copper (EPIC: CS.D.COPPER.CFD.IP)
        # "NATURAL_GAS", # US Natural Gas
    ]

    # IG EPIC Mapping (for CFD accounts)
    # Using MINI markets for smaller position sizes suitable for demo account
    #
    # Forex patterns:
    # .MINI.IP = Mini CFD (10,000 units, 0.1 lot minimum)
    # .CFD.IP = Standard CFD (100,000 units, 1.0 lot minimum)
    #
    # Metal patterns (MT.D prefix):
    # MT.D.{SYMBOL}.MINI.IP = Mini metal CFD
    # MT.D.{SYMBOL}.CFD.IP = Standard metal CFD
    #
    # Commodity patterns (CO.D prefix):
    # CO.D.{SYMBOL}.MINI.IP = Mini commodity CFD
    # CO.D.{SYMBOL}.CFD.IP = Standard commodity CFD
    IG_EPIC_MAP = {
        # Forex Pairs (CS.D prefix)
        "EUR_USD": "CS.D.EURUSD.MINI.IP",
        "USD_JPY": "CS.D.USDJPY.MINI.IP",
        "GBP_USD": "CS.D.GBPUSD.MINI.IP",
        "AUD_USD": "CS.D.AUDUSD.MINI.IP",
        "USD_CAD": "CS.D.USDCAD.MINI.IP",
        "USD_CHF": "CS.D.USDCHF.MINI.IP",
        "NZD_USD": "CS.D.NZDUSD.MINI.IP",
        "EUR_GBP": "CS.D.EURGBP.MINI.IP",
        "EUR_JPY": "CS.D.EURJPY.MINI.IP",
        "EUR_AUD": "CS.D.EURAUD.MINI.IP",
        "EUR_CAD": "CS.D.EURCAD.MINI.IP",
        "EUR_CHF": "CS.D.EURCHF.MINI.IP",
        "EUR_NZD": "CS.D.EURNZD.MINI.IP",
        "GBP_JPY": "CS.D.GBPJPY.MINI.IP",
        "GBP_AUD": "CS.D.GBPAUD.MINI.IP",
        "GBP_CAD": "CS.D.GBPCAD.MINI.IP",
        "GBP_CHF": "CS.D.GBPCHF.MINI.IP",
        "GBP_NZD": "CS.D.GBPNZD.MINI.IP",
        "AUD_JPY": "CS.D.AUDJPY.MINI.IP",
        "AUD_CAD": "CS.D.AUDCAD.MINI.IP",
        "AUD_CHF": "CS.D.AUDCHF.MINI.IP",
        "AUD_NZD": "CS.D.AUDNZD.MINI.IP",
        "CAD_JPY": "CS.D.CADJPY.MINI.IP",
        "CAD_CHF": "CS.D.CADCHF.MINI.IP",
        "CAD_NZD": "CS.D.CADNZD.MINI.IP",
        "CHF_JPY": "CS.D.CHFJPY.MINI.IP",
        "CHF_NZD": "CS.D.CHFNZD.MINI.IP",
        "NZD_JPY": "CS.D.NZDJPY.MINI.IP",

        # Commodity Pairs - Precious Metals (VERIFIED WORKING) ✅
        "XAU_USD": "CS.D.CFDGOLD.CFDGC.IP",      # Spot Gold (Min: 0.1 lots)
        "XAG_USD": "CS.D.CFDSILVER.CFDSI.IP",    # Spot Silver 5000oz (Min: 0.1 lots)

        # Alternative Gold/Silver EPICs (tested and working):
        # "XAU_USD": "CS.D.CFDGOLD.CFM.IP",      # Spot Gold Mini 10oz (Min: 0.5 lots)
        # "XAU_USD": "CS.D.CFPGOLD.CFP.IP",      # Spot Gold £1 Contract (Min: 10 lots)
        # "XAG_USD": "CS.D.CFDSILVER.CFM.IP",    # Mini Spot Silver 500oz (Min: 0.5 lots)

        # Other precious metals (available but not tested):
        "XPT_USD": "MT.D.PL.FWM2.IP",          # Platinum ($10) - JAN-26 Expiry
        "XPD_USD": "CS.D.XPDUSD.CFD.IP",       # Palladium (if available)

        # Commodity Pairs - Energy (CC.D prefix for undated cash CFDs)
        "OIL_CRUDE": "CC.D.CL.USS.IP",        # WTI Crude Oil (undated cash)
        "OIL_BRENT": "CC.D.LCO.USS.IP",       # Brent Crude Oil (undated cash)
        "NATURAL_GAS": "CC.D.NGAS.USS.IP",    # US Natural Gas (undated cash)

        # Commodity Pairs - Industrial Metals (CC.D prefix)
        "COPPER": "CC.D.COPPER.USS.IP",       # Spot Copper (undated cash)
    }

    # Combined list of all tradeable pairs (forex + commodities)
    ALL_PAIRS: List[str] = FOREX_PAIRS + COMMODITY_PAIRS

    # User's preferred pairs (expanded to 20 most liquid + commodities)
    # Selected based on: liquidity, spread tightness, algo-trading suitability
    PRIORITY_PAIRS: List[str] = [
        # Major Pairs (7) - Highest liquidity, tightest spreads
        "EUR_USD",      # 1. Most liquid pair globally
        "GBP_USD",      # 2. Cable - high volatility, good trends
        "USD_JPY",      # 3. Tokyo/Asia favorite, stable
        "USD_CHF",      # 4. Safe haven, low spreads
        "AUD_USD",      # 5. Commodity currency, Asia hours
        "USD_CAD",      # 6. Oil-sensitive, North America
        "NZD_USD",      # 7. Asia/Oceania, good ranges

        # EUR Cross Pairs (6) - EUR diversification
        "EUR_GBP",      # 8. EUR/GBP cross, range-bound
        "EUR_JPY",      # 9. High liquidity cross
        "EUR_AUD",      # 10. Risk sentiment proxy
        "EUR_CAD",      # 11. Energy/Europe correlation
        "EUR_CHF",      # 12. Low volatility, technical
        "EUR_NZD",      # 13. High range, trending

        # GBP Cross Pairs (4) - GBP diversification
        "GBP_JPY",      # 14. "Gopher" - high volatility
        "GBP_AUD",      # 15. Risk-on/off indicator
        "GBP_CAD",      # 16. Energy correlation
        "GBP_CHF",      # 17. Brexit-sensitive

        # Other Liquid Crosses (3)
        "AUD_JPY",      # 18. Risk appetite gauge
        "AUD_CAD",      # 19. Commodity pair
        "CAD_JPY",      # 20. Oil/Asia correlation

        # Top Commodities (4) - VERIFIED WORKING ✅
        "OIL_CRUDE",    # 21. WTI Crude Oil
        "OIL_BRENT",    # 22. Brent Crude Oil
        "XAU_USD",      # 23. Gold (Spot Gold)
        "XAG_USD",      # 24. Silver (Spot Silver)
    ]

    # ============================================================================
    # TIMEFRAME SETTINGS
    # ============================================================================
    PRIMARY_TIMEFRAME: str = "5"  # 5-minute (main trading)
    SECONDARY_TIMEFRAME: str = "1"  # 1-minute (confirmation)
    TERTIARY_TIMEFRAME: str = "15"  # 15-minute (context)

    # How many candles to analyze
    CANDLES_LOOKBACK: int = 100  # Last 100 bars

    # ============================================================================
    # TECHNICAL ANALYSIS SETTINGS
    # ============================================================================
    # RSI Settings
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: float = 70
    RSI_OVERSOLD: float = 30

    # MACD Settings
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

    # Bollinger Bands
    BB_PERIOD: int = 20
    BB_STD: float = 2.0

    # Keltner Channels
    KELTNER_PERIOD: int = 20
    KELTNER_ATR_MULT: float = 2.0

    # Moving Averages
    MA_FAST: int = 9
    MA_MEDIUM: int = 21
    MA_SLOW: int = 50
    MA_VERY_SLOW: int = 200

    # Ichimoku Cloud
    ICHIMOKU_TENKAN: int = 9  # Conversion line
    ICHIMOKU_KIJUN: int = 26  # Base line
    ICHIMOKU_SENKOU_B: int = 52  # Leading span B

    # ADX (Average Directional Index)
    ADX_PERIOD: int = 14
    ADX_STRONG_TREND: float = 25  # ADX > 25 = strong trend

    # Stochastic Oscillator
    STOCH_K_PERIOD: int = 14
    STOCH_D_PERIOD: int = 3
    STOCH_OVERBOUGHT: float = 80
    STOCH_OVERSOLD: float = 20

    # Williams %R
    WILLIAMS_R_PERIOD: int = 14

    # CCI (Commodity Channel Index)
    CCI_PERIOD: int = 20
    CCI_OVERBOUGHT: float = 100
    CCI_OVERSOLD: float = -100

    # Pattern Recognition (Disabled - API issues)
    ENABLE_FINNHUB_PATTERNS: bool = False  # Use Finnhub pattern API
    ENABLE_FINNHUB_INDICATORS: bool = False  # Use Finnhub aggregate indicators
    ENABLE_FINNHUB_SUPPORT_RESISTANCE: bool = False  # Use Finnhub S/R API

    # ============================================================================
    # TRADING SETTINGS
    # ============================================================================
    # Risk Management
    RISK_PERCENT: float = 1.0  # Risk 1% per trade
    MIN_RISK_REWARD: float = 1.5  # Minimum 1.5:1 RR ratio
    MAX_SPREAD_PIPS: float = 3.0  # Max acceptable spread
    MAX_OPEN_POSITIONS: int = 20  # Maximum concurrent open positions
    CHECK_IG_POSITIONS_ON_STARTUP: bool = True  # Check IG for existing positions on startup

    # Position Sizing
    DEFAULT_LOT_SIZE: float = 0.01  # Micro lot
    MAX_POSITION_SIZE: float = 1.0  # Max 1 standard lot

    # Stop Loss / Take Profit (in pips)
    DEFAULT_STOP_LOSS_PIPS: float = 20
    DEFAULT_TAKE_PROFIT_PIPS: float = 40

    # Signal Confidence
    MIN_CONFIDENCE: float = 0.6  # Minimum 60% confidence

    # Analysis Interval
    ANALYSIS_INTERVAL_SECONDS: int = 300  # Analyze pairs every 5 minutes (reduced from 60s to avoid IG API rate limits)

    # ============================================================================
    # AI AGENT SETTINGS
    # ============================================================================
    # LLM Configuration
    LLM_MODEL: str = "gpt-4o-mini"  # Fast model for real-time
    LLM_TEMPERATURE: float = 0.05  # Low = deterministic
    LLM_MAX_TOKENS: int = 500  # Short responses
    LLM_TIMEOUT: int = 10  # 10 seconds timeout

    # Agent Settings
    ENABLE_MULTI_AGENT: bool = True  # Use multiple agents
    ENABLE_DEBATE: bool = False  # Disable debate (too slow)
    AGENTS_TO_USE: List[str] = [
        "price_action",  # Price action analysis
        "momentum",      # Momentum and trend
        "risk",          # Risk assessment
        "decision",      # Final decision maker
    ]

    # ============================================================================
    # DASHBOARD SETTINGS
    # ============================================================================
    DASHBOARD_REFRESH_SECONDS: int = 5  # Update every 5 seconds
    DASHBOARD_PORT: int = 8501  # Streamlit port
    SHOW_CHARTS: bool = True  # Display price charts
    CHART_CANDLES: int = 50  # Show last 50 candles

    # ============================================================================
    # NOTIFICATION SETTINGS
    # ============================================================================
    ENABLE_NOTIFICATIONS: bool = False  # Sound/desktop alerts
    NOTIFY_ON_SIGNALS: bool = True  # Alert on BUY/SELL
    NOTIFY_ON_TP_HIT: bool = True  # Alert on take profit
    NOTIFY_ON_SL_HIT: bool = True  # Alert on stop loss

    # ============================================================================
    # DATA CACHING
    # ============================================================================
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 60  # 1 minute cache
    CACHE_DIR: str = "./forex_cache"

    # ============================================================================
    # LOGGING
    # ============================================================================
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_FILE: str = "./logs/forex_trading.log"
    LOG_TO_CONSOLE: bool = True

    # ============================================================================
    # BACKTESTING SETTINGS
    # ============================================================================
    BACKTEST_START_DATE: str = "2025-01-01"
    BACKTEST_INITIAL_BALANCE: float = 10000.0
    BACKTEST_COMMISSION_PIPS: float = 2.0

    # ============================================================================
    # ADVANCED FEATURES
    # ============================================================================
    # Auto-trading (BE CAREFUL!)
    AUTO_TRADING_ENABLED: bool = False  # DISABLED by default
    AUTO_TRADING_MAX_TRADES_PER_DAY: int = 10
    AUTO_TRADING_MAX_LOSS_PERCENT: float = 5.0  # Stop if 5% loss

    # Multiple timeframe confirmation
    REQUIRE_MULTIPLE_TF_CONFIRMATION: bool = True  # 1m + 5m agree

    # Pattern recognition
    ENABLE_PATTERN_DETECTION: bool = True  # Chart patterns

    # Session filters (forex sessions)
    TRADE_ASIAN_SESSION: bool = True  # 00:00-09:00 UTC
    TRADE_EUROPEAN_SESSION: bool = True  # 07:00-16:00 UTC
    TRADE_US_SESSION: bool = True  # 13:00-22:00 UTC

    # ============================================================================
    # ENHANCEMENT FEATURES (NEW)
    # ============================================================================
    # Sentiment Analysis
    ENABLE_SENTIMENT_ANALYSIS: bool = True  # Enable sentiment analysis
    SENTIMENT_WEIGHT: float = 0.15  # Weight in final decision (15%)

    # Finnhub Technical Analysis & Pattern Recognition
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
    ENABLE_FINNHUB: bool = True  # Enable Finnhub integration
    FINNHUB_AGGREGATE_WEIGHT: float = 0.20  # Weight for aggregate consensus (20%)
    FINNHUB_CACHE_SECONDS: int = 300  # Cache results for 5 minutes
    FINNHUB_ENABLE_PATTERNS: bool = True  # Enable pattern recognition
    FINNHUB_ENABLE_SR: bool = True  # Enable support/resistance validation

    # Claude Validator (Final validation layer)
    ENABLE_CLAUDE_VALIDATOR: bool = True  # Enable Claude validation
    CLAUDE_MIN_CONFIDENCE: float = 0.70  # Min confidence for Claude approval

    # Position Monitoring & Reversal
    ENABLE_POSITION_MONITORING: bool = True  # Enable position monitoring
    POSITION_MONITOR_INTERVAL: int = 300  # Check every 5 minutes (300 sec)
    REVERSAL_COOLDOWN_MINUTES: int = 10  # Min time between reversals
    MAX_REVERSALS_PER_DAY: int = 2  # Max reversals per pair per day
    REVERSAL_CONFIDENCE_THRESHOLD: float = 0.75  # Min confidence for reversal

    @classmethod
    def validate(cls):
        """Validate configuration."""
        if not cls.IG_API_KEY:
            raise ValueError("IG_API_KEY not set in environment")
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment")

        # Check risk parameters
        if cls.RISK_PERCENT > 5.0:
            raise ValueError("RISK_PERCENT too high (max 5%)")
        if cls.MIN_RISK_REWARD < 1.0:
            raise ValueError("MIN_RISK_REWARD must be >= 1.0")

        print("✓ Forex configuration validated")

    @classmethod
    def display(cls):
        """Display current configuration."""
        print("\n" + "="*70)
        print("FOREX & COMMODITY TRADING SYSTEM CONFIGURATION (IG API)")
        print("="*70)
        print(f"Forex Pairs: {len(cls.FOREX_PAIRS)} pairs")
        print(f"Commodities: {len(cls.COMMODITY_PAIRS)} pairs (Gold, Silver, Oil, etc.)")
        print(f"Total Tradeable: {len(cls.ALL_PAIRS)} pairs")
        print(f"\nPriority Pairs ({len(cls.PRIORITY_PAIRS)}):")
        for i, pair in enumerate(cls.PRIORITY_PAIRS, 1):
            print(f"  {i}. {pair}")
        print(f"\nTimeframes: {cls.PRIMARY_TIMEFRAME}m (primary), {cls.SECONDARY_TIMEFRAME}m (confirm)")
        print(f"Risk per trade: {cls.RISK_PERCENT}%")
        print(f"Min R:R ratio: {cls.MIN_RISK_REWARD}:1")
        print(f"Max open positions: {cls.MAX_OPEN_POSITIONS}")
        print(f"\nData Source:")
        print(f"  IG API: {'DEMO' if cls.IG_DEMO else 'LIVE'}")
        print(f"  Pattern Recognition: {'ON' if cls.ENABLE_PATTERN_DETECTION else 'OFF'}")
        print(f"\nAI Model: {cls.LLM_MODEL}")
        print(f"Agents: {', '.join(cls.AGENTS_TO_USE)}")
        print(f"\nDashboard: http://localhost:{cls.DASHBOARD_PORT}")
        print(f"Refresh: Every {cls.DASHBOARD_REFRESH_SECONDS}s")
        print(f"\nAuto-Trading: {'ENABLED ⚠️' if cls.AUTO_TRADING_ENABLED else 'DISABLED ✓'}")
        print("="*70 + "\n")
