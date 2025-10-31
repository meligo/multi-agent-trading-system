"""
Forex Trading Dashboard

Real-time web interface for monitoring forex signals and prices.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
from forex_config import ForexConfig
from forex_agents import ForexTradingSystem, ForexSignal
from typing import List, Dict, Optional

# Page configuration
st.set_page_config(
    page_title="Forex Trading Dashboard",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'system' not in st.session_state:
    st.session_state.system = ForexTradingSystem(
        api_key=ForexConfig.FINNHUB_API_KEY,
        openai_api_key=ForexConfig.OPENAI_API_KEY
    )
    st.session_state.signals = {}
    st.session_state.last_update = None


def format_price_change(current: float, previous: float) -> str:
    """Format price change with color."""
    if previous == 0:
        return ""

    change = current - previous
    pct_change = (change / previous) * 100

    if change > 0:
        return f"🟢 +{change:.5f} ({pct_change:+.2f}%)"
    elif change < 0:
        return f"🔴 {change:.5f} ({pct_change:.2f}%)"
    else:
        return f"⚪ {change:.5f} (0.00%)"


def create_candlestick_chart(df: pd.DataFrame, pair: str, timeframe: str) -> go.Figure:
    """Create candlestick chart with indicators."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{pair} - {timeframe}", "RSI")
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ),
        row=1, col=1
    )

    # Moving averages
    if 'ma_9' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['ma_9'], name='MA 9', line=dict(color='orange', width=1)),
            row=1, col=1
        )
    if 'ma_21' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['ma_21'], name='MA 21', line=dict(color='blue', width=1)),
            row=1, col=1
        )

    # RSI
    if 'rsi_14' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['rsi_14'], name='RSI', line=dict(color='purple', width=2)),
            row=2, col=1
        )
        # Overbought/Oversold lines
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    fig.update_layout(
        height=500,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        hovermode='x unified'
    )

    return fig


def display_signal_card(pair: str, signal: Optional[ForexSignal], analysis: Dict):
    """Display signal information card."""
    current_price = analysis['current_price']

    # Determine signal color
    if signal:
        if signal.signal == 'BUY':
            signal_color = "🟢"
            bg_color = "#d4edda"
        else:  # SELL
            signal_color = "🔴"
            bg_color = "#f8d7da"
    else:
        signal_color = "⏸️"
        bg_color = "#fff3cd"

    # Add commodity icon
    commodity_icon = ""
    if pair in ForexConfig.COMMODITY_PAIRS:
        if pair == "XAU_USD":
            commodity_icon = "🥇 "  # Gold
        elif pair == "XAG_USD":
            commodity_icon = "🥈 "  # Silver
        elif pair == "XPT_USD":
            commodity_icon = "⚪ "  # Platinum
        elif pair == "XPD_USD":
            commodity_icon = "💎 "  # Palladium

    # Create card
    with st.container():
        st.markdown(f"""
        <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
            <h3 style="margin: 0;">{signal_color} {commodity_icon}{pair}</h3>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Current Price", f"{current_price:.5f}")
            st.metric("5m Trend", analysis['trend_primary'])

        with col2:
            rsi = analysis['indicators']['rsi_14']
            st.metric("RSI", f"{rsi:.1f}")
            st.metric("1m Trend", analysis['trend_secondary'])

        with col3:
            if signal:
                st.metric("Signal", signal.signal)
                st.metric("Confidence", f"{signal.confidence*100:.0f}%")
            else:
                st.metric("Signal", "HOLD")
                st.metric("Confidence", "N/A")

        if signal:
            st.markdown("---")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.write(f"**Entry:** {signal.entry_price:.5f}")
            with col2:
                st.write(f"**Stop Loss:** {signal.stop_loss:.5f}")
            with col3:
                st.write(f"**Take Profit:** {signal.take_profit:.5f}")
            with col4:
                st.write(f"**R:R:** {signal.risk_reward_ratio:.1f}:1")

            st.markdown("**Reasoning:**")
            for i, reason in enumerate(signal.reasoning, 1):
                st.write(f"{i}. {reason}")

        # Show hedge fund strategies (always show, even for HOLD)
        if 'hedge_strategies' in analysis:
            st.markdown("---")
            st.markdown("**🏦 Hedge Fund Strategies Detected:**")

            hedge_strategies = analysis['hedge_strategies']
            detected_strategies = []

            for strategy_name, strategy_data in hedge_strategies.items():
                if strategy_data.get('detected'):
                    detected_strategies.append({
                        'name': strategy_name.replace('_', ' ').title(),
                        'strength': strategy_data.get('strength', 0),
                        'direction': strategy_data.get('direction', 'N/A')
                    })

            if detected_strategies:
                cols = st.columns(len(detected_strategies))
                for idx, (col, strat) in enumerate(zip(cols, detected_strategies)):
                    with col:
                        direction_emoji = "📈" if strat['direction'] == 'BULLISH' else "📉" if strat['direction'] == 'BEARISH' else "➡️"
                        st.metric(
                            f"{strat['name']}",
                            f"{strat['strength']}%",
                            f"{direction_emoji} {strat['direction']}"
                        )
            else:
                st.write("No hedge fund strategies detected")

        # Advanced indicators (expandable)
        with st.expander("📊 Advanced Indicators"):
            indicators = analysis['indicators']

            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Trend Strength**")
                adx = indicators.get('adx', 0)
                st.write(f"ADX: {adx:.1f} {'🔥 Strong' if adx > 25 else '📊 Weak'}")
                st.write(f"+DI: {indicators.get('pdi', 0):.1f}")
                st.write(f"-DI: {indicators.get('mdi', 0):.1f}")

            with col2:
                st.markdown("**Oscillators**")
                st.write(f"Stochastic: {indicators.get('stoch_k', 0):.1f}")
                st.write(f"Williams %R: {indicators.get('williams_r', 0):.1f}")
                st.write(f"CCI: {indicators.get('cci', 0):.1f}")

            with col3:
                st.markdown("**Ichimoku Cloud**")
                tenkan = indicators.get('ichimoku_tenkan', current_price)
                kijun = indicators.get('ichimoku_kijun', current_price)
                st.write(f"Tenkan: {tenkan:.5f}")
                st.write(f"Kijun: {kijun:.5f}")
                st.write(f"Cloud: {'🟢 Bullish' if current_price > max(indicators.get('ichimoku_senkou_a', 0), indicators.get('ichimoku_senkou_b', 0)) else '🔴 Bearish' if current_price < min(indicators.get('ichimoku_senkou_a', 999), indicators.get('ichimoku_senkou_b', 999)) else '⚪ Inside'}")


def main():
    """Main dashboard function."""

    # Title
    st.title("💱 Forex Trading Dashboard")

    # Sidebar
    with st.sidebar:
        st.header("Settings")

        # Pair selection
        selected_pairs = st.multiselect(
            "Select Currency Pairs",
            ForexConfig.ALL_PAIRS,  # Use ALL_PAIRS (forex + commodities)
            default=ForexConfig.PRIORITY_PAIRS
        )

        # Auto-refresh
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        refresh_interval = st.slider("Refresh interval (seconds)", 5, 60, 10)

        # Timeframe
        show_charts = st.checkbox("Show Charts", value=True)
        chart_timeframe = st.selectbox("Chart Timeframe", ["1m", "5m"], index=1)

        st.markdown("---")

        # Manual refresh button
        if st.button("🔄 Refresh Now"):
            st.session_state.signals = {}
            st.rerun()

        # Display last update
        if st.session_state.last_update:
            st.write(f"Last update: {st.session_state.last_update.strftime('%H:%M:%S')}")

    # Main content
    if not selected_pairs:
        st.warning("Please select at least one currency pair from the sidebar.")
        return

    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Analyze selected pairs
    total_pairs = len(selected_pairs)

    for idx, pair in enumerate(selected_pairs):
        status_text.text(f"Analyzing {pair}... ({idx + 1}/{total_pairs})")
        progress_bar.progress((idx + 1) / total_pairs)

        try:
            # Get analysis
            system = st.session_state.system

            # Get technical analysis
            timeframe = '5' if chart_timeframe == '5m' else '1'
            analysis = system.analyzer.analyze(pair, timeframe, '1')

            # Generate signal (if not cached)
            cache_key = f"{pair}_{datetime.now().strftime('%Y%m%d%H%M')}"
            if cache_key not in st.session_state.signals:
                signal = system.generate_signal(pair, timeframe, '1')
                st.session_state.signals[cache_key] = (signal, analysis)
            else:
                signal, analysis = st.session_state.signals[cache_key]

            # Display signal card
            display_signal_card(pair, signal, analysis)

            # Display charts
            if show_charts:
                df = analysis['df_primary']
                fig = create_candlestick_chart(df.tail(50), pair, chart_timeframe)
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

        except Exception as e:
            st.error(f"Error analyzing {pair}: {e}")

    # Clear progress
    progress_bar.empty()
    status_text.empty()

    # Update last refresh time
    st.session_state.last_update = datetime.now()

    # Auto-refresh
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
