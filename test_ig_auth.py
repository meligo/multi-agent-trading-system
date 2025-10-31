"""
Test IG Authentication
"""
import os
from dotenv import load_dotenv
from ig_client import IGClient

load_dotenv()

print("="*80)
print("IG AUTHENTICATION TEST")
print("="*80)

# Load credentials
api_key = os.getenv("IG_API_KEY")
username = os.getenv("IG_USERNAME")
password = os.getenv("IG_PASSWORD")
is_demo = os.getenv("IG_DEMO", "true").lower() == "true"

print(f"\nConfiguration:")
print(f"  API Key: {api_key[:20]}...")
print(f"  Username: {username}")
print(f"  Password: {'*' * len(password)}")
print(f"  Demo Mode: {is_demo}")

# Determine URL
base_url = "https://demo-api.ig.com/gateway/deal" if is_demo else "https://api.ig.com/gateway/deal"
print(f"  Base URL: {base_url}")

# Create client
print(f"\n📡 Creating IG client...")
client = IGClient(api_key=api_key, base_url=base_url)

# Try to authenticate
print(f"\n🔐 Attempting authentication...")
try:
    session_data = client.create_session(username, password)
    print(f"✅ Authentication successful!")
    print(f"\nSession Data:")
    print(f"  Account ID: {session_data.get('currentAccountId')}")
    print(f"  Account Type: {session_data.get('accountType')}")
    print(f"  Currency: {session_data.get('currencyIsoCode')}")
    print(f"  Lightstreamer: {session_data.get('lightstreamerEndpoint')}")

    # Try to fetch account info
    print(f"\n📊 Fetching account info...")
    account_info = client.get_account()
    print(f"✅ Account info retrieved successfully!")

    # Try to fetch historical prices
    print(f"\n📈 Fetching EUR/USD historical data...")
    prices = client.get_historical_prices(
        epic="CS.D.EURUSD.TODAY.IP",
        resolution="MINUTE_5",
        max_points=10
    )
    print(f"✅ Retrieved {len(prices.get('prices', []))} candles")
    if prices.get('prices'):
        latest = prices['prices'][-1]
        print(f"   Latest candle: {latest.get('snapshotTime')} - Close: {latest.get('closePrice', {}).get('mid')}")

except Exception as e:
    print(f"❌ Authentication failed!")
    print(f"   Error: {e}")
    if hasattr(e, 'response_text'):
        print(f"   Response: {e.response_text}")

    print(f"\n💡 Troubleshooting:")
    print(f"   1. Verify your IG demo account is activated at: https://www.ig.com/")
    print(f"   2. Check username is correct (usually your email or username)")
    print(f"   3. Check password is correct")
    print(f"   4. Make sure you have a demo account, not just live")
    print(f"   5. Check if 2FA/OTP is enabled (may need additional code)")

print("\n" + "="*80)
