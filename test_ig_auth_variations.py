"""
Test IG Authentication with Different Username Formats
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("IG_API_KEY")
password = os.getenv("IG_PASSWORD")
account_id = "Z64WQT"

print("="*80)
print("IG AUTHENTICATION - TESTING USERNAME VARIATIONS")
print("="*80)

# Try different username formats
username_variations = [
    "meligoke",  # Original
    "Z64WQT",    # Account ID
    "meligoke@Z64WQT",  # Username@AccountID
]

base_url = "https://demo-api.ig.com/gateway/deal"

for username in username_variations:
    print(f"\n{'='*80}")
    print(f"Testing with username: {username}")
    print(f"{'='*80}")

    headers = {
        "X-IG-API-KEY": api_key,
        "Accept": "application/json; charset=UTF-8",
        "Content-Type": "application/json; charset=UTF-8",
        "Version": "2"
    }

    payload = {
        "identifier": username,
        "password": password
    }

    try:
        response = requests.post(
            f"{base_url}/session",
            headers=headers,
            json=payload,
            timeout=10
        )

        print(f"Status: {response.status_code}")

        if response.status_code in (200, 201):
            print(f"✅ SUCCESS!")
            data = response.json()
            cst = response.headers.get('CST')
            xst = response.headers.get('X-SECURITY-TOKEN')
            print(f"  CST: {cst[:20] if cst else None}...")
            print(f"  X-SECURITY-TOKEN: {xst[:20] if xst else None}...")
            print(f"  Account ID: {data.get('currentAccountId')}")
            print(f"  Account Type: {data.get('accountType')}")
            print(f"\n🎉 Found working credentials!")
            break
        else:
            try:
                error_data = response.json()
                print(f"❌ Failed: {error_data.get('errorCode')}")
            except:
                print(f"❌ Failed: {response.text}")

    except Exception as e:
        print(f"❌ Exception: {e}")

print("\n" + "="*80)
print("NOTE: If all variations failed, please verify:")
print("1. Your IG demo account is active at https://www.ig.com/")
print("2. The username/password are correct")
print("3. You have a DEMO account (not just live)")
print("4. 2FA is not enabled (or we need to add OTP support)")
print("="*80)
