"""
Discover Available Commodity EPICs on IG Account

This script searches for available commodity markets and their EPICs.
"""

from trading_ig import IGService
from forex_config import ForexConfig
from ig_rate_limiter import get_rate_limiter
import time

def search_market(ig_service, search_term):
    """Search for markets by term using REST API."""
    rate_limiter = get_rate_limiter()
    rate_limiter.wait_if_needed(is_account_request=True)

    try:
        # Use REST API directly
        url = f"{ig_service.BASE_URL}/markets"
        params = {'searchTerm': search_term}
        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
            'Accept': 'application/json; charset=UTF-8',
            'X-IG-API-KEY': ig_service.API_KEY,
            'CST': ig_service.session[0],
            'X-SECURITY-TOKEN': ig_service.session[1],
            'Version': '1'
        }

        response = ig_service.crud_session.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get('markets', [])
        else:
            print(f"API error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error searching for '{search_term}': {e}")
        return []

def main():
    """Discover available commodity EPICs."""

    print("="*80)
    print("DISCOVERING AVAILABLE COMMODITY EPICS ON IG ACCOUNT")
    print("="*80)

    # Initialize IG service
    ig_service = IGService(
        username=ForexConfig.IG_USERNAME,
        password=ForexConfig.IG_PASSWORD,
        api_key=ForexConfig.IG_API_KEY,
        acc_type="DEMO" if ForexConfig.IG_DEMO else "LIVE",
        acc_number=ForexConfig.IG_ACC_NUMBER
    )

    # Create session
    print("\n1. Creating IG session...")
    ig_service.create_session()
    print("✅ Session created\n")

    # Search terms for commodities
    search_terms = {
        # Gold
        "Gold": ["XAUUSD", "Gold", "Spot Gold"],

        # Silver
        "Silver": ["XAGUSD", "Silver", "Spot Silver"],

        # Platinum
        "Platinum": ["XPTUSD", "Platinum", "Spot Platinum"],

        # Palladium
        "Palladium": ["XPDUSD", "Palladium", "Spot Palladium"],

        # Oil
        "WTI Oil": ["WTI", "Crude Oil", "US Oil"],
        "Brent Oil": ["Brent", "Brent Crude"],

        # Natural Gas
        "Natural Gas": ["Natural Gas", "NATGAS"],

        # Copper
        "Copper": ["Copper", "Spot Copper"],
    }

    results = {}

    print("="*80)
    print("SEARCHING FOR COMMODITIES...")
    print("="*80)

    for category, terms in search_terms.items():
        print(f"\n{'='*80}")
        print(f"CATEGORY: {category}")
        print("="*80)

        found_markets = []

        for term in terms:
            print(f"\nSearching: '{term}'...")
            markets = search_market(ig_service, term)

            if markets:
                print(f"  Found {len(markets)} markets")

                for market in markets:
                    epic = market.get('epic', 'N/A')
                    name = market.get('instrumentName', 'N/A')
                    instrument_type = market.get('instrumentType', 'N/A')
                    market_status = market.get('marketStatus', 'N/A')

                    # Filter for COMMODITIES and cash/spot markets
                    if instrument_type == 'COMMODITIES':
                        # Skip futures (they have month/year in name)
                        if any(month in name.upper() for month in ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', '-20', '-21', '-22', '-23', '-24', '-25']):
                            continue

                        market_info = {
                            'epic': epic,
                            'name': name,
                            'type': instrument_type,
                            'status': market_status
                        }

                        if market_info not in found_markets:
                            found_markets.append(market_info)
                            print(f"    ✅ {epic}")
                            print(f"       Name: {name}")
                            print(f"       Type: {instrument_type}")
                            print(f"       Status: {market_status}")
            else:
                print(f"  No markets found")

            time.sleep(0.5)  # Rate limit protection

        results[category] = found_markets

    # Summary
    print("\n" + "="*80)
    print("SUMMARY - AVAILABLE COMMODITY EPICS")
    print("="*80)

    all_epics = {}

    for category, markets in results.items():
        if markets:
            print(f"\n{category}:")
            for market in markets:
                epic = market['epic']
                name = market['name']
                print(f"  {epic}")
                print(f"    └─ {name}")

                # Group by type
                if 'MINI' in epic:
                    market_type = 'MINI'
                elif 'CFD' in epic:
                    market_type = 'CFD'
                else:
                    market_type = 'OTHER'

                # Extract base symbol
                base_symbol = category.upper().replace(' ', '_')

                if base_symbol not in all_epics:
                    all_epics[base_symbol] = {}

                all_epics[base_symbol][market_type] = epic

    # Generate Python config
    print("\n" + "="*80)
    print("PYTHON CONFIG FOR forex_config.py")
    print("="*80)

    print("\n# Commodity EPICs (discovered from IG API)")
    print("COMMODITY_PAIRS = [")
    for symbol in sorted(all_epics.keys()):
        print(f"    \"{symbol}\",")
    print("]")

    print("\n# Commodity EPIC Mapping")
    print("COMMODITY_EPIC_MAP = {")
    for symbol, epics in sorted(all_epics.items()):
        # Prefer MINI, fallback to CFD
        preferred_epic = epics.get('MINI', epics.get('CFD', epics.get('OTHER')))
        print(f"    \"{symbol}\": \"{preferred_epic}\",")
    print("}")

    print("\n" + "="*80)
    print("DISCOVERY COMPLETE!")
    print("="*80)

if __name__ == "__main__":
    main()
