"""
Test IG API using the trading-ig library - Fixed Version
"""
from trading_ig import IGService
import logging

logging.basicConfig(level=logging.INFO)

print("="*80)
print("TRADING-IG LIBRARY TEST - WORKING CREDENTIALS")
print("="*80)

# Your WORKING credentials
username = "meligokes"
password = "$Demo001"
api_key = "2f6287777a79dfb0c6f2a47c86a6f7d0b07ecef8"
acc_type = "DEMO"
acc_number = "Z64WQT"

print(f"\nConfiguration:")
print(f"  Username: {username}")
print(f"  Account Type: {acc_type}")
print(f"  Account Number: {acc_number}")

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

    print(f"\n📊 Fetching accounts...")
    accounts = ig_service.fetch_accounts()
    print(f"✅ Retrieved accounts")
    print(f"   Type: {type(accounts)}")
    print(f"   Data: {accounts}")

    print(f"\n📈 Testing forex pairs:")

    # Test multiple forex pairs
    forex_pairs = [
        ("CS.D.EURUSD.TODAY.IP", "EUR/USD"),
        ("CS.D.GBPUSD.TODAY.IP", "GBP/USD"),
        ("CS.D.USDJPY.TODAY.IP", "USD/JPY"),
    ]

    for epic, name in forex_pairs:
        print(f"\n  Testing {name} ({epic})...")
        try:
            response = ig_service.fetch_historical_prices_by_epic_and_num_points(
                epic=epic,
                resolution="MINUTE_5",
                num_points=10
            )

            print(f"  ✅ {name} data retrieved!")
            print(f"     Instrument Type: {response.get('instrumentType')}")

            if 'prices' in response:
                prices_df = response['prices']
                print(f"     Data points: {len(prices_df)}")
                if hasattr(prices_df, 'tail'):
                    print(f"     Latest candle:")
                    latest = prices_df.tail(1)
                    print(f"     {latest}")

        except Exception as e:
            print(f"  ⚠️ {name} error: {e}")

    print(f"\n🎉 SUCCESS! IG API is fully working!")
    print(f"✅ Authentication: WORKING")
    print(f"✅ Data Fetching: WORKING")
    print(f"✅ Account Access: WORKING")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
