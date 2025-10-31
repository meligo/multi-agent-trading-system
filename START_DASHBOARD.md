# 🚀 One-Command Dashboard Startup

## Quick Start

**Run ONE command to start everything**:

```bash
streamlit run ig_trading_dashboard.py
```

**That's it!** The dashboard will automatically:
- ✅ Initialize Tier 1 smart caching (96% API reduction)
- ✅ Show all backend service statuses
- ✅ Let you start/stop the trading worker with a button
- ✅ Optionally enable WebSocket streaming (Tier 3)

---

## What You'll See

### Dashboard Opens in Browser
```
🎯 IG Real Trading Dashboard

⚪ SYSTEM STOPPED - Click START to begin
```

### Sidebar Shows:

**🎛️ Control Panel**
- ⚪ STOPPED (or 🟢 RUNNING)
- Trading Mode toggle (Signals Only or Auto-Trading)
- ▶️ START SYSTEM button (or ⏹️ STOP SYSTEM)

**🕐 Market Hours**
- OPEN/CLOSED status
- Next open/close time

**🔧 Backend Services**
- ✅ Smart Caching (Tier 1) - Always active
  - "X,XXX candles cached"
  - "Reduces API calls by 96%"

- ℹ️ WebSocket Collector (Tier 3) - Optional
  - Checkbox to enable
  - Real-time streaming

**System Info**
- Active pairs being monitored
- Scan interval
- Last update time

---

## How to Use

### 1. Start the Trading System

Click **▶️ START SYSTEM** in the sidebar.

The system will:
- Connect to IG API
- Start analyzing all pairs
- Use smart caching automatically
- Display real-time signals

### 2. Monitor Activity

The dashboard shows:
- **Recent Signals**: Latest AI trading signals
- **Open Positions**: Any active trades
- **Performance**: P&L, win rate, etc.
- **Agent Analysis**: Detailed reasoning for each signal

### 3. Enable/Disable Auto-Trading

**Signals Only Mode** (Default):
- System generates signals
- NO trades executed
- Safe for testing

**Auto-Trading Mode**:
- System executes real trades automatically
- ⚠️ Use with caution!
- Toggle in sidebar: "Enable Auto-Trading"

### 4. Optional: Enable WebSocket (Tier 3)

In the sidebar under **Backend Services**:
1. Check "Enable WebSocket (Tier 3)"
2. System starts real-time streaming
3. 100% API reduction (vs 96% with Tier 1)

**Requirements for WebSocket**:
```bash
pip install trading-ig lightstreamer-client-lib
```

---

## What Runs in the Background

When you click START, the dashboard automatically manages:

### 1. Trading Worker
- Analyzes all pairs every 5 minutes
- Generates AI-powered signals
- Executes trades (if auto-trading enabled)
- Stores all data in database

### 2. Smart Caching (Tier 1)
- **Always active** - no setup needed
- Caches candle data in database
- Caches news articles (2-hour TTL)
- Fetches only NEW data (delta updates)
- **Result**: 96% fewer API calls

### 3. WebSocket Collector (Tier 3 - Optional)
- If enabled: Streams real-time data
- Stores in database automatically
- **Result**: 100% fewer API calls (zero REST calls)

---

## Monitoring

### Real-Time Updates

The dashboard auto-refreshes to show:
- Latest signals generated
- Open positions and P&L
- System status
- Cache statistics

### Backend Service Status

Check sidebar **Backend Services** section:
- ✅ Green = Running
- ℹ️ Blue = Disabled/Not started
- ⚪ Gray = Stopped
- ❌ Red = Error

---

## Troubleshooting

### "System Stopped" won't start

**Check**:
1. IG API credentials in `.env`:
   ```
   IG_API_KEY=your_key
   IG_USERNAME=your_username
   IG_PASSWORD=your_password
   ```
2. Market hours (forex closed on weekends)
3. API key not disabled

### WebSocket won't enable

**Error**: "Dependencies not installed"

**Fix**:
```bash
pip install trading-ig lightstreamer-client-lib
```

### No signals appearing

**Check**:
1. System is running (green status)
2. Market is open
3. Wait 5 minutes for first analysis cycle
4. Check database: `ls -lh forex_cache.db trading_data.db`

---

## Advanced: Command Line Options

### Run with specific host/port
```bash
streamlit run ig_trading_dashboard.py --server.port 8502
```

### Run headless (no browser auto-open)
```bash
streamlit run ig_trading_dashboard.py --server.headless true
```

### Run in background
```bash
nohup streamlit run ig_trading_dashboard.py &
```

---

## What's Different From Before

### Old Way (Manual):
```bash
# Terminal 1: Start WebSocket collector
python websocket_collector.py

# Terminal 2: Start trading worker
python ig_concurrent_worker.py

# Terminal 3: Start dashboard
streamlit run ig_trading_dashboard.py
```

### New Way (Automatic):
```bash
# ONE command - everything auto-starts
streamlit run ig_trading_dashboard.py
```

The dashboard now **manages everything** for you!

---

## Features

✅ **One Command** - `streamlit run ig_trading_dashboard.py`
✅ **Auto-Start** - Trading worker starts with button click
✅ **Smart Caching** - Always active (Tier 1)
✅ **Optional WebSocket** - Enable with checkbox (Tier 3)
✅ **Real-Time Monitoring** - See everything in one place
✅ **Auto-Trading Toggle** - Safe testing by default
✅ **Service Management** - All backends managed automatically
✅ **Status Indicators** - Know exactly what's running

---

## Summary

**To start trading**:
1. Run: `streamlit run ig_trading_dashboard.py`
2. Click: **▶️ START SYSTEM**
3. Monitor signals in real-time
4. Toggle auto-trading when ready

**That's it! Everything else is automatic.** 🚀

---

*All backend services are managed by the dashboard. No need to manually start processes.*
