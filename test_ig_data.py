"""
Test IG Data Fetching
"""
from trading_ig import IGService

# Working credentials
username = "meligokes"
password = "$Demo001"
api_key = "2f6287777a79dfb0c6f2a47c86a6f7d0b07ecef8"
acc_type = "DEMO"
acc_number = "Z64WQT"

print("="*80)
print("IG DATA FETCHING TEST")
print("="*80)

ig_service = IGService(username, password, api_key, acc_type, acc_number=acc_number)
ig_service.create_session(version="2")
print("✅ Session created")

# Test fetching EUR/USD data
epic = "CS.D.EURUSD.TODAY.IP"
resolution = "5Min"  # Pandas format: 5Min, not MINUTE_5
numpoints = 100

print(f"\n📈 Fetching {numpoints} points of EUR/USD @ 5min resolution...")
response = ig_service.fetch_historical_prices_by_epic_and_num_points(
    epic, resolution, numpoints
)

print(f"✅ Data retrieved!")
print(f"   Instrument Type: {response.get('instrumentType')}")
print(f"   Prices type: {type(response['prices'])}")
print(f"   Data points: {len(response['prices'])}")

# Show the data
prices_df = response['prices']
print(f"\n   DataFrame shape: {prices_df.shape}")
print(f"   Columns: {list(prices_df.columns)}")
print(f"\n   Latest 3 candles (bid prices):")
print(prices_df[['bid']].tail(3))
print(f"\n   Latest 3 candles (ask prices):")
print(prices_df[['ask']].tail(3))

print("\n" + "="*80)
print("✅ IG DATA FETCHING WORKS PERFECTLY!")
print("="*80)
