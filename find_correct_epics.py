"""
Find Correct IG EPICs for CFD Account

Searches for available forex markets and displays the correct EPICs.
"""

from trading_ig import IGService
from forex_config import ForexConfig
import pandas as pd

print("="*80)
print("FINDING CORRECT IG EPICS FOR YOUR CFD ACCOUNT")
print("="*80)

# Create IG service
ig_service = IGService(
    username=ForexConfig.IG_USERNAME,
    password=ForexConfig.IG_PASSWORD,
    api_key=ForexConfig.IG_API_KEY,
    acc_type="DEMO" if ForexConfig.IG_DEMO else "LIVE",
    acc_number=ForexConfig.IG_ACC_NUMBER
)

# Create session
ig_service.create_session(version="2")
print(f"\n✅ Authenticated as: {ForexConfig.IG_USERNAME}")

# Search for forex markets
print("\n🔍 Searching for EUR/USD markets...\n")

try:
    # Search for EUR/USD
    response = ig_service.search_markets("EUR/USD")

    # trading-ig returns DataFrame
    if isinstance(response, pd.DataFrame) and not response.empty:
        print(f"Found {len(response)} EUR/USD markets:\n")

        for idx, row in response.iterrows():
            epic = row.get('epic', 'N/A')
            instrument_name = row.get('instrumentName', 'N/A')
            instrument_type = row.get('instrumentType', 'N/A')
            expiry = row.get('expiry', 'N/A')

            print(f"Epic: {epic}")
            print(f"  Name: {instrument_name}")
            print(f"  Type: {instrument_type}")
            print(f"  Expiry: {expiry}")
            print()
    else:
        print("❌ No markets found or unexpected response format")
        print(f"Response type: {type(response)}")

except Exception as e:
    print(f"❌ Error searching markets: {e}")
    import traceback
    traceback.print_exc()

# Also try GBP/USD
print("\n" + "="*80)
print("🔍 Searching for GBP/USD markets...\n")

try:
    response = ig_service.search_markets("GBP/USD")

    if isinstance(response, pd.DataFrame) and not response.empty:
        print(f"Found {len(response)} GBP/USD markets:\n")

        for idx, row in response.head(5).iterrows():  # Show first 5
            epic = row.get('epic', 'N/A')
            instrument_name = row.get('instrumentName', 'N/A')
            instrument_type = row.get('instrumentType', 'N/A')

            print(f"Epic: {epic}")
            print(f"  Name: {instrument_name}")
            print(f"  Type: {instrument_type}")
            print()

except Exception as e:
    print(f"❌ Error: {e}")

print("="*80)
print("\n💡 Look for EPICs with 'CFD' type or that match your account type.")
print("   Update forex_config.py IG_EPIC_MAP with the correct EPICs.\n")
