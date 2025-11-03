# DataHub Architecture - Shared Memory Market Data System

## 🎯 Overview

The DataHub provides sub-millisecond shared memory access to real-time market data across all processes in the trading system. This eliminates the need for direct WebSocket/DataBento access from trading agents.

## 🏗️ Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    SCALPING DASHBOARD (Main Process)             │
│                                                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │          DataHubManager (BaseManager)                      │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │             DataHub (In-Memory Cache)                 │ │  │
│  │  │                                                        │ │  │
│  │  │  • Ticks: Dict[symbol → Tick]                        │ │  │
│  │  │  • Candles: Dict[symbol → Deque[Candle]] (100 bars)  │ │  │
│  │  │  • OrderFlow: Dict[symbol → OrderFlowMetrics]        │ │  │
│  │  │  • Thread-safe with locks                            │ │  │
│  │  │  • Sub-millisecond access                            │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│           ▲                    ▲                    ▲            │
│           │ (push)             │ (push)            │ (read)     │
│           │                    │                    │            │
│  ┌────────┴──────┐    ┌───────┴───────┐    ┌──────┴──────────┐│
│  │ WebSocket     │    │  DataBento    │    │ UnifiedData     ││
│  │ Collector     │    │  Client       │    │ Fetcher         ││
│  │               │    │               │    │                 ││
│  │ • Aggregates  │    │ • Calculates  │    │ • Reads ticks   ││
│  │   ticks to 1m │    │   OFI, volume │    │ • Reads candles ││
│  │ • Pushes      │    │   imbalance   │    │ • Reads order   ││
│  │   candles     │    │ • Pushes      │    │   flow          ││
│  │ • Pushes ticks│    │   metrics     │    │ • DB fallback   ││
│  └───────────────┘    └───────────────┘    └─────────────────┘│
│         ▼                      ▼                      ▼          │
│  [PostgreSQL]          [PostgreSQL]          [ScalpingEngine]  │
│  (persistence)         (persistence)         (60-second cycle)  │
└──────────────────────────────────────────────────────────────────┘
```

## 📦 Components

### 1. Market Data Models (`market_data_models.py`)

**Dataclasses:**
- `Tick`: Real-time bid/ask/spread
- `Candle`: OHLC 1-minute candles
- `OrderFlowMetrics`: OFI, volume delta, imbalance, toxicity

### 2. DataHub (`data_hub.py`)

**Core Cache:**
- Thread-safe in-memory storage
- Rolling window (100-200 candles per symbol)
- Staleness detection (TTL checks)
- Warm-start from database

**Methods:**
```python
# Producers call these:
hub.update_tick(tick: Tick)
hub.update_candle_1m(candle: Candle)
hub.update_order_flow(metrics: OrderFlowMetrics)

# Consumers call these:
tick = hub.get_latest_tick(symbol: str) -> Tick
candles = hub.get_latest_candles(symbol: str, limit: int) -> List[Candle]
metrics = hub.get_latest_order_flow(symbol: str) -> OrderFlowMetrics
```

### 3. DataHubManager (`data_hub.py`)

**Multiprocessing Manager:**
- Based on `multiprocessing.managers.BaseManager`
- Exports DataHub instance
- Runs on `127.0.0.1:50000`
- Auth key: `forex_scalper_2025`

**Usage:**
```python
# In dashboard (server):
manager = start_data_hub_manager()
hub = manager.DataHub()

# In subprocess (client):
hub = connect_to_data_hub()
# or
hub = get_data_hub_from_env()  # Uses env vars
```

### 4. Updated Components

**ForexWebSocketCollector:**
- Added: `data_hub` parameter
- Added: `get_latest_tick()` method
- Added: `get_latest_candles()` method
- Added: Tick aggregation to 1-minute candles
- Pushes: Ticks and candles to DataHub
- Keeps: Database persistence as-is

**DataBentoClient:**
- Added: `data_hub` parameter
- Added: `get_latest_order_flow()` method
- Added: OFI calculation (Order Flow Imbalance)
- Added: Volume delta calculation
- Added: VWAP and sweep detection
- Pushes: OrderFlowMetrics to DataHub
- Keeps: Database persistence as-is

**UnifiedDataFetcher:**
- Changed: Uses DataHub as primary source
- Removed: Direct websocket/databento access
- Added: Database fallback for cold start
- Simplified: Only needs DataHub reference

## 🚀 Initialization Flow

### Step 1: Start DataHub Manager (Dashboard)

```python
from data_hub import start_data_hub_manager

# Start manager on main process
manager = start_data_hub_manager(
    address=('127.0.0.1', 50000),
    authkey=b'forex_scalper_2025'
)
hub = manager.DataHub()

# Set environment variables for subprocesses
os.environ['DATA_HUB_HOST'] = '127.0.0.1'
os.environ['DATA_HUB_PORT'] = '50000'
os.environ['DATA_HUB_AUTHKEY'] = 'forex_scalper_2025'
```

### Step 2: Warm-Start DataHub

```python
# Load last 100 candles from database for all pairs
def fetch_candles_from_db(symbol, limit):
    # Query database...
    return candles_list

hub.warm_start_all(
    symbols=['EUR_USD', 'GBP_USD', 'USD_JPY'],
    db_fetch_func=fetch_candles_from_db,
    limit=100
)
```

### Step 3: Start Data Producers

```python
# WebSocket Collector (subprocess or thread)
websocket = ForexWebSocketCollector(
    db_manager=db,
    persistence_manager=persistence,
    data_hub=hub  # Pass DataHub reference
)
websocket.run_forever()

# DataBento Client (subprocess or thread)
databento = DataBentoClient(
    config=config,
    db_manager=db,
    data_hub=hub  # Pass DataHub reference
)
await databento.start()
```

### Step 4: Initialize UnifiedDataFetcher

```python
from unified_data_fetcher import get_unified_data_fetcher

# Create fetcher with DataHub
fetcher = get_unified_data_fetcher(data_hub=hub)

# Optional: Inject other sources
fetcher.inject_sources(
    data_hub=hub,
    finnhub_integration=finnhub,
    insightsentry=insightsentry,
    db=db_manager
)
```

### Step 5: Inject into ScalpingEngine

```python
engine = ScalpingEngine()
engine.set_data_fetcher(fetcher)
engine.run()
```

## ⚡ Performance Characteristics

**Latency:**
- DataHub read: < 1 ms
- Database read: 10-50 ms
- WebSocket stream: Real-time

**Memory:**
- 20 pairs × 100 candles × 80 bytes = ~160 KB
- Ticks: 20 pairs × 100 bytes = 2 KB
- Order flow: 20 pairs × 500 bytes = 10 KB
- **Total: < 1 MB**

**Throughput:**
- 60-second analysis cycle: ✅ Easy
- 1-second cycle: ✅ Possible
- 100ms cycle: ⚠️  Needs optimization

## 🔄 Data Flow Example

### Real-Time Tick Processing

```
1. IG sends tick via WebSocket
   ↓
2. ForexWebSocketCollector receives
   ↓
3. Tick aggregated into forming candle
   ↓
4. Push to DataHub: hub.update_tick(tick)
   ↓
5. On minute boundary: hub.update_candle_1m(candle)
   ↓
6. Background: Save to database
```

### Engine Analysis Cycle

```
1. Engine triggers 60-second analysis
   ↓
2. Calls: fetcher.fetch_market_data('EUR_USD')
   ↓
3. UnifiedDataFetcher calls DataHub:
   - candles = hub.get_latest_candles('EUR_USD', 100)
   - tick = hub.get_latest_tick('EUR_USD')
   - order_flow = hub.get_latest_order_flow('EUR_USD')
   ↓
4. If insufficient data: fallback to database
   ↓
5. Return complete market_data to engine
   ↓
6. Agents analyze and generate signals
```

## 🛡️ Staleness Detection

**TTL Settings:**
- Tick: 2 seconds (very fast)
- Candle: 120 seconds (2 minutes)
- Order Flow: 5 seconds (fast)

**Staleness Handling:**
```python
staleness = hub.check_staleness('EUR_USD')
# Returns: {'tick': False, 'candle': False, 'order_flow': False}

if staleness['tick']:
    logger.warning("Tick data stale - spread unavailable")
    # Engine skips trade or uses wider spread estimate
```

## 📊 Monitoring

**DataHub Status:**
```python
status = hub.get_status()
# Returns:
{
    'symbols_tracked': ['EUR_USD', 'GBP_USD', 'USD_JPY'],
    'ticks_count': 3,
    'candles_by_symbol': {'EUR_USD': 100, 'GBP_USD': 95, 'USD_JPY': 100},
    'order_flow_count': 3,
    'stats': {
        'ticks_received': 15234,
        'candles_received': 312,
        'order_flow_updates': 1523,
        'get_tick_calls': 450,
        'get_candles_calls': 150,
        'get_flow_calls': 150
    },
    'last_updates': {...}
}
```

## 🐛 Troubleshooting

### Issue: DataHub connection fails

**Symptoms:**
```
Failed to connect to DataHub: [Errno 61] Connection refused
```

**Solution:**
1. Check DataHub manager is running
2. Verify address/port/authkey
3. Check firewall settings
4. Ensure environment variables set

### Issue: No candles in DataHub

**Symptoms:**
```
DataHub had 0/100 candles
```

**Solution:**
1. Check warm-start was called
2. Verify WebSocket is pushing candles
3. Check DataHub logs for errors
4. Manually check: `hub.get_status()`

### Issue: Stale data warnings

**Symptoms:**
```
Tick data stale - spread unavailable
```

**Solution:**
1. Check WebSocket connection alive
2. Verify DataHub manager running
3. Check network latency
4. Adjust TTL settings if needed

## 🔧 Configuration

**Environment Variables:**
```bash
DATA_HUB_HOST=127.0.0.1
DATA_HUB_PORT=50000
DATA_HUB_AUTHKEY=forex_scalper_2025
```

**Python Configuration:**
```python
# In dashboard initialization
DATAHUB_CONFIG = {
    'address': ('127.0.0.1', 50000),
    'authkey': b'forex_scalper_2025',
    'max_candles': 200,  # Per symbol
    'cache_ttl': 60,  # Seconds
}
```

## ✅ Benefits

1. **Performance**: Sub-millisecond data access
2. **Scalability**: Supports 20+ pairs easily
3. **Simplicity**: No external dependencies (Redis, etc.)
4. **Isolation**: Producer/consumer decoupling
5. **Reliability**: Database fallback
6. **Monitoring**: Built-in staleness detection

## 🚀 Next Steps

1. **Test**: Run complete flow end-to-end
2. **Monitor**: Check DataHub stats regularly
3. **Optimize**: Tune TTL and cache sizes
4. **Scale**: Add more currency pairs
5. **Extend**: Add ML features to DataHub
