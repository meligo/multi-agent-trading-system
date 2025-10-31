"""
Find the Correct Gold EPIC on IG Account

Tests all possible EPIC patterns for Gold (XAUUSD) to find what actually works.
"""

from ig_trader import IGTrader

def test_epic(trader, epic, name):
    """Test if an EPIC is available."""
    try:
        market_info = trader.ig_service.fetch_market_by_epic(epic)
        snapshot = market_info.get('snapshot', {})
        instrument = market_info.get('instrument', {})

        market_name = instrument.get('name', 'N/A')
        market_status = snapshot.get('marketStatus', 'N/A')
        bid = snapshot.get('bid', 'N/A')
        offer = snapshot.get('offer', 'N/A')

        print(f"\n✅ FOUND: {epic}")
        print(f"   Name: {market_name}")
        print(f"   Status: {market_status}")
        print(f"   Bid: {bid}")
        print(f"   Offer: {offer}")

        return True, {
            'epic': epic,
            'name': market_name,
            'status': market_status,
            'bid': bid,
            'offer': offer
        }
    except Exception as e:
        error_msg = str(e)
        if "unavailable" in error_msg.lower():
            print(f"❌ {epic}: Not available")
        else:
            print(f"❌ {epic}: {error_msg}")
        return False, None

def main():
    """Test all possible Gold EPIC patterns."""

    print("="*80)
    print("SEARCHING FOR GOLD (XAUUSD) EPIC ON YOUR IG ACCOUNT")
    print("="*80)

    trader = IGTrader()

    # All possible EPIC patterns for Gold
    gold_epics = [
        # Spot Gold patterns
        "CS.D.XAUUSD.CFD.IP",          # CFD cash
        "CS.D.XAUUSD.MINI.IP",         # Mini CFD
        "CS.D.XAUUSD.TODAY.IP",        # Today (spread bet)
        "CS.D.XAUUSD.DAILY.IP",        # Daily
        "CS.D.XAUUSD.Cash.IP",         # Cash variant

        # Alternative prefixes
        "CC.D.XAUUSD.CFD.IP",          # Commodity CFD
        "CC.D.XAUUSD.USS.IP",          # Undated cash
        "CC.D.XAUUSD.CASH.IP",         # Cash

        # MT4 patterns (unlikely but test anyway)
        "MT.D.XAUUSD.CFD.IP",
        "MT.D.XAUUSD.MINI.IP",

        # DFB patterns (spread betting)
        "CS.D.XAUUSD.DFB.IP",

        # Gold with different naming
        "CS.D.GOLD.CFD.IP",
        "CC.D.GOLD.USS.IP",
        "CS.D.GOLD.MINI.IP",

        # Spot Gold specific
        "IX.D.GOLD.DAILY.IP",          # Index gold
        "CS.D.SPOTGOLD.CFD.IP",        # Spot prefix

        # Try without IP suffix
        "CS.D.XAUUSD.CFD",
        "CS.D.XAUUSD.MINI",
    ]

    print(f"\nTesting {len(gold_epics)} possible EPIC patterns...\n")

    found_epics = []

    for epic in gold_epics:
        success, info = test_epic(trader, epic, "Gold")
        if success:
            found_epics.append(info)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    if found_epics:
        print(f"\n✅ FOUND {len(found_epics)} WORKING GOLD EPIC(S):\n")
        for info in found_epics:
            print(f"EPIC: {info['epic']}")
            print(f"  Name: {info['name']}")
            print(f"  Status: {info['status']}")
            print(f"  Bid: {info['bid']}, Offer: {info['offer']}")
            print()

            epic_code = info['epic']
            print("Add to forex_config.py:")
            print(f'  "XAU_USD": "{epic_code}",')
            print()
    else:
        print("\n❌ No Gold EPICs found on your account.")
        print("\nPossible reasons:")
        print("1. Demo account may not have Gold access")
        print("2. Region-specific availability")
        print("3. Account type restrictions")
        print("4. Try logging into IG web platform to verify Gold is visible")

    print("="*80)

if __name__ == "__main__":
    main()
