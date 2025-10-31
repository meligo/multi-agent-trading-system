"""
Test the Specific Gold EPICs Found via Search

Tests each Gold EPIC discovered to find which ones are tradeable.
"""

from ig_trader import IGTrader

def test_epic(trader, epic, name):
    """Test if an EPIC is available and tradeable."""
    try:
        print(f"\n{'='*80}")
        print(f"Testing: {name}")
        print(f"EPIC: {epic}")
        print(f"{'='*80}")

        market_info = trader.ig_service.fetch_market_by_epic(epic)
        snapshot = market_info.get('snapshot', {})
        instrument = market_info.get('instrument', {})
        dealing_rules = market_info.get('dealingRules', {})

        market_name = instrument.get('name', 'N/A')
        epic_code = instrument.get('epic', 'N/A')
        market_status = snapshot.get('marketStatus', 'N/A')
        bid = snapshot.get('bid', 'N/A')
        offer = snapshot.get('offer', 'N/A')

        # Deal size info
        min_size = dealing_rules.get('minDealSize', {}).get('value', 'N/A')
        max_size = dealing_rules.get('maxStopOrLimitDistance', {}).get('value', 'N/A')

        print(f"Name: {market_name}")
        print(f"Market Status: {market_status}")
        print(f"Bid: {bid}")
        print(f"Offer: {offer}")
        print(f"Min Deal Size: {min_size}")
        print(f"Max Stop/Limit: {max_size}")

        if market_status == 'TRADEABLE':
            print(f"\n✅ ✅ ✅ TRADEABLE! ✅ ✅ ✅")
            print(f"\n📝 Add to forex_config.py:")
            print(f'  "XAU_USD": "{epic}",')
            return True, epic
        elif market_status == 'CLOSED':
            print(f"\n⏰ CLOSED (but available when market opens)")
            print(f"\n📝 Add to forex_config.py:")
            print(f'  "XAU_USD": "{epic}",')
            return True, epic
        else:
            print(f"\n⚠️  Status: {market_status}")
            return False, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None


def main():
    """Test all found Gold EPICs."""

    print("="*80)
    print("TESTING FOUND GOLD EPICS")
    print("="*80)

    trader = IGTrader()

    # Gold EPICs found from search
    gold_epics = [
        ("CS.D.CFDGOLD.CFDGC.IP", "Spot Gold"),
        ("CS.D.CFDGOLD.CFM.IP", "Spot Gold Mini (10oz)"),
        ("CS.D.CFPGOLD.CFP.IP", "Spot Gold (£1 Contract)"),
        ("MT.D.GC.FWS2.IP", "Gold ($100) - DEC-25 Expiry"),
        ("MT.D.GC.FWM2.IP", "Gold ($33.20) - DEC-25 Expiry"),
    ]

    working_epics = []

    for epic, name in gold_epics:
        success, working_epic = test_epic(trader, epic, name)
        if success:
            working_epics.append((epic, name))

    # Summary
    print("\n" + "="*80)
    print("SUMMARY - WORKING GOLD EPICS")
    print("="*80)

    if working_epics:
        print(f"\n✅ Found {len(working_epics)} working Gold EPIC(s):\n")

        for epic, name in working_epics:
            print(f"EPIC: {epic}")
            print(f"  Name: {name}")
            print(f'  Config: "XAU_USD": "{epic}",')
            print()

        print("\n🎯 RECOMMENDED FOR TRADING:")
        print("="*80)

        # Recommend based on type
        spot_epics = [e for e in working_epics if 'Spot' in e[1]]
        if spot_epics:
            recommended = spot_epics[0]  # First spot epic
            print(f"\n✅ Use: {recommended[0]}")
            print(f"   ({recommended[1]})")
            print(f"\n   This is a spot/cash CFD with no expiry.")
            print(f"   Perfect for algorithmic trading.")
            print(f"\n   Add to forex_config.py:")
            print(f'   "XAU_USD": "{recommended[0]}",')
        else:
            print(f"\n⚠️  Only futures contracts available (have expiry dates)")
            print(f"   Consider using one of these:")
            for epic, name in working_epics:
                print(f"   - {epic} ({name})")

    else:
        print("\n❌ No working Gold EPICs found.")
        print("\nPossible reasons:")
        print("1. Market closed (try during trading hours)")
        print("2. Demo account restrictions")
        print("3. API access limitations")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
