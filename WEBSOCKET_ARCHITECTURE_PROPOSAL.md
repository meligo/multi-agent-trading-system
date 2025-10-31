# WebSocket + Database Architecture Proposal

## Current Problem Analysis

### Indicator Requirements

**Longest lookback periods in `forex_data.py`:**

| Indicator | Candles Needed | Notes |
|-----------|---------------|-------|
| **MA-200** | **200** | Limiting factor |
| Ichimoku Senkou B | 52 | Plus 26-period shift = 78 total |
| MA-50 | 50 | Important trend indicator |
| OBV Z-Score | 50 | Volume analysis |
| Ultimate Oscillator | 28 | Multi-timeframe momentum |
| VPVR (90 bars) | 90 | Volume profile |
| MA-21 | 21 | Medium-term trend |
| Aroon | 25 | Trend detection |
| ADX | 14 | Trend strength |

**Minimum candles required:** 200 (for MA-200)

**Practical minimum without MA-200:** 60-80 candles (covers most indicators)

---

## Quota Calculation (28 Pairs)

### Current System (100 candles):
```
Initial backfill: 28 pairs × 100 candles × 2 TF = 5,600 points
Remaining quota: 10,000 - 5,600 = 4,400 points
Delta updates: 28 pairs × 2 candles × 2 TF = 112 points/cycle
Cycles possible: 4,400 / 112 = 39 cycles
Runtime: ~3.25 hours before exhaustion
```

### Reduced to 60 candles:
```
Initial backfill: 28 pairs × 60 candles × 2 TF = 3,360 points
Remaining quota: 10,000 - 3,360 = 6,640 points
Delta updates: 28 pairs × 2 candles × 2 TF = 112 points/cycle
Cycles possible: 6,640 / 112 = 59 cycles
Runtime: ~5 hours before exhaustion
```

### Reduced to 200 candles (full indicators):
```
Initial backfill: 28 pairs × 200 candles × 2 TF = 11,200 points ❌ EXCEEDS QUOTA!
```

---

## Your WebSocket Proposal: EXCELLENT! ✅

You're absolutely right - **WebSocket streaming is the proper architecture for forex trading systems.**

### Why WebSockets Are Better

#### 1. **No Quota Limits on Streaming**
- IG Lightstreamer API doesn't count against historical data quota
- Unlimited real-time updates
- Can run 24/5 without hitting limits

#### 2. **Real-Time Data (Sub-Second Latency)**
- Get every tick as it happens
- No polling delay (current: 5 min intervals)
- Critical for fast-moving forex markets

#### 3. **Lower API Load**
- One persistent connection vs repeated REST calls
- More efficient for IG's infrastructure
- Industry standard for trading platforms

#### 4. **Better for Multiple Pairs**
- Subscribe to 28 pairs simultaneously
- Single WebSocket handles all pairs
- Multiplexed data stream

---

## Proposed Architecture

### Current (REST Polling + Cache):
```
┌──────────────┐
│ Trading Bot  │
│ (5 min loop) │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│  REST API    │────▶│  IG Markets  │
│  (polling)   │     │  (10k quota) │
└──────┬───────┘     └──────────────┘
       │
       ▼
┌──────────────┐
│ SQLite Cache │
└──────────────┘
```

**Problems:**
- 10k weekly quota limitation
- 5-minute polling delay
- Not real-time
- Inefficient API usage

---

### Proposed (WebSocket Streaming + Database):
```
┌──────────────────────────────────────────┐
│          REAL-TIME DATA LAYER            │
│                                          │
│  ┌────────────────┐                     │
│  │  IG WebSocket  │◀─────────────────┐  │
│  │  (Lightstreamer)│                   │  │
│  └────────┬───────┘                   │  │
│           │                            │  │
│           │ Tick/Candle Stream         │  │
│           ▼                            │  │
│  ┌────────────────┐                   │  │
│  │ Stream Processor│                  │  │
│  │  - Aggregates   │                  │  │
│  │  - Validates    │                  │  │
│  │  - Stores       │                  │  │
│  └────────┬───────┘                   │  │
│           │                            │  │
│           ▼                            │  │
│  ┌────────────────┐   ┌──────────┐   │  │
│  │  TimescaleDB/  │   │  Redis   │   │  │
│  │  PostgreSQL    │   │ (cache)  │   │  │
│  │  (permanent)   │   │ (current)│   │  │
│  └────────────────┘   └──────────┘   │  │
│                                       │  │
└───────────────────────────────────────┘  │
                                           │
┌──────────────────────────────────────────┘
│
│
│          TRADING LAYER
│
▼
┌────────────────┐
│  Trading Bot   │
│  - Queries DB  │
│  - Calculates  │
│  - Executes    │
└────────────────┘
```

---

## Implementation Plan

### Phase 1: WebSocket Data Collector (NEW)

**Create: `ig_websocket_stream.py`**

```python
from trading_ig import IGService
from trading_ig.lightstreamer import Subscription
import sqlite3 / psycopg2

class IGWebSocketCollector:
    """
    Connects to IG Lightstreamer WebSocket.
    Subscribes to 28 currency pairs.
    Stores every completed candle in database.
    """

    def __init__(self, pairs: List[str], timeframes: List[str]):
        self.ig_service = IGService(...)
        self.pairs = pairs
        self.timeframes = timeframes

    def connect(self):
        """Establish WebSocket connection."""
        # Create Lightstreamer connection
        self.ls_client = Subscription(
            mode="MERGE",
            items=[f"CHART:{pair}:{tf}" for pair in self.pairs for tf in self.timeframes],
            fields=["BID", "OFFER", "HIGH", "LOW", "OPEN", "CLOSE", "VOLUME"]
        )
        self.ls_client.addlistener(self.on_price_update)

    def on_price_update(self, item_update):
        """Called for every price tick."""
        # Extract data
        pair = item_update.get_name()
        bid = item_update.get_value("BID")
        offer = item_update.get_value("OFFER")

        # Aggregate into candles (5m, 15m)
        self.aggregate_candle(pair, bid, offer)

    def aggregate_candle(self, pair, bid, offer):
        """Aggregate ticks into candles."""
        # When candle completes, store in DB
        if candle_complete:
            self.store_candle(pair, timeframe, ohlcv)

    def store_candle(self, pair, timeframe, ohlcv):
        """Store completed candle in database."""
        conn = sqlite3.connect("forex_data.db")
        cursor.execute("""
            INSERT INTO candles (pair, timeframe, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pair, timeframe, ...))
        conn.commit()
```

**Benefits:**
- Runs 24/5 continuously
- No quota usage
- Real-time data collection
- Builds historical database organically

---

### Phase 2: Database Schema

**Use PostgreSQL/TimescaleDB (better than SQLite for time-series):**

```sql
-- Main candles table (optimized for time-series)
CREATE TABLE candles (
    id SERIAL PRIMARY KEY,
    pair VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(18, 8) NOT NULL,
    high DECIMAL(18, 8) NOT NULL,
    low DECIMAL(18, 8) NOT NULL,
    close DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(18, 4) NOT NULL,
    source VARCHAR(10) DEFAULT 'websocket',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pair, timeframe, timestamp)
);

-- Create hypertable (TimescaleDB) for automatic partitioning
SELECT create_hypertable('candles', 'timestamp');

-- Indexes for fast queries
CREATE INDEX idx_pair_timeframe_time ON candles (pair, timeframe, timestamp DESC);
CREATE INDEX idx_timestamp ON candles (timestamp DESC);

-- Continuous aggregate for 1-hour candles (computed from 5m)
CREATE MATERIALIZED VIEW candles_1h
WITH (timescaledb.continuous) AS
SELECT
    pair,
    time_bucket('1 hour', timestamp) AS timestamp,
    first(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, timestamp) AS close,
    sum(volume) AS volume
FROM candles
WHERE timeframe = '5'
GROUP BY pair, time_bucket('1 hour', timestamp);
```

**Why PostgreSQL/TimescaleDB over SQLite:**
- Better for concurrent reads/writes
- Automatic partitioning by time
- Continuous aggregates (compute 1h from 5m automatically)
- Better performance at scale
- Native time-series functions

---

### Phase 3: Modified Trading Bot

**Update: `forex_data.py`**

```python
class ForexDataFetcher:
    """Fetches data from local database (populated by WebSocket)."""

    def __init__(self, db_connection):
        self.db = db_connection  # PostgreSQL connection

    def get_candles(self, pair: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        """
        Query database for historical candles.
        No API calls - just database query!
        """
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE pair = %s AND timeframe = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """

        df = pd.read_sql_query(query, self.db, params=(pair, timeframe, count))
        df = df.sort_values('timestamp').reset_index(drop=True)

        return df
```

**Benefits:**
- No API calls during trading
- Can request 200+ candles without quota worry
- Sub-millisecond database queries
- Always have complete historical data

---

## Implementation Timeline

### Week 1: WebSocket Collector
- [ ] Set up IG Lightstreamer connection
- [ ] Subscribe to 28 pairs × 2 timeframes
- [ ] Implement candle aggregation logic
- [ ] Test data collection for 24 hours

### Week 2: Database Migration
- [ ] Set up PostgreSQL/TimescaleDB
- [ ] Create schema and indexes
- [ ] Migrate existing cache data
- [ ] Test query performance

### Week 3: Trading Bot Integration
- [ ] Update `forex_data.py` to use database
- [ ] Remove REST API polling (keep as fallback)
- [ ] Test with live data
- [ ] Monitor for 48 hours

### Week 4: Production
- [ ] Deploy WebSocket collector as daemon
- [ ] Set up monitoring and alerts
- [ ] Configure auto-restart on failure
- [ ] Document new architecture

---

## Cost & Resource Analysis

### Current System:
- **IG API quota:** 10,000 points/week (hard limit)
- **Runtime:** ~3-5 hours before exhaustion
- **Data freshness:** 5-minute polling delay
- **Storage:** SQLite cache (limited)

### New System:
- **IG WebSocket:** Unlimited (no quota)
- **Runtime:** Unlimited (24/5 forex hours)
- **Data freshness:** Real-time (<1 second)
- **Storage:** PostgreSQL (scalable)
- **Additional cost:** $0 (can run on same server)

---

## Hybrid Approach (Interim Solution)

While implementing full WebSocket:

### 1. Reduce REST Fetches to Minimum
```python
# Instead of 100 candles, fetch only what we need
INITIAL_FETCH = 60  # Covers MA-50, Ichimoku, OBV

# 28 pairs × 60 candles × 2 TF = 3,360 points (vs 5,600)
# Saves 2,240 quota points!
```

### 2. Drop MA-200 (Temporarily)
```python
# MA-200 requires 200 candles (7,000 quota points for initial fetch!)
# Most day traders don't use MA-200 anyway
# Focus on MA-9, MA-21, MA-50
```

### 3. Use 15m as Primary Timeframe
```python
# 15m candles instead of 5m
# 28 pairs × 60 candles × 1 TF = 1,680 points
# Much more efficient, still captures trends
```

---

## Recommendation: WebSocket First

**I strongly recommend implementing the WebSocket architecture** because:

1. **Solves quota problem permanently** - No more 10k weekly limit
2. **Real-time data** - Critical for forex trading
3. **Industry standard** - How professional platforms work
4. **Scalable** - Can add more pairs without quota worry
5. **Cost-effective** - No additional API costs

**Interim fixes (60 candles, drop MA-200) are band-aids** - they help but don't solve the root issue.

---

## Technical Stack Recommendation

### For WebSocket Collector:
- **Language:** Python 3.11+
- **Library:** `trading-ig` (official IG Python library)
- **Async:** `asyncio` for concurrent streams
- **Supervisor:** `systemd` or `supervisord` (auto-restart)

### For Database:
- **Primary:** PostgreSQL 15+ with TimescaleDB extension
- **Alternative:** SQLite (if must stay simple)
- **Caching:** Redis (for current prices, <1 sec TTL)

### For Deployment:
- **Container:** Docker (easy deployment)
- **Orchestration:** Docker Compose (WebSocket + DB + Bot)
- **Monitoring:** Prometheus + Grafana
- **Logging:** Structured JSON logs

---

## Migration Path

### Option A: Full Migration (Recommended)
```
Week 1-2: Build WebSocket collector
Week 3: Accumulate 2 weeks of historical data
Week 4: Switch trading bot to database
Week 5: Decommission REST polling
```

### Option B: Hybrid (Lower Risk)
```
Week 1: Deploy WebSocket collector (run in parallel)
Week 2-4: Accumulate data while REST system runs
Week 5: Gradually migrate pairs to WebSocket data
Week 6: Full cutover when confident
```

---

## Questions to Answer

Before proceeding, clarify:

1. **Database preference:**
   - PostgreSQL/TimescaleDB (recommended for time-series)
   - SQLite (simpler, but limited concurrency)
   - Other (MySQL, InfluxDB, etc.)?

2. **Deployment environment:**
   - Local machine (Mac/Windows/Linux)?
   - Cloud (AWS, Azure, GCP)?
   - VPS (DigitalOcean, Linode)?

3. **Timeline preference:**
   - Full migration (1 month, complete solution)
   - Interim fix (reduce to 60 candles, 1 day, band-aid)
   - Hybrid approach (2 weeks, low risk)

4. **Keep MA-200 indicator?**
   - Yes → Need 200 candles (quota intensive)
   - No → Can use 60 candles (much more efficient)

---

## Summary

**Your instinct is 100% correct:**
- ✅ WebSocket streaming is the proper solution
- ✅ Database storage (not just "cache") is correct terminology
- ✅ This is how professional forex platforms work
- ✅ Solves quota problem permanently

**Next steps:**
1. Choose database (PostgreSQL recommended)
2. Implement WebSocket collector
3. Let it accumulate data for 1-2 weeks
4. Migrate trading bot to query database
5. Remove REST API dependency

**This is the correct architectural direction for a production forex trading system.**
