"""
Test IG API using the trading-ig library
"""
from trading_ig import IGService
import logging

logging.basicConfig(level=logging.INFO)

print("="*80)
print("TRADING-IG LIBRARY TEST")
print("="*80)

# Your credentials
username = "meligokes"  # Note: with 's' at the end
password = "$Demo001"
api_key = "2f6287777a79dfb0c6f2a47c86a6f7d0b07ecef8"
acc_type = "DEMO"
acc_number = "Z64WQT"

print(f"\nConfiguration:")
print(f"  Username: {username}")
print(f"  Account Type: {acc_type}")
print(f"  Account Number: {acc_number}")
print(f"  API Key: {api_key[:20]}...")

try:
    print(f"\n📡 Creating IG Service...")
    ig_service = IGService(
        username=username,
        password=password,
        api_key=api_key,
        acc_type=acc_type,
        acc_number=acc_number
    )

    print(f"\n🔐 Creating session (v2)...")
    session_data = ig_service.create_session(version="2")
    print(f"✅ Session created successfully!")
    print(f"   Client ID: {session_data.get('clientId')}")
    print(f"   Account ID: {session_data.get('currentAccountId')}")
    print(f"   Account Type: {session_data.get('accountType')}")
    print(f"   Currency: {session_data.get('currencyIsoCode')}")
    print(f"   Timezone: {session_data.get('timezoneOffset')}")

    print(f"\n📊 Fetching accounts...")
    accounts = ig_service.fetch_accounts()
    print(f"✅ Retrieved {len(accounts)} accounts")
    for i, acc in enumerate(accounts):
        print(f"   Account {i+1}:")
        print(f"      ID: {acc.get('accountId')}")
        print(f"      Name: {acc.get('accountName')}")
        print(f"      Type: {acc.get('accountType')}")
        print(f"      Currency: {acc.get('currency')}")
        print(f"      Balance: {acc.get('balance', {}).get('balance')}")

    print(f"\n📈 Fetching historical prices for EUR/USD...")
    epic = "CS.D.EURUSD.TODAY.IP"  # EUR/USD mini spread bet
    resolution = "MINUTE_5"  # 5-minute candles
    num_points = 10

    response = ig_service.fetch_historical_prices_by_epic_and_num_points(
        epic=epic,
        resolution=resolution,
        num_points=num_points
    )

    print(f"✅ Retrieved historical data!")
    print(f"   Instrument: {response.get('instrumentType')}")

    if 'prices' in response:
        prices_df = response['prices']
        print(f"   Data points: {len(prices_df)}")
        print(f"\n   Latest 3 candles:")
        print(prices_df.tail(3))

    print(f"\n🎉 All tests passed!")
    print(f"✅ IG API is working correctly with trading-ig library!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
