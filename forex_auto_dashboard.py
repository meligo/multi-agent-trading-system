"""
Forex Auto-Trading Dashboard

Real-time dashboard with automated trading, position tracking, and P&L visualization.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
from forex_config import ForexConfig
from forex_agents import ForexTradingSystem
from oanda_trader import OandaTrader, OandaPosition, TradeHistory
from typing import List, Dict

# Page configuration
st.set_page_config(
    page_title="Forex Auto-Trading Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'trader' not in st.session_state:
    try:
        st.session_state.trader = OandaTrader(
            account_id=ForexConfig.OPENAI_API_KEY,  # Will be overridden
            api_token="",
            environment="practice"
        )
        st.session_state.system = ForexTradingSystem(
            api_key=ForexConfig.FINNHUB_API_KEY,
            openai_api_key=ForexConfig.OPENAI_API_KEY
        )
        st.session_state.auto_trading_enabled = False
        st.session_state.signals_cache = {}
        st.session_state.last_update = None
    except Exception as e:
        st.error(f"Failed to initialize: {e}")


def create_pnl_chart(trade_history: List[TradeHistory]) -> go.Figure:
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


def create_trade_distribution_chart(trade_history: List[TradeHistory]) -> go.Figure:
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


def display_position_card(position: OandaPosition):
    """Display single position card."""
    # Determine color
    is_profit = position.unrealized_pl > 0
    bg_color = "#d4edda" if is_profit else "#f8d7da"
    emoji = "📈" if position.side == 'long' else "📉"
    pnl_emoji = "🟢" if is_profit else "🔴"

    st.markdown(f"""
    <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
        <h4 style="margin: 0;">{emoji} {position.pair} {position.side.upper()}</h4>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Entry", f"{position.entry_price:.5f}")
    with col2:
        st.metric("Current", f"{position.current_price:.5f}")
    with col3:
        st.metric("Units", f"{int(position.units)}")
    with col4:
        st.metric("P&L", f"€{position.unrealized_pl:.2f}",
                 delta=f"{pnl_emoji} {'Profit' if is_profit else 'Loss'}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**SL:** {position.stop_loss:.5f}")
    with col2:
        st.write(f"**TP:** {position.take_profit:.5f}")
    with col3:
        if st.button(f"Close {position.trade_id[:8]}", key=f"close_{position.trade_id}"):
            st.session_state.trader.close_position(position.trade_id, "MANUAL")
            st.rerun()


def main():
    """Main dashboard function."""

    # Title
    st.title("🤖 Forex Auto-Trading Dashboard")

    # Check if Oanda is configured
    try:
        import os
        account_id = os.getenv("OANDA_ACCOUNT_ID", "")
        api_token = os.getenv("OANDA_API_TOKEN", "")

        if not account_id or not api_token or api_token == "your_oanda_api_token_here":
            st.error("⚠️ Oanda API not configured! Please set up your credentials.")
            st.info("""
            **How to get your Oanda API credentials:**

            1. Go to: https://www.oanda.com/account/tpa/personal_token
            2. Generate a Personal Access Token
            3. Copy the token and add to `.env` file:
               ```
               OANDA_ACCOUNT_ID=62356299
               OANDA_API_TOKEN=your_token_here
               OANDA_ENVIRONMENT=practice  # or 'live' for real money
               ```
            4. Restart the dashboard

            **Note:** Your MT5 credentials (62356299 / $Statictree65) are for the MT5 platform.
            The API requires a separate API token for automated trading.
            """)
            return

        # Initialize trader
        environment = os.getenv("OANDA_ENVIRONMENT", "practice")
        if 'trader' not in st.session_state or st.session_state.trader.account_id != account_id:
            st.session_state.trader = OandaTrader(account_id, api_token, environment)
            st.session_state.trader.load_trade_history()

    except Exception as e:
        st.error(f"Error initializing Oanda trader: {e}")
        return

    trader = st.session_state.trader
    system = st.session_state.system

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Auto-Trading Controls")

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
            st.warning("⚠️ Real trades will be executed!")
        else:
            st.info("ℹ️ Auto-Trading DISABLED")
            st.write("Signals will be shown but not executed")

        st.markdown("---")

        # Safety settings
        st.markdown("### 🛡️ Safety Settings")
        trader.max_positions = st.slider("Max Open Positions", 1, 10, 5)
        trader.risk_per_trade = st.slider("Risk Per Trade (%)", 0.5, 5.0, 1.0) / 100
        trader.max_daily_loss = st.slider("Max Daily Loss (%)", 1.0, 10.0, 5.0) / 100

        st.markdown("---")

        # Pair selection
        st.markdown("### 📊 Monitor Pairs")
        selected_pairs = st.multiselect(
            "Select Pairs to Monitor",
            ForexConfig.ALL_PAIRS,
            default=ForexConfig.PRIORITY_PAIRS[:3]  # Start with fewer pairs
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

    try:
        account_info = trader.get_account_info()['account']
        balance = float(account_info['balance'])
        unrealized_pl = float(account_info['unrealizedPL'])
        equity = balance + unrealized_pl

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Balance", f"€{balance:,.2f}")
        with col2:
            st.metric("Equity", f"€{equity:,.2f}")
        with col3:
            st.metric("Unrealized P&L", f"€{unrealized_pl:,.2f}",
                     delta="🟢 Profit" if unrealized_pl > 0 else "🔴 Loss")
        with col4:
            positions = trader.get_current_positions()
            st.metric("Open Positions", len(positions))
        with col5:
            total_trades = len(trader.trade_history)
            st.metric("Total Trades", total_trades)

    except Exception as e:
        st.error(f"Failed to get account info: {e}")
        return

    # Open Positions
    st.header("📈 Open Positions")

    positions = trader.get_current_positions()
    if positions:
        # Update P&L
        trader.update_positions_pnl()

        for pos in positions:
            display_position_card(pos)
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
                            result = trader.place_order(signal, auto_execute=True)
                            if result:
                                st.success(f"✅ Trade executed!")
                                st.session_state[f"executed_{cache_key}"] = True
                    else:
                        if st.button(f"Execute Trade", key=f"execute_{pair}"):
                            result = trader.place_order(signal, auto_execute=True)
                            if result:
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

    # P&L Visualization
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

    # Trade History Table
    st.header("📜 Trade History")

    if trader.trade_history:
        trade_df = pd.DataFrame([
            {
                'Time': t.exit_time.strftime('%Y-%m-%d %H:%M'),
                'Pair': t.pair,
                'Side': t.side.upper(),
                'Entry': f"{t.entry_price:.5f}",
                'Exit': f"{t.exit_price:.5f}",
                'Units': f"{int(t.units)}",
                'P&L (€)': f"{t.realized_pl:.2f}",
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
            file_name=f"trade_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No completed trades yet")

    # Update last refresh time
    st.session_state.last_update = datetime.now()

    # Save trade history
    trader.save_trade_history()

    # Auto-refresh
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
