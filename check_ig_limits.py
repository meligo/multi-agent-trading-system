"""
Check IG API Rate Limits for your account
"""
from trading_ig import IGService
from forex_config import ForexConfig
import time

print("="*80)
print("IG API RATE LIMITS CHECK")
print("="*80)

# Create IG service
ig_service = IGService(
    username=ForexConfig.IG_USERNAME,
    password=ForexConfig.IG_PASSWORD,
    api_key=ForexConfig.IG_API_KEY,
    acc_type="DEMO",
    acc_number=ForexConfig.IG_ACC_NUMBER
)

# Wait a bit to avoid rate limit from previous tests
print("\n⏳ Waiting 60 seconds for rate limit reset...")
time.sleep(60)

print("🔄 Creating session...")
ig_service.create_session(version="2")
print("✅ Session created\n")

# Get client apps info (shows rate limits)
print("📊 Fetching API rate limits...\n")
try:
    client_apps = ig_service.get_client_apps()

    print("API KEY INFORMATION:")
    print("-" * 80)

    if hasattr(client_apps, 'to_dict'):
        # It's a DataFrame
        for idx, row in client_apps.iterrows():
            print(f"\nApp Name: {row.get('appName', 'N/A')}")
            print(f"API Key: {row.get('apiKey', 'N/A')}")
            print(f"Status: {row.get('status', 'N/A')}")
            print(f"Created: {row.get('createdDate', 'N/A')}")

            # Rate limits
            if 'allowance' in row:
                allowance = row['allowance']
                print(f"\nRATE LIMITS:")
                print(f"  Overall Allowance: {allowance.get('overallRequests', 'N/A')} requests")
                print(f"  Trading Allowance: {allowance.get('tradingRequests', 'N/A')} requests")
                print(f"  Historical Data: {allowance.get('historicalData', 'N/A')} data points")

            if 'allowanceExpiry' in row:
                print(f"  Allowance Reset: {row['allowanceExpiry']}")
    else:
        print(client_apps)

except Exception as e:
    print(f"❌ Error fetching limits: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("\nKEY TAKEAWAYS:")
print("-" * 80)
print("• Trading requests: ~40 per minute (open/close positions)")
print("• Data requests: Separate limit (historical data)")
print("• Demo limits: Lower than LIVE, can change without notice")
print("• Best practice: Add delays between requests")
print("• Use caching to minimize API calls")
print("="*80)
