#!/usr/bin/env python3
"""
Quick Database Candle Check

Checks if ig_candles table has historical data for warm-start.
"""

import asyncio
import sys
from database import DatabaseManager
from scalping_config import ScalpingConfig


async def check_candles():
    """Check if database has candles for each pair."""
    print("\n" + "="*80)
    print(" Database Candle Check")
    print("="*80)
    print("\nChecking ig_candles table for historical data...\n")

    db = DatabaseManager()
    await db.initialize()

    all_pairs_have_data = True

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
            print(f"✅ {pair:10} {count:6} candles  ({earliest} → {latest})")
        else:
            print(f"❌ {pair:10} NO DATA IN DATABASE")
            all_pairs_have_data = False

    await db.close()

    print("\n" + "="*80)

    if all_pairs_have_data:
        print("✅ ALL PAIRS HAVE HISTORICAL DATA")
        print("\n📌 DataHub warm-start will work correctly!")
        print("   Run: ./quick_fix_test.sh")
        return 0
    else:
        print("⚠️  SOME PAIRS MISSING HISTORICAL DATA")
        print("\n📌 Warm-start will skip pairs without data.")
        print("   Options:")
        print("   1. Run WebSocket for 5-10 minutes to populate database")
        print("   2. Continue anyway - system will use live data only")
        print("\n   Then run: ./quick_fix_test.sh")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(check_candles()))
