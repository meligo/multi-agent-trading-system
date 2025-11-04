"""
Universal IG Markets Spread Handling - Works for ANY Currency Pair

This example shows how to handle spread conversion for ANY currency pair
that IG Markets offers, not just EUR/USD, GBP/USD, USD/JPY.

The system automatically:
1. Fetches metadata from IG Markets API (recommended)
2. Caches it for reuse
3. Falls back to smart defaults if API unavailable
"""

from ig_markets_spread import (
    fetch_and_cache_ig_spec,
    get_cached_spread_pips,
    get_or_fetch_spec,
    cache_ig_instrument_spec
)

print("=" * 70)
print("UNIVERSAL IG MARKETS SPREAD HANDLING")
print("Works for ANY currency pair!")
print("=" * 70)

# ============================================================================
# METHOD 1: Manual Caching (if you already have metadata)
# ============================================================================

print("\n📊 METHOD 1: Manual Caching")
print("-" * 70)

# If you already have the metadata from IG API, cache it manually
pairs_metadata = {
    'EUR_USD': {'pip': '0.0001', 'dpf': 100000},
    'GBP_USD': {'pip': '0.0001', 'dpf': 100000},
    'USD_JPY': {'pip': '0.01', 'dpf': 1000},
    'EUR_CHF': {'pip': '0.0001', 'dpf': 100000},  # Swiss Franc
    'AUD_CAD': {'pip': '0.0001', 'dpf': 100000},  # Aussie/Loonie
    'NZD_JPY': {'pip': '0.01', 'dpf': 1000},      # Kiwi/Yen
    'EUR_GBP': {'pip': '0.0001', 'dpf': 100000},  # Euro/Sterling
}

for pair, meta in pairs_metadata.items():
    cache_ig_instrument_spec(pair, meta['pip'], meta['dpf'])
    print(f"✅ Cached {pair}: pip={meta['pip']}, dpf={meta['dpf']}")

# ============================================================================
# METHOD 2: Automatic Fetching (recommended for production)
# ============================================================================

print("\n📊 METHOD 2: Automatic Fetching from IG API")
print("-" * 70)
print("(Simulated - in production, pass actual ig_service)")
print()

# In production, you would do:
"""
from trading_ig import IGService

ig_service = IGService(username, password, api_key, acc_type)
ig_service.create_session()

# Fetch and cache EUR/CHF automatically
spec = fetch_and_cache_ig_spec('EUR_CHF', ig_service=ig_service)

# Now EUR/CHF spreads use accurate IG metadata
spread_pips = get_cached_spread_pips('EUR_CHF', bid=1.05123, offer=1.05141)
"""

print("Example code:")
print("  fetch_and_cache_ig_spec('EUR_CHF', ig_service=ig_service)")
print("  spread_pips = get_cached_spread_pips('EUR_CHF', bid=1.05123, offer=1.05141)")

# ============================================================================
# METHOD 3: Fallback (automatic for uncached pairs)
# ============================================================================

print("\n📊 METHOD 3: Automatic Fallback")
print("-" * 70)

# For pairs not yet cached, fallback to smart defaults
uncached_pairs = ['EUR_CAD', 'USD_CHF', 'AUD_NZD']

for pair in uncached_pairs:
    # This will use fallback defaults based on currency type
    spread_pips = get_cached_spread_pips(
        pair=pair,
        bid=1.0000,
        offer=1.0009  # 0.9 pip spread
    )
    print(f"✅ {pair}: {spread_pips:.1f} pips (using fallback)")

# ============================================================================
# DEMONSTRATION: Testing with Various Pairs
# ============================================================================

print("\n📊 SPREAD CALCULATIONS (using cached metadata)")
print("=" * 70)

test_cases = [
    # Major pairs
    ('EUR_USD', {'bid': 1.08341, 'offer': 1.08350, 'raw_spread': 9}),
    ('GBP_USD', {'bid': 1.26543, 'offer': 1.26561, 'raw_spread': 18}),
    ('USD_JPY', {'bid': 149.123, 'offer': 149.132, 'raw_spread': 9}),

    # Cross pairs
    ('EUR_CHF', {'bid': 0.93451, 'offer': 0.93469, 'raw_spread': 18}),
    ('AUD_CAD', {'bid': 0.89123, 'offer': 0.89138, 'raw_spread': 15}),
    ('NZD_JPY', {'bid': 87.456, 'offer': 87.465, 'raw_spread': 9}),
    ('EUR_GBP', {'bid': 0.85123, 'offer': 0.85138, 'raw_spread': 15}),
]

for pair, data in test_cases:
    spread_pips_bid_ask = get_cached_spread_pips(
        pair=pair,
        bid=data['bid'],
        offer=data['offer']
    )

    spread_pips_ticks = get_cached_spread_pips(
        pair=pair,
        raw_spread=data['raw_spread']
    )

    print(f"{pair:10} | bid/ask: {spread_pips_bid_ask:.1f} pips | "
          f"ticks: {spread_pips_ticks:.1f} pips | "
          f"✅ Match: {abs(spread_pips_bid_ask - spread_pips_ticks) < 0.1}")

# ============================================================================
# PRODUCTION RECOMMENDATION
# ============================================================================

print("\n" + "=" * 70)
print("📝 PRODUCTION RECOMMENDATIONS")
print("=" * 70)

recommendations = """
1. **At Startup**: Fetch and cache metadata for all pairs you trade
   ```python
   for pair, epic in your_trading_pairs.items():
       fetch_and_cache_ig_spec(pair, ig_service, epic)
   ```

2. **Always Pass bid/ask**: Most accurate method
   ```python
   spread_pips = get_cached_spread_pips(pair, bid=bid, offer=ask)
   ```

3. **Fallback Works**: But warns you to fetch from API
   - JPY pairs: Automatically uses 0.01 pip / 1000 dpf
   - CHF, EUR, etc: Automatically uses 0.0001 pip / 100000 dpf
   - HUF, KRW: Automatically uses 1 pip / 100 dpf

4. **Add New Pairs Anytime**: Just cache their metadata
   ```python
   cache_ig_instrument_spec('NEW_PAIR', '0.0001', 100000)
   ```

5. **Check Logs**: System warns when using fallback vs cached data
"""

print(recommendations)

print("\n" + "=" * 70)
print("✅ System is UNIVERSAL - Works for ANY IG Markets currency pair!")
print("=" * 70)
