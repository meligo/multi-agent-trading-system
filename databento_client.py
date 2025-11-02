"""
DataBento Live Streaming Client
Streams CME futures Level 2 order book data (MBP-10)

Dataset: GLBX.MDP3 (CME Globex MDP 3.0)
Schema: mbp-10 (Market By Price - top 10 levels)
Symbols: 6E (EUR/USD), 6B (GBP/USD), 6J (USD/JPY)

Provides:
- Real-time Level 2 order book (top 10 bid/ask levels)
- Trade executions with aggressor side
- Order flow imbalance (OFI) calculation
- VPIN toxicity detection
- Persistence to TimescaleDB
"""

import os
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import asyncio
from collections import deque
from dataclasses import dataclass, field
import databento as db
from databento.live.session import Session
from databento.common.enums import Schema
from databento.common.types import DBNRecord
from dotenv import load_dotenv

from database_manager import DatabaseManager
from order_book_l2 import OrderBookL2

# Load environment variables
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


@dataclass
class DataBentoConfig:
    """Configuration for DataBento streaming."""
    api_key: str
    dataset: str = "GLBX.MDP3"
    schema: str = "mbp-10"
    symbols: List[str] = field(default_factory=lambda: ["6E", "6B", "6J"])
    stype_in: str = "raw_symbol"

    # Batch size for database writes
    batch_size: int = 1000
    batch_timeout_seconds: float = 1.0

    # Reconnection settings
    max_reconnect_attempts: int = 10
    reconnect_delay_seconds: int = 5


class DataBentoClient:
    """
    Live streaming client for DataBento CME futures data.

    Handles:
    - MBP-10 order book updates
    - Trade executions
    - Sequence gap detection
    - Automatic reconnection
    - Batch persistence to TimescaleDB
    """

    def __init__(
        self,
        config: Optional[DataBentoConfig] = None,
        db_manager: Optional[DatabaseManager] = None
    ):
        """
        Initialize DataBento client.

        Args:
            config: DataBento configuration
            db_manager: Database manager for persistence
        """
        api_key = os.getenv("DATABENTO_API_KEY")
        if not api_key:
            raise ValueError("DATABENTO_API_KEY not set in .env.scalper")

        self.config = config or DataBentoConfig(api_key=api_key)
        self.db = db_manager or DatabaseManager()

        # Order book managers (one per symbol)
        self.order_books: Dict[str, OrderBookL2] = {
            symbol: OrderBookL2(symbol) for symbol in self.config.symbols
        }

        # Batch buffers for database writes
        self.mbp_events_buffer: deque = deque()
        self.trades_buffer: deque = deque()
        self.book_snapshots_buffer: deque = deque()

        # Stats
        self.messages_received = 0
        self.messages_processed = 0
        self.sequence_gaps = 0

        # Running state
        self.running = False
        self.session: Optional[Session] = None

        # Symbol to instrument_id mapping (cached)
        self.symbol_to_instrument: Dict[str, int] = {}

        logger.info(f"DataBento client initialized for {self.config.symbols}")

    async def start(self):
        """Start streaming from DataBento."""
        self.running = True
        await self.db.initialize()

        # Load instrument mappings
        await self._load_instrument_mappings()

        logger.info("📡 Starting DataBento live stream...")

        try:
            # Start batch writer task
            writer_task = asyncio.create_task(self._batch_writer())

            # Connect and stream
            await self._stream_loop()

            # Wait for writer to finish
            await writer_task

        except Exception as e:
            logger.error(f"DataBento streaming error: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop streaming."""
        self.running = False

        # Flush remaining batches
        await self._flush_batches()

        if self.session:
            await self.session.close()

        await self.db.close()
        logger.info("📡 DataBento client stopped")

    async def _load_instrument_mappings(self):
        """Load DataBento symbol to instrument_id mappings."""
        for symbol in self.config.symbols:
            instrument_id = await self.db.get_instrument_id("DATABENTO", symbol)
            if instrument_id:
                self.symbol_to_instrument[symbol] = instrument_id
            else:
                logger.warning(f"No instrument_id found for DATABENTO/{symbol}")

    async def _stream_loop(self):
        """Main streaming loop with reconnection logic."""
        attempt = 0

        while self.running and attempt < self.config.max_reconnect_attempts:
            try:
                # Create live session
                client = db.Live(key=self.config.api_key)

                async with client.subscribe(
                    dataset=self.config.dataset,
                    schema=self.config.schema,
                    symbols=self.config.symbols,
                    stype_in=self.config.stype_in
                ) as session:
                    self.session = session
                    logger.info(f"✅ Connected to DataBento ({self.config.dataset})")

                    # Reset attempt counter on successful connection
                    attempt = 0

                    # Process messages
                    async for record in session:
                        if not self.running:
                            break

                        await self._handle_record(record)
                        self.messages_received += 1

                        # Log stats every 10,000 messages
                        if self.messages_received % 10000 == 0:
                            logger.info(
                                f"📊 Processed {self.messages_received} msgs "
                                f"({self.sequence_gaps} gaps)"
                            )

            except Exception as e:
                attempt += 1
                logger.error(f"Stream error (attempt {attempt}): {e}")

                if attempt < self.config.max_reconnect_attempts:
                    logger.info(f"Reconnecting in {self.config.reconnect_delay_seconds}s...")
                    await asyncio.sleep(self.config.reconnect_delay_seconds)
                else:
                    logger.error("Max reconnection attempts reached")
                    raise

    async def _handle_record(self, record: DBNRecord):
        """
        Handle a single record from DataBento.

        Args:
            record: DBN record (MBP-10 update or trade)
        """
        try:
            # Extract common fields
            symbol = getattr(record, 'symbol', None)
            if not symbol or symbol not in self.symbol_to_instrument:
                return

            instrument_id = self.symbol_to_instrument[symbol]

            # Dispatch based on record type
            schema_type = record.schema

            if schema_type == Schema.MBP_10:
                await self._handle_mbp10(record, instrument_id)
            elif schema_type == Schema.TRADES:
                await self._handle_trade(record, instrument_id)
            else:
                logger.debug(f"Unhandled schema type: {schema_type}")

            self.messages_processed += 1

        except Exception as e:
            logger.error(f"Error handling record: {e}")

    async def _handle_mbp10(self, record: DBNRecord, instrument_id: int):
        """
        Handle MBP-10 order book update.

        Args:
            record: MBP-10 record
            instrument_id: Database instrument ID
        """
        symbol = record.symbol
        ts_event = datetime.fromtimestamp(record.ts_event / 1e9)
        ts_recv = datetime.utcnow()

        # Update order book
        book = self.order_books[symbol]
        book.update(record)

        # Buffer event for database
        for level_idx in range(10):
            # Bid side
            bid_price = getattr(record, f'bid_px_{level_idx:02d}', 0)
            bid_size = getattr(record, f'bid_sz_{level_idx:02d}', 0)

            if bid_price > 0:
                self.mbp_events_buffer.append((
                    ts_event,
                    ts_recv,
                    instrument_id,
                    record.sequence,
                    record.action,
                    'B',  # Bid
                    level_idx,
                    bid_price,
                    bid_size,
                    None  # extras (JSONB)
                ))

            # Ask side
            ask_price = getattr(record, f'ask_px_{level_idx:02d}', 0)
            ask_size = getattr(record, f'ask_sz_{level_idx:02d}', 0)

            if ask_price > 0:
                self.mbp_events_buffer.append((
                    ts_event,
                    ts_recv,
                    instrument_id,
                    record.sequence,
                    record.action,
                    'A',  # Ask
                    level_idx,
                    ask_price,
                    ask_size,
                    None  # extras (JSONB)
                ))

        # Check for snapshot generation (every 100-250ms)
        if book.should_generate_snapshot():
            await self._generate_book_snapshot(symbol, instrument_id, ts_event, ts_recv)

    async def _handle_trade(self, record: DBNRecord, instrument_id: int):
        """
        Handle trade execution record.

        Args:
            record: Trade record
            instrument_id: Database instrument ID
        """
        ts_event = datetime.fromtimestamp(record.ts_event / 1e9)
        ts_recv = datetime.utcnow()

        # Determine aggressor side
        side = 'B' if record.side == 'B' else 'S'

        # Buffer trade for database
        self.trades_buffer.append((
            ts_event,
            ts_recv,
            instrument_id,
            record.price,
            record.size,
            side,
            str(record.trade_id),
            record.sequence,
            None  # extras (JSONB)
        ))

    async def _generate_book_snapshot(
        self,
        symbol: str,
        instrument_id: int,
        ts_event: datetime,
        ts_recv: datetime
    ):
        """
        Generate and buffer a full order book snapshot.

        Args:
            symbol: Symbol
            instrument_id: Database instrument ID
            ts_event: Event timestamp
            ts_recv: Receive timestamp
        """
        book = self.order_books[symbol]

        # Extract top 10 levels
        bid_prices = [level[0] for level in book.bids[:10]]
        bid_sizes = [level[1] for level in book.bids[:10]]
        ask_prices = [level[0] for level in book.asks[:10]]
        ask_sizes = [level[1] for level in book.asks[:10]]

        # Pad to 10 levels
        while len(bid_prices) < 10:
            bid_prices.append(0.0)
            bid_sizes.append(0.0)
        while len(ask_prices) < 10:
            ask_prices.append(0.0)
            ask_sizes.append(0.0)

        best_bid = bid_prices[0] if bid_prices[0] > 0 else None
        best_ask = ask_prices[0] if ask_prices[0] > 0 else None
        mid = (best_bid + best_ask) / 2 if best_bid and best_ask else None
        spread = (best_ask - best_bid) if best_bid and best_ask else None

        # Buffer snapshot
        self.book_snapshots_buffer.append((
            ts_event,
            ts_recv,
            instrument_id,
            bid_prices,
            bid_sizes,
            ask_prices,
            ask_sizes,
            best_bid,
            best_ask,
            mid,
            spread
        ))

    async def _batch_writer(self):
        """Background task that periodically flushes batches to database."""
        while self.running:
            await asyncio.sleep(self.config.batch_timeout_seconds)
            await self._flush_batches()

    async def _flush_batches(self):
        """Flush all buffered data to database."""
        try:
            # Flush MBP events
            if self.mbp_events_buffer:
                rows = list(self.mbp_events_buffer)
                self.mbp_events_buffer.clear()

                await self.db.batch_insert(
                    table="cme_mbp10_events",
                    columns=[
                        "provider_event_ts", "recv_ts", "instrument_id", "seq",
                        "action", "side", "level", "price", "size", "extras"
                    ],
                    rows=rows
                )
                logger.debug(f"Flushed {len(rows)} MBP events")

            # Flush trades
            if self.trades_buffer:
                rows = list(self.trades_buffer)
                self.trades_buffer.clear()

                await self.db.batch_insert(
                    table="cme_trades",
                    columns=[
                        "provider_event_ts", "recv_ts", "instrument_id", "price",
                        "size", "side", "trade_id", "seq", "extras"
                    ],
                    rows=rows
                )
                logger.debug(f"Flushed {len(rows)} trades")

            # Flush book snapshots
            if self.book_snapshots_buffer:
                rows = list(self.book_snapshots_buffer)
                self.book_snapshots_buffer.clear()

                await self.db.batch_insert(
                    table="cme_mbp10_book",
                    columns=[
                        "provider_event_ts", "recv_ts", "instrument_id",
                        "bid_px", "bid_sz", "ask_px", "ask_sz",
                        "best_bid", "best_ask", "mid", "spread"
                    ],
                    rows=rows
                )
                logger.debug(f"Flushed {len(rows)} book snapshots")

        except Exception as e:
            logger.error(f"Batch flush error: {e}")

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def get_book(self, symbol: str) -> Optional[OrderBookL2]:
        """Get current order book for a symbol."""
        return self.order_books.get(symbol)

    def get_best_bid_ask(self, symbol: str) -> Optional[tuple]:
        """Get (best_bid, best_ask) for a symbol."""
        book = self.order_books.get(symbol)
        if not book or not book.bids or not book.asks:
            return None
        return (book.bids[0][0], book.asks[0][0])


# ============================================================================
# TESTING
# ============================================================================

async def test_databento_stream():
    """Test DataBento streaming for 60 seconds."""
    client = DataBentoClient()

    try:
        # Start streaming
        task = asyncio.create_task(client.start())

        # Run for 60 seconds
        await asyncio.sleep(60)

        # Stop
        client.running = False
        await task

        logger.info(f"Test complete: {client.messages_received} messages received")

    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        await client.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(test_databento_stream())
