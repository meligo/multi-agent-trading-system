"""
IG Markets Spread Conversion
Based on GPT-5 analysis - January 2025

IG Markets sends spread data as SCALED TICKS (not price units).
Formula: pips = SPREAD / (decimalPlacesFactor × pip)

Key points:
- Always prefer computing spread from bid/ask when available
- IG's SPREAD field is an integer representing ticks (minimum price increments)
- EUR/USD, GBP/USD: 5-digit (decimalPlacesFactor=100000, pip=0.0001)
- USD/JPY: 3-digit (decimalPlacesFactor=1000, pip=0.01)
"""

from decimal import Decimal, getcontext
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from logging_config import setup_file_logging

# Set precision for Decimal calculations
getcontext().prec = 16

logger = setup_file_logging("ig_markets_spread", console_output=False)


@dataclass
class IGInstrumentSpec:
    """IG Markets instrument specification."""
    pair: str
    pip: Decimal  # e.g., Decimal("0.0001") for EUR/USD, Decimal("0.01") for USD/JPY
    decimal_places_factor: Decimal  # e.g., 100000 for 5-digit, 1000 for 3-digit

    @classmethod
    def from_pair(cls, pair: str, warn: bool = True) -> 'IGInstrumentSpec':
        """
        Create spec from currency pair using FALLBACK defaults.

        **WARNING**: This is FALLBACK ONLY! For production, always fetch from IG API.

        Fallback rules (based on currency type):
        - JPY pairs: 3-digit (pip=0.01, dpf=1000)
        - HUF, KRW pairs: 2-digit (pip=1, dpf=100)  # High-value currencies
        - Major FX: 5-digit (pip=0.0001, dpf=100000)

        For production, ALWAYS fetch from IG API:
        ```python
        market = ig_service.fetch_market_by_epic(epic)
        pip = market["instrument"]["pip"]
        dpf = market["instrument"]["decimalPlacesFactor"]
        spec = IGInstrumentSpec(pair, Decimal(pip), Decimal(dpf))
        ```

        Args:
            pair: Currency pair (e.g., 'EUR_USD', 'USD_JPY', 'EUR_CHF')
            warn: Log warning about using fallback (default True)

        Returns:
            IGInstrumentSpec with fallback values
        """
        pair_upper = pair.upper().replace('_', '').replace('/', '')

        if warn:
            logger.warning(f"⚠️  {pair}: Using FALLBACK spec. "
                          "For production, fetch metadata from IG Markets API!")

        # High-value currencies (quoted in whole units)
        if any(curr in pair_upper for curr in ['HUF', 'KRW']):
            return cls(
                pair=pair,
                pip=Decimal("1"),
                decimal_places_factor=Decimal("100")
            )

        # JPY pairs (2-digit pip, 3-digit quotes)
        elif 'JPY' in pair_upper:
            return cls(
                pair=pair,
                pip=Decimal("0.01"),
                decimal_places_factor=Decimal("1000")
            )

        # All other FX (5-digit quotes)
        else:
            return cls(
                pair=pair,
                pip=Decimal("0.0001"),
                decimal_places_factor=Decimal("100000")
            )


class IGSpreadNormalizer:
    """
    IG Markets spread normalizer.

    Handles IG's specific format where SPREAD is a scaled integer (ticks).
    """

    def __init__(self, spec: IGInstrumentSpec):
        self.spec = spec
        self.pair = spec.pair

    def pips_from_bid_offer(self, bid: Optional[float], offer: Optional[float]) -> Optional[Decimal]:
        """
        Compute spread in pips from bid and offer prices.

        This is the PREFERRED method for IG Markets.

        Args:
            bid: Bid price (e.g., 1.08341)
            offer: Offer/ask price (e.g., 1.08350)

        Returns:
            Spread in pips, or None if bid/offer not available
        """
        if bid is None or offer is None:
            return None

        bid_dec = Decimal(str(bid))
        offer_dec = Decimal(str(offer))

        if offer_dec <= bid_dec:
            logger.warning(f"⚠️  {self.pair}: Offer <= Bid ({offer_dec} <= {bid_dec})")
            return Decimal("0")

        spread_price = offer_dec - bid_dec
        spread_pips = spread_price / self.spec.pip

        logger.debug(f"✅ {self.pair}: Spread from bid/ask = {float(spread_pips):.1f} pips "
                    f"(bid={bid}, ask={offer})")

        return spread_pips

    def pips_from_scaled_spread(self, raw_spread: Optional[float]) -> Optional[Decimal]:
        """
        Convert IG's scaled SPREAD field (ticks) to pips.

        IG sends SPREAD as an integer representing ticks (scaled price units).
        Formula: pips = SPREAD / (decimalPlacesFactor × pip)

        Example EUR/USD (decimalPlacesFactor=100000, pip=0.0001):
        - SPREAD=9 → 9 / (100000 × 0.0001) = 9 / 10 = 0.9 pips
        - SPREAD=60 → 60 / (100000 × 0.0001) = 60 / 10 = 6.0 pips

        Args:
            raw_spread: IG's SPREAD field value (integer ticks)

        Returns:
            Spread in pips, or None if raw_spread not available
        """
        if raw_spread is None:
            return None

        spread_ticks = Decimal(str(raw_spread))

        # IG formula: pips = SPREAD / (decimalPlacesFactor × pip)
        denominator = self.spec.decimal_places_factor * self.spec.pip
        spread_pips = spread_ticks / denominator

        logger.debug(f"✅ {self.pair}: Spread from IG ticks = {float(spread_pips):.1f} pips "
                    f"(raw_spread={raw_spread}, dpf={self.spec.decimal_places_factor})")

        return spread_pips

    def get_spread_pips(
        self,
        bid: Optional[float] = None,
        offer: Optional[float] = None,
        raw_spread: Optional[float] = None,
        sanity_max_pips: float = 50.0
    ) -> Optional[float]:
        """
        Get spread in pips using the best available method.

        Priority:
        1. Compute from bid/offer (most reliable for IG)
        2. Convert from raw_spread if available
        3. Return None if no data

        Args:
            bid: Bid price
            offer: Offer/ask price
            raw_spread: IG's SPREAD field (scaled ticks)
            sanity_max_pips: Maximum plausible spread (default 50)

        Returns:
            Spread in pips as float, or None
        """
        # Method 1: Bid/Offer (preferred)
        pips = self.pips_from_bid_offer(bid, offer)
        if pips is not None:
            pips_float = float(pips)
            if pips_float > sanity_max_pips:
                logger.warning(f"⚠️  {self.pair}: Suspicious spread from bid/ask: {pips_float:.1f} pips "
                             f"(bid={bid}, ask={offer})")
            return pips_float

        # Method 2: Raw spread (scaled ticks)
        pips = self.pips_from_scaled_spread(raw_spread)
        if pips is not None:
            pips_float = float(pips)
            if pips_float > sanity_max_pips:
                logger.warning(f"⚠️  {self.pair}: Suspicious spread from IG ticks: {pips_float:.1f} pips "
                             f"(raw_spread={raw_spread})")
            return pips_float

        logger.warning(f"⚠️  {self.pair}: No spread data available (bid={bid}, offer={offer}, raw={raw_spread})")
        return None


# Convenience functions for quick integration

def get_ig_spread_pips(
    pair: str,
    bid: Optional[float] = None,
    offer: Optional[float] = None,
    raw_spread: Optional[float] = None,
    instrument_pip: Optional[str] = None,
    instrument_dpf: Optional[int] = None
) -> Optional[float]:
    """
    Quick function to get IG Markets spread in pips.

    Args:
        pair: Currency pair (e.g., 'EUR_USD', 'USD_JPY')
        bid: Bid price
        offer: Offer/ask price
        raw_spread: IG's SPREAD field (scaled ticks)
        instrument_pip: Override pip size (e.g., "0.0001")
        instrument_dpf: Override decimalPlacesFactor (e.g., 100000)

    Returns:
        Spread in pips, or None
    """
    # Create or override spec
    if instrument_pip and instrument_dpf:
        spec = IGInstrumentSpec(
            pair=pair,
            pip=Decimal(instrument_pip),
            decimal_places_factor=Decimal(str(instrument_dpf))
        )
    else:
        spec = IGInstrumentSpec.from_pair(pair)

    normalizer = IGSpreadNormalizer(spec)
    return normalizer.get_spread_pips(bid, offer, raw_spread)


# Instrument metadata cache (fetch from IG API in production)
IG_INSTRUMENT_CACHE: Dict[str, IGInstrumentSpec] = {}


def cache_ig_instrument_spec(pair: str, pip: str, decimal_places_factor: int):
    """
    Cache instrument specification fetched from IG Markets API.

    In production, call this once per epic:
    ```python
    market = ig_service.fetch_market_by_epic(epic)
    pip = market["instrument"]["pip"]
    dpf = market["instrument"]["decimalPlacesFactor"]
    cache_ig_instrument_spec(pair, pip, dpf)
    ```

    Args:
        pair: Currency pair (e.g., 'EUR_USD')
        pip: Pip size as string (e.g., "0.0001")
        decimal_places_factor: Scale factor as int (e.g., 100000)
    """
    spec = IGInstrumentSpec(
        pair=pair,
        pip=Decimal(pip),
        decimal_places_factor=Decimal(str(decimal_places_factor))
    )
    pair_key = pair.upper().replace('_', '').replace('/', '')
    IG_INSTRUMENT_CACHE[pair_key] = spec
    logger.info(f"✅ Cached IG instrument spec for {pair}: pip={pip}, dpf={decimal_places_factor}")


def fetch_and_cache_ig_spec(pair: str, ig_service=None, epic: str = None) -> Optional[IGInstrumentSpec]:
    """
    Fetch instrument specification from IG Markets API and cache it.

    This is the RECOMMENDED way to get accurate specs for ANY currency pair.

    Args:
        pair: Currency pair (e.g., 'EUR_USD', 'AUD_CAD', 'EUR_CHF')
        ig_service: IG Markets service instance (from trading-ig library)
        epic: IG epic identifier (if different from pair)

    Returns:
        IGInstrumentSpec if successful, None if fetch failed

    Example:
        ```python
        from trading_ig import IGService
        from ig_markets_spread import fetch_and_cache_ig_spec

        ig_service = IGService(username, password, api_key, acc_type)
        ig_service.create_session()

        # Fetch and cache EUR/CHF
        spec = fetch_and_cache_ig_spec('EUR_CHF', ig_service)

        # Now spreads for EUR/CHF will use accurate metadata
        spread_pips = get_cached_spread_pips('EUR_CHF', bid=1.05123, offer=1.05141)
        ```
    """
    if ig_service is None:
        logger.error(f"❌ {pair}: Cannot fetch spec - ig_service not provided")
        return None

    try:
        # Convert pair to epic format if not provided
        if epic is None:
            # IG Markets typically uses format like 'CS.D.EURCHF.TODAY.IP'
            # This is simplified - you may need to adjust based on your epic naming
            epic_base = pair.upper().replace('_', '').replace('/', '')
            epic = f"CS.D.{epic_base}.TODAY.IP"  # Example format

        logger.info(f"🔍 {pair}: Fetching instrument spec from IG Markets (epic={epic})...")

        # Fetch market data from IG API
        market = ig_service.fetch_market_by_epic(epic)

        # Extract pip and decimalPlacesFactor
        instrument = market.get("instrument", {})
        pip = instrument.get("pip")
        dpf = instrument.get("decimalPlacesFactor") or instrument.get("scalingFactor")

        if pip is None or dpf is None:
            logger.error(f"❌ {pair}: Missing pip={pip} or dpf={dpf} in IG API response")
            return None

        # Cache it
        cache_ig_instrument_spec(pair, pip, dpf)

        return IG_INSTRUMENT_CACHE[pair.upper().replace('_', '').replace('/', '')]

    except Exception as e:
        logger.error(f"❌ {pair}: Failed to fetch from IG Markets: {e}")
        return None


def get_or_fetch_spec(
    pair: str,
    ig_service=None,
    epic: str = None,
    use_fallback: bool = True
) -> IGInstrumentSpec:
    """
    Get instrument spec from cache, fetch from IG API, or use fallback.

    Priority order:
    1. Return from cache if available
    2. Fetch from IG Markets API if ig_service provided
    3. Use fallback defaults if use_fallback=True
    4. Raise error if no spec available

    Args:
        pair: Currency pair
        ig_service: Optional IG Markets service for API fetch
        epic: Optional IG epic identifier
        use_fallback: Allow fallback to defaults (default True)

    Returns:
        IGInstrumentSpec

    Raises:
        ValueError: If no spec available and use_fallback=False
    """
    pair_key = pair.upper().replace('_', '').replace('/', '')

    # 1. Check cache first
    if pair_key in IG_INSTRUMENT_CACHE:
        logger.debug(f"✅ {pair}: Using cached spec")
        return IG_INSTRUMENT_CACHE[pair_key]

    # 2. Try to fetch from IG API
    if ig_service is not None:
        spec = fetch_and_cache_ig_spec(pair, ig_service, epic)
        if spec is not None:
            return spec

    # 3. Use fallback
    if use_fallback:
        logger.warning(f"⚠️  {pair}: Using fallback spec (not fetched from IG)")
        return IGInstrumentSpec.from_pair(pair, warn=False)  # Already warned above

    # 4. No spec available
    raise ValueError(f"No instrument spec available for {pair} and use_fallback=False")


def get_cached_spread_pips(
    pair: str,
    bid: Optional[float] = None,
    offer: Optional[float] = None,
    raw_spread: Optional[float] = None
) -> Optional[float]:
    """
    Get spread using cached instrument specification.

    Falls back to standard spec if not cached.
    """
    pair_key = pair.upper().replace('_', '').replace('/', '')

    if pair_key in IG_INSTRUMENT_CACHE:
        spec = IG_INSTRUMENT_CACHE[pair_key]
    else:
        spec = IGInstrumentSpec.from_pair(pair)
        logger.warning(f"⚠️  {pair}: Using default spec (not cached). "
                      "Consider fetching from IG API for accuracy.")

    normalizer = IGSpreadNormalizer(spec)
    return normalizer.get_spread_pips(bid, offer, raw_spread)


if __name__ == "__main__":
    print("=" * 70)
    print("IG Markets Spread Conversion Tests")
    print("=" * 70)

    # EUR/USD tests
    print("\n📊 EUR/USD (5-digit, decimalPlacesFactor=100000, pip=0.0001)")
    spec_eur = IGInstrumentSpec.from_pair("EUR_USD")
    ig_eur = IGSpreadNormalizer(spec_eur)

    print(f"  From bid/ask: {ig_eur.get_spread_pips(bid=1.08341, offer=1.08350):.1f} pips")
    print(f"  From ticks (9): {ig_eur.get_spread_pips(raw_spread=9):.1f} pips")
    print(f"  From ticks (60): {ig_eur.get_spread_pips(raw_spread=60):.1f} pips")

    # USD/JPY tests
    print("\n📊 USD/JPY (3-digit, decimalPlacesFactor=1000, pip=0.01)")
    spec_jpy = IGInstrumentSpec.from_pair("USD_JPY")
    ig_jpy = IGSpreadNormalizer(spec_jpy)

    print(f"  From bid/ask: {ig_jpy.get_spread_pips(bid=149.123, offer=149.132):.1f} pips")
    print(f"  From ticks (9): {ig_jpy.get_spread_pips(raw_spread=9):.1f} pips")
    print(f"  From ticks (60): {ig_jpy.get_spread_pips(raw_spread=60):.1f} pips")

    # GBP/USD tests
    print("\n📊 GBP/USD (5-digit, decimalPlacesFactor=100000, pip=0.0001)")
    spec_gbp = IGInstrumentSpec.from_pair("GBP_USD")
    ig_gbp = IGSpreadNormalizer(spec_gbp)

    print(f"  From bid/ask: {ig_gbp.get_spread_pips(bid=1.26543, offer=1.26561):.1f} pips")
    print(f"  From ticks (18): {ig_gbp.get_spread_pips(raw_spread=18):.1f} pips")

    # Test convenience function
    print("\n📊 Convenience function tests")
    print(f"  EUR_USD (bid/ask): {get_ig_spread_pips('EUR_USD', bid=1.08341, offer=1.08350):.1f} pips")
    print(f"  EUR_USD (ticks=9): {get_ig_spread_pips('EUR_USD', raw_spread=9):.1f} pips")
    print(f"  USD_JPY (ticks=12): {get_ig_spread_pips('USD_JPY', raw_spread=12):.1f} pips")

    print("\n" + "=" * 70)
    print("✅ All tests complete!")
    print("=" * 70)
