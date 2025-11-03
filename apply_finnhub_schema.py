"""
Apply Finnhub Database Schema
Adds Finnhub tables to the existing PostgreSQL database
"""

import asyncio
import sys
from pathlib import Path
from database_manager import DatabaseManager

async def apply_schema():
    """Apply Finnhub schema to database."""
    print("="*80)
    print("APPLYING FINNHUB SCHEMA TO DATABASE")
    print("="*80)

    # Read schema file
    schema_path = Path(__file__).parent / "finnhub_database_schema.sql"
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        sys.exit(1)

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    print(f"\n📄 Read schema file: {schema_path}")
    print(f"   Schema size: {len(schema_sql)} bytes")

    # Connect to database
    db = DatabaseManager()
    try:
        await db.initialize()
        print("\n✅ Connected to database")

        # Execute schema
        print("\n🔨 Applying schema...")

        try:
            # Execute entire schema as one block
            await db.execute_command(schema_sql)
            print("   ✅ Schema executed successfully")
        except Exception as e:
            print(f"   ⚠️  Error executing schema: {e}")
            # Try executing with psycopg2 raw execution
            print("\n   Trying raw SQL execution...")
            try:
                conn = await db.pool.getconn()
                async with conn.cursor() as cur:
                    await cur.execute(schema_sql)
                await db.pool.putconn(conn)
                print("   ✅ Raw SQL execution successful")
            except Exception as e2:
                print(f"   ❌  Raw SQL execution also failed: {e2}")

        print("\n✅ Schema applied successfully!")

        # Verify tables were created
        print("\n🔍 Verifying Finnhub tables...")
        tables = [
            'finnhub_aggregate_indicators',
            'finnhub_patterns',
            'finnhub_support_resistance',
            'finnhub_candles'
        ]

        for table in tables:
            try:
                result = await db.execute_query(
                    f"SELECT COUNT(*) as count FROM {table}"
                )
                count = result[0]['count'] if result else 0
                print(f"   ✅ {table}: {count} rows")
            except Exception as e:
                print(f"   ❌ {table}: {e}")

        print("\n" + "="*80)
        print("✅ FINNHUB SCHEMA APPLIED SUCCESSFULLY")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Failed to apply schema: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await db.close()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(apply_schema())
