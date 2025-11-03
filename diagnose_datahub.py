#!/usr/bin/env python3
"""
Comprehensive DataHub Diagnostic

Tests if multiple clients see the same DataHub instance.
"""

import time
from data_hub import start_data_hub_manager, connect_to_data_hub
from market_data_models import Tick, Candle
from datetime import datetime

def main():
    print("=" * 80)
    print("DATAHUB DIAGNOSTIC TEST")
    print("=" * 80)
    print()

    # Step 1: Start DataHub manager
    print("1. Starting DataHub manager...")
    manager = start_data_hub_manager(('127.0.0.1', 50051), b'test_key')
    print("   ✅ Manager started on port 50051")
    print()

    # Step 2: Get DataHub from manager (client 1)
    print("2. Client 1: Getting DataHub proxy...")
    hub1 = manager.DataHub()
    print(f"   ✅ Client 1 hub: {hub1}")
    print(f"   Stats: {hub1.get_status()['stats']}")
    print()

    # Step 3: Push data from client 1
    print("3. Client 1: Pushing test candle...")
    candle = Candle(
        symbol='TEST',
        timestamp=datetime.utcnow(),
        open=1.1,
        high=1.2,
        low=1.0,
        close=1.15,
        volume=100.0
    )
    hub1.update_candle_1m(candle)
    print(f"   ✅ Pushed candle")
    print(f"   Stats after push: {hub1.get_status()['stats']}")
    print()

    # Step 4: Create second client connection
    print("4. Client 2: Connecting to DataHub...")
    hub2 = connect_to_data_hub(('127.0.0.1', 50051), b'test_key')
    print(f"   ✅ Client 2 hub: {hub2}")
    print()

    # Step 5: Read from client 2
    print("5. Client 2: Reading data...")
    stats = hub2.get_status()['stats']
    print(f"   Stats: {stats}")
    candles = hub2.get_latest_candles('TEST', 10)
    print(f"   TEST candles: {len(candles)}")
    print()

    # Step 6: Get DataHub from manager again (client 3)
    print("6. Client 3: Getting DataHub proxy from manager...")
    hub3 = manager.DataHub()
    print(f"   ✅ Client 3 hub: {hub3}")
    stats3 = hub3.get_status()['stats']
    print(f"   Stats: {stats3}")
    candles3 = hub3.get_latest_candles('TEST', 10)
    print(f"   TEST candles: {len(candles3)}")
    print()

    # Results
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    if stats['candles_received'] > 0 and len(candles) > 0 and len(candles3) > 0:
        print("✅ SUCCESS: All clients see the same DataHub instance!")
        print(f"   All clients see {stats['candles_received']} candles")
    else:
        print("❌ FAILURE: Clients see different DataHub instances")
        print(f"   Client 1 stats: candles_received={hub1.get_status()['stats']['candles_received']}")
        print(f"   Client 2 stats: candles_received={stats['candles_received']}, candles={len(candles)}")
        print(f"   Client 3 stats: candles_received={stats3['candles_received']}, candles={len(candles3)}")

    # Cleanup
    manager.shutdown()
    print("\n👋 Test complete")

if __name__ == '__main__':
    main()
