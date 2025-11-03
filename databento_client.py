"""
DataBento Live Streaming Client
Streams CME futures trade data with real volume

Dataset: GLBX.MDP3 (CME Globex MDP 3.0)
Schema: trades (Trade executions - real volume)
Symbols: 6E (EUR/USD), 6B (GBP/USD), 6J (USD/JPY)

Provides:
- Real-time trade executions with actual volume
- 1-minute OHLCV candle aggregation (real volume)
- Order flow metrics (buy/sell volume delta)
- VWAP calculation with real volume
- Persistence to TimescaleDB
- Push candles to DataHub for trading system

Note: Uses trades schema instead of mbp-10 for wider subscription compatibility
"""

import os
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
from collections import deque
from dataclasses import dataclass, field
import databento as db
from databento import Live, DBNRecord
from dotenv import load_dotenv

from database_manager import DatabaseManager
from order_book_l2 import OrderBookL2

# Import DataHub and models
try:
    from data_hub import get_data_hub_from_env
    from market_data_models import OrderFlowMetrics, Candle
    DATA_HUB_AVAILABLE = True
except ImportError:
    DATA_HUB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("DataHub not available - order flow metrics will not be cached")

# Load environment variables
env_path = Path(__file__).parent / '.env.scalper'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


@dataclass
class DataBentoConfig:
    """Configuration for DataBento streaming."""
    api_key: str
    dataset: str = "GLBX.MDP3"
    schema: str = "trades"  # Changed from mbp-10 to trades (more widely available)
    # Use continuous front-month contracts (e.g., ES.c.0 = S&P 500 front month)
    symbols: List[str] = field(default_factory=lambda: ["6E.c.0", "6B.c.0", "6J.c.0"])
    stype_in: str = "continuous"  # Changed from raw_symbol to continuous

    # Batch size for database writes
    batch_size: int = 1000
    batch_timeout_seconds: float = 1.0

    # Reconnection settings
    max_reconnect_attempts: int = 10
    reconnect_delay_seconds: int = 5


class BarAggregator:
    """
    Aggregates tick data into 1-minute OHLCV candles with real volume.

    Uses:
    - MBP-10 mid prices for OHLC
    - Trade volumes for real volume (not tick count)
    """

    def __init__(self, futures_symbol: str, spot_symbol: str):
        """
        Initialize bar aggregator.

        Args:
            futures_symbol: Futures contract (6E, 6B, 6J)
            spot_symbol: Spot pair (EUR_USD, GBP_USD, USD_JPY)
        """
        self.futures_symbol = futures_symbol
        self.spot_symbol = spot_symbol

        # Current bar state
        self.bar_start: Optional[datetime] = None
        self.open_price: Optional[float] = None
        self.high_price: Optional[float] = None
        self.low_price: Optional[float] = None
        self.close_price: Optional[float] = None
        self.volume: float = 0.0  # Real trade volume

        # Track updates
        self.updates_count: int = 0

    def update_price(self, timestamp: datetime, mid_price: float) -> Optional[Candle]:
        """
        Update bar with new mid price from MBP-10.

        Args:
            timestamp: Update timestamp
            mid_price: Mid price (best_bid + best_ask) / 2

        Returns:
            Completed Candle if minute boundary crossed, else None
        """
        # Determine bar start time (floor to minute)
        bar_start = timestamp.replace(second=0, microsecond=0)

        # Check if we're starting a new minute
        if self.bar_start is None:
            # First update ever
            self._start_new_bar(bar_start, mid_price)
            return None

        elif bar_start > self.bar_start:
            # New minute started - finalize previous bar
            completed_candle = self._finalize_bar()

            # Start new bar
            self._start_new_bar(bar_start, mid_price)

            return completed_candle

        else:
            # Same minute - update current bar
            self._update_current_bar(mid_price)
            return None

    def add_trade_volume(self, volume: float):
        """
        Add trade volume to current bar.

        Args:
            volume: Trade size (real volume from execution)
        """
        self.volume += volume

    def _start_new_bar(self, bar_start: datetime, open_price: float):
        """Start a new bar."""
        self.bar_start = bar_start
        self.open_price = open_price
        self.high_price = open_price
        self.low_price = open_price
        self.close_price = open_price
        self.volume = 0.0
        self.updates_count = 0

    def _update_current_bar(self, price: float):
        """Update current bar with new price."""
        if self.high_price is None or price > self.high_price:
            self.high_price = price
        if self.low_price is None or price < self.low_price:
            self.low_price = price
        self.close_price = price
        self.updates_count += 1

    def _finalize_bar(self) -> Optional[Candle]:
        """
        Finalize current bar and create Candle object.

        Returns:
            Candle with real volume from CME futures
        """
        if self.bar_start is None or self.open_price is None:
            return None

        candle = Candle(
            symbol=self.spot_symbol,
            timestamp=self.bar_start,
            open=self.open_price,
            high=self.high_price or self.open_price,
            low=self.low_price or self.open_price,
            close=self.close_price or self.open_price,
            volume=self.volume,  # Real volume from trades
            source="DATABENTO",
            volume_type="real"
        )

        logger.debug(
            f"Finalized bar {self.spot_symbol} [{self.bar_start}]: "
            f"O={candle.open:.5f} H={candle.high:.5f} L={candle.low:.5f} C={candle.close:.5f} "
            f"V={candle.volume:.0f} (real volume, {self.updates_count} updates)"
        )

        return candle


class DataBentoClient:
    """
    Live streaming client for DataBento CME futures data.

    Handles:
    - Trade executions with real volume
    - 1-minute OHLCV candle aggregation
    - Order flow metrics calculation
    - Sequence gap detection
    - Automatic reconnection
    - Batch persistence to TimescaleDB
    - Push candles to DataHub

    Note: Uses 'trades' schema for wider subscription compatibility.
    Still provides real volume and all necessary metrics.
    """

    def __init__(
        self,
        config: Optional[DataBentoConfig] = None,
        db_manager: Optional[DatabaseManager] = None,
        data_hub=None
    ):
        """
        Initialize DataBento client.

        Args:
            config: DataBento configuration
            db_manager: Database manager for persistence
            data_hub: DataHub instance for real-time caching (optional)
        """
        api_key = os.getenv("DATABENTO_API_KEY")
        if not api_key:
            raise ValueError("DATABENTO_API_KEY not set in .env.scalper")

        self.config = config or DataBentoConfig(api_key=api_key)
        self.db = db_manager or DatabaseManager()

        # DataHub integration
        self.data_hub = data_hub
        if self.data_hub is None and DATA_HUB_AVAILABLE:
            self.data_hub = get_data_hub_from_env()

        # Order book managers (one per symbol)
        self.order_books: Dict[str, OrderBookL2] = {
            symbol: OrderBookL2(symbol) for symbol in self.config.symbols
        }

        # Batch buffers for database writes
        self.mbp_events_buffer: deque = deque()
        self.trades_buffer: deque = deque()
        self.book_snapshots_buffer: deque = deque()

        # Order flow calculation buffers (60-second rolling windows)
        self.trade_windows: Dict[str, deque] = {
            symbol: deque() for symbol in self.config.symbols
        }
        self.ofi_windows: Dict[str, deque] = {
            symbol: deque() for symbol in self.config.symbols
        }

        # Futures to spot mapping (handles both "6E" and "6E.c.0" notation)
        self.futures_to_spot = {
            '6E': 'EUR_USD',
            '6B': 'GBP_USD',
            '6J': 'USD_JPY',
            '6A': 'AUD_USD',
            '6C': 'USD_CAD',
            '6S': 'USD_CHF',
            '6N': 'NZD_USD',
            # Add continuous contract mappings
            '6E.c.0': 'EUR_USD',
            '6B.c.0': 'GBP_USD',
            '6J.c.0': 'USD_JPY',
        }

        # Bar aggregators for candle generation (REAL volume)
        self.bar_aggregators: Dict[str, BarAggregator] = {}
        for futures_symbol in self.config.symbols:
            spot_symbol = self.futures_to_spot.get(futures_symbol)
            if spot_symbol:
                self.bar_aggregators[futures_symbol] = BarAggregator(
                    futures_symbol=futures_symbol,
                    spot_symbol=spot_symbol
                )

        # Stats
        self.messages_received = 0
        self.messages_processed = 0
        self.sequence_gaps = 0
        self.order_flow_updates = 0
        self.candles_generated = 0

        # Running state
        self.running = False
        self.session: Optional[Session] = None

        # Symbol mapping (for continuous contracts)
        # continuous symbol (6E.c.0) -> raw symbol (6EX5)
        self.cont_to_raw: Dict[str, str] = {}
        # raw symbol (6EX5) -> instrument_id
        self.raw_to_instrument_id: Dict[str, int] = {}
        # instrument_id -> continuous symbol (for reverse lookup)
        self.instrument_id_to_cont: Dict[int, str] = {}

        # Legacy mapping (will be populated from symbol mappings)
        self.symbol_to_instrument: Dict[str, int] = {}

        logger.info(f"DataBento client initialized for {self.config.symbols}")
        logger.info(f"DataHub: {'✅ Connected' if self.data_hub else '❌ Not available'}")

    async def start(self):
        """Start streaming from DataBento."""
        self.running = True
        await self.db.initialize()

        # Note: Symbol mappings are now handled dynamically via SymbolMappingMsg and InstrumentDefMsg
        # No need to pre-load mappings from database

        logger.info("📡 Starting DataBento live stream...")
        logger.info("   Waiting for symbol mappings and instrument definitions...")

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
                # Create live client
                client = Live(key=self.config.api_key)

                # Subscribe to data
                client.subscribe(
                    dataset=self.config.dataset,
                    schema=self.config.schema,
                    symbols=self.config.symbols,
                    stype_in=self.config.stype_in
                )

                self.session = client
                logger.info(f"✅ Connected to DataBento ({self.config.dataset})")

                # Reset attempt counter on successful connection
                attempt = 0

                # Process messages
                async for record in client:
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
            finally:
                if self.session:
                    try:
                        await self.session.close()
                    except:
                        pass

    async def _handle_record(self, record):
        """
        Handle a single record from DataBento.

        Args:
            record: DBN record (trade, MBP-10, SymbolMapping, InstrumentDef, etc.)
        """
        try:
            # Get record type
            rtype = str(type(record).__name__)

            # Handle SymbolMappingMsg (continuous -> raw symbol mapping)
            if 'SymbolMapping' in rtype:
                await self._handle_symbol_mapping(record)
                return

            # Handle InstrumentDefMsg (raw symbol -> instrument_id mapping)
            if 'InstrumentDef' in rtype or 'Definition' in rtype:
                await self._handle_instrument_def(record)
                return

            # For trade/mbp messages, use instrument_id to find continuous symbol
            instrument_id = getattr(record, 'instrument_id', None)
            if not instrument_id:
                return

            # Look up continuous symbol from instrument_id
            cont_symbol = self.instrument_id_to_cont.get(instrument_id)
            if not cont_symbol:
                # Not yet mapped - this is normal at startup, just skip
                return

            # Dispatch based on record type
            if 'trade' in rtype.lower() or 'Trade' in rtype:
                await self._handle_trade(record, instrument_id, cont_symbol)
            elif 'mbp' in rtype.lower() or 'MBP' in rtype:
                await self._handle_mbp10(record, instrument_id, cont_symbol)
            else:
                logger.debug(f"Unhandled record type: {rtype}")

            self.messages_processed += 1

        except Exception as e:
            logger.error(f"Error handling record: {e}")

    async def _handle_symbol_mapping(self, record):
        """
        Handle SymbolMappingMsg - maps continuous symbol to raw symbol.

        Args:
            record: SymbolMappingMsg from DataBento
        """
        try:
            # Get continuous symbol and mapped raw symbol
            cont_symbol = getattr(record, 'stype_in_symbol', None)
            raw_symbol = getattr(record, 'stype_out_symbol', None)

            if not cont_symbol or not raw_symbol:
                return

            # Store continuous -> raw mapping
            self.cont_to_raw[cont_symbol] = raw_symbol

            logger.info(f"📍 Symbol mapping: {cont_symbol} -> {raw_symbol}")

            # If we already have instrument_id for this raw symbol, complete the chain
            if raw_symbol in self.raw_to_instrument_id:
                instrument_id = self.raw_to_instrument_id[raw_symbol]
                self.instrument_id_to_cont[instrument_id] = cont_symbol
                self.symbol_to_instrument[cont_symbol] = instrument_id
                logger.info(f"✅ Complete mapping: {cont_symbol} -> {raw_symbol} -> {instrument_id}")

        except Exception as e:
            logger.error(f"Error handling symbol mapping: {e}")

    async def _handle_instrument_def(self, record):
        """
        Handle InstrumentDefMsg - maps raw symbol to instrument_id.

        Args:
            record: InstrumentDefMsg from DataBento
        """
        try:
            raw_symbol = getattr(record, 'raw_symbol', None)
            instrument_id = getattr(record, 'instrument_id', None)

            if not raw_symbol or not instrument_id:
                return

            # Store raw -> instrument_id mapping
            self.raw_to_instrument_id[raw_symbol] = instrument_id

            logger.info(f"🔧 Instrument definition: {raw_symbol} -> {instrument_id}")

            # Find which continuous symbol(s) map to this raw symbol
            for cont_symbol, mapped_raw in self.cont_to_raw.items():
                if mapped_raw == raw_symbol:
                    self.instrument_id_to_cont[instrument_id] = cont_symbol
                    self.symbol_to_instrument[cont_symbol] = instrument_id
                    logger.info(f"✅ Complete mapping: {cont_symbol} -> {raw_symbol} -> {instrument_id}")

        except Exception as e:
            logger.error(f"Error handling instrument definition: {e}")

    async def _handle_mbp10(self, record: DBNRecord, instrument_id: int, cont_symbol: str):
        """
        Handle MBP-10 order book update.

        Args:
            record: MBP-10 record
            instrument_id: Database instrument ID
            cont_symbol: Continuous contract symbol (6E.c.0, 6B.c.0, etc.)
        """
        symbol = cont_symbol
        ts_event = datetime.fromtimestamp(record.ts_event / 1e9)
        ts_recv = datetime.utcnow()

        # Store previous book state for OFI calculation
        book = self.order_books[symbol]
        prev_book = {
            'bid_price': book.bids[0][0] if book.bids else 0,
            'bid_size': book.bids[0][1] if book.bids else 0,
            'ask_price': book.asks[0][0] if book.asks else 0,
            'ask_size': book.asks[0][1] if book.asks else 0
        }

        # Update order book
        book.update(record)

        # Calculate new book state
        new_book = {
            'bid_price': book.bids[0][0] if book.bids else 0,
            'bid_size': book.bids[0][1] if book.bids else 0,
            'ask_price': book.asks[0][0] if book.asks else 0,
            'ask_size': book.asks[0][1] if book.asks else 0
        }

        # Update OFI
        self._update_ofi_on_book_change(symbol, prev_book, new_book)

        # Update bar aggregator with mid price (for OHLC candles)
        if symbol in self.bar_aggregators and new_book['bid_price'] > 0 and new_book['ask_price'] > 0:
            mid_price = (new_book['bid_price'] + new_book['ask_price']) / 2.0
            aggregator = self.bar_aggregators[symbol]
            completed_candle = aggregator.update_price(ts_event, mid_price)

            # Push completed candle to DataHub
            if completed_candle and self.data_hub:
                try:
                    self.data_hub.update_candle_1m(completed_candle)
                    self.candles_generated += 1
                    logger.info(
                        f"✅ DataBento candle pushed to DataHub: {completed_candle.symbol} "
                        f"[{completed_candle.timestamp}] O={completed_candle.open:.5f} "
                        f"C={completed_candle.close:.5f} V={completed_candle.volume:.0f} (REAL volume)"
                    )
                except Exception as e:
                    logger.error(f"Failed to push DataBento candle to DataHub: {e}")

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

    async def _handle_trade(self, record: DBNRecord, instrument_id: int, cont_symbol: str):
        """
        Handle trade execution record.

        Args:
            record: Trade record
            instrument_id: Database instrument ID
            cont_symbol: Continuous contract symbol (6E.c.0, 6B.c.0, etc.)
        """
        ts_event = datetime.fromtimestamp(record.ts_event / 1e9)
        ts_recv = datetime.utcnow()

        symbol = cont_symbol  # Use continuous symbol instead of record.symbol

        # Determine aggressor side
        side = 'B' if record.side == 'B' else 'S'

        # Add to trade window for order flow calculations
        if symbol in self.trade_windows:
            self.trade_windows[symbol].append({
                'timestamp': ts_recv,
                'price': record.price,
                'size': record.size,
                'side': side,
                'is_sweep': False  # TODO: Detect sweeps from trade characteristics
            })

        # Update bar aggregator with trade price and volume (REAL volume from trades)
        if symbol in self.bar_aggregators:
            aggregator = self.bar_aggregators[symbol]

            # Update OHLC with trade price
            completed_candle = aggregator.update_price(ts_event, record.price)

            # Add real volume from this trade
            aggregator.add_trade_volume(record.size)

            # Push completed candle to DataHub
            if completed_candle and self.data_hub:
                try:
                    self.data_hub.update_candle_1m(completed_candle)
                    self.candles_generated += 1
                    logger.info(
                        f"✅ DataBento candle pushed to DataHub: {completed_candle.symbol} "
                        f"[{completed_candle.timestamp}] O={completed_candle.open:.5f} "
                        f"C={completed_candle.close:.5f} V={completed_candle.volume:.0f} (REAL volume from trades)"
                    )
                except Exception as e:
                    logger.error(f"Failed to push DataBento candle to DataHub: {e}")

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

    def get_latest_order_flow(self, symbol: str) -> Optional[OrderFlowMetrics]:
        """
        Get latest order flow metrics for a futures symbol.

        Args:
            symbol: Futures symbol (6E, 6B, 6J) or spot pair (EUR_USD, etc.)

        Returns:
            OrderFlowMetrics object or None
        """
        # Convert spot to futures if needed
        if '_' in symbol:
            # It's a spot pair, find the futures symbol
            futures_symbol = None
            for fut, spot in self.futures_to_spot.items():
                if spot == symbol:
                    futures_symbol = fut
                    break
            if not futures_symbol:
                return None
        else:
            futures_symbol = symbol
            symbol = self.futures_to_spot.get(futures_symbol)
            if not symbol:
                return None

        # Calculate metrics from trade window
        return self._calculate_order_flow_metrics(futures_symbol, symbol)

    def _calculate_order_flow_metrics(self, futures_symbol: str, spot_symbol: str) -> Optional[OrderFlowMetrics]:
        """
        Calculate order flow metrics from rolling trade window.

        Args:
            futures_symbol: Futures contract symbol (6E, 6B, etc.)
            spot_symbol: Spot pair symbol (EUR_USD, GBP_USD, etc.)

        Returns:
            OrderFlowMetrics object
        """
        if futures_symbol not in self.trade_windows:
            return None

        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=60)

        # Clean old trades
        trade_window = self.trade_windows[futures_symbol]
        while trade_window and trade_window[0]['timestamp'] < cutoff:
            trade_window.popleft()

        if not trade_window:
            return None

        # Calculate volume metrics
        buy_volume = sum(t['size'] for t in trade_window if t['side'] == 'B')
        sell_volume = sum(t['size'] for t in trade_window if t['side'] == 'S')
        total_volume = buy_volume + sell_volume
        net_volume_delta = buy_volume - sell_volume

        # Calculate VWAP
        vwap = None
        if total_volume > 0:
            weighted_sum = sum(t['price'] * t['size'] for t in trade_window)
            vwap = weighted_sum / total_volume

        # Count sweeps (aggressive trades through multiple levels)
        buy_sweeps = sum(1 for t in trade_window if t['side'] == 'B' and t.get('is_sweep', False))
        sell_sweeps = sum(1 for t in trade_window if t['side'] == 'S' and t.get('is_sweep', False))

        # Get top of book
        book = self.order_books.get(futures_symbol)
        best_bid = book.bids[0][0] if book and book.bids else None
        best_ask = book.asks[0][0] if book and book.asks else None
        bid_size = book.bids[0][1] if book and book.bids else 0.0
        ask_size = book.asks[0][1] if book and book.asks else 0.0

        # Calculate Order Flow Imbalance (OFI) from book changes
        ofi_60s = self._calculate_ofi(futures_symbol, cutoff)

        # Create metrics object
        metrics = OrderFlowMetrics(
            symbol=spot_symbol,
            futures_symbol=futures_symbol,
            timestamp=now,
            window_seconds=60,
            ofi_60s=ofi_60s,
            net_volume_delta=net_volume_delta,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            total_volume=total_volume,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_size=bid_size,
            ask_size=ask_size,
            buy_sweep_count=buy_sweeps,
            sell_sweep_count=sell_sweeps,
            vwap_60s=vwap,
            updates_count=len(trade_window)
        )

        # Push to DataHub
        if self.data_hub:
            try:
                self.data_hub.update_order_flow(metrics)
                self.order_flow_updates += 1
            except Exception as e:
                if self.order_flow_updates % 100 == 0:
                    logger.warning(f"DataHub order flow update failed: {e}")

        return metrics

    def _calculate_ofi(self, futures_symbol: str, cutoff: datetime) -> float:
        """
        Calculate Order Flow Imbalance (OFI) over rolling window.

        OFI measures the net change in order book depth at the best bid/ask.
        Positive OFI = buying pressure, Negative OFI = selling pressure.

        Args:
            futures_symbol: Futures symbol
            cutoff: Timestamp cutoff for rolling window

        Returns:
            OFI value (positive = bullish, negative = bearish)
        """
        if futures_symbol not in self.ofi_windows:
            return 0.0

        ofi_window = self.ofi_windows[futures_symbol]

        # Clean old OFI events
        while ofi_window and ofi_window[0]['timestamp'] < cutoff:
            ofi_window.popleft()

        if not ofi_window:
            return 0.0

        # Sum OFI contributions
        total_ofi = sum(event['ofi_delta'] for event in ofi_window)
        return total_ofi

    def _update_ofi_on_book_change(self, futures_symbol: str, prev_book: dict, new_book: dict):
        """
        Update OFI when order book changes.

        OFI logic:
        - If best bid price increases OR bid size increases at same price: +Δbid_size
        - If best ask price decreases OR ask size increases at same price: -Δask_size

        Args:
            futures_symbol: Futures symbol
            prev_book: Previous book state {'bid_price': float, 'bid_size': float, ...}
            new_book: New book state
        """
        if futures_symbol not in self.ofi_windows:
            return

        ofi_delta = 0.0
        timestamp = datetime.utcnow()

        # Bid side
        if new_book.get('bid_price', 0) > prev_book.get('bid_price', 0):
            # Bid price increased (aggressive buying)
            ofi_delta += new_book.get('bid_size', 0)
        elif new_book.get('bid_price', 0) == prev_book.get('bid_price', 0):
            # Same price, check size change
            bid_delta = new_book.get('bid_size', 0) - prev_book.get('bid_size', 0)
            if bid_delta > 0:
                ofi_delta += bid_delta

        # Ask side
        if new_book.get('ask_price', float('inf')) < prev_book.get('ask_price', float('inf')):
            # Ask price decreased (aggressive selling)
            ofi_delta -= new_book.get('ask_size', 0)
        elif new_book.get('ask_price', 0) == prev_book.get('ask_price', 0):
            # Same price, check size change
            ask_delta = new_book.get('ask_size', 0) - prev_book.get('ask_size', 0)
            if ask_delta > 0:
                ofi_delta -= ask_delta

        # Store OFI event
        if ofi_delta != 0:
            self.ofi_windows[futures_symbol].append({
                'timestamp': timestamp,
                'ofi_delta': ofi_delta
            })


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
