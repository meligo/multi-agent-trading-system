"""
Realistic Forex Trading Calculations

Implements professional-grade forex calculations based on industry standards
(MetaTrader, cTrader, institutional platforms).

Core Principles:
1. Buy at ASK, Sell at BID - Spread is paid at both entry and exit
2. Mark-to-Market: Long positions valued at BID, Short at ASK
3. Currency Conversion: Use MID rates when converting P&L to account currency
4. Realistic Execution: Apply slippage, spreads, and swap costs
"""

from typing import Tuple, Dict
import numpy as np
from dataclasses import dataclass


@dataclass
class BidAsk:
    """Bid/Ask price pair."""
    bid: float
    ask: float
    mid: float

    @property
    def spread_pips(self) -> float:
        """Calculate spread in pips."""
        return (self.ask - self.bid) / (0.01 if 'JPY' in str(self) else 0.0001)


# Typical spreads (pips) for major, minor, and exotic pairs
SPREADS = {
    # Majors (1-2 pips typical)
    'EUR_USD': 1.5,
    'GBP_USD': 2.0,
    'USD_JPY': 1.5,
    'AUD_USD': 1.8,
    'USD_CAD': 2.0,
    'USD_CHF': 2.0,
    'NZD_USD': 2.5,

    # Minors (2-4 pips typical)
    'EUR_GBP': 2.5,
    'EUR_JPY': 2.5,
    'GBP_JPY': 3.5,
    'AUD_JPY': 3.0,
    'EUR_CHF': 2.5,
    'EUR_AUD': 3.5,
    'GBP_AUD': 3.5,
    'GBP_CAD': 3.5,
    'GBP_CHF': 3.5,
    'GBP_NZD': 4.0,
    'AUD_CAD': 3.0,
    'AUD_CHF': 3.0,
    'AUD_NZD': 3.0,
    'CAD_CHF': 3.0,
    'CAD_JPY': 3.0,
    'CHF_JPY': 3.0,
    'EUR_CAD': 3.0,
    'EUR_NZD': 4.0,
    'NZD_CAD': 3.5,
    'NZD_CHF': 3.5,
    'NZD_JPY': 3.5,

    # Exotics (5-50 pips)
    'USD_TRY': 25.0,
    'USD_ZAR': 15.0,
    'USD_MXN': 10.0,
}


def get_pip_size(pair: str) -> float:
    """
    Get pip size for a currency pair.

    Args:
        pair: Currency pair (e.g., 'EUR_USD', 'USD_JPY')

    Returns:
        Pip size (0.01 for JPY pairs, 0.0001 for others)
    """
    return 0.01 if 'JPY' in pair else 0.0001


def get_dynamic_spread(pair: str, hour_utc: int = None, atr: float = None) -> float:
    """
    Get dynamic spread based on market conditions.

    Spreads widen during:
    - NY rollover (5pm NY = 21:00-22:00 UTC)
    - Low liquidity (Asian session 0-6 UTC)
    - High volatility (based on ATR)

    Args:
        pair: Currency pair
        hour_utc: Current hour in UTC (0-23)
        atr: Average True Range for volatility adjustment

    Returns:
        Spread in pips
    """
    from datetime import datetime, timezone

    base_spread = SPREADS.get(pair, 2.0)
    multiplier = 1.0

    # Get current hour if not provided
    if hour_utc is None:
        hour_utc = datetime.now(timezone.utc).hour

    # Widen during NY rollover (5pm NY = 21:00 or 22:00 UTC depending on DST)
    if hour_utc in [21, 22]:
        multiplier *= 2.0

    # Widen during low liquidity (Asian session)
    elif 0 <= hour_utc <= 6:
        multiplier *= 1.5

    # Scale with volatility if ATR provided
    if atr is not None:
        pip_size = get_pip_size(pair)
        atr_pips = atr / pip_size
        # If ATR is significantly above normal, widen spread
        normal_atr = base_spread * 10  # Rough estimate
        if atr_pips > normal_atr:
            volatility_factor = min(2.0, atr_pips / normal_atr)
            multiplier *= (1 + (volatility_factor - 1) * 0.3)

    return base_spread * multiplier


def apply_spread(mid_price: float, pair: str, spread_multiplier: float = 1.0,
                 hour_utc: int = None, atr: float = None, use_dynamic: bool = False) -> BidAsk:
    """
    Convert mid price to bid/ask with realistic spread.

    Args:
        mid_price: Mid-market price
        pair: Currency pair
        spread_multiplier: Manual multiplier for spread (e.g., 2.0 for double spread)
        hour_utc: Current hour in UTC for dynamic spread calculation
        atr: Average True Range for volatility-based spread widening
        use_dynamic: Whether to use dynamic spread calculation

    Returns:
        BidAsk object with bid, ask, and mid prices
    """
    pip_size = get_pip_size(pair)

    if use_dynamic:
        spread_pips = get_dynamic_spread(pair, hour_utc, atr)
    else:
        spread_pips = SPREADS.get(pair, 2.0)

    spread_pips *= spread_multiplier

    half_spread = (spread_pips * pip_size) / 2

    bid = mid_price - half_spread
    ask = mid_price + half_spread

    return BidAsk(bid=bid, ask=ask, mid=mid_price)


def get_entry_price(side: str, bid_ask: BidAsk) -> float:
    """
    Get entry price based on order side.

    Args:
        side: 'BUY' or 'SELL'
        bid_ask: BidAsk prices

    Returns:
        Entry price (ASK for BUY, BID for SELL)
    """
    if side == 'BUY':
        return bid_ask.ask  # Buy at ASK
    else:  # SELL
        return bid_ask.bid  # Sell at BID


def get_mark_price(side: str, bid_ask: BidAsk) -> float:
    """
    Get mark-to-market price for position valuation.

    Args:
        side: 'BUY' or 'SELL'
        bid_ask: Current BidAsk prices

    Returns:
        Mark price (BID for long, ASK for short)
    """
    if side == 'BUY':
        return bid_ask.bid  # Long exits at BID
    else:  # SELL
        return bid_ask.ask  # Short exits at ASK


def calculate_unrealized_pnl(
    side: str,
    units: float,
    entry_price: float,
    current_bid_ask: BidAsk,
    quote_currency: str,
    account_currency: str = 'EUR'
) -> float:
    """
    Calculate unrealized P&L for an open position.

    Args:
        side: 'BUY' or 'SELL'
        units: Position size in units
        entry_price: Entry price paid
        current_bid_ask: Current BidAsk prices
        quote_currency: Quote currency of the pair
        account_currency: Account currency (default EUR)

    Returns:
        Unrealized P&L in account currency
    """
    # Get mark price (BID for long, ASK for short)
    mark_price = get_mark_price(side, current_bid_ask)

    # Calculate P&L in quote currency
    if side == 'BUY':
        pnl_quote = units * (mark_price - entry_price)
    else:  # SELL
        pnl_quote = units * (entry_price - mark_price)

    # Convert to account currency
    conversion_rate = get_conversion_rate(quote_currency, account_currency, current_bid_ask.mid)
    pnl_account = pnl_quote * conversion_rate

    return pnl_account


def calculate_realized_pnl(
    side: str,
    units: float,
    entry_price: float,
    exit_bid_ask: BidAsk,
    quote_currency: str,
    account_currency: str = 'EUR'
) -> Tuple[float, float]:
    """
    Calculate realized P&L for a closed position.

    Args:
        side: 'BUY' or 'SELL'
        units: Position size in units
        entry_price: Entry price paid (ASK for BUY, BID for SELL)
        exit_bid_ask: Exit BidAsk prices
        quote_currency: Quote currency of the pair
        account_currency: Account currency (default EUR)

    Returns:
        Tuple of (pnl_account, pnl_pips)
    """
    pip_size = get_pip_size(quote_currency + '_XXX')  # Approximate

    # Get exit price (BID for long, ASK for short)
    exit_price = get_mark_price(side, exit_bid_ask)

    # Calculate P&L in quote currency
    if side == 'BUY':
        pnl_quote = units * (exit_price - entry_price)
        pips = (exit_price - entry_price) / pip_size
    else:  # SELL
        pnl_quote = units * (entry_price - exit_price)
        pips = (entry_price - exit_price) / pip_size

    # Convert to account currency
    conversion_rate = get_conversion_rate(quote_currency, account_currency, exit_bid_ask.mid)
    pnl_account = pnl_quote * conversion_rate

    return pnl_account, pips


def calculate_position_size_risk_based(
    equity_account: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    pair: str,
    account_currency: str = 'EUR'
) -> int:
    """
    Calculate position size to risk exactly X% of equity.

    Example:
        Equity: €50,000
        Risk: 1% = €500
        Entry: 1.10000 (EUR/USD)
        Stop: 1.09500 (50 pips away)

        Result: ~110,000 units (1.1 standard lots)

    Args:
        equity_account: Current equity in account currency
        risk_pct: Risk percentage (e.g., 0.01 for 1%)
        entry_price: Planned entry price
        stop_loss: Stop loss price
        pair: Currency pair (e.g., 'EUR_USD')
        account_currency: Account currency (default EUR)

    Returns:
        Position size in units (rounded to nearest 1000)
    """
    # Stop distance in price
    stop_distance = abs(entry_price - stop_loss)

    # Extract quote currency from pair
    quote_currency = pair.split('_')[1]

    # Get conversion rate (quote currency → account currency)
    # Use entry price as approximate mid rate
    conversion_rate = get_conversion_rate(quote_currency, account_currency, entry_price)

    # Risk per 1 unit in account currency
    risk_per_unit = stop_distance * conversion_rate

    # Calculate units
    risk_amount = equity_account * risk_pct
    units = risk_amount / risk_per_unit

    # Round to minimum step (1000 units = 0.01 lots = micro lot)
    units = round(units / 1000) * 1000

    # Ensure minimum 1000 units
    units = max(1000, units)

    # Cap at reasonable maximum (10 standard lots = 1,000,000 units)
    units = min(1000000, units)

    return int(units)


def get_conversion_rate(from_currency: str, to_currency: str, reference_price: float = 1.0) -> float:
    """
    Get conversion rate from one currency to another.

    This is a simplified version. In production, you would:
    1. Fetch live exchange rates from broker/data provider
    2. Handle all currency combinations properly
    3. Use actual mid rates

    Args:
        from_currency: Source currency (e.g., 'USD')
        to_currency: Target currency (e.g., 'EUR')
        reference_price: Reference price for calculation

    Returns:
        Conversion rate
    """
    # Same currency
    if from_currency == to_currency:
        return 1.0

    # Common conversions (simplified - in production use live rates)
    # These are approximate rates for demonstration
    rates = {
        ('USD', 'EUR'): 0.91,  # 1 USD = 0.91 EUR
        ('EUR', 'USD'): 1.10,  # 1 EUR = 1.10 USD
        ('GBP', 'EUR'): 1.17,  # 1 GBP = 1.17 EUR
        ('EUR', 'GBP'): 0.85,  # 1 EUR = 0.85 GBP
        ('JPY', 'EUR'): 0.0061,  # 1 JPY = 0.0061 EUR
        ('EUR', 'JPY'): 163.0,  # 1 EUR = 163 JPY
        ('AUD', 'EUR'): 0.60,  # 1 AUD = 0.60 EUR
        ('EUR', 'AUD'): 1.67,  # 1 EUR = 1.67 AUD
        ('CAD', 'EUR'): 0.67,  # 1 CAD = 0.67 EUR
        ('EUR', 'CAD'): 1.49,  # 1 EUR = 1.49 CAD
        ('CHF', 'EUR'): 1.06,  # 1 CHF = 1.06 EUR
        ('EUR', 'CHF'): 0.94,  # 1 EUR = 0.94 CHF
        ('NZD', 'EUR'): 0.55,  # 1 NZD = 0.55 EUR
        ('EUR', 'NZD'): 1.82,  # 1 EUR = 1.82 NZD
    }

    pair = (from_currency, to_currency)
    if pair in rates:
        return rates[pair]

    # Try inverse
    inverse_pair = (to_currency, from_currency)
    if inverse_pair in rates:
        return 1.0 / rates[inverse_pair]

    # Cross rates (go through USD or EUR)
    # For simplicity, assume ~1.0 for unknowns (should not happen in production)
    return 1.0


def apply_slippage(
    fill_price: float,
    pair: str,
    spread_pips: float = 2.0,
    atr: float = None,
    is_stop_order: bool = False,
    side: str = 'BUY'
) -> float:
    """
    Add realistic slippage to fill price.

    Market orders: small positive/negative slippage (mean = 0)
    Stop orders: usually negative slippage (mean = worse fill)

    Args:
        fill_price: Expected fill price
        pair: Currency pair
        spread_pips: Current spread in pips
        atr: Average True Range (for volatility adjustment)
        is_stop_order: Whether this is a stop order
        side: 'BUY' or 'SELL'

    Returns:
        Fill price with slippage applied
    """
    pip_size = get_pip_size(pair)

    # Calculate ATR in pips if not provided
    if atr is None:
        atr = spread_pips * pip_size * 5  # Rough estimate

    atr_pips = atr / pip_size

    # Slippage standard deviation
    # σ = base + spread_factor + volatility_factor
    sigma = 0.3 + (spread_pips * 0.1) + (atr_pips * 0.02)

    # Mean slippage
    mean = 0.0

    # Stop orders get worse slippage (biased toward worse fill)
    if is_stop_order:
        sigma *= 1.5
        # Stop orders typically have negative slippage (worse fill)
        # For BUY stop: price goes higher (positive slippage)
        # For SELL stop: price goes lower (negative slippage)
        mean = 0.5 * sigma if side == 'BUY' else -0.5 * sigma

    # Draw from normal distribution
    slippage_pips = np.random.normal(mean, sigma)

    # Cap extreme slippage
    max_slippage = 5 + (2 if is_stop_order else 0)
    slippage_pips = np.clip(slippage_pips, -max_slippage, max_slippage)

    # Apply slippage to price
    slipped_price = fill_price + (slippage_pips * pip_size)

    return slipped_price


def get_realistic_entry_price(
    side: str,
    mid_price: float,
    pair: str,
    atr: float = None,
    use_dynamic_spread: bool = True,
    hour_utc: int = None
) -> Tuple[float, Dict]:
    """
    Get realistic entry price with spread and slippage.

    Args:
        side: 'BUY' or 'SELL'
        mid_price: Mid-market price
        pair: Currency pair
        atr: Average True Range for volatility
        use_dynamic_spread: Whether to use dynamic spreads
        hour_utc: Current hour UTC

    Returns:
        Tuple of (entry_price, details_dict)
    """
    # Apply spread
    bid_ask = apply_spread(mid_price, pair, use_dynamic=use_dynamic_spread,
                          hour_utc=hour_utc, atr=atr)

    # Get base entry price
    base_entry = get_entry_price(side, bid_ask)

    # Calculate spread in pips
    spread_pips = (bid_ask.ask - bid_ask.bid) / get_pip_size(pair)

    # Apply slippage
    final_entry = apply_slippage(
        fill_price=base_entry,
        pair=pair,
        spread_pips=spread_pips,
        atr=atr,
        is_stop_order=False,
        side=side
    )

    details = {
        'mid': mid_price,
        'bid': bid_ask.bid,
        'ask': bid_ask.ask,
        'spread_pips': spread_pips,
        'base_entry': base_entry,
        'final_entry': final_entry,
        'slippage': final_entry - base_entry,
        'slippage_pips': (final_entry - base_entry) / get_pip_size(pair)
    }

    return final_entry, details


def get_realistic_exit_price(
    side: str,
    mid_price: float,
    pair: str,
    atr: float = None,
    is_stop_loss: bool = False,
    use_dynamic_spread: bool = True,
    hour_utc: int = None
) -> Tuple[float, Dict]:
    """
    Get realistic exit price with spread and slippage.

    Args:
        side: Position side 'BUY' or 'SELL'
        mid_price: Mid-market price
        pair: Currency pair
        atr: Average True Range for volatility
        is_stop_loss: Whether this is a stop loss hit
        use_dynamic_spread: Whether to use dynamic spreads
        hour_utc: Current hour UTC

    Returns:
        Tuple of (exit_price, details_dict)
    """
    # Apply spread
    bid_ask = apply_spread(mid_price, pair, use_dynamic=use_dynamic_spread,
                          hour_utc=hour_utc, atr=atr)

    # Get base exit price (opposite side of entry)
    base_exit = get_mark_price(side, bid_ask)

    # Calculate spread in pips
    spread_pips = (bid_ask.ask - bid_ask.bid) / get_pip_size(pair)

    # Apply slippage (opposite side for exit)
    exit_side = 'SELL' if side == 'BUY' else 'BUY'
    final_exit = apply_slippage(
        fill_price=base_exit,
        pair=pair,
        spread_pips=spread_pips,
        atr=atr,
        is_stop_order=is_stop_loss,
        side=exit_side
    )

    details = {
        'mid': mid_price,
        'bid': bid_ask.bid,
        'ask': bid_ask.ask,
        'spread_pips': spread_pips,
        'base_exit': base_exit,
        'final_exit': final_exit,
        'slippage': final_exit - base_exit,
        'slippage_pips': (final_exit - base_exit) / get_pip_size(pair),
        'is_stop_loss': is_stop_loss
    }

    return final_exit, details


def calculate_margin_required(
    units: float,
    pair: str,
    mid_price: float,
    leverage: int = 50
) -> float:
    """
    Calculate margin required to open position.

    Margin = (Notional in account currency) / Leverage

    Args:
        units: Position size in units
        pair: Currency pair
        mid_price: Current mid price
        leverage: Leverage (e.g., 50 for 50:1)

    Returns:
        Margin required in EUR
    """
    quote_currency = pair.split('_')[1]

    # Notional in quote currency
    notional_quote = abs(units) * mid_price

    # Convert to account currency (EUR)
    notional_eur = notional_quote * get_conversion_rate(quote_currency, 'EUR', mid_price)

    # Margin rate = 1 / leverage
    margin_rate = 1.0 / leverage

    margin_required = notional_eur * margin_rate

    return margin_required


def units_to_lots(units: float) -> float:
    """
    Convert units to standard lots.

    Args:
        units: Position size in units

    Returns:
        Position size in lots (1 lot = 100,000 units)
    """
    return units / 100_000


def lots_to_units(lots: float) -> int:
    """
    Convert standard lots to units.

    Args:
        lots: Position size in lots

    Returns:
        Position size in units
    """
    return int(lots * 100_000)


# Test functions
if __name__ == "__main__":
    print("=" * 80)
    print("REALISTIC FOREX CALCULATIONS - TEST")
    print("=" * 80)

    # Test 1: Bid/Ask Spread
    print("\n1. BID/ASK SPREAD")
    print("-" * 80)
    mid = 1.10000
    ba = apply_spread(mid, 'EUR_USD')
    print(f"EUR/USD Mid: {mid:.5f}")
    print(f"Bid: {ba.bid:.5f} | Ask: {ba.ask:.5f}")
    print(f"Spread: {ba.spread_pips:.1f} pips")

    # Test 2: Entry Price
    print("\n2. ENTRY PRICES")
    print("-" * 80)
    print(f"BUY  entry: {get_entry_price('BUY', ba):.5f} (at ASK)")
    print(f"SELL entry: {get_entry_price('SELL', ba):.5f} (at BID)")

    # Test 3: Position Sizing
    print("\n3. POSITION SIZING (Risk-Based)")
    print("-" * 80)
    equity = 50000.0
    risk_pct = 0.01  # 1%
    entry = 1.10000
    stop = 1.09500  # 50 pips

    units = calculate_position_size_risk_based(equity, risk_pct, entry, stop, 'EUR_USD')
    print(f"Equity: €{equity:,.2f}")
    print(f"Risk: {risk_pct*100}% = €{equity*risk_pct:,.2f}")
    print(f"Entry: {entry:.5f} | Stop: {stop:.5f} ({abs(entry-stop)*10000:.0f} pips)")
    print(f"Position size: {units:,} units ({units_to_lots(units):.2f} lots)")

    # Test 4: Unrealized P&L
    print("\n4. UNREALIZED P&L")
    print("-" * 80)
    current_ba = apply_spread(1.10050, 'EUR_USD')  # Price moved up 5 pips

    # Long position
    long_pnl = calculate_unrealized_pnl('BUY', units, ba.ask, current_ba, 'USD', 'EUR')
    print(f"Long position (BUY at {ba.ask:.5f})")
    print(f"Current mark: {current_ba.bid:.5f} (BID)")
    print(f"Unrealized P&L: €{long_pnl:.2f}")

    # Short position
    short_pnl = calculate_unrealized_pnl('SELL', units, ba.bid, current_ba, 'USD', 'EUR')
    print(f"\nShort position (SELL at {ba.bid:.5f})")
    print(f"Current mark: {current_ba.ask:.5f} (ASK)")
    print(f"Unrealized P&L: €{short_pnl:.2f}")

    # Test 5: Realized P&L
    print("\n5. REALIZED P&L (Position Closed)")
    print("-" * 80)
    exit_ba = apply_spread(1.10100, 'EUR_USD')  # Exit at +10 pips from entry

    pnl_eur, pnl_pips = calculate_realized_pnl('BUY', units, ba.ask, exit_ba, 'USD', 'EUR')
    print(f"Long position closed")
    print(f"Entry: {ba.ask:.5f} (ASK) → Exit: {exit_ba.bid:.5f} (BID)")
    print(f"P&L: €{pnl_eur:.2f} ({pnl_pips:.1f} pips)")

    # Test 6: Margin
    print("\n6. MARGIN CALCULATION")
    print("-" * 80)
    margin = calculate_margin_required(units, 'EUR_USD', mid, leverage=50)
    print(f"Position: {units:,} units @ {mid:.5f}")
    print(f"Leverage: 50:1")
    print(f"Margin required: €{margin:,.2f}")
    print(f"Free margin: €{equity - margin:,.2f}")

    print("\n" + "=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)
