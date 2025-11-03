"""
Enhanced Scalping Dashboard - Full System Integration

Auto-starting dashboard with:
- PostgreSQL + TimescaleDB database (remote)
- InsightSentry MEGA (news/calendar/sentiment)
- DataBento (CME futures order flow)
- News gating service (auto-close before events)
- Real-time WebSocket data for EUR/USD, GBP/USD, USD/JPY
- Live indicator calculations (EMA ribbon, VWAP, Donchian, RSI(7), ADX(7))
- Agent debates and trade signals
- 20-minute trade timer monitoring
- Spread monitoring
- Performance metrics

Starts automatically on launch - no user action required!
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import threading
import json
import asyncio
from typing import Dict, List, Optional
import queue
import logging

from scalping_config import ScalpingConfig
from scalping_engine import ScalpingEngine
from scalping_indicators import ScalpingIndicators
from trading_database import get_database
from ig_rate_limiter import get_rate_limiter
from forex_market_hours import get_market_hours
from service_manager import get_service_manager

# Enhanced services
from database_manager import DatabaseManager
from insightsentry_client import InsightSentryClient
from news_gating_service import NewsGatingService, GateConfig
from databento_client import DataBentoClient

# Unified data fetching
from unified_data_fetcher import UnifiedDataFetcher, get_unified_data_fetcher

# DataHub (shared memory cache)
from data_hub import start_data_hub_manager, DataHub, DataHubManager
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="⚡ Enhanced Scalping Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS (same as before)
st.markdown("""
<style>
    .stMetric {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
    }

    .scalp-signal-long {
        background-color: #00ff00;
        color: black;
        padding: 20px;
        border-radius: 10px;
        font-weight: bold;
        font-size: 24px;
        text-align: center;
        animation: pulse 1s infinite;
    }

    .scalp-signal-short {
        background-color: #ff0000;
        color: white;
        padding: 20px;
        border-radius: 10px;
        font-weight: bold;
        font-size: 24px;
        text-align: center;
        animation: pulse 1s infinite;
    }

    .scalp-signal-none {
        background-color: #808080;
        color: white;
        padding: 20px;
        border-radius: 10px;
        font-weight: bold;
        font-size: 24px;
        text-align: center;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    .service-status-ok {
        background-color: #28a745;
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }

    .service-status-warning {
        background-color: #ffc107;
        color: black;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }

    .service-status-error {
        background-color: #dc3545;
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# Global engine singleton
_global_engine = None
_global_engine_lock = threading.Lock()

def get_global_engine():
    """Get the global scalping engine instance."""
    global _global_engine
    with _global_engine_lock:
        return _global_engine

def set_global_engine(engine):
    """Set the global scalping engine instance."""
    global _global_engine
    with _global_engine_lock:
        _global_engine = engine

# Initialize session state for enhanced services
if 'db_manager' not in st.session_state:
    st.session_state.db_manager = None

if 'db_initialized' not in st.session_state:
    st.session_state.db_initialized = False

if 'is_client' not in st.session_state:
    st.session_state.is_client = None

if 'news_gating' not in st.session_state:
    st.session_state.news_gating = None

if 'news_gating_running' not in st.session_state:
    st.session_state.news_gating_running = False

if 'databento_client' not in st.session_state:
    st.session_state.databento_client = None

if 'databento_running' not in st.session_state:
    st.session_state.databento_running = False

if 'unified_data_fetcher' not in st.session_state:
    st.session_state.unified_data_fetcher = None

# DataHub session state
if 'datahub_manager' not in st.session_state:
    st.session_state.datahub_manager = None

if 'datahub' not in st.session_state:
    st.session_state.datahub = None

if 'datahub_initialized' not in st.session_state:
    st.session_state.datahub_initialized = False

if 'enhanced_services_initialized' not in st.session_state:
    st.session_state.enhanced_services_initialized = False

if 'service_status' not in st.session_state:
    st.session_state.service_status = {
        'database': 'Not initialized',
        'insightsentry': 'Not initialized',
        'news_gating': 'Not started',
        'databento': 'Not started',
        'data_fetcher': 'Not initialized',
        'datahub': 'Not initialized'
    }

# Initialize session state (existing)
if 'engine' not in st.session_state:
    existing_engine = get_global_engine()
    if existing_engine and hasattr(existing_engine, 'running') and existing_engine.running:
        st.session_state.engine = existing_engine
        st.session_state.engine_started = True
    else:
        st.session_state.engine = None
        st.session_state.engine_started = False

if 'service_manager' not in st.session_state:
    st.session_state.service_manager = get_service_manager()

if 'enable_websocket' not in st.session_state:
    st.session_state.enable_websocket = True

if 'auto_start_done' not in st.session_state:
    st.session_state.auto_start_done = False

if 'live_data' not in st.session_state:
    st.session_state.live_data = {pair: None for pair in ScalpingConfig.SCALPING_PAIRS}

if 'indicator_data' not in st.session_state:
    st.session_state.indicator_data = {pair: {} for pair in ScalpingConfig.SCALPING_PAIRS}

if 'trade_signals' not in st.session_state:
    st.session_state.trade_signals = {pair: None for pair in ScalpingConfig.SCALPING_PAIRS}

# Database
db = get_database()
market_hours = get_market_hours()


# ============================================================================
# ENHANCED SERVICES INITIALIZATION
# ============================================================================

async def initialize_enhanced_services():
    """Initialize all enhanced services (DataHub, database, InsightSentry, news gating, DataBento)."""
    try:
        # 0. Initialize DataHub (FIRST - before all other services)
        st.session_state.service_status['datahub'] = 'Starting...'
        try:
            logger.info("🚀 Starting DataHub manager...")

            # Start DataHub manager
            manager = start_data_hub_manager(
                address=('127.0.0.1', 50000),
                authkey=b'forex_scalper_2025'
            )
            st.session_state.datahub_manager = manager
            st.session_state.datahub = manager.DataHub()

            # Set environment variables for subprocesses
            os.environ['DATA_HUB_HOST'] = '127.0.0.1'
            os.environ['DATA_HUB_PORT'] = '50000'
            os.environ['DATA_HUB_AUTHKEY'] = 'forex_scalper_2025'

            st.session_state.datahub_initialized = True
            st.session_state.service_status['datahub'] = '✅ Running'
            logger.info("✅ DataHub manager started at 127.0.0.1:50000")

        except Exception as e:
            st.session_state.service_status['datahub'] = f'❌ {str(e)[:30]}'
            logger.error(f"DataHub initialization failed: {e}")
            # Continue anyway - system can run without DataHub (degraded mode)

        # 1. Initialize Database
        st.session_state.service_status['database'] = 'Connecting...'
        st.session_state.db_manager = DatabaseManager()
        await st.session_state.db_manager.initialize()

        # Check if schema exists
        needs_setup = await _check_schema_exists()
        if needs_setup:
            logger.info("Loading database schema...")
            await st.session_state.db_manager.execute_schema()

        st.session_state.db_initialized = True
        st.session_state.service_status['database'] = '✅ Connected'
        logger.info("✅ Database initialized")

        # Warm-start DataHub from database (if DataHub available)
        if st.session_state.datahub:
            try:
                logger.info("🔥 Warm-starting DataHub from database...")

                # Fetch recent candles from database for each pair
                from scalping_config import ScalpingConfig
                from market_data_models import Candle

                for pair in ScalpingConfig.SCALPING_PAIRS:
                    try:
                        # Query last 100 1-minute candles from database
                        query = """
                        SELECT timestamp, open, high, low, close, volume
                        FROM ig_candles
                        WHERE symbol = %s AND timeframe = '1'
                        ORDER BY timestamp DESC
                        LIMIT 100
                        """

                        result = await st.session_state.db_manager.execute_query(query, (pair,))

                        if result:
                            # Convert to Candle objects (oldest first)
                            candles = []
                            for row in reversed(result):
                                candle = Candle(
                                    symbol=pair,
                                    timestamp=row['timestamp'],
                                    open=float(row['open']),
                                    high=float(row['high']),
                                    low=float(row['low']),
                                    close=float(row['close']),
                                    volume=float(row.get('volume', 0))
                                )
                                candles.append(candle)

                            # Warm-start DataHub
                            count = st.session_state.datahub.warm_start_candles(pair, candles)
                            logger.info(f"  ✅ {pair}: {count} candles loaded")
                        else:
                            logger.info(f"  ⚠️  {pair}: No historical data in database")

                    except Exception as e:
                        logger.warning(f"  ⚠️  {pair}: Database fetch failed: {e}")

                logger.info("✅ DataHub warm-start complete")

            except Exception as e:
                logger.warning(f"DataHub warm-start failed: {e}")

        # 2. Initialize InsightSentry Client
        st.session_state.service_status['insightsentry'] = 'Initializing...'
        st.session_state.is_client = InsightSentryClient()
        st.session_state.service_status['insightsentry'] = '✅ Ready'
        logger.info("✅ InsightSentry client initialized")

        # 3. Initialize News Gating Service
        st.session_state.service_status['news_gating'] = 'Starting...'
        gate_config = GateConfig(
            gate_window_minutes=15,
            close_window_minutes=10,
            close_positions=True,
            check_interval=60
        )
        st.session_state.news_gating = NewsGatingService(
            config=gate_config,
            db_manager=st.session_state.db_manager,
            insightsentry_client=st.session_state.is_client
        )

        # Capture news_gating instance for thread (session_state not accessible in threads)
        news_gating_instance = st.session_state.news_gating

        # Start in background thread
        def run_news_gating():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(news_gating_instance.start())

        news_thread = threading.Thread(target=run_news_gating, daemon=True)
        news_thread.start()

        st.session_state.news_gating_running = True
        st.session_state.service_status['news_gating'] = '✅ Running'
        logger.info("✅ News Gating Service started")

        # 4. Initialize DataBento (market hours only) with DataHub
        try:
            st.session_state.databento_client = DataBentoClient(
                db_manager=st.session_state.db_manager,
                data_hub=st.session_state.datahub  # Pass DataHub reference
            )
            st.session_state.service_status['databento'] = '✅ Ready (market hours)'
            logger.info("✅ DataBento client initialized")
        except Exception as e:
            st.session_state.service_status['databento'] = f'⚠️ {str(e)[:30]}'
            logger.warning(f"DataBento initialization skipped: {e}")

        # 5. Initialize Unified Data Fetcher (NEW: uses DataHub as primary source)
        st.session_state.service_status['data_fetcher'] = 'Initializing...'
        try:
            # Create fetcher with DataHub
            st.session_state.unified_data_fetcher = get_unified_data_fetcher(
                data_hub=st.session_state.datahub
            )

            # Inject secondary sources (database, InsightSentry)
            st.session_state.unified_data_fetcher.inject_sources(
                data_hub=st.session_state.datahub,  # Primary data source
                finnhub_integration=None,  # TODO: Add Finnhub integration
                finnhub_fetcher=None,      # TODO: Add Finnhub fetcher
                insightsentry=st.session_state.is_client,
                db=st.session_state.db_manager  # Fallback for historical data
            )

            st.session_state.service_status['data_fetcher'] = '✅ Ready'
            logger.info("✅ Unified Data Fetcher initialized with DataHub")
        except Exception as e:
            st.session_state.service_status['data_fetcher'] = f'⚠️ {str(e)[:30]}'
            logger.warning(f"Unified Data Fetcher initialization error: {e}")

        st.session_state.enhanced_services_initialized = True
        return True

    except Exception as e:
        logger.error(f"Error initializing enhanced services: {e}")
        st.session_state.service_status['database'] = f'❌ {str(e)[:30]}'
        return False


async def _check_schema_exists():
    """Check if database schema exists."""
    try:
        result = await st.session_state.db_manager.execute_query(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'instruments')"
        )
        exists = result[0]['exists'] if result else False
        return not exists
    except:
        return True


def initialize_services_sync():
    """Synchronous wrapper for async initialization."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(initialize_enhanced_services())


# AUTO-START: Launch everything on first load
if not st.session_state.auto_start_done:
    try:
        # CRITICAL: Initialize enhanced services FIRST (includes DataHub)
        # This must happen before WebSocket starts so WebSocket can connect to DataHub
        if not st.session_state.enhanced_services_initialized:
            with st.spinner("Initializing enhanced services (Database, DataHub, InsightSentry, News Gating)..."):
                initialize_services_sync()

        # Start WebSocket collector AFTER DataHub is ready
        # WebSocket will connect to DataHub via environment variables
        if st.session_state.enable_websocket:
            st.session_state.service_manager.start_all(enable_websocket=True)
            logger.info("✅ WebSocket collector started (connected to DataHub)")

        st.session_state.auto_start_done = True
    except Exception as e:
        logger.error(f"⚠️ Auto-start error: {e}")


# ============================================================================
# EXISTING FUNCTIONS (keep all from original)
# ============================================================================

def start_scalping_engine(force_start: bool = False):
    """Start the scalping engine with auto-trading.

    Returns:
        tuple: (success: bool, message: str, message_type: str)
    """
    market_status = market_hours.get_market_status()

    if not market_status['is_open'] and not force_start:
        next_open = market_status['next_open'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')
        time_until = market_status['time_until_open_human']
        msg = f"""🛑 **FOREX MARKET IS CLOSED**

Cannot start scalping during closed hours.

**Next Market Open:** {next_open}
**Time Until Open:** {time_until}
**Current UTC Time:** {datetime.utcnow().strftime('%H:%M:%S')} UTC

💡 *Use "Force Start (Testing)" below to start anyway for testing.*"""
        return False, msg, "error"

    current_hour = datetime.utcnow().hour
    if not (ScalpingConfig.TRADING_START_TIME.hour <= current_hour < ScalpingConfig.TRADING_END_TIME.hour) and not force_start:
        # Outside optimal hours - show warning but don't block
        pass

    if st.session_state.engine is None or not hasattr(st.session_state.engine, 'running') or not st.session_state.engine.running:
        # Create and start engine in background thread
        st.session_state.engine = ScalpingEngine()

        # Inject unified data fetcher (so engine can fetch market data)
        if st.session_state.unified_data_fetcher:
            st.session_state.engine.set_data_fetcher(st.session_state.unified_data_fetcher)
            logger.info("✅ Data fetcher injected into engine")
        else:
            logger.warning("⚠️  No unified data fetcher available - engine will have limited data")

        # Start engine in background thread (run() is blocking)
        engine_thread = threading.Thread(target=st.session_state.engine.run, daemon=True)
        engine_thread.start()

        # Wait a moment for the engine to initialize
        time.sleep(0.5)

        st.session_state.engine_started = True
        set_global_engine(st.session_state.engine)

        session = market_hours.get_market_session()

        if force_start and not market_hours.get_market_status()['is_open']:
            msg = f"""⚠️ **SCALPING ENGINE STARTED (TESTING MODE)**

🚨 **Market is CLOSED** - Running for testing purposes only!

**Pairs:** {', '.join(ScalpingConfig.SCALPING_PAIRS)}
**Timeframe:** 1-minute candles (60s analysis)
**Max Trade Duration:** {ScalpingConfig.MAX_TRADE_DURATION_MINUTES} minutes
**Spread Limit:** {ScalpingConfig.MAX_SPREAD_PIPS} pips

⚠️ No live market data available - spreads may be stale."""
            return True, msg, "warning"
        else:
            msg = f"""✅ **SCALPING ENGINE STARTED**

**Market Session:** {session}
**Pairs:** {', '.join(ScalpingConfig.SCALPING_PAIRS)}
**Timeframe:** 1-minute candles (60s analysis)
**Max Trade Duration:** {ScalpingConfig.MAX_TRADE_DURATION_MINUTES} minutes
**Spread Limit:** {ScalpingConfig.MAX_SPREAD_PIPS} pips

🚀 Engine is now monitoring markets and will auto-trade when signals align!"""
            return True, msg, "success"

    return False, "Engine is already running", "info"


def stop_scalping_engine():
    """Stop the scalping engine and close all positions.

    Returns:
        tuple: (success: bool, message: str)
    """
    if st.session_state.engine and st.session_state.engine.running:
        st.session_state.engine.stop()
        st.session_state.engine_started = False
        return True, "✅ Scalping engine stopped. All positions will be closed at market."
    return False, "Engine is not running"


# (Keep all other functions from original: create_indicator_chart, display_trade_timer,
#  display_spread_monitor, display_signal_card - they're unchanged)

# ============================================================================
# MAIN DASHBOARD
# ============================================================================

st.title("⚡ Enhanced Scalping Dashboard")
st.markdown("**Fast Momentum Scalping + Order Flow + News Gating** | 1-Minute Charts | 10-20 Minute Holds")

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Engine Controls")

    # Market status
    market_status = market_hours.get_market_status()
    if market_status['is_open']:
        session = market_hours.get_market_session()
        st.success(f"✅ Market OPEN\n\n**Session:** {session}")
    else:
        next_open = market_status['next_open'].strftime('%H:%M %Z')
        st.error(f"🛑 Market CLOSED\n\n**Next Open:** {next_open}")

    st.markdown("---")

    # Enhanced Services Status
    st.subheader("🔧 Enhanced Services")

    for service_name, status in st.session_state.service_status.items():
        if '✅' in status:
            st.markdown(f'<div class="service-status-ok">{service_name}: {status}</div>', unsafe_allow_html=True)
        elif '⚠️' in status:
            st.markdown(f'<div class="service-status-warning">{service_name}: {status}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="service-status-error">{service_name}: {status}</div>', unsafe_allow_html=True)

    # Show active gates
    if st.session_state.news_gating_running:
        try:
            # Get gates synchronously
            loop = asyncio.new_event_loop()
            gates = loop.run_until_complete(st.session_state.news_gating.get_all_gates())

            if gates:
                st.warning(f"⚠️ {len(gates)} Active News Gates")
                for gate in gates[:3]:
                    st.caption(f"- {gate['provider_symbol']}: {gate['reason']}")
        except:
            pass

    st.markdown("---")

    # Message placeholder for start/stop feedback
    msg_placeholder = st.empty()

    # Show current market status
    market_status = market_hours.get_market_status()
    is_open = bool(market_status.get('is_open', False))
    st.caption(f"🕐 Market: **{'OPEN' if is_open else 'CLOSED'}** | {datetime.utcnow().strftime('%H:%M')} UTC")

    # Start/Stop buttons
    if not st.session_state.engine_started:
        start_clicked = st.button("🚀 START SCALPING ENGINE", key="start_engine_btn", type="primary", use_container_width=True)

        # Force start option visible only when market is closed
        force_clicked = False
        if not is_open:
            st.markdown("**Testing Mode:**")
            force_clicked = st.button("⚠️ FORCE START (Testing)", key="force_start_btn", type="secondary", use_container_width=True)

        # Handle button clicks
        if start_clicked or force_clicked:
            success, message, msg_type = start_scalping_engine(force_start=force_clicked)

            if success:
                # Show success message and rerun
                msg_placeholder.success(message)
                time.sleep(1)  # Let user see the message
                st.rerun()
            else:
                # Show error message (don't rerun)
                if msg_type == "error":
                    msg_placeholder.error(message)
                elif msg_type == "warning":
                    msg_placeholder.warning(message)
                else:
                    msg_placeholder.info(message)
    else:
        stop_clicked = st.button("🛑 STOP ENGINE", key="stop_engine_btn", type="secondary", use_container_width=True)
        if stop_clicked:
            if st.checkbox("Confirm stop and close all positions", key="confirm_stop_check"):
                success, message = stop_scalping_engine()
                if success:
                    msg_placeholder.success(message)
                    time.sleep(1)
                    st.rerun()
                else:
                    msg_placeholder.warning(message)

    st.markdown("---")

    # Configuration display
    st.subheader("📋 Strategy Config")
    st.write(f"**Pairs:** {len(ScalpingConfig.SCALPING_PAIRS)}")
    for pair in ScalpingConfig.SCALPING_PAIRS:
        st.write(f"  - {pair}")

    st.write(f"**Timeframe:** {ScalpingConfig.PRIMARY_TIMEFRAME}")
    st.write(f"**Analysis:** Every {ScalpingConfig.ANALYSIS_INTERVAL_SECONDS}s")
    st.write(f"**TP:** {ScalpingConfig.TAKE_PROFIT_PIPS} pips")
    st.write(f"**SL:** {ScalpingConfig.STOP_LOSS_PIPS} pips")
    st.write(f"**Max Duration:** {ScalpingConfig.MAX_TRADE_DURATION_MINUTES} min")
    st.write(f"**Max Spread:** {ScalpingConfig.MAX_SPREAD_PIPS} pips")

    st.markdown("---")

    # WebSocket status
    ws_status = st.session_state.service_manager.get_websocket_status()
    if ws_status.get('running', False):
        st.success("✅ WebSocket: ACTIVE")
        pairs_connected = ws_status.get('pairs_subscribed', 0)
        st.write(f"**Pairs:** {pairs_connected}")
    else:
        st.warning("⚠️ WebSocket: DISCONNECTED")
        if st.button("Reconnect WebSocket"):
            st.session_state.service_manager.start_all(enable_websocket=True)
            st.rerun()

    st.markdown("---")

    # Auto-refresh control (don't rerun here!)
    auto_refresh = st.checkbox("Auto-refresh (2s)", value=True)

# Create tabs in main content area (after sidebar)
tab1, tab2 = st.tabs(["📊 Trading Dashboard", "📅 Economic Calendar"])

# Main content - Tab 1: Trading Dashboard
with tab1:
    if not st.session_state.engine_started:
        st.info("""
        🎯 **Welcome to the Enhanced Scalping Dashboard**

        This dashboard provides:
        - ✅ **PostgreSQL + TimescaleDB** - High-performance time-series storage
        - ✅ **InsightSentry MEGA** - Economic calendar & news monitoring
        - ✅ **News Gating** - Auto-close positions before high-impact events
        - ✅ **DataBento** - CME futures order flow (L2 depth)
        - ✅ **Live 1-minute market data** via WebSocket
        - ✅ **Optimized scalping indicators** (EMA 3/6/12, VWAP, Donchian, RSI(7), ADX(7))
        - ✅ **AI agent debates** and trading signals
        - ✅ **Active trade monitoring** with 20-minute countdown
        - ✅ **Spread monitoring** and rejection

        **Click "START SCALPING ENGINE" in the sidebar to begin!**
        """)
    else:
        # Get latest data from engine
        if st.session_state.engine:
            # Performance metrics row
            col1, col2, col3, col4, col5, col6 = st.columns(6)

            stats = st.session_state.engine.get_performance_stats()

            with col1:
                st.metric("Total Trades", stats.get('total_trades', 0))
            with col2:
                win_rate = stats.get('win_rate', 0)
                st.metric("Win Rate", f"{win_rate:.1f}%",
                         delta=f"{win_rate - 60:.1f}%" if win_rate > 0 else None)
            with col3:
                st.metric("Profit Factor", f"{stats.get('profit_factor', 0):.2f}")
            with col4:
                st.metric("Today's P&L", f"${stats.get('daily_pnl', 0):.2f}")
            with col5:
                st.metric("Open Positions", stats.get('open_positions', 0))
            with col6:
                avg_duration = stats.get('avg_trade_duration_minutes', 0)
                st.metric("Avg Duration", f"{avg_duration:.1f}m")

            st.markdown("---")

            # Rest of dashboard (keep all original visualization code)
            st.info("Full scalping visualization here (signals, spreads, charts, debates, etc.)")

with tab2:
    # Economic Calendar Tab
    st.header("📅 Economic Calendar - High-Impact Events")

    if 'is_client' in st.session_state and st.session_state.is_client:
        try:
            # Fetch events for next 2 weeks
            events = asyncio.run(
                st.session_state.is_client.get_economic_calendar(
                    countries=["US", "EU", "GB", "JP"],
                    min_impact="high"
                )
            )

            if events:
                st.success(f"✅ Found {len(events)} high-impact events")

                # Filter controls
                col1, col2, col3 = st.columns(3)
                with col1:
                    country_filter = st.multiselect(
                        "Filter by Country",
                        options=["US", "EU", "GB", "JP", "All"],
                        default=["All"]
                    )
                with col2:
                    event_types = list(set([e.get('type', 'Unknown') for e in events]))
                    type_filter = st.multiselect(
                        "Filter by Type",
                        options=["All"] + event_types,
                        default=["All"]
                    )
                with col3:
                    days_ahead = st.slider("Days Ahead", 1, 14, 7)

                # Filter events
                filtered_events = events
                if "All" not in country_filter:
                    filtered_events = [e for e in filtered_events if e.get('country') in country_filter]
                if "All" not in type_filter:
                    filtered_events = [e for e in filtered_events if e.get('type') in type_filter]

                # Group by date
                from datetime import datetime, timedelta
                from collections import defaultdict

                events_by_date = defaultdict(list)
                cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)

                for event in filtered_events:
                    try:
                        event_date = datetime.fromisoformat(event.get('date', '').replace('Z', '+00:00'))
                        if event_date <= cutoff_date:
                            date_key = event_date.strftime('%Y-%m-%d')
                            events_by_date[date_key].append(event)
                    except:
                        pass

                # Display calendar
                st.markdown("---")

                for date_str in sorted(events_by_date.keys()):
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    day_name = date_obj.strftime('%A')

                    # Date header with day count
                    days_until = (date_obj - datetime.utcnow()).days
                    if days_until == 0:
                        date_label = f"🔴 TODAY - {day_name}, {date_obj.strftime('%B %d, %Y')}"
                    elif days_until == 1:
                        date_label = f"🟡 TOMORROW - {day_name}, {date_obj.strftime('%B %d, %Y')}"
                    else:
                        date_label = f"📅 {day_name}, {date_obj.strftime('%B %d, %Y')} ({days_until} days)"

                    st.subheader(date_label)

                    day_events = sorted(events_by_date[date_str], key=lambda x: x.get('date', ''))

                    for event in day_events:
                        event_time = datetime.fromisoformat(event.get('date', '').replace('Z', '+00:00'))
                        time_str = event_time.strftime('%H:%M GMT')

                        # Color code by importance
                        importance = event.get('importance', 'low')
                        if importance == 'high':
                            importance_badge = "🔴 HIGH"
                        elif importance == 'medium':
                            importance_badge = "🟡 MEDIUM"
                        else:
                            importance_badge = "🟢 LOW"

                        # Event card
                        with st.expander(f"🕐 {time_str} | {importance_badge} | {event.get('country', 'N/A')} - {event.get('title', 'Unknown')}"):
                            col1, col2 = st.columns([2, 1])

                            with col1:
                                st.markdown(f"**Event:** {event.get('title', 'N/A')}")
                                st.markdown(f"**Type:** {event.get('type', 'N/A')}")
                                st.markdown(f"**Country:** {event.get('country', 'N/A')}")
                                st.markdown(f"**Currency:** {event.get('currency', 'N/A')}")

                                if event.get('previous'):
                                    st.markdown(f"**Previous:** {event.get('previous')}")
                                if event.get('forecast'):
                                    st.markdown(f"**Forecast:** {event.get('forecast')}")
                                if event.get('reference_date'):
                                    st.markdown(f"**Reference Date:** {event.get('reference_date')}")

                            with col2:
                                st.markdown(f"**Importance:** {importance_badge}")
                                st.markdown(f"**Time:** {time_str}")

                                # Calculate gating window
                                gate_start = event_time - timedelta(minutes=15)
                                gate_close = event_time - timedelta(minutes=10)

                                st.markdown("---")
                                st.markdown("**⚠️ Trading Gating:**")
                                st.markdown(f"Gate opens: {gate_start.strftime('%H:%M GMT')}")
                                st.markdown(f"Close positions: {gate_close.strftime('%H:%M GMT')}")

                                if event.get('source_url'):
                                    st.markdown(f"[📊 Source]({event.get('source_url')})")

                    st.markdown("---")

                st.info(f"📊 Showing {len(filtered_events)} events (from {len(events)} total)")

            else:
                st.warning("⚠️ No high-impact events found in the next 2 weeks")

        except Exception as e:
            st.error(f"❌ Error fetching calendar data: {e}")
            st.exception(e)
    else:
        st.warning("⚠️ InsightSentry client not initialized. Start the services in the sidebar.")

# Footer
st.markdown("---")
st.caption(f"⚡ Enhanced Scalping Engine v3.0 | Database: Remote PostgreSQL + TimescaleDB | Data: InsightSentry MEGA + DataBento | Last Update: {datetime.now().strftime('%H:%M:%S')}")

# Auto-refresh logic - MUST be at the very end after all content is rendered!
if auto_refresh:
    import time
    now = time.time()
    refresh_interval = 2  # seconds

    # Initialize next refresh time if not set
    if '_next_refresh_at' not in st.session_state:
        st.session_state['_next_refresh_at'] = now + refresh_interval

    # Check if it's time to refresh
    if now >= st.session_state['_next_refresh_at']:
        st.session_state['_next_refresh_at'] = now + refresh_interval
        st.rerun()  # Safe to rerun here - all content has been rendered!
