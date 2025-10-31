"""
Historical Data Backfill Script

One-time script to populate database with initial 200 candles per pair.
Uses IG REST API but splits into batches to stay within quota:

Batch 1: 23 pairs × 200 candles × 2 TF = 9,200 points (Week 1)
Batch 2: 5 pairs × 200 candles × 2 TF = 2,000 points (Week 2 or later)

After backfill complete, switch to WebSocket for unlimited streaming.
"""

import time
from datetime import datetime
from forex_config import ForexConfig
from ig_data_fetcher import IGDataFetcher
from forex_database import ForexDatabase


# Split 28 pairs into batches to stay under quota
BATCH_1_PAIRS = [
    'EUR_USD', 'GBP_USD', 'USD_JPY', 'USD_CHF', 'AUD_USD',
    'NZD_USD', 'USD_CAD', 'EUR_GBP', 'EUR_JPY', 'EUR_CHF',
    'EUR_AUD', 'EUR_CAD', 'EUR_NZD', 'GBP_JPY', 'GBP_CHF',
    'GBP_AUD', 'AUD_JPY', 'AUD_NZD', 'NZD_JPY', 'CHF_JPY',
    'CAD_JPY', 'GBP_CAD', 'GBP_NZD'
]  # 23 pairs × 400 points = 9,200 points

BATCH_2_PAIRS = [
    'AUD_CAD', 'AUD_CHF', 'CAD_CHF', 'EUR_PLN', 'USD_MXN'
]  # 5 pairs × 400 points = 2,000 points

CANDLES_TO_FETCH = 200  # For MA-200 support
TIMEFRAMES = ['5', '15']


def backfill_batch(pairs: list, batch_name: str):
    """
    Backfill historical data for a batch of pairs.

    Args:
        pairs: List of currency pairs to fetch
        batch_name: Name for logging (e.g., "Batch 1")
    """
    print("=" * 80)
    print(f"HISTORICAL DATA BACKFILL - {batch_name}")
    print("=" * 80)
    print(f"\nPairs in this batch: {len(pairs)}")
    print(f"Candles per pair: {CANDLES_TO_FETCH}")
    print(f"Timeframes: {TIMEFRAMES}")

    expected_quota = len(pairs) * CANDLES_TO_FETCH * len(TIMEFRAMES)
    print(f"\n📊 Expected quota usage: {expected_quota:,} points")
    print(f"   Safe limit: 9,500 points")

    if expected_quota > 9500:
        print(f"\n⚠️  WARNING: This batch exceeds safe quota limit!")
        print(f"   Consider reducing pairs or candles.")
        response = input("\nContinue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Backfill cancelled.")
            return

    # Initialize
    print(f"\n🔧 Initializing IG data fetcher...")
    ig_fetcher = IGDataFetcher(
        api_key=ForexConfig.IG_API_KEY,
        username=ForexConfig.IG_USERNAME,
        password=ForexConfig.IG_PASSWORD,
        use_cache=False  # Go straight to database
    )

    print(f"🔧 Initializing database...")
    db = ForexDatabase()

    total_candles = 0
    quota_used = 0
    failed_pairs = []

    print(f"\n📥 Starting backfill at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)

    for i, pair in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] Processing {pair}...")

        for tf in TIMEFRAMES:
            try:
                # Fetch historical data
                print(f"   📥 Fetching {tf}m data ({CANDLES_TO_FETCH} candles)...", end=" ", flush=True)

                df = ig_fetcher.get_candles(pair, tf, count=CANDLES_TO_FETCH)

                # Store in database
                db.store_candles(pair, tf, df, source='ig_rest_backfill')

                candles_stored = len(df)
                total_candles += candles_stored
                quota_used += candles_stored

                print(f"✅ {candles_stored} candles stored")

                # Rate limiting (2 sec per request per IG requirements)
                time.sleep(2)

            except Exception as e:
                print(f"❌ Error: {e}")
                failed_pairs.append(f"{pair} {tf}m")
                continue

        # Progress update every 5 pairs
        if i % 5 == 0:
            print(f"\n   Progress: {i}/{len(pairs)} pairs completed")
            print(f"   Quota used so far: {quota_used:,}/10,000 ({quota_used/100:.1f}%)")

    # Summary
    print("\n" + "=" * 80)
    print(f"{batch_name} COMPLETE!")
    print("=" * 80)
    print(f"   Total candles stored: {total_candles:,}")
    print(f"   Quota used: {quota_used:,}/10,000 ({quota_used/100:.1f}%)")
    print(f"   Quota remaining: {10000 - quota_used:,}")

    if failed_pairs:
        print(f"\n⚠️  Failed to fetch {len(failed_pairs)} pair/timeframe combinations:")
        for fp in failed_pairs:
            print(f"   - {fp}")
        print(f"\n   Retry these manually if needed.")
    else:
        print(f"\n✅ All pairs fetched successfully!")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


def show_status():
    """Show current database status."""
    print("\n" + "=" * 80)
    print("DATABASE STATUS")
    print("=" * 80)

    db = ForexDatabase()
    stats = db.get_statistics()

    print(f"\n📊 Current Statistics:")
    print(f"   Total candles in database: {stats['total_candles']:,}")
    print(f"   Unique pairs: {stats['unique_pairs']}")
    print(f"   Timeframes: {stats['timeframes']}")
    print(f"   Date range: {stats['oldest_candle']} to {stats['newest_candle']}")
    print(f"   Data sources: {stats['sources']}")

    print(f"\n📝 Pairs in database:")
    for pair, count in sorted(stats['pairs_count'].items()):
        print(f"   {pair}: {count:,} candles")

    print("=" * 80)


def main():
    """Main backfill orchestrator."""
    print("\n" + "=" * 80)
    print("FOREX HISTORICAL DATA BACKFILL")
    print("=" * 80)
    print(f"\nThis script will fetch historical data in batches:")
    print(f"\n   Batch 1: {len(BATCH_1_PAIRS)} pairs × {CANDLES_TO_FETCH} candles × {len(TIMEFRAMES)} TF")
    print(f"            = {len(BATCH_1_PAIRS) * CANDLES_TO_FETCH * len(TIMEFRAMES):,} quota points")
    print(f"\n   Batch 2: {len(BATCH_2_PAIRS)} pairs × {CANDLES_TO_FETCH} candles × {len(TIMEFRAMES)} TF")
    print(f"            = {len(BATCH_2_PAIRS) * CANDLES_TO_FETCH * len(TIMEFRAMES):,} quota points")
    print(f"\n   Total: {(len(BATCH_1_PAIRS) + len(BATCH_2_PAIRS)) * CANDLES_TO_FETCH * len(TIMEFRAMES):,} quota points")
    print(f"\n⚠️  Note: Run Batch 2 in a different week to avoid quota exhaustion")

    print("\n" + "=" * 80)
    print("OPTIONS:")
    print("=" * 80)
    print("1. Run Batch 1 (23 pairs, 9,200 quota)")
    print("2. Run Batch 2 (5 pairs, 2,000 quota)")
    print("3. Run both batches (⚠️  uses 11,200 quota - exceeds weekly limit!)")
    print("4. Show database status")
    print("5. Exit")

    choice = input("\nSelect option (1-5): ").strip()

    if choice == '1':
        print("\n🚀 Starting Batch 1...")
        backfill_batch(BATCH_1_PAIRS, "Batch 1")
        show_status()

    elif choice == '2':
        print("\n🚀 Starting Batch 2...")
        backfill_batch(BATCH_2_PAIRS, "Batch 2")
        show_status()

    elif choice == '3':
        print("\n⚠️  WARNING: Running both batches will use 11,200 quota points!")
        print("   This EXCEEDS the 10,000 weekly limit.")
        print("   You may get rate limited or errors.")
        response = input("\nAre you SURE you want to continue? (type YES): ")

        if response == 'YES':
            print("\n🚀 Starting Batch 1...")
            backfill_batch(BATCH_1_PAIRS, "Batch 1")

            print("\n⏸️  Waiting 60 seconds before Batch 2...")
            time.sleep(60)

            print("\n🚀 Starting Batch 2...")
            backfill_batch(BATCH_2_PAIRS, "Batch 2")

            show_status()
        else:
            print("❌ Cancelled.")

    elif choice == '4':
        show_status()

    elif choice == '5':
        print("\n👋 Exiting...")
        return

    else:
        print("❌ Invalid option.")
        return

    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("\nOnce all batches are complete:")
    print("1. Start WebSocket collector: python websocket_collector.py")
    print("2. WebSocket will maintain data with NO quota usage")
    print("3. Run trading bot: python ig_concurrent_worker.py")
    print("\n✅ System will then run indefinitely with real-time data!")
    print("=" * 80)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    main()
