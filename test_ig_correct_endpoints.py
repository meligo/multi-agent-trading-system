#!/usr/bin/env python3
"""
Test IG API using CORRECT endpoints from the guide
Testing both DEMO and LIVE with proper headers
"""

import requests
import json

api_key = "4e241a68a913a4934550e95582ffa820492b43bb"
username = "Aertsb"
password = "Br@mB0Tr@d3!"

print(f"\n{'='*80}")
print(f" TESTING IG API - CORRECT ENDPOINTS")
print(f"{'='*80}")

# Test 1: DEMO endpoint
print(f"\n1. Testing DEMO API (https://demo-api.ig.com)")
print(f"   Endpoint: /gateway/deal/session")

demo_url = "https://demo-api.ig.com/gateway/deal/session"
headers = {
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json; charset=UTF-8",
    "X-IG-API-KEY": api_key,
    "Version": "2"
}
body = {
    "identifier": username,
    "password": password
}

try:
    print(f"\n   Sending POST request...")
    print(f"   Headers: X-IG-API-KEY, Version: 2")
    print(f"   Body: {{identifier: '{username}', password: '***'}}")

    response = requests.post(demo_url, headers=headers, json=body, timeout=10)

    print(f"\n   Response Status: {response.status_code}")
    print(f"   Response Headers: {dict(response.headers)}")
    print(f"   Response Body: {response.text[:500]}")

    if response.status_code == 200:
        CST = response.headers.get('CST')
        X_SECURITY_TOKEN = response.headers.get('X-SECURITY-TOKEN')

        print(f"\n   ✅ DEMO API SUCCESS!")
        print(f"   CST: {CST[:30]}..." if CST else "   ❌ No CST token")
        print(f"   X-SECURITY-TOKEN: {X_SECURITY_TOKEN[:30]}..." if X_SECURITY_TOKEN else "   ❌ No security token")

        # Get account info
        if CST and X_SECURITY_TOKEN:
            print(f"\n   Fetching account information...")
            accounts_url = "https://demo-api.ig.com/gateway/deal/accounts"
            account_headers = {
                "CST": CST,
                "X-SECURITY-TOKEN": X_SECURITY_TOKEN,
                "X-IG-API-KEY": api_key,
                "Version": "1"
            }

            accounts_response = requests.get(accounts_url, headers=account_headers)
            if accounts_response.status_code == 200:
                accounts_data = accounts_response.json()
                print(f"\n   ✅ Accounts retrieved:")
                for acc in accounts_data.get('accounts', []):
                    print(f"      - {acc.get('accountName')} ({acc.get('accountType')})")
                    print(f"        Balance: {acc.get('balance', {}).get('balance')}")

        exit(0)  # Success!

    else:
        print(f"\n   ❌ DEMO API FAILED")

        # Try to parse error
        try:
            error_data = response.json()
            print(f"   Error Code: {error_data.get('errorCode')}")
        except:
            pass

except Exception as e:
    print(f"\n   ❌ Exception: {e}")

# Test 2: LIVE endpoint
print(f"\n{'='*80}")
print(f"2. Testing LIVE API (https://api.ig.com)")
print(f"   Endpoint: /gateway/deal/session")

live_url = "https://api.ig.com/gateway/deal/session"

try:
    print(f"\n   Sending POST request...")

    response = requests.post(live_url, headers=headers, json=body, timeout=10)

    print(f"\n   Response Status: {response.status_code}")
    print(f"   Response Body: {response.text[:500]}")

    if response.status_code == 200:
        CST = response.headers.get('CST')
        X_SECURITY_TOKEN = response.headers.get('X-SECURITY-TOKEN')

        print(f"\n   ✅ LIVE API SUCCESS!")
        print(f"   CST: {CST[:30]}..." if CST else "   ❌ No CST token")
        print(f"   X-SECURITY-TOKEN: {X_SECURITY_TOKEN[:30]}..." if X_SECURITY_TOKEN else "   ❌ No security token")

        # Get account info
        if CST and X_SECURITY_TOKEN:
            print(f"\n   Fetching account information...")
            accounts_url = "https://api.ig.com/gateway/deal/accounts"
            account_headers = {
                "CST": CST,
                "X-SECURITY-TOKEN": X_SECURITY_TOKEN,
                "X-IG-API-KEY": api_key,
                "Version": "1"
            }

            accounts_response = requests.get(accounts_url, headers=account_headers)
            if accounts_response.status_code == 200:
                accounts_data = accounts_response.json()
                print(f"\n   ✅ Accounts retrieved:")
                for acc in accounts_data.get('accounts', []):
                    print(f"      - {acc.get('accountName')} ({acc.get('accountType')})")
                    print(f"        Balance: {acc.get('balance', {}).get('balance')}")

                print(f"\n   ⚠️  NOTE: You're using a LIVE account!")
                print(f"   Update .env.scalper: IG_DEMO=false")

        exit(0)  # Success!

    else:
        print(f"\n   ❌ LIVE API FAILED")

        # Try to parse error
        try:
            error_data = response.json()
            print(f"   Error Code: {error_data.get('errorCode')}")
        except:
            pass

except Exception as e:
    print(f"\n   ❌ Exception: {e}")

# Summary
print(f"\n{'='*80}")
print(f" DIAGNOSIS")
print(f"{'='*80}")
print(f"\nBoth DEMO and LIVE failed. Possible issues:")
print(f"\n1. **Account Type Issue** (Most Likely)")
print(f"   - API only works with Spread Bet and CFD accounts")
print(f"   - If your default account is ISA, SIPP, or Share Trading → Auth fails")
print(f"   - Solution: Log in to IG and switch default account type")
print(f"\n2. **Credentials Still Incorrect**")
print(f"   - Username or password has a typo")
print(f"   - Solution: Verify by logging in manually to https://www.ig.com/")
print(f"\n3. **Account Not Verified**")
print(f"   - Account needs email verification before API access")
print(f"   - Solution: Check email for verification link from IG")
print(f"\n4. **API Access Not Enabled**")
print(f"   - Account might not have API access enabled")
print(f"   - Solution: Log in to https://labs.ig.com/ and enable API access")
print(f"\nNext step: Log in manually to https://www.ig.com/ to verify:")
print(f"  - That credentials work")
print(f"  - What account type you have (must be Spread Bet or CFD)")
print(f"  - That API access is enabled")
