"""
Database Persistence Layer

Wraps DatabaseManager with convenience methods for saving:
- Ticks from WebSocket
- Candles aggregated from ticks
- Agent signals
- Orders and fills
- Positions

Designed to be used alongside DataHub for persistent storage.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from database_manager import DatabaseManager
from market_data_models import Tick, Candle

logger = logging.getLogger(__name__)


class DatabasePersistence:
    """
    High-level database persistence for trading system.

    Provides async methods to save all trading data to PostgreSQL.
    Works alongside DataHub (in-memory) for persistent storage.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database persistence.

        Args:
            database_url: PostgreSQL connection string (or uses env var)
        """
        self.db = DatabaseManager(database_url=database_url)
        self.initialized = False
        self._tick_buffer: List[Dict] = []
        self._candle_buffer: List[Dict] = []
        self._buffer_size = 100  # Batch insert every 100 items

        logger.info("DatabasePersistence initialized")

    async def initialize(self) -> bool:
        """
        Initialize database connection pool.

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.db.initialize()
            self.initialized = True
            logger.info("✅ Database persistence ready")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            self.initialized = False
            return False

    async def close(self):
        """Close database connection pool."""
        if self.initialized:
            await self.db.close()
            logger.info("Database persistence closed")

    # ========================================================================
    # TICK PERSISTENCE
    # ========================================================================

    async def save_tick(self, tick: Tick, source: str = 'IG') -> bool:
        """
        Save a single tick to database (buffered).

        Args:
            tick: Tick object
            source: Data source ('IG', 'DATABENTO', etc)

        Returns:
            True if saved/buffered, False if error
        """
        if not self.initialized:
            return False

        try:
            # Add to buffer
            self._tick_buffer.append({
                'timestamp': tick.timestamp,
                'symbol': tick.symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'mid': tick.mid,
                'spread': tick.spread,
                'source': source
            })

            # Flush buffer if full
            if len(self._tick_buffer) >= self._buffer_size:
                await self._flush_tick_buffer()

            return True

        except Exception as e:
            logger.error(f"Error saving tick for {tick.symbol}: {e}")
            return False

    async def _flush_tick_buffer(self):
        """Flush tick buffer to database using batch insert."""
        if not self._tick_buffer:
            return

        try:
            # Prepare rows for batch insert
            rows = [
                (
                    t['timestamp'],
                    t['symbol'],
                    t['bid'],
                    t['ask'],
                    t['mid'],
                    t['spread'],
                    t['source']
                )
                for t in self._tick_buffer
            ]

            # Batch insert
            await self.db.batch_insert(
                table='ig_spot_ticks',
                columns=['timestamp', 'symbol', 'bid', 'ask', 'mid', 'spread', 'source'],
                rows=rows,
                batch_size=1000
            )

            logger.debug(f"✅ Flushed {len(rows)} ticks to database")
            self._tick_buffer.clear()

        except Exception as e:
            logger.error(f"❌ Failed to flush tick buffer: {e}")
            # Don't clear buffer on error - will retry next time

    # ========================================================================
    # CANDLE PERSISTENCE
    # ========================================================================

    async def save_candle(self, candle: Candle, timeframe: str = '1m') -> bool:
        """
        Save a single candle to database (buffered).

        Args:
            candle: Candle object
            timeframe: Timeframe ('1m', '5m', etc)

        Returns:
            True if saved/buffered, False if error
        """
        if not self.initialized:
            return False

        try:
            # Add to buffer
            self._candle_buffer.append({
                'timestamp': candle.timestamp,
                'symbol': candle.symbol,
                'timeframe': timeframe,
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            })

            # Flush buffer if full
            if len(self._candle_buffer) >= self._buffer_size:
                await self._flush_candle_buffer()

            return True

        except Exception as e:
            logger.error(f"Error saving candle for {candle.symbol}: {e}")
            return False

    async def _flush_candle_buffer(self):
        """Flush candle buffer to database using batch insert."""
        if not self._candle_buffer:
            return

        try:
            # Note: candles table doesn't exist yet - need to create it
            # For now, just log and clear buffer
            logger.warning(f"⚠️  Candle buffer has {len(self._candle_buffer)} items but no candles table yet")
            self._candle_buffer.clear()

            # TODO: Uncomment when candles table is created
            # rows = [
            #     (
            #         c['timestamp'],
            #         c['symbol'],
            #         c['timeframe'],
            #         c['open'],
            #         c['high'],
            #         c['low'],
            #         c['close'],
            #         c['volume']
            #     )
            #     for c in self._candle_buffer
            # ]
            #
            # await self.db.batch_insert(
            #     table='candles',
            #     columns=['timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume'],
            #     rows=rows,
            #     batch_size=1000
            # )

        except Exception as e:
            logger.error(f"❌ Failed to flush candle buffer: {e}")

    # ========================================================================
    # AGENT SIGNAL PERSISTENCE
    # ========================================================================

    async def save_agent_signal(
        self,
        symbol: str,
        signal_type: str,
        direction: str,
        confidence: float,
        reasoning: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Save agent signal to database.

        Args:
            symbol: Trading pair
            signal_type: Type of signal ('SETUP', 'RISK', 'MOMENTUM', etc)
            direction: 'LONG', 'SHORT', or 'NEUTRAL'
            confidence: Confidence score (0.0 to 1.0)
            reasoning: Text explanation
            metadata: Additional data as JSON

        Returns:
            True if saved, False otherwise
        """
        if not self.initialized:
            return False

        try:
            query = """
            INSERT INTO agent_signals (
                timestamp, symbol, signal_type, direction, confidence, reasoning, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

            await self.db.execute(
                query,
                datetime.utcnow(),
                symbol,
                signal_type,
                direction,
                confidence,
                reasoning,
                metadata or {}
            )

            logger.debug(f"✅ Saved {signal_type} signal for {symbol}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save agent signal: {e}")
            return False

    # ========================================================================
    # ORDER PERSISTENCE
    # ========================================================================

    async def save_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[int]:
        """
        Save order to database.

        Args:
            symbol: Trading pair
            order_type: 'MARKET', 'LIMIT', etc
            side: 'BUY' or 'SELL'
            quantity: Order size in lots
            price: Limit price (if LIMIT order)
            stop_loss: Stop loss price
            take_profit: Take profit price
            metadata: Additional data as JSON

        Returns:
            Order ID if saved, None otherwise
        """
        if not self.initialized:
            return None

        try:
            query = """
            INSERT INTO orders (
                timestamp, symbol, order_type, side, quantity, price,
                stop_loss, take_profit, status, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING order_id
            """

            result = await self.db.fetchrow(
                query,
                datetime.utcnow(),
                symbol,
                order_type,
                side,
                quantity,
                price,
                stop_loss,
                take_profit,
                'PENDING',
                metadata or {}
            )

            order_id = result['order_id'] if result else None
            logger.info(f"✅ Saved order {order_id} for {symbol}: {side} {quantity} lots")
            return order_id

        except Exception as e:
            logger.error(f"❌ Failed to save order: {e}")
            return None

    # ========================================================================
    # PERIODIC FLUSH
    # ========================================================================

    async def flush_all_buffers(self):
        """Flush all buffered data to database."""
        await self._flush_tick_buffer()
        await self._flush_candle_buffer()
        logger.debug("✅ All buffers flushed")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_global_persistence: Optional[DatabasePersistence] = None


async def initialize_persistence(database_url: Optional[str] = None) -> DatabasePersistence:
    """
    Initialize global database persistence instance.

    Args:
        database_url: PostgreSQL connection string (or uses env var)

    Returns:
        DatabasePersistence instance
    """
    global _global_persistence

    if _global_persistence is None:
        _global_persistence = DatabasePersistence(database_url)
        await _global_persistence.initialize()

    return _global_persistence


def get_persistence() -> Optional[DatabasePersistence]:
    """Get global persistence instance (must call initialize_persistence first)."""
    return _global_persistence


async def close_persistence():
    """Close global persistence instance."""
    global _global_persistence

    if _global_persistence:
        await _global_persistence.close()
        _global_persistence = None
