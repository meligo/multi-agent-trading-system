"""
Paper Trading Dashboard V3 - Database-Driven with Concurrent Worker

Features:
- Database-driven (all data from SQLite)
- Concurrent analysis of ALL currency pairs
- 60-second refresh interval
- Complete agent analysis history
- Real-time performance metrics
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from concurrent_worker import ConcurrentTradingWorker
from trading_database import get_database
from forex_config import ForexConfig

# Page configuration
st.set_page_config(
    page_title="Paper Trading Dashboard V3",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'worker' not in st.session_state:
    st.session_state.worker = ConcurrentTradingWorker(
        initial_balance=50000.0,
        auto_trading=False,
        max_workers=10
    )
    st.session_state.worker_running = False
    st.session_state.db = get_database()
    st.session_state.last_update = None


def create_pnl_chart(trades: list) -> go.Figure:
    """Create cumulative P&L chart from database trades."""
    if not trades:
        fig = go.Figure()
        fig.add_annotation(
            text="No trades yet",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        fig.update_layout(height=300)
        return fig

    # Sort by exit time
    trades = sorted(trades, key=lambda t: t['exit_time'])

    # Calculate cumulative P&L
    cumulative_pnl = []
    running_total = 0
    timestamps = []

    for trade in trades:
        running_total += trade['realized_pl']
        cumulative_pnl.append(running_total)
        timestamps.append(datetime.fromisoformat(trade['exit_time']))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=cumulative_pnl,
        mode='lines+markers',
        name='Cumulative P&L',
        line=dict(color='green' if cumulative_pnl[-1] > 0 else 'red', width=3),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 0, 0.1)' if cumulative_pnl[-1] > 0 else 'rgba(255, 0, 0, 0.1)'
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        title="Cumulative P&L Over Time",
        xaxis_title="Time",
        yaxis_title="P&L (€)",
        height=400,
        hovermode='x unified',
        showlegend=False
    )

    return fig


def render_positions_tab(db):
    """Render open positions tab."""
    st.header("📈 Open Positions")

    positions = db.get_open_positions()

    if not positions:
        st.info("No open positions")
        return

    for pos in positions:
        is_profit = pos.get('unrealized_pl', 0) > 0
        bg_color = "#d4edda" if is_profit else "#f8d7da"
        emoji = "📈" if pos['side'] == 'BUY' else "📉"
        pnl_emoji = "🟢" if is_profit else "🔴"

        st.markdown(f"""
        <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
            <h4 style="margin: 0;">{emoji} {pos['pair']} {pos['side']}</h4>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Entry", f"{pos['entry_price']:.5f}")
        with col2:
            st.metric("Current", f"{pos['current_price']:.5f}")
        with col3:
            st.metric("Units", f"{int(pos['units']):,}")
        with col4:
            st.metric("P&L", f"€{pos.get('unrealized_pl', 0):.2f}",
                     delta=f"{pnl_emoji} {'Profit' if is_profit else 'Loss'}")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**SL:** {pos['stop_loss']:.5f}")
        with col2:
            st.write(f"**TP:** {pos['take_profit']:.5f}")
        with col3:
            st.write(f"**Entry:** {datetime.fromisoformat(pos['entry_time']).strftime('%Y-%m-%d %H:%M')}")


def render_signals_tab(db):
    """Render recent signals tab."""
    st.header("🎯 Recent Signals")

    signals = db.get_signals(limit=20)

    if not signals:
        st.info("No signals generated yet")
        return

    for signal in signals:
        signal_color = "#d4edda" if signal['signal'] == 'BUY' else "#f8d7da"
        emoji = "🟢" if signal['signal'] == 'BUY' else "🔴"
        executed_badge = "✅ EXECUTED" if signal['executed'] else "⏸️ NOT EXECUTED"

        st.markdown(f"""
        <div style="background-color: {signal_color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
            <h4>{emoji} {signal['pair']} - {signal['signal']} ({signal['confidence']*100:.0f}% confidence)</h4>
            <p style="margin: 0; color: gray;">{executed_badge} | {datetime.fromisoformat(signal['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Entry", f"{signal['entry_price']:.5f}")
        with col2:
            st.metric("Stop Loss", f"{signal['stop_loss']:.5f}")
        with col3:
            st.metric("Take Profit", f"{signal['take_profit']:.5f}")
        with col4:
            st.metric("R:R", f"{signal['risk_reward_ratio']:.1f}:1")

        with st.expander("View Signal Reasoning"):
            for i, reason in enumerate(signal.get('reasoning', []), 1):
                st.write(f"{i}. {reason}")

        # SL/TP Calculation Details
        with st.expander("📐 SL/TP Calculation Details"):
            import json

            col1, col2, col3 = st.columns(3)

            with col1:
                sl_method = signal.get('sl_method', 'unknown')
                st.metric("SL Method", sl_method.upper())

            with col2:
                tp_method = signal.get('tp_method', 'unknown')
                st.metric("TP Method", tp_method.upper())

            with col3:
                rr_adjusted = signal.get('rr_adjusted', False)
                st.metric("RR Adjusted", "✅ Yes" if rr_adjusted else "❌ No")

            st.markdown("---")

            # Market Context
            st.subheader("Market Context")
            mcol1, mcol2, mcol3 = st.columns(3)

            with mcol1:
                atr = signal.get('atr_value')
                if atr:
                    st.metric("ATR", f"{atr:.5f}")
                else:
                    st.metric("ATR", "N/A")

            with mcol2:
                support = signal.get('nearest_support')
                if support:
                    st.metric("Support", f"{support:.5f}")
                else:
                    st.metric("Support", "N/A")

            with mcol3:
                resistance = signal.get('nearest_resistance')
                if resistance:
                    st.metric("Resistance", f"{resistance:.5f}")
                else:
                    st.metric("Resistance", "N/A")

            st.markdown("---")

            # Calculation Steps
            calc_steps = signal.get('calculation_steps')
            if calc_steps:
                if isinstance(calc_steps, str):
                    try:
                        calc_steps = json.loads(calc_steps)
                    except:
                        calc_steps = []

                if calc_steps:
                    st.subheader("Step-by-Step Calculation")
                    for i, step in enumerate(calc_steps, 1):
                        # Highlight warnings
                        if "⚠️" in step or "adjusted" in step.lower():
                            st.warning(f"{i}. {step}")
                        else:
                            st.write(f"{i}. {step}")
                else:
                    st.info("No calculation steps recorded")
            else:
                st.info("No calculation steps available (signal generated before tracking was enabled)")

        st.markdown("---")


def render_sl_tp_analysis_tab(db):
    """Render SL/TP calculation analysis tab."""
    st.header("📐 SL/TP Calculation Analysis")

    # Get recent signals with limit selector
    limit = st.slider("Show last N signals", 10, 100, 50, key="sl_tp_limit")
    signals = db.get_signals(limit=limit)

    if not signals:
        st.info("No signals generated yet. Run the worker to generate signals.")
        return

    import json

    # Calculate statistics
    rr_high = []  # >= 2.0
    rr_medium = []  # 1.5-2.0
    rr_low = []  # < 1.5
    sl_methods = {}
    tp_methods = {}
    rr_adjusted_count = 0

    for signal in signals:
        rr = signal['risk_reward_ratio']
        if rr >= 2.0:
            rr_high.append(signal)
        elif rr >= 1.5:
            rr_medium.append(signal)
        else:
            rr_low.append(signal)

        sl_method = signal.get('sl_method', 'unknown')
        tp_method = signal.get('tp_method', 'unknown')
        sl_methods[sl_method] = sl_methods.get(sl_method, 0) + 1
        tp_methods[tp_method] = tp_methods.get(tp_method, 0) + 1

        if signal.get('rr_adjusted'):
            rr_adjusted_count += 1

    # Display summary
    st.subheader("📊 R:R Distribution")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("High (≥2.0)", f"{len(rr_high)}", f"{len(rr_high)/len(signals)*100:.0f}%")
    with col2:
        st.metric("Medium (1.5-2.0)", f"{len(rr_medium)}", f"{len(rr_medium)/len(signals)*100:.0f}%")
    with col3:
        st.metric("Low (<1.5)", f"{len(rr_low)}", f"{len(rr_low)/len(signals)*100:.0f}%")

    st.markdown("---")

    # SL/TP Methods
    st.subheader("🎯 SL/TP Placement Methods")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Stop Loss Methods:**")
        for method, count in sorted(sl_methods.items()):
            pct = count/len(signals)*100
            st.write(f"- {method.upper()}: {count} ({pct:.0f}%)")

    with col2:
        st.markdown("**Take Profit Methods:**")
        for method, count in sorted(tp_methods.items()):
            pct = count/len(signals)*100
            st.write(f"- {method.upper()}: {count} ({pct:.0f}%)")

    st.markdown("---")

    # R:R Adjustments
    st.subheader("⚙️ R:R Adjustments")
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Adjusted to meet minimum", f"{rr_adjusted_count}", f"{rr_adjusted_count/len(signals)*100:.0f}%")
    with col2:
        natural_rr = len(signals) - rr_adjusted_count
        st.metric("Natural R:R", f"{natural_rr}", f"{natural_rr/len(signals)*100:.0f}%")

    st.markdown("---")

    # Examples from each category
    st.subheader("🔍 Examples by R:R Category")

    # High R:R examples
    if rr_high:
        st.markdown("**High R:R Examples (≥2.0):**")
        for i, signal in enumerate(rr_high[:3], 1):
            with st.expander(f"{i}. {signal['pair']} - {signal['signal']} @ {signal['entry_price']:.5f} (R:R: {signal['risk_reward_ratio']:.2f}:1)"):
                st.write(f"**Timestamp:** {signal['timestamp']}")
                st.write(f"**Pips Risk:** {signal['pips_risk']:.1f} | **Pips Reward:** {signal['pips_reward']:.1f}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**SL Method:** {signal.get('sl_method', 'unknown').upper()}")
                with col2:
                    st.write(f"**TP Method:** {signal.get('tp_method', 'unknown').upper()}")
                with col3:
                    rr_adj = signal.get('rr_adjusted', False)
                    st.write(f"**RR Adjusted:** {'✅ Yes' if rr_adj else '❌ No'}")

                # Show calculation steps
                calc_steps = signal.get('calculation_steps')
                if calc_steps:
                    if isinstance(calc_steps, str):
                        try:
                            calc_steps = json.loads(calc_steps)
                        except:
                            calc_steps = []

                    if calc_steps:
                        st.markdown("**Calculation Steps:**")
                        for step in calc_steps:
                            if "⚠️" in step:
                                st.warning(step)
                            else:
                                st.write(f"- {step}")

    # Medium R:R examples
    if rr_medium:
        st.markdown("---")
        st.markdown("**Medium R:R Examples (1.5-2.0):**")
        for i, signal in enumerate(rr_medium[:3], 1):
            with st.expander(f"{i}. {signal['pair']} - {signal['signal']} @ {signal['entry_price']:.5f} (R:R: {signal['risk_reward_ratio']:.2f}:1)"):
                st.write(f"**Timestamp:** {signal['timestamp']}")
                st.write(f"**Pips Risk:** {signal['pips_risk']:.1f} | **Pips Reward:** {signal['pips_reward']:.1f}")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**SL Method:** {signal.get('sl_method', 'unknown').upper()}")
                with col2:
                    st.write(f"**TP Method:** {signal.get('tp_method', 'unknown').upper()}")
                with col3:
                    rr_adj = signal.get('rr_adjusted', False)
                    st.write(f"**RR Adjusted:** {'✅ Yes' if rr_adj else '❌ No'}")

                # Show calculation steps
                calc_steps = signal.get('calculation_steps')
                if calc_steps:
                    if isinstance(calc_steps, str):
                        try:
                            calc_steps = json.loads(calc_steps)
                        except:
                            calc_steps = []

                    if calc_steps:
                        st.markdown("**Calculation Steps:**")
                        for step in calc_steps:
                            if "⚠️" in step:
                                st.warning(step)
                            else:
                                st.write(f"- {step}")

    # Low R:R examples (if any)
    if rr_low:
        st.markdown("---")
        st.markdown("**Low R:R Examples (<1.5) - Should be rare!:**")
        for i, signal in enumerate(rr_low[:3], 1):
            with st.expander(f"{i}. {signal['pair']} - {signal['signal']} @ {signal['entry_price']:.5f} (R:R: {signal['risk_reward_ratio']:.2f}:1)"):
                st.warning("⚠️ This signal has a low R:R ratio. This should be rare as the system adjusts to minimum 1.5:1")
                st.write(f"**Timestamp:** {signal['timestamp']}")
                st.write(f"**Pips Risk:** {signal['pips_risk']:.1f} | **Pips Reward:** {signal['pips_reward']:.1f}")


def render_agent_analysis_tab(db):
    """Render agent analysis history tab."""
    st.header("🤖 Agent Analysis History")

    # Pair selector
    col1, col2 = st.columns([3, 1])

    with col1:
        selected_pair = st.selectbox(
            "Select pair to view analysis history",
            ["All Pairs"] + ForexConfig.ALL_PAIRS
        )

    with col2:
        limit = st.slider("Show last N analyses", 5, 50, 10)

    # Get analyses
    if selected_pair == "All Pairs":
        analyses = db.get_agent_analysis(pair=None, limit=limit)
    else:
        analyses = db.get_agent_analysis(pair=selected_pair, limit=limit)

    if not analyses:
        st.info("No analysis data yet")
        return

    for analysis in analyses:
        timestamp = datetime.fromisoformat(analysis['timestamp'])
        signal_badge = "✅ SIGNAL" if analysis['signal_generated'] else "⏸️ HOLD"

        st.markdown(f"""
        <div style="background-color: #e9ecef; padding: 15px; border-radius: 10px; margin-bottom: 15px;">
            <h4>{analysis['pair']} - {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {signal_badge}</h4>
            <p><strong>Price:</strong> {analysis['current_price']:.5f} | <strong>Trend (5m):</strong> {analysis['trend_primary']} | <strong>Trend (1m):</strong> {analysis['trend_secondary']}</p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("View Complete Agent Flow"):
            # Price Action
            st.subheader("🎯 Price Action Agent")
            price_action = analysis.get('price_action_output', {})
            st.json(price_action)

            # Momentum
            st.subheader("⚡ Momentum Agent")
            momentum = analysis.get('momentum_output', {})
            st.json(momentum)

            # Decision
            st.subheader("✅ Decision Maker")
            decision = analysis.get('decision_output', {})
            st.json(decision)


def render_performance_tab(db):
    """Render performance metrics tab."""
    st.header("📊 Performance Over Time")

    # Time range selector
    time_range = st.selectbox("Time Range", ["Last 24 Hours", "Last 7 Days", "Last 30 Days"])

    hours = {
        "Last 24 Hours": 24,
        "Last 7 Days": 24 * 7,
        "Last 30 Days": 24 * 30
    }[time_range]

    metrics = db.get_performance_history(hours=hours)

    if not metrics:
        st.info("No performance data yet")
        return

    # Create dataframe
    df = pd.DataFrame(metrics)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Balance chart
    fig_balance = go.Figure()
    fig_balance.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['balance'],
        mode='lines',
        name='Balance',
        line=dict(color='blue', width=2)
    ))
    fig_balance.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['equity'],
        mode='lines',
        name='Equity',
        line=dict(color='green', width=2, dash='dash')
    ))
    fig_balance.update_layout(
        title="Balance & Equity Over Time",
        xaxis_title="Time",
        yaxis_title="Amount (€)",
        height=400,
        hovermode='x unified'
    )

    st.plotly_chart(fig_balance, use_container_width=True)

    # Win Rate chart
    fig_winrate = go.Figure()
    fig_winrate.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['win_rate'],
        mode='lines+markers',
        name='Win Rate',
        line=dict(color='purple', width=2),
        fill='tozeroy'
    ))
    fig_winrate.update_layout(
        title="Win Rate Over Time",
        xaxis_title="Time",
        yaxis_title="Win Rate (%)",
        height=300,
        hovermode='x unified'
    )

    st.plotly_chart(fig_winrate, use_container_width=True)


def main():
    """Main dashboard function."""
    st.title("📊 Paper Trading Dashboard V3 (Database-Driven)")
    st.write("*Concurrent analysis of all pairs with full database persistence*")

    worker = st.session_state.worker
    db = st.session_state.db

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Worker Controls")

        # Worker status
        if st.session_state.worker_running:
            st.success("✅ Worker RUNNING")
            if st.button("🛑 Stop Worker"):
                worker.stop()
                st.session_state.worker_running = False
                st.rerun()
        else:
            st.info("⏸️ Worker STOPPED")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("▶️ Start Worker"):
                    worker.auto_trading = st.session_state.get('auto_trading_enabled', False)
                    worker.start()
                    st.session_state.worker_running = True
                    st.rerun()
            with col2:
                if st.button("⚡ Run Once"):
                    worker.run_once()
                    st.rerun()

        st.markdown("---")

        # Auto-trading toggle
        st.markdown("### 🤖 Auto-Trading")
        auto_trading = st.toggle(
            "Enable Auto-Trading",
            value=worker.auto_trading,
            help="Auto-execute signals when confidence is high"
        )
        worker.auto_trading = auto_trading
        st.session_state['auto_trading_enabled'] = auto_trading

        if auto_trading:
            st.success("✅ Will execute signals")
        else:
            st.info("ℹ️ Signals shown only")

        st.markdown("---")

        # Risk settings
        st.markdown("### 🛡️ Risk Settings")
        worker.trader.max_positions = st.slider("Max Positions", 1, 20, 5)
        worker.trader.risk_per_trade = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.0) / 100

        st.markdown("---")

        # Database stats
        st.markdown("### 📊 Database Stats")
        stats = db.get_statistics()
        st.metric("Total Trades", stats['total_trades'])
        st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
        st.metric("Open Positions", stats['open_positions'])

        # Export button
        if st.button("📥 Export Data"):
            db.export_to_csv('trades', 'trades_export.csv')
            db.export_to_csv('signals', 'signals_export.csv')
            st.success("✅ Exported to CSV")

    # Account summary
    st.header("💰 Account Summary")

    latest_metrics = db.get_performance_history(hours=1)
    if latest_metrics:
        latest = latest_metrics[-1]

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Balance", f"€{latest['balance']:,.2f}")
        with col2:
            st.metric("Equity", f"€{latest['equity']:,.2f}")
        with col3:
            st.metric("Unrealized P&L", f"€{latest['unrealized_pl']:,.2f}")
        with col4:
            st.metric("Open Positions", latest['open_positions'])
        with col5:
            st.metric("Total Trades", latest['total_trades'])

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 Positions",
        "🎯 Signals",
        "📐 SL/TP Analysis",
        "🤖 Agent Analysis",
        "📊 Performance",
        "📜 Trade History"
    ])

    with tab1:
        render_positions_tab(db)

    with tab2:
        render_signals_tab(db)

    with tab3:
        render_sl_tp_analysis_tab(db)

    with tab4:
        render_agent_analysis_tab(db)

    with tab5:
        render_performance_tab(db)

    with tab6:
        st.header("📜 Trade History")
        trades = db.get_trades(limit=100)

        if trades:
            trade_df = pd.DataFrame([
                {
                    'Time': datetime.fromisoformat(t['exit_time']).strftime('%Y-%m-%d %H:%M'),
                    'Pair': t['pair'],
                    'Side': t['side'],
                    'Entry': f"{t['entry_price']:.5f}",
                    'Exit': f"{t['exit_price']:.5f}",
                    'Units': f"{int(t['units']):,}",
                    'P&L (€)': f"{t['realized_pl']:.2f}",
                    'Pips': f"{t['realized_pl_pips']:.1f}",
                    'Reason': t['exit_reason']
                }
                for t in trades
            ])

            st.dataframe(trade_df, use_container_width=True)

            # Cumulative P&L chart
            fig_pnl = create_pnl_chart(trades)
            st.plotly_chart(fig_pnl, use_container_width=True)
        else:
            st.info("No trades yet")

    # Update timestamp
    st.session_state.last_update = datetime.now()

    # Auto-refresh
    if st.session_state.worker_running:
        st.write(f"*Auto-refreshing every 30 seconds...*")
        time.sleep(30)
        st.rerun()


if __name__ == "__main__":
    main()
