# Comprehensive Research: Forex Data Streaming with WebSockets

## Executive Summary

WebSocket streaming is fundamentally superior to REST API polling for financial data due to eliminated rate limits, lower latency, persistent connections, and efficient delta updates. Professional trading systems use persistent connections with local caching strategies to maintain historical data while streaming only new candles, avoiding the limitations of repeated REST calls.

---

## 1. WebSocket vs REST API: Fundamental Differences

### Rate Limiting Comparison

**REST API Approach (Problematic)**
- Each request counts against rate limits
- Typical limits: 50-1200 requests per minute (varies by provider)
- Polling every minute for 1-minute candles = 1440 requests/day
- Multiple symbols quickly exhaust quota
- Binance example: Rate weight increased significantly in recent updates

**WebSocket Approach (Optimal)**
- Persistent connection with no per-message rate limits
- IG Trading API: 40 concurrent WebSocket connections max
- Updates pushed to client continuously
- No request-response overhead
- Scales to hundreds of symbols on single connection

### Latency Characteristics

| Metric | REST API | WebSocket |
|--------|----------|-----------|
| Round-trip time | 100-500ms | 1-50ms |
| Connection setup | Per request | Once at startup |
| Update frequency | Fixed interval | Event-driven |
| Overhead | HTTP headers, TLS per call | Single TLS connection |
| Scaling multiple symbols | Linear degradation | Constant efficiency |

**Key Insight from Industry Sources:**
> "WebSockets dramatically reduce latency compared to repeated REST calls, which is crucial when markets move at high speed. In crypto markets, even a few milliseconds difference can impact profitability." - BloFin API Documentation

---

## 2. Major Forex/Financial Data Providers

### IG Trading API (Lightstreamer-based)

**Documentation:** https://labs.ig.com/streaming-api-guide

**Architecture:**
- Uses Lightstreamer protocol (optimized for financial data)
- Downloads client library per programming language
- Real-time market prices, trade notifications, account status
- Python wrapper: `trading-ig` package

**Streaming Capabilities:**
```
L1:CS.D.USDJPY.CFD.IP: Time 20:35:43 - Bid 119.870 - Ask 119.885
L1:CS.D.GBPUSD.CFD.IP: Time 20:35:46 - Bid 1.51270 - Ask 1.51290
```

**Concurrency Limits:**
- Default: 40 concurrent WebSocket connections
- 2 streams per asset = maximum 20 assets simultaneously

**Rate Limiting:** Connection-based, not message-based

---

### Finnhub WebSocket API

**Documentation:** https://finnhub.io/docs/api/websocket-trades

**Features:**
- Real-time streaming for US stocks, forex, crypto
- Available to paying users (free tier may have limitations)
- Supports multiple asset classes in single connection

**Real-World Implementation Example:**
Project: Finnhub Real-Time Pipeline with Spark
- Architecture: Finnhub → Python Producer → Kafka → Spark → Cassandra → Grafana
- Data Flow:
  1. WebSocket connects to Finnhub
  2. Messages encoded to Avro format
  3. Ingested into Kafka broker
  4. Spark processes with Structured Streaming
  5. Results persisted in Cassandra
  6. Dashboard updates every 500ms

**Repository:** https://github.com/piyush-an/Finnhub-Realtime-Pipeline

---

### Coinbase Exchange API

**Connectivity Options:**
- REST API: Lower-frequency trading
- FIX Order Entry API: Higher-frequency trading
- **WebSocket Feed:** Real-time market data streaming
- FIX Market Data API: Latency-sensitive scenarios

**Note:** FIX 4.2 deprecated June 3, 2025 - migrate to FIX 5

---

### CCXT Pro (Cryptocurrency Universal Library)

**Critical for Understanding Delta Updates and Caching:**

**WebSocket vs REST Pattern:**
```
REST Pattern (inefficient):
while (true):
    orderbook = await exchange.fetchOrderBook(symbol, limit)
    # react

WebSocket Pattern (efficient):
while (true):
    orderbook = await exchange.watchOrderBook(symbol, limit)
    # react
```

**Key Difference:** WebSocket uses incremental updates (deltas), REST requires full fetches

---

## 3. Core Concept: Incremental Data Structures & Delta Updates

### What Are Delta Updates?

Delta updates send only changed data between states, not full snapshots. This is fundamental to professional trading systems.

**Example: Order Book Updates**
```
Initial snapshot (full):
Bids: [100.5, 100.4, 100.3, 100.2, 100.1]
Asks: [100.6, 100.7, 100.8, 100.9, 101.0]

Delta update (only changes):
Bid at 100.3 removed
New ask at 101.1 added
```

**For OHLCV Candle Data:**
- Instead of fetching all candles up to now
- Receive only NEW candles since last update
- Local cache maintains historical data

### Implementation in CCXT Pro

**Cache Architecture:**
```python
# Configure cache limits
exchange = ccxtpro.binance({
    'options': {
        'tradesLimit': 1000,      # Store 1000 most recent trades
        'OHLCVLimit': 1000,       # Store 1000 candles per timeframe
        'ordersLimit': 1000,      # Store 1000 orders
    }
})

# Watch for new trades - only updates received
trades = await exchange.watch_trades(symbol, since=None, limit=2)
# Returns just the most recent 2 new trades, not full history
```

**Sliding Window Strategy:**
```
Cached Frame Size: 1000 trades
past > -----time----> future
       [===old===|===new===]

As new trades arrive:
- New trades added to end
- Oldest trades dropped from beginning
- Window stays at ~1000 trades
```

**Key Behavior:**
- Cache grows from 0 to limit (1000)
- Once full, maintains size by FIFO
- Only returns data within cached frame
- Cannot paginate beyond cached data

---

## 4. Optimal Architecture: Local Caching + WebSocket Streaming

### The Problem with Pure REST API Pulls

```python
# INEFFICIENT - Hitting rate limits
while True:
    # Get ALL candles from start to now every minute
    candles = api.fetch_candles(symbol='EURUSD', timeframe='1m')
    # Problem: Redundant data transfer, rate limit exhaustion

    # After 5 minutes with 10 symbols: 50 requests
    # After 1 hour: 600 requests (exceeds most rate limits)
```

### Optimal Solution: Historical Cache + Delta Updates

```python
class ForexDataManager:
    def __init__(self, symbol, timeframe='1m'):
        self.symbol = symbol
        self.timeframe = timeframe
        self.local_cache = {}  # {timestamp: OHLCV}
        self.last_candle_time = None

    async def initialize_historical_data(self, days_back=30):
        """
        ONE-TIME: Fetch historical data using REST
        Reduces rate limit impact by batching old data
        """
        historical = await self.api.fetch_ohlcv(
            self.symbol,
            self.timeframe,
            limit=days_back * 1440  # Max candles
        )
        for candle in historical:
            timestamp = candle[0]
            self.local_cache[timestamp] = candle

        self.last_candle_time = max(self.local_cache.keys())
        return len(self.local_cache)

    async def stream_updates(self):
        """
        CONTINUOUS: Stream only new candles via WebSocket
        Zero rate limit impact, efficient data transfer
        """
        async for candle in self.websocket.watch_ohlcv(
            self.symbol,
            self.timeframe
        ):
            timestamp = candle[0]

            # Only cache NEW candles since last update
            if timestamp > self.last_candle_time:
                self.local_cache[timestamp] = candle
                self.last_candle_time = timestamp
                yield candle  # Emit new candle event

            # Cleanup old candles (TTL strategy)
            self.cleanup_old_candles()

    def cleanup_old_candles(self, retention_days=30):
        """
        TTL Strategy: Remove candles older than retention period
        Prevents unbounded memory growth
        """
        cutoff = now() - timedelta(days=retention_days)
        expired = [
            ts for ts in self.local_cache
            if ts < cutoff
        ]
        for ts in expired:
            del self.local_cache[ts]
```

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│         STARTUP (One-time REST call)                │
│                                                       │
│  Fetch last 30 days of OHLCV via REST              │
│  (Batch operation - minimal rate impact)            │
│  ↓                                                   │
│  Load into local cache (TimescaleDB/Redis)         │
│  Historical data ready for backtesting             │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│    CONTINUOUS (WebSocket delta updates)             │
│                                                       │
│  WebSocket subscription (persistent)               │
│  ↓                                                   │
│  New candle arrives every 60 seconds                │
│  ↓                                                   │
│  Merge into local cache (append-only)              │
│  ↓                                                   │
│  Trigger trading signals/indicators                │
│  ↓                                                   │
│  Old data auto-deleted per TTL policy             │
└─────────────────────────────────────────────────────┘
```

---

## 5. Database Schemas for Caching OHLCV Data

### Option 1: TimescaleDB (PostgreSQL Extension)

**Best for:** High-frequency data, complex queries, cost-effective

```sql
-- TimescaleDB Hypertable for OHLCV data
CREATE TABLE ohlcv_data (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    trades_count INTEGER
);

-- Create hypertable with chunking by time
SELECT create_hypertable('ohlcv_data', 'time');

-- Partition by symbol for faster queries
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,timeframe'
);

-- Set TTL for automatic cleanup
SELECT add_retention_policy('ohlcv_data', INTERVAL '30 days');

-- Create materialized view for 15-minute candlestick
CREATE MATERIALIZED VIEW ohlcv_15m AS
SELECT
    time_bucket('15 min', time) AS bucket,
    symbol,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume
FROM ohlcv_data
GROUP BY bucket, symbol
WITH DATA;

-- Refresh materialized view on data insert
ALTER MATERIALIZED VIEW ohlcv_15m
    SET (timescaledb.materialized_only = false);
```

**Performance:** TimescaleDB shows 100x+ speedups for aggregation queries vs vanilla PostgreSQL

**Materialized View Benefits:**
- Incremental refresh on new data insert
- Pre-aggregated results ready instantly
- Efficient storage with compression
- Automatic partition management

### Option 2: InfluxDB (Time-Series Specialized)

**Best for:** Extremely high write rates, simple queries, minimal storage

```python
# InfluxDB 2.0 - Optimized for time series
from influxdb_client import InfluxDBClient, Point

client = InfluxDBClient(url="http://localhost:8086",
                        token="your-token",
                        org="your-org")
write_api = client.write_api(write_options=SYNCHRONOUS)

# Write OHLCV point
point = (
    Point("ohlcv")
    .tag("symbol", "EURUSD")
    .tag("timeframe", "1m")
    .field("open", 1.0950)
    .field("high", 1.0960)
    .field("low", 1.0945)
    .field("close", 1.0955)
    .field("volume", 1500000)
    .time(timestamp)
)

write_api.write(bucket="forex", record=point)

# Query with aggregation
query = '''from(bucket:"forex")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "ohlcv" and r.symbol == "EURUSD")
  |> aggregateWindow(every: 15m, fn: mean)
'''
```

**Advantages:**
- Built for time-series operations
- Automatic data compression
- Native TTL/retention policies
- High write throughput

### Option 3: Redis Time Series Module

**Best for:** Real-time cache, extremely fast reads, session data

```python
import redis
from redis.commands.timeseries import TimeSeries

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
ts = r.ts()

# Create time series with automatic retention
ts.create(
    'ohlcv:EURUSD:1m',
    retention_msecs=30*24*60*60*1000,  # 30 days
    labels={'symbol': 'EURUSD', 'timeframe': '1m'}
)

# Add OHLCV candle (store as JSON)
import json
candle_data = json.dumps({
    'o': 1.0950,
    'h': 1.0960,
    'l': 1.0945,
    'c': 1.0955,
    'v': 1500000
})

ts.add('ohlcv:EURUSD:1m', timestamp, candle_data)

# Query range with aggregation
candles = ts.range(
    'ohlcv:EURUSD:1m',
    from_time='-1h',
    to_time='+',
    aggregation_type='avg',
    bucket_size_msec=60000
)
```

**Advantages:**
- Sub-millisecond response times
- Automatic TTL cleanup
- Excellent for multi-symbol cache
- Perfect for in-memory cache layer

### Recommended Architecture: Hybrid Approach

```
┌──────────────────────────────────────────────────┐
│         Real-time Cache Layer                     │
│    (Redis Time Series - microsecond access)      │
│  - Current symbols (hot data)                    │
│  - Last 24 hours of candles                      │
│  - Automatic TTL expiry                          │
└──────────┬───────────────────────────────────────┘
           │ Sync every 5 minutes
           ↓
┌──────────────────────────────────────────────────┐
│    Historical Database Layer                      │
│  (TimescaleDB - optimized storage)               │
│  - Complete history (30+ days)                   │
│  - Materialized views for aggregations          │
│  - Compression enabled                           │
│  - TTL-based automatic cleanup                   │
└──────────────────────────────────────────────────┘
```

---

## 6. TTL (Time-To-Live) Strategies

### Different Data Types Require Different TTLs

| Data Type | Typical TTL | Rationale |
|-----------|-----------|-----------|
| 1-minute candles | 30 days | Sufficient for day trader backtesting |
| 5-minute candles | 90 days | Covers swing trading strategies |
| Hourly candles | 1 year | Long-term trend analysis |
| Daily candles | Unlimited | Historical reference |
| Tick data | 7 days | High storage cost, quickly stale |
| Order book snapshots | 1-3 hours | Not useful beyond session |
| Trade executions | 30-60 days | Regulatory/audit requirements |

### Implementation Examples

**TimescaleDB TTL:**
```sql
-- Automatic deletion for 1-minute candles after 30 days
SELECT add_retention_policy('ohlcv_data',
    INTERVAL '30 days',
    if_not_exists => true);

-- Can vary by symbol using triggers
-- Symbol 'EURUSD' keeps 60 days
-- Symbol 'EXOTICPAIR' keeps 14 days
```

**Redis TTL:**
```python
# Automatic expiry on every write
redis.setex(
    f'ohlcv:{symbol}:{timeframe}',
    ttl_seconds=30*24*60*60,  # 30 days
    value=candle_json
)

# Alternative: Set on key creation
ts.create('key', retention_msecs=30*24*60*60*1000)
```

**Application-Level TTL (Recommended for Control):**
```python
async def cleanup_cache():
    """Runs periodically to enforce TTL policies"""
    cutoff_times = {
        '1m': now() - timedelta(days=30),
        '5m': now() - timedelta(days=90),
        '1h': now() - timedelta(days=365),
        '1d': None,  # Keep forever
    }

    for timeframe, cutoff in cutoff_times.items():
        if cutoff:
            deleted = await db.ohlcv_data.delete_many({
                'timeframe': timeframe,
                'time': {'$lt': cutoff}
            })
            logger.info(f"Deleted {deleted} {timeframe} candles older than {cutoff}")
```

---

## 7. Delta Updates Implementation Strategy

### Scenario: Switching from REST to WebSocket

#### Phase 1: Historical Bootstrap (REST)

```python
async def bootstrap_historical_data():
    """
    One-time cost: Download all historical data
    Subsequent operations: Zero rate limit impact
    """
    # Single REST call with large limit
    candles = await api.fetch_ohlcv(
        'EURUSD',
        timeframe='1m',
        since=timestamp_30_days_ago,
        limit=43200  # All 1-min candles for 30 days
    )

    await db.ohlcv_data.insert_many([
        {
            'time': c[0],
            'symbol': 'EURUSD',
            'timeframe': '1m',
            'open': c[1],
            'high': c[2],
            'low': c[3],
            'close': c[4],
            'volume': c[5],
        }
        for c in candles
    ])

    return len(candles)  # Should be ~43200
```

#### Phase 2: Delta Streaming (WebSocket)

```python
async def stream_delta_updates():
    """
    Continuous stream of only NEW candles
    Connection reuses, no rate limits
    """
    last_processed = await db.ohlcv_data.find_one(
        sort=[('time', -1)]
    )
    last_timestamp = last_processed['time']

    async for candle in ws.watch_ohlcv('EURUSD', '1m'):
        timestamp = candle[0]

        if timestamp > last_timestamp:
            # New candle!
            await db.ohlcv_data.insert_one({
                'time': timestamp,
                'symbol': 'EURUSD',
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5],
            })

            last_timestamp = timestamp
            yield candle  # Emit for strategy processing
```

#### Phase 3: Handling Connection Drops (Critical)

```python
async def resilient_stream_with_recovery():
    """
    Handles disconnections gracefully
    Detects missed candles and backfills
    """
    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        try:
            last_db_candle = await db.get_last_candle('EURUSD', '1m')

            async for candle in ws.watch_ohlcv('EURUSD', '1m'):
                retry_count = 0  # Reset on successful stream

                # Check for gaps (missed candles during disconnect)
                gap = (candle[0] - last_db_candle['time']) / 60000  # in minutes
                if gap > 1:
                    logger.warning(f"Detected {gap} minute gap, backfilling...")
                    await backfill_missed_candles(
                        'EURUSD', '1m',
                        from_time=last_db_candle['time'] + 60000,
                        to_time=candle[0]
                    )

                await db.insert_candle(candle)
                last_db_candle = candle

        except Exception as e:
            retry_count += 1
            wait_time = min(2 ** retry_count, 60)  # Exponential backoff
            logger.error(f"Stream error: {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)

    raise Exception("Max retries exceeded, stream failed")

async def backfill_missed_candles(symbol, timeframe, from_time, to_time):
    """
    Fill gaps detected during WebSocket reconnection
    Uses REST API only when necessary
    """
    candles = await api.fetch_ohlcv(
        symbol,
        timeframe,
        since=from_time,
        limit=(to_time - from_time) / 60000 + 1
    )

    await db.ohlcv_data.insert_many([
        format_candle(c, symbol, timeframe)
        for c in candles
    ])

    logger.info(f"Backfilled {len(candles)} missing candles")
```

---

## 8. Professional Trading Systems Approach

### How Hedge Funds Handle Real-Time Data

**Key Findings:**
1. **Persistent Connections:** Single WebSocket connection per exchange, never closed
2. **Local Snapshots:** Complete market state maintained in memory
3. **Delta Merging:** Incoming updates merged into snapshots (not replacing)
4. **Multi-layer Cache:** Hot cache (Redis) + Cold storage (TimescaleDB)
5. **Rate Limit Awareness:** Monitor and respect provider limits even though WebSocket has none
6. **Redundancy:** Multiple data sources for critical symbols

### Example: Professional Architecture

```python
class ProfessionalForexSystem:
    def __init__(self):
        self.hot_cache = RedisTimeSeries()      # Last 1 hour
        self.cold_storage = TimescaleDB()        # 30+ days history
        self.websocket_connections = {}
        self.snapshot_state = {}                 # Current market state

    async def initialize(self, symbols_list):
        """Setup all necessary connections and cache"""

        # 1. Connect to exchanges
        for symbol in symbols_list:
            self.websocket_connections[symbol] = await self.connect_ws(symbol)

        # 2. Bootstrap historical data (one-time)
        for symbol in symbols_list:
            historical = await self.api.fetch_ohlcv(
                symbol, '1m',
                since=now() - timedelta(days=30)
            )
            await self.cold_storage.insert_batch(historical)

        # 3. Load recent data into hot cache
        for symbol in symbols_list:
            recent = await self.cold_storage.query(
                symbol=symbol,
                timeframe='1m',
                since=now() - timedelta(hours=1)
            )
            await self.hot_cache.load(symbol, recent)

        # 4. Start streaming delta updates
        for symbol in symbols_list:
            asyncio.create_task(self.stream_deltas(symbol))

    async def stream_deltas(self, symbol):
        """Continuous streaming with high availability"""
        backoff = 0.1

        while True:
            try:
                async for candle in self.websocket_connections[symbol]:
                    # Update snapshot
                    self.snapshot_state[symbol] = candle

                    # Write to both layers
                    await self.hot_cache.add(symbol, candle)
                    await self.cold_storage.add(symbol, candle)

                    # Trigger analysis
                    await self.analyze_market(symbol, candle)

                    backoff = 0.1  # Reset on success

            except Exception as e:
                logger.error(f"Error in delta stream for {symbol}: {e}")
                backoff = min(backoff * 2, 30)
                await asyncio.sleep(backoff)

    async def analyze_market(self, symbol, new_candle):
        """
        Process new candle through strategy
        Uses local snapshot for instant access
        """
        # Get full context from cache (no external calls)
        historical = await self.hot_cache.get_range(
            symbol,
            since=now() - timedelta(hours=24)
        )

        # Run technical analysis
        signals = self.strategy.analyze(historical, new_candle)

        # Execute trades if signals present
        if signals.buy:
            await self.execute_trade('buy', symbol)
        elif signals.sell:
            await self.execute_trade('sell', symbol)
```

---

## 9. Practical Code Examples

### Python Implementation with asyncio

```python
import asyncio
import aioredis
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ForexStreamingSystem:
    """
    Production-ready forex data streaming system
    Combines REST bootstrap + WebSocket delta updates + TTL caching
    """

    def __init__(self, provider_api, redis_url='redis://localhost'):
        self.api = provider_api
        self.redis = None
        self.redis_url = redis_url
        self.cache_ttl = {
            '1m': 30 * 24 * 3600,    # 30 days
            '5m': 90 * 24 * 3600,    # 90 days
            '1h': 365 * 24 * 3600,   # 1 year
        }

    async def initialize(self):
        """Setup connection and bootstrap data"""
        self.redis = await aioredis.create_redis_pool(self.redis_url)
        logger.info("Redis connected")

    async def bootstrap_symbol(self, symbol, timeframe='1m', days_back=30):
        """
        Initial historical data load (REST API)
        Batched to minimize rate limit impact
        """
        logger.info(f"Bootstrapping {symbol} {timeframe} ({days_back} days)")

        since = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)

        candles = await self.api.fetch_ohlcv(
            symbol,
            timeframe,
            since=since,
            limit=1000
        )

        cache_key = f"ohlcv:{symbol}:{timeframe}"

        for candle in candles:
            timestamp_str = datetime.fromtimestamp(candle[0]/1000).isoformat()
            candle_key = f"{cache_key}:{timestamp_str}"

            await self.redis.setex(
                candle_key,
                self.cache_ttl[timeframe],
                f"{candle[1]},{candle[2]},{candle[3]},{candle[4]},{candle[5]}"
            )

        logger.info(f"Loaded {len(candles)} candles for {symbol}")
        return len(candles)

    async def watch_symbol(self, symbol, timeframe='1m', callback=None):
        """
        Stream new candles via WebSocket
        Automatically updates cache with delta
        """
        logger.info(f"Starting watch for {symbol} {timeframe}")

        while True:
            try:
                async for candle in self.api.watch_ohlcv(symbol, timeframe):
                    timestamp = datetime.fromtimestamp(candle[0]/1000)
                    timestamp_str = timestamp.isoformat()

                    # Store in cache with TTL
                    cache_key = f"ohlcv:{symbol}:{timeframe}:{timestamp_str}"
                    candle_data = f"{candle[1]},{candle[2]},{candle[3]},{candle[4]},{candle[5]}"

                    await self.redis.setex(
                        cache_key,
                        self.cache_ttl[timeframe],
                        candle_data
                    )

                    logger.info(
                        f"[{timestamp_str}] {symbol} {timeframe} "
                        f"O:{candle[1]:.5f} H:{candle[2]:.5f} "
                        f"L:{candle[3]:.5f} C:{candle[4]:.5f} V:{int(candle[5])}"
                    )

                    if callback:
                        await callback(symbol, candle)

            except Exception as e:
                logger.error(f"Watch error for {symbol}: {e}")
                await asyncio.sleep(5)  # Exponential backoff in production

    async def get_historical(self, symbol, timeframe, limit=100):
        """
        Retrieve cached historical data
        Instant response from Redis, no external calls
        """
        pattern = f"ohlcv:{symbol}:{timeframe}:*"
        keys = await self.redis.keys(pattern)

        candles = []
        for key in sorted(keys)[-limit:]:
            data = await self.redis.get(key)
            if data:
                o, h, l, c, v = map(float, data.decode().split(','))
                candles.append([o, h, l, c, v])

        return candles

    async def close(self):
        """Cleanup resources"""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
        logger.info("Connection closed")

# Usage Example
async def main():
    system = ForexStreamingSystem(provider_api=your_api_instance)
    await system.initialize()

    # Bootstrap with historical data (one-time)
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
    for symbol in symbols:
        await system.bootstrap_symbol(symbol, timeframe='1m', days_back=30)

    # Start streaming updates
    tasks = [
        system.watch_symbol(symbol, timeframe='1m')
        for symbol in symbols
    ]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await system.close()

if __name__ == '__main__':
    asyncio.run(main())
```

### JavaScript Implementation with Node.js

```javascript
const ccxt = require('ccxt').pro;
const redis = require('redis').createClient();

class ForexStreamingSystem {
    constructor(exchangeName = 'binance') {
        this.exchange = new ccxt[exchangeName]({
            enableRateLimit: true,
            options: {
                tradesLimit: 1000,
                OHLCVLimit: 1000,
            }
        });
        this.redis = redis;
        this.cacheTTL = {
            '1m': 30 * 24 * 3600,
            '5m': 90 * 24 * 3600,
            '1h': 365 * 24 * 3600,
        };
    }

    async initialize() {
        await this.redis.connect();
        await this.exchange.loadMarkets();
        console.log('System initialized');
    }

    async bootstrapSymbol(symbol, timeframe = '1m', daysBack = 30) {
        console.log(`Bootstrapping ${symbol} ${timeframe}`);

        const since = Date.now() - (daysBack * 24 * 60 * 60 * 1000);

        const candles = await this.exchange.fetchOHLCV(
            symbol,
            timeframe,
            since
        );

        for (const candle of candles) {
            const [timestamp, o, h, l, c, v] = candle;
            const key = `ohlcv:${symbol}:${timeframe}:${timestamp}`;
            const value = JSON.stringify({ o, h, l, c, v });

            await this.redis.setEx(
                key,
                this.cacheTTL[timeframe],
                value
            );
        }

        console.log(`Loaded ${candles.length} candles`);
        return candles.length;
    }

    async watchSymbol(symbol, timeframe = '1m', callback = null) {
        console.log(`Watching ${symbol} ${timeframe}`);

        while (true) {
            try {
                const candles = await this.exchange.watchOHLCV(
                    symbol,
                    timeframe
                );

                for (const candle of candles) {
                    const [timestamp, o, h, l, c, v] = candle;
                    const date = new Date(timestamp);
                    const key = `ohlcv:${symbol}:${timeframe}:${timestamp}`;
                    const value = JSON.stringify({ o, h, l, c, v });

                    await this.redis.setEx(
                        key,
                        this.cacheTTL[timeframe],
                        value
                    );

                    console.log(
                        `[${date.toISOString()}] ${symbol} ` +
                        `O:${o.toFixed(5)} H:${h.toFixed(5)} ` +
                        `L:${l.toFixed(5)} C:${c.toFixed(5)} V:${Math.round(v)}`
                    );

                    if (callback) {
                        await callback(symbol, candle);
                    }
                }
            } catch (error) {
                console.error(`Watch error: ${error.message}`);
                await new Promise(resolve => setTimeout(resolve, 5000));
            }
        }
    }

    async getHistorical(symbol, timeframe, limit = 100) {
        const pattern = `ohlcv:${symbol}:${timeframe}:*`;
        const keys = await this.redis.keys(pattern);

        const candles = [];
        for (const key of keys.slice(-limit)) {
            const data = await this.redis.get(key);
            if (data) {
                candles.push(JSON.parse(data));
            }
        }

        return candles;
    }

    async close() {
        await this.exchange.close();
        await this.redis.quit();
        console.log('Closed');
    }
}

// Usage
(async () => {
    const system = new ForexStreamingSystem();
    await system.initialize();

    const symbols = ['BTC/USDT', 'ETH/USDT'];

    // Bootstrap
    for (const symbol of symbols) {
        await system.bootstrapSymbol(symbol, '1m', 30);
    }

    // Stream
    const tasks = symbols.map(symbol =>
        system.watchSymbol(symbol, '1m')
    );

    process.on('SIGINT', async () => {
        console.log('Shutting down...');
        await system.close();
        process.exit(0);
    });

    await Promise.all(tasks);
})();
```

---

## 10. Best Practices Summary

### Do's
- Use WebSocket for continuous market data (no rate limits per message)
- Bootstrap historical data once with REST (batch operation)
- Stream only NEW candles via WebSocket (delta updates)
- Cache locally in Redis/TimescaleDB with aggressive TTL
- Monitor connection health and auto-reconnect
- Implement exponential backoff for failures
- Use incremental structures (merge deltas, not replace)

### Don'ts
- Don't poll REST API for every new candle (rate limit suicide)
- Don't store unlimited historical data in memory
- Don't ignore provider connection limits (40 concurrent IG connections)
- Don't assume WebSocket connection is permanent (handle disconnections)
- Don't mix update strategies (don't fetch full candles then merge deltas)
- Don't ignore TTL policies (memory will grow unbounded)

### Rate Limit Math

```
REST API Polling (INEFFICIENT):
- Symbol EURUSD, 1m timeframe
- Poll every minute: 1 request/min
- 10 symbols: 10 requests/min
- Over 1 hour: 600 requests
- Daily: 14,400 requests (exceeds most limits)

WebSocket Streaming (EFFICIENT):
- 1 connection for 10 symbols
- Updates pushed continuously
- 0 requests per message
- Daily: 0 rate limit consumption
- Can add 100+ symbols on same connection
```

---

## 11. Key Insights from Industry Leaders

### IG Markets
- Max 40 concurrent WebSocket connections
- Uses Lightstreamer protocol (built for financial data)
- Stream type: Sub (receive only)
- No per-message rate limits

### Finnhub + Spark Pipeline
- Real-time trades from WebSocket
- Kafka for message queue (decoupling)
- Spark for aggregation (calculate OHLCV from trades)
- Cassandra for persistence
- Dashboard updates every 500ms
- Architecture scales horizontally

### Coinbase
- WebSocket Feed for real-time market data
- REST API for low-frequency trading
- FIX APIs for high-frequency trading
- Multiple connectivity options for different use cases

### CCXT Pro
- Incremental data structures (sliding window caches)
- Delta merging (only changes transmitted)
- Default 1000-entry cache per data type
- Real-time vs throttling modes
- Automatic reconnection and rate limiting

---

## 12. Implementation Roadmap

### Week 1: Foundation
- Set up Redis TimeSeries instance
- Set up TimescaleDB instance
- Create WebSocket connection wrapper

### Week 2: Bootstrap & Streaming
- Implement REST bootstrap (historical data load)
- Implement WebSocket delta streaming
- Add cache management with TTL

### Week 3: Resilience
- Add reconnection logic with exponential backoff
- Implement gap detection and backfill
- Add connection health monitoring

### Week 4: Optimization
- Profile cache hit rates
- Tune TTL policies per timeframe
- Optimize database queries
- Add metrics/logging

---

## References

1. **IG Trading API:** https://labs.ig.com/streaming-api-guide
2. **Finnhub WebSocket:** https://finnhub.io/docs/api/websocket-trades
3. **CCXT Pro Manual:** https://github.com/ccxt/ccxt/wiki/ccxt.pro.manual
4. **QuestDB Materialized Views:** https://questdb.com/docs/guides/mat-views/
5. **Coinbase Exchange API:** https://docs.cdp.coinbase.com/exchange/introduction/welcome
6. **TimescaleDB Financial Data:** https://docs.tigerdata.com/tutorials/latest/financial-tick-data/
7. **Finnhub Real-Time Pipeline (GitHub):** https://github.com/piyush-an/Finnhub-Realtime-Pipeline
8. **Redis Time Series:** https://redis.io/docs/latest/develop/data-types/timeseries/

---

## Conclusion

Professional trading systems don't poll REST APIs for market data—they use persistent WebSocket connections with local caching. The architecture combines:

1. **One-time REST bootstrap** for historical data
2. **Continuous WebSocket streaming** for new candles
3. **Local cache (Redis)** for hot data access
4. **Persistent database (TimescaleDB)** for history
5. **TTL policies** to prevent unbounded growth
6. **Delta merging** to handle incremental updates efficiently

This eliminates rate limiting issues entirely while providing sub-millisecond latency for trading decisions.
