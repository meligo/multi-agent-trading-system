"""
Unified Data Fetcher - Aggregates data from all sources

Combines:
- DataHub (real-time ticks & candles from WebSocket)
- Finnhub (technical analysis, patterns, S/R)
- DataBento (CME futures order flow via DataHub)
- InsightSentry (news, events, sentiment)
- Database (fallback for historical candles)
"""

import asyncio
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from finnhub_integration import FinnhubIntegration
from finnhub_data_fetcher import FinnhubDataFetcher
from insightsentry_client import InsightSentryClient
from database_manager import DatabaseManager
from data_persistence_manager import DataPersistenceManager

# Import DataHub (new unified data source)
try:
    from data_hub import DataHub
    DATA_HUB_AVAILABLE = True
except ImportError:
    DATA_HUB_AVAILABLE = False
    logging.warning("DataHub not available - running in legacy mode")

logger = logging.getLogger(__name__)


class UnifiedDataFetcher:
    """
    Unified data fetcher that aggregates market data from multiple sources.

    NEW ARCHITECTURE (DataHub-based):
    - Price action (DataHub - real-time from WebSocket)
    - Order flow (DataHub - real-time from DataBento)
    - Technical analysis (Finnhub - direct)
    - News sentiment (InsightSentry - direct)
    - Historical data (Database - fallback)
    """

    def __init__(self, data_hub: Optional[DataHub] = None):
        """
        Initialize unified data fetcher.

        Args:
            data_hub: DataHub instance for real-time data (REQUIRED for real-time trading)
        """
        logger.info("Initializing Unified Data Fetcher...")

        # Primary data source (DataHub)
        self.data_hub = data_hub
        if not self.data_hub:
            logger.warning("⚠️  No DataHub provided - real-time data will be limited!")

        # Secondary data sources (optional)
        self.finnhub_integration: Optional[FinnhubIntegration] = None
        self.finnhub_fetcher: Optional[FinnhubDataFetcher] = None
        self.insightsentry: Optional[InsightSentryClient] = None

        # Database (for historical data fallback)
        self.db: Optional[DatabaseManager] = None
        self.persistence: Optional[DataPersistenceManager] = None

        # Cache (to avoid hitting APIs too frequently)
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl: int = 60  # 60 seconds

        # Futures mapping (for DataBento)
        self.futures_map = {
            'EUR_USD': '6E',  # EUR futures
            'GBP_USD': '6B',  # GBP futures
            'USD_JPY': '6J',  # JPY futures
        }

        logger.info(f"✅ Unified Data Fetcher initialized (DataHub: {'✅' if self.data_hub else '❌'})")

    def inject_sources(
        self,
        data_hub: Optional[DataHub] = None,
        finnhub_integration: Optional[FinnhubIntegration] = None,
        finnhub_fetcher: Optional[FinnhubDataFetcher] = None,
        insightsentry: Optional[InsightSentryClient] = None,
        db: Optional[DatabaseManager] = None,
        persistence: Optional[DataPersistenceManager] = None
    ):
        """
        Inject data sources (allows dashboard to share instances).

        NEW: Uses DataHub as primary data source instead of direct WebSocket/DataBento access.
        """
        if data_hub:
            self.data_hub = data_hub

        self.finnhub_integration = finnhub_integration
        self.finnhub_fetcher = finnhub_fetcher
        self.insightsentry = insightsentry
        self.db = db
        self.persistence = persistence

        logger.info(f"✅ Data sources injected:")
        logger.info(f"   DataHub: {self.data_hub is not None}")
        logger.info(f"   Finnhub Integration: {self.finnhub_integration is not None}")
        logger.info(f"   Finnhub Fetcher: {self.finnhub_fetcher is not None}")
        logger.info(f"   InsightSentry: {self.insightsentry is not None}")
        logger.info(f"   Database: {self.db is not None}")

    def fetch_market_data(self, pair: str, timeframe: str = "1m", bars: int = 100) -> Optional[Dict]:
        """
        Fetch complete market data for a pair from all sources.

        Args:
            pair: Trading pair (EUR_USD, GBP_USD, etc.)
            timeframe: Timeframe (1m, 5m, 15m)
            bars: Number of candles to fetch

        Returns:
            {
                'pair': 'EUR_USD',
                'timestamp': datetime,
                'candles': DataFrame,  # OHLC data
                'spread': 1.0,         # Current spread in pips
                'bid': 1.0500,
                'ask': 1.0510,
                'ta_consensus': {...}, # Finnhub TA
                'patterns': [...],     # Chart patterns
                'support_resistance': {...},
                'order_flow': {...},   # DataBento futures
                'indicators': {...},   # Calculated indicators
            }
        """
        # Check cache first
        cache_key = f"{pair}_{timeframe}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            age = (datetime.utcnow() - cached_data['timestamp']).total_seconds()
            if age < self.cache_ttl:
                logger.debug(f"Using cached data for {pair} (age: {age:.1f}s)")
                return cached_data

        logger.info(f"📊 Fetching market data for {pair} ({timeframe})")

        # Initialize market data structure
        market_data = {
            'pair': pair,
            'timestamp': datetime.utcnow(),
            'candles': None,
            'spread': None,
            'bid': None,
            'ask': None,
            'ta_consensus': None,
            'patterns': None,
            'support_resistance': None,
            'order_flow': None,
            'indicators': None,
        }

        # 1. Fetch IG WebSocket data (primary price source)
        try:
            candles, spread, bid, ask = self._fetch_ig_data(pair, timeframe, bars)
            market_data['candles'] = candles
            market_data['spread'] = spread
            market_data['bid'] = bid
            market_data['ask'] = ask
        except Exception as e:
            logger.warning(f"Failed to fetch IG data for {pair}: {e}")

        # 2. Fetch Finnhub technical analysis
        try:
            ta_data = self._fetch_finnhub_ta(pair, timeframe)
            market_data['ta_consensus'] = ta_data.get('consensus')
            market_data['patterns'] = ta_data.get('patterns')
            market_data['support_resistance'] = ta_data.get('support_resistance')
        except Exception as e:
            logger.warning(f"Failed to fetch Finnhub data for {pair}: {e}")

        # 3. Fetch DataBento order flow (if futures available)
        try:
            if pair in self.futures_map:
                order_flow = self._fetch_order_flow(pair)
                market_data['order_flow'] = order_flow
        except Exception as e:
            logger.warning(f"Failed to fetch DataBento data for {pair}: {e}")

        # 4. Calculate indicators (if we have candles)
        if market_data['candles'] is not None:
            try:
                indicators = self._calculate_indicators(market_data['candles'])
                market_data['indicators'] = indicators
            except Exception as e:
                logger.warning(f"Failed to calculate indicators for {pair}: {e}")

        # Cache the result
        self.cache[cache_key] = market_data

        logger.info(f"✅ Fetched {pair} data: candles={market_data['candles'] is not None}, "
                   f"spread={market_data['spread']}, TA={market_data['ta_consensus'] is not None}")

        return market_data

    def _fetch_ig_data(self, pair: str, timeframe: str, bars: int) -> tuple:
        """
        Fetch candles and spread from DataHub (primary) or Database (fallback).

        NEW IMPLEMENTATION: Uses DataHub instead of direct WebSocket access.
        """
        if not self.data_hub and not self.db:
            logger.warning("No data source available for market data")
            return None, None, None, None

        candles_df = None
        bid, ask, spread = None, None, None

        # PRIMARY: Get candles from DataHub
        if self.data_hub:
            try:
                candles_list = self.data_hub.get_latest_candles(pair, limit=bars * 2)  # Get extra for filtering
                if candles_list:
                    # Separate candles by source
                    databento_candles = [c for c in candles_list if getattr(c, 'source', 'IG') == 'DATABENTO']
                    ig_candles = [c for c in candles_list if getattr(c, 'source', 'IG') == 'IG']

                    # PRIORITY 1: Use DataBento candles (real volume)
                    if databento_candles and len(databento_candles) >= bars * 0.5:
                        logger.info(f"✅ Using DataBento candles (REAL volume) for {pair}: {len(databento_candles)} available")
                        candles_to_use = databento_candles[-bars:]  # Take most recent
                        volume_source = "DATABENTO (real)"
                    # FALLBACK: Use IG candles (tick volume)
                    elif ig_candles:
                        logger.info(f"⚠️ Using IG candles (tick volume) for {pair}: {len(ig_candles)} available (DataBento: {len(databento_candles)})")
                        candles_to_use = ig_candles[-bars:]  # Take most recent
                        volume_source = "IG (tick)"
                    else:
                        candles_to_use = candles_list[-bars:]  # Use whatever we have
                        volume_source = "mixed"

                    # Convert Candle objects to DataFrame
                    candles_df = pd.DataFrame([
                        {
                            'timestamp': c.timestamp,
                            'open': c.open,
                            'high': c.high,
                            'low': c.low,
                            'close': c.close,
                            'volume': c.volume,
                            'volume_source': getattr(c, 'source', 'IG'),
                            'volume_type': getattr(c, 'volume_type', 'tick')
                        }
                        for c in candles_to_use
                    ])
                    if not candles_df.empty:
                        candles_df.set_index('timestamp', inplace=True)
                        candles_df.sort_index(inplace=True)
                        logger.debug(f"Using {volume_source} candles: {len(candles_df)} bars")
            except Exception as e:
                logger.warning(f"DataHub candle fetch error: {e}")

        # FALLBACK: If insufficient candles, try database
        if candles_df is None or len(candles_df) < bars * 0.5:  # Need at least 50% of requested bars
            if self.db:
                try:
                    logger.debug(f"Fetching from database (DataHub had {len(candles_df) if candles_df is not None else 0}/{bars} candles)")
                    db_candles = self._fetch_candles_from_db(pair, timeframe, bars)
                    if db_candles is not None:
                        candles_df = db_candles
                except Exception as e:
                    logger.warning(f"Database candle fetch error: {e}")

        # Get current tick/spread from DataHub
        if self.data_hub:
            try:
                tick = self.data_hub.get_latest_tick(pair)
                if tick:
                    bid = tick.bid
                    ask = tick.ask
                    spread = tick.spread
            except Exception as e:
                logger.warning(f"DataHub tick fetch error: {e}")

        # Fallback: Estimate spread from database if not available
        if spread is None and self.db:
            try:
                spread = self._estimate_spread_from_db(pair)
            except Exception as e:
                logger.warning(f"Database spread estimate error: {e}")

        return candles_df, spread, bid, ask

    def _fetch_candles_from_db(self, pair: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch recent candles from database."""
        if not self.db:
            return None

        # TODO: Implement database candle fetching
        # Query ig_candles table for recent candles
        logger.debug(f"Database candle fetching not yet implemented for {pair}")
        return None

    def _estimate_spread_from_db(self, pair: str) -> Optional[float]:
        """Estimate spread from recent database ticks."""
        if not self.db:
            return None

        # TODO: Implement spread estimation
        # Query ig_spot_ticks for recent ticks and calculate average spread
        logger.debug(f"Database spread estimation not yet implemented for {pair}")
        return None

    def _fetch_finnhub_ta(self, pair: str, timeframe: str) -> Dict:
        """Fetch Finnhub technical analysis data."""
        ta_data = {
            'consensus': None,
            'patterns': None,
            'support_resistance': None
        }

        if not self.finnhub_integration:
            return ta_data

        try:
            # Get aggregate indicators consensus
            aggregate = self.finnhub_integration.get_aggregate_indicators(pair, timeframe)
            if aggregate:
                ta_data['consensus'] = aggregate

            # Get chart patterns
            patterns = self.finnhub_integration.get_patterns(pair, timeframe)
            if patterns:
                ta_data['patterns'] = patterns

            # Get support/resistance levels
            sr_levels = self.finnhub_integration.get_support_resistance(pair)
            if sr_levels:
                ta_data['support_resistance'] = sr_levels

        except Exception as e:
            logger.warning(f"Finnhub TA fetch error: {e}")

        return ta_data

    def _fetch_order_flow(self, pair: str) -> Optional[Dict]:
        """
        Fetch CME futures order flow from DataHub.

        NEW IMPLEMENTATION: Reads from DataHub instead of direct DataBento access.
        """
        if not self.data_hub or pair not in self.futures_map:
            return None

        try:
            # Get latest order flow metrics from DataHub
            metrics = self.data_hub.get_latest_order_flow(pair)
            if metrics:
                # Convert OrderFlowMetrics to dict
                return metrics.to_dict()
            return None
        except Exception as e:
            logger.warning(f"DataHub order flow error: {e}")
            return None

    def _calculate_indicators(self, candles: pd.DataFrame) -> Dict:
        """
        Calculate scalping indicators from candle data.

        Indicators optimized for 1-minute scalping:
        - EMA 3, 6, 12 (fast momentum)
        - VWAP (intraday anchor)
        - RSI(7) (quick overbought/oversold)
        - ADX(7) (trend strength)
        - Donchian Channels (20-period)
        """
        if candles is None or len(candles) == 0:
            return None

        indicators = {}

        try:
            # EMAs (fast)
            indicators['ema_3'] = candles['close'].ewm(span=3, adjust=False).mean().iloc[-1]
            indicators['ema_6'] = candles['close'].ewm(span=6, adjust=False).mean().iloc[-1]
            indicators['ema_12'] = candles['close'].ewm(span=12, adjust=False).mean().iloc[-1]

            # VWAP (if volume available)
            if 'volume' in candles.columns:
                typical_price = (candles['high'] + candles['low'] + candles['close']) / 3
                indicators['vwap'] = (typical_price * candles['volume']).sum() / candles['volume'].sum()

                # Check if we're using real volume or tick volume
                if 'volume_type' in candles.columns:
                    volume_type = candles['volume_type'].iloc[0] if not candles.empty else 'tick'
                    indicators['vwap_type'] = 'true_vwap' if volume_type == 'real' else 'twap'
                    if volume_type == 'tick':
                        logger.debug("⚠️ VWAP calculated with tick volume (TWAP) - not true VWAP")
                    else:
                        logger.debug("✅ VWAP calculated with real volume (true VWAP)")
                else:
                    indicators['vwap_type'] = 'twap'  # Assume tick volume if no metadata
            else:
                indicators['vwap'] = None
                indicators['vwap_type'] = None

            # RSI(7)
            delta = candles['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
            rs = gain / loss
            indicators['rsi_7'] = 100 - (100 / (1 + rs.iloc[-1]))

            # Donchian Channels (20-period)
            indicators['donchian_upper'] = candles['high'].rolling(window=20).max().iloc[-1]
            indicators['donchian_lower'] = candles['low'].rolling(window=20).min().iloc[-1]
            indicators['donchian_mid'] = (indicators['donchian_upper'] + indicators['donchian_lower']) / 2

            # ADX(7) - simplified
            # (Full ADX calculation is complex, this is a quick approximation)
            high_low = candles['high'] - candles['low']
            high_close = abs(candles['high'] - candles['close'].shift())
            low_close = abs(candles['low'] - candles['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr_7 = tr.rolling(window=7).mean().iloc[-1]
            indicators['atr_7'] = atr_7

            # Price position relative to Donchian
            current_price = candles['close'].iloc[-1]
            indicators['price_position'] = (current_price - indicators['donchian_lower']) / (indicators['donchian_upper'] - indicators['donchian_lower'])

            # EMA alignment (bullish if 3 > 6 > 12)
            indicators['ema_bullish'] = indicators['ema_3'] > indicators['ema_6'] > indicators['ema_12']
            indicators['ema_bearish'] = indicators['ema_3'] < indicators['ema_6'] < indicators['ema_12']

        except Exception as e:
            logger.warning(f"Indicator calculation error: {e}")

        return indicators

    def get_spread(self, pair: str) -> Optional[float]:
        """
        Quick spread check for a pair (cached).

        NEW IMPLEMENTATION: Uses DataHub.
        """
        cache_key = f"{pair}_1m"
        if cache_key in self.cache:
            return self.cache[cache_key].get('spread')

        # Fetch spread from DataHub
        if self.data_hub:
            try:
                tick = self.data_hub.get_latest_tick(pair)
                if tick:
                    return tick.spread
            except Exception as e:
                logger.warning(f"DataHub spread fetch error: {e}")

        return None

    def clear_cache(self):
        """Clear cached data."""
        self.cache.clear()
        logger.info("🗑️  Cache cleared")


# Singleton instance (for easy access)
_unified_fetcher_instance: Optional[UnifiedDataFetcher] = None


def get_unified_data_fetcher(data_hub: Optional[DataHub] = None) -> UnifiedDataFetcher:
    """
    Get or create singleton instance.

    Args:
        data_hub: DataHub instance (required for first initialization)

    Returns:
        UnifiedDataFetcher singleton
    """
    global _unified_fetcher_instance
    if _unified_fetcher_instance is None:
        _unified_fetcher_instance = UnifiedDataFetcher(data_hub=data_hub)
    elif data_hub and _unified_fetcher_instance.data_hub is None:
        # Update existing instance with DataHub if it was created without one
        _unified_fetcher_instance.data_hub = data_hub
        logger.info("✅ DataHub injected into existing UnifiedDataFetcher")
    return _unified_fetcher_instance
