#!/usr/bin/env python3
"""
Test NEW IG API key
"""

from trading_ig import IGService

# NEW credentials from user
api_key = "4e241a68a913a4934550e95582ffa820492b43bb"
username = "Aertsb"
password = "Br@mB0Tr@d3!"

print(f"\n{'='*80}")
print(f" TESTING NEW IG API KEY")
print(f"{'='*80}")
print(f"\nAPI Key: {api_key[:30]}...{api_key[-15:]}")
print(f"Username: {username}")
print(f"Password: {password[:3]}{'*' * (len(password) - 3)}")

# Try DEMO account
print(f"\n🔌 Testing DEMO account...")

try:
    ig_service = IGService(
        username=username,
        password=password,
        api_key=api_key,
        acc_type='DEMO'
    )

    ig_service.create_session()
    accounts = ig_service.fetch_accounts()

    print(f"\n🎉 SUCCESS! IG API CONNECTION WORKING!")
    print(f"\n✅ Accounts: {len(accounts)}")
    for acc in accounts:
        print(f"   - {acc['accountName']} ({acc['accountType']})")
        print(f"     Balance: {acc['balance']['balance']} {acc['currency']}")
        print(f"     Available: {acc['balance']['available']}")

    ig_service.logout()

    print(f"\n{'='*80}")
    print(f" 🚀 READY TO COLLECT DATA!")
    print(f"{'='*80}")
    print(f"\nNext steps:")
    print(f"  1. Run: streamlit run scalping_dashboard.py")
    print(f"  2. Watch for: '📊 EUR_USD: Tick received'")
    print(f"  3. Verify: python test_all_data_sources.py")
    print(f"\n✅ ALL SYSTEMS GO!")

except Exception as e:
    print(f"\n❌ FAILED: {e}")
    print(f"\n   If still failing:")
    print(f"   1. Verify you can log in to https://www.ig.com/")
    print(f"   2. Check email for verification link")
    print(f"   3. Contact IG support if account is locked")
