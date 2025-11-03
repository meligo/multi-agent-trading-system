# 🚀 Quick Start - Enhanced Scalping Dashboard

## One-Command Launch

```bash
streamlit run scalping_dashboard.py
```

That's it! Everything starts automatically in the background.

---

## What Starts Automatically

When you run the dashboard, it automatically starts:

1. **✅ DataHub Server** (Port 50000)
2. **✅ IG WebSocket Collector** (tick data + tick volume candles)
3. **✅ DataBento Streaming Client** (REAL VOLUME candles from CME futures)
4. **✅ PostgreSQL + TimescaleDB** (historical data)
5. **✅ InsightSentry MEGA** (news/calendar/sentiment)
6. **✅ News Gating Service** (risk protection)

---

## Monitoring

Check DataBento status in the **sidebar**:
- ✅ DataBento: STREAMING (real volume)
- Shows candle count generated
- Displays CME futures symbols (6E, 6B, 6J)

---

## Verification

Test multi-source integration:
```bash
python test_databento_candles.py
```

Expected output after 1-2 minutes:
```
EUR_USD:
  DataBento (real volume): 50 candles ✅
  IG (tick volume): 100 candles
  Latest DataBento Candle:
     Volume: 1250 (REAL)
```

---

**Status:** ✅ Ready for Testing
**Date:** 2025-11-03
