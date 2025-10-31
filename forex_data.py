"""
Forex Data Fetching and Technical Analysis

Handles:
- Real-time forex data from Finnhub
- Technical indicator calculations
- Support/Resistance detection
- Signal generation
"""

import finnhub
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from forex_config import ForexConfig

# Import TA library (stockstats already installed)
from stockstats import wrap as stockstats_wrap


@dataclass
class ForexCandle:
    """Single forex candle data."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)


@dataclass
class ForexSignal:
    """Trading signal with all relevant data and SL/TP calculation details."""
    pair: str
    timeframe: str
    signal: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 to 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    pips_risk: float
    pips_reward: float
    reasoning: List[str]
    indicators: Dict[str, float]
    timestamp: datetime
    # SL/TP calculation details
    sl_method: str = 'atr'  # 'atr', 'support', 'resistance'
    tp_method: str = 'atr'  # 'atr', 'support', 'resistance'
    rr_adjusted: bool = False  # Whether RR was adjusted to meet minimum
    calculation_steps: List[str] = None  # Step-by-step calculation log
    atr_value: float = None  # ATR value used
    nearest_support: float = None  # Support level used
    nearest_resistance: float = None  # Resistance level used

    def __post_init__(self):
        if self.calculation_steps is None:
            self.calculation_steps = []

    def __str__(self):
        rr_indicator = " (RR adjusted)" if self.rr_adjusted else ""
        return f"{self.pair} {self.signal} @ {self.entry_price:.5f} (SL: {self.stop_loss:.5f}, TP: {self.take_profit:.5f}, RR: {self.risk_reward_ratio:.1f}:1{rr_indicator})"


class ForexDataFetcher:
    """Fetch real-time forex data from IG API."""

    def __init__(self, api_key: str):
        from ig_data_fetcher import IGDataFetcher
        from finnhub_data_fetcher import FinnhubDataFetcher
        from candle_cache import CandleCache
        from forex_config import ForexConfig

        # Use IG data fetcher (primary)
        self.ig_fetcher = IGDataFetcher(
            api_key=api_key,
            username=ForexConfig.IG_USERNAME or None,
            password=ForexConfig.IG_PASSWORD or None
        )

        # Use Finnhub as fallback when IG hits rate limits
        try:
            self.finnhub_fetcher = FinnhubDataFetcher()
            print("✅ Finnhub fallback initialized")
        except ValueError:
            self.finnhub_fetcher = None
            print("⚠️  Finnhub API key not found - fallback disabled")

        # Smart candle caching (eliminates 98% of API calls)
        try:
            self.candle_cache = CandleCache()
            print("✅ Candle cache initialized (smart delta updates enabled)")
        except Exception as e:
            self.candle_cache = None
            print(f"⚠️  Candle cache disabled: {e}")

        self.cache = {}  # Simple in-memory cache (legacy)

    def _fetch_candles_direct(
        self,
        pair: str,
        timeframe: str,
        count: int
    ) -> pd.DataFrame:
        """
        Fetch candles directly from API (with Finnhub fallback).

        This is the internal fetch function used by the caching layer.
        Returns DataFrame with 'time' column (not indexed).

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            timeframe: Timeframe ('1', '5', '15', '60', 'D')
            count: Number of candles to fetch

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        try:
            # Try IG first
            df = self.ig_fetcher.get_candles(pair, timeframe, count)
            return df

        except Exception as ig_error:
            # Check if this is an IG rate limit error
            error_str = str(ig_error).lower()
            if 'exceeded' in error_str and 'allowance' in error_str:
                # Try to fall back to Finnhub if available
                if self.finnhub_fetcher:
                    print(f"   ⚠️  IG rate limit hit for {pair}, falling back to Finnhub...")
                    try:
                        df = self.finnhub_fetcher.get_candles(pair, timeframe, count)
                        print(f"   ✅ Fetched from Finnhub successfully")
                        return df

                    except Exception as finnhub_error:
                        raise ValueError(f"Both IG and Finnhub failed for {pair}: IG={ig_error}, Finnhub={finnhub_error}")
                else:
                    # No Finnhub fallback available
                    raise ValueError(f"IG rate limit exceeded for {pair} and no Finnhub fallback available. Error: {ig_error}")
            else:
                # Not a rate limit error, re-raise original
                raise ValueError(f"Error fetching {pair} on {timeframe}m: {ig_error}")

    def get_candles(
        self,
        pair: str,
        timeframe: str,
        count: int = 100
    ) -> pd.DataFrame:
        """
        Get forex candles for a pair with smart caching.

        Uses delta updates to eliminate 98% of API calls.
        - First call: Bootstraps cache from API
        - Subsequent calls: Returns cached data (0 API calls)
        - New data available: Fetches only NEW candles (delta update)

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            timeframe: Timeframe ('1', '5', '15', '60', 'D')
            count: Number of candles to fetch

        Returns:
            DataFrame with OHLCV data (datetime indexed)
        """
        # Use caching layer if available
        if self.candle_cache:
            df = self.candle_cache.get_candles(
                pair=pair,
                timeframe=timeframe,
                count=count,
                fetch_func=lambda p, tf, c: self._fetch_candles_direct(p, tf, c)
            )
        else:
            # Fallback to direct fetch if cache disabled
            df = self._fetch_candles_direct(pair, timeframe, count)

        # Convert to expected format (with datetime index)
        df_indexed = df.copy()
        if 'time' in df_indexed.columns:
            df_indexed['datetime'] = pd.to_datetime(df['time'])
            df_indexed.set_index('datetime', inplace=True)
            df_indexed = df_indexed.drop('time', axis=1)

        return df_indexed.tail(count)

    def get_current_price(self, pair: str) -> float:
        """Get current price for a pair."""
        return self.ig_fetcher.get_current_price(pair)

    def get_multiple_timeframes(
        self,
        pair: str,
        timeframes: List[str],
        count: int = 100
    ) -> Dict[str, pd.DataFrame]:
        """Get data for multiple timeframes."""
        result = {}
        for tf in timeframes:
            try:
                result[tf] = self.get_candles(pair, tf, count)
            except Exception as e:
                print(f"Error fetching {pair} {tf}m: {e}")
        return result


class FinnhubPatterns:
    """Finnhub Pattern Recognition API."""

    def __init__(self, client: finnhub.Client):
        self.client = client

    def get_patterns(self, pair: str, timeframe: str = 'D') -> Dict:
        """
        Get chart patterns from Finnhub.

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            timeframe: Timeframe (D for daily, 60 for hourly)

        Returns:
            Dictionary with patterns found
        """
        symbol = f"OANDA:{pair}"
        try:
            patterns = self.client.pattern_recognition(symbol, timeframe)
            return patterns
        except Exception as e:
            print(f"Error fetching patterns for {pair}: {e}")
            return {'points': []}


class FinnhubIndicators:
    """Finnhub Aggregate Indicators API."""

    def __init__(self, client: finnhub.Client):
        self.client = client

    def get_aggregate_indicators(self, pair: str, timeframe: str = 'D') -> Dict:
        """
        Get aggregate technical indicators from Finnhub.

        Returns:
            Dictionary with buy/sell/neutral counts
        """
        symbol = f"OANDA:{pair}"
        try:
            indicators = self.client.aggregate_indicator(symbol, timeframe)
            return indicators
        except Exception as e:
            print(f"Error fetching aggregate indicators for {pair}: {e}")
            return {'technicalAnalysis': {}}


class FinnhubSupportResistance:
    """Finnhub Support/Resistance API."""

    def __init__(self, client: finnhub.Client):
        self.client = client

    def get_levels(self, pair: str, timeframe: str = 'D') -> Dict:
        """
        Get support/resistance levels from Finnhub.

        Returns:
            Dictionary with support and resistance levels
        """
        symbol = f"OANDA:{pair}"
        try:
            levels = self.client.support_resistance(symbol, timeframe)
            return levels
        except Exception as e:
            print(f"Error fetching S/R levels for {pair}: {e}")
            return {'levels': []}


class TechnicalAnalysis:
    """Calculate technical indicators."""

    @staticmethod
    def infer_pip_size(pair: str) -> float:
        """Infer pip size for a currency pair."""
        if 'JPY' in pair or 'XJY' in pair:
            return 0.01
        return 0.0001

    @staticmethod
    def add_obv(df: pd.DataFrame, ema_span: int = 20, zscore_window: int = 50) -> pd.DataFrame:
        """
        Add On-Balance Volume (OBV) indicator.

        OBV tracks cumulative volume based on price direction.
        Rising OBV confirms uptrends, falling OBV confirms downtrends.

        Args:
            df: DataFrame with OHLCV data
            ema_span: Span for EMA smoothing
            zscore_window: Window for z-score normalization
        """
        # Calculate price change direction
        delta = df['close'].diff()
        sign = (delta > 0).astype(np.int8) - (delta < 0).astype(np.int8)  # -1, 0, 1

        # OBV = cumulative sum of (sign * volume)
        df['obv'] = (sign * df['volume'].fillna(0)).cumsum().astype('float64')

        # OBV EMA for smoothing
        df['obv_ema'] = df['obv'].ewm(span=ema_span, adjust=False).mean()

        # OBV z-score for normalized momentum
        rolling = df['obv'].rolling(zscore_window, min_periods=zscore_window//2)
        df['obv_zscore'] = (df['obv'] - rolling.mean()) / (rolling.std(ddof=0) + 1e-12)

        # OBV change rate (momentum)
        df['obv_change_rate'] = df['obv'].pct_change(5).fillna(0) * 100  # 5-period % change

        return df

    @staticmethod
    def add_vpvr_features(df: pd.DataFrame, pair: str, window_bars: int = 300,
                          bin_pips: int = 5) -> pd.DataFrame:
        """
        Add Volume Profile Visible Range (VPVR) features.

        VPVR shows volume distribution at price levels:
        - POC (Point of Control): Price with highest volume
        - VAH (Value Area High): Upper bound of 70% volume area
        - VAL (Value Area Low): Lower bound of 70% volume area

        Args:
            df: DataFrame with OHLCV data
            pair: Currency pair for pip calculation
            window_bars: Number of bars for visible range
            bin_pips: Bin size in pips
        """
        pip_size = TechnicalAnalysis.infer_pip_size(pair)
        bin_size = bin_pips * pip_size

        # Use typical price for volume distribution
        typical_price = (df['high'] + df['low'] + df['close']) / 3.0

        # Initialize columns
        df['vpvr_poc'] = np.nan
        df['vpvr_vah'] = np.nan
        df['vpvr_val'] = np.nan
        df['vpvr_dist_poc'] = np.nan
        df['vpvr_position'] = 0  # -1 below VAL, 0 inside VA, 1 above VAH

        # Calculate VPVR for each bar (rolling window)
        for i in range(window_bars, len(df)):
            start_idx = i - window_bars
            window_data = df.iloc[start_idx:i+1]

            if window_data.empty:
                continue

            # Get price range
            pmin = float(window_data['low'].min())
            pmax = float(window_data['high'].max())

            # Create bins
            edges = np.arange(pmin - bin_size, pmax + 2*bin_size, bin_size)

            # Build volume histogram
            prices = typical_price.iloc[start_idx:i+1].values
            volumes = window_data['volume'].values.astype('float64')
            hist, _ = np.histogram(prices, bins=edges, weights=volumes)

            if hist.sum() == 0:
                continue

            # Find POC (highest volume bin)
            poc_idx = int(hist.argmax())
            poc_price = (edges[poc_idx] + edges[poc_idx+1]) * 0.5

            # Calculate Value Area (70% of volume)
            target = 0.7 * hist.sum()
            used = hist[poc_idx]
            left = poc_idx - 1
            right = poc_idx + 1
            vah_idx, val_idx = poc_idx, poc_idx

            while used < target:
                left_vol = hist[left] if left >= 0 else -1
                right_vol = hist[right] if right < len(hist) else -1

                if right_vol >= left_vol:
                    used += max(right_vol, 0)
                    vah_idx = right
                    right += 1
                    if right >= len(hist):
                        break
                else:
                    used += max(left_vol, 0)
                    val_idx = left
                    left -= 1
                    if left < 0:
                        break

            val = edges[val_idx]
            vah = edges[vah_idx+1]

            # Store features for current bar
            current_price = df['close'].iloc[i]
            df.iloc[i, df.columns.get_loc('vpvr_poc')] = poc_price
            df.iloc[i, df.columns.get_loc('vpvr_vah')] = vah
            df.iloc[i, df.columns.get_loc('vpvr_val')] = val
            df.iloc[i, df.columns.get_loc('vpvr_dist_poc')] = (current_price - poc_price) / pip_size

            # Position relative to value area
            if current_price > vah:
                df.iloc[i, df.columns.get_loc('vpvr_position')] = 1
            elif current_price < val:
                df.iloc[i, df.columns.get_loc('vpvr_position')] = -1
            else:
                df.iloc[i, df.columns.get_loc('vpvr_position')] = 0

        return df

    @staticmethod
    def add_initial_balance(df: pd.DataFrame, tz: str = 'America/New_York',
                           session_open: str = '17:00', ib_minutes: int = 60) -> pd.DataFrame:
        """
        Add Initial Balance (first hour of trading day) features.

        The first hour establishes the day's range. Breakouts suggest trend days,
        rejections suggest rotation/range days.

        Args:
            df: DataFrame with OHLCV data
            tz: Timezone for session definition
            session_open: Session start time (default NY 17:00 for forex day)
            ib_minutes: Initial balance period in minutes
        """
        if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
            # Assume UTC if not tz-aware
            df.index = pd.to_datetime(df.index).tz_localize('UTC')

        # Convert to session timezone
        idx_local = df.index.tz_convert(tz)
        h, m = map(int, session_open.split(':'))
        open_offset = pd.Timedelta(hours=h, minutes=m)

        # Calculate session ID
        shifted = idx_local - open_offset
        session_id = shifted.floor('D')

        # Time since session open
        session_open_ts = session_id + open_offset
        since_open = idx_local - session_open_ts

        # Mark bars within initial balance period
        is_ib = (since_open >= pd.Timedelta(0)) & (since_open < pd.Timedelta(minutes=ib_minutes))

        # Initialize columns
        df['ib_high'] = np.nan
        df['ib_low'] = np.nan
        df['ib_volume'] = 0.0
        df['ib_vwap'] = np.nan

        # Calculate IB features for each session manually
        tp = (df['high'] + df['low'] + df['close']) / 3.0

        for session in session_id.unique():
            session_mask = (session_id == session)
            session_data = df[session_mask]
            session_ib_mask = is_ib[session_mask]

            if session_ib_mask.sum() > 0:
                # Get IB high/low for this session
                ib_high_val = session_data.loc[session_ib_mask, 'high'].max()
                ib_low_val = session_data.loc[session_ib_mask, 'low'].min()
                ib_volume_val = session_data.loc[session_ib_mask, 'volume'].sum()

                # Calculate IB VWAP
                tp_ib = tp[session_mask].where(session_ib_mask)
                vol_ib = df['volume'][session_mask].where(session_ib_mask)
                ib_vwap_val = (tp_ib * vol_ib).sum() / (vol_ib.sum() + 1e-12)

                # Assign to all bars in this session
                df.loc[session_mask, 'ib_high'] = ib_high_val
                df.loc[session_mask, 'ib_low'] = ib_low_val
                df.loc[session_mask, 'ib_volume'] = ib_volume_val
                df.loc[session_mask, 'ib_vwap'] = ib_vwap_val

        df['ib_range'] = df['ib_high'] - df['ib_low']

        # Breakout flags
        df['ib_breakout_up'] = (df['high'] > df['ib_high']).astype(int)
        df['ib_breakout_down'] = (df['low'] < df['ib_low']).astype(int)

        return df

    @staticmethod
    def add_fair_value_gaps(df: pd.DataFrame, pair: str, min_pips: int = 2) -> pd.DataFrame:
        """
        Add Fair Value Gaps (FVG) detection.

        FVGs are 3-candle imbalances/gaps in price action:
        - Bullish FVG: When candle[i+1].low > candle[i-1].high
        - Bearish FVG: When candle[i+1].high < candle[i-1].low

        These gaps often act as support/resistance and get "filled" later.

        Args:
            df: DataFrame with OHLCV data
            pair: Currency pair for pip calculation
            min_pips: Minimum gap size in pips to filter noise
        """
        pip_size = TechnicalAnalysis.infer_pip_size(pair)

        # Shifted values for 3-candle pattern
        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)
        next_low = df['low'].shift(-1)
        next_high = df['high'].shift(-1)

        # Detect gaps
        bull_mask = (next_low > prev_high)
        bear_mask = (prev_low > next_high)

        # Gap zones
        bull_low = prev_high.where(bull_mask)
        bull_high = next_low.where(bull_mask)
        bear_low = next_high.where(bear_mask)
        bear_high = prev_low.where(bear_mask)

        # Gap sizes
        bull_size = (bull_high - bull_low)
        bear_size = (bear_high - bear_low)

        # Filter by minimum size
        bull_mask &= (bull_size >= min_pips * pip_size)
        bear_mask &= (bear_size >= min_pips * pip_size)

        # Store FVG data
        df['fvg_bull'] = bull_mask.fillna(False).astype(int)
        df['fvg_bull_low'] = bull_low.where(bull_mask)
        df['fvg_bull_high'] = bull_high.where(bull_mask)
        df['fvg_bull_size_pips'] = (bull_size / pip_size).where(bull_mask)

        df['fvg_bear'] = bear_mask.fillna(False).astype(int)
        df['fvg_bear_low'] = bear_low.where(bear_mask)
        df['fvg_bear_high'] = bear_high.where(bear_mask)
        df['fvg_bear_size_pips'] = (bear_size / pip_size).where(bear_mask)

        # Calculate distance to nearest unfilled FVG
        df['fvg_nearest_bull_dist'] = np.nan
        df['fvg_nearest_bear_dist'] = np.nan

        for i in range(len(df)):
            current_price = df['close'].iloc[i]

            # Find nearest unfilled bullish FVG (below current price)
            bull_fvgs = df.iloc[:i][df['fvg_bull'].iloc[:i] == 1]
            if len(bull_fvgs) > 0:
                # Check if unfilled (price hasn't gone back into gap)
                unfilled_bull = []
                for idx, fvg in bull_fvgs.iterrows():
                    fvg_low = fvg['fvg_bull_low']
                    fvg_high = fvg['fvg_bull_high']
                    # Check if any bar after FVG touched the gap
                    idx_loc = df.index.get_loc(idx)
                    future_bars = df.iloc[idx_loc+1:i+1]
                    touched = ((future_bars['low'] <= fvg_high) & (future_bars['high'] >= fvg_low)).any()
                    if not touched:
                        unfilled_bull.append((fvg_high, abs(current_price - fvg_high) / pip_size))

                if unfilled_bull:
                    nearest = min(unfilled_bull, key=lambda x: x[1])
                    df.iloc[i, df.columns.get_loc('fvg_nearest_bull_dist')] = nearest[1]

            # Find nearest unfilled bearish FVG (above current price)
            bear_fvgs = df.iloc[:i][df['fvg_bear'].iloc[:i] == 1]
            if len(bear_fvgs) > 0:
                unfilled_bear = []
                for idx, fvg in bear_fvgs.iterrows():
                    fvg_low = fvg['fvg_bear_low']
                    fvg_high = fvg['fvg_bear_high']
                    idx_loc = df.index.get_loc(idx)
                    future_bars = df.iloc[idx_loc+1:i+1]
                    touched = ((future_bars['low'] <= fvg_high) & (future_bars['high'] >= fvg_low)).any()
                    if not touched:
                        unfilled_bear.append((fvg_low, abs(current_price - fvg_low) / pip_size))

                if unfilled_bear:
                    nearest = min(unfilled_bear, key=lambda x: x[1])
                    df.iloc[i, df.columns.get_loc('fvg_nearest_bear_dist')] = nearest[1]

        return df

    @staticmethod
    def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators to DataFrame."""
        # Use stockstats for easy indicator calculation
        stock = stockstats_wrap(df.copy())

        # RSI
        df['rsi_14'] = stock['rsi_14']

        # MACD
        df['macd'] = stock['macd']
        df['macd_signal'] = stock['macds']
        df['macd_hist'] = stock['macdh']

        # Bollinger Bands
        df['bb_upper'] = stock['boll_ub']
        df['bb_middle'] = stock['boll']
        df['bb_lower'] = stock['boll_lb']

        # Keltner Channels (EMA + ATR)
        ema_20 = df['close'].ewm(span=ForexConfig.KELTNER_PERIOD, adjust=False).mean()
        atr = stock['atr']
        df['keltner_upper'] = ema_20 + (atr * ForexConfig.KELTNER_ATR_MULT)
        df['keltner_middle'] = ema_20
        df['keltner_lower'] = ema_20 - (atr * ForexConfig.KELTNER_ATR_MULT)

        # Moving Averages
        df['ma_9'] = stock['close_9_sma']
        df['ma_21'] = stock['close_21_sma']
        df['ma_50'] = stock['close_50_sma']
        df['ma_200'] = stock['close_200_sma'] if len(df) >= 200 else df['close']

        # ATR (Average True Range)
        df['atr'] = stock['atr']

        # ADX (Average Directional Index)
        df['adx'] = stock[f'dx_{ForexConfig.ADX_PERIOD}_ema']

        # Calculate +DI and -DI manually (stockstats doesn't support pdi/mdi directly)
        period = ForexConfig.ADX_PERIOD

        # True Range
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr_val = tr.rolling(window=period).mean()

        # +DM and -DM
        high_diff = df['high'] - df['high'].shift()
        low_diff = df['low'].shift() - df['low']

        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

        # Smooth +DM and -DM
        plus_dm_smooth = pd.Series(plus_dm).rolling(window=period).mean()
        minus_dm_smooth = pd.Series(minus_dm).rolling(window=period).mean()

        # +DI and -DI
        df['pdi'] = 100 * (plus_dm_smooth / atr_val)
        df['mdi'] = 100 * (minus_dm_smooth / atr_val)

        # Stochastic Oscillator
        df['stoch_k'] = stock[f'kdjk_{ForexConfig.STOCH_K_PERIOD}']
        df['stoch_d'] = stock[f'kdjd_{ForexConfig.STOCH_K_PERIOD}']

        # Williams %R
        df['williams_r'] = stock[f'wr_{ForexConfig.WILLIAMS_R_PERIOD}']

        # CCI (Commodity Channel Index)
        df['cci'] = stock[f'cci_{ForexConfig.CCI_PERIOD}']

        # Volume moving average
        df['volume_ma'] = df['volume'].rolling(20).mean()

        # Parabolic SAR (calculate manually as stockstats doesn't support it)
        # Simplified SAR calculation
        try:
            # Try to use stockstats if it supports it
            df['sar'] = stock['psar']
        except:
            # Manual calculation (simplified)
            # For simplicity, use MA as proxy for SAR (not accurate but functional)
            df['sar'] = df['close'].rolling(10).mean()

        # VWAP (for intraday only - volume weighted average price)
        if len(df) > 0:
            df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()

        # === NEW: Money Flow Index (MFI) - Volume-weighted RSI ===
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']

        # Positive and negative money flow
        price_diff = typical_price - typical_price.shift(1)
        positive_flow = money_flow.where(price_diff > 0, 0)
        negative_flow = money_flow.where(price_diff < 0, 0)

        # 14-period MFI
        positive_mf = positive_flow.rolling(window=14).sum()
        negative_mf = negative_flow.rolling(window=14).sum()
        money_ratio = positive_mf / (negative_mf + 1e-10)
        df['mfi'] = 100 - (100 / (1 + money_ratio))

        # === NEW: Ultimate Oscillator - Multi-timeframe momentum (7, 14, 28 periods) ===
        # Buying pressure and true range
        bp = df['close'] - pd.concat([df['low'], df['close'].shift()], axis=1).min(axis=1)
        tr = pd.concat([
            df['high'] - df['low'],
            abs(df['high'] - df['close'].shift()),
            abs(df['low'] - df['close'].shift())
        ], axis=1).max(axis=1)

        # Calculate averages for 3 timeframes
        avg7 = bp.rolling(7).sum() / (tr.rolling(7).sum() + 1e-10)
        avg14 = bp.rolling(14).sum() / (tr.rolling(14).sum() + 1e-10)
        avg28 = bp.rolling(28).sum() / (tr.rolling(28).sum() + 1e-10)

        # Weighted combination
        df['uo'] = 100 * ((4 * avg7 + 2 * avg14 + avg28) / 7)

        # === NEW: Aroon Indicator - Time since period high/low ===
        aroon_period = 25

        # Calculate periods since high/low
        def periods_since_max(x):
            """Calculate periods since maximum value."""
            if len(x) == 0:
                return 0
            return float(len(x) - 1 - x.values.argmax())

        def periods_since_min(x):
            """Calculate periods since minimum value."""
            if len(x) == 0:
                return 0
            return float(len(x) - 1 - x.values.argmin())

        # Aroon Up: ((period - periods_since_high) / period) * 100
        periods_since_high = df['high'].rolling(aroon_period + 1).apply(periods_since_max, raw=False)
        df['aroon_up'] = ((aroon_period - periods_since_high) / aroon_period) * 100

        # Aroon Down: ((period - periods_since_low) / period) * 100
        periods_since_low = df['low'].rolling(aroon_period + 1).apply(periods_since_min, raw=False)
        df['aroon_down'] = ((aroon_period - periods_since_low) / aroon_period) * 100

        return df

    @staticmethod
    def add_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
        """Add Ichimoku Cloud indicators."""
        # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        period9_high = df['high'].rolling(window=ForexConfig.ICHIMOKU_TENKAN).max()
        period9_low = df['low'].rolling(window=ForexConfig.ICHIMOKU_TENKAN).min()
        df['ichimoku_tenkan'] = (period9_high + period9_low) / 2

        # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        period26_high = df['high'].rolling(window=ForexConfig.ICHIMOKU_KIJUN).max()
        period26_low = df['low'].rolling(window=ForexConfig.ICHIMOKU_KIJUN).min()
        df['ichimoku_kijun'] = (period26_high + period26_low) / 2

        # Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, shifted 26 periods ahead
        df['ichimoku_senkou_a'] = ((df['ichimoku_tenkan'] + df['ichimoku_kijun']) / 2).shift(26)

        # Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, shifted 26 periods ahead
        period52_high = df['high'].rolling(window=ForexConfig.ICHIMOKU_SENKOU_B).max()
        period52_low = df['low'].rolling(window=ForexConfig.ICHIMOKU_SENKOU_B).min()
        df['ichimoku_senkou_b'] = ((period52_high + period52_low) / 2).shift(26)

        # Chikou Span (Lagging Span): Current closing price shifted back 26 periods
        df['ichimoku_chikou'] = df['close'].shift(-26)

        return df

    @staticmethod
    def add_kama(df: pd.DataFrame, n: int = 10, fastest: int = 2, slowest: int = 30) -> pd.DataFrame:
        """
        Add Kaufman Adaptive Moving Average (KAMA).

        KAMA adapts to market volatility using an efficiency ratio:
        - Fast in trending markets (high efficiency)
        - Slow in choppy markets (low efficiency)

        This reduces whipsaws and false signals compared to traditional MAs.

        Formula:
        1. Efficiency Ratio (ER) = |Change| / Volatility
           - Change = abs(Close(n) - Close(0))
           - Volatility = sum(abs(Close(i) - Close(i-1))) over n periods

        2. Smoothing Constant (SC) = [ER × (Fast - Slow) + Slow]²
           - Fast = 2/(fastest+1)
           - Slow = 2/(slowest+1)

        3. KAMA(i) = KAMA(i-1) + SC × (Price - KAMA(i-1))

        Args:
            df: DataFrame with OHLCV data
            n: Efficiency ratio period (default 10)
            fastest: Fast EMA period (default 2)
            slowest: Slow EMA period (default 30)

        Returns:
            DataFrame with KAMA columns added

        Reference:
            Perry J. Kaufman - "Trading Systems and Methods"
            Article: "The KAMA Advantage" by Nayab Bhutta
        """
        close = df['close']

        # Calculate Efficiency Ratio (ER)
        # ER measures how directional the price movement is
        change = abs(close - close.shift(n))
        volatility = close.diff().abs().rolling(window=n).sum()

        # Avoid division by zero
        er = change / (volatility + 1e-10)

        # Calculate Smoothing Constant (SC)
        # SC adapts between fast and slow based on ER
        fast_sc = 2 / (fastest + 1)
        slow_sc = 2 / (slowest + 1)

        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

        # Calculate KAMA iteratively
        # Start with SMA for first value
        kama = pd.Series(index=df.index, dtype=float)
        kama.iloc[n] = close.iloc[:n+1].mean()

        # Iteratively calculate KAMA
        for i in range(n + 1, len(close)):
            kama.iloc[i] = kama.iloc[i-1] + sc.iloc[i] * (close.iloc[i] - kama.iloc[i-1])

        df['kama'] = kama

        # Additional KAMA-based signals
        # KAMA slope (trend strength)
        df['kama_slope'] = df['kama'].diff(5)  # 5-period slope

        # Price distance from KAMA (overbought/oversold)
        df['kama_distance'] = ((df['close'] - df['kama']) / df['kama']) * 100

        # KAMA vs traditional MA (filter)
        # When KAMA > MA, market is trending (high efficiency)
        ma_20 = df['close'].rolling(20).mean()
        df['kama_vs_ma'] = df['kama'] - ma_20

        return df

    @staticmethod
    def add_donchian_channels(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Add Donchian Channels.

        Donchian Channels identify breakout levels using highest high and lowest low.
        Used by the legendary Turtle Traders for trend-following breakouts.

        Formula:
        - Upper Channel = Highest high over period
        - Lower Channel = Lowest low over period
        - Middle Channel = (Upper + Lower) / 2

        Args:
            df: DataFrame with OHLCV data
            period: Lookback period (default 20)

        Returns:
            DataFrame with Donchian Channel columns added

        Reference:
            Richard Dennis - Turtle Trading System
        """
        # Upper channel: highest high
        df['donchian_upper'] = df['high'].rolling(window=period).max()

        # Lower channel: lowest low
        df['donchian_lower'] = df['low'].rolling(window=period).min()

        # Middle channel: average
        df['donchian_middle'] = (df['donchian_upper'] + df['donchian_lower']) / 2

        # Channel width (volatility measure)
        df['donchian_width'] = df['donchian_upper'] - df['donchian_lower']

        # Breakout signals
        df['donchian_breakout_up'] = (df['close'] > df['donchian_upper'].shift(1)).astype(int)
        df['donchian_breakout_down'] = (df['close'] < df['donchian_lower'].shift(1)).astype(int)

        # Price position within channel (0-100%)
        channel_range = df['donchian_upper'] - df['donchian_lower']
        df['donchian_position'] = ((df['close'] - df['donchian_lower']) / (channel_range + 1e-10)) * 100

        return df

    @staticmethod
    def add_rvi(df: pd.DataFrame, period: int = 10, signal_period: int = 4) -> pd.DataFrame:
        """
        Add Relative Vigor Index (RVI).

        RVI measures trend strength by comparing close position within range.
        Similar to RSI but focuses on vigor (open-close relationship).

        Formula:
        1. Numerator = (Close - Open)
        2. Denominator = (High - Low)
        3. RVI = SMA(Numerator, period) / SMA(Denominator, period)
        4. Signal = SMA(RVI, signal_period)

        Interpretation:
        - RVI > 0: Bullish vigor (closes above opens)
        - RVI < 0: Bearish vigor (closes below opens)
        - RVI crossover Signal: Trend change

        Args:
            df: DataFrame with OHLCV data
            period: RVI period (default 10)
            signal_period: Signal line period (default 4)

        Returns:
            DataFrame with RVI columns added

        Reference:
            John Ehlers - "Cybernetic Analysis for Stocks and Futures"
        """
        # Calculate numerator (close - open)
        numerator = df['close'] - df['open']

        # Calculate denominator (high - low)
        denominator = df['high'] - df['low']

        # RVI = SMA(numerator) / SMA(denominator)
        numerator_sma = numerator.rolling(window=period).mean()
        denominator_sma = denominator.rolling(window=period).mean()

        df['rvi'] = numerator_sma / (denominator_sma + 1e-10)

        # Signal line (SMA of RVI)
        df['rvi_signal'] = df['rvi'].rolling(window=signal_period).mean()

        # RVI histogram (difference from signal)
        df['rvi_histogram'] = df['rvi'] - df['rvi_signal']

        # Crossover signals
        rvi_cross_up = (df['rvi'] > df['rvi_signal']) & (df['rvi'].shift(1) <= df['rvi_signal'].shift(1))
        rvi_cross_down = (df['rvi'] < df['rvi_signal']) & (df['rvi'].shift(1) >= df['rvi_signal'].shift(1))

        df['rvi_cross_up'] = rvi_cross_up.astype(int)
        df['rvi_cross_down'] = rvi_cross_down.astype(int)

        return df

    @staticmethod
    def add_divergence(df: pd.DataFrame, lookback: int = 14) -> pd.DataFrame:
        """
        Add RSI/MACD Divergence Detection.

        Detects:
        - Bullish Regular Divergence: Price lower low, RSI/MACD higher low
        - Bearish Regular Divergence: Price higher high, RSI/MACD lower high
        - Hidden Divergences: Continuation patterns

        Args:
            df: DataFrame with price and indicator data
            lookback: Period for peak/trough detection

        Returns:
            DataFrame with divergence signals
        """
        # Initialize divergence columns
        df['rsi_bullish_div'] = 0
        df['rsi_bearish_div'] = 0
        df['macd_bullish_div'] = 0
        df['macd_bearish_div'] = 0
        df['rsi_hidden_bull_div'] = 0
        df['rsi_hidden_bear_div'] = 0

        # Initialize summary columns (must exist even if early return)
        df['divergence_bullish'] = 0
        df['divergence_bearish'] = 0
        df['divergence_signal'] = 0

        # Need sufficient data
        if len(df) < lookback * 3:
            return df

        # Ensure indicators exist
        if 'rsi_14' not in df.columns or 'macd' not in df.columns:
            return df

        # Helper function to find peaks (local maxima)
        def find_peaks(series: pd.Series, order: int = 5) -> list:
            """Find local peaks in a series."""
            peaks = []
            for i in range(order, len(series) - order):
                if all(series.iloc[i] > series.iloc[i-j] for j in range(1, order+1)) and \
                   all(series.iloc[i] > series.iloc[i+j] for j in range(1, order+1)):
                    peaks.append(i)
            return peaks

        # Helper function to find troughs (local minima)
        def find_troughs(series: pd.Series, order: int = 5) -> list:
            """Find local troughs in a series."""
            troughs = []
            for i in range(order, len(series) - order):
                if all(series.iloc[i] < series.iloc[i-j] for j in range(1, order+1)) and \
                   all(series.iloc[i] < series.iloc[i+j] for j in range(1, order+1)):
                    troughs.append(i)
            return troughs

        # Find price peaks and troughs
        price_peaks = find_peaks(df['high'], order=3)
        price_troughs = find_troughs(df['low'], order=3)

        # Find RSI peaks and troughs
        rsi_peaks = find_peaks(df['rsi_14'], order=3)
        rsi_troughs = find_troughs(df['rsi_14'], order=3)

        # Find MACD peaks and troughs
        macd_peaks = find_peaks(df['macd'], order=3)
        macd_troughs = find_troughs(df['macd'], order=3)

        # Detect Regular Bearish Divergence (price higher high, RSI lower high)
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            for i in range(len(price_peaks) - 1):
                price_peak1_idx = price_peaks[i]
                price_peak2_idx = price_peaks[i + 1]

                # Price makes higher high
                if df['high'].iloc[price_peak2_idx] > df['high'].iloc[price_peak1_idx]:
                    # Find corresponding RSI peaks
                    rsi_peak1 = None
                    rsi_peak2 = None

                    for rsi_idx in rsi_peaks:
                        if abs(rsi_idx - price_peak1_idx) <= 3:
                            rsi_peak1 = rsi_idx
                        if abs(rsi_idx - price_peak2_idx) <= 3:
                            rsi_peak2 = rsi_idx

                    # RSI makes lower high = Bearish Divergence
                    if rsi_peak1 is not None and rsi_peak2 is not None:
                        if df['rsi_14'].iloc[rsi_peak2] < df['rsi_14'].iloc[rsi_peak1]:
                            df.loc[df.index[price_peak2_idx], 'rsi_bearish_div'] = 1

        # Detect Regular Bullish Divergence (price lower low, RSI higher low)
        if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
            for i in range(len(price_troughs) - 1):
                price_trough1_idx = price_troughs[i]
                price_trough2_idx = price_troughs[i + 1]

                # Price makes lower low
                if df['low'].iloc[price_trough2_idx] < df['low'].iloc[price_trough1_idx]:
                    # Find corresponding RSI troughs
                    rsi_trough1 = None
                    rsi_trough2 = None

                    for rsi_idx in rsi_troughs:
                        if abs(rsi_idx - price_trough1_idx) <= 3:
                            rsi_trough1 = rsi_idx
                        if abs(rsi_idx - price_trough2_idx) <= 3:
                            rsi_trough2 = rsi_idx

                    # RSI makes higher low = Bullish Divergence
                    if rsi_trough1 is not None and rsi_trough2 is not None:
                        if df['rsi_14'].iloc[rsi_trough2] > df['rsi_14'].iloc[rsi_trough1]:
                            df.loc[df.index[price_trough2_idx], 'rsi_bullish_div'] = 1

        # Detect MACD Bearish Divergence
        if len(price_peaks) >= 2 and len(macd_peaks) >= 2:
            for i in range(len(price_peaks) - 1):
                price_peak1_idx = price_peaks[i]
                price_peak2_idx = price_peaks[i + 1]

                if df['high'].iloc[price_peak2_idx] > df['high'].iloc[price_peak1_idx]:
                    macd_peak1 = None
                    macd_peak2 = None

                    for macd_idx in macd_peaks:
                        if abs(macd_idx - price_peak1_idx) <= 3:
                            macd_peak1 = macd_idx
                        if abs(macd_idx - price_peak2_idx) <= 3:
                            macd_peak2 = macd_idx

                    if macd_peak1 is not None and macd_peak2 is not None:
                        if df['macd'].iloc[macd_peak2] < df['macd'].iloc[macd_peak1]:
                            df.loc[df.index[price_peak2_idx], 'macd_bearish_div'] = 1

        # Detect MACD Bullish Divergence
        if len(price_troughs) >= 2 and len(macd_troughs) >= 2:
            for i in range(len(price_troughs) - 1):
                price_trough1_idx = price_troughs[i]
                price_trough2_idx = price_troughs[i + 1]

                if df['low'].iloc[price_trough2_idx] < df['low'].iloc[price_trough1_idx]:
                    macd_trough1 = None
                    macd_trough2 = None

                    for macd_idx in macd_troughs:
                        if abs(macd_idx - price_trough1_idx) <= 3:
                            macd_trough1 = macd_idx
                        if abs(macd_idx - price_trough2_idx) <= 3:
                            macd_trough2 = macd_idx

                    if macd_trough1 is not None and macd_trough2 is not None:
                        if df['macd'].iloc[macd_trough2] > df['macd'].iloc[macd_trough1]:
                            df.loc[df.index[price_trough2_idx], 'macd_bullish_div'] = 1

        # Detect Hidden Divergences (continuation patterns)
        # Hidden Bullish: Price higher low, RSI lower low (trend continuation up)
        if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
            for i in range(len(price_troughs) - 1):
                price_trough1_idx = price_troughs[i]
                price_trough2_idx = price_troughs[i + 1]

                # Price makes higher low
                if df['low'].iloc[price_trough2_idx] > df['low'].iloc[price_trough1_idx]:
                    rsi_trough1 = None
                    rsi_trough2 = None

                    for rsi_idx in rsi_troughs:
                        if abs(rsi_idx - price_trough1_idx) <= 3:
                            rsi_trough1 = rsi_idx
                        if abs(rsi_idx - price_trough2_idx) <= 3:
                            rsi_trough2 = rsi_idx

                    # RSI makes lower low = Hidden Bullish Divergence
                    if rsi_trough1 is not None and rsi_trough2 is not None:
                        if df['rsi_14'].iloc[rsi_trough2] < df['rsi_14'].iloc[rsi_trough1]:
                            df.loc[df.index[price_trough2_idx], 'rsi_hidden_bull_div'] = 1

        # Hidden Bearish: Price lower high, RSI higher high (trend continuation down)
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            for i in range(len(price_peaks) - 1):
                price_peak1_idx = price_peaks[i]
                price_peak2_idx = price_peaks[i + 1]

                # Price makes lower high
                if df['high'].iloc[price_peak2_idx] < df['high'].iloc[price_peak1_idx]:
                    rsi_peak1 = None
                    rsi_peak2 = None

                    for rsi_idx in rsi_peaks:
                        if abs(rsi_idx - price_peak1_idx) <= 3:
                            rsi_peak1 = rsi_idx
                        if abs(rsi_idx - price_peak2_idx) <= 3:
                            rsi_peak2 = rsi_idx

                    # RSI makes higher high = Hidden Bearish Divergence
                    if rsi_peak1 is not None and rsi_peak2 is not None:
                        if df['rsi_14'].iloc[rsi_peak2] > df['rsi_14'].iloc[rsi_peak1]:
                            df.loc[df.index[price_peak2_idx], 'rsi_hidden_bear_div'] = 1

        # Create summary signals (any divergence in last N candles)
        lookback_window = 5
        df['divergence_bullish'] = (
            df['rsi_bullish_div'].rolling(window=lookback_window).sum() +
            df['macd_bullish_div'].rolling(window=lookback_window).sum()
        ).clip(upper=1)  # Binary: 0 or 1

        df['divergence_bearish'] = (
            df['rsi_bearish_div'].rolling(window=lookback_window).sum() +
            df['macd_bearish_div'].rolling(window=lookback_window).sum()
        ).clip(upper=1)  # Binary: 0 or 1

        df['divergence_signal'] = df['divergence_bullish'] - df['divergence_bearish']

        return df

    @staticmethod
    def detect_trend(df: pd.DataFrame) -> str:
        """
        Detect current trend.

        Returns:
            'UP', 'DOWN', or 'SIDEWAYS'
        """
        if 'ma_9' not in df.columns:
            return 'UNKNOWN'

        current_price = df['close'].iloc[-1]
        ma_9 = df['ma_9'].iloc[-1]
        ma_21 = df['ma_21'].iloc[-1]
        ma_50 = df['ma_50'].iloc[-1] if not pd.isna(df['ma_50'].iloc[-1]) else ma_21

        # Strong uptrend
        if current_price > ma_9 > ma_21 > ma_50:
            return 'UP'

        # Strong downtrend
        if current_price < ma_9 < ma_21 < ma_50:
            return 'DOWN'

        # Check recent slope
        ma_21_slope = (df['ma_21'].iloc[-1] - df['ma_21'].iloc[-5]) / 5

        if abs(ma_21_slope) < 0.0001:
            return 'SIDEWAYS'

        return 'UP' if ma_21_slope > 0 else 'DOWN'

    @staticmethod
    def detect_divergence(df: pd.DataFrame) -> Optional[str]:
        """Detect RSI divergence."""
        if len(df) < 20:
            return None

        # Get recent highs/lows
        recent_df = df.tail(20)
        price_high = recent_df['high'].max()
        price_low = recent_df['low'].min()

        price_high_idx = recent_df['high'].idxmax()
        price_low_idx = recent_df['low'].idxmin()

        # Check if RSI diverges
        if 'rsi_14' in df.columns:
            rsi_at_high = df.loc[price_high_idx, 'rsi_14']
            rsi_current = df['rsi_14'].iloc[-1]

            # Bearish divergence (price higher high, RSI lower high)
            if df['close'].iloc[-1] >= price_high * 0.99 and rsi_current < rsi_at_high:
                return 'BEARISH_DIVERGENCE'

            # Bullish divergence (price lower low, RSI higher low)
            rsi_at_low = df.loc[price_low_idx, 'rsi_14']
            if df['close'].iloc[-1] <= price_low * 1.01 and rsi_current > rsi_at_low:
                return 'BULLISH_DIVERGENCE'

        return None


class HedgeFundStrategies:
    """Implement hedge fund trading strategies."""

    @staticmethod
    def detect_mean_reversion(df: pd.DataFrame, current_price: float) -> Dict:
        """
        Detect mean reversion opportunities.

        Hedge funds use mean reversion when price deviates significantly from average.
        """
        signals = []
        strength = 0

        # 1. Bollinger Band bounce
        bb_upper = df['bb_upper'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        bb_middle = df['bb_middle'].iloc[-1]

        if current_price <= bb_lower:
            signals.append("Price at lower Bollinger Band - potential bounce")
            strength += 30
        elif current_price >= bb_upper:
            signals.append("Price at upper Bollinger Band - potential reversal")
            strength += 30

        # 2. RSI oversold/overbought
        rsi = df['rsi_14'].iloc[-1]
        if rsi < 30:
            signals.append(f"RSI oversold ({rsi:.1f}) - bullish reversal likely")
            strength += 25
        elif rsi > 70:
            signals.append(f"RSI overbought ({rsi:.1f}) - bearish reversal likely")
            strength += 25

        # 3. Price deviation from MA
        ma_50 = df['ma_50'].iloc[-1]
        deviation = abs(current_price - ma_50) / ma_50 * 100

        if deviation > 2:  # 2% deviation
            signals.append(f"Price {deviation:.1f}% from MA50 - mean reversion setup")
            strength += 20

        # 4. Stochastic oversold/overbought
        stoch_k = df['stoch_k'].iloc[-1]
        if stoch_k < 20:
            signals.append(f"Stochastic oversold ({stoch_k:.1f}) - bullish reversal")
            strength += 15
        elif stoch_k > 80:
            signals.append(f"Stochastic overbought ({stoch_k:.1f}) - bearish reversal")
            strength += 15

        return {
            'type': 'MEAN_REVERSION',
            'detected': len(signals) >= 2,
            'strength': min(strength, 100),
            'signals': signals
        }

    @staticmethod
    def detect_momentum(df: pd.DataFrame) -> Dict:
        """
        Detect momentum trading opportunities.

        Hedge funds chase strong momentum with confirmation.
        """
        signals = []
        strength = 0
        direction = 'NEUTRAL'

        # 1. MACD crossover
        macd = df['macd'].iloc[-1]
        macd_signal = df['macd_signal'].iloc[-1]
        macd_prev = df['macd'].iloc[-2]
        macd_signal_prev = df['macd_signal'].iloc[-2]

        if macd > macd_signal and macd_prev <= macd_signal_prev:
            signals.append("Bullish MACD crossover confirmed")
            strength += 25
            direction = 'BULLISH'
        elif macd < macd_signal and macd_prev >= macd_signal_prev:
            signals.append("Bearish MACD crossover confirmed")
            strength += 25
            direction = 'BEARISH'

        # 2. ADX trend strength
        adx = df['adx'].iloc[-1]
        pdi = df['pdi'].iloc[-1]
        mdi = df['mdi'].iloc[-1]

        if adx > ForexConfig.ADX_STRONG_TREND:
            if pdi > mdi:
                signals.append(f"Strong uptrend (ADX: {adx:.1f}, +DI > -DI)")
                strength += 30
                direction = 'BULLISH'
            else:
                signals.append(f"Strong downtrend (ADX: {adx:.1f}, -DI > +DI)")
                strength += 30
                direction = 'BEARISH'

        # 3. Moving average momentum
        ma_9 = df['ma_9'].iloc[-1]
        ma_21 = df['ma_21'].iloc[-1]
        ma_50 = df['ma_50'].iloc[-1]

        if ma_9 > ma_21 > ma_50:
            signals.append("Bullish MA alignment (9>21>50)")
            strength += 20
        elif ma_9 < ma_21 < ma_50:
            signals.append("Bearish MA alignment (9<21<50)")
            strength += 20

        # 4. RSI momentum
        rsi = df['rsi_14'].iloc[-1]
        rsi_prev = df['rsi_14'].iloc[-5]

        if rsi > 50 and rsi > rsi_prev:
            signals.append(f"Bullish RSI momentum (RSI: {rsi:.1f})")
            strength += 15
        elif rsi < 50 and rsi < rsi_prev:
            signals.append(f"Bearish RSI momentum (RSI: {rsi:.1f})")
            strength += 15

        return {
            'type': 'MOMENTUM',
            'detected': len(signals) >= 2,
            'direction': direction,
            'strength': min(strength, 100),
            'signals': signals
        }

    @staticmethod
    def detect_trend_following(df: pd.DataFrame, current_price: float) -> Dict:
        """
        Detect trend following opportunities.

        Hedge funds ride established trends with confirmation.
        """
        signals = []
        strength = 0
        direction = 'NEUTRAL'

        # 1. Ichimoku Cloud analysis
        tenkan = df['ichimoku_tenkan'].iloc[-1]
        kijun = df['ichimoku_kijun'].iloc[-1]
        senkou_a = df['ichimoku_senkou_a'].iloc[-1]
        senkou_b = df['ichimoku_senkou_b'].iloc[-1]

        if not pd.isna(senkou_a) and not pd.isna(senkou_b):
            # Price above cloud = bullish
            if current_price > max(senkou_a, senkou_b):
                signals.append("Price above Ichimoku cloud - strong uptrend")
                strength += 30
                direction = 'BULLISH'
            # Price below cloud = bearish
            elif current_price < min(senkou_a, senkou_b):
                signals.append("Price below Ichimoku cloud - strong downtrend")
                strength += 30
                direction = 'BEARISH'

            # Tenkan/Kijun cross
            if tenkan > kijun:
                signals.append("Ichimoku Tenkan > Kijun - bullish")
                strength += 15
            elif tenkan < kijun:
                signals.append("Ichimoku Tenkan < Kijun - bearish")
                strength += 15

        # 2. Moving average trend
        ma_9 = df['ma_9'].iloc[-1]
        ma_21 = df['ma_21'].iloc[-1]
        ma_50 = df['ma_50'].iloc[-1]

        if current_price > ma_9 > ma_21 > ma_50:
            signals.append("Strong bullish trend (price > all MAs)")
            strength += 25
            direction = 'BULLISH'
        elif current_price < ma_9 < ma_21 < ma_50:
            signals.append("Strong bearish trend (price < all MAs)")
            strength += 25
            direction = 'BEARISH'

        # 3. ADX confirms trend
        adx = df['adx'].iloc[-1]
        if adx > 30:
            signals.append(f"Very strong trend (ADX: {adx:.1f})")
            strength += 20

        # 4. Parabolic SAR
        sar = df['sar'].iloc[-1]
        if current_price > sar:
            signals.append("Parabolic SAR bullish (price > SAR)")
            strength += 10
        elif current_price < sar:
            signals.append("Parabolic SAR bearish (price < SAR)")
            strength += 10

        return {
            'type': 'TREND_FOLLOWING',
            'detected': len(signals) >= 2,
            'direction': direction,
            'strength': min(strength, 100),
            'signals': signals
        }

    @staticmethod
    def detect_breakout(df: pd.DataFrame, current_price: float, support: List[float], resistance: List[float]) -> Dict:
        """
        Detect breakout opportunities.

        Hedge funds trade breakouts with volume confirmation.
        """
        signals = []
        strength = 0
        direction = 'NEUTRAL'

        # 1. Support/resistance breakout
        if resistance:
            nearest_resistance = min([r for r in resistance if r > current_price], default=None)
            if nearest_resistance:
                distance_to_resistance = (nearest_resistance - current_price) / current_price * 100
                if distance_to_resistance < 0.1:  # Within 0.1%
                    signals.append(f"At resistance {nearest_resistance:.5f} - breakout pending")
                    strength += 30
                    direction = 'BULLISH'

        if support:
            nearest_support = max([s for s in support if s < current_price], default=None)
            if nearest_support:
                distance_to_support = (current_price - nearest_support) / current_price * 100
                if distance_to_support < 0.1:  # Within 0.1%
                    signals.append(f"At support {nearest_support:.5f} - breakdown pending")
                    strength += 30
                    direction = 'BEARISH'

        # 2. Bollinger/Keltner squeeze
        bb_width = (df['bb_upper'].iloc[-1] - df['bb_lower'].iloc[-1]) / df['bb_middle'].iloc[-1]
        keltner_width = (df['keltner_upper'].iloc[-1] - df['keltner_lower'].iloc[-1]) / df['keltner_middle'].iloc[-1]

        if bb_width < keltner_width:
            signals.append("Bollinger squeeze inside Keltner - volatility breakout coming")
            strength += 25

        # 3. Volume confirmation
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume_ma'].iloc[-1]

        if current_volume > avg_volume * 1.5:
            signals.append(f"High volume ({current_volume/avg_volume:.1f}x avg) - breakout confirmed")
            strength += 20

        # 4. ATR expansion
        atr = df['atr'].iloc[-1]
        atr_ma = df['atr'].rolling(20).mean().iloc[-1]

        if atr > atr_ma * 1.2:
            signals.append("ATR expanding - increased volatility")
            strength += 15

        return {
            'type': 'BREAKOUT',
            'detected': len(signals) >= 2,
            'direction': direction,
            'strength': min(strength, 100),
            'signals': signals
        }


class SupportResistance:
    """Detect support and resistance levels."""

    @staticmethod
    def find_levels(df: pd.DataFrame, window: int = 10) -> Tuple[List[float], List[float]]:
        """
        Find support and resistance levels.

        Returns:
            (support_levels, resistance_levels)
        """
        highs = df['high'].values
        lows = df['low'].values

        # Find local maxima (resistance)
        resistance = []
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i-window:i+window+1]):
                resistance.append(highs[i])

        # Find local minima (support)
        support = []
        for i in range(window, len(lows) - window):
            if lows[i] == min(lows[i-window:i+window+1]):
                support.append(lows[i])

        # Group similar levels
        def group_levels(levels: List[float], tolerance: float = 0.0005) -> List[float]:
            if not levels:
                return []

            grouped = []
            levels = sorted(levels)
            current_group = [levels[0]]

            for level in levels[1:]:
                if abs(level - current_group[-1]) / current_group[-1] < tolerance:
                    current_group.append(level)
                else:
                    grouped.append(np.mean(current_group))
                    current_group = [level]

            grouped.append(np.mean(current_group))
            return grouped

        return (
            group_levels(support),
            group_levels(resistance)
        )

    @staticmethod
    def nearest_levels(
        current_price: float,
        support: List[float],
        resistance: List[float]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Find nearest support and resistance."""
        support_below = [s for s in support if s < current_price]
        resistance_above = [r for r in resistance if r > current_price]

        nearest_support = max(support_below) if support_below else None
        nearest_resistance = min(resistance_above) if resistance_above else None

        return nearest_support, nearest_resistance


class ForexAnalyzer:
    """Main analyzer combining data fetching and TA."""

    def __init__(self, api_key: str):
        self.data_fetcher = ForexDataFetcher(api_key)
        self.ta = TechnicalAnalysis()
        self.sr = SupportResistance()
        self.hedge_strategies = HedgeFundStrategies()

        # Finnhub API integrations (disabled for IG - not available)
        # IG uses different data source, so these are set to None
        self.patterns = None
        self.indicators = None
        self.finnhub_sr = None

    def analyze(
        self,
        pair: str,
        primary_tf: str = '5',
        secondary_tf: str = '1'
    ) -> Dict:
        """
        Perform complete technical analysis on a pair.

        Returns:
            Dictionary with all analysis data
        """
        # Fetch data for both timeframes (REDUCED to respect IG demo account limits)
        # Demo limit: ~60-100 data points/min. Was 1000/pair (500+500), now 200/pair (100+100)
        df_primary = self.data_fetcher.get_candles(pair, primary_tf, count=100)
        df_secondary = self.data_fetcher.get_candles(pair, secondary_tf, count=100)

        # Add basic indicators
        df_primary = self.ta.add_indicators(df_primary)
        df_secondary = self.ta.add_indicators(df_secondary)

        # Add Ichimoku Cloud
        df_primary = self.ta.add_ichimoku(df_primary)
        df_secondary = self.ta.add_ichimoku(df_secondary)

        # Add KAMA (Kaufman Adaptive Moving Average)
        df_primary = self.ta.add_kama(df_primary, n=10, fastest=2, slowest=30)
        df_secondary = self.ta.add_kama(df_secondary, n=10, fastest=2, slowest=30)

        # Add Donchian Channels (Turtle Trading breakout system)
        df_primary = self.ta.add_donchian_channels(df_primary, period=20)
        df_secondary = self.ta.add_donchian_channels(df_secondary, period=20)

        # Add RVI (Relative Vigor Index)
        df_primary = self.ta.add_rvi(df_primary, period=10, signal_period=4)
        df_secondary = self.ta.add_rvi(df_secondary, period=10, signal_period=4)

        # Add Divergence Detection (RSI/MACD)
        df_primary = self.ta.add_divergence(df_primary, lookback=14)
        df_secondary = self.ta.add_divergence(df_secondary, lookback=14)

        # Add advanced volume and market structure indicators (adjusted for 100 candles)
        df_primary = self.ta.add_obv(df_primary, ema_span=20, zscore_window=50)
        df_primary = self.ta.add_vpvr_features(df_primary, pair, window_bars=90, bin_pips=5)  # Reduced from 300
        df_primary = self.ta.add_initial_balance(df_primary, tz='America/New_York', session_open='17:00', ib_minutes=60)
        df_primary = self.ta.add_fair_value_gaps(df_primary, pair, min_pips=2)

        # Add advanced indicators to secondary timeframe too (shorter window)
        df_secondary = self.ta.add_obv(df_secondary, ema_span=10, zscore_window=30)
        df_secondary = self.ta.add_vpvr_features(df_secondary, pair, window_bars=80, bin_pips=3)  # Reduced from 200
        df_secondary = self.ta.add_fair_value_gaps(df_secondary, pair, min_pips=1)

        # Current price
        current_price = float(df_primary['close'].iloc[-1])

        # Trend analysis
        trend_primary = self.ta.detect_trend(df_primary)
        trend_secondary = self.ta.detect_trend(df_secondary)

        # Divergence
        divergence = self.ta.detect_divergence(df_primary)

        # Support/Resistance (custom implementation)
        support, resistance = self.sr.find_levels(df_primary)
        nearest_support, nearest_resistance = self.sr.nearest_levels(
            current_price, support, resistance
        )

        # Finnhub pattern recognition (if enabled)
        patterns_data = {}
        if ForexConfig.ENABLE_FINNHUB_PATTERNS:
            patterns_data = self.patterns.get_patterns(pair, 'D')

        # Finnhub aggregate indicators (if enabled)
        aggregate_indicators = {}
        if ForexConfig.ENABLE_FINNHUB_INDICATORS:
            aggregate_indicators = self.indicators.get_aggregate_indicators(pair, 'D')

        # Finnhub support/resistance (if enabled)
        finnhub_sr_data = {}
        if ForexConfig.ENABLE_FINNHUB_SUPPORT_RESISTANCE:
            finnhub_sr_data = self.finnhub_sr.get_levels(pair, 'D')

        # Hedge fund strategies
        hedge_strategies = {
            'mean_reversion': self.hedge_strategies.detect_mean_reversion(df_primary, current_price),
            'momentum': self.hedge_strategies.detect_momentum(df_primary),
            'trend_following': self.hedge_strategies.detect_trend_following(df_primary, current_price),
            'breakout': self.hedge_strategies.detect_breakout(df_primary, current_price, support, resistance),
        }

        # Indicators (primary timeframe) - comprehensive list with 40+ indicators
        indicators = {
            # Core indicators
            'rsi_14': float(df_primary['rsi_14'].iloc[-1]) if not pd.isna(df_primary['rsi_14'].iloc[-1]) else 50.0,
            'macd': float(df_primary['macd'].iloc[-1]) if not pd.isna(df_primary['macd'].iloc[-1]) else 0.0,
            'macd_signal': float(df_primary['macd_signal'].iloc[-1]) if not pd.isna(df_primary['macd_signal'].iloc[-1]) else 0.0,
            'macd_hist': float(df_primary['macd_hist'].iloc[-1]) if not pd.isna(df_primary['macd_hist'].iloc[-1]) else 0.0,
            'atr': float(df_primary['atr'].iloc[-1]) if not pd.isna(df_primary['atr'].iloc[-1]) else 0.0001,

            # Moving averages
            'ma_9': float(df_primary['ma_9'].iloc[-1]) if not pd.isna(df_primary['ma_9'].iloc[-1]) else current_price,
            'ma_21': float(df_primary['ma_21'].iloc[-1]) if not pd.isna(df_primary['ma_21'].iloc[-1]) else current_price,
            'ma_50': float(df_primary['ma_50'].iloc[-1]) if not pd.isna(df_primary['ma_50'].iloc[-1]) else current_price,

            # Bollinger Bands
            'bb_upper': float(df_primary['bb_upper'].iloc[-1]) if not pd.isna(df_primary['bb_upper'].iloc[-1]) else current_price,
            'bb_middle': float(df_primary['bb_middle'].iloc[-1]) if not pd.isna(df_primary['bb_middle'].iloc[-1]) else current_price,
            'bb_lower': float(df_primary['bb_lower'].iloc[-1]) if not pd.isna(df_primary['bb_lower'].iloc[-1]) else current_price,

            # Keltner Channels
            'keltner_upper': float(df_primary['keltner_upper'].iloc[-1]) if not pd.isna(df_primary['keltner_upper'].iloc[-1]) else current_price,
            'keltner_middle': float(df_primary['keltner_middle'].iloc[-1]) if not pd.isna(df_primary['keltner_middle'].iloc[-1]) else current_price,
            'keltner_lower': float(df_primary['keltner_lower'].iloc[-1]) if not pd.isna(df_primary['keltner_lower'].iloc[-1]) else current_price,

            # ADX (trend strength)
            'adx': float(df_primary['adx'].iloc[-1]) if not pd.isna(df_primary['adx'].iloc[-1]) else 20.0,
            'pdi': float(df_primary['pdi'].iloc[-1]) if not pd.isna(df_primary['pdi'].iloc[-1]) else 20.0,
            'mdi': float(df_primary['mdi'].iloc[-1]) if not pd.isna(df_primary['mdi'].iloc[-1]) else 20.0,

            # Stochastic
            'stoch_k': float(df_primary['stoch_k'].iloc[-1]) if not pd.isna(df_primary['stoch_k'].iloc[-1]) else 50.0,
            'stoch_d': float(df_primary['stoch_d'].iloc[-1]) if not pd.isna(df_primary['stoch_d'].iloc[-1]) else 50.0,

            # Williams %R
            'williams_r': float(df_primary['williams_r'].iloc[-1]) if not pd.isna(df_primary['williams_r'].iloc[-1]) else -50.0,

            # CCI
            'cci': float(df_primary['cci'].iloc[-1]) if not pd.isna(df_primary['cci'].iloc[-1]) else 0.0,

            # === NEW: Money Flow Index (MFI) ===
            'mfi': float(df_primary['mfi'].iloc[-1]) if not pd.isna(df_primary['mfi'].iloc[-1]) else 50.0,

            # === NEW: Ultimate Oscillator ===
            'uo': float(df_primary['uo'].iloc[-1]) if not pd.isna(df_primary['uo'].iloc[-1]) else 50.0,

            # === NEW: Aroon Indicator ===
            'aroon_up': float(df_primary['aroon_up'].iloc[-1]) if not pd.isna(df_primary['aroon_up'].iloc[-1]) else 50.0,
            'aroon_down': float(df_primary['aroon_down'].iloc[-1]) if not pd.isna(df_primary['aroon_down'].iloc[-1]) else 50.0,

            # Parabolic SAR
            'sar': float(df_primary['sar'].iloc[-1]) if not pd.isna(df_primary['sar'].iloc[-1]) else current_price,

            # VWAP
            'vwap': float(df_primary['vwap'].iloc[-1]) if not pd.isna(df_primary['vwap'].iloc[-1]) else current_price,

            # Ichimoku Cloud
            'ichimoku_tenkan': float(df_primary['ichimoku_tenkan'].iloc[-1]) if not pd.isna(df_primary['ichimoku_tenkan'].iloc[-1]) else current_price,
            'ichimoku_kijun': float(df_primary['ichimoku_kijun'].iloc[-1]) if not pd.isna(df_primary['ichimoku_kijun'].iloc[-1]) else current_price,
            'ichimoku_senkou_a': float(df_primary['ichimoku_senkou_a'].iloc[-1]) if not pd.isna(df_primary['ichimoku_senkou_a'].iloc[-1]) else current_price,
            'ichimoku_senkou_b': float(df_primary['ichimoku_senkou_b'].iloc[-1]) if not pd.isna(df_primary['ichimoku_senkou_b'].iloc[-1]) else current_price,

            # === NEW: KAMA (Kaufman Adaptive Moving Average) ===
            'kama': float(df_primary['kama'].iloc[-1]) if not pd.isna(df_primary['kama'].iloc[-1]) else current_price,
            'kama_slope': float(df_primary['kama_slope'].iloc[-1]) if not pd.isna(df_primary['kama_slope'].iloc[-1]) else 0.0,
            'kama_distance': float(df_primary['kama_distance'].iloc[-1]) if not pd.isna(df_primary['kama_distance'].iloc[-1]) else 0.0,
            'kama_vs_ma': float(df_primary['kama_vs_ma'].iloc[-1]) if not pd.isna(df_primary['kama_vs_ma'].iloc[-1]) else 0.0,

            # === NEW: Donchian Channels (Turtle Trading) ===
            'donchian_upper': float(df_primary['donchian_upper'].iloc[-1]) if not pd.isna(df_primary['donchian_upper'].iloc[-1]) else current_price,
            'donchian_lower': float(df_primary['donchian_lower'].iloc[-1]) if not pd.isna(df_primary['donchian_lower'].iloc[-1]) else current_price,
            'donchian_middle': float(df_primary['donchian_middle'].iloc[-1]) if not pd.isna(df_primary['donchian_middle'].iloc[-1]) else current_price,
            'donchian_width': float(df_primary['donchian_width'].iloc[-1]) if not pd.isna(df_primary['donchian_width'].iloc[-1]) else 0.0,
            'donchian_breakout_up': int(df_primary['donchian_breakout_up'].iloc[-1]) if not pd.isna(df_primary['donchian_breakout_up'].iloc[-1]) else 0,
            'donchian_breakout_down': int(df_primary['donchian_breakout_down'].iloc[-1]) if not pd.isna(df_primary['donchian_breakout_down'].iloc[-1]) else 0,
            'donchian_position': float(df_primary['donchian_position'].iloc[-1]) if not pd.isna(df_primary['donchian_position'].iloc[-1]) else 50.0,

            # === NEW: RVI (Relative Vigor Index) ===
            'rvi': float(df_primary['rvi'].iloc[-1]) if not pd.isna(df_primary['rvi'].iloc[-1]) else 0.0,
            'rvi_signal': float(df_primary['rvi_signal'].iloc[-1]) if not pd.isna(df_primary['rvi_signal'].iloc[-1]) else 0.0,
            'rvi_histogram': float(df_primary['rvi_histogram'].iloc[-1]) if not pd.isna(df_primary['rvi_histogram'].iloc[-1]) else 0.0,
            'rvi_cross_up': int(df_primary['rvi_cross_up'].iloc[-1]) if not pd.isna(df_primary['rvi_cross_up'].iloc[-1]) else 0,
            'rvi_cross_down': int(df_primary['rvi_cross_down'].iloc[-1]) if not pd.isna(df_primary['rvi_cross_down'].iloc[-1]) else 0,

            # === NEW: Divergence Detection (RSI/MACD) ===
            'rsi_bullish_div': int(df_primary['rsi_bullish_div'].iloc[-1]) if not pd.isna(df_primary['rsi_bullish_div'].iloc[-1]) else 0,
            'rsi_bearish_div': int(df_primary['rsi_bearish_div'].iloc[-1]) if not pd.isna(df_primary['rsi_bearish_div'].iloc[-1]) else 0,
            'macd_bullish_div': int(df_primary['macd_bullish_div'].iloc[-1]) if not pd.isna(df_primary['macd_bullish_div'].iloc[-1]) else 0,
            'macd_bearish_div': int(df_primary['macd_bearish_div'].iloc[-1]) if not pd.isna(df_primary['macd_bearish_div'].iloc[-1]) else 0,
            'rsi_hidden_bull_div': int(df_primary['rsi_hidden_bull_div'].iloc[-1]) if not pd.isna(df_primary['rsi_hidden_bull_div'].iloc[-1]) else 0,
            'rsi_hidden_bear_div': int(df_primary['rsi_hidden_bear_div'].iloc[-1]) if not pd.isna(df_primary['rsi_hidden_bear_div'].iloc[-1]) else 0,
            'divergence_bullish': int(df_primary['divergence_bullish'].iloc[-1]) if not pd.isna(df_primary['divergence_bullish'].iloc[-1]) else 0,
            'divergence_bearish': int(df_primary['divergence_bearish'].iloc[-1]) if not pd.isna(df_primary['divergence_bearish'].iloc[-1]) else 0,
            'divergence_signal': int(df_primary['divergence_signal'].iloc[-1]) if not pd.isna(df_primary['divergence_signal'].iloc[-1]) else 0,

            # === NEW: Volume Indicators (OBV) ===
            'obv': float(df_primary['obv'].iloc[-1]) if not pd.isna(df_primary['obv'].iloc[-1]) else 0.0,
            'obv_ema': float(df_primary['obv_ema'].iloc[-1]) if not pd.isna(df_primary['obv_ema'].iloc[-1]) else 0.0,
            'obv_zscore': float(df_primary['obv_zscore'].iloc[-1]) if not pd.isna(df_primary['obv_zscore'].iloc[-1]) else 0.0,
            'obv_change_rate': float(df_primary['obv_change_rate'].iloc[-1]) if not pd.isna(df_primary['obv_change_rate'].iloc[-1]) else 0.0,

            # === NEW: Volume Profile (VPVR) ===
            'vpvr_poc': float(df_primary['vpvr_poc'].iloc[-1]) if not pd.isna(df_primary['vpvr_poc'].iloc[-1]) else current_price,
            'vpvr_vah': float(df_primary['vpvr_vah'].iloc[-1]) if not pd.isna(df_primary['vpvr_vah'].iloc[-1]) else current_price,
            'vpvr_val': float(df_primary['vpvr_val'].iloc[-1]) if not pd.isna(df_primary['vpvr_val'].iloc[-1]) else current_price,
            'vpvr_dist_poc': float(df_primary['vpvr_dist_poc'].iloc[-1]) if not pd.isna(df_primary['vpvr_dist_poc'].iloc[-1]) else 0.0,
            'vpvr_position': int(df_primary['vpvr_position'].iloc[-1]) if not pd.isna(df_primary['vpvr_position'].iloc[-1]) else 0,

            # === NEW: Initial Balance (First Hour) ===
            'ib_high': float(df_primary['ib_high'].iloc[-1]) if not pd.isna(df_primary['ib_high'].iloc[-1]) else current_price,
            'ib_low': float(df_primary['ib_low'].iloc[-1]) if not pd.isna(df_primary['ib_low'].iloc[-1]) else current_price,
            'ib_range': float(df_primary['ib_range'].iloc[-1]) if not pd.isna(df_primary['ib_range'].iloc[-1]) else 0.0,
            'ib_volume': float(df_primary['ib_volume'].iloc[-1]) if not pd.isna(df_primary['ib_volume'].iloc[-1]) else 0.0,
            'ib_vwap': float(df_primary['ib_vwap'].iloc[-1]) if not pd.isna(df_primary['ib_vwap'].iloc[-1]) else current_price,
            'ib_breakout_up': int(df_primary['ib_breakout_up'].iloc[-1]) if not pd.isna(df_primary['ib_breakout_up'].iloc[-1]) else 0,
            'ib_breakout_down': int(df_primary['ib_breakout_down'].iloc[-1]) if not pd.isna(df_primary['ib_breakout_down'].iloc[-1]) else 0,

            # === NEW: Fair Value Gaps (FVG) ===
            'fvg_bull': int(df_primary['fvg_bull'].iloc[-1]) if not pd.isna(df_primary['fvg_bull'].iloc[-1]) else 0,
            'fvg_bull_low': float(df_primary['fvg_bull_low'].iloc[-1]) if not pd.isna(df_primary['fvg_bull_low'].iloc[-1]) else 0.0,
            'fvg_bull_high': float(df_primary['fvg_bull_high'].iloc[-1]) if not pd.isna(df_primary['fvg_bull_high'].iloc[-1]) else 0.0,
            'fvg_bull_size_pips': float(df_primary['fvg_bull_size_pips'].iloc[-1]) if not pd.isna(df_primary['fvg_bull_size_pips'].iloc[-1]) else 0.0,
            'fvg_bear': int(df_primary['fvg_bear'].iloc[-1]) if not pd.isna(df_primary['fvg_bear'].iloc[-1]) else 0,
            'fvg_bear_low': float(df_primary['fvg_bear_low'].iloc[-1]) if not pd.isna(df_primary['fvg_bear_low'].iloc[-1]) else 0.0,
            'fvg_bear_high': float(df_primary['fvg_bear_high'].iloc[-1]) if not pd.isna(df_primary['fvg_bear_high'].iloc[-1]) else 0.0,
            'fvg_bear_size_pips': float(df_primary['fvg_bear_size_pips'].iloc[-1]) if not pd.isna(df_primary['fvg_bear_size_pips'].iloc[-1]) else 0.0,
            'fvg_nearest_bull_dist': float(df_primary['fvg_nearest_bull_dist'].iloc[-1]) if not pd.isna(df_primary['fvg_nearest_bull_dist'].iloc[-1]) else 999.0,
            'fvg_nearest_bear_dist': float(df_primary['fvg_nearest_bear_dist'].iloc[-1]) if not pd.isna(df_primary['fvg_nearest_bear_dist'].iloc[-1]) else 999.0,
        }

        return {
            'pair': pair,
            'current_price': current_price,
            'trend_primary': trend_primary,
            'trend_secondary': trend_secondary,
            'divergence': divergence,
            'support': support,
            'resistance': resistance,
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'indicators': indicators,
            'hedge_strategies': hedge_strategies,
            'df_primary': df_primary,
            'df_secondary': df_secondary,
            'patterns': patterns_data,
            'aggregate_indicators': aggregate_indicators,
            'finnhub_support_resistance': finnhub_sr_data,
            'timestamp': datetime.now()
        }

    def calculate_sl_tp(
        self,
        entry: float,
        signal: str,
        atr: float,
        nearest_support: Optional[float] = None,
        nearest_resistance: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit levels.

        Args:
            entry: Entry price
            signal: 'BUY' or 'SELL'
            atr: Average True Range
            nearest_support: Nearest support level
            nearest_resistance: Nearest resistance level

        Returns:
            (stop_loss, take_profit)
        """
        # Use ATR-based stops
        atr_multiplier_sl = 1.5
        atr_multiplier_tp = 3.0

        if signal == 'BUY':
            # Stop below entry
            sl_atr = entry - (atr * atr_multiplier_sl)
            # Use support if closer
            sl = min(sl_atr, nearest_support) if nearest_support and nearest_support < entry else sl_atr

            # Take profit above entry
            tp_atr = entry + (atr * atr_multiplier_tp)
            # Use resistance if closer
            tp = max(tp_atr, nearest_resistance * 0.99) if nearest_resistance and nearest_resistance > entry else tp_atr

        else:  # SELL
            # Stop above entry
            sl_atr = entry + (atr * atr_multiplier_sl)
            # Use resistance if closer
            sl = max(sl_atr, nearest_resistance) if nearest_resistance and nearest_resistance > entry else sl_atr

            # Take profit below entry
            tp_atr = entry - (atr * atr_multiplier_tp)
            # Use support if closer
            tp = min(tp_atr, nearest_support * 1.01) if nearest_support and nearest_support < entry else tp_atr

        return sl, tp

    def pips_between(self, price1: float, price2: float, pair: str) -> float:
        """Calculate pips between two prices."""
        # For JPY pairs, pip = 0.01
        # For others, pip = 0.0001
        pip_size = 0.01 if 'JPY' in pair else 0.0001
        return abs(price1 - price2) / pip_size


# Quick test function
def test_forex_data():
    """Test the forex data fetching."""
    print("Testing Forex Data Module...")
    print("="*60)

    analyzer = ForexAnalyzer(ForexConfig.IG_API_KEY)

    # Test with EUR/USD
    print("\nAnalyzing EUR/USD...")
    analysis = analyzer.analyze('EUR_USD', '5', '1')

    print(f"Current Price: {analysis['current_price']:.5f}")
    print(f"Trend (5m): {analysis['trend_primary']}")
    print(f"Trend (1m): {analysis['trend_secondary']}")
    print(f"RSI: {analysis['indicators']['rsi_14']:.2f}")
    print(f"MACD: {analysis['indicators']['macd']:.5f}")
    print(f"Divergence: {analysis['divergence']}")
    print(f"Nearest Support: {analysis['nearest_support']}")
    print(f"Nearest Resistance: {analysis['nearest_resistance']}")

    print("\n✓ Forex data module working!")
    print("="*60)


if __name__ == "__main__":
    # Load environment FIRST
    from dotenv import load_dotenv
    import os
    load_dotenv()

    # Verify API key loaded
    if not os.getenv("IG_API_KEY"):
        print("ERROR: IG_API_KEY not found in .env")
        exit(1)

    test_forex_data()
