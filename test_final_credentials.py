#!/usr/bin/env python3
"""
Test FINAL correct credentials
"""

import requests

# CORRECT credentials from user
api_key = "4e241a68a913a4934550e95582ffa820492b43bb"
username = "Bramboke"
password = "$Bramboke1$"

print(f"\n{'='*80}")
print(f" TESTING FINAL CORRECT CREDENTIALS")
print(f"{'='*80}")
print(f"\nAPI Key: {api_key[:30]}...{api_key[-15:]}")
print(f"Username: {username}")
print(f"Password: {password[:2]}{'*' * (len(password) - 4)}{password[-2:]}")

# Test DEMO
print(f"\n🔌 Testing DEMO API...")

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
    response = requests.post(demo_url, headers=headers, json=body, timeout=10)

    print(f"Response Status: {response.status_code}")

    if response.status_code == 200:
        CST = response.headers.get('CST')
        X_SECURITY_TOKEN = response.headers.get('X-SECURITY-TOKEN')

        print(f"\n🎉🎉🎉 SUCCESS! IG API WORKING! 🎉🎉🎉")
        print(f"\nTokens received:")
        print(f"  CST: {CST[:40]}...")
        print(f"  X-SECURITY-TOKEN: {X_SECURITY_TOKEN[:40]}...")

        # Get accounts
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
            print(f"\n✅ Accounts:")
            for acc in accounts_data.get('accounts', []):
                print(f"   - {acc.get('accountName')} ({acc.get('accountType')})")
                print(f"     Balance: {acc.get('balance', {}).get('balance')} {acc.get('currency')}")
                print(f"     Available: {acc.get('balance', {}).get('available')}")

        print(f"\n{'='*80}")
        print(f" 🚀 ALL SYSTEMS GO!")
        print(f"{'='*80}")
        print(f"\nNext steps:")
        print(f"  1. Restart dashboard: streamlit run scalping_dashboard.py")
        print(f"  2. Watch for: '📊 EUR_USD: Tick received'")
        print(f"  3. Verify collection: python test_all_data_sources.py")
        print(f"\n✅ DATA COLLECTION WILL START IMMEDIATELY!")
        exit(0)

    else:
        print(f"❌ DEMO failed: {response.text}")

        # Try LIVE
        print(f"\n🔌 Testing LIVE API...")
        live_url = "https://api.ig.com/gateway/deal/session"
        response = requests.post(live_url, headers=headers, json=body, timeout=10)

        print(f"Response Status: {response.status_code}")

        if response.status_code == 200:
            CST = response.headers.get('CST')
            X_SECURITY_TOKEN = response.headers.get('X-SECURITY-TOKEN')

            print(f"\n🎉 SUCCESS WITH LIVE ACCOUNT!")
            print(f"⚠️  You're using a LIVE account - update IG_DEMO=false in .env.scalper")
            exit(0)
        else:
            print(f"❌ LIVE also failed: {response.text}")

except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()
