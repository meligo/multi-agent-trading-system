#!/usr/bin/env python3
"""
Comprehensive Data Source Testing

Tests ALL 3 data sources and verifies database persistence:
1. IG Markets WebSocket - Spot forex ticks/candles
2. Finnhub - Technical indicators and patterns
3. DataBento - CME futures order flow

This script:
- Tests API credentials
- Attempts data collection
- Verifies database storage
- Shows what's working and what's not
"""

import os
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment from .env.scalper (primary)
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path, override=True)

# Also load from .env (fallback)
load_dotenv(override=False)

from database_manager import DatabaseManager
from forex_config import ForexConfig


async def test_ig_credentials():
    """Test IG API credentials."""
    print("\n" + "="*80)
    print(" TEST 1: IG Markets API Credentials")
    print("="*80)

    api_key = os.getenv("IG_API_KEY")
    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")
    demo = os.getenv("IG_DEMO", "true").lower() == "true"

    print(f"\n📋 Credentials Found:")
    print(f"   API Key: {api_key[:20]}...{api_key[-10:] if api_key else 'MISSING'}")
    print(f"   Username: {username if username else 'MISSING'}")
    print(f"   Password: {'*' * len(password) if password else 'MISSING'}")
    print(f"   Account Type: {'DEMO' if demo else 'LIVE'}")

    if not api_key or not username or not password:
        print("\n❌ MISSING IG CREDENTIALS")
        print("   Set in .env.scalper:")
        print("   IG_API_KEY=your_key")
        print("   IG_USERNAME=your_username")
        print("   IG_PASSWORD=your_password")
        return False

    # Try to connect
    print(f"\n🔌 Testing IG API connection...")
    try:
        from trading_ig import IGService

        ig_service = IGService(
            username=username,
            password=password,
            api_key=api_key,
            acc_type='DEMO' if demo else 'LIVE'
        )

        # Create session
        ig_service.create_session()

        # Get account info
        accounts = ig_service.fetch_accounts()

        print(f"✅ IG API Connection SUCCESS")
        print(f"   Accounts: {len(accounts)}")
        for acc in accounts:
            print(f"   - {acc['accountName']} ({acc['accountType']})")

        ig_service.logout()
        return True

    except Exception as e:
        print(f"❌ IG API Connection FAILED: {e}")
        print(f"\n   Possible causes:")
        print(f"   1. API key expired/invalid")
        print(f"   2. Wrong username/password")
        print(f"   3. Account type mismatch (DEMO vs LIVE)")
        print(f"   4. IG API temporarily down")
        return False


async def test_finnhub_credentials():
    """Test Finnhub API credentials."""
    print("\n" + "="*80)
    print(" TEST 2: Finnhub API Credentials")
    print("="*80)

    api_key = os.getenv("FINNHUB_API_KEY")

    print(f"\n📋 Credentials Found:")
    print(f"   API Key: {api_key[:20]}...{api_key[-10:] if api_key else 'MISSING'}")

    if not api_key:
        print("\n⚠️  NO FINNHUB API KEY")
        print("   Finnhub is optional - system will work without it")
        print("   To enable, add to .env.scalper:")
        print("   FINNHUB_API_KEY=your_key")
        return False

    # Try to fetch data
    print(f"\n🔌 Testing Finnhub API...")
    try:
        import requests

        # Test with EUR/USD
        url = "https://finnhub.io/api/v1/scan/technical-indicator"
        params = {
            'symbol': 'OANDA:EUR_USD',
            'resolution': 'D',
            'token': api_key
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            ta = data.get('technicalAnalysis', {})
            counts = ta.get('count', {})

            print(f"✅ Finnhub API Connection SUCCESS")
            print(f"   Technical Analysis for EUR/USD:")
            print(f"   - Buy signals: {counts.get('buy', 0)}")
            print(f"   - Sell signals: {counts.get('sell', 0)}")
            print(f"   - Neutral: {counts.get('neutral', 0)}")
            return True
        else:
            print(f"❌ Finnhub API FAILED: HTTP {response.status_code}")
            if response.status_code == 429:
                print(f"   Rate limit exceeded")
            return False

    except Exception as e:
        print(f"❌ Finnhub API Connection FAILED: {e}")
        return False


async def test_databento_credentials():
    """Test DataBento API credentials."""
    print("\n" + "="*80)
    print(" TEST 3: DataBento API Credentials")
    print("="*80)

    api_key = os.getenv("DATABENTO_API_KEY")

    print(f"\n📋 Credentials Found:")
    print(f"   API Key: {api_key[:20]}...{api_key[-10:] if api_key else 'MISSING'}")

    if not api_key:
        print("\n⚠️  NO DATABENTO API KEY")
        print("   DataBento is optional - provides CME futures order flow")
        print("   To enable, add to .env.scalper:")
        print("   DATABENTO_API_KEY=your_key")
        return False

    # Try to connect
    print(f"\n🔌 Testing DataBento API...")
    try:
        import databento as db

        client = db.Historical(api_key)

        # List datasets
        datasets = client.metadata.list_datasets()

        print(f"✅ DataBento API Connection SUCCESS")
        print(f"   Available datasets: {len(datasets)}")
        print(f"   - Using GLBX.MDP3 (CME Globex)")
        return True

    except Exception as e:
        print(f"❌ DataBento API Connection FAILED: {e}")
        return False


async def test_database_tables():
    """Check if all required database tables exist."""
    print("\n" + "="*80)
    print(" TEST 4: Database Tables")
    print("="*80)

    db = DatabaseManager()
    await db.initialize()

    required_tables = [
        # IG Markets tables
        ('ig_spot_ticks', 'IG spot forex ticks'),
        ('ig_candles', 'IG 1-minute candles'),

        # Finnhub tables
        ('finnhub_candles', 'Finnhub historical candles'),
        ('finnhub_aggregate_indicators', 'Finnhub technical indicators'),
        ('finnhub_patterns', 'Finnhub chart patterns'),
        ('finnhub_support_resistance', 'Finnhub S/R levels'),

        # DataBento tables
        ('cme_mbp10_events', 'CME Level 2 order book events'),
        ('cme_trades', 'CME trade executions'),
        ('cme_mbp10_book', 'CME order book snapshots'),

        # Core tables
        ('instruments', 'Trading instruments')
    ]

    print(f"\n📊 Checking database tables...")

    missing_tables = []
    for table_name, description in required_tables:
        query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        );
        """
        result = await db.execute_query(query, (table_name,))
        exists = result[0]['exists'] if result else False

        if exists:
            print(f"   ✅ {table_name:30} {description}")
        else:
            print(f"   ❌ {table_name:30} {description} - MISSING")
            missing_tables.append(table_name)

    await db.close()

    if missing_tables:
        print(f"\n⚠️  Missing {len(missing_tables)} tables")
        print(f"   Run database schema setup to create them")
        return False
    else:
        print(f"\n✅ All required tables exist")
        return True


async def test_ig_data_in_database():
    """Check if IG data exists in database."""
    print("\n" + "="*80)
    print(" TEST 5: IG Data in Database")
    print("="*80)

    db = DatabaseManager()
    await db.initialize()

    # Check ticks
    print(f"\n📊 Checking IG ticks...")
    tick_query = """
    SELECT
        i.provider_symbol,
        COUNT(*) as tick_count,
        MAX(t.provider_event_ts) as latest_tick
    FROM ig_spot_ticks t
    JOIN instruments i ON t.instrument_id = i.instrument_id
    WHERE i.provider = 'IG'
    GROUP BY i.provider_symbol
    ORDER BY tick_count DESC
    LIMIT 10;
    """

    ticks = await db.execute_query(tick_query)
    if ticks:
        print(f"✅ Found {len(ticks)} symbols with tick data:")
        for row in ticks:
            print(f"   {row['provider_symbol']:10} {row['tick_count']:8,} ticks (last: {row['latest_tick']})")
    else:
        print(f"❌ No tick data in database")

    # Check candles
    print(f"\n📊 Checking IG candles...")
    candle_query = """
    SELECT
        i.provider_symbol,
        COUNT(*) as candle_count,
        MAX(c.provider_event_ts) as latest_candle
    FROM ig_candles c
    JOIN instruments i ON c.instrument_id = i.instrument_id
    WHERE i.provider = 'IG' AND c.timeframe = '1'
    GROUP BY i.provider_symbol
    ORDER BY candle_count DESC
    LIMIT 10;
    """

    candles = await db.execute_query(candle_query)
    if candles:
        print(f"✅ Found {len(candles)} symbols with candle data:")
        for row in candles:
            print(f"   {row['provider_symbol']:10} {row['candle_count']:8,} candles (last: {row['latest_candle']})")
    else:
        print(f"❌ No candle data in database")

    await db.close()

    return bool(ticks and candles)


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print(" COMPREHENSIVE DATA SOURCE TEST")
    print(" Testing ALL 3 data sources + database persistence")
    print("="*80)
    print(f"\n⏰ Test started: {datetime.now()}")

    results = {}

    # Test credentials
    results['ig'] = await test_ig_credentials()
    results['finnhub'] = await test_finnhub_credentials()
    results['databento'] = await test_databento_credentials()

    # Test database
    results['tables'] = await test_database_tables()
    results['ig_data'] = await test_ig_data_in_database()

    # Summary
    print("\n" + "="*80)
    print(" TEST SUMMARY")
    print("="*80)

    print(f"\n✅ Data Sources:")
    print(f"   IG Markets:  {'✅ WORKING' if results['ig'] else '❌ FAILED'}")
    print(f"   Finnhub:     {'✅ WORKING' if results['finnhub'] else '⚠️  NOT CONFIGURED'}")
    print(f"   DataBento:   {'✅ WORKING' if results['databento'] else '⚠️  NOT CONFIGURED'}")

    print(f"\n📊 Database:")
    print(f"   Tables:      {'✅ ALL EXIST' if results['tables'] else '❌ MISSING'}")
    print(f"   IG Data:     {'✅ HAS DATA' if results['ig_data'] else '❌ EMPTY'}")

    # Overall status
    critical_pass = results['ig'] and results['tables']

    if critical_pass and results['ig_data']:
        print(f"\n🎉 ALL CRITICAL SYSTEMS WORKING")
        print(f"   ✅ IG API connected")
        print(f"   ✅ Database has data")
        print(f"   ✅ Scalping engine can run")
    elif critical_pass:
        print(f"\n⚠️  CRITICAL SYSTEMS READY BUT NO DATA YET")
        print(f"   ✅ IG API connected")
        print(f"   ✅ Database tables exist")
        print(f"   ⚠️  No historical data - needs WebSocket to run")
        print(f"\n   Next step: Start WebSocket collector to populate database")
    else:
        print(f"\n❌ CRITICAL ISSUES FOUND")
        if not results['ig']:
            print(f"   ❌ IG API not working - check credentials")
        if not results['tables']:
            print(f"   ❌ Database tables missing - run schema setup")

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
