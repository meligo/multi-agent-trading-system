# Quick Start - Enhanced Scalping Dashboard

**Version**: 3.0
**Status**: ✅ Fully Integrated - Single Entry Point

---

## What This Does

The enhanced scalping dashboard automatically:
- ✅ Connects to remote PostgreSQL + TimescaleDB database
- ✅ Loads database schema (if missing)
- ✅ Starts InsightSentry MEGA client (economic calendar + news)
- ✅ Starts News Gating Service (auto-close positions before events)
- ✅ Initializes DataBento client (CME futures order flow)
- ✅ Displays service status in real-time
- ✅ Runs the scalping engine with all data providers

**NO MANUAL FILE RUNNING REQUIRED!**

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements_scalping_enhanced.txt
```

### 2. Verify Configuration

The `.env.scalper` file already has:
- ✅ Remote PostgreSQL: `postgresql://postgres:aEo4Ac3X5GHFbLoAsC83@pga.bittics.com:5000/forexscalper_dev`
- ✅ InsightSentry MEGA API key
- ✅ DataBento API key
- ✅ IG Markets API key (scalping)
- ✅ OpenAI API key
- ✅ All other credentials

---

## Running the Dashboard

### Single Command

```bash
streamlit run scalping_dashboard.py
```

That's it! The dashboard will:

1. **Auto-initialize (first 5-10 seconds)**:
   - Connect to remote database
   - Load schema if needed
   - Start InsightSentry client
   - Start News Gating Service (background)
   - Initialize DataBento client

2. **Show service status** in sidebar:
   ```
   🔧 Enhanced Services
   ✅ database: Connected
   ✅ insightsentry: Ready
   ✅ news_gating: Running
   ✅ databento: Ready (market hours)
   ```

3. **Display active news gates** (if any):
   ```
   ⚠️ 2 Active News Gates
   - EUR_USD: NFP (US)
   - GBP_USD: BoE Rate Decision
   ```

4. **Wait for you to click**: "🚀 START SCALPING ENGINE"

---

## What You'll See

### Sidebar

**Engine Controls**
- Market status (Open/Closed)
- Service status indicators
- Active news gates
- START/STOP buttons
- Configuration display
- WebSocket status

### Main Dashboard

**Performance Metrics**
- Total trades
- Win rate
- Profit factor
- Today's P&L
- Open positions
- Average duration

**Trading Signals**
- Real-time signals for each pair
- Agent reasoning
- Indicator values
- Confidence scores

**Spread Monitor**
- Current spreads
- Color-coded (green/yellow/red)
- Trade acceptance status

**Active Trades**
- Position details
- Current P&L
- 20-minute countdown timer

**Charts**
- 1-minute candles
- EMA ribbon (3, 6, 12)
- VWAP
- Donchian Channel
- RSI(7)
- ADX(7)
- SuperTrend

**Agent Debates**
- Recent analysis
- Momentum agent view
- Technical agent view
- Validator decision

---

## Service Details

### PostgreSQL + TimescaleDB

**Connection**:
- Host: `pga.bittics.com:5000`
- Database: `forexscalper_dev`
- User: `postgres`
- TimescaleDB: Enabled ✅

**Tables Auto-Created**:
- `instruments` - Symbol mappings
- `ig_spot_ticks` - IG Markets spot data
- `cme_mbp10_events` - DataBento L2 updates
- `cme_trades` - Trade executions
- `cme_mbp10_book` - Order book snapshots
- `iss_econ_calendar` - Economic events
- `iss_news_events` - Breaking news
- `gating_state` - Trading restrictions
- `microstructure_features` - OFI, VPIN, microprice
- `orders`, `fills`, `positions` - Execution history

### InsightSentry MEGA

**Plan**: $50/month
- REST API: 600,000 requests/month (60/min)
- WebSocket: 10 connections/day (saved for Phase 3)
- Concurrent symbols: 12 per connection

**What It Does**:
- Fetches economic calendar every 60 seconds
- Identifies high-impact events (NFP, CPI, FOMC, etc.)
- Monitors for breaking news

### News Gating Service

**What It Does**:
- Monitors calendar for upcoming high-impact events
- Creates "gating windows" 15 min before events
- **Automatically closes positions** 10 min before events
- Prevents new entries during gating windows
- Logs all gating activity to database

**Example**:
```
Event: NFP (US) at 13:30 GMT
Gate Start: 13:15 GMT (15 min before)
Close Positions: 13:20 GMT (10 min before)
Gate End: 13:35 GMT (5 min after)

Affected Pairs: EUR_USD, GBP_USD, USD_JPY
```

### DataBento

**What It Does**:
- Streams CME Globex MBP-10 (Market By Price - top 10 levels)
- Provides real-time L2 order book
- Tracks trade executions with aggressor side
- Calculates microstructure features (OFI, microprice, queue imbalance)

**Symbols**:
- `6E` - EUR/USD futures
- `6B` - GBP/USD futures
- `6J` - USD/JPY futures

**Market Hours**: Sunday 5pm - Friday 4pm CT

---

## Troubleshooting

### Issue: "Database connection failed"

**Check**:
1. Verify DATABASE_URL in `.env.scalper`
2. Test connection:
   ```bash
   psql postgresql://postgres:aEo4Ac3X5GHFbLoAsC83@pga.bittics.com:5000/forexscalper_dev -c "SELECT NOW();"
   ```

### Issue: "InsightSentry API error"

**Possible Causes**:
- Rate limit exceeded (60/min)
- Invalid API key
- RapidAPI service down

**Check**:
```bash
curl --request GET \
  --url 'https://insightsentry.p.rapidapi.com/v2/calendar/economic?countries=US&minImpact=high' \
  --header 'x-rapidapi-host: insightsentry.p.rapidapi.com' \
  --header 'x-rapidapi-key: 7803c4923fmsh8bb847b52f885c9p1ae67bjsn5eb22dbbd7bd'
```

### Issue: "News Gating Service not starting"

**Check**:
1. Database connection working?
2. InsightSentry client initialized?
3. Look for errors in terminal output

### Issue: "DataBento connection failed"

**Possible Causes**:
- Outside market hours (Sun 5pm - Fri 4pm CT)
- Invalid API key
- No active subscription

**Note**: DataBento only streams during CME Globex hours. Dashboard will show "Ready (market hours)" but won't connect outside trading hours.

---

## Performance Monitoring

### Database Size

Check storage usage:
```bash
# Connect to database
psql postgresql://postgres:aEo4Ac3X5GHFbLoAsC83@pga.bittics.com:5000/forexscalper_dev

# Check table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size('public.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size('public.'||tablename) DESC;
```

Expected after 24h:
- `cme_mbp10_events`: ~500MB (compressed)
- `ig_spot_ticks`: ~100MB
- `cme_trades`: ~50MB
- `cme_mbp10_book`: ~200MB

### Service Logs

Dashboard logs to:
- Terminal output (real-time)
- `scalping_dashboard.log` file

Watch logs:
```bash
tail -f scalping_dashboard.log
```

---

## Next Steps

After dashboard is running:

1. **Verify Services**: Check sidebar status indicators (all green)
2. **Watch News Gates**: Monitor for active gating windows
3. **Start Engine**: Click "🚀 START SCALPING ENGINE"
4. **Monitor Performance**: Watch metrics in real-time
5. **Let It Run**: News gating will automatically close positions before events

---

## Support

- **Main Documentation**: `ENHANCED_SCALPING_SETUP.md`
- **Research Summary**: `RESEARCH_FINDINGS_SUMMARY.md`
- **Full Roadmap**: `SCALPING_SYSTEM_TRANSFORMATION_ROADMAP.md`
- **Database Schema**: `database_setup.sql`

---

**Status**: ✅ Ready to Run
**Command**: `streamlit run scalping_dashboard.py`
**Time to Start**: ~5-10 seconds (auto-init)
**User Action Required**: Just click "START SCALPING ENGINE"!
