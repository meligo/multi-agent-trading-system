"""
Paper Trading Dashboard

Real-time dashboard with automated paper trading, live position monitoring, and P&L tracking.
Uses live 1-minute candles to monitor positions and auto-close at SL/TP.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
from forex_config import ForexConfig
from forex_agents import ForexTradingSystem
from paper_trader import PaperTrader, PaperPosition, PaperTrade
from typing import List

# Page configuration
st.set_page_config(
    page_title="Paper Trading Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'trader' not in st.session_state:
    st.session_state.trader = PaperTrader(initial_balance=50000.0)
    st.session_state.system = ForexTradingSystem(
        api_key=ForexConfig.FINNHUB_API_KEY,
        openai_api_key=ForexConfig.OPENAI_API_KEY
    )
    st.session_state.auto_trading_enabled = False
    st.session_state.signals_cache = {}
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

    # Sort by exit time
    trades = sorted(trade_history, key=lambda t: t.exit_time)

    # Calculate cumulative P&L
    cumulative_pnl = []
    running_total = 0
    timestamps = []

    for trade in trades:
        running_total += trade.realized_pl
        cumulative_pnl.append(running_total)
        timestamps.append(trade.exit_time)

    # Create figure
    fig = go.Figure()

    # Add cumulative P&L line
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=cumulative_pnl,
        mode='lines+markers',
        name='Cumulative P&L',
        line=dict(color='green' if cumulative_pnl[-1] > 0 else 'red', width=3),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 0, 0.1)' if cumulative_pnl[-1] > 0 else 'rgba(255, 0, 0, 0.1)'
    ))

    # Add zero line
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

    # Calculate stats
    profits = [t.realized_pl for t in trade_history if t.realized_pl > 0]
    losses = [t.realized_pl for t in trade_history if t.realized_pl < 0]

    fig = go.Figure()

    # Win/Loss bars
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
    # Determine color
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


def main():
    """Main dashboard function."""

    # Title
    st.title("📊 Paper Trading Dashboard")
    st.write("*Simulated trading with live 1-minute candle monitoring*")

    trader = st.session_state.trader
    system = st.session_state.system

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Paper Trading Controls")

        # Auto-trading toggle
        st.markdown("### 🤖 Auto-Trading")
        auto_trading = st.toggle(
            "Enable Auto-Trading",
            value=st.session_state.auto_trading_enabled,
            help="When enabled, trades will be automatically executed based on AI signals"
        )
        st.session_state.auto_trading_enabled = auto_trading

        if auto_trading:
            st.success("✅ Auto-Trading ACTIVE")
            st.info("📝 Paper trading mode (no real money)")
        else:
            st.info("ℹ️ Auto-Trading DISABLED")
            st.write("Signals will be shown but not executed")

        st.markdown("---")

        # Safety settings
        st.markdown("### 🛡️ Risk Settings")
        trader.max_positions = st.slider("Max Open Positions", 1, 10, 5)
        trader.risk_per_trade = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.0) / 100
        trader.max_daily_loss = st.slider("Max Daily Loss (%)", 1.0, 10.0, 5.0) / 100

        st.markdown("---")

        # Pair selection
        st.markdown("### 📊 Monitor Pairs")
        selected_pairs = st.multiselect(
            "Select Pairs to Monitor",
            ForexConfig.ALL_PAIRS,
            default=ForexConfig.PRIORITY_PAIRS[:3]
        )

        st.markdown("---")

        # Refresh settings
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        refresh_interval = st.slider("Refresh (seconds)", 10, 60, 30)

        if st.button("🔄 Refresh Now"):
            st.rerun()

        # Display last update
        if st.session_state.last_update:
            st.write(f"Last: {st.session_state.last_update.strftime('%H:%M:%S')}")

    # Main content
    if not selected_pairs:
        st.warning("Please select at least one pair to monitor")
        return

    # Account summary
    st.header("💰 Account Summary")

    # Update positions to get latest P&L
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
            # Get analysis
            timeframe = '5'
            analysis = system.analyzer.analyze(pair, timeframe, '1')

            # Generate signal
            cache_key = f"{pair}_{datetime.now().strftime('%Y%m%d%H%M')}"
            if cache_key not in st.session_state.signals_cache:
                signal = system.generate_signal(pair, timeframe, '1')
                st.session_state.signals_cache[cache_key] = signal
            else:
                signal = st.session_state.signals_cache[cache_key]

            # Display signal
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
                    # Position size
                    units = trader.calculate_position_size(signal)
                    st.metric("Units", f"{units:,}")

                # Show reasoning
                with st.expander("📋 Signal Details"):
                    st.markdown("**Reasoning:**")
                    for i, reason in enumerate(signal.reasoning, 1):
                        st.write(f"{i}. {reason}")

                # Execute trade button
                col1, col2 = st.columns([3, 1])
                with col2:
                    if auto_trading:
                        st.info("Will auto-execute")
                        # Execute automatically
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
        # Cumulative P&L
        fig_pnl = create_pnl_chart(trader.trade_history)
        st.plotly_chart(fig_pnl, use_container_width=True)

    with col2:
        # Trade distribution
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

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total P&L", f"€{stats['total_pnl']:.2f}")
    with col2:
        st.metric("ROI", f"{stats['roi']:.2f}%")
    with col3:
        st.metric("Wins", f"{stats.get('wins', 0)} / {stats.get('losses', 0)}")

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

        # Download button
        csv = trade_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Trade History",
            data=csv,
            file_name=f"paper_trades_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No completed trades yet")

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
