#!/usr/bin/env python3
"""
Comprehensive Data Collection Test

Tests the complete data pipeline:
1. Database has historical candles
2. DataHub warm-starts successfully
3. DataHub can receive updates
4. UnifiedDataFetcher retrieves data correctly
"""

import asyncio
import logging
import sys
from datetime import datetime
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_database_has_candles():
    """Test 1: Check if database has historical candle data."""
    print("\n" + "="*80)
    print("TEST 1: Database Historical Candles")
    print("="*80)

    from database import DatabaseManager
    from scalping_config import ScalpingConfig

    db = DatabaseManager()
    await db.initialize()

    results = {}

    for pair in ScalpingConfig.SCALPING_PAIRS:
        query = """
        SELECT COUNT(*) as count,
               MIN(timestamp) as earliest,
               MAX(timestamp) as latest
        FROM ig_candles
        WHERE symbol = %s AND timeframe = '1'
        """

        result = await db.execute_query(query, (pair,))

        if result and result[0]['count'] > 0:
            count = result[0]['count']
            earliest = result[0]['earliest']
            latest = result[0]['latest']
            results[pair] = {
                'count': count,
                'earliest': earliest,
                'latest': latest,
                'has_data': True
            }
            print(f"✅ {pair}: {count} candles (from {earliest} to {latest})")
        else:
            results[pair] = {'has_data': False, 'count': 0}
            print(f"❌ {pair}: NO CANDLES IN DATABASE")

    await db.close()

    all_have_data = all(r['has_data'] for r in results.values())

    if all_have_data:
        print("\n✅ All pairs have historical data!")
        return True, results
    else:
        print("\n❌ Some pairs missing historical data - warm-start will fail for those pairs")
        return False, results


def test_datahub_warm_start():
    """Test 2: Verify DataHub warm-start works."""
    print("\n" + "="*80)
    print("TEST 2: DataHub Warm-Start")
    print("="*80)

    from data_hub import DataHub
    from market_data_models import Candle
    from datetime import datetime, timedelta

    hub = DataHub(max_candles=100)

    # Create test candles
    test_symbol = 'EUR_USD'
    test_candles = []

    base_time = datetime.utcnow()
    base_price = 1.0500

    for i in range(10):
        candle = Candle(
            symbol=test_symbol,
            timestamp=base_time - timedelta(minutes=10-i),
            open=base_price + i*0.0001,
            high=base_price + i*0.0001 + 0.0005,
            low=base_price + i*0.0001 - 0.0003,
            close=base_price + i*0.0001 + 0.0002,
            volume=1000.0
        )
        test_candles.append(candle)

    # Warm-start
    count = hub.warm_start_candles(test_symbol, test_candles)
    print(f"✅ Warm-started {count} candles")

    # Verify retrieval
    retrieved = hub.get_latest_candles(test_symbol, limit=20)
    print(f"✅ Retrieved {len(retrieved)} candles from DataHub")

    if len(retrieved) == 10:
        print(f"✅ Candle count matches!")

        # Check order (should be oldest to newest)
        if retrieved[0].timestamp < retrieved[-1].timestamp:
            print(f"✅ Candles in correct order (oldest → newest)")
        else:
            print(f"❌ Candles in wrong order")
            return False

        return True
    else:
        print(f"❌ Expected 10 candles, got {len(retrieved)}")
        return False


def test_datahub_live_updates():
    """Test 3: Verify DataHub can receive live updates."""
    print("\n" + "="*80)
    print("TEST 3: DataHub Live Updates")
    print("="*80)

    from data_hub import DataHub
    from market_data_models import Tick, Candle
    from datetime import datetime
    import time

    hub = DataHub(max_candles=100)

    # Test tick update
    tick = Tick(
        symbol='GBP_USD',
        bid=1.2500,
        ask=1.2510,
        mid=1.2505,
        spread=1.0,
        timestamp=datetime.utcnow()
    )
    hub.update_tick(tick)
    print(f"✅ Tick update sent")

    # Retrieve tick
    retrieved_tick = hub.get_latest_tick('GBP_USD')
    if retrieved_tick and retrieved_tick.bid == 1.2500:
        print(f"✅ Tick retrieved: bid={retrieved_tick.bid}, ask={retrieved_tick.ask}")
    else:
        print(f"❌ Tick retrieval failed")
        return False

    # Test candle update
    candle = Candle(
        symbol='GBP_USD',
        timestamp=datetime.utcnow(),
        open=1.2500,
        high=1.2520,
        low=1.2495,
        close=1.2510,
        volume=1000.0
    )
    hub.update_candle_1m(candle)
    print(f"✅ Candle update sent")

    # Retrieve candle
    retrieved_candles = hub.get_latest_candles('GBP_USD', limit=1)
    if retrieved_candles and len(retrieved_candles) == 1:
        print(f"✅ Candle retrieved: close={retrieved_candles[0].close}")
    else:
        print(f"❌ Candle retrieval failed")
        return False

    # Check status
    status = hub.get_status()
    print(f"\n📊 DataHub Status:")
    print(f"   Symbols: {status['symbols_tracked']}")
    print(f"   Stats: {status['stats']}")

    return True


async def test_unified_fetcher_with_datahub():
    """Test 4: Verify UnifiedDataFetcher works with DataHub."""
    print("\n" + "="*80)
    print("TEST 4: UnifiedDataFetcher with DataHub")
    print("="*80)

    from data_hub import DataHub
    from unified_data_fetcher import UnifiedDataFetcher
    from market_data_models import Tick, Candle
    from database import DatabaseManager
    from datetime import datetime, timedelta

    # Initialize components
    hub = DataHub(max_candles=100)
    db = DatabaseManager()
    await db.initialize()

    fetcher = UnifiedDataFetcher(data_hub=hub)
    fetcher.inject_sources(
        data_hub=hub,
        db=db,
        finnhub_integration=None,
        finnhub_fetcher=None,
        insightsentry=None
    )

    # Populate DataHub with test data
    test_symbol = 'EUR_USD'

    # Add tick
    tick = Tick(
        symbol=test_symbol,
        bid=1.0500,
        ask=1.0510,
        mid=1.0505,
        spread=1.0,
        timestamp=datetime.utcnow()
    )
    hub.update_tick(tick)

    # Add candles
    for i in range(50):
        candle = Candle(
            symbol=test_symbol,
            timestamp=datetime.utcnow() - timedelta(minutes=50-i),
            open=1.0500 + i*0.0001,
            high=1.0520 + i*0.0001,
            low=1.0495 + i*0.0001,
            close=1.0510 + i*0.0001,
            volume=1000.0
        )
        hub.update_candle_1m(candle)

    print(f"✅ Populated DataHub with 1 tick and 50 candles")

    # Test fetcher
    result = await fetcher.fetch_all_data(test_symbol, timeframe='1', bars=50)

    if result:
        candles_df = result.get('candles')
        spread = result.get('spread')

        if candles_df is not None and not candles_df.empty:
            print(f"✅ Fetcher retrieved {len(candles_df)} candles from DataHub")
            print(f"   Latest close: {candles_df.iloc[-1]['close']}")
        else:
            print(f"❌ No candles retrieved")
            await db.close()
            return False

        if spread is not None:
            print(f"✅ Fetcher retrieved spread: {spread} pips")
        else:
            print(f"⚠️  No spread retrieved (might use database fallback)")

        await db.close()
        return True
    else:
        print(f"❌ Fetcher returned no data")
        await db.close()
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print(" Data Collection Test Suite")
    print("="*80)

    results = []

    # Test 1: Database
    try:
        db_passed, db_results = await test_database_has_candles()
        results.append(("Database Candles", db_passed))
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        results.append(("Database Candles", False))

    # Test 2: DataHub Warm-Start
    try:
        warmstart_passed = test_datahub_warm_start()
        results.append(("DataHub Warm-Start", warmstart_passed))
    except Exception as e:
        print(f"❌ DataHub warm-start test failed: {e}")
        results.append(("DataHub Warm-Start", False))

    # Test 3: DataHub Live Updates
    try:
        live_passed = test_datahub_live_updates()
        results.append(("DataHub Live Updates", live_passed))
    except Exception as e:
        print(f"❌ DataHub live updates test failed: {e}")
        results.append(("DataHub Live Updates", False))

    # Test 4: UnifiedDataFetcher
    try:
        fetcher_passed = await test_unified_fetcher_with_datahub()
        results.append(("UnifiedDataFetcher", fetcher_passed))
    except Exception as e:
        print(f"❌ UnifiedDataFetcher test failed: {e}")
        results.append(("UnifiedDataFetcher", False))

    # Summary
    print("\n" + "="*80)
    print(" Test Results Summary")
    print("="*80)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:8} {name}")

    all_passed = all(result[1] for result in results)
    print("="*80)

    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ Data collection system is fully operational!")
        print("\n📌 Next Steps:")
        print("   1. Restart dashboard: streamlit run scalping_dashboard.py")
        print("   2. Watch for warm-start logs")
        print("   3. Click 'Force Start' on engine")
        print("   4. Verify candles=True in engine logs")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("\n⚠️  Issues Found:")
        for name, passed in results:
            if not passed:
                print(f"   • {name}")

        print("\n📌 Troubleshooting:")
        if not results[0][1]:  # Database test failed
            print("   • Run WebSocket collector first to populate database")
            print("   • Or import historical data")
        if not results[3][1]:  # Fetcher test failed
            print("   • Check UnifiedDataFetcher DataHub integration")
            print("   • Verify database fallback works")

        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
