# IG Real Trading Dashboard - READY

## 🎯 Integrated Real Trading Dashboard

Your complete trading system is now available in a **single Streamlit dashboard** that:

✅ Automatically scans for trading opportunities
✅ Shows real-time data from your IG account
✅ Displays AI-generated signals
✅ Executes **REAL trades** on your IG demo account
✅ Monitors open positions and P&L
✅ Respects API rate limits

## 🚀 How to Launch

### Option 1: Using Launch Script

```bash
./start_ig_dashboard.sh
```

### Option 2: Direct Command

```bash
streamlit run ig_trading_dashboard.py
```

The dashboard will open at: **http://localhost:8501**

## 📊 Dashboard Features

### Tab 1: Overview
- **Account balance** from IG (€20,000)
- **Available funds** for trading
- **Open positions** count
- **Auto-trading status**
- Recent trading activity

### Tab 2: Signals
- All AI-generated trading signals
- Filter by signal type (BUY/SELL/HOLD)
- Filter by currency pair
- Signal statistics and confidence levels
- Color-coded for easy reading

### Tab 3: Positions
- **Real positions** from your IG account
- Current P&L for each position
- Position details (entry, stop loss, take profit)
- Total P&L summary

### Tab 4: Analysis
- Technical analysis per pair
- Charts and indicators (coming soon)

## 🎛️ Control Panel (Sidebar)

### Start/Stop Buttons
- **▶️ Start**: Begins scanning for opportunities every 60 seconds
- **⏹️ Stop**: Stops the trading worker

### Auto-Trading Toggle

**🟢 DISABLED (Default)**:
- System generates signals only
- No trades are executed
- Safe for testing and observation

**🔴 ENABLED**:
- System executes REAL trades on IG
- Trades open automatically when signals trigger
- Uses 1% risk per trade
- Stop loss and take profit set automatically

### System Status
- Worker running/stopped
- Pairs being monitored (5 priority pairs)
- Update interval (60 seconds)

### API Rate Limits
- Real-time display of remaining API requests
- Account: X/30 requests per minute
- App: X/60 requests per minute
- Visual progress bars

### Monitored Pairs
Shows which 5 priority pairs are being analyzed:
- EUR_USD
- GBP_USD
- USD_JPY
- EUR_GBP
- AUD_USD

## 🔄 Automatic Operation

When you click **Start**:

1. **Background worker launches** automatically
2. **Every 60 seconds** it:
   - Fetches real-time data from IG
   - Analyzes all 5 priority pairs sequentially
   - Generates AI trading signals
   - Saves everything to database
   - Updates dashboard display

3. **If auto-trading enabled**:
   - Executes trades immediately when BUY/SELL signals appear
   - Opens positions on your IG demo account
   - Sets stop loss and take profit automatically
   - Monitors positions continuously

## 🛡️ Safety Features

✅ **Auto-trading disabled by default**
✅ **Rate limiting** - respects IG's 30 req/min limit
✅ **Sequential analysis** - no parallel API spam
✅ **Real-time monitoring** - see exactly what's happening
✅ **Database logging** - everything is recorded
✅ **Stop button** - kill switch to stop trading

## 📱 How to Use

### First Time Setup

1. Launch the dashboard:
   ```bash
   ./start_ig_dashboard.sh
   ```

2. Dashboard opens at http://localhost:8501

3. **Test with signals only first**:
   - Keep "Auto-Trading" checkbox **unchecked**
   - Click "▶️ Start" button
   - Watch signals appear in real-time
   - Verify everything works correctly

4. **When ready for real trading**:
   - Check the "Enable Auto-Trading" checkbox
   - Click "▶️ Start" button
   - System will execute REAL trades on IG

### Daily Usage

1. Launch dashboard
2. Click "▶️ Start"
3. Choose auto-trading mode (on/off)
4. Monitor in real-time
5. Click "⏹️ Stop" when done

### Dashboard Auto-Refreshes

The dashboard automatically refreshes every 5 seconds to show:
- Latest signals
- Updated positions
- Current account balance
- New API request stats

## 🔍 What You'll See

### On Start

```
🔄 Starting analysis cycle at 2025-10-27 19:45:00
📊 Rate Limits: Account 0/30, App 0/60
📊 Open positions: 0
📊 Analyzing 5 priority pairs...

🔍 Analyzing EUR_USD...
   ✅ BUY signal (confidence: 0.75)
   📊 Rate: 24/30 remaining

🔍 Analyzing GBP_USD...
   ⏸️  HOLD (confidence: 0.45)
   📊 Rate: 18/30 remaining
```

### With Auto-Trading Enabled

```
🔍 Analyzing EUR_USD...
   ✅ BUY signal (confidence: 0.75)
   ✅ REAL TRADE EXECUTED: EUR_USD BUY 0.01 lots
   Deal reference: ABC123
   📊 Rate: 18/30 remaining
```

## 📋 Configuration

Current settings (in `forex_config.py`):

```python
# Priority pairs (analyzed every cycle)
PRIORITY_PAIRS = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "EUR_GBP",
    "AUD_USD"
]

# Trading settings
RISK_PERCENT = 1.0  # Risk 1% per trade
MIN_RISK_REWARD = 1.5  # Minimum 1.5:1 RR
DEFAULT_STOP_LOSS_PIPS = 20
DEFAULT_TAKE_PROFIT_PIPS = 40

# Dashboard settings
DASHBOARD_REFRESH_SECONDS = 5  # Auto-refresh every 5s
```

## ⚠️ Important Notes

1. **Rate Limits**: System analyzes pairs sequentially to stay within IG's 30 requests/minute limit

2. **Auto-Trading**: When enabled, real trades execute immediately. No confirmation prompt!

3. **Demo Account**: All trades execute on your IG demo account (€20,000 balance)

4. **Database**: All signals, trades, and analysis saved to `trading_data.db`

5. **Stop Anytime**: Click stop button to immediately halt trading

## 🎨 Dashboard Colors

- 🟢 **Green**: BUY signals, positive P&L
- 🔴 **Red**: SELL signals, negative P&L
- 🟡 **Yellow**: HOLD signals, neutral

## 🔧 Troubleshooting

### "Worker Already Running"
- Click Stop, wait 2 seconds, then Start again

### "API Rate Limit Exceeded"
- Wait 60 seconds for limit to reset
- System will automatically wait when needed

### "No Signals Appearing"
- Check worker is running (green status)
- Wait for full 60-second cycle
- Market may be quiet (normal)

### Dashboard Not Updating
- Should auto-refresh every 5 seconds
- Manual refresh: Press F5 in browser

## 🎉 You're Ready!

Your complete IG real trading system is ready to use:

```bash
# Launch the dashboard
./start_ig_dashboard.sh
```

Then:
1. ✅ Click "Start" to begin scanning
2. ✅ Watch signals appear in real-time
3. ✅ Enable auto-trading when confident
4. ✅ Monitor your trades in the dashboard

**Happy Trading!** 🚀📈

---

**Account**: Z64WQT (IG Demo, €20,000 EUR)
**System**: Real-time AI multi-agent forex trading
**Status**: 🟢 READY FOR TRADING
