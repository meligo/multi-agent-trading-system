"""
Finnhub Integration for Forex Trading

Provides:
1. Aggregate Indicators - Consensus signal from 30+ technical indicators
2. Pattern Recognition - Automated chart pattern detection
3. Support/Resistance - Pre-calculated S/R levels for validation
4. Technical Indicators - Backup/validation for local calculations

API Documentation: https://finnhub.io/docs/api/
"""

import os
import time
import requests
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from forex_config import ForexConfig


class FinnhubIntegration:
    """
    Finnhub API integration for forex technical analysis.

    Features:
    - Aggregate indicators (consensus from 30+ TAs)
    - Pattern recognition (chart patterns)
    - Support/resistance levels
    - Caching to avoid rate limits (60 calls/min free tier)
    """

    def __init__(self, api_key: Optional[str] = None, db_manager=None, persistence_manager=None):
        """
        Initialize Finnhub integration.

        Args:
            api_key: Finnhub API key (defaults to config)
            db_manager: DatabaseManager instance (optional)
            persistence_manager: DataPersistenceManager instance (optional)
        """
        self.api_key = api_key or ForexConfig.FINNHUB_API_KEY
        self.base_url = "https://finnhub.io/api/v1"

        if not self.api_key:
            print("⚠️  Finnhub API key not found. Finnhub features disabled.")
            self.enabled = False
        else:
            self.enabled = ForexConfig.ENABLE_FINNHUB
            print(f"✅ Finnhub integration initialized (enabled: {self.enabled})")

        # Cache to avoid rate limits
        self._cache = {}
        self._cache_ttl = ForexConfig.FINNHUB_CACHE_SECONDS

        # Database persistence
        self.db_manager = db_manager
        self.persistence = persistence_manager
        self.persist_enabled = persistence_manager is not None

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get cached result if still valid."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return data
        return None

    def _set_cache(self, key: str, data: Dict):
        """Store result in cache."""
        self._cache[key] = (data, time.time())

    def _pair_to_finnhub_symbol(self, pair: str) -> str:
        """
        Convert trading pair to Finnhub forex symbol.

        EUR_USD -> OANDA:EUR_USD
        GBP_JPY -> OANDA:GBP_JPY
        """
        # Finnhub uses OANDA format for forex
        return f"OANDA:{pair}"

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        Make API request to Finnhub.

        Args:
            endpoint: API endpoint (e.g., '/forex/aggregate-indicator')
            params: Additional parameters

        Returns:
            JSON response or None if error
        """
        if not self.enabled:
            return None

        try:
            # Add API key to params
            if params is None:
                params = {}
            params['token'] = self.api_key

            # Make request
            url = f"{self.base_url}{endpoint}"
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("⚠️  Finnhub rate limit exceeded. Using cached data.")
                return None
            else:
                print(f"⚠️  Finnhub API error: {response.status_code}")
                return None

        except Exception as e:
            print(f"⚠️  Finnhub request failed: {e}")
            return None

    def get_aggregate_indicators(self, pair: str, timeframe: str = "D") -> Dict:
        """
        Get aggregate technical indicators consensus.

        This provides a "vote" from 30+ technical indicators:
        - How many indicators say BUY
        - How many say SELL
        - How many are NEUTRAL

        Args:
            pair: Currency pair (e.g., "EUR_USD")
            timeframe: Timeframe (D=daily, W=weekly, M=monthly)

        Returns:
            {
                'symbol': 'OANDA:EUR_USD',
                'technicalAnalysis': {
                    'count': {'buy': 18, 'sell': 5, 'neutral': 7},
                    'signal': 'buy'  # Overall consensus
                },
                'trend': {
                    'adx': 35.2,
                    'trending': True
                },
                'consensus': 'BULLISH',  # Our interpretation
                'confidence': 0.60  # Buy percentage (18/30 = 0.60)
            }
        """
        # Check cache
        cache_key = f"aggregate_{pair}_{timeframe}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Convert pair to Finnhub symbol
        symbol = self._pair_to_finnhub_symbol(pair)

        # Make request
        data = self._make_request(
            '/scan/technical-indicator',
            {'symbol': symbol, 'resolution': timeframe}
        )

        if not data:
            return {
                'symbol': symbol,
                'technicalAnalysis': {'count': {'buy': 0, 'sell': 0, 'neutral': 0}, 'signal': 'neutral'},
                'consensus': 'NEUTRAL',
                'confidence': 0.0,
                'error': 'API request failed'
            }

        # Extract counts
        ta = data.get('technicalAnalysis', {})
        counts = ta.get('count', {'buy': 0, 'sell': 0, 'neutral': 0})

        # Calculate consensus
        total = counts.get('buy', 0) + counts.get('sell', 0) + counts.get('neutral', 0)
        if total == 0:
            consensus = 'NEUTRAL'
            confidence = 0.0
        else:
            buy_pct = counts.get('buy', 0) / total
            sell_pct = counts.get('sell', 0) / total

            if buy_pct > 0.55:
                consensus = 'BULLISH'
                confidence = buy_pct
            elif sell_pct > 0.55:
                consensus = 'BEARISH'
                confidence = sell_pct
            else:
                consensus = 'NEUTRAL'
                confidence = 0.5

        result = {
            'symbol': symbol,
            'technicalAnalysis': ta,
            'trend': data.get('trend', {}),
            'consensus': consensus,
            'confidence': confidence,
            'buy_count': counts.get('buy', 0),
            'sell_count': counts.get('sell', 0),
            'neutral_count': counts.get('neutral', 0),
            'total_indicators': total
        }

        # Cache result
        self._set_cache(cache_key, result)

        # Save to database if persistence enabled
        if self.persist_enabled:
            try:
                asyncio.create_task(self.persistence.save_finnhub_aggregate_indicators(
                    symbol=pair,
                    timestamp=datetime.utcnow(),
                    timeframe=timeframe,
                    buy_count=counts.get('buy', 0),
                    sell_count=counts.get('sell', 0),
                    neutral_count=counts.get('neutral', 0),
                    total_indicators=total,
                    consensus=consensus,
                    confidence=confidence,
                    signal=ta.get('signal', 'neutral'),
                    adx=data.get('trend', {}).get('adx'),
                    trending=data.get('trend', {}).get('trending'),
                    extras=data.get('trend', {})
                ))
            except Exception as e:
                print(f"⚠️  Failed to save Finnhub aggregate indicators: {e}")

        return result

    def get_patterns(self, pair: str, timeframe: str = "D") -> Dict:
        """
        Get detected chart patterns.

        Detects patterns like:
        - Head and Shoulders
        - Double Top/Bottom
        - Triangle patterns
        - Flags and pennants
        - Wedges

        Args:
            pair: Currency pair
            timeframe: Timeframe

        Returns:
            {
                'patterns': [
                    {
                        'type': 'double_top',
                        'direction': 'bearish',
                        'confidence': 0.85
                    }
                ],
                'has_patterns': True,
                'bullish_count': 0,
                'bearish_count': 1
            }
        """
        if not ForexConfig.FINNHUB_ENABLE_PATTERNS:
            return {'patterns': [], 'has_patterns': False}

        # Check cache
        cache_key = f"patterns_{pair}_{timeframe}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Convert pair
        symbol = self._pair_to_finnhub_symbol(pair)

        # Make request
        data = self._make_request(
            '/scan/pattern',
            {'symbol': symbol, 'resolution': timeframe}
        )

        if not data or 'points' not in data:
            return {'patterns': [], 'has_patterns': False, 'error': 'No patterns found'}

        # Parse patterns
        patterns = []
        bullish_count = 0
        bearish_count = 0

        for pattern_data in data.get('points', []):
            pattern_type = pattern_data.get('patternname', '').lower()
            is_bearish = 'bear' in pattern_type or 'short' in pattern_type

            pattern = {
                'type': pattern_type,
                'direction': 'bearish' if is_bearish else 'bullish',
                'start_time': pattern_data.get('start', 0),
                'end_time': pattern_data.get('end', 0),
                'confidence': 0.75  # Finnhub doesn't provide confidence, use default
            }

            patterns.append(pattern)

            if is_bearish:
                bearish_count += 1
            else:
                bullish_count += 1

        result = {
            'patterns': patterns,
            'has_patterns': len(patterns) > 0,
            'bullish_count': bullish_count,
            'bearish_count': bearish_count
        }

        # Cache result
        self._set_cache(cache_key, result)

        # Save to database if persistence enabled
        if self.persist_enabled and patterns:
            try:
                asyncio.create_task(self.persistence.save_finnhub_patterns(
                    symbol=pair,
                    timestamp=datetime.utcnow(),
                    timeframe=timeframe,
                    patterns=patterns
                ))
            except Exception as e:
                print(f"⚠️  Failed to save Finnhub patterns: {e}")

        return result

    def get_support_resistance(self, pair: str) -> Dict:
        """
        Get support and resistance levels.

        Args:
            pair: Currency pair

        Returns:
            {
                'support': [1.0850, 1.0820, 1.0800],
                'resistance': [1.0900, 1.0920, 1.0950],
                'has_levels': True
            }
        """
        if not ForexConfig.FINNHUB_ENABLE_SR:
            return {'support': [], 'resistance': [], 'has_levels': False}

        # Check cache
        cache_key = f"sr_{pair}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Convert pair
        symbol = self._pair_to_finnhub_symbol(pair)

        # Make request
        data = self._make_request(
            '/scan/support-resistance',
            {'symbol': symbol, 'resolution': 'D'}
        )

        if not data:
            return {'support': [], 'resistance': [], 'has_levels': False, 'error': 'API request failed'}

        # Parse support/resistance (Finnhub returns all levels together)
        levels = data.get('levels', [])
        support_levels = levels[:len(levels)//2] if levels else []
        resistance_levels = levels[len(levels)//2:] if levels else []

        result = {
            'support': support_levels,
            'resistance': resistance_levels,
            'has_levels': len(levels) > 0
        }

        # Cache result
        self._set_cache(cache_key, result)

        # Save to database if persistence enabled
        if self.persist_enabled and levels:
            try:
                asyncio.create_task(self.persistence.save_finnhub_support_resistance(
                    symbol=pair,
                    timestamp=datetime.utcnow(),
                    support_levels=support_levels,
                    resistance_levels=resistance_levels
                ))
            except Exception as e:
                print(f"⚠️  Failed to save Finnhub S/R levels: {e}")

        return result

    def get_comprehensive_analysis(self, pair: str, timeframe: str = "D") -> Dict:
        """
        Get comprehensive Finnhub analysis for a currency pair.

        Combines:
        - Aggregate indicators
        - Pattern recognition
        - Support/resistance

        Args:
            pair: Currency pair
            timeframe: Timeframe

        Returns:
            Complete analysis dictionary
        """
        return {
            'aggregate': self.get_aggregate_indicators(pair, timeframe),
            'patterns': self.get_patterns(pair, timeframe),
            'support_resistance': self.get_support_resistance(pair)
        }


# Test function
def test_finnhub_integration():
    """Test Finnhub integration with sample pair."""
    print("Testing Finnhub Integration...")
    print("=" * 70)

    # Create integration
    finnhub = FinnhubIntegration()

    if not finnhub.enabled:
        print("❌ Finnhub is disabled (no API key)")
        return

    # Test with EUR/USD
    pair = "EUR_USD"
    print(f"\n🔍 Testing with {pair}...")

    # Get aggregate indicators
    print("\n📊 Aggregate Indicators:")
    agg = finnhub.get_aggregate_indicators(pair)
    if 'error' not in agg:
        print(f"   Consensus: {agg['consensus']}")
        print(f"   Confidence: {agg['confidence']:.1%}")
        print(f"   Buy: {agg['buy_count']}, Sell: {agg['sell_count']}, Neutral: {agg['neutral_count']}")
    else:
        print(f"   Error: {agg['error']}")

    # Get patterns
    print("\n📈 Pattern Recognition:")
    patterns = finnhub.get_patterns(pair)
    if patterns['has_patterns']:
        for p in patterns['patterns']:
            print(f"   • {p['type'].upper()} ({p['direction']})")
    else:
        print("   No patterns detected")

    # Get support/resistance
    print("\n🎯 Support/Resistance:")
    sr = finnhub.get_support_resistance(pair)
    if sr['has_levels']:
        print(f"   Support: {sr['support'][:3]}")
        print(f"   Resistance: {sr['resistance'][:3]}")
    else:
        print("   No levels available")

    print("\n" + "=" * 70)
    print("✓ Finnhub integration test complete!")


if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    test_finnhub_integration()
