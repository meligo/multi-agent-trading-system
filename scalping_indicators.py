"""
Scalping Indicators - Optimized for 1-Minute Charts

Indicator suite based on GPT-5 analysis and academic research.
Optimized for 10-20 minute scalping holds on 1-minute timeframes.

Key indicators:
- Fast EMA Ribbon (3, 6, 12)
- VWAP with deviation bands
- Donchian Channel
- RSI(7), ADX(7)
- SuperTrend, ATR(5)
- Bollinger Squeeze detection
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List
from datetime import datetime, time as dt_time


class ScalpingIndicators:
    """Calculate technical indicators optimized for scalping."""

    @staticmethod
    def calculate_ema_ribbon(df: pd.DataFrame, periods: List[int] = [3, 6, 12]) -> pd.DataFrame:
        """
        Calculate fast EMA ribbon for trend detection.

        Args:
            df: DataFrame with 'close' column
            periods: EMA periods (default: [3, 6, 12] for scalping)

        Returns:
            DataFrame with ema_3, ema_6, ema_12 columns
        """
        for period in periods:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()

        # Ribbon alignment (all EMAs in order)
        df['ema_ribbon_bullish'] = (df['ema_3'] > df['ema_6']) & (df['ema_6'] > df['ema_12'])
        df['ema_ribbon_bearish'] = (df['ema_3'] < df['ema_6']) & (df['ema_6'] < df['ema_12'])

        # EMA slope (momentum strength)
        df['ema_6_slope'] = df['ema_6'].diff()
        df['ema_12_slope'] = df['ema_12'].diff()

        return df

    @staticmethod
    def calculate_vwap(df: pd.DataFrame, session_start_hour: int = 8) -> pd.DataFrame:
        """
        Calculate session-anchored VWAP with deviation bands.

        VWAP = Intraday "fair value" institutional anchor.
        Critical for scalping direction bias.

        Args:
            df: DataFrame with 'high', 'low', 'close', 'volume', datetime index
            session_start_hour: Session anchor (8 = 08:00 GMT London open)

        Returns:
            DataFrame with vwap, vwap_1std_upper, vwap_1std_lower, etc.
        """
        # Typical price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

        # Session reset (anchor VWAP at session start)
        df['session'] = (df.index.hour >= session_start_hour).astype(int)
        df['session_change'] = df['session'].diff().fillna(0)

        # Cumulative volume and TP*volume
        df['cumulative_tpv'] = (df['typical_price'] * df['volume']).groupby(
            (df['session_change'] != 0).cumsum()
        ).cumsum()

        df['cumulative_volume'] = df['volume'].groupby(
            (df['session_change'] != 0).cumsum()
        ).cumsum()

        # VWAP = Sum(TP * Volume) / Sum(Volume)
        df['vwap'] = df['cumulative_tpv'] / df['cumulative_volume']

        # Standard deviation bands (±1σ, ±2σ)
        df['vwap_deviation'] = (df['typical_price'] - df['vwap']) ** 2
        df['vwap_variance'] = df['vwap_deviation'].groupby(
            (df['session_change'] != 0).cumsum()
        ).expanding().mean().reset_index(drop=True, level=0)
        df['vwap_std'] = np.sqrt(df['vwap_variance'])

        df['vwap_1std_upper'] = df['vwap'] + df['vwap_std']
        df['vwap_1std_lower'] = df['vwap'] - df['vwap_std']
        df['vwap_2std_upper'] = df['vwap'] + (2 * df['vwap_std'])
        df['vwap_2std_lower'] = df['vwap'] - (2 * df['vwap_std'])

        # Price position relative to VWAP
        df['above_vwap'] = df['close'] > df['vwap']
        df['below_vwap'] = df['close'] < df['vwap']

        # Cleanup
        df.drop(['typical_price', 'session', 'session_change', 'cumulative_tpv',
                 'cumulative_volume', 'vwap_deviation', 'vwap_variance'], axis=1, inplace=True)

        return df

    @staticmethod
    def calculate_donchian_channel(df: pd.DataFrame, period: int = 15) -> pd.DataFrame:
        """
        Calculate Donchian Channel for breakout detection.

        Donchian = Highest high / Lowest low over N periods.
        Breakout = Price closes outside channel → momentum burst.

        Args:
            df: DataFrame with 'high', 'low', 'close'
            period: Lookback period (15 = approx. 10-20 min hold horizon on 1m)

        Returns:
            DataFrame with donchian_upper, donchian_lower, donchian_mid
        """
        df['donchian_upper'] = df['high'].rolling(window=period).max()
        df['donchian_lower'] = df['low'].rolling(window=period).min()
        df['donchian_mid'] = (df['donchian_upper'] + df['donchian_lower']) / 2

        # Breakout signals
        df['donchian_breakout_long'] = df['close'] > df['donchian_upper'].shift(1)
        df['donchian_breakout_short'] = df['close'] < df['donchian_lower'].shift(1)

        # Channel width (volatility measure)
        df['donchian_width'] = df['donchian_upper'] - df['donchian_lower']

        return df

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 7) -> pd.DataFrame:
        """
        Calculate fast RSI for momentum detection.

        RSI(7) is optimized for 1-minute scalping (NOT RSI(14)).
        - RSI > 55 with rising slope = bullish momentum
        - RSI < 45 with falling slope = bearish momentum

        Args:
            df: DataFrame with 'close'
            period: RSI period (7 for scalping, NOT 14)

        Returns:
            DataFrame with rsi, rsi_slope
        """
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # RSI slope (momentum direction)
        df['rsi_slope'] = df['rsi'].diff()

        # Momentum signals
        df['rsi_bullish'] = (df['rsi'] > 55) & (df['rsi_slope'] > 0)
        df['rsi_bearish'] = (df['rsi'] < 45) & (df['rsi_slope'] < 0)

        return df

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 7) -> pd.DataFrame:
        """
        Calculate fast ADX for trend strength filtering.

        ADX(7) is optimized for 1-minute scalping (NOT ADX(14)).
        - ADX > 18 and rising = trending (take breakouts)
        - ADX < 18 or falling = choppy (skip trades)

        Args:
            df: DataFrame with 'high', 'low', 'close'
            period: ADX period (7 for scalping)

        Returns:
            DataFrame with adx, plus_di, minus_di
        """
        # True Range
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )

        # Directional Movement
        df['plus_dm'] = np.where(
            (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
            np.maximum(df['high'] - df['high'].shift(1), 0),
            0
        )
        df['minus_dm'] = np.where(
            (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
            np.maximum(df['low'].shift(1) - df['low'], 0),
            0
        )

        # Smoothed TR and DM
        df['atr'] = df['tr'].rolling(window=period).mean()
        df['plus_di'] = 100 * (df['plus_dm'].rolling(window=period).mean() / df['atr'])
        df['minus_di'] = 100 * (df['minus_dm'].rolling(window=period).mean() / df['atr'])

        # ADX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].rolling(window=period).mean()

        # ADX slope (trend acceleration)
        df['adx_slope'] = df['adx'].diff()

        # Trend filter
        df['adx_trending'] = (df['adx'] > 18) & (df['adx_slope'] > 0)

        # Directional bias
        df['di_bullish'] = df['plus_di'] > df['minus_di']
        df['di_bearish'] = df['minus_di'] > df['plus_di']

        # Cleanup
        df.drop(['tr', 'plus_dm', 'minus_dm', 'dx'], axis=1, inplace=True)

        return df

    @staticmethod
    def calculate_supertrend(df: pd.DataFrame, atr_period: int = 7, multiplier: float = 1.5) -> pd.DataFrame:
        """
        Calculate SuperTrend for trailing stops and exits.

        SuperTrend = ATR-based adaptive stop that reacts to volatility.
        Great for protecting 6-10 pip wins without large giveback.

        Args:
            df: DataFrame with 'high', 'low', 'close'
            atr_period: ATR period (7 for scalping)
            multiplier: ATR multiplier (1.5 for scalping, 2.0+ for swing)

        Returns:
            DataFrame with supertrend, supertrend_direction
        """
        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=atr_period).mean()

        # Basic upper/lower bands
        hl_avg = (df['high'] + df['low']) / 2
        df['basic_upper'] = hl_avg + (multiplier * df['atr'])
        df['basic_lower'] = hl_avg - (multiplier * df['atr'])

        # SuperTrend bands (with trailing logic)
        df['supertrend_upper'] = df['basic_upper']
        df['supertrend_lower'] = df['basic_lower']

        for i in range(1, len(df)):
            # Upper band: Trail down if close still below, reset if close crosses above
            if df['basic_upper'].iloc[i] < df['supertrend_upper'].iloc[i-1] or \
               df['close'].iloc[i-1] > df['supertrend_upper'].iloc[i-1]:
                df.loc[df.index[i], 'supertrend_upper'] = df['basic_upper'].iloc[i]
            else:
                df.loc[df.index[i], 'supertrend_upper'] = df['supertrend_upper'].iloc[i-1]

            # Lower band: Trail up if close still above, reset if close crosses below
            if df['basic_lower'].iloc[i] > df['supertrend_lower'].iloc[i-1] or \
               df['close'].iloc[i-1] < df['supertrend_lower'].iloc[i-1]:
                df.loc[df.index[i], 'supertrend_lower'] = df['basic_lower'].iloc[i]
            else:
                df.loc[df.index[i], 'supertrend_lower'] = df['supertrend_lower'].iloc[i-1]

        # SuperTrend line and direction
        df['supertrend'] = np.where(
            df['close'] > df['supertrend_upper'].shift(1),
            df['supertrend_lower'],
            df['supertrend_upper']
        )

        df['supertrend_direction'] = np.where(
            df['close'] > df['supertrend'],
            1,  # Bullish (price above SuperTrend)
            -1  # Bearish (price below SuperTrend)
        )

        # Cleanup
        df.drop(['tr', 'basic_upper', 'basic_lower', 'supertrend_upper', 'supertrend_lower'],
                axis=1, inplace=True)

        return df

    @staticmethod
    def calculate_bollinger_squeeze(df: pd.DataFrame, bb_period: int = 20, bb_std: float = 2.0,
                                     kc_period: int = 20, kc_mult: float = 1.5) -> pd.DataFrame:
        """
        Calculate Bollinger Band Squeeze (BB vs Keltner Channel).

        Squeeze = Low volatility phase that often precedes momentum bursts.
        When BB contracts inside KC, volatility is compressed → breakout incoming.

        Args:
            df: DataFrame with 'high', 'low', 'close'
            bb_period: Bollinger Band period (20)
            bb_std: BB standard deviations (2.0)
            kc_period: Keltner Channel period (20)
            kc_mult: KC ATR multiplier (1.5)

        Returns:
            DataFrame with bb_upper, bb_lower, kc_upper, kc_lower, squeeze_on
        """
        # Bollinger Bands
        df['bb_mid'] = df['close'].rolling(window=bb_period).mean()
        bb_std_dev = df['close'].rolling(window=bb_period).std()
        df['bb_upper'] = df['bb_mid'] + (bb_std * bb_std_dev)
        df['bb_lower'] = df['bb_mid'] - (bb_std * bb_std_dev)

        # Keltner Channel
        df['kc_mid'] = df['close'].rolling(window=kc_period).mean()
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        kc_atr = df['tr'].rolling(window=kc_period).mean()
        df['kc_upper'] = df['kc_mid'] + (kc_mult * kc_atr)
        df['kc_lower'] = df['kc_mid'] - (kc_mult * kc_atr)

        # Squeeze detection (BB inside KC)
        df['squeeze_on'] = (df['bb_upper'] < df['kc_upper']) & (df['bb_lower'] > df['kc_lower'])

        # Squeeze release (just exited squeeze)
        df['squeeze_off'] = df['squeeze_on'].shift(1) & ~df['squeeze_on']

        # Bollinger Band width (alternative volatility measure)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']

        # Cleanup
        df.drop(['tr'], axis=1, inplace=True)

        return df

    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame, config: Dict = None) -> pd.DataFrame:
        """
        Calculate all scalping indicators in one pass.

        Args:
            df: DataFrame with OHLCV data
            config: Optional config dict with indicator parameters

        Returns:
            DataFrame with all indicators
        """
        if config is None:
            config = {
                "ema_periods": [3, 6, 12],
                "rsi_period": 7,
                "adx_period": 7,
                "vwap_session_start": 8,
                "donchian_period": 15,
                "supertrend_atr": 7,
                "supertrend_mult": 1.5,
                "bb_period": 20,
                "bb_std": 2.0,
                "kc_period": 20,
                "kc_mult": 1.5,
            }

        df = ScalpingIndicators.calculate_ema_ribbon(df, config["ema_periods"])
        df = ScalpingIndicators.calculate_rsi(df, config["rsi_period"])
        df = ScalpingIndicators.calculate_adx(df, config["adx_period"])
        df = ScalpingIndicators.calculate_vwap(df, config["vwap_session_start"])
        df = ScalpingIndicators.calculate_donchian_channel(df, config["donchian_period"])
        df = ScalpingIndicators.calculate_supertrend(df, config["supertrend_atr"], config["supertrend_mult"])
        df = ScalpingIndicators.calculate_bollinger_squeeze(
            df, config["bb_period"], config["bb_std"], config["kc_period"], config["kc_mult"]
        )

        # Volume spike detection
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_spike'] = df['volume'] > (2.0 * df['volume_ma'])

        return df

    @staticmethod
    def get_trade_signals(df: pd.DataFrame) -> Dict[str, any]:
        """
        Generate trade signals from latest indicator values.

        Returns dict with:
        - direction: "LONG", "SHORT", or "NONE"
        - confidence: 0-100
        - signals: Dict of individual signal states
        - summary: Human-readable summary
        """
        latest = df.iloc[-1]

        signals = {
            # Trend confirmation
            "ema_ribbon_bullish": latest['ema_ribbon_bullish'],
            "ema_ribbon_bearish": latest['ema_ribbon_bearish'],
            "above_vwap": latest['above_vwap'],
            "below_vwap": latest['below_vwap'],

            # Breakouts
            "donchian_breakout_long": latest['donchian_breakout_long'],
            "donchian_breakout_short": latest['donchian_breakout_short'],
            "squeeze_off": latest['squeeze_off'],

            # Momentum
            "rsi_bullish": latest['rsi_bullish'],
            "rsi_bearish": latest['rsi_bearish'],
            "adx_trending": latest['adx_trending'],
            "di_bullish": latest['di_bullish'],
            "di_bearish": latest['di_bearish'],

            # Volume
            "volume_spike": latest['volume_spike'],

            # SuperTrend
            "supertrend_bullish": latest['supertrend_direction'] == 1,
            "supertrend_bearish": latest['supertrend_direction'] == -1,
        }

        # Count bullish signals
        bullish_count = sum([
            signals['ema_ribbon_bullish'],
            signals['above_vwap'],
            signals['donchian_breakout_long'],
            signals['squeeze_off'] and signals['ema_ribbon_bullish'],
            signals['rsi_bullish'],
            signals['adx_trending'] and signals['di_bullish'],
            signals['volume_spike'],
            signals['supertrend_bullish'],
        ])

        # Count bearish signals
        bearish_count = sum([
            signals['ema_ribbon_bearish'],
            signals['below_vwap'],
            signals['donchian_breakout_short'],
            signals['squeeze_off'] and signals['ema_ribbon_bearish'],
            signals['rsi_bearish'],
            signals['adx_trending'] and signals['di_bearish'],
            signals['volume_spike'],
            signals['supertrend_bearish'],
        ])

        # Determine direction
        if bullish_count >= 5:
            direction = "LONG"
            confidence = min(100, bullish_count * 12)
        elif bearish_count >= 5:
            direction = "SHORT"
            confidence = min(100, bearish_count * 12)
        else:
            direction = "NONE"
            confidence = max(bullish_count, bearish_count) * 10

        # Build summary
        summary_parts = []
        if signals['ema_ribbon_bullish']:
            summary_parts.append("EMA ribbon bullish")
        elif signals['ema_ribbon_bearish']:
            summary_parts.append("EMA ribbon bearish")

        if signals['above_vwap']:
            summary_parts.append(f"Price above VWAP ({latest['vwap']:.5f})")
        elif signals['below_vwap']:
            summary_parts.append(f"Price below VWAP ({latest['vwap']:.5f})")

        if signals['adx_trending']:
            summary_parts.append(f"ADX trending ({latest['adx']:.1f})")

        if signals['volume_spike']:
            summary_parts.append("Volume spike detected")

        summary = ", ".join(summary_parts) if summary_parts else "No clear signals"

        return {
            "direction": direction,
            "confidence": confidence,
            "signals": signals,
            "summary": summary,
            "indicator_values": {
                "ema_3": latest['ema_3'],
                "ema_6": latest['ema_6'],
                "ema_12": latest['ema_12'],
                "vwap": latest['vwap'],
                "rsi": latest['rsi'],
                "adx": latest['adx'],
                "supertrend": latest['supertrend'],
                "donchian_upper": latest['donchian_upper'],
                "donchian_lower": latest['donchian_lower'],
            }
        }


    @staticmethod
    def calculate_floor_pivots(prev_high: float, prev_low: float, prev_close: float) -> Dict[str, float]:
        """
        Calculate classic floor pivot points from previous day's data.

        Used by institutions and prop desks worldwide.

        Args:
            prev_high: Previous day's high
            prev_low: Previous day's low
            prev_close: Previous day's close

        Returns:
            Dict with PP, R1, R2, R3, S1, S2, S3
        """
        PP = (prev_high + prev_low + prev_close) / 3
        R1 = (2 * PP) - prev_low
        R2 = PP + (prev_high - prev_low)
        R3 = prev_high + 2 * (PP - prev_low)
        S1 = (2 * PP) - prev_high
        S2 = PP - (prev_high - prev_low)
        S3 = prev_low - 2 * (prev_high - PP)

        return {
            'PP': PP,
            'R1': R1, 'R2': R2, 'R3': R3,
            'S1': S1, 'S2': S2, 'S3': S3
        }

    @staticmethod
    def calculate_big_figures(current_price: float, levels: int = 5) -> List[float]:
        """
        Calculate big figure levels (00/25/50/75) around current price.

        Option barriers and psychological levels where orders cluster.

        Args:
            current_price: Current market price
            levels: Number of levels above and below to generate

        Returns:
            List of big figure levels sorted ascending
        """
        # Round down to nearest 00
        base = int(current_price * 10000) // 100 * 100

        figures = []
        # Generate levels below
        for i in range(levels, 0, -1):
            for offset in [0, 25, 50, 75]:
                level = (base - (i * 100) + offset) / 10000
                if level < current_price:
                    figures.append(level)

        # Generate levels at and above
        for i in range(levels + 1):
            for offset in [0, 25, 50, 75]:
                level = (base + (i * 100) + offset) / 10000
                if level >= current_price:
                    figures.append(level)

        return sorted(set(figures))

    @staticmethod
    def calculate_opening_range(df: pd.DataFrame, session_start_hour: int, range_minutes: int = 15) -> Dict[str, any]:
        """
        Calculate Opening Range for ORB strategy.

        First N minutes of session define the range; breakouts traded.

        Args:
            df: DataFrame with OHLC data
            session_start_hour: Hour session starts (8 for London, 13 for NY)
            range_minutes: Minutes to define range (typically 5-15)

        Returns:
            Dict with OR_high, OR_low, OR_mid, OR_range
        """
        if df.empty or len(df) < range_minutes:
            return {'OR_high': None, 'OR_low': None, 'OR_mid': None, 'OR_range': None}

        # Find first candle at or after session start
        session_candles = df[df.index.hour == session_start_hour]
        if len(session_candles) < range_minutes:
            return {'OR_high': None, 'OR_low': None, 'OR_mid': None, 'OR_range': None}

        # Get first N minutes
        or_data = session_candles.head(range_minutes)
        OR_high = or_data['high'].max()
        OR_low = or_data['low'].min()
        OR_mid = (OR_high + OR_low) / 2
        OR_range = OR_high - OR_low

        return {
            'OR_high': OR_high,
            'OR_low': OR_low,
            'OR_mid': OR_mid,
            'OR_range': OR_range
        }

    @staticmethod
    def detect_liquidity_sweep(df: pd.DataFrame, lookback: int = 2) -> pd.Series:
        """
        Detect liquidity sweeps (stop-run reversals / SFP).

        Price pierces Donchian but closes back inside = trapped traders.

        Args:
            df: DataFrame with OHLC and donchian_upper/lower
            lookback: Candles to check for close back inside (default 2)

        Returns:
            Series with 'sweep_long' (bullish) and 'sweep_short' (bearish) signals
        """
        if 'donchian_upper' not in df.columns or 'donchian_lower' not in df.columns:
            df['liquidity_sweep_long'] = False
            df['liquidity_sweep_short'] = False
            return df

        sweep_long = []
        sweep_short = []

        for i in range(len(df)):
            long_sweep = False
            short_sweep = False

            if i >= lookback:
                # Check if any recent candle broke below Donchian lower
                # but current candle closed back inside
                for j in range(1, lookback + 1):
                    if (df['low'].iloc[i-j] < df['donchian_lower'].iloc[i-j] and
                        df['close'].iloc[i] > df['donchian_lower'].iloc[i]):
                        long_sweep = True
                        break

                # Check if any recent candle broke above Donchian upper
                # but current candle closed back inside
                for j in range(1, lookback + 1):
                    if (df['high'].iloc[i-j] > df['donchian_upper'].iloc[i-j] and
                        df['close'].iloc[i] < df['donchian_upper'].iloc[i]):
                        short_sweep = True
                        break

            sweep_long.append(long_sweep)
            sweep_short.append(short_sweep)

        df['liquidity_sweep_long'] = sweep_long
        df['liquidity_sweep_short'] = sweep_short

        return df

    @staticmethod
    def detect_inside_bars(df: pd.DataFrame, min_bars: int = 3) -> pd.Series:
        """
        Detect inside bar compression patterns.

        Multiple inside bars = volatility compression → expansion coming.

        Args:
            df: DataFrame with OHLC
            min_bars: Minimum consecutive inside bars (default 3)

        Returns:
            Series indicating compression zones
        """
        inside_bar = (df['high'] <= df['high'].shift(1)) & (df['low'] >= df['low'].shift(1))

        # Count consecutive inside bars
        consecutive = inside_bar.astype(int).groupby((inside_bar != inside_bar.shift()).cumsum()).cumsum()

        df['inside_bar_compression'] = consecutive >= min_bars

        return df

    @staticmethod
    def detect_narrow_range(df: pd.DataFrame, period: int = 4) -> pd.Series:
        """
        Detect Narrow Range patterns (NR4, NR7, etc).

        Narrowest range in N periods = compression → breakout.

        Args:
            df: DataFrame with OHLC
            period: Lookback period (4 for NR4, 7 for NR7)

        Returns:
            Series indicating narrow range candles
        """
        df['range'] = df['high'] - df['low']
        df['is_nr'] = df['range'] == df['range'].rolling(window=period).min()

        return df

    @staticmethod
    def detect_impulse_move(df: pd.DataFrame, atr_multiplier: float = 1.5) -> pd.Series:
        """
        Detect impulse moves (large momentum candles).

        Candle range ≥ 1.5x ATR = impulse → watch for pullback entry.

        Args:
            df: DataFrame with OHLC and 'atr' column
            atr_multiplier: Multiplier for ATR (default 1.5)

        Returns:
            Series indicating impulse candles
        """
        if 'atr' not in df.columns:
            # Calculate ATR if not present
            df = ScalpingIndicators.calculate_adx(df, period=14)  # ADX also calculates ATR

        df['candle_range'] = df['high'] - df['low']
        df['is_impulse'] = df['candle_range'] >= (atr_multiplier * df['atr'])

        # Also check if closes beyond Donchian
        if 'donchian_upper' in df.columns and 'donchian_lower' in df.columns:
            df['is_impulse'] = df['is_impulse'] & (
                (df['close'] > df['donchian_upper']) |
                (df['close'] < df['donchian_lower'])
            )

        return df

    @staticmethod
    def calculate_adr(df: pd.DataFrame, period: int = 20) -> float:
        """
        Calculate Average Daily Range over N days.

        Used to detect when current day is overextended.

        Args:
            df: DataFrame with daily OHLC data
            period: Lookback period (default 20 days)

        Returns:
            ADR value
        """
        daily_range = df['high'] - df['low']
        adr = daily_range.rolling(window=period).mean().iloc[-1]
        return adr

    @staticmethod
    def is_fix_window(current_time: datetime) -> Dict[str, bool]:
        """
        Check if current time is in London Fix or NY Options Cut window.

        London Fix: 15:40-16:10 GMT
        NY Options Cut: Also around 15:45-16:15 GMT (10:00 NY time)

        Args:
            current_time: Current datetime (UTC/GMT)

        Returns:
            Dict with 'in_fix_window', 'fix_type'
        """
        hour = current_time.hour
        minute = current_time.minute

        # London Fix window: 15:40-16:10 GMT
        if hour == 15 and minute >= 40:
            return {'in_fix_window': True, 'fix_type': 'london_fix_pre'}
        if hour == 16 and minute <= 10:
            return {'in_fix_window': True, 'fix_type': 'london_fix_post'}

        return {'in_fix_window': False, 'fix_type': None}


if __name__ == "__main__":
    # Test with sample data
    print("Scalping Indicators Module")
    print("="*80)
    print("Available indicators:")
    print("  - Fast EMA Ribbon (3, 6, 12)")
    print("  - Session VWAP with ±1σ, ±2σ bands")
    print("  - Donchian Channel (15)")
    print("  - RSI(7) with momentum detection")
    print("  - ADX(7) trend strength filter")
    print("  - SuperTrend(7, 1.5) for trailing stops")
    print("  - Bollinger Squeeze (BB vs KC)")
    print("  - Volume spike detection")
    print("\nNEW - Professional Techniques:")
    print("  - Floor Pivot Points (PP, S1/R1, S2/R2)")
    print("  - Big Figure Levels (00/25/50/75)")
    print("  - Opening Range Breakout (ORB)")
    print("  - Liquidity Sweep / SFP detection")
    print("  - Inside Bar / NR compression")
    print("  - Impulse move detection")
    print("  - ADR (Average Daily Range)")
    print("  - Fix window detection (16:00 GMT)")
    print("="*80)
