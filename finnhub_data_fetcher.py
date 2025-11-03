"""
Finnhub Data Fetcher for Forex Candles

Provides fallback when IG API hits rate limits.
Finnhub free tier: 60 calls/minute
"""

import finnhub
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from forex_config import ForexConfig


class FinnhubDataFetcher:
    """Fetch forex candles from Finnhub API."""

    def __init__(self, api_key: Optional[str] = None, db_manager=None, persistence_manager=None):
        """
        Initialize Finnhub client.

        Args:
            api_key: Finnhub API key (defaults to config)
            db_manager: DatabaseManager instance (optional)
            persistence_manager: DataPersistenceManager instance (optional)
        """
        self.api_key = api_key or ForexConfig.FINNHUB_API_KEY

        if not self.api_key:
            raise ValueError("Finnhub API key not found")

        self.client = finnhub.Client(api_key=self.api_key)

        # Database persistence
        self.db_manager = db_manager
        self.persistence = persistence_manager
        self.persist_enabled = persistence_manager is not None

    def _ig_pair_to_finnhub(self, ig_pair: str) -> str:
        """
        Convert IG format to Finnhub format.

        IG format: EUR_USD, GBP_JPY
        Finnhub format: OANDA:EUR_USD, OANDA:GBP_JPY

        Args:
            ig_pair: Pair in IG format (e.g., 'EUR_USD')

        Returns:
            Pair in Finnhub format (e.g., 'OANDA:EUR_USD')
        """
        # Finnhub uses OANDA provider for forex
        return f"OANDA:{ig_pair}"

    def _timeframe_to_resolution(self, timeframe: str) -> str:
        """
        Convert timeframe to Finnhub resolution.

        Timeframes: '1' (1min), '5' (5min), '15' (15min), '60' (1hour), 'D' (daily)
        Finnhub resolutions: 1, 5, 15, 30, 60, D, W, M

        Args:
            timeframe: Timeframe string

        Returns:
            Finnhub resolution string
        """
        timeframe_map = {
            '1': '1',    # 1 minute
            '5': '5',    # 5 minutes
            '15': '15',  # 15 minutes
            '30': '30',  # 30 minutes
            '60': '60',  # 1 hour
            'D': 'D',    # Daily
            'W': 'W',    # Weekly
            'M': 'M'     # Monthly
        }

        if timeframe not in timeframe_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {list(timeframe_map.keys())}")

        return timeframe_map[timeframe]

    def get_candles(
        self,
        pair: str,
        timeframe: str,
        count: int = 100
    ) -> pd.DataFrame:
        """
        Get forex candles from Finnhub.

        Args:
            pair: Currency pair in IG format (e.g., 'EUR_USD')
            timeframe: Timeframe ('1', '5', '15', '60', 'D')
            count: Number of candles to fetch

        Returns:
            DataFrame with columns: time, open, high, low, close, volume

        Raises:
            ValueError: If API call fails
        """
        try:
            # Convert IG pair format to Finnhub format
            finnhub_symbol = self._ig_pair_to_finnhub(pair)

            # Convert timeframe to Finnhub resolution
            resolution = self._timeframe_to_resolution(timeframe)

            # Calculate time range
            # Finnhub requires Unix timestamps
            now = datetime.now()

            # Estimate how far back to look based on timeframe and count
            if timeframe == '1':
                lookback = timedelta(minutes=count * 2)  # Buffer for weekends
            elif timeframe == '5':
                lookback = timedelta(minutes=count * 5 * 2)
            elif timeframe == '15':
                lookback = timedelta(minutes=count * 15 * 2)
            elif timeframe == '60':
                lookback = timedelta(hours=count * 2)
            elif timeframe == 'D':
                lookback = timedelta(days=count * 2)
            else:
                lookback = timedelta(days=count)  # Default

            from_ts = int((now - lookback).timestamp())
            to_ts = int(now.timestamp())

            # Fetch candles from Finnhub
            response = self.client.forex_candles(
                symbol=finnhub_symbol,
                resolution=resolution,
                _from=from_ts,
                to=to_ts
            )

            # Check if response is valid
            if response['s'] != 'ok':
                raise ValueError(f"Finnhub API returned status: {response['s']}")

            # Convert to DataFrame
            df = pd.DataFrame({
                'time': response['t'],
                'open': response['o'],
                'high': response['h'],
                'low': response['l'],
                'close': response['c'],
                'volume': response.get('v', [0] * len(response['t']))  # Volume may not be available
            })

            # Convert Unix timestamps to datetime
            df['time'] = pd.to_datetime(df['time'], unit='s')

            # Sort by time (oldest first)
            df = df.sort_values('time').reset_index(drop=True)

            # Return last 'count' candles
            result_df = df.tail(count).reset_index(drop=True)

            # Save to database if persistence enabled
            if self.persist_enabled:
                try:
                    candles = result_df.to_dict('records')
                    asyncio.create_task(self.persistence.save_finnhub_candles(
                        symbol=pair,
                        timeframe=timeframe,
                        candles=candles
                    ))
                except Exception as e:
                    print(f"⚠️  Failed to save Finnhub candles: {e}")

            return result_df

        except Exception as e:
            raise ValueError(f"Failed to fetch {pair} from Finnhub: {str(e)}")

    def get_current_price(self, pair: str) -> float:
        """
        Get current price for a currency pair.

        Args:
            pair: Currency pair in IG format (e.g., 'EUR_USD')

        Returns:
            Current bid price

        Raises:
            ValueError: If API call fails
        """
        try:
            # Convert to Finnhub format
            finnhub_symbol = self._ig_pair_to_finnhub(pair)

            # Get forex quote
            quote = self.client.quote(finnhub_symbol)

            # Return current price (use 'c' for current price)
            return float(quote['c'])

        except Exception as e:
            raise ValueError(f"Failed to get current price for {pair}: {str(e)}")


# Test function
def test_finnhub_fetcher():
    """Test Finnhub data fetcher."""
    print("Testing Finnhub Data Fetcher...")
    print("=" * 70)

    try:
        fetcher = FinnhubDataFetcher()

        # Test format conversion
        print("\n📝 Testing pair format conversion:")
        ig_pair = "EUR_USD"
        finnhub_symbol = fetcher._ig_pair_to_finnhub(ig_pair)
        print(f"   IG format: {ig_pair}")
        print(f"   Finnhub format: {finnhub_symbol}")
        assert finnhub_symbol == "OANDA:EUR_USD", "Format conversion failed"
        print("   ✅ Format conversion works!")

        # Test timeframe conversion
        print("\n📝 Testing timeframe conversion:")
        test_timeframes = ['1', '5', '15', '60', 'D']
        for tf in test_timeframes:
            resolution = fetcher._timeframe_to_resolution(tf)
            print(f"   {tf} -> {resolution}")
        print("   ✅ Timeframe conversion works!")

        # Test fetching candles
        print("\n📈 Testing candle fetch for EUR_USD (5min):")
        df = fetcher.get_candles("EUR_USD", "5", count=10)
        print(f"   Fetched {len(df)} candles")
        print(f"   Columns: {list(df.columns)}")
        print(f"   First candle time: {df['time'].iloc[0]}")
        print(f"   Last candle time: {df['time'].iloc[-1]}")
        print(f"   Latest close price: {df['close'].iloc[-1]:.5f}")
        print("   ✅ Candle fetch works!")

        # Test current price
        print("\n💰 Testing current price fetch:")
        price = fetcher.get_current_price("EUR_USD")
        print(f"   EUR/USD current price: {price:.5f}")
        print("   ✅ Current price fetch works!")

        print("\n" + "=" * 70)
        print("✅ All tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_finnhub_fetcher()
