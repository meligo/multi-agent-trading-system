#!/usr/bin/env python3
"""
WebSocket Status Checker

Checks if IG WebSocket is actually receiving data.
"""

import asyncio
import sys
from datetime import datetime
from database_manager import DatabaseManager

async def check_websocket_status():
    """Check if WebSocket is receiving and storing data."""
    print("\n" + "="*80)
    print(" WebSocket Data Collection Status")
    print("="*80)

    db = DatabaseManager()
    await db.initialize()

    # Check ig_spot_ticks (raw ticks from WebSocket)
    print("\n1. Checking IG Spot Ticks (raw WebSocket data)...")
    query1 = """
    SELECT
        i.provider_symbol,
        COUNT(*) as tick_count,
        MAX(t.provider_event_ts) as latest_tick,
        MIN(t.provider_event_ts) as earliest_tick
    FROM ig_spot_ticks t
    JOIN instruments i ON t.instrument_id = i.instrument_id
    WHERE i.provider = 'IG'
    GROUP BY i.provider_symbol
    ORDER BY tick_count DESC;
    """

    ticks = await db.execute_query(query1)

    if ticks:
        print(f"\n✅ WebSocket IS receiving ticks!")
        for row in ticks:
            print(f"   {row['provider_symbol']:10} {row['tick_count']:8} ticks  (last: {row['latest_tick']})")
    else:
        print(f"\n❌ NO TICKS in ig_spot_ticks table")
        print(f"   WebSocket is NOT receiving data from IG Markets")

    # Check ig_candles (aggregated 1-minute candles)
    print("\n2. Checking IG Candles (1-minute aggregated)...")
    query2 = """
    SELECT
        i.provider_symbol,
        COUNT(*) as candle_count,
        MAX(c.provider_event_ts) as latest_candle,
        MIN(c.provider_event_ts) as earliest_candle
    FROM ig_candles c
    JOIN instruments i ON c.instrument_id = i.instrument_id
    WHERE i.provider = 'IG' AND c.timeframe = '1'
    GROUP BY i.provider_symbol
    ORDER BY candle_count DESC;
    """

    candles = await db.execute_query(query2)

    if candles:
        print(f"\n✅ IG Candles exist!")
        for row in candles:
            print(f"   {row['provider_symbol']:10} {row['candle_count']:8} candles  (last: {row['latest_candle']})")
    else:
        print(f"\n❌ NO CANDLES in ig_candles table")
        print(f"   Either WebSocket not running or not aggregating ticks")

    # Check instruments table
    print("\n3. Checking Instruments Configuration...")
    query3 = """
    SELECT provider, provider_symbol, asset_class, active
    FROM instruments
    WHERE provider = 'IG'
    ORDER BY provider_symbol;
    """

    instruments = await db.execute_query(query3)

    if instruments:
        print(f"\n✅ IG Instruments configured:")
        for row in instruments:
            status = "✅" if row['active'] else "❌"
            print(f"   {status} {row['provider_symbol']:10} ({row['asset_class']})")
    else:
        print(f"\n❌ NO IG instruments configured!")

    await db.close()

    # Summary
    print("\n" + "="*80)
    print(" Summary")
    print("="*80)

    has_ticks = bool(ticks)
    has_candles = bool(candles)
    has_instruments = bool(instruments)

    if has_ticks and has_candles:
        print("\n✅ WebSocket is WORKING - receiving and aggregating data")
        print("   DataHub warm-start should work on next restart")
    elif has_ticks and not has_candles:
        print("\n⚠️  WebSocket receiving ticks but NOT aggregating to candles")
        print("   Check candle aggregation logic in websocket_collector.py")
    elif not has_ticks and has_instruments:
        print("\n❌ WebSocket NOT receiving data from IG Markets")
        print("\n   Possible causes:")
        print("   1. Markets are CLOSED (Forex closed on weekends)")
        print("   2. IG API credentials not configured")
        print("   3. WebSocket not actually connected to IG streaming")
        print("\n   Check:")
        print("   - Current time vs market hours (Forex: Sun 5pm EST - Fri 5pm EST)")
        print("   - Environment variables: IG_API_KEY, IG_USERNAME, IG_PASSWORD")
        print("   - WebSocket connection logs for errors")
    elif not has_instruments:
        print("\n❌ IG Instruments not configured in database")
        print("   Run database schema setup first")

    # Check current time vs market hours
    from scalping_config import market_hours
    market_status = market_hours.get_market_status()

    print("\n" + "="*80)
    print(f" Market Status: {'OPEN' if market_status['is_open'] else 'CLOSED'}")
    print("="*80)

    if not market_status['is_open']:
        print(f"\n⚠️  Forex markets are currently CLOSED")
        print(f"   Next open: {market_status['next_open']}")
        print(f"   Time until: {market_status['time_until_open_human']}")
        print(f"\n   This is why WebSocket has no data to stream!")
    else:
        print(f"\n✅ Markets are OPEN - WebSocket should be streaming")
        if not has_ticks:
            print(f"   But no ticks received - check IG credentials/connection")

if __name__ == "__main__":
    asyncio.run(check_websocket_status())
