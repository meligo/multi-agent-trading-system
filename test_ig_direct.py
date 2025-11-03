#!/usr/bin/env python3
"""
Direct IG API test with the new credentials
"""

from trading_ig import IGService
import sys

# Credentials from user
api_key = "79ae278ca555968dda0d4837b90b813c4c941fdc"
username = "Aertsb"
password = "Br@mB0Tr@d3!"

print(f"\n{'='*80}")
print(f" TESTING IG CREDENTIALS - DIRECT")
print(f"{'='*80}")
print(f"\nAPI Key: {api_key[:30]}...{api_key[-15:]}")
print(f"Username: {username}")
print(f"Password: {password[:3]}{'*' * (len(password) - 3)}")

try:
    print(f"\n🔌 Attempting connection...")

    # Try DEMO account
    print(f"\n   Trying DEMO account...")
    ig_service = IGService(
        username=username,
        password=password,
        api_key=api_key,
        acc_type='DEMO'
    )

    ig_service.create_session()
    accounts = ig_service.fetch_accounts()

    print(f"\n✅ SUCCESS WITH DEMO ACCOUNT!")
    print(f"   Accounts: {len(accounts)}")
    for acc in accounts:
        print(f"   - {acc['accountName']} ({acc['accountType']}): {acc['balance']['balance']}")

    ig_service.logout()
    sys.exit(0)

except Exception as demo_error:
    print(f"\n❌ DEMO failed: {demo_error}")

    # Try LIVE account
    try:
        print(f"\n   Trying LIVE account...")
        ig_service = IGService(
            username=username,
            password=password,
            api_key=api_key,
            acc_type='LIVE'
        )

        ig_service.create_session()
        accounts = ig_service.fetch_accounts()

        print(f"\n✅ SUCCESS WITH LIVE ACCOUNT!")
        print(f"   Accounts: {len(accounts)}")
        for acc in accounts:
            print(f"   - {acc['accountName']} ({acc['accountType']}): {acc['balance']['balance']}")

        ig_service.logout()
        print(f"\n⚠️  NOTE: You're using a LIVE account!")
        print(f"   Update .env.scalper: IG_DEMO=false")
        sys.exit(0)

    except Exception as live_error:
        print(f"\n❌ LIVE failed: {live_error}")

        print(f"\n{'='*80}")
        print(f" BOTH DEMO AND LIVE FAILED")
        print(f"{'='*80}")
        print(f"\nPossible issues:")
        print(f"  1. Credentials are still incorrect")
        print(f"  2. Account needs email verification")
        print(f"  3. Account is locked/suspended")
        print(f"  4. API key needs to be generated fresh from IG portal")
        print(f"  5. Account doesn't have API access enabled")
        print(f"\nNext steps:")
        print(f"  1. Log in to https://www.ig.com/ manually")
        print(f"  2. Verify you can access your account")
        print(f"  3. Go to https://labs.ig.com/")
        print(f"  4. Check if API access is enabled")
        print(f"  5. Generate a NEW API key")
        print(f"  6. Try again with new key")

        sys.exit(1)
