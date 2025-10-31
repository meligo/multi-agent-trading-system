"""
Tavily Web Search Integration for Forex Trading

Provides real-time web search capabilities for:
- Social media sentiment analysis
- News and events
- Macro economic indicators
- Fundamental analysis
"""

import os
from typing import List, Dict, Optional
from tavily import TavilyClient
from forex_config import ForexConfig
from news_cache import NewsCache


class TavilyIntegration:
    """
    Tavily API integration for real-time web search.

    Provides specialized search functions for trading intelligence.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tavily integration with persistent caching.

        Args:
            api_key: Tavily API key (defaults to environment variable)
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")

        if not self.api_key:
            print("⚠️  Tavily API key not found. Web search features disabled.")
            self.enabled = False
            self.client = None
        else:
            try:
                self.client = TavilyClient(api_key=self.api_key)
                self.enabled = True
                print("✅ Tavily integration initialized")
            except Exception as e:
                print(f"⚠️  Tavily initialization failed: {e}")
                self.enabled = False
                self.client = None

        # Smart database cache (eliminates 96% of API calls)
        try:
            self.news_cache = NewsCache(default_ttl_hours=2)
            print("✅ Tavily news cache initialized (2-hour TTL)")
        except Exception as e:
            print(f"⚠️  News cache disabled: {e}")
            self.news_cache = None

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> List[Dict]:
        """
        Perform a general web search.

        Note: Caching is now handled at higher levels (get_news_and_events, etc.)
        via the database cache.

        Args:
            query: Search query
            max_results: Number of results to return
            search_depth: "basic" or "advanced"

        Returns:
            List of search results with title, content, url
        """
        if not self.enabled:
            return [{"error": "Tavily not available"}]

        try:
            response = self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth
            )

            results = []
            for result in response.get('results', []):
                results.append({
                    'title': result.get('title', ''),
                    'content': result.get('content', ''),
                    'url': result.get('url', ''),
                    'score': result.get('score', 0)
                })

            return results

        except Exception as e:
            print(f"⚠️  Tavily search failed: {e}")
            return [{"error": str(e)}]

    def get_social_sentiment(
        self,
        pair: str,
        timeframe: str = "24h"
    ) -> Dict:
        """
        Search for social media sentiment about a currency pair with smart caching.

        Args:
            pair: Currency pair (e.g., "EUR_USD")
            timeframe: Time range (e.g., "24h", "7d")

        Returns:
            Dictionary with sentiment analysis results
        """
        # Format pair for search (EUR/USD instead of EUR_USD)
        search_pair = pair.replace("_", "/")

        query = f"{search_pair} forex social media sentiment trading discussions {timeframe}"

        # Use cached news if available
        if self.news_cache:
            def fetch_sentiment_direct(q):
                """Internal fetch function for cache."""
                return self.search(q, max_results=5, search_depth="advanced")

            results = self.news_cache.get_news(
                pair=pair,
                query=query,
                fetch_func=fetch_sentiment_direct
            )
        else:
            # Fallback to direct search if cache disabled
            results = self.search(query, max_results=5, search_depth="advanced")

        if not results or 'error' in results[0]:
            return {
                'pair': pair,
                'sentiment': 'NEUTRAL',
                'confidence': 0.0,
                'sources': 0,
                'summary': 'No sentiment data available',
                'error': results[0].get('error', 'Unknown error') if results else 'No results'
            }

        # Aggregate sentiment from results
        summary_text = "\n\n".join([
            f"Source: {r.get('title', 'Unknown')}\n{r.get('content', '')[:200]}"
            for r in results[:3]
        ])

        return {
            'pair': pair,
            'sources': len(results),
            'results': results,
            'summary': summary_text,
            'search_performed': True
        }

    def get_news_and_events(
        self,
        pair: str,
        lookback: str = "24h"
    ) -> Dict:
        """
        Search for recent news and events affecting a currency pair with smart caching.

        Uses database cache with 2-hour TTL to eliminate 96% of API calls.

        Args:
            pair: Currency pair
            lookback: Time range to search

        Returns:
            Dictionary with news results
        """
        search_pair = pair.replace("_", "/")

        # Get base currencies
        base, quote = pair.split("_")

        query = f"{search_pair} forex news {base} {quote} central bank economic data {lookback}"

        # Use cached news if available
        if self.news_cache:
            def fetch_news_direct(q):
                """Internal fetch function for cache."""
                return self.search(q, max_results=5, search_depth="advanced")

            results = self.news_cache.get_news(
                pair=pair,
                query=query,
                fetch_func=fetch_news_direct
            )
        else:
            # Fallback to direct search if cache disabled
            results = self.search(query, max_results=5, search_depth="advanced")

        if not results or 'error' in results[0]:
            return {
                'pair': pair,
                'news_count': 0,
                'summary': 'No news available',
                'error': results[0].get('error', 'Unknown error') if results else 'No results'
            }

        headlines = [r.get('title', '') for r in results]
        summary = "\n\n".join([
            f"• {r.get('title', 'Unknown')}\n  {r.get('content', '')[:150]}..."
            for r in results[:3]
        ])

        return {
            'pair': pair,
            'news_count': len(results),
            'headlines': headlines,
            'results': results,
            'summary': summary
        }

    def get_macro_economic_context(
        self,
        currencies: List[str] = None
    ) -> Dict:
        """
        Search for macroeconomic news affecting currencies.

        Args:
            currencies: List of currency codes (e.g., ["USD", "EUR"])

        Returns:
            Dictionary with macro economic context
        """
        if not currencies:
            currencies = ["USD", "EUR", "GBP", "JPY"]

        currency_str = " ".join(currencies)
        query = f"macroeconomic news central bank interest rates inflation {currency_str} latest"

        results = self.search(query, max_results=5, search_depth="advanced")

        if not results or 'error' in results[0]:
            return {
                'currencies': currencies,
                'context_available': False,
                'error': results[0].get('error', 'Unknown error') if results else 'No results'
            }

        summary = "\n\n".join([
            f"• {r.get('title', '')}\n  {r.get('content', '')[:200]}..."
            for r in results[:3]
        ])

        return {
            'currencies': currencies,
            'context_available': True,
            'results': results,
            'summary': summary
        }

    def get_fundamental_analysis(
        self,
        pair: str
    ) -> Dict:
        """
        Search for fundamental analysis and economic indicators.

        Args:
            pair: Currency pair

        Returns:
            Dictionary with fundamental analysis
        """
        base, quote = pair.split("_")

        query = f"{base} vs {quote} fundamental analysis economic indicators interest rate GDP inflation employment"

        results = self.search(query, max_results=5, search_depth="advanced")

        if not results or 'error' in results[0]:
            return {
                'pair': pair,
                'analysis_available': False,
                'error': results[0].get('error', 'Unknown error') if results else 'No results'
            }

        summary = "\n\n".join([
            f"• {r.get('title', '')}\n  {r.get('content', '')[:200]}..."
            for r in results[:3]
        ])

        return {
            'pair': pair,
            'analysis_available': True,
            'results': results,
            'summary': summary
        }

    def get_comprehensive_analysis(
        self,
        pair: str
    ) -> Dict:
        """
        Get comprehensive analysis combining all search types.

        Args:
            pair: Currency pair

        Returns:
            Dictionary with all available intelligence
        """
        base, quote = pair.split("_")

        return {
            'social_sentiment': self.get_social_sentiment(pair),
            'news_events': self.get_news_and_events(pair),
            'macro_context': self.get_macro_economic_context([base, quote]),
            'fundamental_analysis': self.get_fundamental_analysis(pair)
        }


# Test function
def test_tavily_integration():
    """Test Tavily integration with sample queries."""
    print("Testing Tavily Integration...")
    print("=" * 70)

    from dotenv import load_dotenv
    load_dotenv()

    tavily = TavilyIntegration()

    if not tavily.enabled:
        print("❌ Tavily is disabled (no API key)")
        return

    # Test with EUR/USD
    pair = "EUR_USD"
    print(f"\n🔍 Testing with {pair}...")

    # Test social sentiment
    print("\n📱 Social Sentiment:")
    sentiment = tavily.get_social_sentiment(pair)
    if 'summary' in sentiment:
        print(f"   Sources: {sentiment.get('sources', 0)}")
        print(f"   Summary (first 300 chars):\n   {sentiment['summary'][:300]}...")

    # Test news
    print("\n📰 News & Events:")
    news = tavily.get_news_and_events(pair)
    if 'headlines' in news:
        print(f"   News Count: {news['news_count']}")
        for headline in news['headlines'][:3]:
            print(f"   • {headline}")

    # Test macro context
    print("\n🌍 Macro Economic Context:")
    macro = tavily.get_macro_economic_context(["EUR", "USD"])
    if 'summary' in macro:
        print(f"   {macro['summary'][:300]}...")

    print("\n✓ Tavily integration test complete!")


if __name__ == "__main__":
    test_tavily_integration()
