"""
Test Currency Exposure Filtering Logic

Simulates multiple signal scenarios to verify the currency filtering algorithm
works correctly and selects only the highest confidence signal per currency.
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class MockSignal:
    """Mock trading signal for testing."""
    signal: str  # 'BUY', 'SELL', or 'HOLD'
    confidence: float
    entry_price: float = 1.1000


def get_currencies_from_pair(pair: str) -> tuple:
    """
    Extract the two currencies from a pair name.

    Args:
        pair: Currency pair like 'EUR_USD' or 'OIL_CRUDE'

    Returns:
        Tuple of (base_currency, quote_currency) or (None, None) for commodities
    """
    # Commodities don't have currency pairs
    if pair in ['OIL_CRUDE', 'OIL_BRENT', 'XAU_USD', 'XAG_USD']:
        return (None, None)

    # Split forex pair
    if '_' in pair:
        parts = pair.split('_')
        if len(parts) == 2:
            return (parts[0], parts[1])

    return (None, None)


def filter_signals_by_currency_exposure(signals_with_pairs: List[tuple]) -> List[tuple]:
    """
    Filter signals to prevent duplicate currency exposure.
    Only keeps the highest confidence signal for each currency.

    Args:
        signals_with_pairs: List of (signal, pair) tuples

    Returns:
        Filtered list of (signal, pair) tuples
    """
    if not signals_with_pairs:
        return []

    # Track currency exposure with best signal
    currency_exposure = {}  # currency -> (confidence, signal, pair)

    for signal, pair in signals_with_pairs:
        if not signal or signal.signal not in ['BUY', 'SELL']:
            continue

        base, quote = get_currencies_from_pair(pair)

        # Handle commodities (no currency filtering)
        if base is None and quote is None:
            # Always include commodities
            if pair not in currency_exposure:
                currency_exposure[pair] = (signal.confidence, signal, pair)
            elif signal.confidence > currency_exposure[pair][0]:
                currency_exposure[pair] = (signal.confidence, signal, pair)
            continue

        # Check if either currency already has a signal
        base_exists = base in currency_exposure
        quote_exists = quote in currency_exposure

        # Determine if we should accept this signal
        should_accept = False

        if not base_exists and not quote_exists:
            # Neither currency has a signal yet - accept this signal
            should_accept = True
        elif base_exists and quote_exists:
            # Both currencies already have signals
            # Only accept if this signal has higher confidence than BOTH existing signals
            base_conf = currency_exposure[base][0]
            quote_conf = currency_exposure[quote][0]
            if signal.confidence > base_conf and signal.confidence > quote_conf:
                # Remove old signal's currencies
                old_base_pair = currency_exposure[base][2]
                old_quote_pair = currency_exposure[quote][2]

                # Remove currencies from the signal being replaced
                for old_pair_to_remove in [old_base_pair, old_quote_pair]:
                    old_b, old_q = get_currencies_from_pair(old_pair_to_remove)
                    if old_b:
                        currency_exposure.pop(old_b, None)
                    if old_q:
                        currency_exposure.pop(old_q, None)

                should_accept = True
        elif base_exists or quote_exists:
            # One currency has a signal, the other doesn't
            existing_currency = base if base_exists else quote
            existing_conf = currency_exposure[existing_currency][0]

            if signal.confidence > existing_conf:
                # Remove old signal's currencies
                old_pair = currency_exposure[existing_currency][2]
                old_base, old_quote = get_currencies_from_pair(old_pair)
                if old_base:
                    currency_exposure.pop(old_base, None)
                if old_quote:
                    currency_exposure.pop(old_quote, None)

                should_accept = True

        # Add the signal if accepted
        if should_accept:
            currency_exposure[base] = (signal.confidence, signal, pair)
            currency_exposure[quote] = (signal.confidence, signal, pair)

    # Extract unique signals (avoid duplicates from both currencies pointing to same signal)
    unique_signals = {}
    for conf, signal, pair in currency_exposure.values():
        if pair not in unique_signals:
            unique_signals[pair] = (signal, pair)

    return list(unique_signals.values())


def print_scenario(name: str, signals: List[tuple], filtered: List[tuple]):
    """Print test scenario results."""
    print(f"\n{'='*80}")
    print(f"SCENARIO: {name}")
    print(f"{'='*80}")

    print(f"\n📊 Input Signals ({len(signals)}):")
    for signal, pair in signals:
        base, quote = get_currencies_from_pair(pair)
        if base and quote:
            print(f"   {pair}: {signal.signal} (confidence: {signal.confidence:.2f}) - {base}/{quote}")
        else:
            print(f"   {pair}: {signal.signal} (confidence: {signal.confidence:.2f}) - Commodity")

    print(f"\n✅ Filtered Signals ({len(filtered)}):")
    for signal, pair in filtered:
        base, quote = get_currencies_from_pair(pair)
        if base and quote:
            print(f"   {pair}: {signal.signal} (confidence: {signal.confidence:.2f}) - {base}/{quote}")
        else:
            print(f"   {pair}: {signal.signal} (confidence: {signal.confidence:.2f}) - Commodity")

    if len(signals) > len(filtered):
        print(f"\n⚠️  Filtered out {len(signals) - len(filtered)} signals to prevent duplicate currency exposure")


def test_scenario_1():
    """Scenario 1: Multiple EUR signals - should keep only highest confidence."""
    signals = [
        (MockSignal('BUY', 0.75), 'EUR_USD'),
        (MockSignal('SELL', 0.80), 'EUR_GBP'),  # Highest confidence, takes EUR and GBP
        (MockSignal('BUY', 0.70), 'EUR_JPY'),
        (MockSignal('SELL', 0.78), 'GBP_JPY'),  # Can't take because GBP already used
    ]

    filtered = filter_signals_by_currency_exposure(signals)
    print_scenario("Multiple EUR Signals", signals, filtered)

    # Verify: Should keep only EUR_GBP (0.80) because it has highest confidence
    # GBP_JPY (0.78) is rejected because GBP is already taken by EUR_GBP (0.80)
    assert len(filtered) == 1, f"Expected 1 signal, got {len(filtered)}"
    pairs = [pair for _, pair in filtered]
    assert 'EUR_GBP' in pairs, "EUR_GBP should be selected (highest confidence for both EUR and GBP)"
    print("✅ Test passed!")


def test_scenario_2():
    """Scenario 2: Same currency different directions - highest confidence wins."""
    signals = [
        (MockSignal('BUY', 0.85), 'EUR_USD'),   # Higher confidence
        (MockSignal('SELL', 0.72), 'EUR_GBP'),
    ]

    filtered = filter_signals_by_currency_exposure(signals)
    print_scenario("Same Currency Different Directions", signals, filtered)

    # Verify: Should keep only EUR_USD (0.85)
    assert len(filtered) == 1, f"Expected 1 signal, got {len(filtered)}"
    assert filtered[0][1] == 'EUR_USD', "EUR_USD should win (higher confidence)"
    print("✅ Test passed!")


def test_scenario_3():
    """Scenario 3: Commodities always included (no currency conflicts)."""
    signals = [
        (MockSignal('BUY', 0.75), 'EUR_USD'),
        (MockSignal('SELL', 0.80), 'GBP_USD'),    # Best USD signal
        (MockSignal('SELL', 0.70), 'OIL_CRUDE'),  # Commodity
        (MockSignal('BUY', 0.68), 'OIL_BRENT'),   # Commodity
    ]

    filtered = filter_signals_by_currency_exposure(signals)
    print_scenario("Commodities + Forex", signals, filtered)

    # Verify: Should keep GBP_USD (best USD), OIL_CRUDE, OIL_BRENT
    assert len(filtered) == 3, f"Expected 3 signals, got {len(filtered)}"
    pairs = [pair for _, pair in filtered]
    assert 'GBP_USD' in pairs, "GBP_USD should be selected (best USD)"
    assert 'OIL_CRUDE' in pairs, "OIL_CRUDE should be included (commodity)"
    assert 'OIL_BRENT' in pairs, "OIL_BRENT should be included (commodity)"
    print("✅ Test passed!")


def test_scenario_4():
    """Scenario 4: Complex multi-currency scenario."""
    signals = [
        (MockSignal('BUY', 0.75), 'EUR_USD'),
        (MockSignal('SELL', 0.68), 'GBP_USD'),
        (MockSignal('BUY', 0.82), 'USD_JPY'),    # Best USD signal
        (MockSignal('SELL', 0.80), 'EUR_GBP'),   # Best EUR signal
        (MockSignal('BUY', 0.70), 'EUR_JPY'),
        (MockSignal('SELL', 0.76), 'AUD_CAD'),
        (MockSignal('BUY', 0.78), 'GBP_CHF'),    # Best GBP signal
    ]

    filtered = filter_signals_by_currency_exposure(signals)
    print_scenario("Complex Multi-Currency", signals, filtered)

    # Verify: Should filter to unique currencies with highest confidence
    # Expected: USD_JPY (0.82), EUR_GBP (0.80 - already includes GBP), AUD_CAD (0.76)
    # Wait, EUR_GBP includes both EUR and GBP
    # GBP_CHF (0.78) conflicts with EUR_GBP's GBP
    # So we should get signals that cover USD, JPY, EUR, GBP, AUD, CAD, CHF optimally

    pairs = [pair for _, pair in filtered]
    print(f"\n🔍 Debug - Selected pairs: {pairs}")

    # Key assertions:
    # 1. No duplicate currencies
    all_currencies = []
    for _, pair in filtered:
        base, quote = get_currencies_from_pair(pair)
        if base:
            all_currencies.extend([base, quote])

    unique_currencies = set(all_currencies)

    # Check that each currency appears exactly once
    from collections import Counter
    currency_counts = Counter(all_currencies)
    duplicates = {curr: count for curr, count in currency_counts.items() if count > 1}

    assert len(duplicates) == 0, f"No duplicate currencies allowed, but found: {duplicates}"
    print(f"✅ No duplicate currencies: {unique_currencies}")

    # 2. High confidence signals should be present
    assert 'USD_JPY' in pairs, "USD_JPY should be selected (highest USD confidence)"
    print("✅ Test passed!")


def test_scenario_5():
    """Scenario 5: All 22 pairs with various signals."""
    signals = [
        # Major Pairs
        (MockSignal('BUY', 0.75), 'EUR_USD'),
        (MockSignal('SELL', 0.68), 'GBP_USD'),
        (MockSignal('BUY', 0.82), 'USD_JPY'),    # Best USD
        (MockSignal('SELL', 0.72), 'USD_CHF'),
        (MockSignal('BUY', 0.70), 'AUD_USD'),
        (MockSignal('SELL', 0.65), 'USD_CAD'),
        (MockSignal('BUY', 0.63), 'NZD_USD'),

        # EUR Crosses
        (MockSignal('SELL', 0.80), 'EUR_GBP'),   # Best EUR
        (MockSignal('BUY', 0.71), 'EUR_JPY'),
        (MockSignal('SELL', 0.69), 'EUR_AUD'),
        (MockSignal('BUY', 0.67), 'EUR_CAD'),
        (MockSignal('SELL', 0.64), 'EUR_CHF'),
        (MockSignal('BUY', 0.62), 'EUR_NZD'),

        # GBP Crosses
        (MockSignal('SELL', 0.77), 'GBP_JPY'),
        (MockSignal('BUY', 0.74), 'GBP_AUD'),
        (MockSignal('SELL', 0.68), 'GBP_CAD'),
        (MockSignal('BUY', 0.66), 'GBP_CHF'),

        # Other Crosses
        (MockSignal('BUY', 0.73), 'AUD_JPY'),
        (MockSignal('SELL', 0.71), 'AUD_CAD'),
        (MockSignal('BUY', 0.69), 'CAD_JPY'),

        # Commodities
        (MockSignal('SELL', 0.74), 'OIL_CRUDE'),
        (MockSignal('BUY', 0.71), 'OIL_BRENT'),
    ]

    filtered = filter_signals_by_currency_exposure(signals)
    print_scenario("All 22 Pairs Mixed Signals", signals, filtered)

    # Verify no duplicate currencies
    all_currencies = []
    for _, pair in filtered:
        base, quote = get_currencies_from_pair(pair)
        if base:
            all_currencies.extend([base, quote])

    # Check for duplicates
    from collections import Counter
    currency_counts = Counter(all_currencies)
    duplicates = {curr: count for curr, count in currency_counts.items() if count > 1}

    assert len(duplicates) == 0, f"Duplicate currencies found: {duplicates}"

    unique_currencies = set(all_currencies)
    print(f"\n✅ No duplicate currencies: {unique_currencies}")

    # Commodities should always be included
    pairs = [pair for _, pair in filtered]
    assert 'OIL_CRUDE' in pairs, "OIL_CRUDE should be included"
    assert 'OIL_BRENT' in pairs, "OIL_BRENT should be included"

    print(f"✅ Test passed! {len(filtered)} unique signals selected from {len(signals)} total")


def main():
    """Run all test scenarios."""
    print("="*80)
    print("TESTING CURRENCY EXPOSURE FILTERING ALGORITHM")
    print("="*80)
    print("\nThis tests the logic that prevents duplicate currency exposure")
    print("by selecting only the highest confidence signal per currency.\n")

    try:
        test_scenario_1()
        test_scenario_2()
        test_scenario_3()
        test_scenario_4()
        test_scenario_5()

        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nThe currency filtering algorithm is working correctly:")
        print("  ✅ Prevents duplicate currency exposure")
        print("  ✅ Selects highest confidence signal per currency")
        print("  ✅ Handles commodities correctly (no conflicts)")
        print("  ✅ Works with all 22 pairs")
        print("\nReady for production use!")

    except AssertionError as e:
        print("\n" + "="*80)
        print(f"❌ TEST FAILED: {e}")
        print("="*80)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
