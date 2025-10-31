"""
Test IG API Without Session Authentication
Try to fetch data using only API key
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("IG_API_KEY")

print("="*80)
print("IG API - NO AUTH TEST")
print("="*80)
print(f"\nTrying to fetch data with API key only (no session)...")
print(f"API Key: {api_key[:20]}...")

# Try to get historical prices without authentication
epic = "CS.D.EURUSD.TODAY.IP"
url = f"https://demo-api.ig.com/gateway/deal/prices/{epic}"

headers = {
    "X-IG-API-KEY": api_key,
    "Accept": "application/json; charset=UTF-8",
    "Version": "3"
}

params = {
    "resolution": "MINUTE_5",
    "max": 10
}

print(f"\nRequest:")
print(f"  URL: {url}")
print(f"  Headers: {headers}")
print(f"  Params: {params}")

print(f"\n📡 Making request...")

try:
    response = requests.get(url, headers=headers, params=params, timeout=10)
    print(f"\n📊 Response:")
    print(f"  Status: {response.status_code}")
    print(f"  Headers: {dict(response.headers)}")

    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ SUCCESS! Data received:")
        print(f"     Instrument: {data.get('instrumentType')}")
        print(f"     Prices: {len(data.get('prices', []))} candles")
        if data.get('prices'):
            latest = data['prices'][-1]
            print(f"     Latest: {latest}")
    else:
        print(f"  ❌ FAILED")
        try:
            error_data = response.json()
            print(f"     Error: {error_data}")
        except:
            print(f"     Response text: {response.text}")

except Exception as e:
    print(f"❌ Exception: {e}")

print("\n" + "="*80)
