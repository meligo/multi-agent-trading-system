"""
IG Real Trading Dashboard

Streamlit dashboard that:
- Starts IG trading worker automatically
- Shows real-time data from IG account
- Displays AI signals and analysis
- Executes REAL trades on IG demo account
"""

import streamlit as st
import pandas as pd
import time
import json
from datetime import datetime, timedelta
import threading
from typing import Dict, List, Optional

from forex_config import ForexConfig
from ig_concurrent_worker import IGConcurrentWorker
from trading_database import get_database
from ig_rate_limiter import get_rate_limiter
from forex_market_hours import get_market_hours
from service_manager import get_service_manager

# Page config
st.set_page_config(
    page_title="IG Real Trading Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Global worker singleton (persists across browser refreshes)
_global_worker = None
_global_worker_lock = threading.Lock()

def get_global_worker():
    """Get the global worker instance (persists across sessions)."""
    global _global_worker
    with _global_worker_lock:
        return _global_worker

def set_global_worker(worker):
    """Set the global worker instance."""
    global _global_worker
    with _global_worker_lock:
        _global_worker = worker

# Initialize session state
if 'worker' not in st.session_state:
    # Try to reconnect to existing worker
    existing_worker = get_global_worker()
    if existing_worker and existing_worker.running:
        st.session_state.worker = existing_worker
        st.session_state.worker_started = True
        st.session_state.auto_trading_enabled = existing_worker.auto_trading
    else:
        st.session_state.worker = None
        st.session_state.worker_started = False
        st.session_state.auto_trading_enabled = True  # Auto-enable trading by default

if 'confirm_close_all' not in st.session_state:
    st.session_state.confirm_close_all = False

# Initialize service manager (manages WebSocket collector, etc.)
if 'service_manager' not in st.session_state:
    st.session_state.service_manager = get_service_manager()

if 'enable_websocket' not in st.session_state:
    st.session_state.enable_websocket = True  # Tier 3 - WebSocket streaming (auto-enabled)

# Database
db = get_database()

# Auto-start services on first load
if 'auto_start_done' not in st.session_state:
    st.session_state.auto_start_done = False

if 'auto_start_worker_attempted' not in st.session_state:
    st.session_state.auto_start_worker_attempted = False

if not st.session_state.auto_start_done:
    # Auto-start WebSocket collector if enabled
    if st.session_state.enable_websocket:
        try:
            st.session_state.service_manager.start_all(enable_websocket=True)
        except Exception as e:
            print(f"⚠️ WebSocket auto-start failed: {e}")

    # Mark auto-start as done (only run once per session)
    st.session_state.auto_start_done = True


def start_worker(auto_trading: bool = False):
    """Start the IG trading worker in background."""
    # Check if market is open
    market_hours = get_market_hours()
    market_status = market_hours.get_market_status()

    if not market_status['is_open']:
        # Market is closed - show warning to user
        next_open = market_status['next_open'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')
        time_until = market_status['time_until_open_human']
        st.error(f"""
        🛑 **FOREX MARKET IS CLOSED**

        Cannot start trading system while market is closed.

        **Next Market Open:** {next_open}
        **Time Until Open:** {time_until}

        The system will automatically pause during closed market hours.
        """)
        return False

    # Check if worker already exists
    if st.session_state.worker is None or not st.session_state.worker.running:
        st.session_state.worker = IGConcurrentWorker(
            auto_trading=auto_trading,
            max_workers=1,  # Sequential analysis
            interval_seconds=ForexConfig.ANALYSIS_INTERVAL_SECONDS  # Configurable interval (default: 300s / 5 minutes)
        )
        st.session_state.worker.start()
        st.session_state.worker_started = True
        st.session_state.auto_trading_enabled = auto_trading

        # Store in global singleton for persistence
        set_global_worker(st.session_state.worker)

        # Show market session info
        session = market_hours.get_market_session()
        st.success(f"""
        ✅ **System Started**

        **Market Session:** {session}
        **Auto-Trading:** {'ENABLED ⚠️' if auto_trading else 'DISABLED ✓'}
        **Analysis Interval:** {ForexConfig.ANALYSIS_INTERVAL_SECONDS // 60} minutes

        System will automatically pause when market closes (Friday 5 PM EST).
        """)
        return True
    return False


def stop_worker():
    """Stop the IG trading worker."""
    if st.session_state.worker and st.session_state.worker.running:
        st.session_state.worker.stop()
        st.session_state.worker_started = False

        # Clear global singleton
        set_global_worker(None)

        return True
    return False


def get_worker_status() -> Dict:
    """Get current worker status."""
    if st.session_state.worker and st.session_state.worker.running:
        return st.session_state.worker.get_status()
    return {
        'running': False,
        'auto_trading': False,
        'account_balance': 0,
        'available_funds': 0,
        'open_positions': 0,
        'pairs_monitored': 0,
    }


def get_recent_signals(limit: int = 20) -> pd.DataFrame:
    """Get recent trading signals from database."""
    try:
        signals = db.get_recent_signals(limit=limit)
        if signals:
            df = pd.DataFrame(signals)
            # Format timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()


def get_signal_details(signal_id: int) -> Optional[Dict]:
    """
    Get full signal details including agent reasoning.

    Args:
        signal_id: Signal ID to fetch

    Returns:
        Dictionary with full signal details or None
    """
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    signal_id, pair, timeframe, signal, confidence,
                    entry_price, stop_loss, take_profit, risk_reward,
                    pips_risk, pips_reward, reasoning, indicators,
                    executed, timestamp, sl_method, tp_method,
                    rr_adjusted, calculation_steps
                FROM signals
                WHERE signal_id = ?
            """, (signal_id,))

            row = cursor.fetchone()
            if row:
                import json
                return {
                    'signal_id': row[0],
                    'pair': row[1],
                    'timeframe': row[2],
                    'signal': row[3],
                    'confidence': row[4],
                    'entry_price': row[5],
                    'stop_loss': row[6],
                    'take_profit': row[7],
                    'risk_reward': row[8],
                    'pips_risk': row[9],
                    'pips_reward': row[10],
                    'reasoning': json.loads(row[11]) if row[11] else [],
                    'indicators': json.loads(row[12]) if row[12] else {},
                    'executed': row[13],
                    'timestamp': row[14],
                    'sl_method': row[15],
                    'tp_method': row[16],
                    'rr_adjusted': row[17],
                    'calculation_steps': row[18]
                }
            return None
    except Exception as e:
        print(f"Error fetching signal details: {e}")
        return None


def get_agent_analysis(signal_id: int) -> Optional[Dict]:
    """
    Get agent analysis for a specific signal.

    Args:
        signal_id: Signal ID

    Returns:
        Dictionary with price_action, momentum, decision data
    """
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price_action, momentum, decision
                FROM agent_analysis
                WHERE signal_id = ?
            """, (signal_id,))

            row = cursor.fetchone()
            if row:
                import json
                return {
                    'price_action': json.loads(row[0]) if row[0] else {},
                    'momentum': json.loads(row[1]) if row[1] else {},
                    'decision': json.loads(row[2]) if row[2] else {}
                }
            return None
    except Exception as e:
        print(f"Error fetching agent analysis: {e}")
        return None


def get_open_positions() -> List[Dict]:
    """Get current open positions from IG."""
    if st.session_state.worker:
        return st.session_state.worker.trader.get_open_positions()
    return []


def close_all_positions() -> Dict:
    """
    Close all open positions on IG account.

    Returns:
        Dictionary with:
            - success_count: Number of positions closed successfully
            - failed_count: Number of positions that failed to close
            - total_count: Total positions attempted
            - errors: List of error messages
    """
    if not st.session_state.worker or not st.session_state.worker.trader:
        return {
            'success_count': 0,
            'failed_count': 0,
            'total_count': 0,
            'errors': ['Trading worker not running']
        }

    positions = get_open_positions()

    if not positions:
        return {
            'success_count': 0,
            'failed_count': 0,
            'total_count': 0,
            'errors': ['No open positions to close']
        }

    success_count = 0
    failed_count = 0
    errors = []

    for pos in positions:
        deal_id = pos.get('deal_id')
        pair = pos.get('pair', 'Unknown')

        if not deal_id:
            failed_count += 1
            errors.append(f"{pair}: No deal_id found")
            continue

        try:
            # Close the position
            result = st.session_state.worker.trader.close_position(deal_id)

            if result and result.get('dealStatus') == 'ACCEPTED':
                success_count += 1
            else:
                failed_count += 1
                reason = result.get('reason', 'Unknown reason') if result else 'No response'
                errors.append(f"{pair} (ID: {deal_id}): {reason}")
        except Exception as e:
            failed_count += 1
            errors.append(f"{pair} (ID: {deal_id}): {str(e)}")

    return {
        'success_count': success_count,
        'failed_count': failed_count,
        'total_count': len(positions),
        'errors': errors
    }


def get_rate_limit_stats() -> Dict:
    """Get current rate limit statistics."""
    limiter = get_rate_limiter()
    return limiter.get_stats()


# Main dashboard
st.title("🎯 IG Real Trading Dashboard")

# BIG STATUS BANNER at top
status = get_worker_status()

if status['running']:
    if status['auto_trading']:
        st.error("### 🔴 SYSTEM ACTIVE - AUTO-TRADING ENABLED - EXECUTING REAL TRADES!")
    else:
        st.success("### 🟢 SYSTEM ACTIVE - SIGNALS ONLY MODE")
else:
    st.warning("### ⚪ SYSTEM STOPPED - Click START to begin")

st.markdown("---")

# Auto-start trading worker (only once per session)
if not st.session_state.auto_start_worker_attempted and not status['running']:
    try:
        # Get market status
        market_hours = get_market_hours()
        market_status = market_hours.get_market_status()

        if market_status['is_open']:
            # Market is open - start worker with auto-trading enabled
            start_worker(auto_trading=st.session_state.auto_trading_enabled)
            st.session_state.auto_start_worker_attempted = True
            st.rerun()
        else:
            # Market is closed - just mark as attempted
            st.session_state.auto_start_worker_attempted = True
    except Exception as e:
        print(f"⚠️ Auto-start worker failed: {e}")
        st.session_state.auto_start_worker_attempted = True

# Sidebar - Controls
with st.sidebar:
    st.header("🎛️ Control Panel")

    st.markdown("---")

    # BIG STATUS INDICATOR
    if status['running']:
        st.markdown("## 🟢 RUNNING")
        st.success("System is actively scanning markets")
    else:
        st.markdown("## ⚪ STOPPED")
        st.warning("System is not running")

    st.markdown("---")

    # Auto-trading toggle
    st.markdown("### Trading Mode")
    auto_trading = st.checkbox(
        "🔴 Enable Auto-Trading (REAL TRADES!)",
        value=st.session_state.auto_trading_enabled,
        help="⚠️ When enabled, system will execute REAL trades on IG!"
    )

    if auto_trading:
        st.error("⚠️ AUTO-TRADING ACTIVE!\nReal trades will be executed automatically!")
    else:
        st.success("✓ SIGNALS ONLY\nNo trades will be executed")

    st.markdown("---")

    # Start/Stop buttons - BIGGER and CLEARER
    if status['running']:
        # Show STOP button prominently
        if st.button("⏹️ STOP SYSTEM", type="primary", use_container_width=True, help="Stop all trading activity"):
            if stop_worker():
                st.success("✅ System stopped!")
                st.rerun()
    else:
        # Show START button prominently
        if st.button("▶️ START SYSTEM", type="primary", use_container_width=True, help="Begin scanning for opportunities"):
            if start_worker(auto_trading=auto_trading):
                st.success("✅ System started!")
                st.rerun()

    st.markdown("---")

    # Emergency Close All Button in Sidebar
    if status['running']:
        positions = get_open_positions()
        if positions and len(positions) > 0:
            st.markdown("### 🚨 Emergency Controls")

            if st.button("🛑 Close All Positions", use_container_width=True, help=f"Close all {len(positions)} open position(s)"):
                st.session_state.confirm_close_all = True
                st.rerun()

            st.caption(f"Currently {len(positions)} position(s) open")

    st.markdown("---")

    # Market Hours Info
    st.markdown("### 🕐 Market Hours")
    market_hours = get_market_hours()
    market_status = market_hours.get_market_status()

    if market_status['is_open']:
        session = market_hours.get_market_session()
        st.success(f"**OPEN** ({session})")
        next_close = market_status['next_close'].strftime('%a %H:%M %Z')
        time_until = market_status['time_until_close_human']
        st.caption(f"Closes: {next_close}")
        st.caption(f"In: {time_until}")
    else:
        st.error("**CLOSED**")
        next_open = market_status['next_open'].strftime('%a %H:%M %Z')
        time_until = market_status['time_until_open_human']
        st.caption(f"Opens: {next_open}")
        st.caption(f"In: {time_until}")

    st.markdown("---")

    # Backend Services Status
    st.markdown("### 🔧 Backend Services")

    service_status = st.session_state.service_manager.get_status()

    # Smart Caching (Tier 1) - Always Active
    caching = service_status['caching']
    st.success(f"✅ **{caching['name']}**")
    st.caption(caching['cache_hit_rate'])
    st.caption("Reduces API calls by 96%")

    # WebSocket Collector (Tier 3) - Optional
    ws = service_status['websocket']
    if ws['status'] == 'running':
        st.success(f"✅ **{ws['name']}**")
        st.caption(f"Uptime: {ws['uptime']}")
        st.caption("Real-time streaming (0 API calls)")
    elif ws['status'] == 'disabled':
        st.info(f"ℹ️ **{ws['name']}**")
        st.caption(ws['reason'])

        # Enable WebSocket checkbox
        enable_ws = st.checkbox(
            "Enable WebSocket (Tier 3)",
            value=st.session_state.enable_websocket,
            help="Start real-time streaming (requires trading-ig library)"
        )

        if enable_ws and not st.session_state.enable_websocket:
            st.session_state.enable_websocket = True
            st.session_state.service_manager.start_all(enable_websocket=True)
            st.rerun()
    elif ws['status'] == 'not_started':
        st.warning(f"⚪ **{ws['name']}**")
        st.caption("Not running (using Tier 1 caching)")
    else:
        st.error(f"❌ **{ws['name']}**")
        st.caption(f"Status: {ws['status']}")
        if ws['reason']:
            st.caption(ws['reason'])

    st.markdown("---")

    # Worker Status Details
    st.markdown("### System Info")

    if status['running']:
        st.metric("Active Pairs", f"{status['pairs_monitored']} pairs")
        interval_mins = ForexConfig.ANALYSIS_INTERVAL_SECONDS // 60
        st.metric("Scan Interval", f"{interval_mins} minutes" if interval_mins >= 1 else f"{ForexConfig.ANALYSIS_INTERVAL_SECONDS} seconds")
        st.metric("Last Update", datetime.now().strftime("%H:%M:%S"))
    else:
        st.info("System not running")
        st.caption("Click START to begin")

    st.markdown("---")

    # Rate Limits
    st.markdown("### API Rate Limits")
    rate_stats = get_rate_limit_stats()

    account_pct = (rate_stats['account_requests'] / rate_stats['account_limit']) * 100
    st.progress(account_pct / 100)
    st.caption(f"Account: {rate_stats['account_requests']}/{rate_stats['account_limit']} requests")

    app_pct = (rate_stats['app_requests'] / rate_stats['app_limit']) * 100
    st.progress(app_pct / 100)
    st.caption(f"App: {rate_stats['app_requests']}/{rate_stats['app_limit']} requests")

    st.markdown("---")

    # All 28 Forex Pairs
    st.markdown("### All Forex Pairs (28)")

    st.caption("🔥 Priority Pairs (Analyzed):")
    for pair in ForexConfig.PRIORITY_PAIRS:
        st.text(f"  ✓ {pair}")

    st.markdown("---")
    st.caption("📊 All Pairs:")

    # Show all pairs in a scrollable area
    with st.expander("View All 28 Pairs", expanded=False):
        for pair in ForexConfig.ALL_PAIRS:
            if pair in ForexConfig.PRIORITY_PAIRS:
                st.text(f"🔥 {pair} (active)")
            else:
                st.text(f"   {pair}")

# Main content area
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Signals", "💼 Positions", "📉 Analysis"])

with tab1:
    st.header("Account Overview")

    # Account metrics
    status = get_worker_status()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Account Balance",
            f"€{status['account_balance']:,.2f}",
            delta=None
        )

    with col2:
        st.metric(
            "Available Funds",
            f"€{status['available_funds']:,.2f}",
            delta=None
        )

    with col3:
        st.metric(
            "Open Positions",
            status['open_positions']
        )

    with col4:
        st.metric(
            "Auto-Trading",
            "ENABLED" if status['auto_trading'] else "DISABLED",
            delta="⚠️" if status['auto_trading'] else "✓"
        )

    st.markdown("---")

    # Recent activity
    st.subheader("Recent Trading Activity")

    recent_signals = get_recent_signals(limit=10)

    if not recent_signals.empty:
        # Show last 5 signals
        display_df = recent_signals[['timestamp', 'pair', 'signal', 'confidence', 'entry_price']].head(5)
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        display_df['confidence'] = display_df['confidence'].apply(lambda x: f"{x:.2%}")

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        interval_mins = ForexConfig.ANALYSIS_INTERVAL_SECONDS // 60
        interval_str = f"{interval_mins} minutes" if interval_mins >= 1 else f"{ForexConfig.ANALYSIS_INTERVAL_SECONDS} seconds"
        st.info(f"No recent signals. Worker will generate signals every {interval_str}.")

with tab2:
    st.header("Trading Signals")

    # Filter controls
    col1, col2 = st.columns([1, 3])

    with col1:
        signal_filter = st.selectbox(
            "Filter by Signal",
            ["All", "BUY", "SELL", "HOLD"]
        )

    with col2:
        pair_filter = st.multiselect(
            "Filter by Pair",
            options=ForexConfig.PRIORITY_PAIRS,
            default=ForexConfig.PRIORITY_PAIRS
        )

    # Get signals
    signals_df = get_recent_signals(limit=100)

    if not signals_df.empty:
        # Apply filters
        if signal_filter != "All":
            signals_df = signals_df[signals_df['signal'] == signal_filter]

        if pair_filter:
            signals_df = signals_df[signals_df['pair'].isin(pair_filter)]

        # Format for display
        display_cols = ['timestamp', 'pair', 'timeframe', 'signal',
                       'confidence', 'entry_price', 'stop_loss', 'take_profit']

        # Add risk_reward_ratio if it exists
        if 'risk_reward_ratio' in signals_df.columns:
            display_cols.append('risk_reward_ratio')
        elif 'risk_reward' in signals_df.columns:
            display_cols.append('risk_reward')

        display_df = signals_df[display_cols].copy()

        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        display_df['confidence'] = display_df['confidence'].apply(lambda x: f"{x:.2%}")

        # Color code signals
        def color_signal(val):
            if val == 'BUY':
                return 'background-color: #90EE90'
            elif val == 'SELL':
                return 'background-color: #FFB6C1'
            else:
                return 'background-color: #FFFFE0'

        styled_df = display_df.style.applymap(color_signal, subset=['signal'])

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            height=400
        )

        # Statistics
        st.markdown("---")
        st.subheader("Signal Statistics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Signals", len(signals_df))

        with col2:
            buy_count = len(signals_df[signals_df['signal'] == 'BUY'])
            st.metric("BUY Signals", buy_count)

        with col3:
            sell_count = len(signals_df[signals_df['signal'] == 'SELL'])
            st.metric("SELL Signals", sell_count)

        with col4:
            avg_confidence = signals_df['confidence'].mean()
            st.metric("Avg Confidence", f"{avg_confidence:.2%}")

        # Detailed Agent Reasoning Section
        st.markdown("---")
        st.subheader("🤖 Agent Decision Analysis")
        st.caption("Expand any signal below to see the complete agent reasoning chain")

        # Show top 10 most recent signals with expandable details
        recent_for_details = signals_df.head(10)

        for idx, row in recent_for_details.iterrows():
            signal_id = row.get('signal_id')
            if not signal_id:
                continue

            # Create expander for each signal
            with st.expander(
                f"📊 {row['pair']} - {row['signal']} @ {row['entry_price']:.5f} ({row['timestamp'].strftime('%H:%M:%S')}) - Confidence: {row['confidence']:.0%}",
                expanded=False
            ):
                # Get detailed signal info
                signal_details = get_signal_details(signal_id)
                agent_analysis = get_agent_analysis(signal_id)

                if signal_details:
                    # Display signal summary
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric("Entry Price", f"{signal_details['entry_price']:.5f}")
                        st.metric("Stop Loss", f"{signal_details['stop_loss']:.5f}")

                    with col2:
                        st.metric("Take Profit", f"{signal_details['take_profit']:.5f}")
                        st.metric("Risk/Reward", f"{signal_details['risk_reward']:.2f}:1")

                    with col3:
                        st.metric("Pips Risk", f"{signal_details.get('pips_risk', 0):.1f}")
                        st.metric("Pips Reward", f"{signal_details.get('pips_reward', 0):.1f}")

                    st.markdown("---")

                    # Display agent analysis if available
                    if agent_analysis:
                        st.markdown("### 🧠 Agent Analysis Chain")

                        # Price Action Agent
                        st.markdown("#### 1️⃣ Price Action Agent")
                        price_action = agent_analysis.get('price_action', {})
                        if price_action:
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.write("**Has Setup:**", "✅ Yes" if price_action.get('has_setup') else "❌ No")
                                st.write("**Direction:**", price_action.get('direction', 'N/A'))
                                st.write("**Confidence:**", f"{price_action.get('confidence', 0)}%")
                            with col2:
                                st.write("**Setup Type:**", price_action.get('setup_type', 'N/A'))
                                st.write("**Key Levels:**", ", ".join([str(l) for l in price_action.get('key_levels', [])]))

                            st.markdown("**💭 Reasoning:**")
                            st.info(price_action.get('reasoning', 'No reasoning provided'))
                        else:
                            st.warning("No price action analysis available")

                        st.markdown("---")

                        # Momentum Agent
                        st.markdown("#### 2️⃣ Momentum Agent")
                        momentum = agent_analysis.get('momentum', {})
                        if momentum:
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.write("**Momentum:**", momentum.get('momentum', 'N/A'))
                                st.write("**Strength:**", momentum.get('strength', 'N/A'))
                                st.write("**Confidence:**", f"{momentum.get('confidence', 0)}%")
                            with col2:
                                st.write("**Timeframe Alignment:**", momentum.get('timeframe_alignment', 'N/A'))
                                st.write("**Divergences:**", momentum.get('divergences', 'None'))

                            st.markdown("**💭 Reasoning:**")
                            st.info(momentum.get('reasoning', 'No reasoning provided'))
                        else:
                            st.warning("No momentum analysis available")

                        st.markdown("---")

                        # Decision Maker
                        st.markdown("#### 3️⃣ Decision Maker (Final Decision)")
                        decision = agent_analysis.get('decision', {})
                        if decision:
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                signal_emoji = "🟢" if decision.get('signal') == 'BUY' else "🔴" if decision.get('signal') == 'SELL' else "⚪"
                                st.write(f"**Final Signal:** {signal_emoji} {decision.get('signal', 'N/A')}")
                                st.write("**Confidence:**", f"{decision.get('confidence', 0)}%")
                            with col2:
                                st.write("**Agent Agreement:**", "✅" if decision.get('agent_agreement') else "⚠️ Disagreement")

                            st.markdown("**💭 Final Reasoning:**")
                            reasons = decision.get('reasons', [])
                            if isinstance(reasons, list):
                                for reason in reasons:
                                    st.write(f"• {reason}")
                            else:
                                st.info(str(reasons))
                        else:
                            st.warning("No decision analysis available")

                    else:
                        st.warning("Agent analysis not available for this signal. This may be an older signal from before agent tracking was implemented.")

                    # Display final reasoning bullets
                    if signal_details.get('reasoning'):
                        st.markdown("---")
                        st.markdown("### 📝 Final Signal Reasoning")
                        reasoning_list = signal_details['reasoning']
                        if isinstance(reasoning_list, list):
                            for reason in reasoning_list:
                                st.write(f"• {reason}")
                        else:
                            st.write(reasoning_list)

                else:
                    st.error("Could not load signal details")

    else:
        st.info("No signals yet. Start the worker to begin generating signals.")

with tab3:
    st.header("Open Positions (IG Account)")

    positions = get_open_positions()

    if positions:
        positions_df = pd.DataFrame(positions)

        # Display positions
        display_cols = ['pair', 'direction', 'size', 'level', 'profit_loss', 'stop_level', 'limit_level']
        available_cols = [col for col in display_cols if col in positions_df.columns]

        st.dataframe(
            positions_df[available_cols],
            use_container_width=True,
            hide_index=True
        )

        # Position statistics
        st.markdown("---")
        st.subheader("Position Statistics")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Positions", len(positions))

        with col2:
            total_pnl = positions_df['profit_loss'].sum() if 'profit_loss' in positions_df.columns else 0
            st.metric("Total P&L", f"€{total_pnl:,.2f}")

        with col3:
            winning = len(positions_df[positions_df['profit_loss'] > 0]) if 'profit_loss' in positions_df.columns else 0
            st.metric("Winning Positions", winning)

        # Close All Positions Button
        st.markdown("---")
        st.subheader("Emergency Controls")

        # Two-step confirmation process
        if not st.session_state.confirm_close_all:
            # First click: Show warning and ask for confirmation
            if st.button("🛑 CLOSE ALL POSITIONS", type="primary", use_container_width=True):
                st.session_state.confirm_close_all = True
                st.rerun()
        else:
            # Second step: Show confirmation dialog
            st.warning(f"⚠️ **WARNING**: You are about to close **{len(positions)} open position(s)**. This action cannot be undone!")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("✅ YES, CLOSE ALL", type="primary", use_container_width=True):
                    # Execute close all
                    with st.spinner("Closing all positions..."):
                        result = close_all_positions()

                    st.session_state.confirm_close_all = False

                    # Show results
                    if result['success_count'] > 0:
                        st.success(f"✅ Successfully closed {result['success_count']} position(s)")

                    if result['failed_count'] > 0:
                        st.error(f"❌ Failed to close {result['failed_count']} position(s)")
                        with st.expander("Show Error Details"):
                            for error in result['errors']:
                                st.text(f"• {error}")

                    # Refresh to show updated positions
                    time.sleep(1)
                    st.rerun()

            with col2:
                if st.button("❌ CANCEL", use_container_width=True):
                    st.session_state.confirm_close_all = False
                    st.rerun()

    else:
        st.info("No open positions on IG account.")
        st.caption("Positions will appear here when trades are executed.")

with tab4:
    st.header("Technical Analysis")

    # Select pair to analyze
    selected_pair = st.selectbox(
        "Select Currency Pair",
        options=ForexConfig.PRIORITY_PAIRS
    )

    st.info(f"Detailed analysis for {selected_pair} will be shown here.")
    st.caption("This tab will show charts, indicators, and AI agent analysis.")

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Refresh: {ForexConfig.DASHBOARD_REFRESH_SECONDS}s")

# Auto-refresh
time.sleep(ForexConfig.DASHBOARD_REFRESH_SECONDS)
st.rerun()
