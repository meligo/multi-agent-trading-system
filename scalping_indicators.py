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
    print("="*80)
