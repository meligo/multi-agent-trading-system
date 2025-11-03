"""
Test if IG Markets are currently open and providing data
"""

import os
from dotenv import load_dotenv
from trading_ig import IGService
from datetime import datetime

# Load environment
load_dotenv()

# Connect to IG
ig_service = IGService(
    username=os.getenv("IG_USERNAME"),
    password=os.getenv("IG_PASSWORD"),
    api_key=os.getenv("IG_API_KEY"),
    acc_type='DEMO',
    acc_number=os.getenv("IG_ACC_NUMBER")
)

print("=" * 80)
print("IG MARKET STATUS TEST")
print("=" * 80)
print(f"Time: {datetime.now()}")
print()

try:
    # Create session
    ig_service.create_session()
    print("✅ Connected to IG API")
    print()

    # Test each pair
    epics = {
        "EUR_USD": "CS.D.EURUSD.MINI.IP",
        "GBP_USD": "CS.D.GBPUSD.MINI.IP",
        "USD_JPY": "CS.D.USDJPY.MINI.IP"
    }

    for pair, epic in epics.items():
        try:
            # Get market details
            market = ig_service.fetch_market_by_epic(epic)

            # Extract snapshot data
            snapshot = market['snapshot']
            bid = snapshot['bid']
            offer = snapshot['offer']
            market_status = snapshot.get('marketStatus', 'UNKNOWN')

            # Calculate spread
            if 'JPY' in pair:
                spread = (offer - bid) / 0.01  # JPY pip value
            else:
                spread = (offer - bid) / 0.0001  # Standard pip value

            print(f"{pair}:")
            print(f"  Epic: {epic}")
            print(f"  Status: {market_status}")
            print(f"  Bid: {bid}")
            print(f"  Ask: {offer}")
            print(f"  Spread: {spread:.1f} pips")
            print()

        except Exception as e:
            print(f"❌ {pair}: Error - {e}")
            print()

except Exception as e:
    print(f"❌ Failed to connect: {e}")
