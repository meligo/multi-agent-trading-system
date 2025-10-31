# Rate Limit Fix - Implementation Roadmap

## Date: 2025-10-30
## Status: **READY TO IMPLEMENT**

---

## 🚨 Critical Problem

**Current State**: System hitting IG API rate limit (403 "exceeded-account-historical-data-allowance") after just a few analysis cycles.

**Root Cause**:
```
Every 5 minutes:
  For 24 pairs:
    - Fetch 100 historical candles from IG REST API
    - Call Tavily news API for same headlines
    - Recompute all 53 technical indicators from scratch
```

**Result**: 24 pairs × 12 cycles/hour × 2 timeframes = **576 API calls/hour** just for candles!

---

## 📊 Research Summary

### From GPT-5 Analysis:
- **Problem**: REST API polling is fundamentally wasteful
- **Solution**: WebSocket streaming + local cache + delta updates
- **Impact**: 14,400 API calls/day → **0 API calls/day**

### From Search Agent Research:
- **Documents Created**: 7 comprehensive guides (4,000+ lines)
- **Key Finding**: Industry standard is REST bootstrap (one-time) + WebSocket stream + Local cache
- **Performance**: 100-500ms latency → 10-50ms with websockets

---

## 🎯 Three-Tier Implementation Plan

### **TIER 1 - IMMEDIATE FIXES** (2-4 hours)
**Goal**: Stop rate limit errors TODAY

#### 1.1 Database Schema for Candle Caching
```sql
-- Store candles locally (never refetch same data)
CREATE TABLE candles (
    symbol_id INT NOT NULL,
    timeframe SMALLINT NOT NULL,  -- minutes (1, 5, 15, 60)
    ts TIMESTAMPTZ NOT NULL,      -- candle open time (UTC)
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION,
    finalized BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (symbol_id, timeframe, ts)
);

-- Track what we've already fetched
CREATE TABLE md_state (
    symbol_id INT NOT NULL,
    timeframe SMALLINT NOT NULL,
    last_finalized_ts TIMESTAMPTZ,  -- last closed candle we have
    last_fetch_ts TIMESTAMPTZ,       -- when we last checked
    PRIMARY KEY (symbol_id, timeframe)
);
```

#### 1.2 Delta Update Logic
```python
def get_candles_smart(pair, timeframe, count=100):
    """
    Smart candle fetcher:
    - First check: Do we have these candles in DB?
    - If yes: Return from DB (NO API CALL)
    - If partial: Fetch only NEW candles since last_finalized_ts
    - If empty: Bootstrap fetch (one-time only)
    """
    # Check DB first
    db_candles = db.get_candles(pair, timeframe, count)

    if len(db_candles) >= count:
        # We have enough cached data
        print(f"✅ Using cached candles for {pair} (0 API calls)")
        return db_candles

    # Need more data - fetch delta only
    last_ts = db.get_last_finalized_ts(pair, timeframe)
    if last_ts:
        # Delta update: fetch only NEW candles
        new_candles = api.get_candles(pair, timeframe, start=last_ts)
        db.upsert_candles(new_candles)
        print(f"✅ Fetched {len(new_candles)} NEW candles (delta update)")
    else:
        # Bootstrap: first-time fetch
        all_candles = api.get_candles(pair, timeframe, count)
        db.upsert_candles(all_candles)
        print(f"✅ Bootstrapped {len(all_candles)} candles (one-time)")

    return db.get_candles(pair, timeframe, count)
```

#### 1.3 Tavily News Caching
```python
# Current problem: Fetching same news every 5 minutes
# Solution: Cache with TTL

import hashlib
from datetime import datetime, timedelta

class NewsCache:
    def __init__(self, ttl_hours=2):
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_file = "news_cache.json"

    def get_news(self, pair, query):
        # Check cache first
        cache_key = hashlib.sha256(f"{pair}:{query}".encode()).hexdigest()
        cached = self.load_from_cache(cache_key)

        if cached and datetime.now() - cached['fetched_at'] < self.ttl:
            print(f"✅ Using cached news for {pair} (age: {cached['age']})")
            return cached['articles']

        # Cache miss or expired - fetch new
        articles = tavily.search(query)
        self.save_to_cache(cache_key, articles)
        print(f"📰 Fetched {len(articles)} NEW articles from Tavily")
        return articles
```

**Expected Impact**:
- API calls for candles: **576/hour → ~24/hour** (98% reduction)
- Tavily calls: **12/hour → 0.5/hour** (96% reduction)
- System will work within IG rate limits immediately

---

### **TIER 2 - INCREMENTAL UPDATES** (4-8 hours)
**Goal**: Only analyze NEW candles (not recompute everything)

#### 2.1 Incremental Technical Indicators
```python
class RollingIndicators:
    """
    Maintain rolling window of last N candles + indicator state.
    Update incrementally instead of recomputing.
    """
    def __init__(self, window=200):
        self.candles = []  # Rolling buffer
        self.ema_state = {}  # EMA values
        self.rsi_state = {}  # RSI values
        self.macd_state = {}  # MACD values

    def update(self, new_candle):
        """
        Add one new candle and update all indicators incrementally.
        """
        self.candles.append(new_candle)
        if len(self.candles) > self.window:
            self.candles.pop(0)

        # Update EMA incrementally (no full recompute)
        self.ema_state = self.update_ema(new_candle, self.ema_state)
        self.rsi_state = self.update_rsi(new_candle, self.rsi_state)
        self.macd_state = self.update_macd(new_candle, self.macd_state)

        return self.get_current_indicators()
```

**Expected Impact**:
- Indicator computation: **O(n×53) → O(53)** (100x faster)
- CPU usage: **High → Low**
- Analysis time: **2-5 seconds → 50-200ms**

---

### **TIER 3 - WEBSOCKET STREAMING** (8-16 hours)
**Goal**: Real-time updates with ZERO REST API calls

#### 3.1 WebSocket Agent Architecture
```python
class MarketDataWSAgent:
    """
    Maintains persistent websocket connection for real-time data.
    No more REST API polling!
    """
    async def run(self):
        while True:
            try:
                async with self.connect_ws() as ws:
                    await self.subscribe(self.pairs)

                    async for tick in ws:
                        # Update current building candle
                        candle_updates = self.candle_builder.update(tick)

                        if candle_updates.finalized:
                            # Candle closed - persist and notify
                            await db.upsert_candle(candle_updates)
                            await bus.publish("candle_close", candle_updates)
                            print(f"📊 New {pair} candle closed")

            except Exception as e:
                # On disconnect: backfill gaps via REST
                await self.backfill_gaps()
                await self.exponential_backoff()
```

#### 3.2 Event-Driven Analysis
```python
# OLD: Poll every 5 minutes (wasteful)
while True:
    analyze_all_pairs()
    time.sleep(300)

# NEW: Event-driven (efficient)
async def on_candle_close(event):
    """Triggered when a candle closes."""
    pair = event['pair']
    timeframe = event['timeframe']

    # Only analyze THIS pair (not all 24)
    indicators = incremental_update(pair, timeframe)

    if signal_changed(indicators):
        # Only run agents if signal changed
        decision = await decision_engine.analyze(pair, indicators)
```

**Expected Impact**:
- REST API calls: **24/hour → 0/hour** (100% elimination)
- Latency: **2-5 seconds → 50-200ms** (40-100x faster)
- Rate limit errors: **Frequent → Never**

---

## 📋 Implementation Checklist

### Phase 1: Immediate Fixes (TODAY)
- [ ] Create SQLite database for candle storage
- [ ] Implement `get_candles_smart()` with delta updates
- [ ] Add `NewsCache` class with 2-hour TTL
- [ ] Update `ForexDataFetcher` to check DB before API
- [ ] Test: Verify no 403 errors after changes
- [ ] Monitor: API call count should drop 95%+

### Phase 2: Incremental Updates (TOMORROW)
- [ ] Implement `RollingIndicators` class
- [ ] Update analysis worker to use incremental updates
- [ ] Add candle_close event system (Redis or in-memory)
- [ ] Test: Verify indicator values match full recompute
- [ ] Monitor: CPU usage and analysis time

### Phase 3: WebSocket Streaming (WEEK 2)
- [ ] Implement `MarketDataWSAgent` for IG Lightstreamer
- [ ] Add backfill logic for gap detection
- [ ] Convert to event-driven architecture
- [ ] Test: Verify data consistency with REST
- [ ] Deploy: Gradual rollout (1 pair → all pairs)

---

## 🔢 Expected Metrics

| Metric | Before | After Tier 1 | After Tier 2 | After Tier 3 |
|--------|--------|--------------|--------------|--------------|
| **API Calls/Hour** | 576 | 24 | 12 | 0 |
| **Analysis Time** | 3-5s | 2-3s | 100-300ms | 50-200ms |
| **CPU Usage** | High | Medium | Low | Very Low |
| **Rate Limit Errors** | Frequent | Rare | Never | Never |
| **Latency** | 500ms | 300ms | 200ms | 50ms |

---

## 🚀 Quick Start (Tier 1 Implementation)

### Step 1: Create Database
```bash
cd /Users/meligo/multi-agent-trading-system
python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('forex_cache.db')
c = conn.cursor()

# Candles table
c.execute('''
CREATE TABLE IF NOT EXISTS candles (
    pair TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL,
    finalized BOOLEAN NOT NULL DEFAULT 1,
    PRIMARY KEY (pair, timeframe, timestamp)
)
''')

# State tracking
c.execute('''
CREATE TABLE IF NOT EXISTS md_state (
    pair TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    last_finalized_ts INTEGER,
    last_fetch_ts INTEGER,
    PRIMARY KEY (pair, timeframe)
)
''')

conn.commit()
conn.close()
print("✅ Database created: forex_cache.db")
EOF
```

### Step 2: Create Caching Layer
```bash
# Will create: candle_cache.py
# Will create: news_cache.py
# Will update: forex_data.py (to use caching)
```

### Step 3: Test
```bash
# Run one analysis cycle
# Expected: First run fetches from API, subsequent runs use cache
python ig_concurrent_worker.py
```

---

## 📚 Reference Documents

All research documents available in project root:
- `00_START_HERE.md` - Quick navigation guide
- `FOREX_WEBSOCKET_RESEARCH.md` - Main technical reference (1,168 lines)
- `WEBSOCKET_IMPLEMENTATION_PATTERNS.md` - Code patterns (1,010 lines)
- `PROVIDER_SPECIFIC_CONFIGS.md` - IG/Finnhub integration guides

---

## ✅ Success Criteria

### Tier 1 Success:
- ✅ No 403 rate limit errors for 24 hours
- ✅ API call count < 50/hour (down from 576/hour)
- ✅ System runs continuously without errors

### Tier 2 Success:
- ✅ Analysis time < 500ms per pair
- ✅ CPU usage < 30% sustained
- ✅ Indicator values match reference implementation

### Tier 3 Success:
- ✅ ZERO REST API calls (except bootstrap and gaps)
- ✅ Latency < 100ms for new candles
- ✅ 99.9% uptime with auto-reconnect

---

## 🎯 Next Steps

**IMMEDIATE ACTION** (next 2-4 hours):
1. Create `forex_cache.db` database
2. Implement `candle_cache.py` with delta updates
3. Implement `news_cache.py` with TTL
4. Update `forex_data.py` to use caching
5. Test and verify rate limits resolved

**Status**: READY TO IMPLEMENT
**Priority**: CRITICAL (system currently unusable due to rate limits)
**Timeline**: Tier 1 can be completed TODAY

---

*This roadmap solves the rate limit problem at its root cause by eliminating redundant API calls, implementing smart caching, and eventually moving to real-time websocket streaming.*
