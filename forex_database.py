"""
Forex Database Module

Stores and retrieves forex candle data.
Supports both SQLite (simple) and PostgreSQL (production).

Use SQLite for development/testing.
Use PostgreSQL + TimescaleDB for production (better for time-series).
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path


class ForexDatabase:
    """
    Database manager for forex historical data.

    Stores OHLCV candles from multiple sources:
    - ig_rest_backfill: Initial historical pull
    - websocket: Real-time streaming data
    - finnhub: Fallback data source
    """

    def __init__(self, db_path: str = "forex_data.db", db_type: str = "sqlite"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file or PostgreSQL connection string
            db_type: 'sqlite' or 'postgresql'
        """
        self.db_path = db_path
        self.db_type = db_type

        if db_type == "sqlite":
            self._init_sqlite()
        elif db_type == "postgresql":
            self._init_postgresql()
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def _init_sqlite(self):
        """Create SQLite tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main candles table
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

        # Indexes for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pair_tf_time
            ON candles(pair, timeframe, timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON candles(timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source
            ON candles(source)
        """)

        conn.commit()
        conn.close()

        print(f"✅ SQLite database initialized: {self.db_path}")

    def _init_postgresql(self):
        """Create PostgreSQL tables with TimescaleDB hypertable."""
        # TODO: Implement PostgreSQL connection
        # For production use, connect to PostgreSQL with TimescaleDB extension
        raise NotImplementedError("PostgreSQL support coming soon. Use SQLite for now.")

    def store_candles(self, pair: str, timeframe: str, df: pd.DataFrame, source: str = 'websocket'):
        """
        Store multiple candles (bulk insert).

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            timeframe: Timeframe in minutes ('5', '15', etc.)
            df: DataFrame with columns: time, open, high, low, close, volume
            source: Data source ('ig_rest_backfill', 'websocket', 'finnhub')
        """
        if df.empty:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Convert timestamps if needed
        if 'time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['time']).astype(int) // 10**9
        elif 'timestamp' not in df.columns:
            raise ValueError("DataFrame must have 'time' or 'timestamp' column")

        created_at = int(datetime.now().timestamp())

        # Insert all candles
        inserted = 0
        duplicates = 0

        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO candles
                    (pair, timeframe, timestamp, open, high, low, close, volume, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pair,
                    timeframe,
                    int(row['timestamp']),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row.get('volume', 0)),
                    source,
                    created_at
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
                continue
            except Exception as e:
                print(f"⚠️  Error storing candle: {e}")
                continue

        conn.commit()
        conn.close()

        if duplicates > 0:
            print(f"   💾 Stored {inserted} candles, skipped {duplicates} duplicates")
        else:
            print(f"   💾 Stored {inserted} candles")

    def store_candle(self, pair: str, timeframe: str, candle: dict, source: str = 'websocket'):
        """
        Store single candle (from WebSocket).

        Args:
            pair: Currency pair
            timeframe: Timeframe in minutes
            candle: Dict with keys: timestamp, open, high, low, close, volume
            source: Data source
        """
        # Convert single candle to DataFrame
        df = pd.DataFrame([candle])
        self.store_candles(pair, timeframe, df, source)

    def get_candles(self, pair: str, timeframe: str, count: int = 100) -> pd.DataFrame:
        """
        Retrieve most recent candles from database.

        Args:
            pair: Currency pair
            timeframe: Timeframe in minutes
            count: Number of most recent candles to return

        Returns:
            DataFrame with columns: time, open, high, low, close, volume

        Raises:
            ValueError: If no data found for pair/timeframe
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

        if df.empty:
            raise ValueError(f"No data in database for {pair} {timeframe}m")

        # Convert timestamp to datetime
        df['time'] = pd.to_datetime(df['timestamp'], unit='s')

        # Sort by time ascending (oldest first)
        df = df.sort_values('timestamp').reset_index(drop=True)

        return df[['time', 'open', 'high', 'low', 'close', 'volume', 'source']]

    def get_latest_timestamp(self, pair: str, timeframe: str) -> Optional[int]:
        """
        Get timestamp of most recent candle for a pair/timeframe.

        Args:
            pair: Currency pair
            timeframe: Timeframe in minutes

        Returns:
            Unix timestamp of latest candle, or None if no data
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT MAX(timestamp)
            FROM candles
            WHERE pair = ? AND timeframe = ?
        """, (pair, timeframe))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result and result[0] else None

    def get_candle_count(self, pair: str, timeframe: str) -> int:
        """Get total number of candles for a pair/timeframe."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM candles
            WHERE pair = ? AND timeframe = ?
        """, (pair, timeframe))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else 0

    def get_statistics(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Dict with database stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total candles
        cursor.execute("SELECT COUNT(*) FROM candles")
        total_candles = cursor.fetchone()[0]

        # Unique pairs
        cursor.execute("SELECT COUNT(DISTINCT pair) FROM candles")
        unique_pairs = cursor.fetchone()[0]

        # Unique timeframes
        cursor.execute("SELECT DISTINCT timeframe FROM candles ORDER BY timeframe")
        timeframes = [row[0] for row in cursor.fetchall()]

        # Date range
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM candles")
        min_ts, max_ts = cursor.fetchone()
        oldest = datetime.fromtimestamp(min_ts).strftime('%Y-%m-%d %H:%M') if min_ts else 'N/A'
        newest = datetime.fromtimestamp(max_ts).strftime('%Y-%m-%d %H:%M') if max_ts else 'N/A'

        # By source
        cursor.execute("SELECT source, COUNT(*) FROM candles GROUP BY source")
        sources = dict(cursor.fetchall())

        # Candles per pair
        cursor.execute("SELECT pair, COUNT(*) FROM candles GROUP BY pair ORDER BY pair")
        pairs_count = dict(cursor.fetchall())

        conn.close()

        return {
            'total_candles': total_candles,
            'unique_pairs': unique_pairs,
            'timeframes': timeframes,
            'oldest_candle': oldest,
            'newest_candle': newest,
            'sources': sources,
            'pairs_count': pairs_count
        }

    def clear_old_data(self, days_to_keep: int = 30):
        """
        Remove candles older than specified days.

        Args:
            days_to_keep: Number of days of history to keep
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = int((datetime.now().timestamp()) - (days_to_keep * 24 * 60 * 60))

        cursor.execute("SELECT COUNT(*) FROM candles WHERE timestamp < ?", (cutoff,))
        to_delete = cursor.fetchone()[0]

        if to_delete == 0:
            print(f"✅ No candles older than {days_to_keep} days")
            conn.close()
            return

        print(f"🗑️  Deleting {to_delete:,} candles older than {days_to_keep} days...")

        cursor.execute("DELETE FROM candles WHERE timestamp < ?", (cutoff,))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        print(f"✅ Removed {deleted:,} old candles")

    def vacuum(self):
        """Optimize database (reclaim space, rebuild indexes)."""
        print("🔧 Optimizing database...")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("VACUUM")
        cursor.execute("ANALYZE")

        conn.commit()
        conn.close()

        print("✅ Database optimized")


# Test/Demo
if __name__ == "__main__":
    print("="*80)
    print("FOREX DATABASE TEST")
    print("="*80)

    # Create database
    db = ForexDatabase("test_forex.db")

    # Simulate storing some data
    test_data = pd.DataFrame({
        'time': pd.date_range(start='2025-01-29 10:00', periods=10, freq='5min'),
        'open': [1.0800 + i*0.0001 for i in range(10)],
        'high': [1.0805 + i*0.0001 for i in range(10)],
        'low': [1.0795 + i*0.0001 for i in range(10)],
        'close': [1.0802 + i*0.0001 for i in range(10)],
        'volume': [1000 + i*100 for i in range(10)]
    })

    print("\n📥 Storing test data...")
    db.store_candles("EUR_USD", "5", test_data, source="test")

    # Retrieve
    print("\n📤 Retrieving data...")
    retrieved = db.get_candles("EUR_USD", "5", count=5)
    print(retrieved)

    # Stats
    print("\n📊 Database Statistics:")
    stats = db.get_statistics()
    print(f"   Total candles: {stats['total_candles']}")
    print(f"   Unique pairs: {stats['unique_pairs']}")
    print(f"   Timeframes: {stats['timeframes']}")
    print(f"   Date range: {stats['oldest_candle']} to {stats['newest_candle']}")

    print("\n✅ Database test complete!")
