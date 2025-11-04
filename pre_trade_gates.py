"""
Pre-Trade Gates - Hard Filters for M1 Scalping

All trades must pass these gates before pattern detection.
Based on GPT-5 recommendations for 10-pip scalps with 6-pip stops.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, time
import pandas as pd
from logging_config import setup_file_logging
from pattern_detectors import calculate_atr, pips_to_price, price_to_pips, get_pip_value
from spread_converter import spread_to_pips as convert_spread_to_pips
from ig_markets_spread import get_ig_spread_pips

logger = setup_file_logging("pre_trade_gates", console_output=False)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class GateConfig:
    """Pre-trade gate configuration."""

    # Spread Gates
    max_spread_pct_of_stop: float = 0.25  # 25% of 6-pip stop = 1.5 pips max
    stop_pips: float = 6.0

    # ATR Regime Gates
    atr_fast_period: int = 14
    atr_slow_period: int = 60
    min_atr_regime_ratio: float = 0.6  # ATR_fast / ATR_slow
    min_atr_pips: Dict[str, float] = None  # Set in __post_init__

    # Session Time Gates (UTC)
    london_core_start: time = time(7, 0)
    london_core_end: time = time(10, 30)
    ny_core_start: time = time(13, 30)
    ny_core_end: time = time(16, 0)
    tokyo_start: time = time(0, 0)  # Optional for USD/JPY
    tokyo_end: time = time(2, 0)

    # HTF Structure Gates
    min_distance_to_htf_pips: float = 6.0  # Minimum clear space to next level

    # News Gates (minutes)
    news_block_before_mins: int = 5
    news_block_after_mins: int = 10

    def __post_init__(self):
        if self.min_atr_pips is None:
            self.min_atr_pips = {
                'EUR_USD': 5.0,
                'GBP_USD': 6.0,
                'USD_JPY': 6.0  # In JPY terms (0.06)
            }


CONFIG = GateConfig()


# ============================================================================
# GATE RESULT
# ============================================================================

@dataclass
class GateResult:
    """Result of gate check."""
    passed: bool
    gate_name: str
    reason: str
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# ============================================================================
# SPREAD GATE
# ============================================================================

def check_spread_gate(
    current_spread: float,
    pair: str,
    bid: Optional[float] = None,
    ask: Optional[float] = None,
    use_ig_markets: bool = True
) -> GateResult:
    """
    Check if spread is acceptable for trading.

    For IG Markets (recommended):
    - Prioritizes bid/ask calculation (most accurate)
    - Falls back to treating spread as SCALED TICKS
    - Formula: pips = SPREAD / (decimalPlacesFactor × pip)

    For other brokers:
    - Uses auto-detection (price/pips/points)

    Args:
        current_spread: Current spread (IG: scaled ticks; others: auto-detect)
        pair: Currency pair
        bid: Bid price (IG Markets: strongly recommended)
        ask: Ask/offer price (IG Markets: strongly recommended)
        use_ig_markets: Use IG-specific conversion (default True)

    Returns:
        GateResult indicating pass/fail
    """
    if use_ig_markets:
        # IG Markets-specific handling
        spread_pips = get_ig_spread_pips(
            pair=pair,
            bid=bid,
            offer=ask,
            raw_spread=current_spread
        )

        if spread_pips is None:
            logger.error(f"❌ {pair}: Could not determine spread (bid={bid}, ask={ask}, raw={current_spread})")
            return GateResult(
                passed=False,
                gate_name="SPREAD",
                reason="No spread data available",
                metadata={'error': 'no_data'}
            )

        conversion_method = "bid/ask" if (bid is not None and ask is not None) else "IG ticks"
        logger.info(f"✅ {pair}: Spread = {spread_pips:.1f} pips (via {conversion_method})")

    else:
        # Generic auto-detection for other brokers
        try:
            spread_pips = convert_spread_to_pips(
                current_spread,
                pair,
                digits=5 if 'JPY' not in pair else 3
            )
            conversion_method = "auto-detect"
        except Exception as e:
            logger.error(f"❌ Spread conversion error for {pair}: {e}")
            spread_pips = price_to_pips(current_spread, pair)
            conversion_method = "fallback"

    max_spread_pips = CONFIG.max_spread_pct_of_stop * CONFIG.stop_pips
    passed = spread_pips <= max_spread_pips

    reason = (f"Spread: {spread_pips:.1f} pips "
             f"{'<=' if passed else '>'} "
             f"{max_spread_pips:.1f} pips max "
             f"({conversion_method})")

    return GateResult(
        passed=passed,
        gate_name="SPREAD",
        reason=reason,
        metadata={
            'spread_pips': spread_pips,
            'spread_raw': current_spread,
            'max_allowed': max_spread_pips,
            'bid': bid,
            'ask': ask,
            'conversion_method': conversion_method
        }
    )


# ============================================================================
# ATR REGIME GATE
# ============================================================================

def check_atr_regime_gate(data: pd.DataFrame, pair: str) -> GateResult:
    """
    Check if market volatility is adequate for scalping.

    Requires:
    1. ATR_fast / ATR_slow >= 0.6 (volatility regime check)
    2. ATR_fast >= minimum pips for pair (absolute volatility check)

    Args:
        data: OHLCV dataframe
        pair: Currency pair

    Returns:
        GateResult indicating pass/fail
    """
    if len(data) < CONFIG.atr_slow_period:
        return GateResult(
            passed=False,
            gate_name="ATR_REGIME",
            reason=f"Insufficient data: {len(data)} bars < {CONFIG.atr_slow_period} required",
            metadata={'data_bars': len(data)}
        )

    atr_fast = calculate_atr(data, CONFIG.atr_fast_period)
    atr_slow = calculate_atr(data, CONFIG.atr_slow_period)

    if atr_slow == 0:
        return GateResult(
            passed=False,
            gate_name="ATR_REGIME",
            reason="ATR_slow is zero (no volatility)",
            metadata={'atr_fast': atr_fast, 'atr_slow': atr_slow}
        )

    atr_ratio = atr_fast / atr_slow
    atr_fast_pips = price_to_pips(atr_fast, pair)
    min_atr_required = CONFIG.min_atr_pips.get(pair, 5.0)

    # Check both conditions
    ratio_ok = atr_ratio >= CONFIG.min_atr_regime_ratio
    absolute_ok = atr_fast_pips >= min_atr_required

    passed = ratio_ok and absolute_ok

    if not ratio_ok:
        reason = f"ATR regime too low: {atr_ratio:.2f} < {CONFIG.min_atr_regime_ratio}"
    elif not absolute_ok:
        reason = f"ATR too low: {atr_fast_pips:.1f} pips < {min_atr_required:.1f} required"
    else:
        reason = f"ATR regime OK: {atr_ratio:.2f}, {atr_fast_pips:.1f} pips"

    return GateResult(
        passed=passed,
        gate_name="ATR_REGIME",
        reason=reason,
        metadata={
            'atr_fast_pips': atr_fast_pips,
            'atr_slow_pips': price_to_pips(atr_slow, pair),
            'atr_ratio': atr_ratio,
            'min_required_pips': min_atr_required
        }
    )


# ============================================================================
# SESSION TIME GATE
# ============================================================================

def check_session_gate(current_time: datetime, pair: str) -> GateResult:
    """
    Check if current time is within active trading sessions.

    Active sessions (UTC):
    - London core: 07:00-10:30
    - NY core: 13:30-16:00
    - Tokyo (USD/JPY only): 00:00-02:00

    Args:
        current_time: Current datetime (should be UTC)
        pair: Currency pair

    Returns:
        GateResult indicating pass/fail
    """
    time_utc = current_time.time()

    # Check London session
    if CONFIG.london_core_start <= time_utc <= CONFIG.london_core_end:
        return GateResult(
            passed=True,
            gate_name="SESSION",
            reason=f"London core session ({time_utc})",
            metadata={'session': 'LONDON', 'time_utc': str(time_utc)}
        )

    # Check NY session
    if CONFIG.ny_core_start <= time_utc <= CONFIG.ny_core_end:
        return GateResult(
            passed=True,
            gate_name="SESSION",
            reason=f"NY core session ({time_utc})",
            metadata={'session': 'NY', 'time_utc': str(time_utc)}
        )

    # Check Tokyo session (USD/JPY only)
    if pair == 'USD_JPY':
        if CONFIG.tokyo_start <= time_utc <= CONFIG.tokyo_end:
            return GateResult(
                passed=True,
                gate_name="SESSION",
                reason=f"Tokyo session (USD/JPY) ({time_utc})",
                metadata={'session': 'TOKYO', 'time_utc': str(time_utc)}
            )

    return GateResult(
        passed=False,
        gate_name="SESSION",
        reason=f"Outside active sessions ({time_utc} UTC)",
        metadata={'time_utc': str(time_utc), 'pair': pair}
    )


# ============================================================================
# HTF STRUCTURE GATE
# ============================================================================

def check_htf_distance_gate(data: pd.DataFrame, pair: str, direction: str,
                             entry_price: float, target_pips: float = 10.0) -> GateResult:
    """
    Check if there's enough distance to next HTF level.

    Looks for:
    - Recent swing highs/lows
    - Round numbers (.00, .50)
    - Previous day high/low

    Args:
        data: OHLCV dataframe
        pair: Currency pair
        direction: 'BUY' or 'SELL'
        entry_price: Proposed entry price
        target_pips: Target in pips (default 10)

    Returns:
        GateResult indicating pass/fail
    """
    if len(data) < 50:
        return GateResult(
            passed=True,  # Don't block if insufficient data
            gate_name="HTF_DISTANCE",
            reason="Insufficient data for HTF check (passed by default)",
            metadata={'data_bars': len(data)}
        )

    # Find nearest resistance/support
    if direction == 'BUY':
        # Look for resistance above
        recent_highs = data['high'].iloc[-50:].sort_values(ascending=False).head(5)
        nearest_level = recent_highs[recent_highs > entry_price].min()

        # Check round numbers above
        pip_value = get_pip_value(pair)
        if 'JPY' in pair:
            round_level = (int(entry_price / 0.50) + 1) * 0.50  # Next .50 level
        else:
            round_level = (int(entry_price / 0.0050) + 1) * 0.0050  # Next .0050 level

        if pd.notna(nearest_level):
            nearest_level = min(nearest_level, round_level)
        else:
            nearest_level = round_level

    else:  # SELL
        # Look for support below
        recent_lows = data['low'].iloc[-50:].sort_values(ascending=True).head(5)
        nearest_level = recent_lows[recent_lows < entry_price].max()

        # Check round numbers below
        if 'JPY' in pair:
            round_level = int(entry_price / 0.50) * 0.50  # Previous .50 level
        else:
            round_level = int(entry_price / 0.0050) * 0.0050  # Previous .0050 level

        if pd.notna(nearest_level):
            nearest_level = max(nearest_level, round_level)
        else:
            nearest_level = round_level

    # Calculate distance
    distance_pips = abs(price_to_pips(nearest_level - entry_price, pair))
    required_distance = max(CONFIG.min_distance_to_htf_pips, target_pips * 0.6)

    passed = distance_pips >= required_distance

    reason = (f"HTF distance: {distance_pips:.1f} pips "
             f"{'>==' if passed else '<'} "
             f"{required_distance:.1f} pips required")

    return GateResult(
        passed=passed,
        gate_name="HTF_DISTANCE",
        reason=reason,
        metadata={
            'distance_pips': distance_pips,
            'required_pips': required_distance,
            'nearest_level': nearest_level,
            'entry_price': entry_price,
            'direction': direction
        }
    )


# ============================================================================
# NEWS GATE
# ============================================================================

# For now, we'll implement a simple time-based blocker
# In production, this should connect to an economic calendar API

KNOWN_NEWS_TIMES_UTC = [
    # US NFP (First Friday, 08:30 ET = 13:30 UTC)
    time(13, 30),
    # US CPI (monthly, 08:30 ET = 13:30 UTC)
    time(13, 30),
    # Fed Rate Decision (usually 14:00 ET = 19:00 UTC)
    time(19, 0),
    # ECB Rate Decision (usually 12:45 UTC)
    time(12, 45),
    # BOE Rate Decision (usually 12:00 UTC)
    time(12, 0),
]


def check_news_gate(current_time: datetime) -> GateResult:
    """
    Check if trading is blocked due to upcoming news.

    This is a simplified implementation. In production, should use:
    - ForexFactory API
    - Investing.com calendar
    - Or similar real-time economic calendar

    Args:
        current_time: Current datetime (UTC)

    Returns:
        GateResult indicating pass/fail
    """
    time_utc = current_time.time()
    current_mins = time_utc.hour * 60 + time_utc.minute

    for news_time in KNOWN_NEWS_TIMES_UTC:
        news_mins = news_time.hour * 60 + news_time.minute

        # Check if within blocked window
        if (news_mins - CONFIG.news_block_before_mins <= current_mins <=
            news_mins + CONFIG.news_block_after_mins):
            return GateResult(
                passed=False,
                gate_name="NEWS",
                reason=f"News block: {CONFIG.news_block_before_mins}min before to "
                       f"{CONFIG.news_block_after_mins}min after {news_time}",
                metadata={
                    'current_time': str(time_utc),
                    'news_time': str(news_time),
                    'minutes_to_news': news_mins - current_mins
                }
            )

    return GateResult(
        passed=True,
        gate_name="NEWS",
        reason="No major news events imminent",
        metadata={'current_time': str(time_utc)}
    )


# ============================================================================
# MAIN GATE CHECKER
# ============================================================================

def check_all_gates(data: pd.DataFrame, pair: str, current_spread: float,
                    current_time: datetime, direction: Optional[str] = None,
                    entry_price: Optional[float] = None,
                    bid: Optional[float] = None,
                    ask: Optional[float] = None,
                    use_ig_markets: bool = True) -> Tuple[bool, List[GateResult]]:
    """
    Check all pre-trade gates.

    Args:
        data: OHLCV dataframe
        pair: Currency pair
        current_spread: Current spread (IG: scaled ticks; others: auto-detect)
        current_time: Current datetime (UTC)
        direction: Trade direction ('BUY' or 'SELL') - optional for HTF check
        entry_price: Proposed entry price - optional for HTF check
        bid: Bid price (IG Markets: strongly recommended)
        ask: Ask/offer price (IG Markets: strongly recommended)
        use_ig_markets: Use IG-specific conversion (default True)

    Returns:
        Tuple of (all_passed: bool, results: List[GateResult])
    """
    results = []

    # Gate 1: Spread (IG Markets-aware)
    spread_result = check_spread_gate(
        current_spread,
        pair,
        bid=bid,
        ask=ask,
        use_ig_markets=use_ig_markets
    )
    results.append(spread_result)

    # Gate 2: ATR Regime
    atr_result = check_atr_regime_gate(data, pair)
    results.append(atr_result)

    # Gate 3: Session Time
    session_result = check_session_gate(current_time, pair)
    results.append(session_result)

    # Gate 4: News
    news_result = check_news_gate(current_time)
    results.append(news_result)

    # Gate 5: HTF Distance (optional - only if direction/entry provided)
    if direction and entry_price:
        htf_result = check_htf_distance_gate(data, pair, direction, entry_price)
        results.append(htf_result)

    # Check if all passed
    all_passed = all(r.passed for r in results)

    # Log results
    if all_passed:
        logger.info(f"✅ All pre-trade gates PASSED for {pair}")
    else:
        failed = [r for r in results if not r.passed]
        logger.info(f"❌ Pre-trade gates FAILED for {pair}: {[r.gate_name for r in failed]}")
        for r in failed:
            logger.info(f"   - {r.gate_name}: {r.reason}")

    return all_passed, results


def format_gate_results(results: List[GateResult]) -> str:
    """Format gate results for display."""
    lines = []
    lines.append("\n" + "="*70)
    lines.append("PRE-TRADE GATE CHECK")
    lines.append("="*70)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        lines.append(f"{status} | {result.gate_name:15} | {result.reason}")

    lines.append("="*70)

    all_passed = all(r.passed for r in results)
    final_status = "✅ ALL GATES PASSED - TRADING ALLOWED" if all_passed else "❌ GATES FAILED - TRADING BLOCKED"
    lines.append(final_status)
    lines.append("="*70)

    return "\n".join(lines)
