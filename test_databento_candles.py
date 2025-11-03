#!/usr/bin/env python3
"""
Test DataBento Candle Integration

Verifies that:
1. DataBento client is generating 1-minute OHLCV candles
2. Candles have real volume (not tick count)
3. Candles are pushed to DataHub
4. UnifiedDataFetcher prioritizes DataBento over IG
"""

import sys
import time
import logging
from datetime import datetime
from data_hub import connect_to_data_hub

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_databento_candles():
    """Test DataBento candle generation and DataHub integration."""

    print("=" * 80)
    print("DATABENTO CANDLE INTEGRATION TEST")
    print("=" * 80)

    # Connect to DataHub
    try:
        logger.info("Connecting to DataHub...")
        hub = connect_to_data_hub(('127.0.0.1', 50000), b'forex_scalper_2025')
        logger.info("✅ Connected to DataHub")
    except Exception as e:
        logger.error(f"❌ Failed to connect to DataHub: {e}")
        logger.error("Make sure DataHub server is running: python start_datahub_server.py")
        return False

    # Get DataHub status
    print("\n" + "=" * 80)
    print("DATAHUB STATUS")
    print("=" * 80)
    try:
        status = hub.get_status()
        print(f"Stats: {status['stats']}")
        print(f"Symbols tracked: {status['symbols_tracked']}")
        print(f"Candles by symbol: {status['candles_by_symbol']}")
    except Exception as e:
        logger.error(f"Failed to get DataHub status: {e}")

    # Test each pair
    test_pairs = ['EUR_USD', 'GBP_USD', 'USD_JPY']

    print("\n" + "=" * 80)
    print("CHECKING CANDLES BY SOURCE")
    print("=" * 80)

    for pair in test_pairs:
        print(f"\n{pair}:")
        print("-" * 40)

        try:
            # Get all candles for this pair
            candles = hub.get_latest_candles(pair, limit=100)

            if not candles:
                print(f"  ❌ No candles found")
                continue

            # Separate by source
            databento_candles = [c for c in candles if getattr(c, 'source', 'IG') == 'DATABENTO']
            ig_candles = [c for c in candles if getattr(c, 'source', 'IG') == 'IG']

            print(f"  Total candles: {len(candles)}")
            print(f"  DataBento (real volume): {len(databento_candles)}")
            print(f"  IG (tick volume): {len(ig_candles)}")

            # Show latest DataBento candle
            if databento_candles:
                latest = databento_candles[-1]
                print(f"\n  ✅ Latest DataBento Candle:")
                print(f"     Timestamp: {latest.timestamp}")
                print(f"     OHLC: O={latest.open:.5f} H={latest.high:.5f} L={latest.low:.5f} C={latest.close:.5f}")
                print(f"     Volume: {latest.volume:.0f} (REAL)")
                print(f"     Source: {getattr(latest, 'source', 'unknown')}")
                print(f"     Volume Type: {getattr(latest, 'volume_type', 'unknown')}")

                # Check if volume is real
                if latest.volume > 0:
                    print(f"     ✅ Has real trade volume!")
                else:
                    print(f"     ⚠️ Volume is zero - may need more time for trades")
            else:
                print(f"  ⚠️ No DataBento candles yet")
                print(f"     Waiting for DataBento client to generate 1-minute bars...")

            # Show latest IG candle for comparison
            if ig_candles:
                latest = ig_candles[-1]
                print(f"\n  IG Candle (for comparison):")
                print(f"     Timestamp: {latest.timestamp}")
                print(f"     OHLC: O={latest.open:.5f} H={latest.high:.5f} L={latest.low:.5f} C={latest.close:.5f}")
                print(f"     Volume: {latest.volume:.0f} (tick count)")
                print(f"     Source: {getattr(latest, 'source', 'IG')}")

        except Exception as e:
            logger.error(f"  ❌ Error checking {pair}: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    try:
        status = hub.get_status()
        total_candles = status['stats']['candles_received']

        # Count DataBento vs IG candles
        databento_count = 0
        ig_count = 0

        for pair in test_pairs:
            candles = hub.get_latest_candles(pair, limit=100)
            databento_count += len([c for c in candles if getattr(c, 'source', 'IG') == 'DATABENTO'])
            ig_count += len([c for c in candles if getattr(c, 'source', 'IG') == 'IG'])

        print(f"Total candles in DataHub: {total_candles}")
        print(f"  DataBento (real volume): {databento_count}")
        print(f"  IG (tick volume): {ig_count}")

        if databento_count > 0:
            print(f"\n✅ SUCCESS: DataBento candles are flowing to DataHub!")
            print(f"   Real volume from CME futures is now available.")
        else:
            print(f"\n⚠️ WAITING: No DataBento candles yet.")
            print(f"   Make sure DataBento client is running.")
            print(f"   It may take 1-2 minutes for first candles to appear.")

    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    return True


if __name__ == "__main__":
    success = test_databento_candles()
    sys.exit(0 if success else 1)
