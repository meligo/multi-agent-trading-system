"""
Search for Gold Markets Using IG API

Uses IG's market search to find ALL gold-related markets available on your account.
"""

from ig_trader import IGTrader
import requests

def search_markets_via_api(ig_service, search_term):
    """Search markets using REST API."""
    try:
        # Build URL
        base_url = ig_service.BASE_URL
        url = f"{base_url}/markets"

        # Get session tokens
        # The ig_service should have stored tokens after create_session
        cst = ig_service.ig_session
        token = ig_service.ig_session_token

        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
            'Accept': 'application/json; charset=UTF-8',
            'X-IG-API-KEY': ig_service.API_KEY,
            'CST': cst,
            'X-SECURITY-TOKEN': token,
            'Version': '1'
        }

        params = {'searchTerm': search_term}

        print(f"\nSearching for: '{search_term}'...")
        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            markets = data.get('markets', [])
            return markets
        else:
            print(f"API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return []

    except Exception as e:
        print(f"Error searching: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    """Search for Gold markets."""

    print("="*80)
    print("SEARCHING FOR GOLD MARKETS VIA IG API")
    print("="*80)

    trader = IGTrader()

    # Search terms for gold
    search_terms = [
        "GOLD",
        "XAU",
        "XAUUSD",
        "Gold",
        "Spot Gold",
        "AU",
    ]

    all_results = {}

    for term in search_terms:
        markets = search_markets_via_api(trader.ig_service, term)

        if markets:
            print(f"  ✅ Found {len(markets)} results")

            for market in markets:
                epic = market.get('epic', 'N/A')
                name = market.get('instrumentName', 'N/A')
                inst_type = market.get('instrumentType', 'N/A')
                expiry = market.get('expiry', 'N/A')
                market_id = market.get('marketId', 'N/A')

                # Filter for gold-related
                if any(gold_term in name.upper() for gold_term in ['GOLD', 'XAU', 'AU']):
                    all_results[epic] = {
                        'epic': epic,
                        'name': name,
                        'type': inst_type,
                        'expiry': expiry,
                        'market_id': market_id
                    }
        else:
            print(f"  ❌ No results")

    # Display results
    print("\n" + "="*80)
    print("GOLD MARKETS FOUND")
    print("="*80)

    if all_results:
        print(f"\n✅ Found {len(all_results)} unique Gold markets:\n")

        for epic, info in all_results.items():
            print(f"EPIC: {epic}")
            print(f"  Name: {info['name']}")
            print(f"  Type: {info['type']}")
            print(f"  Expiry: {info['expiry']}")
            print(f"  Market ID: {info['market_id']}")

            # Try to fetch market details
            try:
                market_details = trader.ig_service.fetch_market_by_epic(epic)
                snapshot = market_details.get('snapshot', {})
                status = snapshot.get('marketStatus', 'N/A')
                bid = snapshot.get('bid', 'N/A')
                offer = snapshot.get('offer', 'N/A')

                print(f"  Status: {status}")
                print(f"  Bid: {bid}, Offer: {offer}")

                if status == 'TRADEABLE':
                    print(f"  ✅ TRADEABLE!")
            except:
                print(f"  ⚠️  Could not fetch details")

            print()
    else:
        print("\n❌ No Gold markets found via search.")
        print("\nThis means:")
        print("1. Your demo account doesn't have Gold market access")
        print("2. Try logging into IG web platform")
        print("3. Check if Gold appears in 'Commodities' section")
        print("4. You may need to request Gold access or upgrade account")

    print("="*80)

if __name__ == "__main__":
    main()
