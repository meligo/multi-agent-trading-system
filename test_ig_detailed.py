#!/usr/bin/env python3
"""
Detailed IG API diagnostics
"""

from trading_ig import IGService
import requests
import json

api_key = "4e241a68a913a4934550e95582ffa820492b43bb"
username = "Aertsb"
password = "Br@mB0Tr@d3!"

print(f"\n{'='*80}")
print(f" DETAILED IG API DIAGNOSTICS")
print(f"{'='*80}")

# Test 1: Check credentials format
print(f"\n1. Credential Format Check:")
print(f"   Username length: {len(username)} chars")
print(f"   Password length: {len(password)} chars")
print(f"   API Key length: {len(api_key)} chars")
print(f"   Username repr: {repr(username)}")
print(f"   Password repr: {repr(password)}")

# Test 2: Try direct REST API call
print(f"\n2. Direct REST API Test:")
try:
    url = "https://demo-api.ig.com/gateway/deal/session"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json; charset=UTF-8",
        "X-IG-API-KEY": api_key,
        "Version": "2"
    }
    data = {
        "identifier": username,
        "password": password
    }

    print(f"   URL: {url}")
    print(f"   Headers: {headers}")
    print(f"   Data: {{'identifier': '{username}', 'password': '***'}}")

    response = requests.post(url, headers=headers, json=data)

    print(f"\n   Response Status: {response.status_code}")
    print(f"   Response Body: {response.text[:200]}")

    if response.status_code == 200:
        print(f"\n   ✅ REST API SUCCESS!")
    else:
        print(f"\n   ❌ REST API FAILED")

except Exception as e:
    print(f"   ❌ Exception: {e}")

# Test 3: Try with trading_ig library (DEMO)
print(f"\n3. trading_ig Library Test (DEMO):")
try:
    ig_service = IGService(
        username=username,
        password=password,
        api_key=api_key,
        acc_type='DEMO'
    )

    ig_service.create_session()
    print(f"   ✅ Library DEMO SUCCESS!")

except Exception as e:
    print(f"   ❌ Library DEMO FAILED: {e}")

# Test 4: Try with trading_ig library (LIVE)
print(f"\n4. trading_ig Library Test (LIVE):")
try:
    ig_service = IGService(
        username=username,
        password=password,
        api_key=api_key,
        acc_type='LIVE'
    )

    ig_service.create_session()
    print(f"   ✅ Library LIVE SUCCESS!")

except Exception as e:
    print(f"   ❌ Library LIVE FAILED: {e}")

print(f"\n{'='*80}")
print(f" DIAGNOSIS")
print(f"{'='*80}")
print(f"\nIf ALL tests failed with 401 'invalid-details':")
print(f"  → Username or password is still incorrect")
print(f"  → OR account needs email verification")
print(f"  → OR account is locked/suspended")
print(f"\nAction: Log in manually to https://www.ig.com/")
print(f"  - Use username: {username}")
print(f"  - Use password: (the one you provided)")
print(f"  - If you can't log in → reset password")
print(f"  - If you CAN log in → contact IG support about API access")
