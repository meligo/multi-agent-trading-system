"""
Scalping Engine Real-Time Dashboard

Auto-starting dashboard with:
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
from typing import Dict, List, Optional
import queue

from scalping_config import ScalpingConfig
from scalping_engine import ScalpingEngine
from scalping_indicators import ScalpingIndicators
from trading_database import get_database
from ig_rate_limiter import get_rate_limiter
from forex_market_hours import get_market_hours
from service_manager import get_service_manager

# Page config
st.set_page_config(
    page_title="⚡ Scalping Engine Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for scalping dashboard
st.markdown("""
<style>
    /* Fast-moving elements for scalping feel */
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

    .trade-timer {
        font-size: 32px;
        font-weight: bold;
        text-align: center;
        padding: 15px;
        border-radius: 10px;
        background: linear-gradient(to right, #ff416c, #ff4b2b);
        color: white;
    }

    .indicator-value {
        font-size: 18px;
        font-weight: bold;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
        margin: 5px 0;
    }

    .spread-ok {
        background-color: #28a745;
        color: white;
    }

    .spread-warning {
        background-color: #ffc107;
        color: black;
    }

    .spread-danger {
        background-color: #dc3545;
        color: white;
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

# Initialize session state
if 'engine' not in st.session_state:
    existing_engine = get_global_engine()
    if existing_engine and existing_engine.running:
        st.session_state.engine = existing_engine
        st.session_state.engine_started = True
    else:
        st.session_state.engine = None
        st.session_state.engine_started = False

if 'service_manager' not in st.session_state:
    st.session_state.service_manager = get_service_manager()

if 'enable_websocket' not in st.session_state:
    st.session_state.enable_websocket = True  # Auto-enabled for scalping

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

# AUTO-START: Launch everything on first load
if not st.session_state.auto_start_done:
    try:
        # Start WebSocket collector
        if st.session_state.enable_websocket:
            st.session_state.service_manager.start_all(enable_websocket=True)
            print("✅ WebSocket collector started")

        st.session_state.auto_start_done = True
    except Exception as e:
        print(f"⚠️ Auto-start error: {e}")


def start_scalping_engine(demo_mode: bool = True):
    """Start the scalping engine with auto-trading."""
    # Check market hours
    market_status = market_hours.get_market_status()

    if not market_status['is_open']:
        next_open = market_status['next_open'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')
        time_until = market_status['time_until_open_human']
        st.error(f"""
        🛑 **FOREX MARKET IS CLOSED**

        Cannot start scalping during closed hours.

        **Next Market Open:** {next_open}
        **Time Until Open:** {time_until}
        """)
        return False

    # Check if we're in optimal trading hours (08:00-20:00 GMT)
    current_hour = datetime.utcnow().hour
    if not (ScalpingConfig.TRADING_START_TIME.hour <= current_hour < ScalpingConfig.TRADING_END_TIME.hour):
        st.warning(f"""
        ⚠️ **OUTSIDE OPTIMAL SCALPING HOURS**

        Current time: {datetime.utcnow().strftime('%H:%M')} GMT
        Optimal hours: {ScalpingConfig.TRADING_START_TIME.strftime('%H:%M')} - {ScalpingConfig.TRADING_END_TIME.strftime('%H:%M')} GMT

        Spreads may be wider and liquidity lower.
        """)

    # Create and start engine
    if st.session_state.engine is None or not st.session_state.engine.running:
        st.session_state.engine = ScalpingEngine(demo_mode=demo_mode)
        st.session_state.engine.start()
        st.session_state.engine_started = True

        # Store globally
        set_global_engine(st.session_state.engine)

        session = market_hours.get_market_session()
        st.success(f"""
        ✅ **SCALPING ENGINE STARTED**

        **Market Session:** {session}
        **Mode:** {'DEMO' if demo_mode else 'LIVE ⚠️'}
        **Pairs:** {', '.join(ScalpingConfig.SCALPING_PAIRS)}
        **Timeframe:** 1-minute candles (60s analysis)
        **Max Trade Duration:** {ScalpingConfig.MAX_TRADE_DURATION_MINUTES} minutes
        **Spread Limit:** {ScalpingConfig.MAX_SPREAD_PIPS} pips

        🚀 Engine is now monitoring markets and will auto-trade when signals align!
        """)
        return True
    return False


def stop_scalping_engine():
    """Stop the scalping engine and close all positions."""
    if st.session_state.engine and st.session_state.engine.running:
        st.session_state.engine.stop()
        st.session_state.engine_started = False
        st.success("✅ Scalping engine stopped. All positions will be closed at market.")


def create_indicator_chart(pair: str, df: pd.DataFrame) -> go.Figure:
    """Create real-time indicator chart for a pair."""
    if df is None or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="Loading data...",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        return fig

    # Create subplots
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=(
            f'{pair} Price + EMAs + VWAP + Donchian',
            'RSI(7)',
            'ADX(7)',
            'SuperTrend'
        )
    )

    # Row 1: Price + EMAs + VWAP + Donchian
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price'
    ), row=1, col=1)

    # EMA Ribbon (3, 6, 12)
    if 'ema_3' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['ema_3'], name='EMA 3', line=dict(color='cyan', width=1)), row=1, col=1)
    if 'ema_6' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['ema_6'], name='EMA 6', line=dict(color='blue', width=1)), row=1, col=1)
    if 'ema_12' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['ema_12'], name='EMA 12', line=dict(color='purple', width=1)), row=1, col=1)

    # VWAP
    if 'vwap' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], name='VWAP', line=dict(color='orange', width=2, dash='dash')), row=1, col=1)

    # Donchian Channel
    if 'donchian_upper' in df.columns and 'donchian_lower' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['donchian_upper'], name='Donchian Upper', line=dict(color='green', width=1, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['donchian_lower'], name='Donchian Lower', line=dict(color='red', width=1, dash='dot')), row=1, col=1)

    # Row 2: RSI(7)
    if 'rsi' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['rsi'], name='RSI(7)', line=dict(color='purple', width=2)), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
        fig.add_hline(y=55, line_dash="dash", line_color="green", opacity=0.3, row=2, col=1)
        fig.add_hline(y=45, line_dash="dash", line_color="red", opacity=0.3, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)

    # Row 3: ADX(7)
    if 'adx' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['adx'], name='ADX(7)', line=dict(color='blue', width=2)), row=3, col=1)
        fig.add_hline(y=18, line_dash="dash", line_color="orange", opacity=0.5, row=3, col=1)

    if 'plus_di' in df.columns and 'minus_di' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['plus_di'], name='+DI', line=dict(color='green', width=1)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['minus_di'], name='-DI', line=dict(color='red', width=1)), row=3, col=1)

    # Row 4: SuperTrend
    if 'supertrend' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['supertrend'], name='SuperTrend', line=dict(color='orange', width=2)), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['close'], name='Price', line=dict(color='white', width=1)), row=4, col=1)

    fig.update_layout(
        height=800,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        template='plotly_dark'
    )

    return fig


def display_trade_timer(entry_time: datetime, max_duration_minutes: int):
    """Display countdown timer for open trade."""
    elapsed = (datetime.now() - entry_time).total_seconds()
    remaining = (max_duration_minutes * 60) - elapsed

    minutes_remaining = int(remaining // 60)
    seconds_remaining = int(remaining % 60)

    if remaining <= 0:
        st.markdown(f"""
        <div class="trade-timer">
        ⏰ TIME EXPIRED - AUTO-CLOSING
        </div>
        """, unsafe_allow_html=True)
    elif remaining < 180:  # Less than 3 minutes
        st.markdown(f"""
        <div class="trade-timer">
        ⏰ {minutes_remaining:02d}:{seconds_remaining:02d} - CLOSING SOON!
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="trade-timer">
        ⏱️ Time Remaining: {minutes_remaining:02d}:{seconds_remaining:02d}
        </div>
        """, unsafe_allow_html=True)


def display_spread_monitor(pair: str, current_spread: float):
    """Display current spread with color coding."""
    if current_spread <= ScalpingConfig.IDEAL_SPREAD_PIPS:
        css_class = "spread-ok"
        status = "EXCELLENT"
    elif current_spread <= ScalpingConfig.SPREAD_PENALTY_THRESHOLD:
        css_class = "spread-ok"
        status = "GOOD"
    elif current_spread <= ScalpingConfig.MAX_SPREAD_PIPS:
        css_class = "spread-warning"
        status = "ACCEPTABLE"
    else:
        css_class = "spread-danger"
        status = "TOO WIDE - TRADE REJECTED"

    st.markdown(f"""
    <div class="indicator-value {css_class}">
    📊 {pair} Spread: {current_spread:.1f} pips ({status})
    </div>
    """, unsafe_allow_html=True)


def display_signal_card(pair: str, signal: Dict):
    """Display trading signal with agent reasoning."""
    if signal is None:
        st.info(f"🔄 {pair}: Analyzing...")
        return

    direction = signal.get('direction', 'NONE')
    confidence = signal.get('confidence', 0)
    reasoning = signal.get('reasoning', [])

    if direction == "LONG":
        css_class = "scalp-signal-long"
        emoji = "🟢"
    elif direction == "SHORT":
        css_class = "scalp-signal-short"
        emoji = "🔴"
    else:
        css_class = "scalp-signal-none"
        emoji = "⚪"

    st.markdown(f"""
    <div class="{css_class}">
    {emoji} {pair}: {direction} ({confidence}% Confidence)
    </div>
    """, unsafe_allow_html=True)

    with st.expander(f"View {pair} Analysis Details"):
        st.write("**Agent Reasoning:**")
        for reason in reasoning:
            st.write(f"- {reason}")

        st.write("\n**Indicator Values:**")
        indicators = signal.get('indicators', {})
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("EMA 3", f"{indicators.get('ema_3', 0):.5f}")
            st.metric("EMA 6", f"{indicators.get('ema_6', 0):.5f}")
            st.metric("EMA 12", f"{indicators.get('ema_12', 0):.5f}")

        with col2:
            st.metric("VWAP", f"{indicators.get('vwap', 0):.5f}")
            st.metric("RSI(7)", f"{indicators.get('rsi', 0):.1f}")
            st.metric("ADX(7)", f"{indicators.get('adx', 0):.1f}")

        with col3:
            st.metric("SuperTrend", f"{indicators.get('supertrend', 0):.5f}")
            st.metric("Donchian Upper", f"{indicators.get('donchian_upper', 0):.5f}")
            st.metric("Donchian Lower", f"{indicators.get('donchian_lower', 0):.5f}")


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

st.title("⚡ Scalping Engine Dashboard")
st.markdown("**Fast Momentum Scalping** | 1-Minute Charts | 10-20 Minute Holds")

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

    # Start/Stop buttons
    if not st.session_state.engine_started:
        if st.button("🚀 START SCALPING ENGINE", type="primary", use_container_width=True):
            start_scalping_engine(demo_mode=True)
            st.rerun()
    else:
        if st.button("🛑 STOP ENGINE", type="secondary", use_container_width=True):
            if st.checkbox("Confirm stop and close all positions"):
                stop_scalping_engine()
                st.rerun()

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

    # Auto-refresh
    auto_refresh = st.checkbox("Auto-refresh (1s)", value=True)
    if auto_refresh:
        time.sleep(1)
        st.rerun()

# Main content area
if not st.session_state.engine_started:
    st.info("""
    🎯 **Welcome to the Scalping Engine Dashboard**

    This dashboard provides real-time monitoring of:
    - Live 1-minute market data via WebSocket
    - Optimized scalping indicators (EMA 3/6/12, VWAP, Donchian, RSI(7), ADX(7))
    - AI agent debates and trading signals
    - Active trade monitoring with 20-minute countdown
    - Spread monitoring and rejection
    - Performance metrics

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

        # Trading signals row
        st.subheader("🎯 Current Signals")
        sig_col1, sig_col2, sig_col3 = st.columns(3)

        for idx, pair in enumerate(ScalpingConfig.SCALPING_PAIRS):
            signal = st.session_state.trade_signals.get(pair)

            with [sig_col1, sig_col2, sig_col3][idx]:
                display_signal_card(pair, signal)

        st.markdown("---")

        # Spread monitoring row
        st.subheader("📊 Spread Monitor")
        spread_col1, spread_col2, spread_col3 = st.columns(3)

        for idx, pair in enumerate(ScalpingConfig.SCALPING_PAIRS):
            current_spread = st.session_state.engine.get_current_spread(pair) if st.session_state.engine else 1.0

            with [spread_col1, spread_col2, spread_col3][idx]:
                display_spread_monitor(pair, current_spread)

        st.markdown("---")

        # Open positions monitoring
        open_positions = st.session_state.engine.get_open_positions()

        if open_positions:
            st.subheader("⏱️ Active Trades")
            for position in open_positions:
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"**{position['pair']} {position['direction']}**")
                    st.write(f"Entry: {position['entry_price']:.5f} | TP: {position['take_profit']:.5f} | SL: {position['stop_loss']:.5f}")
                    st.write(f"Current P&L: ${position['current_pnl']:.2f} ({position['pips_pnl']:.1f} pips)")

                with col2:
                    display_trade_timer(position['entry_time'], ScalpingConfig.MAX_TRADE_DURATION_MINUTES)

        st.markdown("---")

        # Indicator charts
        st.subheader("📈 Real-Time Indicators")

        chart_tabs = st.tabs(ScalpingConfig.SCALPING_PAIRS)

        for idx, pair in enumerate(ScalpingConfig.SCALPING_PAIRS):
            with chart_tabs[idx]:
                df = st.session_state.live_data.get(pair)

                if df is not None and len(df) > 0:
                    fig = create_indicator_chart(pair, df)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"Loading {pair} data from WebSocket...")

        st.markdown("---")

        # Agent debates section
        with st.expander("🤖 View Latest Agent Debates"):
            debates = st.session_state.engine.get_recent_debates()

            if debates:
                for debate in debates[-5:]:  # Last 5 debates
                    st.markdown(f"**{debate['timestamp']} - {debate['pair']}**")
                    st.write(f"*Fast Momentum Agent:* {debate['momentum_analysis']}")
                    st.write(f"*Technical Agent:* {debate['technical_analysis']}")
                    st.write(f"**Scalp Validator Decision:** {debate['validator_decision']}")
                    st.markdown("---")
            else:
                st.info("No debates yet. Engine will start analyzing once data is available.")

        # Performance charts
        with st.expander("📊 View Performance Charts"):
            trade_history = st.session_state.engine.get_trade_history()

            if trade_history:
                # Cumulative P&L
                st.subheader("Cumulative P&L")
                cumulative_pnl = np.cumsum([t['pnl'] for t in trade_history])
                timestamps = [t['exit_time'] for t in trade_history]

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=cumulative_pnl,
                    mode='lines+markers',
                    line=dict(color='green' if cumulative_pnl[-1] > 0 else 'red', width=3),
                    fill='tozeroy'
                ))
                fig.update_layout(height=400, template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No completed trades yet.")

# Footer
st.markdown("---")
st.caption(f"⚡ Scalping Engine v2.0 | Indicators: EMA(3,6,12), VWAP, Donchian, RSI(7), ADX(7), SuperTrend | Last Update: {datetime.now().strftime('%H:%M:%S')}")
