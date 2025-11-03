"""
Migrate SQLite Forex Data to PostgreSQL
Moves all candle data from forex_data.db (SQLite) to PostgreSQL
"""

import sqlite3
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from database_manager import DatabaseManager
from data_persistence_manager import DataPersistenceManager

async def create_ig_candles_table(db: DatabaseManager):
    """Create ig_candles table if it doesn't exist."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS ig_candles (
        provider_event_ts TIMESTAMPTZ NOT NULL,
        recv_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
        timeframe TEXT NOT NULL,
        open DOUBLE PRECISION NOT NULL,
        high DOUBLE PRECISION NOT NULL,
        low DOUBLE PRECISION NOT NULL,
        close DOUBLE PRECISION NOT NULL,
        volume DOUBLE PRECISION,
        source TEXT NOT NULL,
        extras JSONB
    );
    """

    create_hypertable_sql = """
    SELECT create_hypertable('ig_candles', 'provider_event_ts',
        chunk_time_interval => INTERVAL '1 day',
        if_not_exists => TRUE
    );
    """

    create_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_ig_candles_instrument
    ON ig_candles(instrument_id, timeframe, provider_event_ts DESC);
    """

    create_dedupe_index_sql = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ig_candles_dedupe
    ON ig_candles(instrument_id, timeframe, provider_event_ts);
    """

    try:
        await db.execute_command(create_table_sql)
        print("   ✅ Created ig_candles table")
    except Exception as e:
        if "already exists" in str(e):
            print("   ⏭️  ig_candles table already exists")
        else:
            print(f"   ⚠️  Error creating table: {e}")

    try:
        await db.execute_command(create_hypertable_sql)
        print("   ✅ Created hypertable for ig_candles")
    except Exception as e:
        if "already a hypertable" in str(e):
            print("   ⏭️  ig_candles already a hypertable")
        else:
            print(f"   ⚠️  Error creating hypertable: {e}")

    try:
        await db.execute_command(create_index_sql)
        print("   ✅ Created index on ig_candles")
    except Exception as e:
        print(f"   ⚠️  Error creating index: {e}")

    try:
        await db.execute_command(create_dedupe_index_sql)
        print("   ✅ Created dedupe index on ig_candles")
    except Exception as e:
        print(f"   ⚠️  Error creating dedupe index: {e}")


async def migrate_candles():
    """Migrate all candles from SQLite to PostgreSQL."""
    print("="*80)
    print("MIGRATING SQLITE DATA TO POSTGRESQL")
    print("="*80)

    # Check if SQLite database exists
    sqlite_path = Path("forex_data.db")
    if not sqlite_path.exists():
        print("\n⚠️  SQLite database not found: forex_data.db")
        print("   Nothing to migrate.")
        return

    print(f"\n📄 Found SQLite database: {sqlite_path}")

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) as count FROM candles")
    total_count = cursor.fetchone()['count']
    print(f"   Total candles in SQLite: {total_count:,}")

    if total_count == 0:
        print("\n   No data to migrate.")
        sqlite_conn.close()
        return

    # Get data summary
    cursor.execute("""
        SELECT pair, timeframe, source, COUNT(*) as count
        FROM candles
        GROUP BY pair, timeframe, source
        ORDER BY pair, timeframe
    """)
    summary = cursor.fetchall()

    print("\n📊 Data Summary:")
    for row in summary:
        print(f"   {row['pair']} {row['timeframe']}m ({row['source']}): {row['count']:,} candles")

    # Connect to PostgreSQL
    db = DatabaseManager()
    try:
        await db.initialize()
        print("\n✅ Connected to PostgreSQL")

        # Create ig_candles table
        print("\n🔨 Creating ig_candles table...")
        await create_ig_candles_table(db)

        # Migrate data in batches
        print("\n🔄 Migrating data...")
        batch_size = 1000
        offset = 0
        migrated = 0
        errors = 0

        while offset < total_count:
            # Fetch batch from SQLite
            cursor.execute(f"""
                SELECT * FROM candles
                ORDER BY timestamp
                LIMIT {batch_size} OFFSET {offset}
            """)
            batch = cursor.fetchall()

            if not batch:
                break

            # Insert batch into PostgreSQL
            for row in batch:
                try:
                    # Get instrument_id
                    instrument_id = await db.get_instrument_id("IG", row['pair'])
                    if not instrument_id:
                        # Create instrument if doesn't exist
                        await db.execute_command("""
                            INSERT INTO instruments (provider, provider_symbol, asset_class, currency, active)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (provider, provider_symbol, expiry) DO NOTHING
                        """, "IG", row['pair'], "FX_SPOT", row['pair'].split('_')[0], True)
                        instrument_id = await db.get_instrument_id("IG", row['pair'])

                    if instrument_id:
                        # Convert Unix timestamp to datetime
                        candle_time = datetime.fromtimestamp(row['timestamp'])

                        # Insert candle
                        await db.execute_command("""
                            INSERT INTO ig_candles (
                                provider_event_ts, recv_ts, instrument_id, timeframe,
                                open, high, low, close, volume, source
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                            ON CONFLICT (instrument_id, timeframe, provider_event_ts) DO NOTHING
                        """,
                            candle_time,
                            datetime.fromtimestamp(row['created_at']),
                            instrument_id,
                            f"{row['timeframe']}m",
                            row['open'],
                            row['high'],
                            row['low'],
                            row['close'],
                            row['volume'],
                            row['source']
                        )
                        migrated += 1
                except Exception as e:
                    errors += 1
                    if errors <= 5:  # Only print first 5 errors
                        print(f"      ⚠️  Error migrating row: {e}")

            offset += batch_size

            # Progress update
            progress = min(100, (offset / total_count) * 100)
            print(f"   Progress: {migrated:,}/{total_count:,} ({progress:.1f}%)", end='\r')

        print(f"\n\n✅ Migration complete!")
        print(f"   Migrated: {migrated:,} candles")
        print(f"   Errors: {errors:,}")

        # Verify migration
        print("\n🔍 Verifying migration...")
        result = await db.execute_query("SELECT COUNT(*) as count FROM ig_candles")
        pg_count = result[0]['count'] if result else 0
        print(f"   PostgreSQL ig_candles: {pg_count:,} rows")

        # Show sample data
        print("\n📋 Sample migrated data:")
        sample = await db.execute_query("""
            SELECT
                i.provider_symbol,
                c.timeframe,
                c.provider_event_ts,
                c.close,
                c.source
            FROM ig_candles c
            JOIN instruments i ON c.instrument_id = i.instrument_id
            ORDER BY c.provider_event_ts DESC
            LIMIT 5
        """)
        for row in sample:
            print(f"   {row['provider_symbol']} {row['timeframe']} @ {row['provider_event_ts']}: {row['close']:.5f} ({row['source']})")

        print("\n" + "="*80)
        print("✅ MIGRATION COMPLETE")
        print("="*80)
        print("\n💡 The SQLite database (forex_data.db) is still intact.")
        print("   You can delete it after verifying the migration.")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sqlite_conn.close()
        await db.close()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(migrate_candles())
