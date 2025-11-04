"""
Test IG Markets Spread Fix
Verifies that the 600-9000 pip bug is resolved.
"""

import pandas as pd
from datetime import datetime
from pre_trade_gates import check_spread_gate, check_all_gates

print("=" * 70)
print("IG MARKETS SPREAD FIX - INTEGRATION TEST")
print("=" * 70)

# Scenario 1: EUR/USD with SPREAD=9 ticks (should be 0.9 pips)
print("\n📊 Test 1: EUR/USD SPREAD=9 with bid/ask (preferred method)")
result = check_spread_gate(
    current_spread=9,
    pair='EUR_USD',
    bid=1.08341,
    ask=1.08350,
    use_ig_markets=True
)
print(f"   Result: {result.reason}")
print(f"   Passed: {'✅' if result.passed else '❌'}")
print(f"   Spread: {result.metadata['spread_pips']:.1f} pips")
assert result.passed, "Test 1 failed: Spread should pass"
assert 0.8 < result.metadata['spread_pips'] < 1.0, "Test 1 failed: Spread should be ~0.9 pips"

# Scenario 2: EUR/USD with SPREAD=9 ticks (no bid/ask, use ticks formula)
print("\n📊 Test 2: EUR/USD SPREAD=9 without bid/ask (IG ticks formula)")
result = check_spread_gate(
    current_spread=9,
    pair='EUR_USD',
    use_ig_markets=True
)
print(f"   Result: {result.reason}")
print(f"   Passed: {'✅' if result.passed else '❌'}")
print(f"   Spread: {result.metadata['spread_pips']:.1f} pips")
assert result.passed, "Test 2 failed: Spread should pass"
assert 0.8 < result.metadata['spread_pips'] < 1.0, "Test 2 failed: Spread should be ~0.9 pips"

# Scenario 3: EUR/USD with SPREAD=60 ticks (should be 6.0 pips)
print("\n📊 Test 3: EUR/USD SPREAD=60 (wider spread, still valid)")
result = check_spread_gate(
    current_spread=60,
    pair='EUR_USD',
    use_ig_markets=True
)
print(f"   Result: {result.reason}")
print(f"   Passed: {'✅' if result.passed else '❌'}")
print(f"   Spread: {result.metadata['spread_pips']:.1f} pips")
# Note: 6.0 pips > 1.5 pips max, so should FAIL (but correctly calculated)
assert not result.passed, "Test 3 failed: 6.0 pips should fail (>1.5 max)"
assert 5.9 < result.metadata['spread_pips'] < 6.1, "Test 3 failed: Spread should be ~6.0 pips"

# Scenario 4: USD/JPY with SPREAD=9 ticks
print("\n📊 Test 4: USD/JPY SPREAD=9")
result = check_spread_gate(
    current_spread=9,
    pair='USD_JPY',
    bid=149.123,
    ask=149.132,
    use_ig_markets=True
)
print(f"   Result: {result.reason}")
print(f"   Passed: {'✅' if result.passed else '❌'}")
print(f"   Spread: {result.metadata['spread_pips']:.1f} pips")
assert result.passed, "Test 4 failed: Spread should pass"
assert 0.8 < result.metadata['spread_pips'] < 1.0, "Test 4 failed: Spread should be ~0.9 pips"

# Scenario 5: GBP/USD with SPREAD=18 ticks (typical)
print("\n📊 Test 5: GBP/USD SPREAD=18")
result = check_spread_gate(
    current_spread=18,
    pair='GBP_USD',
    bid=1.26543,
    ask=1.26561,
    use_ig_markets=True
)
print(f"   Result: {result.reason}")
print(f"   Passed: {'✅' if result.passed else '❌'}")
print(f"   Spread: {result.metadata['spread_pips']:.1f} pips")
# 1.8 pips > 1.5 pips max, so should FAIL
assert not result.passed, "Test 5 failed: 1.8 pips should fail (>1.5 max)"
assert 1.7 < result.metadata['spread_pips'] < 1.9, "Test 5 failed: Spread should be ~1.8 pips"

# Scenario 6: Full gate check with all parameters
print("\n📊 Test 6: Full gate check (check_all_gates)")
# Create minimal OHLCV data
data = pd.DataFrame({
    'open': [1.08340] * 100,
    'high': [1.08350] * 100,
    'low': [1.08330] * 100,
    'close': [1.08345] * 100,
    'volume': [1000] * 100
})

gates_passed, results = check_all_gates(
    data=data,
    pair='EUR_USD',
    current_spread=9,
    current_time=datetime(2025, 1, 15, 8, 30),  # London core session
    bid=1.08341,
    ask=1.08350,
    use_ig_markets=True
)

spread_result = results[0]  # First result is spread gate
print(f"   Spread gate: {spread_result.reason}")
print(f"   Spread passed: {'✅' if spread_result.passed else '❌'}")
print(f"   Spread: {spread_result.metadata['spread_pips']:.1f} pips")
assert spread_result.passed, "Test 6 failed: Spread should pass"
assert 0.8 < spread_result.metadata['spread_pips'] < 1.0, "Test 6 failed: Spread should be ~0.9 pips"

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED!")
print("=" * 70)
print("\nSummary:")
print("  ✅ SPREAD=9 ticks → 0.9 pips (EUR/USD)")
print("  ✅ SPREAD=60 ticks → 6.0 pips (EUR/USD)")
print("  ✅ SPREAD=9 ticks → 0.9 pips (USD/JPY)")
print("  ✅ SPREAD=18 ticks → 1.8 pips (GBP/USD)")
print("  ✅ Bid/ask method works correctly")
print("  ✅ IG ticks formula works correctly")
print("  ✅ Integration with check_all_gates works")
print("\n🎉 The 600-9000 pip bug is FIXED!")
print("=" * 70)
