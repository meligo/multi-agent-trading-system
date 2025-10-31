"""
Forex Sentiment Analysis Module

Integrates multiple sentiment sources:
1. News sentiment from forex-specific APIs
2. Retail trader positioning from Myfxbook/FXSSI
3. Social media sentiment
4. Economic calendar events
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json


class ForexSentimentAnalyzer:
    """Analyzes market sentiment for forex pairs from multiple sources."""

    def __init__(self):
        """Initialize sentiment analyzer with API keys."""
        # API keys from environment
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
        self.forexnews_key = os.getenv('FOREXNEWS_API_KEY', '')
        self.tavily_key = os.getenv('TAVILY_API_KEY', '')

        # Cache for sentiment data (avoid excessive API calls)
        self.sentiment_cache = {}
        self.cache_duration = 300  # 5 minutes

    def get_news_sentiment(self, pair: str) -> Dict:
        """
        Get news sentiment for a forex pair.

        Args:
            pair: Currency pair like 'EUR_USD'

        Returns:
            Dictionary with sentiment score and news headlines
        """
        cache_key = f"news_{pair}"
        if self._is_cache_valid(cache_key):
            return self.sentiment_cache[cache_key]['data']

        sentiment_data = {
            'score': 0.0,  # -1.0 (bearish) to +1.0 (bullish)
            'confidence': 0.0,  # 0.0 to 1.0
            'headlines': [],
            'source': 'aggregated'
        }

        # Try Alpha Vantage sentiment
        if self.alpha_vantage_key:
            av_sentiment = self._get_alpha_vantage_sentiment(pair)
            if av_sentiment:
                sentiment_data = self._merge_sentiment(sentiment_data, av_sentiment)

        # Try ForexNewsAPI
        if self.forexnews_key:
            fn_sentiment = self._get_forexnews_sentiment(pair)
            if fn_sentiment:
                sentiment_data = self._merge_sentiment(sentiment_data, fn_sentiment)

        # Cache result
        self._cache_data(cache_key, sentiment_data)

        return sentiment_data

    def get_trader_positioning(self, pair: str) -> Dict:
        """
        Get retail trader positioning from Myfxbook/FXSSI.

        Args:
            pair: Currency pair like 'EUR_USD'

        Returns:
            Dictionary with long/short percentages
        """
        cache_key = f"positioning_{pair}"
        if self._is_cache_valid(cache_key):
            return self.sentiment_cache[cache_key]['data']

        positioning_data = {
            'long_percentage': 50.0,
            'short_percentage': 50.0,
            'sentiment': 'neutral',  # bullish/neutral/bearish
            'contrarian_signal': None,  # When extreme, do opposite
            'source': 'unknown'
        }

        # Try to get positioning from FXSSI (web scraping or API if available)
        fxssi_data = self._get_fxssi_positioning(pair)
        if fxssi_data:
            positioning_data = fxssi_data

        # Analyze for contrarian signals
        positioning_data = self._analyze_contrarian(positioning_data)

        # Cache result
        self._cache_data(cache_key, positioning_data)

        return positioning_data

    def get_economic_events(self, currencies: List[str]) -> List[Dict]:
        """
        Get upcoming economic events for specific currencies.

        Args:
            currencies: List of currency codes like ['EUR', 'USD']

        Returns:
            List of economic events with impact ratings
        """
        cache_key = f"events_{'_'.join(sorted(currencies))}"
        if self._is_cache_valid(cache_key):
            return self.sentiment_cache[cache_key]['data']

        events = []

        # Try Forex Factory calendar or similar
        # For now, return empty list (would integrate with Forex Factory API)

        # Cache result
        self._cache_data(cache_key, events)

        return events

    def get_combined_sentiment(self, pair: str) -> Dict:
        """
        Get combined sentiment from all sources.

        Args:
            pair: Currency pair like 'EUR_USD'

        Returns:
            Comprehensive sentiment analysis
        """
        # Get news sentiment
        news = self.get_news_sentiment(pair)

        # Get trader positioning
        positioning = self.get_trader_positioning(pair)

        # Get economic events
        currencies = pair.split('_')
        events = self.get_economic_events(currencies)

        # Calculate combined sentiment score
        combined_score = self._calculate_combined_sentiment(news, positioning, events)

        return {
            'pair': pair,
            'timestamp': datetime.now().isoformat(),
            'overall_sentiment': combined_score['sentiment'],
            'sentiment_score': combined_score['score'],
            'confidence': combined_score['confidence'],
            'news': news,
            'positioning': positioning,
            'upcoming_events': events,
            'recommendation': combined_score['recommendation']
        }

    def _get_alpha_vantage_sentiment(self, pair: str) -> Optional[Dict]:
        """Get sentiment from Alpha Vantage."""
        if not self.alpha_vantage_key:
            return None

        try:
            # Convert pair format: EUR_USD -> EURUSD
            symbol = pair.replace('_', '')

            url = f"https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': f'FOREX:{symbol}',
                'apikey': self.alpha_vantage_key,
                'limit': 50
            }

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()

                if 'feed' in data:
                    # Analyze sentiment from news feed
                    sentiment_score = 0.0
                    count = 0
                    headlines = []

                    for article in data['feed'][:10]:  # Top 10 articles
                        if 'overall_sentiment_score' in article:
                            sentiment_score += article['overall_sentiment_score']
                            count += 1
                            headlines.append({
                                'title': article.get('title', ''),
                                'source': article.get('source', ''),
                                'sentiment': article['overall_sentiment_score'],
                                'url': article.get('url', '')
                            })

                    if count > 0:
                        return {
                            'score': sentiment_score / count,
                            'confidence': min(count / 10, 1.0),
                            'headlines': headlines,
                            'source': 'alpha_vantage'
                        }
        except Exception as e:
            print(f"Error getting Alpha Vantage sentiment: {e}")

        return None

    def _get_forexnews_sentiment(self, pair: str) -> Optional[Dict]:
        """Get sentiment from ForexNewsAPI."""
        if not self.forexnews_key:
            return None

        try:
            # ForexNewsAPI endpoint - correct format from docs
            # Convert EUR_USD -> EUR-USD
            currency_param = pair.replace('_', '-')

            url = "https://forexnewsapi.com/api/v1/currency"
            params = {
                'token': self.forexnews_key,
                'currency': currency_param,
                'items': 20
            }

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()

                if 'data' in data:
                    # Analyze headlines for sentiment
                    # Simple keyword-based sentiment
                    bullish_keywords = ['rise', 'gain', 'bull', 'up', 'surge', 'rally', 'strong', 'positive']
                    bearish_keywords = ['fall', 'drop', 'bear', 'down', 'plunge', 'decline', 'weak', 'negative']

                    sentiment_score = 0.0
                    headlines = []

                    for article in data['data']:
                        title = article.get('title', '').lower()
                        description = article.get('description', '').lower()
                        text = f"{title} {description}"

                        # Count sentiment keywords
                        bull_count = sum(1 for keyword in bullish_keywords if keyword in text)
                        bear_count = sum(1 for keyword in bearish_keywords if keyword in text)

                        article_sentiment = 0.0
                        if bull_count + bear_count > 0:
                            article_sentiment = (bull_count - bear_count) / (bull_count + bear_count)

                        sentiment_score += article_sentiment
                        headlines.append({
                            'title': article.get('title', ''),
                            'source': article.get('source', ''),
                            'sentiment': article_sentiment,
                            'url': article.get('url', '')
                        })

                    count = len(data['data'])
                    if count > 0:
                        return {
                            'score': sentiment_score / count,
                            'confidence': min(count / 20, 1.0),
                            'headlines': headlines,
                            'source': 'forexnews_api'
                        }
        except Exception as e:
            print(f"Error getting ForexNews sentiment: {e}")

        return None

    def _get_fxssi_positioning(self, pair: str) -> Optional[Dict]:
        """
        Get trader positioning from FXSSI.

        Note: FXSSI doesn't have a public API, so this would require
        web scraping or a paid data feed. For now, returns None.
        """
        # Would implement web scraping or API integration here
        return None

    def _analyze_contrarian(self, positioning: Dict) -> Dict:
        """
        Analyze positioning for contrarian signals.

        When retail traders are extremely one-sided (>75%), often a reversal occurs.
        """
        long_pct = positioning['long_percentage']
        short_pct = positioning['short_percentage']

        # Extreme long positioning (>75%) -> contrarian bearish
        if long_pct > 75:
            positioning['sentiment'] = 'extremely_bullish'
            positioning['contrarian_signal'] = 'SELL'  # Do opposite
        # Extreme short positioning (>75%) -> contrarian bullish
        elif short_pct > 75:
            positioning['sentiment'] = 'extremely_bearish'
            positioning['contrarian_signal'] = 'BUY'  # Do opposite
        # Balanced positioning
        elif 45 <= long_pct <= 55:
            positioning['sentiment'] = 'neutral'
            positioning['contrarian_signal'] = None
        # Moderate bullish
        elif long_pct > 55:
            positioning['sentiment'] = 'bullish'
            positioning['contrarian_signal'] = None
        # Moderate bearish
        else:
            positioning['sentiment'] = 'bearish'
            positioning['contrarian_signal'] = None

        return positioning

    def _calculate_combined_sentiment(self, news: Dict, positioning: Dict, events: List[Dict]) -> Dict:
        """
        Calculate combined sentiment from all sources.

        Weights:
        - News sentiment: 40%
        - Trader positioning: 30%
        - Economic events: 30%
        """
        # News sentiment contribution (40%)
        news_contribution = news['score'] * 0.4 * news['confidence']

        # Positioning contribution (30%)
        # Convert positioning to sentiment score
        positioning_score = (positioning['long_percentage'] - 50) / 50  # -1 to +1
        positioning_contribution = positioning_score * 0.3

        # Events contribution (30%)
        # High-impact events coming up can shift sentiment
        events_score = 0.0
        if events:
            # Would analyze event impact here
            pass
        events_contribution = events_score * 0.3

        # Combined score
        combined_score = news_contribution + positioning_contribution + events_contribution

        # Determine sentiment category
        if combined_score > 0.3:
            sentiment = 'bullish'
        elif combined_score < -0.3:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'

        # Confidence based on data availability
        confidence = (news['confidence'] + (1.0 if positioning['source'] != 'unknown' else 0.0)) / 2

        # Generate recommendation
        if abs(combined_score) > 0.5 and confidence > 0.5:
            recommendation = 'strong_signal'
        elif abs(combined_score) > 0.3 and confidence > 0.3:
            recommendation = 'moderate_signal'
        else:
            recommendation = 'weak_signal'

        return {
            'score': combined_score,
            'sentiment': sentiment,
            'confidence': confidence,
            'recommendation': recommendation
        }

    def _merge_sentiment(self, existing: Dict, new: Dict) -> Dict:
        """Merge sentiment data from multiple sources."""
        # Average scores weighted by confidence
        total_confidence = existing.get('confidence', 0) + new.get('confidence', 0)

        if total_confidence > 0:
            weighted_score = (
                existing.get('score', 0) * existing.get('confidence', 0) +
                new.get('score', 0) * new.get('confidence', 0)
            ) / total_confidence

            existing['score'] = weighted_score
            existing['confidence'] = min(total_confidence / 2, 1.0)

        # Merge headlines
        existing['headlines'].extend(new.get('headlines', []))
        existing['source'] = 'multiple'

        return existing

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self.sentiment_cache:
            return False

        cache_entry = self.sentiment_cache[key]
        age = datetime.now() - cache_entry['timestamp']

        return age.total_seconds() < self.cache_duration

    def _cache_data(self, key: str, data: any):
        """Cache data with timestamp."""
        self.sentiment_cache[key] = {
            'data': data,
            'timestamp': datetime.now()
        }


# Example usage
if __name__ == "__main__":
    analyzer = ForexSentimentAnalyzer()

    # Test sentiment analysis
    sentiment = analyzer.get_combined_sentiment("EUR_USD")
    print(json.dumps(sentiment, indent=2, default=str))
