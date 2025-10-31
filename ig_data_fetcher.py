"""
IG Data Fetcher with Intelligent Caching

Fetches forex market data from IG API for technical analysis.
Uses aggressive caching to stay under IG's 10,000 weekly historical data point quota.

Strategy:
1. Check cache first for requested data
2. If cache has enough fresh data, return it immediately (0 quota used)
3. If cache is stale, fetch only NEW candles (delta update)
4. Store all fetched candles in SQLite cache
5. Track weekly quota usage and warn when approaching limit
"""

import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Optional
from ig_client import IGClient
from forex_config import ForexConfig
from ig_cache_manager import IGCacheManager


class IGDataFetcher:
    """
    Fetches forex candle data from IG API with intelligent caching.

    Provides historical price data compatible with the forex technical analyzer.
    Minimizes IG API quota usage through aggressive local caching.
    """

    def __init__(self, api_key: str, username: Optional[str] = None, password: Optional[str] = None, use_cache: bool = True):
        """
        Initialize IG data fetcher.

        Args:
            api_key: IG API key
            username: IG username (optional, for authenticated requests)
            password: IG password (optional, for authenticated requests)
            use_cache: Enable intelligent caching to minimize quota usage
        """
        self.client = IGClient(
            api_key=api_key,
            base_url="https://demo-api.ig.com/gateway/deal" if ForexConfig.IG_DEMO else "https://api.ig.com/gateway/deal"
        )
        self.username = username
        self.password = password
        self.authenticated = False

        # Initialize cache manager
        self.use_cache = use_cache
        if use_cache:
            self.cache = IGCacheManager()
            print("✅ IG cache manager initialized")

        # Try to authenticate if credentials provided
        if username and password:
            try:
                self.client.create_session(username, password)
                self.authenticated = True
                print(f"✅ IG authenticated: {username}")

                # Show quota status
                if use_cache:
                    self._print_quota_status()
            except Exception as e:
                print(f"⚠️ IG authentication failed: {e}")
                print("   Continuing without authentication (limited data access)")

    def _print_quota_status(self):
        """Print current IG quota usage."""
        if not self.use_cache:
            return

        stats = self.cache.get_cache_stats()
        used = stats['weekly_ig_quota_used']
        remaining = stats['quota_remaining']

        if remaining < 1000:
            print(f"⚠️  IG Quota: {used}/10,000 used - ⚠️ {remaining} remaining!")
        elif remaining < 3000:
            print(f"📊 IG Quota: {used}/10,000 used - {remaining} remaining")
        else:
            print(f"✅ IG Quota: {used}/10,000 used - {remaining} remaining")

    def _get_epic(self, pair: str) -> str:
        """
        Convert pair notation to IG EPIC.

        Args:
            pair: Pair in format 'EUR_USD'

        Returns:
            IG EPIC like 'CS.D.EURUSD.TODAY.IP'
        """
        if pair in ForexConfig.IG_EPIC_MAP:
            return ForexConfig.IG_EPIC_MAP[pair]

        # Fallback: construct EPIC from pair
        clean_pair = pair.replace("_", "")
        return f"CS.D.{clean_pair}.TODAY.IP"

    def _map_timeframe(self, timeframe: str) -> str:
        """
        Map internal timeframe notation to IG resolution.

        Args:
            timeframe: Internal timeframe ('1', '5', '15', etc.)

        Returns:
            IG resolution string
        """
        timeframe_map = {
            '1': 'MINUTE',
            '5': 'MINUTE_5',
            '15': 'MINUTE_15',
            '30': 'MINUTE_30',
            '60': 'HOUR',
            '240': 'HOUR_4',
            '1440': 'DAY',
        }
        return timeframe_map.get(timeframe, 'MINUTE_5')

    def get_candles(self, pair: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        """
        Get historical candles for a pair with intelligent caching.

        Strategy:
        1. Check cache first - if fresh data available, return it (0 quota used!)
        2. If cache is stale or empty, fetch only NEW candles (delta update)
        3. Store fetched data in cache
        4. Return requested number of candles from cache

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            timeframe: Timeframe in minutes (e.g., '5', '15', '60')
            count: Number of candles to fetch

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        try:
            # STRATEGY 1: Check cache first (quota-efficient)
            if self.use_cache:
                cached_df = self.cache.get_cached_candles(pair, timeframe, count)

                # Check if cached data is fresh enough
                if cached_df is not None and not self.cache.needs_update(pair, timeframe, max_age_minutes=5):
                    # Fresh cached data available - return immediately (0 quota used!)
                    print(f"   💾 Using cached data for {pair} (0 quota)")
                    return cached_df

                # Cache is stale or insufficient - need to fetch updates
                last_ts = self.cache.get_last_timestamp(pair, timeframe)

                if last_ts:
                    # We have some cached data - fetch only delta (new candles)
                    # Calculate how many new candles we need based on timeframe
                    now = datetime.now().timestamp()
                    age_seconds = now - last_ts
                    timeframe_minutes = int(timeframe)
                    new_candles_needed = int(age_seconds / (timeframe_minutes * 60)) + 5  # +5 buffer

                    # Limit to reasonable amount
                    fetch_count = min(new_candles_needed, 50)
                    print(f"   🔄 Fetching {fetch_count} new candles for {pair} (delta update)")
                else:
                    # No cached data - initial fetch
                    fetch_count = count
                    print(f"   📥 Initial fetch of {fetch_count} candles for {pair}")
            else:
                # Cache disabled - fetch full amount
                fetch_count = count

            # STRATEGY 2: Fetch from IG
            # Get IG EPIC
            epic = self._get_epic(pair)

            # Map timeframe
            resolution = self._map_timeframe(timeframe)

            # Fetch historical prices from IG
            response = self.client.get_historical_prices(
                epic=epic,
                resolution=resolution,
                max_points=fetch_count
            )

            # RATE LIMIT PROTECTION: Add 2-second delay after historical data request
            time.sleep(2.0)

            # Parse response
            if 'prices' not in response:
                raise ValueError(f"No price data returned for {pair}")

            prices = response['prices']
            if not prices:
                raise ValueError(f"Empty price data for {pair}")

            # Convert to DataFrame
            data = []
            for candle in prices:
                # IG returns snapshot data with ask/bid prices
                # We'll use mid prices (average of ask and bid)
                if 'snapshotTime' in candle:
                    timestamp = candle['snapshotTime']
                elif 'snapshotTimeUTC' in candle:
                    timestamp = candle['snapshotTimeUTC']
                else:
                    continue

                # Get OHLC from ask/bid or mid prices
                if 'openPrice' in candle:
                    # Use provided OHLC
                    open_price = candle['openPrice'].get('mid', candle['openPrice'].get('ask', 0))
                    high_price = candle['highPrice'].get('mid', candle['highPrice'].get('ask', 0))
                    low_price = candle['lowPrice'].get('mid', candle['lowPrice'].get('ask', 0))
                    close_price = candle['closePrice'].get('mid', candle['closePrice'].get('ask', 0))
                else:
                    # Fallback to last traded price if available
                    continue

                # Volume (if available, otherwise 0)
                volume = candle.get('lastTradedVolume', 0)

                data.append({
                    'time': timestamp,
                    'open': float(open_price) if open_price else 0,
                    'high': float(high_price) if high_price else 0,
                    'low': float(low_price) if low_price else 0,
                    'close': float(close_price) if close_price else 0,
                    'volume': float(volume) if volume else 0
                })

            if not data:
                raise ValueError(f"No valid candle data for {pair}")

            # Create DataFrame
            df = pd.DataFrame(data)

            # Convert time to datetime
            df['time'] = pd.to_datetime(df['time'])

            # Sort by time
            df = df.sort_values('time')

            # Reset index
            df = df.reset_index(drop=True)

            # Ensure we have the required columns
            df = df[['time', 'open', 'high', 'low', 'close', 'volume']]

            # STRATEGY 3: Store fetched data in cache
            if self.use_cache:
                self.cache.store_candles(pair, timeframe, df, source="ig")

                # Print updated quota status
                stats = self.cache.get_cache_stats()
                used = stats['weekly_ig_quota_used']
                remaining = stats['quota_remaining']
                print(f"   📊 IG Quota: {used:,}/{10000:,} used ({remaining:,} remaining)")

                # Return from cache (ensures we get requested count even with delta updates)
                cached_df = self.cache.get_cached_candles(pair, timeframe, count)
                if cached_df is not None:
                    return cached_df

            # Fallback: return fetched data directly
            return df.tail(count)

        except Exception as e:
            raise ValueError(f"Failed to fetch data for {pair}: {str(e)}")

    def get_current_price(self, pair: str) -> float:
        """
        Get current market price for a pair.

        Args:
            pair: Currency pair (e.g., 'EUR_USD')

        Returns:
            Current mid price
        """
        try:
            # Get latest candle
            df = self.get_candles(pair, '1', count=1)
            if df.empty:
                raise ValueError(f"No price data for {pair}")

            return float(df['close'].iloc[-1])

        except Exception as e:
            raise ValueError(f"Failed to get current price for {pair}: {str(e)}")


# Test
if __name__ == "__main__":
    print("="*80)
    print("IG DATA FETCHER TEST")
    print("="*80)

    # Initialize fetcher
    fetcher = IGDataFetcher(
        api_key=ForexConfig.IG_API_KEY,
        username=ForexConfig.IG_USERNAME or None,
        password=ForexConfig.IG_PASSWORD or None
    )

    print(f"\n📊 Fetching data for EUR/USD...")
    try:
        # Test getting candles
        df = fetcher.get_candles("EUR_USD", "5", count=10)
        print(f"✅ Fetched {len(df)} candles")
        print(f"\nLatest candles:")
        print(df.tail(3))

        # Test getting current price
        price = fetcher.get_current_price("EUR_USD")
        print(f"\n✅ Current EUR/USD price: {price:.5f}")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nNote: Full data access may require authentication.")
        print("Set IG_USERNAME and IG_PASSWORD environment variables to test with credentials.")

    print("\n" + "="*80)
