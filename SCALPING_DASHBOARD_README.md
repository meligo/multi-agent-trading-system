# Scalping Engine Dashboard - User Guide

**Version**: 2.0
**Date**: 2025-10-31
**Branch**: `scalper-engine`

---

## 🎯 Overview

The **Scalping Dashboard** is a real-time, auto-starting web interface for monitoring and controlling the scalping engine. It provides:

- **Real-time WebSocket data** for EUR/USD, GBP/USD, USD/JPY
- **Live indicator calculations** (EMA ribbon, VWAP, Donchian, RSI(7), ADX(7), SuperTrend)
- **Agent debates and trading signals** in real-time
- **20-minute trade timer monitoring** with countdown
- **Spread monitoring and rejection** logic
- **Performance metrics** (win rate, profit factor, P&L)
- **Auto-start functionality** - everything launches automatically!

---

## 🚀 Quick Start (3 Commands)

### 1. Launch Dashboard (Auto-Starts Everything!)

```bash
./run_scalping_dashboard.sh
```

That's it! The script will:
- ✅ Check and activate virtual environment
- ✅ Install missing dependencies
- ✅ Start WebSocket collector for real-time data
- ✅ Launch Streamlit dashboard (opens in browser)
- ✅ Auto-connect to IG demo account

### 2. Start Scalping Engine

Once the dashboard opens:
1. Click **"🚀 START SCALPING ENGINE"** in the sidebar
2. Engine begins analyzing markets every 60 seconds
3. WebSocket provides real-time 1-minute candle data
4. Agents debate and generate signals automatically

### 3. Monitor and Trade

- Watch real-time indicators update every second
- See agent debates and trade signals
- Monitor open positions with 20-minute countdown timers
- View spread status (green = good, yellow = acceptable, red = rejected)
- Track performance metrics (win rate, profit factor, P&L)

---

## 📊 Dashboard Features

### 1. **Performance Metrics Bar**
Top row shows:
- Total Trades
- Win Rate (vs 60% target)
- Profit Factor
- Today's P&L
- Open Positions
- Average Trade Duration

### 2. **Trading Signals Section**
Real-time signals for each pair:
- 🟢 **GREEN**: LONG signal (>60% confidence)
- 🔴 **RED**: SHORT signal (>60% confidence)
- ⚪ **GRAY**: No signal / waiting for setup

Click to expand and see:
- Agent reasoning
- All indicator values
- Confidence percentage

### 3. **Spread Monitor**
Live spread display for all pairs:
- **Green**: Spread ≤ 0.8 pips (EXCELLENT)
- **Yellow**: Spread 0.8-1.2 pips (ACCEPTABLE)
- **Red**: Spread > 1.2 pips (REJECTED - no trade)

### 4. **Active Trades Monitoring**
For each open position:
- **Entry details**: Price, TP, SL
- **Current P&L**: Dollars and pips
- **⏱️ COUNTDOWN TIMER**: Minutes:seconds until 20-minute auto-close
  - Green = >5 minutes remaining
  - Yellow = 3-5 minutes
  - Red = <3 minutes, flashing

### 5. **Real-Time Indicator Charts**
Interactive Plotly charts with:

**Chart 1**: Price + EMAs + VWAP + Donchian
- Candlestick price action
- EMA Ribbon (3, 6, 12) - color-coded
- Session VWAP (orange dashed line)
- Donchian Channel (green/red dotted)

**Chart 2**: RSI(7)
- Fast RSI with 70/55/45/30 levels
- Green = bullish momentum (>55)
- Red = bearish momentum (<45)

**Chart 3**: ADX(7) + DI
- ADX trend strength (>18 = trending)
- +DI (green) vs -DI (red)

**Chart 4**: SuperTrend vs Price
- SuperTrend trailing stop
- Price vs SuperTrend line

### 6. **Agent Debates Section**
Expandable view showing:
- Fast Momentum Agent analysis
- Technical Agent analysis
- Scalp Validator (Judge) decision
- Reasoning for each decision

### 7. **Performance Charts**
Expandable section with:
- Cumulative P&L over time
- Win/Loss distribution
- Trade duration histogram

---

## ⚙️ Configuration & Controls

### Sidebar Controls

#### **Market Status**
- ✅ **GREEN**: Market open, ready to trade
- 🛑 **RED**: Market closed, shows next open time

#### **Engine Controls**
- **START ENGINE**: Launches scalping engine with auto-trading
- **STOP ENGINE**: Stops engine and closes all positions (requires confirmation)

#### **Strategy Configuration** (Read-Only)
- Pairs: EUR/USD, GBP/USD, USD/JPY
- Timeframe: 1-minute candles
- Analysis: Every 60 seconds
- TP/SL: 10 pips / 6 pips
- Max Duration: 20 minutes
- Max Spread: 1.2 pips

#### **WebSocket Status**
- Shows connection status
- Number of pairs subscribed
- Reconnect button if disconnected

#### **Auto-Refresh**
- Toggle 1-second auto-refresh (recommended ON)
- Keeps all data and charts updated in real-time

---

## 🔌 WebSocket Integration

The dashboard uses WebSocket for **real-time 1-minute data**:

### What WebSocket Provides:
- **Live price updates** (bid, ask, mid)
- **1-minute candles** (OHLC) as they form
- **Real-time spreads**
- **Volume data** for spike detection

### Auto-Start Behavior:
1. Dashboard launches → WebSocket collector starts automatically
2. Subscribes to EUR/USD, GBP/USD, USD/JPY
3. Buffers last 100 candles per pair
4. Engine reads from WebSocket buffer every 60 seconds
5. If WebSocket disconnects, auto-reconnect after 30s

### WebSocket vs REST API:
| Feature | WebSocket (Scalping) | REST API (Main System) |
|---------|---------------------|------------------------|
| Update Frequency | Real-time (1s) | Every 5 minutes |
| Latency | <50ms | 1-2 seconds |
| Best For | Scalping | Swing trading |

---

## 📈 Indicator Display

### EMA Ribbon (3, 6, 12)
- **Cyan**: EMA 3 (ultra-fast)
- **Blue**: EMA 6 (fast)
- **Purple**: EMA 12 (medium)

**Bullish**: 3 > 6 > 12 (all rising)
**Bearish**: 3 < 6 < 12 (all falling)

### VWAP (Orange Dashed Line)
- Anchored at 08:00 GMT (London open)
- Price above = long bias
- Price below = short bias
- ±1σ, ±2σ bands = S/R levels

### Donchian Channel
- **Green dotted**: Upper band (15-bar high)
- **Red dotted**: Lower band (15-bar low)
- Breakout above/below = momentum signal

### RSI(7) with Momentum Levels
- **>55 (rising)**: Bullish momentum
- **<45 (falling)**: Bearish momentum
- 70/30 = overbought/oversold

### ADX(7) Trend Filter
- **>18 (rising)**: Trending → take breakouts
- **<18**: Choppy → skip trades
- +DI vs -DI = directional confirmation

### SuperTrend Trailing Stop
- Price above SuperTrend = bullish
- Price below SuperTrend = bearish
- Use for exits and trailing stops

---

## ⏱️ 20-Minute Timer

Each open trade has a **visual countdown timer**:

```
⏱️ Time Remaining: 18:32
```

**Behavior**:
- Counts down from 20:00 to 00:00
- **>5 minutes**: White background (safe)
- **3-5 minutes**: Yellow background (closing soon)
- **<3 minutes**: Red background + flashing animation
- **00:00**: Auto-closes position immediately

**Why 20 Minutes?**
- Scalping = quick in/out (10-20 min target)
- Prevents holding losing positions too long
- Forces discipline and prevents hope trading

---

## 🎨 Visual Indicators

### Signal Colors
- 🟢 **GREEN**: LONG signal (confidence ≥60%)
- 🔴 **RED**: SHORT signal (confidence ≥60%)
- ⚪ **GRAY**: No clear signal

### Spread Colors
- **Green**: ≤0.8 pips (excellent for scalping)
- **Yellow**: 0.8-1.2 pips (acceptable)
- **Red**: >1.2 pips (REJECTED - too expensive)

### Timer Colors
- **White/Gray**: >5 minutes left
- **Yellow**: 3-5 minutes (warning)
- **Red (Flashing)**: <3 minutes (urgent)

### P&L Colors
- **Green**: Positive P&L
- **Red**: Negative P&L
- **Gray**: Breakeven

---

## 📊 Performance Metrics

### Win Rate
- Target: **60%+** for profitable scalping
- Dashboard shows delta vs 60% target
- Updates in real-time with each completed trade

### Profit Factor
- Total wins ÷ Total losses
- **>2.0** = excellent
- **1.5-2.0** = good
- **<1.5** = review strategy

### Average Trade Duration
- Target: **10-15 minutes**
- If consistently hitting 20-min limit, may indicate poor entries

### Today's P&L
- Resets at 00:00 GMT
- Includes both realized and unrealized P&L
- Auto-stops if daily loss limit reached

---

## 🛠️ Troubleshooting

### Dashboard Won't Start

**Problem**: `./run_scalping_dashboard.sh` fails

**Solutions**:
```bash
# Make script executable
chmod +x run_scalping_dashboard.sh

# Install dependencies manually
pip install streamlit plotly pandas numpy

# Run directly with Python
streamlit run scalping_dashboard.py
```

### WebSocket Not Connecting

**Problem**: Shows "WebSocket: DISCONNECTED"

**Solutions**:
1. Check `.env` file has correct IG credentials
2. Click "Reconnect WebSocket" button in sidebar
3. Restart dashboard
4. Check IG account is not rate-limited

### No Data Showing

**Problem**: Charts say "Loading data..."

**Solutions**:
1. Wait 60-120 seconds for initial data collection
2. Check market hours (08:00-20:00 GMT only)
3. Verify WebSocket is connected
4. Check IG API is responding (test in main system)

### Engine Not Starting

**Problem**: "Market is closed" or won't start

**Solutions**:
- Market hours: Sunday 5 PM EST - Friday 5 PM EST
- Optimal hours: 08:00-20:00 GMT (dashboard warning otherwise)
- Check IG account has available balance
- Ensure demo mode is enabled for testing

### Trades Not Executing

**Problem**: Signals showing but no trades

**Possible Reasons**:
1. Spread > 1.2 pips (rejected automatically)
2. Daily trade limit reached (40 trades/day)
3. Daily loss limit hit (-1.5%)
4. Consecutive losses paused trading (5 losses = 30-min pause)
5. Not enough confirmations (need 4+ signals)

**Check**:
- Spread monitor (must be green/yellow)
- Performance metrics (check limits)
- Agent reasoning (expand signal cards)

---

## 🔐 Security & Safety

### Demo Mode (Recommended)
- Dashboard starts in **DEMO mode** by default
- Uses IG demo account
- No real money at risk
- Perfect for testing and validation

### Risk Controls (Auto-Enforced)
✅ Max 40 trades per day
✅ Max 2 open positions simultaneously
✅ Daily loss limit: -1.5% account equity
✅ Consecutive loss protection: 5 losses = 30-min pause
✅ Spread rejection: Auto-skip if spread > 1.2 pips
✅ 20-minute auto-close: Prevents runaway losses

### API Keys
- Stored in `.env` file (never commit!)
- Not displayed in dashboard
- Use demo account keys for testing

---

## 📱 Mobile & Tablet Support

The dashboard is **responsive** but optimized for desktop:

- **Desktop** (recommended): Full charts, all features
- **Tablet**: Most features work, charts may be cramped
- **Mobile**: Basic functionality only, charts difficult to read

**Best Experience**:
- 1920x1080 or higher resolution
- Chrome, Firefox, or Safari (latest versions)
- Multiple monitors = optimal (charts on one, controls on other)

---

## ⚡ Performance Tips

### For Best Dashboard Performance:

1. **Auto-Refresh**: Keep ON for live updates
2. **WebSocket**: Always keep connected
3. **Browser**: Use Chrome/Firefox (best Plotly support)
4. **Network**: Stable internet (scalping needs low latency)

### If Dashboard Lags:

- Close unused chart tabs
- Reduce history depth (modify code: `last 50 candles` instead of 100)
- Disable auto-refresh temporarily
- Clear browser cache

---

## 📚 Files Reference

### Dashboard Files
- `scalping_dashboard.py` - Main Streamlit dashboard
- `run_scalping_dashboard.sh` - Auto-start script
- `SCALPING_DASHBOARD_README.md` - This file

### Engine Files
- `scalping_engine.py` - Core trading engine
- `scalping_agents.py` - AI agents (FastMomentum, Technical, etc.)
- `scalping_config.py` - Configuration parameters
- `scalping_indicators.py` - Indicator calculations
- `scalping_cli.py` - Command-line interface

### Documentation
- `INDICATOR_OPTIMIZATION.md` - Indicator research report
- `SCALPING_ENGINE_README.md` - Engine documentation
- `SCALPING_QUICKSTART.md` - Quick start guide
- `SCALPING_VERIFICATION.md` - Requirements checklist

---

## 🎓 Learning Resources

### Understand the Indicators:
1. Read `INDICATOR_OPTIMIZATION.md` for research backing
2. Watch indicators update in real-time on charts
3. Compare agent reasoning with indicator values
4. Review past trades to see which indicators predicted best

### Test Strategies:
1. Run in demo mode for 1-2 weeks
2. Track which indicators give best signals
3. Adjust parameters if needed (in `scalping_config.py`)
4. Validate 60%+ win rate before going live

---

## 🚀 Next Steps

### After Dashboard Is Running:

1. **Watch for 30-60 minutes**
   - Observe indicator updates
   - See how agents debate
   - Watch spread changes
   - Note signal generation

2. **Paper Trade for 1 Week**
   - Let engine run in demo mode
   - Track performance metrics
   - Validate win rate ≥60%
   - Check spread costs <20% of profit

3. **Optimize If Needed**
   - Adjust indicator parameters
   - Fine-tune entry confirmations
   - Test different time windows
   - Review losing trades for patterns

4. **Go Live (When Ready)**
   - Start with 0.01-0.05 lot size
   - Monitor first 50 trades closely
   - Scale up gradually if profitable
   - Maintain strict risk management

---

## ✅ Dashboard Checklist

Before each trading session:

- [ ] Dashboard launched successfully
- [ ] WebSocket status: ✅ ACTIVE
- [ ] Market status: ✅ OPEN (or shows next open time)
- [ ] All 3 pairs showing data
- [ ] Indicators calculating (charts updating)
- [ ] Engine ready to start
- [ ] Demo mode enabled (for testing)
- [ ] Auto-refresh: ON
- [ ] Browser: Chrome/Firefox
- [ ] Full-screen or large window

**Ready to Start**: Click "🚀 START SCALPING ENGINE"

---

## 📞 Support & Feedback

### Need Help?
1. Check `SCALPING_ENGINE_README.md` for detailed documentation
2. Review `INDICATOR_OPTIMIZATION.md` for indicator questions
3. Read `SCALPING_QUICKSTART.md` for quick reference
4. Check troubleshooting section above

### Found a Bug?
- Note what you were doing
- Screenshot the error
- Check browser console (F12)
- Review terminal output for errors

---

## 📖 Version History

### v2.0 (2025-10-31)
- ✅ Real-time dashboard with WebSocket integration
- ✅ Optimized indicators (EMA 3/6/12, VWAP, Donchian, RSI(7), ADX(7))
- ✅ Agent debates display
- ✅ 20-minute trade timer with countdown
- ✅ Spread monitoring with color coding
- ✅ Performance metrics and charts
- ✅ Auto-start functionality

### v1.0 (2025-10-31)
- Initial scalping engine implementation
- Basic indicators and agents
- CLI interface only

---

**Happy Scalping! 📈⚡**

*Remember: Start with demo mode, validate your win rate, and always respect your risk limits!*
