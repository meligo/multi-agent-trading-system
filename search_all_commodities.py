"""
Search for ALL Commodity Markets Including Gold Using IG API

Uses the trading-ig library's search functionality to find metals and commodities.
"""

from ig_trader import IGTrader

def main():
    """Search for commodity markets including Gold, Silver, Platinum."""

    print("="*80)
    print("SEARCHING FOR ALL COMMODITY MARKETS (Gold, Silver, Platinum, etc.)")
    print("="*80)

    trader = IGTrader()

    # Search terms to try
    search_terms = [
        "GOLD",
        "XAU",
        "XAUUSD",
        "Gold",
        "Spot Gold",
        "SILVER",
        "XAG",
        "XAGUSD",
        "Silver",
        "PLATINUM",
        "Platinum",
        "COPPER",
        "Copper",
        "PALLADIUM",
        "Palladium",
        "Metal",
        "Metals",
        "Precious",
    ]

    all_results = {}

    for term in search_terms:
        try:
            print(f"\n🔍 Searching for: '{term}'...")

            # Use the trading-ig search_markets function
            response = trader.ig_service.search_markets(term)

            # Check if response is a DataFrame
            if response is not None:
                # Convert to dict if it's a DataFrame
                if hasattr(response, 'to_dict'):
                    # It's a DataFrame - convert to list of dicts
                    if not response.empty:
                        markets = response.to_dict('records')
                        print(f"  ✅ Found {len(markets)} results")

                        for market in markets:
                            epic = market.get('epic', 'N/A')
                            name = market.get('instrumentName', 'N/A')
                            inst_type = market.get('instrumentType', 'N/A')
                            expiry = market.get('expiry', 'N/A')

                            # Store all results (don't filter yet)
                            if epic != 'N/A':
                                all_results[epic] = {
                                    'epic': epic,
                                    'name': name,
                                    'type': inst_type,
                                    'expiry': expiry,
                                    'search_term': term
                                }
                                print(f"     - {name} ({epic})")
                    else:
                        print(f"  ℹ️  No results")
                elif isinstance(response, dict) and 'markets' in response:
                    # It's a dict with markets key
                    markets = response['markets']
                    if markets:
                        print(f"  ✅ Found {len(markets)} results")

                        for market in markets:
                            epic = market.get('epic', 'N/A')
                            name = market.get('instrumentName', 'N/A')
                            inst_type = market.get('instrumentType', 'N/A')
                            expiry = market.get('expiry', 'N/A')

                            # Store all results (don't filter yet)
                            if epic != 'N/A':
                                all_results[epic] = {
                                    'epic': epic,
                                    'name': name,
                                    'type': inst_type,
                                    'expiry': expiry,
                                    'search_term': term
                                }
                                print(f"     - {name} ({epic})")
                    else:
                        print(f"  ℹ️  No results")
                else:
                    print(f"  ℹ️  No results")
            else:
                print(f"  ℹ️  No results")

        except Exception as e:
            print(f"  ⚠️  Error: {e}")

    # Display all unique results
    print("\n" + "="*80)
    print("ALL COMMODITY MARKETS FOUND")
    print("="*80)

    if all_results:
        print(f"\n✅ Found {len(all_results)} unique commodity markets:\n")

        # Group by type
        metals = {}
        others = {}

        for epic, info in all_results.items():
            name_upper = info['name'].upper()

            # Categorize
            if any(metal in name_upper for metal in ['GOLD', 'XAU', 'SILVER', 'XAG', 'PLATINUM', 'PALLADIUM', 'COPPER']):
                metals[epic] = info
            else:
                others[epic] = info

        # Display metals first
        if metals:
            print("="*80)
            print("PRECIOUS METALS & INDUSTRIAL METALS")
            print("="*80)

            for epic, info in metals.items():
                print(f"\nEPIC: {epic}")
                print(f"  Name: {info['name']}")
                print(f"  Type: {info['type']}")
                print(f"  Expiry: {info['expiry']}")
                print(f"  Found via search: '{info['search_term']}'")

                # Try to fetch market details to check if tradeable
                try:
                    market_details = trader.ig_service.fetch_market_by_epic(epic)
                    snapshot = market_details.get('snapshot', {})
                    instrument = market_details.get('instrument', {})

                    status = snapshot.get('marketStatus', 'N/A')
                    bid = snapshot.get('bid', 'N/A')
                    offer = snapshot.get('offer', 'N/A')

                    dealing_rules = market_details.get('dealingRules', {})
                    min_size = dealing_rules.get('minDealSize', {}).get('value', 'N/A')

                    print(f"  Status: {status}")
                    print(f"  Bid: {bid}, Offer: {offer}")
                    print(f"  Min Deal Size: {min_size}")

                    if status == 'TRADEABLE':
                        print(f"  ✅ TRADEABLE!")

                        # Suggest configuration
                        pair_name = None
                        if 'GOLD' in info['name'].upper() or 'XAU' in epic:
                            pair_name = "XAU_USD"
                        elif 'SILVER' in info['name'].upper() or 'XAG' in epic:
                            pair_name = "XAG_USD"
                        elif 'PLATINUM' in info['name'].upper():
                            pair_name = "XPT_USD"
                        elif 'COPPER' in info['name'].upper():
                            pair_name = "COPPER"

                        if pair_name:
                            print(f"\n  📝 Add to forex_config.py:")
                            print(f'     "{pair_name}": "{epic}",')
                    else:
                        print(f"  ⚠️  Status: {status}")

                except Exception as e:
                    print(f"  ⚠️  Could not fetch details: {e}")

        # Display others
        if others:
            print("\n" + "="*80)
            print("OTHER COMMODITIES")
            print("="*80)

            for epic, info in others.items():
                print(f"\nEPIC: {epic}")
                print(f"  Name: {info['name']}")
                print(f"  Type: {info['type']}")

    else:
        print("\n❌ No commodity markets found.")
        print("\nThis could mean:")
        print("1. Search terms don't match available markets")
        print("2. Demo account has limited commodity access")
        print("3. Markets may be available but not searchable via API")
        print("\nTry:")
        print("1. Log into IG web platform")
        print("2. Navigate to 'Commodities' section")
        print("3. Note exact market names and EPICs")
        print("4. Test those EPICs using find_gold_epic.py")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
