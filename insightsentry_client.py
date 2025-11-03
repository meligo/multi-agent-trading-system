"""
InsightSentry MEGA Client (RapidAPI)
Fetches economic calendar, news, and market data for forex scalping

Plan: MEGA ($50/month)
- 10 WebSocket connections/day (hard limit)
- 600,000 REST API requests/month (60/min rate limit)
- REST API for economic calendar and news
- WebSocket for real-time streaming (conserve usage)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
import aiohttp
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


class InsightSentryClient:
    """
    REST client for InsightSentry MEGA API via RapidAPI.

    Endpoints (v3):
    - /v3/calendar/events - Economic calendar events (NFP, CPI, FOMC, etc.)
    - /v3/newsfeed - Breaking financial news
    - /v3/calendar/earnings - Earnings reports
    - /v3/calendar/dividends - Dividend schedules
    - /v3/symbols/search - Symbol search
    """

    BASE_URL = "https://insightsentry.p.rapidapi.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_host: Optional[str] = None
    ):
        """
        Initialize InsightSentry client.

        Args:
            api_key: RapidAPI key (from INSIGHTSENTRY_RAPIDAPI_KEY)
            api_host: RapidAPI host (from INSIGHTSENTRY_RAPIDAPI_HOST)
        """
        self.api_key = api_key or os.getenv("INSIGHTSENTRY_RAPIDAPI_KEY")
        self.api_host = api_host or os.getenv("INSIGHTSENTRY_RAPIDAPI_HOST", "insightsentry.p.rapidapi.com")

        if not self.api_key:
            raise ValueError("INSIGHTSENTRY_RAPIDAPI_KEY not set in .env.scalper")

        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host
        }

        self.session: Optional[aiohttp.ClientSession] = None
        logger.info("InsightSentry REST client initialized")

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a GET request to InsightSentry API.

        Args:
            endpoint: API endpoint (e.g., '/v2/calendar/economic')
            params: Query parameters

        Returns:
            JSON response
        """
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                logger.debug(f"GET {endpoint} -> {resp.status}")
                return data
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {endpoint} - {e}")
            raise

    # ========================================================================
    # ECONOMIC CALENDAR
    # ========================================================================

    async def get_economic_calendar(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        countries: List[str] = ["US", "EU", "GB", "JP"],
        min_impact: str = "high"
    ) -> List[Dict[str, Any]]:
        """
        Fetch economic calendar events from v3 API.

        Args:
            from_date: Start date (default: now) - ignored in v3, uses weeks instead
            to_date: End date (default: +7 days) - ignored in v3, uses weeks instead
            countries: Country codes (US, EU, GB, JP, etc.)
            min_impact: Minimum impact ('low', 'medium', 'high')

        Returns:
            List of calendar events
        """
        # v3 API uses weeks ahead (w) instead of date ranges
        weeks_ahead = 1
        if to_date:
            days_ahead = (to_date - datetime.utcnow()).days
            weeks_ahead = max(1, min(4, (days_ahead + 6) // 7))  # Round up, max 4 weeks

        params = {
            "w": weeks_ahead,
            "importance": min_impact
        }

        # v3 API only supports single country filter, so we'll request all and filter
        # If single country specified, use it
        if len(countries) == 1:
            params["country"] = countries[0]

        try:
            data = await self._request("/v3/calendar/events", params)
            all_events = data.get("data", [])

            # Filter by countries if multiple specified
            if len(countries) > 1:
                events = [e for e in all_events if e.get("country") in countries]
            else:
                events = all_events

            # Filter by importance (if not already done server-side)
            if min_impact:
                events = [e for e in events if e.get("importance") == min_impact]

            logger.info(f"Fetched {len(events)} economic calendar events (filtered from {len(all_events)})")
            return events
        except Exception as e:
            logger.error(f"Failed to fetch economic calendar: {e}")
            return []

    async def get_high_impact_events(
        self,
        lookback_hours: int = 0,
        lookahead_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get high-impact events in a time window.

        Args:
            lookback_hours: Hours in the past to check
            lookahead_hours: Hours in the future to check

        Returns:
            List of high-impact events
        """
        now = datetime.utcnow()
        from_date = now - timedelta(hours=lookback_hours)
        to_date = now + timedelta(hours=lookahead_hours)

        events = await self.get_economic_calendar(
            from_date=from_date,
            to_date=to_date,
            min_impact="high"
        )

        return events

    # ========================================================================
    # NEWS
    # ========================================================================

    async def get_news(
        self,
        categories: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
        languages: List[str] = ["en"],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch breaking news from v3 newsfeed.

        Args:
            categories: News categories (not used in v3, filtered client-side)
            symbols: Symbols to filter (filtered client-side from related_symbols)
            languages: Language codes (not used in v3)
            limit: Maximum number of news items (capped at 500 per page)

        Returns:
            List of news events
        """
        params = {
            "page": 1
        }

        try:
            data = await self._request("/v3/newsfeed", params)
            all_news = data.get("data", [])

            # Filter by symbols if specified (check related_symbols field)
            news_items = all_news
            if symbols:
                news_items = [
                    item for item in all_news
                    if any(sym in item.get("related_symbols", []) for sym in symbols)
                ]

            # Limit results
            news_items = news_items[:limit]

            logger.info(f"Fetched {len(news_items)} news items (filtered from {len(all_news)})")
            return news_items
        except Exception as e:
            logger.error(f"Failed to fetch news: {e}")
            return []

    async def get_forex_news(
        self,
        symbols: List[str] = ["FX:EURUSD", "FX:GBPUSD", "FX:USDJPY"],
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get forex-specific news.

        Args:
            symbols: FX symbols (use 'FX:EURUSD' format for InsightSentry)
            limit: Maximum number of items

        Returns:
            List of forex news
        """
        return await self.get_news(
            categories=["FOREX", "CENTRAL_BANK", "ECONOMIC_DATA"],
            symbols=symbols,
            limit=limit
        )

    # ========================================================================
    # SENTIMENT (Not available in v3)
    # ========================================================================

    async def get_sentiment(
        self,
        symbols: Optional[List[str]] = None,
        timeframe: str = "1h"
    ) -> Dict[str, Any]:
        """
        Fetch market sentiment data.

        **NOTE**: Sentiment endpoint not available in v3 API.
        Returns empty dict for backward compatibility.

        Args:
            symbols: Symbols to query (e.g., ['FX:EURUSD'])
            timeframe: Timeframe for sentiment ('1h', '4h', '1d')

        Returns:
            Empty dict (sentiment not available in v3)
        """
        logger.warning("Sentiment endpoint not available in InsightSentry v3 API")
        return {}

    # ========================================================================
    # SYMBOL INFO (v3 uses search)
    # ========================================================================

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get detailed information about a symbol using v3 search.

        Args:
            symbol: Symbol to search (e.g., 'EURUSD', 'AAPL')

        Returns:
            Symbol information (first match from search)
        """
        try:
            params = {"query": symbol}
            data = await self._request("/v3/symbols/search", params)
            results = data.get("data", [])

            if results:
                logger.info(f"Found {len(results)} matches for {symbol}")
                return results[0]  # Return first match
            else:
                logger.warning(f"No results found for {symbol}")
                return {}
        except Exception as e:
            logger.error(f"Failed to fetch symbol info: {e}")
            return {}

    # ========================================================================
    # CURRENCY MAPPING HELPERS
    # ========================================================================

    @staticmethod
    def ig_to_insightsentry_symbol(ig_symbol: str) -> str:
        """
        Convert IG symbol to InsightSentry format.

        Args:
            ig_symbol: IG symbol (e.g., 'EUR_USD')

        Returns:
            InsightSentry symbol (e.g., 'FX:EURUSD')
        """
        # Remove underscore and add FX: prefix
        base_symbol = ig_symbol.replace("_", "")
        return f"FX:{base_symbol}"

    @staticmethod
    def extract_currencies(ig_symbol: str) -> List[str]:
        """
        Extract currency codes from IG symbol.

        Args:
            ig_symbol: IG symbol (e.g., 'EUR_USD')

        Returns:
            List of currencies (e.g., ['EUR', 'USD'])
        """
        parts = ig_symbol.split("_")
        return parts if len(parts) == 2 else []


# ============================================================================
# TESTING & EXAMPLES
# ============================================================================

async def test_client():
    """Test InsightSentry client functionality."""
    async with InsightSentryClient() as client:
        # Test economic calendar
        logger.info("=" * 60)
        logger.info("Testing Economic Calendar")
        logger.info("=" * 60)
        events = await client.get_high_impact_events(
            lookback_hours=12,
            lookahead_hours=48
        )
        for event in events[:5]:
            logger.info(f"  {event.get('scheduled_time')} - {event.get('country')} - {event.get('event_name')}")

        # Test forex news
        logger.info("=" * 60)
        logger.info("Testing Forex News")
        logger.info("=" * 60)
        news = await client.get_forex_news(limit=10)
        for item in news[:5]:
            logger.info(f"  {item.get('timestamp')} - {item.get('headline')}")

        # Test sentiment
        logger.info("=" * 60)
        logger.info("Testing Sentiment")
        logger.info("=" * 60)
        sentiment = await client.get_sentiment(
            symbols=["FX:EURUSD", "FX:GBPUSD", "FX:USDJPY"],
            timeframe="1h"
        )
        logger.info(f"  Sentiment data: {sentiment}")

        # Test symbol mapping
        logger.info("=" * 60)
        logger.info("Testing Symbol Mapping")
        logger.info("=" * 60)
        logger.info(f"  EUR_USD -> {client.ig_to_insightsentry_symbol('EUR_USD')}")
        logger.info(f"  GBP_USD -> {client.ig_to_insightsentry_symbol('GBP_USD')}")
        logger.info(f"  USD_JPY -> {client.ig_to_insightsentry_symbol('USD_JPY')}")


async def monitor_events():
    """
    Monitor upcoming high-impact events (run continuously).
    Useful for understanding what events are coming up.
    """
    async with InsightSentryClient() as client:
        while True:
            events = await client.get_high_impact_events(
                lookback_hours=0,
                lookahead_hours=24
            )

            logger.info(f"Found {len(events)} high-impact events in next 24h:")
            for event in events:
                scheduled = event.get('scheduled_time')
                country = event.get('country')
                name = event.get('event_name')
                importance = event.get('importance')
                logger.info(f"  [{importance}] {scheduled} - {country} - {name}")

            # Sleep for 1 hour before checking again
            await asyncio.sleep(3600)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run tests
    asyncio.run(test_client())

    # Uncomment to run continuous monitoring:
    # asyncio.run(monitor_events())
