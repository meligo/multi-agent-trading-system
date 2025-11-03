#!/usr/bin/env python3
"""
Dynamic Stop Loss / Take Profit Calculator

Implements research-backed dynamic SL/TP methods for forex scalping:
1. Volatility scaling (ATR-based)
2. Market structure anchoring (swings, pivots, round numbers)
3. Time governance (timeouts, decay)
4. Trailing stops (Chandelier method)

References:
- Kaminski & Lo (2014) - Adaptive stop-loss rules
- Moreira & Muir (2017) - Volatility management
- Kissell (2013) - Algorithmic trading
- Kase (1996) - Dev-Stop method
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class SLTPLevels:
    """Stop Loss and Take Profit levels with metadata."""
    sl_price: float
    tp_price: float
    sl_pips: float
    tp_pips: float
    method: str  # 'volatility', 'structure', 'hybrid'
    confidence: float  # 0-1, how confident we are in these levels
    metadata: Dict  # Additional info (ATR value, structure levels, etc.)


class DynamicSLTPCalculator:
    """
    Calculate dynamic Stop Loss and Take Profit levels.

    Uses three-layer approach:
    1. Volatility-based baseline
    2. Market structure adjustment
    3. Time-based governance
    """

    def __init__(self,
                 atr_period: int = 14,
                 atr_mult_sl: float = 0.8,
                 atr_mult_tp: float = 1.2,
                 atr_mult_trail: float = 1.0,
                 buffer_spread_mult: float = 1.5,
                 buffer_atr_mult: float = 0.1,
                 timeout_minutes: int = 12,
                 time_decay_lambda: float = 1.2,
                 breakeven_trigger: float = 0.6):
        """
        Initialize calculator with research-backed parameters.

        Args:
            atr_period: Lookback period for ATR (default: 14 bars)
            atr_mult_sl: Multiplier for SL distance (default: 0.8)
            atr_mult_tp: Multiplier for TP distance (default: 1.2)
            atr_mult_trail: Multiplier for trailing stop (default: 1.0)
            buffer_spread_mult: Spread buffer multiplier (default: 1.5)
            buffer_atr_mult: ATR buffer multiplier (default: 0.1)
            timeout_minutes: Max trade duration (default: 12 min)
            time_decay_lambda: Time decay rate (default: 1.2)
            breakeven_trigger: Move to BE trigger (default: 0.6 × ATR)
        """
        # Volatility parameters
        self.atr_period = atr_period
        self.atr_mult_sl = atr_mult_sl
        self.atr_mult_tp = atr_mult_tp
        self.atr_mult_trail = atr_mult_trail

        # Buffer parameters
        self.buffer_spread_mult = buffer_spread_mult
        self.buffer_atr_mult = buffer_atr_mult

        # Time governance
        self.timeout_minutes = timeout_minutes
        self.time_decay_lambda = time_decay_lambda

        # Break-even
        self.breakeven_trigger = breakeven_trigger

        # JPY pair detection
        self.jpy_pairs = ['USD_JPY', 'EUR_JPY', 'GBP_JPY', 'AUD_JPY', 'NZD_JPY', 'CAD_JPY', 'CHF_JPY']

    def calculate_atr(self, candles: List[Dict]) -> float:
        """
        Calculate Average True Range from candle data.

        Args:
            candles: List of candle dicts with 'high', 'low', 'close'

        Returns:
            ATR value (in price units, not pips)
        """
        if len(candles) < 2:
            return 0.0

        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            close_prev = candles[i-1]['close']

            tr = max(
                high - low,
                abs(high - close_prev),
                abs(low - close_prev)
            )
            true_ranges.append(tr)

        # EMA of True Range
        if len(true_ranges) == 0:
            return 0.0

        # Simple average if not enough data for EMA
        if len(true_ranges) < self.atr_period:
            return np.mean(true_ranges)

        # Calculate EMA
        alpha = 2.0 / (self.atr_period + 1)
        ema = true_ranges[0]
        for tr in true_ranges[1:]:
            ema = alpha * tr + (1 - alpha) * ema

        return ema

    def find_swing_levels(self, candles: List[Dict], lookback: int = 20) -> Tuple[float, float]:
        """
        Find recent swing high and swing low (fractals).

        Args:
            candles: List of candle dicts
            lookback: Bars to look back for swings

        Returns:
            (swing_low, swing_high) tuple
        """
        if len(candles) < lookback:
            lookback = len(candles)

        recent_candles = candles[-lookback:]

        swing_low = min(c['low'] for c in recent_candles)
        swing_high = max(c['high'] for c in recent_candles)

        return swing_low, swing_high

    def calculate_pivots(self, prev_day_high: float, prev_day_low: float, prev_day_close: float) -> Dict[str, float]:
        """
        Calculate daily pivot levels.

        Args:
            prev_day_high: Previous day's high
            prev_day_low: Previous day's low
            prev_day_close: Previous day's close

        Returns:
            Dict with pivot, r1, r2, r3, s1, s2, s3
        """
        pivot = (prev_day_high + prev_day_low + prev_day_close) / 3.0

        return {
            'pivot': pivot,
            'r1': 2 * pivot - prev_day_low,
            'r2': pivot + (prev_day_high - prev_day_low),
            'r3': prev_day_high + 2 * (pivot - prev_day_low),
            's1': 2 * pivot - prev_day_high,
            's2': pivot - (prev_day_high - prev_day_low),
            's3': prev_day_low - 2 * (prev_day_high - pivot)
        }

    def get_nearest_round_number(self, price: float, pair: str) -> Tuple[float, float]:
        """
        Find nearest round numbers (00/50 levels).

        Args:
            price: Current price
            pair: Currency pair

        Returns:
            (level_below, level_above) tuple
        """
        is_jpy = pair in self.jpy_pairs

        if is_jpy:
            # JPY: Round to 0.50 levels (e.g., 154.00, 154.50)
            step = 0.50
            level_below = np.floor(price / step) * step
            level_above = np.ceil(price / step) * step
        else:
            # Standard: Round to 0.0050 levels (e.g., 1.3000, 1.3050)
            step = 0.0050
            level_below = np.floor(price / step) * step
            level_above = np.ceil(price / step) * step

        return level_below, level_above

    def price_to_pips(self, price_distance: float, pair: str) -> float:
        """Convert price distance to pips."""
        is_jpy = pair in self.jpy_pairs
        pip_value = 0.01 if is_jpy else 0.0001
        return price_distance / pip_value

    def pips_to_price(self, pips: float, pair: str) -> float:
        """Convert pips to price distance."""
        is_jpy = pair in self.jpy_pairs
        pip_value = 0.01 if is_jpy else 0.0001
        return pips * pip_value

    def calculate_buffer(self, atr: float, spread: float, pair: str) -> float:
        """
        Calculate buffer distance to avoid stop-runs.

        Args:
            atr: Current ATR value
            spread: Current spread in pips
            pair: Currency pair

        Returns:
            Buffer distance in price units
        """
        spread_price = self.pips_to_price(spread, pair)
        buffer_price = (
            self.buffer_spread_mult * spread_price +
            self.buffer_atr_mult * atr
        )
        return buffer_price

    def calculate_sltp(self,
                      entry_price: float,
                      direction: str,  # 'long' or 'short'
                      pair: str,
                      candles: List[Dict],
                      spread: float,
                      prev_day_high: Optional[float] = None,
                      prev_day_low: Optional[float] = None,
                      prev_day_close: Optional[float] = None,
                      use_structure: bool = True) -> SLTPLevels:
        """
        Calculate dynamic SL/TP levels.

        Args:
            entry_price: Entry price
            direction: 'long' or 'short'
            pair: Currency pair (e.g., 'EUR_USD')
            candles: Recent 1-minute candles (at least 20)
            spread: Current spread in pips
            prev_day_high: Previous day's high (optional, for pivots)
            prev_day_low: Previous day's low (optional, for pivots)
            prev_day_close: Previous day's close (optional, for pivots)
            use_structure: Whether to use market structure adjustments

        Returns:
            SLTPLevels object with prices and metadata
        """
        # Step 1: Calculate ATR
        atr = self.calculate_atr(candles)

        if atr == 0:
            # Fallback to minimal stops
            atr = self.pips_to_price(5.0, pair)  # 5 pips minimum

        # Step 2: Volatility-based baseline
        sl_vol = self.atr_mult_sl * atr
        tp_vol = self.atr_mult_tp * atr

        # Step 3: Buffer calculation
        buffer = self.calculate_buffer(atr, spread, pair)

        metadata = {
            'atr': atr,
            'atr_pips': self.price_to_pips(atr, pair),
            'spread': spread,
            'buffer': buffer,
            'buffer_pips': self.price_to_pips(buffer, pair)
        }

        # Step 4: Structure adjustments (if enabled and data available)
        sl_final = sl_vol
        tp_final = tp_vol
        method = 'volatility'

        if use_structure and len(candles) >= 20:
            swing_low, swing_high = self.find_swing_levels(candles)
            metadata['swing_low'] = swing_low
            metadata['swing_high'] = swing_high

            if direction == 'long':
                # SL: Beyond swing low with buffer
                sl_struct = entry_price - swing_low + buffer
                sl_final = max(sl_vol, sl_struct)

                # TP: Towards swing high or round number
                round_below, round_above = self.get_nearest_round_number(entry_price, pair)
                if round_above > entry_price:
                    tp_struct = round_above - entry_price - buffer
                    tp_final = min(tp_vol, max(tp_struct, sl_vol * 1.2))  # Ensure R:R > 1

            else:  # short
                # SL: Beyond swing high with buffer
                sl_struct = swing_high - entry_price + buffer
                sl_final = max(sl_vol, sl_struct)

                # TP: Towards swing low or round number
                round_below, round_above = self.get_nearest_round_number(entry_price, pair)
                if round_below < entry_price:
                    tp_struct = entry_price - round_below - buffer
                    tp_final = min(tp_vol, max(tp_struct, sl_vol * 1.2))

            method = 'hybrid'

            # Step 5: Pivot adjustments (if available)
            if all(v is not None for v in [prev_day_high, prev_day_low, prev_day_close]):
                pivots = self.calculate_pivots(prev_day_high, prev_day_low, prev_day_close)
                metadata['pivots'] = pivots

                # Find nearest pivot level in TP direction
                if direction == 'long':
                    pivot_targets = [p for p in [pivots['r1'], pivots['r2']] if p > entry_price]
                    if pivot_targets:
                        nearest_pivot = min(pivot_targets)
                        tp_pivot = nearest_pivot - entry_price - buffer
                        if tp_pivot > sl_final * 1.2:  # Ensure good R:R
                            tp_final = min(tp_final, tp_pivot)
                else:
                    pivot_targets = [p for p in [pivots['s1'], pivots['s2']] if p < entry_price]
                    if pivot_targets:
                        nearest_pivot = max(pivot_targets)
                        tp_pivot = entry_price - nearest_pivot - buffer
                        if tp_pivot > sl_final * 1.2:
                            tp_final = min(tp_final, tp_pivot)

        # Step 6: Calculate final prices
        if direction == 'long':
            sl_price = entry_price - sl_final
            tp_price = entry_price + tp_final
        else:
            sl_price = entry_price + sl_final
            tp_price = entry_price - tp_final

        # Convert to pips
        sl_pips = self.price_to_pips(sl_final, pair)
        tp_pips = self.price_to_pips(tp_final, pair)

        # Calculate confidence based on R:R and structure alignment
        risk_reward = tp_pips / sl_pips if sl_pips > 0 else 0
        confidence = min(1.0, max(0.3, (risk_reward - 1.0) / 2.0))  # Higher R:R = higher confidence

        metadata['risk_reward'] = risk_reward

        return SLTPLevels(
            sl_price=sl_price,
            tp_price=tp_price,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            method=method,
            confidence=confidence,
            metadata=metadata
        )

    def calculate_trailing_stop(self,
                                entry_price: float,
                                current_price: float,
                                direction: str,
                                highest_since_entry: float,
                                lowest_since_entry: float,
                                atr: float,
                                pair: str,
                                current_sl: float) -> float:
        """
        Calculate Chandelier-style trailing stop.

        Args:
            entry_price: Original entry price
            current_price: Current market price
            direction: 'long' or 'short'
            highest_since_entry: Highest price since entry
            lowest_since_entry: Lowest price since entry
            atr: Current ATR value
            pair: Currency pair
            current_sl: Current stop loss level

        Returns:
            New stop loss level (never worse than current)
        """
        trail_distance = self.atr_mult_trail * atr

        if direction == 'long':
            # Trail below highest high
            new_sl = highest_since_entry - trail_distance
            # Never move stop loss down
            return max(current_sl, new_sl)
        else:
            # Trail above lowest low
            new_sl = lowest_since_entry + trail_distance
            # Never move stop loss up
            return min(current_sl, new_sl)

    def should_move_to_breakeven(self,
                                entry_price: float,
                                current_price: float,
                                direction: str,
                                atr: float,
                                spread: float,
                                pair: str) -> Tuple[bool, float]:
        """
        Check if trade should move to break-even.

        Args:
            entry_price: Original entry price
            current_price: Current market price
            direction: 'long' or 'short'
            atr: Current ATR value
            spread: Current spread in pips
            pair: Currency pair

        Returns:
            (should_move, new_sl_level) tuple
        """
        favorable_move = abs(current_price - entry_price)
        trigger_distance = self.breakeven_trigger * atr

        if favorable_move >= trigger_distance:
            # Add small cushion to cover costs
            spread_price = self.pips_to_price(spread, pair)
            cushion = 0.2 * spread_price

            if direction == 'long':
                be_level = entry_price + cushion
                if current_price > be_level:
                    return True, be_level
            else:
                be_level = entry_price - cushion
                if current_price < be_level:
                    return True, be_level

        return False, entry_price

    def calculate_time_decayed_sl(self,
                                  entry_price: float,
                                  initial_sl_distance: float,
                                  direction: str,
                                  elapsed_seconds: float) -> float:
        """
        Calculate time-decayed stop loss.

        As time passes, allowed adverse distance shrinks.

        Args:
            entry_price: Original entry price
            initial_sl_distance: Initial SL distance from entry
            direction: 'long' or 'short'
            elapsed_seconds: Seconds since entry

        Returns:
            New SL level (tighter than initial)
        """
        elapsed_minutes = elapsed_seconds / 60.0
        timeout_fraction = elapsed_minutes / self.timeout_minutes

        # Exponential decay: b(t) = b0 × exp(-λ × t / T_max)
        decayed_distance = initial_sl_distance * np.exp(
            -self.time_decay_lambda * timeout_fraction
        )

        if direction == 'long':
            return entry_price - decayed_distance
        else:
            return entry_price + decayed_distance


# Example usage and testing
if __name__ == "__main__":
    # Create calculator with default parameters
    calculator = DynamicSLTPCalculator()

    # Example candle data (1-minute bars)
    candles = [
        {'high': 1.1025, 'low': 1.1020, 'close': 1.1023},
        {'high': 1.1028, 'low': 1.1022, 'close': 1.1025},
        {'high': 1.1030, 'low': 1.1024, 'close': 1.1027},
        {'high': 1.1032, 'low': 1.1026, 'close': 1.1030},
        {'high': 1.1035, 'low': 1.1028, 'close': 1.1032},
        {'high': 1.1038, 'low': 1.1030, 'close': 1.1035},
        {'high': 1.1040, 'low': 1.1033, 'close': 1.1037},
        {'high': 1.1042, 'low': 1.1035, 'close': 1.1040},
        {'high': 1.1045, 'low': 1.1038, 'close': 1.1042},
        {'high': 1.1048, 'low': 1.1040, 'close': 1.1045},
        {'high': 1.1050, 'low': 1.1042, 'close': 1.1047},
        {'high': 1.1052, 'low': 1.1045, 'close': 1.1050},
        {'high': 1.1055, 'low': 1.1048, 'close': 1.1052},
        {'high': 1.1057, 'low': 1.1050, 'close': 1.1055},
        {'high': 1.1060, 'low': 1.1052, 'close': 1.1057},
    ]

    # Calculate SL/TP for a long position
    levels = calculator.calculate_sltp(
        entry_price=1.1060,
        direction='long',
        pair='EUR_USD',
        candles=candles,
        spread=0.8,
        prev_day_high=1.1100,
        prev_day_low=1.1000,
        prev_day_close=1.1050
    )

    print("="*60)
    print("Dynamic SL/TP Example")
    print("="*60)
    print(f"Entry Price: {levels.metadata['entry_price'] if 'entry_price' in levels.metadata else 1.1060:.5f}")
    print(f"SL Price: {levels.sl_price:.5f} ({levels.sl_pips:.1f} pips)")
    print(f"TP Price: {levels.tp_price:.5f} ({levels.tp_pips:.1f} pips)")
    print(f"Risk:Reward: 1:{levels.metadata['risk_reward']:.2f}")
    print(f"Method: {levels.method}")
    print(f"Confidence: {levels.confidence:.1%}")
    print(f"\nATR: {levels.metadata['atr_pips']:.2f} pips")
    print(f"Buffer: {levels.metadata['buffer_pips']:.2f} pips")
    print(f"Spread: {levels.metadata['spread']:.1f} pips")
    print("="*60)
