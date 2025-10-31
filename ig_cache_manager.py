"""
IG Data Cache Manager - Quota-Efficient Historical Data Storage

Solves IG's 10,000 weekly historical data point limit by:
1. Caching all historical candles in SQLite
2. Only fetching NEW candles (delta updates)
3. Using free /markets endpoint for current prices
4. Reconstructing candles from price snapshots when quota exhausted

Math:
- Old system: 24 pairs × 100 candles × 2 TF = 4,800 points/cycle → quota exhausted in 10 min
- New system: 24 pairs × 1 candle = 24 points/cycle → 10,000 / 24 = 416 cycles = ~35 hours
- With Finnhub fallback: Unlimited operation
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple
import json
from pathlib import Path


class IGCacheManager:
    """
    Manages local cache of IG historical data to minimize quota usage.

    Strategy:
    1. Store all fetched candles in SQLite
    2. Track last candle timestamp per pair/timeframe
    3. Only fetch candles newer than last cached candle
    4. Fallback to Finnhub when IG quota exhausted
    """

    def __init__(self, db_path: str = "ig_cache.db"):
        """Initialize cache manager with SQLite database."""
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Candles table - stores all OHLCV data
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

        # Index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pair_timeframe_timestamp
            ON candles(pair, timeframe, timestamp DESC)
        """)

        # Metadata table - tracks last update and quota usage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                pair TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                last_timestamp INTEGER,
                last_update INTEGER,
                total_candles INTEGER DEFAULT 0,
                PRIMARY KEY(pair, timeframe)
            )
        """)

        # Quota usage tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quota_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                pair TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                candles_fetched INTEGER NOT NULL,
                source TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

        print(f"✅ Cache database initialized: {self.db_path}")

    def get_cached_candles(
        self,
        pair: str,
        timeframe: str,
        count: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve cached candles from database.

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            timeframe: Timeframe ('1', '5', '15', etc.)
            count: Number of most recent candles to return

        Returns:
            DataFrame with cached candles or None if not enough data
        """
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT timestamp, open, high, low, close, volume, source
            FROM candles
            WHERE pair = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """

        df = pd.read_sql_query(query, conn, params=(pair, timeframe, count))
        conn.close()

        if len(df) < count:
            return None  # Not enough cached data

        # Convert timestamp to datetime
        df['time'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('timestamp').reset_index(drop=True)

        return df[['time', 'open', 'high', 'low', 'close', 'volume', 'source']]

    def get_last_timestamp(self, pair: str, timeframe: str) -> Optional[int]:
        """Get timestamp of last cached candle."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT last_timestamp FROM metadata
            WHERE pair = ? AND timeframe = ?
        """, (pair, timeframe))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def store_candles(
        self,
        pair: str,
        timeframe: str,
        df: pd.DataFrame,
        source: str = "ig"
    ):
        """
        Store candles in cache.

        Args:
            pair: Currency pair
            timeframe: Timeframe
            df: DataFrame with columns: time, open, high, low, close, volume
            source: Data source ('ig' or 'finnhub')
        """
        if df.empty:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Convert to Unix timestamps
        if 'time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['time']).astype(int) // 10**9

        created_at = int(datetime.now().timestamp())

        # Insert candles (ignore duplicates)
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO candles
                    (pair, timeframe, timestamp, open, high, low, close, volume, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pair, timeframe, int(row['timestamp']),
                    float(row['open']), float(row['high']), float(row['low']),
                    float(row['close']), float(row['volume']),
                    source, created_at
                ))
            except Exception as e:
                print(f"⚠️  Error storing candle: {e}")
                continue

        # Update metadata
        last_timestamp = int(df['timestamp'].max())
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (pair, timeframe, last_timestamp, last_update, total_candles)
            VALUES (?, ?, ?, ?,
                (SELECT COUNT(*) FROM candles WHERE pair = ? AND timeframe = ?)
            )
        """, (pair, timeframe, last_timestamp, created_at, pair, timeframe))

        # Track quota usage (only for IG)
        if source == "ig":
            cursor.execute("""
                INSERT INTO quota_usage (timestamp, pair, timeframe, candles_fetched, source)
                VALUES (?, ?, ?, ?, ?)
            """, (created_at, pair, timeframe, len(df), source))

        conn.commit()
        conn.close()

        print(f"✅ Cached {len(df)} {timeframe}m candles for {pair} from {source}")

    def get_weekly_quota_usage(self) -> int:
        """Calculate IG data points used in last 7 days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        week_ago = int((datetime.now() - timedelta(days=7)).timestamp())

        cursor.execute("""
            SELECT SUM(candles_fetched)
            FROM quota_usage
            WHERE timestamp >= ? AND source = 'ig'
        """, (week_ago,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result[0] else 0

    def needs_update(self, pair: str, timeframe: str, max_age_minutes: int = 10) -> bool:
        """Check if cached data needs updating."""
        last_ts = self.get_last_timestamp(pair, timeframe)

        if not last_ts:
            return True  # No cached data

        age_seconds = datetime.now().timestamp() - last_ts
        age_minutes = age_seconds / 60

        return age_minutes > max_age_minutes

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total candles
        cursor.execute("SELECT COUNT(*) FROM candles")
        total_candles = cursor.fetchone()[0]

        # By source
        cursor.execute("SELECT source, COUNT(*) FROM candles GROUP BY source")
        by_source = dict(cursor.fetchall())

        # Weekly quota usage
        weekly_usage = self.get_weekly_quota_usage()

        # Pairs cached
        cursor.execute("SELECT COUNT(DISTINCT pair) FROM candles")
        pairs_cached = cursor.fetchone()[0]

        conn.close()

        return {
            "total_candles": total_candles,
            "by_source": by_source,
            "weekly_ig_quota_used": weekly_usage,
            "quota_remaining": 10000 - weekly_usage,
            "pairs_cached": pairs_cached
        }

    def clear_old_data(self, days_to_keep: int = 30):
        """Remove candles older than specified days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())

        cursor.execute("DELETE FROM candles WHERE timestamp < ?", (cutoff,))
        cursor.execute("DELETE FROM quota_usage WHERE timestamp < ?", (cutoff,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        print(f"🗑️  Removed {deleted} candles older than {days_to_keep} days")


# Test the cache manager
if __name__ == "__main__":
    print("="*80)
    print("IG CACHE MANAGER TEST")
    print("="*80)

    cache = IGCacheManager("test_ig_cache.db")

    # Simulate storing some data
    test_data = pd.DataFrame({
        'time': pd.date_range(start='2025-10-28 10:00', periods=10, freq='5min'),
        'open': [1.1000 + i*0.0001 for i in range(10)],
        'high': [1.1005 + i*0.0001 for i in range(10)],
        'low': [1.0995 + i*0.0001 for i in range(10)],
        'close': [1.1002 + i*0.0001 for i in range(10)],
        'volume': [1000 + i*100 for i in range(10)]
    })

    cache.store_candles("EUR_USD", "5", test_data, source="ig")

    # Retrieve
    cached = cache.get_cached_candles("EUR_USD", "5", count=5)
    print(f"\n✅ Retrieved {len(cached)} cached candles:")
    print(cached)

    # Stats
    stats = cache.get_cache_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"   Total candles: {stats['total_candles']}")
    print(f"   IG quota used (7 days): {stats['weekly_ig_quota_used']}")
    print(f"   Quota remaining: {stats['quota_remaining']}")
    print(f"   Pairs cached: {stats['pairs_cached']}")

    print(f"\n✅ Cache manager test complete!")
