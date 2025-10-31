"""
IG Data Fetcher using trading-ig library

Fetches forex market data from IG API using the professional trading-ig library.
"""

import pandas as pd
from datetime import datetime
from typing import Optional
from trading_ig import IGService
from forex_config import ForexConfig
from ig_rate_limiter import get_rate_limiter


class IGDataFetcher:
    """
    Fetches forex candle data from IG API using trading-ig library.

    Provides historical price data compatible with the forex technical analyzer.
    """

    def __init__(self, api_key: str = None, username: str = None, password: str = None,
                 acc_number: str = None):
        """
        Initialize IG data fetcher.

        Args:
            api_key: IG API key (defaults to ForexConfig.IG_API_KEY)
            username: IG username (defaults to ForexConfig.IG_USERNAME)
            password: IG password (defaults to ForexConfig.IG_PASSWORD)
            acc_number: IG account number (defaults to ForexConfig.IG_ACC_NUMBER)
        """
        self.api_key = api_key or ForexConfig.IG_API_KEY
        self.username = username or ForexConfig.IG_USERNAME
        self.password = password or ForexConfig.IG_PASSWORD
        self.acc_number = acc_number or ForexConfig.IG_ACC_NUMBER
        self.acc_type = "DEMO" if ForexConfig.IG_DEMO else "LIVE"

        # Create IG service
        self.ig_service = IGService(
            username=self.username,
            password=self.password,
            api_key=self.api_key,
            acc_type=self.acc_type,
            acc_number=self.acc_number
        )

        # Create session
        try:
            self.ig_service.create_session(version="2")
            print(f"✅ IG session created for {self.username} ({self.acc_type})")
        except Exception as e:
            print(f"⚠️ IG authentication failed: {e}")
            raise

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
        Map internal timeframe notation to pandas-style resolution.

        Args:
            timeframe: Internal timeframe ('1', '5', '15', etc.)

        Returns:
            Pandas-style resolution string (e.g., '5Min', '1h')
        """
        timeframe_map = {
            '1': '1Min',
            '5': '5Min',
            '15': '15Min',
            '30': '30Min',
            '60': '1h',
            '240': '4h',
            '1440': 'D',
        }
        return timeframe_map.get(timeframe, '5Min')

    def get_candles(self, pair: str, timeframe: str, count: int = 500) -> pd.DataFrame:
        """
        Get historical candles for a pair.

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            timeframe: Timeframe in minutes (e.g., '5', '15', '60')
            count: Number of candles to fetch

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        try:
            # Wait for rate limiter
            rate_limiter = get_rate_limiter()
            rate_limiter.wait_if_needed(is_account_request=True)

            # Get IG EPIC
            epic = self._get_epic(pair)

            # Map timeframe
            resolution = self._map_timeframe(timeframe)

            # Fetch historical prices from IG
            response = self.ig_service.fetch_historical_prices_by_epic_and_num_points(
                epic=epic,
                resolution=resolution,
                numpoints=count
            )

            # Extract prices DataFrame
            if 'prices' not in response:
                raise ValueError(f"No price data returned for {pair}")

            prices_df = response['prices']
            if prices_df.empty:
                raise ValueError(f"Empty price data for {pair}")

            # Convert multi-level DataFrame to simple OHLCV format
            # Calculate mid prices from bid/ask
            df = pd.DataFrame({
                'time': prices_df.index,
                'open': (prices_df[('bid', 'Open')] + prices_df[('ask', 'Open')]) / 2,
                'high': (prices_df[('bid', 'High')] + prices_df[('ask', 'High')]) / 2,
                'low': (prices_df[('bid', 'Low')] + prices_df[('ask', 'Low')]) / 2,
                'close': (prices_df[('bid', 'Close')] + prices_df[('ask', 'Close')]) / 2,
                'volume': prices_df[('last', 'Volume')].values if ('last', 'Volume') in prices_df.columns else 0
            })

            # Reset index
            df = df.reset_index(drop=True)

            # Ensure time is datetime
            if not pd.api.types.is_datetime64_any_dtype(df['time']):
                df['time'] = pd.to_datetime(df['time'])

            return df

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
    print("IG DATA FETCHER TEST (trading-ig library)")
    print("="*80)

    # Initialize fetcher
    fetcher = IGDataFetcher()

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

    print("\n" + "="*80)
