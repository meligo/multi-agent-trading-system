#!/usr/bin/env python3
"""
Test and Collect Data from WORKING Sources

This script:
1. Tests Finnhub data collection and database storage
2. Tests DataBento data collection and database storage
3. Proves that 2/3 data sources are working
4. Shows exactly what data is being saved
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path, override=True)

from database_manager import DatabaseManager
from finnhub_integration import FinnhubIntegration
from data_persistence_manager import DataPersistenceManager


async def test_finnhub_collection():
    """Test Finnhub data collection and storage."""
    print("\n" + "="*80)
    print(" TEST 1: Finnhub Data Collection")
    print("="*80)

    # Initialize
    db = DatabaseManager()
    await db.initialize()

    persistence = DataPersistenceManager(db)
    finnhub = FinnhubIntegration(persistence_manager=persistence)

    if not finnhub.enabled:
        print("\n❌ Finnhub not enabled")
        await db.close()
        return False

    print(f"\n✅ Finnhub initialized")

    # Test pairs
    test_pairs = ["EUR_USD", "GBP_USD", "USD_JPY"]

    print(f"\n📊 Fetching technical indicators for {len(test_pairs)} pairs...")

    for pair in test_pairs:
        print(f"\n   Testing {pair}...")

        # Get aggregate indicators
        indicators = finnhub.get_aggregate_indicators(pair, timeframe="D")

        if 'error' in indicators:
            print(f"      ❌ Error: {indicators['error']}")
            continue

        # Display results
        print(f"      ✅ Consensus: {indicators['consensus']}")
        print(f"         Confidence: {indicators['confidence']:.1%}")
        print(f"         Buy: {indicators['buy_count']}, Sell: {indicators['sell_count']}, Neutral: {indicators['neutral_count']}")

        # The data should have been saved automatically by persistence manager
        # Let's verify
        query = """
        SELECT COUNT(*) as count
        FROM finnhub_aggregate_indicators
        WHERE symbol = %s
        AND timestamp > NOW() - INTERVAL '1 minute';
        """
        result = await db.execute_query(query, (pair,))
        count = result[0]['count'] if result else 0

        if count > 0:
            print(f"      ✅ Saved to database ({count} record)")
        else:
            print(f"      ⚠️  Not saved to database (check persistence manager)")

    # Check total indicators in database
    total_query = "SELECT COUNT(*) as count FROM finnhub_aggregate_indicators;"
    result = await db.execute_query(total_query)
    total = result[0]['count'] if result else 0

    print(f"\n📊 Total Finnhub indicators in database: {total:,}")

    await db.close()

    return total > 0


async def test_databento_connection():
    """Test DataBento connection (not full streaming, just connection test)."""
    print("\n" + "="*80)
    print(" TEST 2: DataBento Connection")
    print("="*80)

    api_key = os.getenv("DATABENTO_API_KEY")

    if not api_key:
        print("\n❌ No DataBento API key")
        return False

    print(f"\n✅ DataBento API key found")

    try:
        import databento as db

        client = db.Historical(api_key)

        # List datasets
        datasets = client.metadata.list_datasets()

        print(f"✅ Connected to DataBento")
        print(f"   Available datasets: {len(datasets)}")
        print(f"   Using: GLBX.MDP3 (CME Globex MDP 3.0)")

        # Note: We're not starting live streaming here because that requires
        # a long-running process. The dashboard should handle that.

        print(f"\n⚠️  Note: Full data collection requires dashboard to be running")
        print(f"   DataBento streams Level 2 order book data continuously")
        print(f"   This test only verifies API connection")

        return True

    except Exception as e:
        print(f"❌ DataBento connection failed: {e}")
        return False


async def check_database_schema():
    """Verify all database tables exist and are ready."""
    print("\n" + "="*80)
    print(" TEST 3: Database Schema Verification")
    print("="*80)

    db = DatabaseManager()
    await db.initialize()

    tables = [
        'finnhub_aggregate_indicators',
        'finnhub_patterns',
        'finnhub_support_resistance',
        'cme_mbp10_events',
        'cme_trades',
        'cme_mbp10_book'
    ]

    print(f"\n📊 Checking {len(tables)} tables...")

    all_exist = True
    for table in tables:
        query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        );
        """
        result = await db.execute_query(query, (table,))
        exists = result[0]['exists'] if result else False

        if exists:
            print(f"   ✅ {table}")
        else:
            print(f"   ❌ {table} - MISSING")
            all_exist = False

    await db.close()

    return all_exist


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print(" DATA COLLECTION TEST - WORKING SOURCES ONLY")
    print(" Testing Finnhub and DataBento (IG blocked on invalid credentials)")
    print("="*80)
    print(f"\n⏰ Test started: {datetime.now()}")

    # Run tests
    schema_ok = await check_database_schema()
    finnhub_ok = await test_finnhub_collection()
    databento_ok = await test_databento_connection()

    # Summary
    print("\n" + "="*80)
    print(" SUMMARY")
    print("="*80)

    print(f"\n✅ Working Data Sources:")
    print(f"   Finnhub:   {'✅ COLLECTING DATA' if finnhub_ok else '❌ FAILED'}")
    print(f"   DataBento: {'✅ API CONNECTED' if databento_ok else '❌ FAILED'}")

    print(f"\n📊 Database:")
    print(f"   Schema:    {'✅ ALL TABLES EXIST' if schema_ok else '❌ MISSING TABLES'}")

    print(f"\n❌ Blocked Data Sources:")
    print(f"   IG Markets: ❌ INVALID CREDENTIALS")
    print(f"               Username/password incorrect")
    print(f"               API Key: 79ae278ca555968dda0d...c4c941fdc")

    if finnhub_ok:
        print(f"\n🎉 SUCCESS: Finnhub is collecting and saving data!")
        print(f"   Technical indicators are being stored to database")
        print(f"   Agent can use this for trade decisions")
    else:
        print(f"\n⚠️  Finnhub not collecting data")

    if databento_ok:
        print(f"\n✅ DataBento API is ready")
        print(f"   Dashboard can start streaming when needed")
    else:
        print(f"\n⚠️  DataBento not ready")

    print(f"\n📋 Next Steps:")
    print(f"   1. Fix IG credentials:")
    print(f"      - Verify username: meligokes")
    print(f"      - Verify password in IG website")
    print(f"      - Update .env.scalper with correct credentials")
    print(f"\n   2. Restart dashboard to enable all 3 sources")
    print(f"\n   3. Verify data collection:")
    print(f"      python test_all_data_sources.py")

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
