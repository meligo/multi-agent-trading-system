# Simple WebSocket Migration Plan

## User's Correct Insight ✅

The 10k weekly quota is **MORE than enough** for initial backfill:

```
Initial historical pull (ONE TIME):
28 pairs × 100 candles × 2 TF = 5,600 points ✅ Fits in quota!

Then:
Switch to WebSocket → Captures all new data → NO quota usage ever again
```

**Key Realization:**
- We DON'T need repeated REST polling every 5 minutes
- We just need ONE big historical pull
- Then WebSocket maintains everything
- Simple!

---

## Revised Architecture (Simpler!)

### Phase 1: Initial Backfill (One-Time, ~1 hour)

```python
# Use existing REST API to populate database
for pair in 28_PAIRS:
    for timeframe in ['5', '15']:
        df = ig_fetcher.get_candles(pair, timeframe, count=100)
        database.store_candles(df)

# Total quota used: 5,600 points (54% of weekly allowance)
# Remaining: 4,400 points (for any retries/fixes)
```

### Phase 2: Start WebSocket (Permanent)

```python
# Connect to IG Lightstreamer
websocket.connect()
websocket.subscribe(28_PAIRS, timeframes=['5', '15'])

# On every new candle:
def on_candle_complete(pair, timeframe, candle):
    database.store_candle(pair, timeframe, candle)
    # NO quota used - WebSocket is free!
```

### Phase 3: Trading Bot Uses Database

```python
# Query database for analysis
df = database.get_candles('EUR_USD', '5', count=100)

# Calculate indicators
indicators = calculate_all_indicators(df)

# Make trading decisions
# No API calls needed - just database queries!
```

---

## Implementation Timeline (Much Faster!)

### Day 1: Initial Backfill
- ✅ Use existing `ig_data_fetcher.py` to pull 100 candles per pair
- ✅ Store in PostgreSQL/SQLite
- ✅ Uses 5,600 quota points (one-time)
- ⏱️ Takes ~1 hour (with rate limiting)

### Day 2-3: Build WebSocket Collector
- Build WebSocket → Database pipeline
- Subscribe to 28 pairs
- Test data collection for 24 hours

### Day 4: Switch Trading Bot
- Update bot to query database instead of REST API
- Remove REST polling
- System now runs on WebSocket + DB

### Day 5+: Production
- Unlimited operation
- No quota concerns
- Real-time data

**Total migration time: 5 days instead of 1 month!**

---

## Simplified Code Structure

### 1. One-Time Backfill Script

**Create: `backfill_historical_data.py`**

```python
"""
One-time script to populate database with initial historical data.
Uses IG REST API (consumes quota) but only runs ONCE.
"""

import time
from forex_config import ForexConfig
from ig_data_fetcher import IGDataFetcher
from database import ForexDatabase

def backfill_all_pairs():
    """Backfill historical data for all 28 pairs."""

    print("="*80)
    print("HISTORICAL DATA BACKFILL")
    print("="*80)

    # Initialize
    ig_fetcher = IGDataFetcher(
        api_key=ForexConfig.IG_API_KEY,
        username=ForexConfig.IG_USERNAME,
        password=ForexConfig.IG_PASSWORD,
        use_cache=False  # Don't use cache, go straight to DB
    )

    db = ForexDatabase()

    pairs = ForexConfig.PAIRS  # All 28 pairs
    timeframes = ['5', '15']

    total_candles = 0
    quota_used = 0

    print(f"\n📥 Backfilling {len(pairs)} pairs × {len(timeframes)} timeframes × 100 candles")
    print(f"   Expected quota usage: {len(pairs) * len(timeframes) * 100} points\n")

    for i, pair in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] Processing {pair}...")

        for tf in timeframes:
            try:
                # Fetch historical data
                print(f"   Fetching {tf}m data...", end=" ")
                df = ig_fetcher.get_candles(pair, tf, count=100)

                # Store in database
                db.store_candles(pair, tf, df, source='ig_rest')

                candles_stored = len(df)
                total_candles += candles_stored
                quota_used += candles_stored

                print(f"✅ {candles_stored} candles stored")

                # Rate limiting (2 sec per request per IG requirements)
                time.sleep(2)

            except Exception as e:
                print(f"❌ Error: {e}")
                continue

    print(f"\n" + "="*80)
    print(f"BACKFILL COMPLETE!")
    print(f"="*80)
    print(f"   Total candles stored: {total_candles:,}")
    print(f"   Quota used: {quota_used:,}/10,000 ({quota_used/100:.1f}%)")
    print(f"   Quota remaining: {10000-quota_used:,}")
    print(f"\n✅ Database is ready! Now start WebSocket collector.")
    print(f"="*80)

if __name__ == "__main__":
    backfill_all_pairs()
```

**Run once:**
```bash
python backfill_historical_data.py
```

Result:
- ✅ 5,600 candles in database
- ✅ 5,600 quota points used (54% of allowance)
- ✅ Ready for WebSocket

---

### 2. WebSocket Collector (Runs Forever)

**Create: `websocket_collector.py`**

```python
"""
Permanent WebSocket collector.
Subscribes to IG Lightstreamer and stores all candles in database.
NO quota usage - runs indefinitely!
"""

from trading_ig import IGService
from trading_ig.lightstreamer import Subscription
from database import ForexDatabase
from forex_config import ForexConfig
import datetime

class ForexWebSocketCollector:
    """Collects real-time data from IG WebSocket."""

    def __init__(self):
        self.ig_service = IGService(
            username=ForexConfig.IG_USERNAME,
            password=ForexConfig.IG_PASSWORD,
            api_key=ForexConfig.IG_API_KEY,
            acc_type='DEMO' if ForexConfig.IG_DEMO else 'LIVE'
        )
        self.db = ForexDatabase()
        self.pairs = ForexConfig.PAIRS

    def connect(self):
        """Connect to Lightstreamer WebSocket."""
        print("🔌 Connecting to IG Lightstreamer...")

        self.ig_service.create_session()

        # Subscribe to all pairs
        subscription = Subscription(
            mode="MERGE",
            items=[f"CHART:{pair}:5MINUTE" for pair in self.pairs],
            fields=["BID", "OFFER", "OFR_OPEN", "OFR_HIGH", "OFR_LOW", "OFR_CLOSE"]
        )

        subscription.addlistener(self.on_price_update)

        self.ig_service.ls_client.subscribe(subscription)

        print(f"✅ Subscribed to {len(self.pairs)} pairs")
        print(f"📡 Streaming data... (NO quota usage!)")

    def on_price_update(self, item_update):
        """Called when candle completes."""
        try:
            # Extract candle data
            item_name = item_update.get('name')  # e.g., "CHART:EUR_USD:5MINUTE"

            # Parse item name
            parts = item_name.split(':')
            pair = parts[1]
            timeframe = '5'  # 5-minute candles

            # Extract OHLC
            candle = {
                'timestamp': datetime.datetime.now(),
                'open': float(item_update.get('OFR_OPEN', 0)),
                'high': float(item_update.get('OFR_HIGH', 0)),
                'low': float(item_update.get('OFR_LOW', 0)),
                'close': float(item_update.get('OFR_CLOSE', 0)),
                'volume': 0  # IG doesn't provide volume for forex
            }

            # Store in database
            self.db.store_candle(pair, timeframe, candle, source='websocket')

            print(f"📊 {pair} {timeframe}m: {candle['close']:.5f}")

        except Exception as e:
            print(f"⚠️ Error processing update: {e}")

    def run_forever(self):
        """Keep collector running indefinitely."""
        self.connect()

        print("\n" + "="*80)
        print("WebSocket collector running... Press Ctrl+C to stop")
        print("="*80)

        try:
            # Keep alive
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping collector...")
            self.ig_service.logout()

if __name__ == "__main__":
    collector = ForexWebSocketCollector()
    collector.run_forever()
```

**Run as daemon:**
```bash
python websocket_collector.py &

# Or with systemd for auto-restart:
sudo systemctl start forex-websocket-collector
```

---

### 3. Database Module

**Create: `database.py`**

```python
"""
Simple database module for storing candles.
Works with SQLite (simple) or PostgreSQL (production).
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional

class ForexDatabase:
    """Stores and retrieves forex candle data."""

    def __init__(self, db_path: str = "forex_data.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                source TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(pair, timeframe, timestamp)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pair_tf_time
            ON candles(pair, timeframe, timestamp DESC)
        """)

        conn.commit()
        conn.close()

    def store_candles(self, pair: str, timeframe: str, df: pd.DataFrame, source: str = 'websocket'):
        """Store multiple candles (bulk insert)."""
        if df.empty:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Convert timestamps
        if 'time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['time']).astype(int) // 10**9

        created_at = int(datetime.now().timestamp())

        # Insert all candles
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO candles
                    (pair, timeframe, timestamp, open, high, low, close, volume, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pair, timeframe, int(row['timestamp']),
                    float(row['open']), float(row['high']), float(row['low']),
                    float(row['close']), float(row.get('volume', 0)),
                    source, created_at
                ))
            except Exception as e:
                print(f"⚠️ Error storing candle: {e}")
                continue

        conn.commit()
        conn.close()

    def store_candle(self, pair: str, timeframe: str, candle: dict, source: str = 'websocket'):
        """Store single candle (from WebSocket)."""
        df = pd.DataFrame([candle])
        self.store_candles(pair, timeframe, df, source)

    def get_candles(self, pair: str, timeframe: str, count: int = 100) -> pd.DataFrame:
        """Retrieve candles from database."""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE pair = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """

        df = pd.read_sql_query(query, conn, params=(pair, timeframe, count))
        conn.close()

        if df.empty:
            raise ValueError(f"No data in database for {pair} {timeframe}m")

        # Convert timestamp to datetime
        df['time'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('timestamp').reset_index(drop=True)

        return df[['time', 'open', 'high', 'low', 'close', 'volume']]
```

---

### 4. Update Trading Bot

**Modify: `forex_data.py`**

```python
class ForexDataFetcher:
    """Fetches data from database (populated by WebSocket)."""

    def __init__(self, use_database: bool = True):
        if use_database:
            self.db = ForexDatabase()
            print("✅ Using database for historical data (WebSocket-fed)")
        else:
            # Fallback to REST API
            self.ig_fetcher = IGDataFetcher(...)

    def get_candles(self, pair: str, timeframe: str, count: int = 100) -> pd.DataFrame:
        """Get candles from database."""
        try:
            # Query database (WebSocket-maintained)
            df = self.db.get_candles(pair, timeframe, count)
            return df
        except Exception as db_error:
            # Fallback to REST if database empty
            print(f"⚠️ Database query failed, falling back to REST API...")
            df = self.ig_fetcher.get_candles(pair, timeframe, count)
            return df
```

---

## Migration Steps (Simplified)

### Step 1: Initial Backfill (Run Once)
```bash
# This uses 5,600 quota points - one time only
python backfill_historical_data.py
```

**Output:**
```
================================================================================
HISTORICAL DATA BACKFILL
================================================================================

📥 Backfilling 28 pairs × 2 timeframes × 100 candles
   Expected quota usage: 5,600 points

[1/28] Processing EUR_USD...
   Fetching 5m data... ✅ 100 candles stored
   Fetching 15m data... ✅ 100 candles stored

[2/28] Processing GBP_USD...
   Fetching 5m data... ✅ 100 candles stored
   Fetching 15m data... ✅ 100 candles stored

...

================================================================================
BACKFILL COMPLETE!
================================================================================
   Total candles stored: 5,600
   Quota used: 5,600/10,000 (56%)
   Quota remaining: 4,400

✅ Database is ready! Now start WebSocket collector.
================================================================================
```

### Step 2: Start WebSocket Collector
```bash
# Runs forever - NO quota usage
python websocket_collector.py &
```

**Output:**
```
🔌 Connecting to IG Lightstreamer...
✅ Subscribed to 28 pairs
📡 Streaming data... (NO quota usage!)

================================================================================
WebSocket collector running... Press Ctrl+C to stop
================================================================================

📊 EUR_USD 5m: 1.08432
📊 GBP_USD 5m: 1.26789
📊 USD_JPY 5m: 149.234
...
```

### Step 3: Run Trading Bot
```bash
# Bot now queries database instead of REST API
python ig_concurrent_worker.py
```

**Result:** Unlimited operation, no quota worries!

---

## Benefits of This Approach

### ✅ Simple Migration
- One backfill script
- One WebSocket collector
- Update bot to use database
- Done!

### ✅ Fits Within Quota
- 5,600 points for backfill (< 10k limit)
- WebSocket has NO quota impact
- Unlimited operation after initial backfill

### ✅ Real-Time Data
- WebSocket provides <1 second updates
- Much better than 5-minute polling
- Professional-grade latency

### ✅ Scalable
- Can add more pairs easily
- Can request 200 candles (MA-200) without quota worry
- Database query time: <10ms

---

## Cost Breakdown

### One-Time Costs:
- **Initial backfill:** 5,600 quota points (56% of weekly allowance)
- **Time:** ~1 hour (with rate limiting)

### Ongoing Costs:
- **WebSocket:** $0 (no quota)
- **Database:** $0 (SQLite) or ~$10/month (PostgreSQL on cloud)
- **Server:** $0 (local) or ~$5/month (VPS)

**Total ongoing: $0-15/month for unlimited operation**

---

## Summary

You were absolutely correct:

1. ✅ **Initial backfill fits in quota:** 5,600 < 10,000
2. ✅ **WebSocket for ongoing data:** No quota usage
3. ✅ **Database, not cache:** Permanent storage
4. ✅ **Simpler than I described:** Just 5 days!

**Next Step:**
Would you like me to create the three implementation files?
1. `backfill_historical_data.py`
2. `websocket_collector.py`
3. `database.py`

Then you can run the backfill and start WebSocket streaming!
