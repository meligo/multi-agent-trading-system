"""
Data Persistence Manager
Handles saving data from all services to PostgreSQL database

Services:
- InsightSentry (economic calendar, news)
- News Gating Service (gating states)
- DataBento (already has persistence)
- IG Markets (spot ticks)
- Trading Engine (signals, orders, fills, positions)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class DataPersistenceManager:
    """Manages data persistence for all services."""

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize persistence manager.

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        logger.info("DataPersistenceManager initialized")

    # ==========================================================================
    # INSIGHTSENTRY - Economic Calendar
    # ==========================================================================

    async def save_economic_events(self, events: List[Dict[str, Any]]) -> int:
        """
        Save economic calendar events to database.

        Args:
            events: List of events from InsightSentry

        Returns:
            Number of events saved
        """
        if not events:
            return 0

        rows = []
        for event in events:
            try:
                # Parse datetime
                scheduled_time = datetime.fromisoformat(event.get('date', '').replace('Z', '+00:00'))

                # Generate event ID
                event_id = f"{event.get('country')}_{event.get('title')}_{scheduled_time.strftime('%Y%m%d%H%M')}"

                rows.append((
                    scheduled_time,
                    datetime.utcnow(),
                    event_id,
                    event.get('country'),
                    event.get('currency'),
                    event.get('title'),
                    event.get('importance', 'medium'),
                    event.get('forecast'),
                    event.get('previous'),
                    None,  # actual (null until released)
                    'scheduled',  # status
                    None,  # revision_of
                    event.get('type')  # notes
                ))
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")
                continue

        if rows:
            try:
                # Use UPSERT to avoid duplicates
                query = """
                INSERT INTO iss_econ_calendar (
                    scheduled_time, recv_ts, event_id, country, currency,
                    event_name, importance, forecast, previous, actual,
                    status, revision_of, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    forecast = EXCLUDED.forecast,
                    previous = EXCLUDED.previous,
                    recv_ts = EXCLUDED.recv_ts
                """

                saved = 0
                for row in rows:
                    await self.db.execute_command(query, row)
                    saved += 1

                logger.info(f"✅ Saved {saved} economic events to database")
                return saved
            except Exception as e:
                logger.error(f"Failed to save economic events: {e}")
                return 0

        return 0

    # ==========================================================================
    # INSIGHTSENTRY - News
    # ==========================================================================

    async def save_news_events(self, news_items: List[Dict[str, Any]]) -> int:
        """
        Save news events to database.

        Args:
            news_items: List of news from InsightSentry

        Returns:
            Number of news items saved
        """
        if not news_items:
            return 0

        rows = []
        for item in news_items:
            try:
                # Parse timestamp
                published_at = item.get('published_at')
                if isinstance(published_at, int):
                    provider_event_ts = datetime.fromtimestamp(published_at)
                else:
                    provider_event_ts = datetime.fromisoformat(str(published_at).replace('Z', '+00:00'))

                # Generate event ID
                event_id = f"news_{item.get('source', 'unknown')}_{published_at}"

                rows.append((
                    provider_event_ts,
                    datetime.utcnow(),
                    event_id,
                    item.get('title', ''),
                    item.get('content', ''),
                    [],  # categories (empty for now)
                    item.get('related_symbols', []),
                    'medium',  # severity (default)
                    None,  # sentiment_score
                    item.get('link', ''),
                    'en',  # language
                    item.get('source', 'Unknown')
                ))
            except Exception as e:
                logger.warning(f"Failed to parse news item: {e}")
                continue

        if rows:
            try:
                query = """
                INSERT INTO iss_news_events (
                    provider_event_ts, recv_ts, event_id, headline, body,
                    categories, symbols, severity, sentiment_score,
                    url, language, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO NOTHING
                """

                saved = 0
                for row in rows:
                    await self.db.execute_command(query, row)
                    saved += 1

                logger.info(f"✅ Saved {saved} news items to database")
                return saved
            except Exception as e:
                logger.error(f"Failed to save news items: {e}")
                return 0

        return 0

    # ==========================================================================
    # NEWS GATING - Gating States
    # ==========================================================================

    async def save_gating_state(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        reason: str,
        window_minutes: int,
        state: str = 'scheduled',
        event_id: Optional[str] = None
    ) -> bool:
        """
        Save gating state to database.

        Args:
            symbol: Trading symbol (EUR_USD, GBP_USD, USD_JPY)
            start_time: When gate starts
            end_time: When gate ends
            reason: Reason for gating (e.g., 'NFP', 'CPI')
            window_minutes: Duration in minutes
            state: Gate state ('active', 'scheduled', 'cleared')
            event_id: Link to calendar event

        Returns:
            True if saved successfully
        """
        try:
            # Get instrument_id
            instrument_id = await self.db.get_instrument_id("IG", symbol)
            if not instrument_id:
                logger.warning(f"No instrument_id found for {symbol}")
                return False

            query = """
            INSERT INTO gating_state (
                instrument_id, start_time, end_time, reason,
                window_minutes, state, event_id, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument_id, start_time) DO UPDATE SET
                state = EXCLUDED.state,
                end_time = EXCLUDED.end_time
            """

            await self.db.execute_command(
                query,
                (instrument_id, start_time, end_time, reason, window_minutes, state, event_id, datetime.utcnow())
            )

            logger.debug(f"✅ Saved gating state for {symbol}: {reason} ({state})")
            return True

        except Exception as e:
            logger.error(f"Failed to save gating state: {e}")
            return False

    # ==========================================================================
    # IG MARKETS - Spot Ticks
    # ==========================================================================

    async def save_ig_tick(
        self,
        symbol: str,
        timestamp: datetime,
        bid: float,
        ask: float,
        mid: Optional[float] = None
    ) -> bool:
        """
        Save IG spot tick to database.

        Args:
            symbol: Trading symbol
            timestamp: Tick timestamp
            bid: Bid price
            ask: Ask price
            mid: Mid price (calculated if not provided)

        Returns:
            True if saved successfully
        """
        try:
            # Get instrument_id
            instrument_id = await self.db.get_instrument_id("IG", symbol)
            if not instrument_id:
                logger.warning(f"No instrument_id found for {symbol}")
                return False

            # Calculate mid if not provided
            if mid is None:
                mid = (bid + ask) / 2

            query = """
            INSERT INTO ig_spot_ticks (
                provider_event_ts, recv_ts, instrument_id,
                bid, ask, mid
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """

            await self.db.execute_command(
                query,
                (timestamp, datetime.utcnow(), instrument_id, bid, ask, mid)
            )

            return True

        except Exception as e:
            logger.error(f"Failed to save IG tick: {e}")
            return False

    async def batch_save_ig_ticks(self, ticks: List[Dict[str, Any]]) -> int:
        """
        Batch save IG spot ticks.

        Args:
            ticks: List of tick data

        Returns:
            Number of ticks saved
        """
        if not ticks:
            return 0

        rows = []
        for tick in ticks:
            try:
                instrument_id = await self.db.get_instrument_id("IG", tick['symbol'])
                if not instrument_id:
                    continue

                mid = tick.get('mid', (tick['bid'] + tick['ask']) / 2)

                rows.append((
                    tick['timestamp'],
                    datetime.utcnow(),
                    instrument_id,
                    tick['bid'],
                    tick['ask'],
                    mid
                ))
            except Exception as e:
                logger.warning(f"Failed to parse tick: {e}")
                continue

        if rows:
            try:
                await self.db.batch_insert(
                    table="ig_spot_ticks",
                    columns=["provider_event_ts", "recv_ts", "instrument_id", "bid", "ask", "mid"],
                    rows=rows
                )
                logger.debug(f"✅ Batch saved {len(rows)} IG ticks")
                return len(rows)
            except Exception as e:
                logger.error(f"Failed to batch save IG ticks: {e}")
                return 0

        return 0

    # ==========================================================================
    # TRADING ENGINE - Agent Signals
    # ==========================================================================

    async def save_agent_signal(
        self,
        symbol: str,
        timestamp: datetime,
        agent_name: str,
        signal: str,  # 'BUY', 'SELL', 'HOLD'
        confidence: float,
        reasoning: str,
        indicators: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save agent trading signal to database.

        Args:
            symbol: Trading symbol
            timestamp: Signal timestamp
            agent_name: Name of agent
            signal: Signal type
            confidence: Confidence score (0-1)
            reasoning: Agent reasoning
            indicators: Indicator values

        Returns:
            True if saved successfully
        """
        try:
            instrument_id = await self.db.get_instrument_id("IG", symbol)
            if not instrument_id:
                logger.warning(f"No instrument_id found for {symbol}")
                return False

            query = """
            INSERT INTO agent_signals (
                signal_ts, instrument_id, agent_name, signal,
                confidence, reasoning, indicators
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

            await self.db.execute_command(
                query,
                (timestamp, instrument_id, agent_name, signal, confidence, reasoning, indicators)
            )

            logger.debug(f"✅ Saved agent signal: {agent_name} -> {signal} on {symbol}")
            return True

        except Exception as e:
            logger.error(f"Failed to save agent signal: {e}")
            return False

    # ==========================================================================
    # FINNHUB - Aggregate Indicators
    # ==========================================================================

    async def save_finnhub_aggregate_indicators(
        self,
        symbol: str,
        timestamp: datetime,
        timeframe: str,
        buy_count: int,
        sell_count: int,
        neutral_count: int,
        total_indicators: int,
        consensus: str,
        confidence: float,
        signal: str,
        adx: Optional[float] = None,
        trending: Optional[bool] = None,
        extras: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save Finnhub aggregate indicators to database.

        Args:
            symbol: Trading symbol
            timestamp: Timestamp
            timeframe: Timeframe ('D', 'W', 'M')
            buy_count: Number of buy indicators
            sell_count: Number of sell indicators
            neutral_count: Number of neutral indicators
            total_indicators: Total indicators
            consensus: Consensus ('BULLISH', 'BEARISH', 'NEUTRAL')
            confidence: Confidence score (0-1)
            signal: Overall signal ('buy', 'sell', 'neutral')
            adx: ADX value
            trending: Is trending
            extras: Additional data

        Returns:
            True if saved successfully
        """
        try:
            instrument_id = await self.db.get_instrument_id("FINNHUB", f"FX:{symbol}")
            if not instrument_id:
                logger.warning(f"No instrument_id found for Finnhub {symbol}")
                return False

            query = """
            INSERT INTO finnhub_aggregate_indicators (
                provider_event_ts, recv_ts, instrument_id, timeframe,
                buy_count, sell_count, neutral_count, total_indicators,
                consensus, confidence, signal, adx, trending, extras
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            await self.db.execute_command(
                query,
                (timestamp, datetime.utcnow(), instrument_id, timeframe, buy_count, sell_count, neutral_count, total_indicators, consensus, confidence, signal, adx, trending, extras)
            )

            logger.debug(f"✅ Saved Finnhub aggregate indicators for {symbol}")
            return True

        except Exception as e:
            logger.error(f"Failed to save Finnhub aggregate indicators: {e}")
            return False

    # ==========================================================================
    # FINNHUB - Patterns
    # ==========================================================================

    async def save_finnhub_patterns(
        self,
        symbol: str,
        timestamp: datetime,
        timeframe: str,
        patterns: List[Dict[str, Any]]
    ) -> int:
        """
        Save Finnhub chart patterns to database.

        Args:
            symbol: Trading symbol
            timestamp: Timestamp
            timeframe: Timeframe
            patterns: List of pattern dictionaries

        Returns:
            Number of patterns saved
        """
        if not patterns:
            return 0

        try:
            instrument_id = await self.db.get_instrument_id("FINNHUB", f"FX:{symbol}")
            if not instrument_id:
                logger.warning(f"No instrument_id found for Finnhub {symbol}")
                return 0

            query = """
            INSERT INTO finnhub_patterns (
                provider_event_ts, recv_ts, instrument_id, timeframe,
                pattern_type, direction, confidence, start_time, end_time, extras
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            saved = 0
            for pattern in patterns:
                try:
                    start_time = None
                    end_time = None

                    if 'start_time' in pattern and pattern['start_time']:
                        start_time = datetime.fromtimestamp(pattern['start_time'])
                    if 'end_time' in pattern and pattern['end_time']:
                        end_time = datetime.fromtimestamp(pattern['end_time'])

                    await self.db.execute_command(
                        query,
                        (timestamp, datetime.utcnow(), instrument_id, timeframe, pattern.get('type', 'unknown'), pattern.get('direction', 'unknown'), pattern.get('confidence', 0.75), start_time, end_time, pattern.get('extras'))
                    )
                    saved += 1
                except Exception as e:
                    logger.warning(f"Failed to save pattern: {e}")
                    continue

            logger.debug(f"✅ Saved {saved} Finnhub patterns for {symbol}")
            return saved

        except Exception as e:
            logger.error(f"Failed to save Finnhub patterns: {e}")
            return 0

    # ==========================================================================
    # FINNHUB - Support/Resistance
    # ==========================================================================

    async def save_finnhub_support_resistance(
        self,
        symbol: str,
        timestamp: datetime,
        support_levels: List[float],
        resistance_levels: List[float]
    ) -> int:
        """
        Save Finnhub support/resistance levels to database.

        Args:
            symbol: Trading symbol
            timestamp: Timestamp
            support_levels: List of support prices
            resistance_levels: List of resistance prices

        Returns:
            Number of levels saved
        """
        if not support_levels and not resistance_levels:
            return 0

        try:
            instrument_id = await self.db.get_instrument_id("FINNHUB", f"FX:{symbol}")
            if not instrument_id:
                logger.warning(f"No instrument_id found for Finnhub {symbol}")
                return 0

            query = """
            INSERT INTO finnhub_support_resistance (
                provider_event_ts, recv_ts, instrument_id,
                level_type, price_level
            ) VALUES (%s, %s, %s, %s, %s)
            """

            saved = 0

            # Save support levels
            for level in support_levels:
                try:
                    await self.db.execute_command(
                        query,
                        (timestamp, datetime.utcnow(), instrument_id, 'support', level)
                    )
                    saved += 1
                except Exception as e:
                    logger.warning(f"Failed to save support level: {e}")
                    continue

            # Save resistance levels
            for level in resistance_levels:
                try:
                    await self.db.execute_command(
                        query,
                        (timestamp, datetime.utcnow(), instrument_id, 'resistance', level)
                    )
                    saved += 1
                except Exception as e:
                    logger.warning(f"Failed to save resistance level: {e}")
                    continue

            logger.debug(f"✅ Saved {saved} Finnhub S/R levels for {symbol}")
            return saved

        except Exception as e:
            logger.error(f"Failed to save Finnhub S/R levels: {e}")
            return 0

    # ==========================================================================
    # FINNHUB - Candles
    # ==========================================================================

    async def save_finnhub_candles(
        self,
        symbol: str,
        timeframe: str,
        candles: List[Dict[str, Any]]
    ) -> int:
        """
        Save Finnhub candles to database.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe ('1', '5', '15', '60', 'D')
            candles: List of candle dictionaries with 'time', 'open', 'high', 'low', 'close', 'volume'

        Returns:
            Number of candles saved
        """
        if not candles:
            return 0

        try:
            instrument_id = await self.db.get_instrument_id("FINNHUB", f"FX:{symbol}")
            if not instrument_id:
                logger.warning(f"No instrument_id found for Finnhub {symbol}")
                return 0

            query = """
            INSERT INTO finnhub_candles (
                provider_event_ts, recv_ts, instrument_id, timeframe,
                open, high, low, close, volume
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument_id, timeframe, provider_event_ts) DO NOTHING
            """

            saved = 0
            for candle in candles:
                try:
                    # Handle both datetime objects and Unix timestamps
                    candle_time = candle.get('time')
                    if isinstance(candle_time, (int, float)):
                        candle_time = datetime.fromtimestamp(candle_time)
                    elif not isinstance(candle_time, datetime):
                        continue

                    await self.db.execute_command(
                        query,
                        (candle_time, datetime.utcnow(), instrument_id, timeframe, candle.get('open'), candle.get('high'), candle.get('low'), candle.get('close'), candle.get('volume', 0.0))
                    )
                    saved += 1
                except Exception as e:
                    logger.warning(f"Failed to save candle: {e}")
                    continue

            logger.debug(f"✅ Saved {saved} Finnhub candles for {symbol} ({timeframe})")
            return saved

        except Exception as e:
            logger.error(f"Failed to save Finnhub candles: {e}")
            return 0


# Global singleton
_persistence_manager = None


def get_persistence_manager(db_manager: DatabaseManager) -> DataPersistenceManager:
    """Get or create global persistence manager instance."""
    global _persistence_manager
    if _persistence_manager is None:
        _persistence_manager = DataPersistenceManager(db_manager)
    return _persistence_manager
