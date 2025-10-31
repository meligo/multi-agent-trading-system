"""
Paper Trading Dashboard V2 with Agent Analysis

Enhanced dashboard with tabs showing:
1. Trading - Main trading interface
2. Agent Analysis - Complete agent flow for each pair
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import json
from forex_config import ForexConfig
from forex_agents import ForexTradingSystem
from paper_trader import PaperTrader, PaperPosition, PaperTrade
from typing import List

# Page configuration
st.set_page_config(
    page_title="Paper Trading Dashboard V2",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'trader' not in st.session_state:
    st.session_state.trader = PaperTrader(initial_balance=50000.0)
    st.session_state.system = ForexTradingSystem(
        api_key=ForexConfig.IG_API_KEY,
        openai_api_key=ForexConfig.OPENAI_API_KEY
    )
    st.session_state.auto_trading_enabled = False
    st.session_state.signals_cache = {}
    st.session_state.agent_details_cache = {}
    st.session_state.last_update = None


def create_pnl_chart(trade_history: List[PaperTrade]) -> go.Figure:
    """Create cumulative P&L chart."""
    if not trade_history:
        fig = go.Figure()
        fig.add_annotation(
            text="No trades yet",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        fig.update_layout(height=300)
        return fig

    trades = sorted(trade_history, key=lambda t: t.exit_time)
    cumulative_pnl = []
    running_total = 0
    timestamps = []

    for trade in trades:
        running_total += trade.realized_pl
        cumulative_pnl.append(running_total)
        timestamps.append(trade.exit_time)

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


def create_trade_distribution_chart(trade_history: List[PaperTrade]) -> go.Figure:
    """Create trade distribution chart."""
    if not trade_history:
        fig = go.Figure()
        fig.add_annotation(
            text="No trades yet",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(height=300)
        return fig

    profits = [t for t in trade_history if t.realized_pl > 0]
    losses = [t for t in trade_history if t.realized_pl < 0]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=['Wins', 'Losses'],
        y=[len(profits), len(losses)],
        marker_color=['green', 'red'],
        text=[len(profits), len(losses)],
        textposition='auto',
    ))

    fig.update_layout(
        title="Trade Distribution",
        yaxis_title="Number of Trades",
        height=300,
        showlegend=False
    )

    return fig


def display_position_card(position: PaperPosition):
    """Display single position card."""
    is_profit = position.unrealized_pl > 0
    bg_color = "#d4edda" if is_profit else "#f8d7da"
    emoji = "📈" if position.side == 'BUY' else "📉"
    pnl_emoji = "🟢" if is_profit else "🔴"

    st.markdown(f"""
    <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
        <h4 style="margin: 0;">{emoji} {position.pair} {position.side}</h4>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Entry", f"{position.entry_price:.5f}")
    with col2:
        st.metric("Current", f"{position.current_price:.5f}")
    with col3:
        st.metric("Units", f"{int(position.units):,}")
    with col4:
        st.metric("P&L", f"€{position.unrealized_pl:.2f}",
                 delta=f"{pnl_emoji} {'Profit' if is_profit else 'Loss'}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**SL:** {position.stop_loss:.5f}")
    with col2:
        st.write(f"**TP:** {position.take_profit:.5f}")
    with col3:
        if st.button(f"Close Position", key=f"close_{position.position_id}"):
            st.session_state.trader.close_position(position.position_id, "MANUAL")
            st.rerun()


def render_trading_tab(trader, system, selected_pairs, auto_trading):
    """Render the main trading tab."""

    # Account summary
    st.header("💰 Account Summary")
    trader.update_positions()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Balance", f"€{trader.balance:,.2f}")
    with col2:
        st.metric("Equity", f"€{trader.equity:,.2f}")
    with col3:
        unrealized_pl = trader.get_unrealized_pnl()
        st.metric("Unrealized P&L", f"€{unrealized_pl:,.2f}",
                 delta="🟢 Profit" if unrealized_pl > 0 else "🔴 Loss")
    with col4:
        st.metric("Open Positions", len(trader.open_positions))
    with col5:
        st.metric("Total Trades", len(trader.trade_history))

    # Open Positions
    st.header("📈 Open Positions")

    if trader.open_positions:
        for position in trader.open_positions.values():
            display_position_card(position)
    else:
        st.info("No open positions")

    st.markdown("---")

    # Trading Signals
    st.header("🎯 AI Trading Signals")

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, pair in enumerate(selected_pairs):
        status_text.text(f"Analyzing {pair}... ({idx + 1}/{len(selected_pairs)})")
        progress_bar.progress((idx + 1) / len(selected_pairs))

        try:
            timeframe = '5'
            cache_key = f"{pair}_{datetime.now().strftime('%Y%m%d%H%M')}"

            if cache_key not in st.session_state.signals_cache:
                signal = system.generate_signal(pair, timeframe, '1')
                st.session_state.signals_cache[cache_key] = signal
            else:
                signal = st.session_state.signals_cache[cache_key]

            if signal:
                signal_emoji = "🟢" if signal.signal == 'BUY' else "🔴"
                bg_color = "#d4edda" if signal.signal == 'BUY' else "#f8d7da"

                st.markdown(f"""
                <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                    <h3>{signal_emoji} {pair} - {signal.signal} Signal ({signal.confidence*100:.0f}% confidence)</h3>
                </div>
                """, unsafe_allow_html=True)

                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric("Entry", f"{signal.entry_price:.5f}")
                with col2:
                    st.metric("Stop Loss", f"{signal.stop_loss:.5f}")
                with col3:
                    st.metric("Take Profit", f"{signal.take_profit:.5f}")
                with col4:
                    st.metric("R:R", f"{signal.risk_reward_ratio:.1f}:1")
                with col5:
                    units = trader.calculate_position_size(signal)
                    st.metric("Units", f"{units:,}")

                with st.expander("📋 Signal Details"):
                    st.markdown("**Reasoning:**")
                    for i, reason in enumerate(signal.reasoning, 1):
                        st.write(f"{i}. {reason}")

                col1, col2 = st.columns([3, 1])
                with col2:
                    if auto_trading:
                        st.info("Will auto-execute")
                        if f"executed_{cache_key}" not in st.session_state:
                            position_id = trader.open_position(signal)
                            if position_id:
                                st.success(f"✅ Trade executed!")
                                st.session_state[f"executed_{cache_key}"] = True
                    else:
                        if st.button(f"Execute Trade", key=f"execute_{pair}"):
                            position_id = trader.open_position(signal)
                            if position_id:
                                st.success("✅ Trade executed!")
                                st.rerun()
            else:
                st.info(f"⏸️ {pair} - HOLD (No clear setup)")

            st.markdown("---")

        except Exception as e:
            st.error(f"Error analyzing {pair}: {e}")

    progress_bar.empty()
    status_text.empty()

    st.markdown("---")

    # Performance Analytics
    st.header("📊 Performance Analytics")

    col1, col2 = st.columns(2)

    with col1:
        fig_pnl = create_pnl_chart(trader.trade_history)
        st.plotly_chart(fig_pnl, use_container_width=True)

    with col2:
        fig_dist = create_trade_distribution_chart(trader.trade_history)
        st.plotly_chart(fig_dist, use_container_width=True)

    # Statistics
    st.header("📈 Trading Statistics")

    stats = trader.get_statistics()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Trades", stats['total_trades'])
    with col2:
        st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
    with col3:
        st.metric("Avg Win", f"€{stats['avg_win']:.2f}")
    with col4:
        st.metric("Avg Loss", f"€{stats['avg_loss']:.2f}")
    with col5:
        st.metric("Profit Factor", f"{stats['profit_factor']:.2f}")

    # Trade History Table
    st.header("📜 Trade History")

    if trader.trade_history:
        trade_df = pd.DataFrame([
            {
                'Time': t.exit_time.strftime('%Y-%m-%d %H:%M'),
                'Pair': t.pair,
                'Side': t.side,
                'Entry': f"{t.entry_price:.5f}",
                'Exit': f"{t.exit_price:.5f}",
                'Units': f"{int(t.units):,}",
                'P&L (€)': f"{t.realized_pl:.2f}",
                'Pips': f"{t.realized_pl_pips:.1f}",
                'Reason': t.exit_reason
            }
            for t in sorted(trader.trade_history, key=lambda x: x.exit_time, reverse=True)
        ])

        st.dataframe(trade_df, use_container_width=True)

        csv = trade_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Trade History",
            data=csv,
            file_name=f"paper_trades_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No completed trades yet")


def render_agent_analysis_tab(system, selected_pairs):
    """Render the agent analysis tab showing complete flow."""

    st.header("🤖 Multi-Agent Analysis Flow")
    st.write("*See how all 4 agents analyze each currency pair with 53+ indicators*")

    st.markdown("---")

    # Pair selector for detailed view
    if selected_pairs:
        analysis_pair = st.selectbox(
            "Select pair for detailed analysis",
            selected_pairs,
            key="agent_analysis_pair"
        )

        if st.button("🔄 Run Analysis", key="run_agent_analysis"):
            with st.spinner(f"Running complete agent analysis for {analysis_pair}..."):
                try:
                    # Get complete agent flow
                    details = system.generate_signal_with_details(analysis_pair, '5', '1')
                    st.session_state.agent_details_cache[analysis_pair] = details
                except Exception as e:
                    st.error(f"Error running analysis: {e}")

        # Display cached results
        if analysis_pair in st.session_state.agent_details_cache:
            details = st.session_state.agent_details_cache[analysis_pair]

            # Overview
            st.success(f"✅ Analysis complete for {analysis_pair}")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Current Price", f"{details['analysis']['current_price']:.5f}")
            with col2:
                st.metric("5m Trend", details['analysis']['trend_primary'])
            with col3:
                st.metric("1m Trend", details['analysis']['trend_secondary'])

            st.markdown("---")

            # Agent Flow
            st.subheader("🔄 Agent Flow")

            # Step 1: Technical Analysis
            with st.expander("📊 Step 1: Technical Analysis (53+ Indicators)", expanded=True):
                st.write("**Market Data & Indicators**")

                indicators = details['analysis']['indicators']

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("**Core Indicators:**")
                    st.write(f"• RSI: {indicators['rsi_14']:.1f}")
                    st.write(f"• MACD: {indicators['macd']:.5f}")
                    st.write(f"• ADX: {indicators['adx']:.1f}")
                    st.write(f"• ATR: {indicators['atr']:.5f}")

                with col2:
                    st.markdown("**Volume Analysis:**")
                    st.write(f"• OBV Z-Score: {indicators['obv_zscore']:.2f}")
                    st.write(f"• OBV Change: {indicators['obv_change_rate']:.1f}%")
                    st.write(f"• VPVR POC: {indicators['vpvr_poc']:.5f}")
                    st.write(f"• Distance to POC: {indicators['vpvr_dist_poc']:.1f} pips")

                with col3:
                    st.markdown("**Market Structure:**")
                    st.write(f"• IB Range: {indicators['ib_range']:.5f}")
                    st.write(f"• IB Breakout Up: {'YES' if indicators['ib_breakout_up'] else 'NO'}")
                    st.write(f"• IB Breakout Down: {'YES' if indicators['ib_breakout_down'] else 'NO'}")
                    st.write(f"• FVG Bull: {'DETECTED' if indicators['fvg_bull'] else 'None'}")

                # Hedge Fund Strategies
                st.markdown("**Hedge Fund Strategies:**")
                hedge_strats = details['analysis']['hedge_strategies']

                col1, col2, col3, col4 = st.columns(4)

                for idx, (name, data) in enumerate(hedge_strats.items()):
                    col = [col1, col2, col3, col4][idx]
                    with col:
                        if data.get('detected'):
                            st.success(f"✅ {name.replace('_', ' ').title()}")
                            st.write(f"Strength: {data['strength']}%")
                            if 'direction' in data:
                                st.write(f"Direction: {data['direction']}")
                        else:
                            st.info(f"⏸️ {name.replace('_', ' ').title()}")

                # Show all indicators in expandable section
                with st.expander("🔍 All 53 Indicators (Raw Data)"):
                    indicator_df = pd.DataFrame([
                        {"Indicator": k, "Value": f"{v:.5f}" if isinstance(v, float) else str(v)}
                        for k, v in indicators.items()
                    ])
                    st.dataframe(indicator_df, use_container_width=True, height=400)

            # Step 2: Price Action Agent
            with st.expander("🎯 Step 2: Price Action Agent Analysis", expanded=True):
                price_action = details['price_action']

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Setup Detected", "YES" if price_action.get('has_setup') else "NO")
                    st.metric("Setup Type", price_action.get('setup_type') or "N/A")
                    st.metric("Direction", price_action.get('direction', 'NONE'))

                with col2:
                    st.metric("Confidence", f"{price_action.get('confidence', 0)}%")

                st.markdown("**Key Levels:**")
                for level in price_action.get('key_levels', []):
                    st.write(f"• {level}")

                st.markdown("**Reasoning:**")
                st.info(price_action.get('reasoning', 'N/A'))

                st.markdown("**Complete Output:**")
                st.json(price_action)

            # Step 3: Momentum Agent
            with st.expander("⚡ Step 3: Momentum Agent Analysis", expanded=True):
                momentum = details['momentum']

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Strong Momentum", "YES" if momentum.get('strong_momentum') else "NO")
                    st.metric("Direction", momentum.get('direction', 'NEUTRAL'))
                    st.metric("Timeframes Aligned", "YES" if momentum.get('timeframes_aligned') else "NO")

                with col2:
                    st.metric("Entry Timing", momentum.get('entry_timing', 'WAIT'))
                    st.metric("Confidence", f"{momentum.get('confidence', 0)}%")

                st.markdown("**Reasoning:**")
                st.info(momentum.get('reasoning', 'N/A'))

                st.markdown("**Complete Output:**")
                st.json(momentum)

            # Step 4: Decision Maker
            with st.expander("✅ Step 4: Decision Maker (Final Decision)", expanded=True):
                decision = details['decision']

                # Visual indicator for signal
                signal = decision.get('signal', 'HOLD')
                if signal == 'BUY':
                    st.success(f"🟢 FINAL DECISION: {signal}")
                elif signal == 'SELL':
                    st.error(f"🔴 FINAL DECISION: {signal}")
                else:
                    st.info(f"⏸️ FINAL DECISION: {signal}")

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Signal", signal)
                    st.metric("Confidence", f"{decision.get('confidence', 0)}%")

                with col2:
                    signal_obj = details['signal']
                    if signal_obj:
                        st.metric("Entry", f"{signal_obj.entry_price:.5f}")
                        st.metric("R:R Ratio", f"{signal_obj.risk_reward_ratio:.1f}:1")

                st.markdown("**Decision Reasons:**")
                for i, reason in enumerate(decision.get('reasons', []), 1):
                    st.write(f"{i}. {reason}")

                st.markdown("**Complete Output:**")
                st.json(decision)

            # Step 5: Final Signal
            if details['signal']:
                with st.expander("📋 Step 5: Final Trading Signal", expanded=True):
                    signal = details['signal']

                    st.success(f"✅ Tradeable signal generated!")

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Pair", signal.pair)
                        st.metric("Signal", signal.signal)

                    with col2:
                        st.metric("Entry", f"{signal.entry_price:.5f}")
                        st.metric("Confidence", f"{signal.confidence*100:.0f}%")

                    with col3:
                        st.metric("Stop Loss", f"{signal.stop_loss:.5f}")
                        st.metric("Risk", f"{signal.pips_risk:.1f} pips")

                    with col4:
                        st.metric("Take Profit", f"{signal.take_profit:.5f}")
                        st.metric("Reward", f"{signal.pips_reward:.1f} pips")

                    st.metric("Risk/Reward Ratio", f"{signal.risk_reward_ratio:.2f}:1")

                    st.markdown("**Signal Reasoning:**")
                    for i, reason in enumerate(signal.reasoning, 1):
                        st.write(f"{i}. {reason}")
            else:
                with st.expander("⏸️ Step 5: No Trading Signal"):
                    st.warning("No tradeable signal generated. Decision was HOLD or confidence too low.")

                    decision = details['decision']
                    st.write(f"**Signal:** {decision.get('signal', 'HOLD')}")
                    st.write(f"**Confidence:** {decision.get('confidence', 0)}%")
                    st.write(f"**Minimum Required:** {ForexConfig.MIN_CONFIDENCE * 100}%")

        else:
            st.info("👆 Click 'Run Analysis' to see the complete agent flow for the selected pair")

    else:
        st.warning("Please select at least one pair in the sidebar")


def main():
    """Main dashboard function with tabs."""

    # Title
    st.title("📊 Paper Trading Dashboard V2")
    st.write("*Complete multi-agent trading system with detailed analysis*")

    trader = st.session_state.trader
    system = st.session_state.system

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Controls")

        # Auto-trading toggle
        st.markdown("### 🤖 Auto-Trading")
        auto_trading = st.toggle(
            "Enable Auto-Trading",
            value=st.session_state.auto_trading_enabled,
            help="When enabled, trades will be automatically executed"
        )
        st.session_state.auto_trading_enabled = auto_trading

        if auto_trading:
            st.success("✅ Auto-Trading ACTIVE")
        else:
            st.info("ℹ️ Manual Mode")

        st.markdown("---")

        # Risk settings
        st.markdown("### 🛡️ Risk Settings")
        trader.max_positions = st.slider("Max Positions", 1, 10, 5)
        trader.risk_per_trade = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.0) / 100
        trader.max_daily_loss = st.slider("Max Daily Loss (%)", 1.0, 10.0, 5.0) / 100

        st.markdown("---")

        # Pair selection
        st.markdown("### 📊 Monitor Pairs")
        selected_pairs = st.multiselect(
            "Select Pairs",
            ForexConfig.ALL_PAIRS,
            default=ForexConfig.PRIORITY_PAIRS[:3]
        )

        st.markdown("---")

        # Refresh settings
        auto_refresh = st.checkbox("Auto-refresh", value=False)
        refresh_interval = st.slider("Refresh (seconds)", 10, 60, 30)

        if st.button("🔄 Refresh Now"):
            st.rerun()

        if st.session_state.last_update:
            st.write(f"Last: {st.session_state.last_update.strftime('%H:%M:%S')}")

    # Main content with tabs
    if not selected_pairs:
        st.warning("Please select at least one pair in the sidebar")
        return

    # Create tabs
    tab1, tab2 = st.tabs(["📈 Trading", "🤖 Agent Analysis"])

    with tab1:
        render_trading_tab(trader, system, selected_pairs, auto_trading)

    with tab2:
        render_agent_analysis_tab(system, selected_pairs)

    # Update last refresh time
    st.session_state.last_update = datetime.now()

    # Save state
    trader.save_state()

    # Auto-refresh
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
