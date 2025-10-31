"""
Test IG Cache System - Verify Quota-Efficient Data Fetching

Tests:
1. Initial fetch and cache storage
2. Fresh cache returns (0 quota used)
3. Delta updates (only new candles fetched)
4. Quota tracking and reporting
5. Multiple pairs and timeframes
"""

import pandas as pd
import time
from datetime import datetime
from forex_config import ForexConfig
from ig_data_fetcher import IGDataFetcher

def test_ig_cache_system():
    """Test complete IG cache system."""
    print("=" * 80)
    print("IG CACHE SYSTEM TEST")
    print("=" * 80)
    print()

    # Initialize IG data fetcher with caching enabled
    print("🔧 Initializing IG data fetcher with cache...")
    fetcher = IGDataFetcher(
        api_key=ForexConfig.IG_API_KEY,
        username=ForexConfig.IG_USERNAME,
        password=ForexConfig.IG_PASSWORD,
        use_cache=True
    )
    print()

    # Test 1: Initial fetch (should use quota)
    print("=" * 80)
    print("TEST 1: Initial Fetch (No Cache)")
    print("=" * 80)

    pair = "EUR_USD"
    timeframe = "5"

    print(f"\n📥 Fetching {pair} {timeframe}m candles (first time - will use quota)...")
    try:
        df1 = fetcher.get_candles(pair, timeframe, count=100)
        print(f"✅ Fetched {len(df1)} candles")
        print(f"   Oldest: {df1['time'].iloc[0]}")
        print(f"   Newest: {df1['time'].iloc[-1]}")
        print(f"   Latest close: {df1['close'].iloc[-1]:.5f}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Show cache stats
    if fetcher.use_cache:
        stats = fetcher.cache.get_cache_stats()
        print(f"\n📊 Cache Statistics After Initial Fetch:")
        print(f"   Total candles: {stats['total_candles']}")
        print(f"   Pairs cached: {stats['pairs_cached']}")
        print(f"   IG quota used (7 days): {stats['weekly_ig_quota_used']}")
        print(f"   Quota remaining: {stats['quota_remaining']}")

    # Test 2: Immediate re-fetch (should use cache, 0 quota)
    print("\n" + "=" * 80)
    print("TEST 2: Immediate Re-Fetch (Should Use Cache)")
    print("=" * 80)

    print(f"\n💾 Fetching same data immediately (should use cache - 0 quota)...")
    quota_before = stats['weekly_ig_quota_used']

    try:
        df2 = fetcher.get_candles(pair, timeframe, count=100)
        print(f"✅ Retrieved {len(df2)} candles")
        print(f"   Latest close: {df2['close'].iloc[-1]:.5f}")

        # Check quota usage
        stats = fetcher.cache.get_cache_stats()
        quota_after = stats['weekly_ig_quota_used']
        quota_used = quota_after - quota_before

        if quota_used == 0:
            print(f"\n✅ SUCCESS: 0 quota used (returned from cache)")
        else:
            print(f"\n⚠️  WARNING: {quota_used} quota used (expected 0)")

    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 3: Wait and fetch again (should do delta update)
    print("\n" + "=" * 80)
    print("TEST 3: Delta Update After Wait")
    print("=" * 80)

    print(f"\n⏳ Waiting 6 minutes to trigger delta update...")
    print(f"   (Cache freshness threshold: 5 minutes)")
    print(f"   Simulating by clearing last_update timestamp...")

    # Simulate stale cache by manually setting old timestamp
    if fetcher.use_cache:
        import sqlite3
        conn = sqlite3.connect(fetcher.cache.db_path)
        cursor = conn.cursor()
        # Set last_update to 7 minutes ago
        old_timestamp = int((datetime.now().timestamp()) - (7 * 60))
        cursor.execute("""
            UPDATE metadata
            SET last_update = ?
            WHERE pair = ? AND timeframe = ?
        """, (old_timestamp, pair, timeframe))
        conn.commit()
        conn.close()
        print(f"   ✅ Simulated 7-minute-old cache")

    quota_before = stats['weekly_ig_quota_used']

    print(f"\n🔄 Fetching again (should do delta update - minimal quota)...")
    try:
        df3 = fetcher.get_candles(pair, timeframe, count=100)
        print(f"✅ Retrieved {len(df3)} candles")
        print(f"   Latest close: {df3['close'].iloc[-1]:.5f}")

        # Check quota usage
        stats = fetcher.cache.get_cache_stats()
        quota_after = stats['weekly_ig_quota_used']
        quota_used = quota_after - quota_before

        if quota_used <= 10:
            print(f"\n✅ SUCCESS: Only {quota_used} quota used (delta update)")
        else:
            print(f"\n⚠️  WARNING: {quota_used} quota used (expected <10)")

    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 4: Multiple pairs (test quota accumulation)
    print("\n" + "=" * 80)
    print("TEST 4: Multiple Pairs")
    print("=" * 80)

    test_pairs = ["GBP_USD", "USD_JPY"]
    quota_before = stats['weekly_ig_quota_used']

    print(f"\n📥 Fetching 2 additional pairs...")
    for test_pair in test_pairs:
        try:
            df = fetcher.get_candles(test_pair, timeframe, count=100)
            print(f"   ✅ {test_pair}: {len(df)} candles, close={df['close'].iloc[-1]:.5f}")
        except Exception as e:
            print(f"   ❌ {test_pair}: {e}")

    stats = fetcher.cache.get_cache_stats()
    quota_after = stats['weekly_ig_quota_used']
    quota_used = quota_after - quota_before

    print(f"\n📊 Quota used for 2 new pairs: {quota_used}")
    print(f"   Expected: ~200 (100 candles × 2 pairs)")
    print(f"   Efficiency: {(quota_used / 200) * 100:.1f}% of expected")

    # Final Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    stats = fetcher.cache.get_cache_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"   Total candles cached: {stats['total_candles']}")
    print(f"   Pairs cached: {stats['pairs_cached']}")
    print(f"   By source: {stats['by_source']}")
    print(f"   ")
    print(f"📈 Quota Usage:")
    print(f"   IG quota used (7 days): {stats['weekly_ig_quota_used']:,}")
    print(f"   Quota remaining: {stats['quota_remaining']:,}")
    print(f"   Percentage used: {(stats['weekly_ig_quota_used'] / 10000) * 100:.1f}%")

    # Calculate efficiency
    expected_without_cache = 100 * 4  # 4 pair fetches × 100 candles each
    actual_used = stats['weekly_ig_quota_used']
    efficiency_gain = ((expected_without_cache - actual_used) / expected_without_cache) * 100

    print(f"\n💡 Efficiency Analysis:")
    print(f"   Without cache: {expected_without_cache} quota points")
    print(f"   With cache: {actual_used} quota points")
    print(f"   Efficiency gain: {efficiency_gain:.1f}%")

    print("\n" + "=" * 80)
    print("✅ CACHE SYSTEM TEST COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_ig_cache_system()
