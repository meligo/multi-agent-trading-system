"""
DataHub - Shared In-Memory Market Data Cache

Provides sub-millisecond access to real-time market data across processes.
Uses multiprocessing.managers.BaseManager for inter-process communication.

Architecture:
- Producers (WebSocket, DataBento) push updates
- Consumers (UnifiedDataFetcher, Agents) read snapshots
- Automatic DB fallback for cold starts
- Thread-safe with internal locks

Usage:
    # In main process (Dashboard)
    manager = start_data_hub_manager()
    hub = manager.get_hub()

    # In subprocess (WebSocket)
    hub = connect_to_data_hub()
    hub.update_tick(tick)

    # In consumer (UnifiedDataFetcher)
    tick = hub.get_latest_tick('EUR_USD')
    candles = hub.get_latest_candles('EUR_USD', limit=100)
"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Deque
from multiprocessing.managers import BaseManager
import os

from market_data_models import Tick, Candle, OrderFlowMetrics

logger = logging.getLogger(__name__)


class DataHub:
    """
    Thread-safe in-memory cache for market data.

    Stores:
    - Latest tick per symbol (bid, ask, spread)
    - 1-minute candles (rolling window, 100-200 bars)
    - Order flow metrics per symbol (60-second window)

    All methods are thread-safe via internal locks.
    """

    def __init__(self, max_candles: int = 200):
        """
        Initialize DataHub.

        Args:
            max_candles: Maximum candles to store per symbol
        """
        self.max_candles = max_candles

        # Storage dictionaries (symbol -> data)
        self.ticks: Dict[str, Tick] = {}
        self.candles_1m: Dict[str, Deque[Candle]] = {}
        self.order_flow: Dict[str, OrderFlowMetrics] = {}

        # Timestamp tracking for staleness
        self.last_update_ts: Dict[str, Dict[str, datetime]] = {}

        # Thread locks
        self._tick_lock = threading.Lock()
        self._candle_lock = threading.Lock()
        self._flow_lock = threading.Lock()

        # Statistics
        self.stats = {
            'ticks_received': 0,
            'candles_received': 0,
            'order_flow_updates': 0,
            'get_tick_calls': 0,
            'get_candles_calls': 0,
            'get_flow_calls': 0
        }

        logger.info(f"DataHub initialized (max_candles={max_candles})")

    # ========================================================================
    # UPDATE METHODS (called by producers)
    # ========================================================================

    def update_tick(self, tick: Tick) -> None:
        """
        Update latest tick for a symbol.

        Args:
            tick: Tick object
        """
        with self._tick_lock:
            self.ticks[tick.symbol] = tick

            # Update timestamp
            if tick.symbol not in self.last_update_ts:
                self.last_update_ts[tick.symbol] = {}
            self.last_update_ts[tick.symbol]['tick'] = datetime.utcnow()

            self.stats['ticks_received'] += 1

    def update_candle_1m(self, candle: Candle) -> None:
        """
        Update 1-minute candle for a symbol.

        Args:
            candle: Candle object
        """
        with self._candle_lock:
            # Initialize deque if first candle
            if candle.symbol not in self.candles_1m:
                self.candles_1m[candle.symbol] = deque(maxlen=self.max_candles)

            # Add candle (deque automatically removes oldest)
            self.candles_1m[candle.symbol].append(candle)

            # Update timestamp
            if candle.symbol not in self.last_update_ts:
                self.last_update_ts[candle.symbol] = {}
            self.last_update_ts[candle.symbol]['candle'] = datetime.utcnow()

            self.stats['candles_received'] += 1

    def update_order_flow(self, metrics: OrderFlowMetrics) -> None:
        """
        Update order flow metrics for a symbol.

        Args:
            metrics: OrderFlowMetrics object
        """
        with self._flow_lock:
            self.order_flow[metrics.symbol] = metrics

            # Update timestamp
            if metrics.symbol not in self.last_update_ts:
                self.last_update_ts[metrics.symbol] = {}
            self.last_update_ts[metrics.symbol]['order_flow'] = datetime.utcnow()

            self.stats['order_flow_updates'] += 1

    # ========================================================================
    # RETRIEVAL METHODS (called by consumers)
    # ========================================================================

    def get_latest_tick(self, symbol: str) -> Optional[Tick]:
        """
        Get latest tick for a symbol.

        Args:
            symbol: Trading pair (EUR_USD, GBP_USD, etc.)

        Returns:
            Tick object or None if not available
        """
        with self._tick_lock:
            self.stats['get_tick_calls'] += 1
            return self.ticks.get(symbol)

    def get_latest_candles(self, symbol: str, limit: int = 100) -> List[Candle]:
        """
        Get latest N candles for a symbol.

        Args:
            symbol: Trading pair
            limit: Number of candles to return (most recent)

        Returns:
            List of Candle objects (oldest to newest)
        """
        with self._candle_lock:
            self.stats['get_candles_calls'] += 1

            if symbol not in self.candles_1m:
                return []

            # Get last N candles
            candles = list(self.candles_1m[symbol])
            if len(candles) > limit:
                candles = candles[-limit:]

            return candles

    def get_latest_order_flow(self, symbol: str) -> Optional[OrderFlowMetrics]:
        """
        Get latest order flow metrics for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            OrderFlowMetrics object or None if not available
        """
        with self._flow_lock:
            self.stats['get_flow_calls'] += 1
            return self.order_flow.get(symbol)

    # ========================================================================
    # BULK OPERATIONS (for warm-start from DB)
    # ========================================================================

    def warm_start_candles(self, symbol: str, candles: List[Candle]) -> int:
        """
        Load historical candles from database (cold start).

        Args:
            symbol: Trading pair
            candles: List of Candle objects (should be pre-sorted oldest to newest)

        Returns:
            Number of candles loaded
        """
        with self._candle_lock:
            if symbol not in self.candles_1m:
                self.candles_1m[symbol] = deque(maxlen=self.max_candles)

            # Add all candles
            for candle in candles:
                self.candles_1m[symbol].append(candle)

            logger.info(f"Warm-started {len(candles)} candles for {symbol}")
            return len(candles)

    def warm_start_all(self, symbols: List[str], db_fetch_func, limit: int = 100):
        """
        Warm-start cache from database for multiple symbols.

        Args:
            symbols: List of trading pairs
            db_fetch_func: Callable that fetches candles from DB
                          Signature: db_fetch_func(symbol, limit) -> List[Candle]
            limit: Number of candles to load per symbol
        """
        logger.info(f"Warm-starting DataHub for {len(symbols)} symbols...")

        total_loaded = 0
        for symbol in symbols:
            try:
                candles = db_fetch_func(symbol, limit)
                if candles:
                    count = self.warm_start_candles(symbol, candles)
                    total_loaded += count
            except Exception as e:
                logger.error(f"Failed to warm-start {symbol}: {e}")

        logger.info(f"✅ Warm-start complete: {total_loaded} total candles loaded")

    # ========================================================================
    # STATUS & DIAGNOSTICS
    # ========================================================================

    def get_status(self) -> Dict:
        """
        Get DataHub status and statistics.

        Returns:
            Dictionary with status info
        """
        with self._tick_lock, self._candle_lock, self._flow_lock:
            candle_counts = {
                symbol: len(candles) for symbol, candles in self.candles_1m.items()
            }

            return {
                'symbols_tracked': list(set(
                    list(self.ticks.keys()) +
                    list(self.candles_1m.keys()) +
                    list(self.order_flow.keys())
                )),
                'ticks_count': len(self.ticks),
                'candles_by_symbol': candle_counts,
                'order_flow_count': len(self.order_flow),
                'stats': self.stats.copy(),
                'last_updates': self.last_update_ts.copy()
            }

    def check_staleness(self, symbol: str, max_age_seconds: Dict[str, int] = None) -> Dict[str, bool]:
        """
        Check if data for a symbol is stale.

        Args:
            symbol: Trading pair
            max_age_seconds: Dict of max ages for each data type
                           Default: {'tick': 2, 'candle': 120, 'order_flow': 5}

        Returns:
            Dictionary of staleness flags
        """
        if max_age_seconds is None:
            max_age_seconds = {'tick': 2, 'candle': 120, 'order_flow': 5}

        now = datetime.utcnow()
        staleness = {}

        if symbol in self.last_update_ts:
            for data_type, max_age in max_age_seconds.items():
                if data_type in self.last_update_ts[symbol]:
                    last_update = self.last_update_ts[symbol][data_type]
                    age = (now - last_update).total_seconds()
                    staleness[data_type] = age > max_age
                else:
                    staleness[data_type] = True
        else:
            staleness = {k: True for k in max_age_seconds.keys()}

        return staleness

    def clear_symbol(self, symbol: str):
        """Clear all data for a symbol."""
        with self._tick_lock, self._candle_lock, self._flow_lock:
            self.ticks.pop(symbol, None)
            self.candles_1m.pop(symbol, None)
            self.order_flow.pop(symbol, None)
            self.last_update_ts.pop(symbol, None)
            logger.info(f"Cleared data for {symbol}")

    def clear_all(self):
        """Clear all data."""
        with self._tick_lock, self._candle_lock, self._flow_lock:
            self.ticks.clear()
            self.candles_1m.clear()
            self.order_flow.clear()
            self.last_update_ts.clear()
            logger.info("Cleared all DataHub data")


# ============================================================================
# MANAGER SETUP (for inter-process communication)
# ============================================================================

from multiprocessing.managers import BaseProxy

# Custom proxy to control what methods clients can access
class DataHubProxy(BaseProxy):
    """Proxy for DataHub that exposes specific methods to clients."""
    _exposed_ = (
        'update_tick', 'update_candle_1m', 'update_order_flow',
        'get_latest_tick', 'get_latest_candles', 'get_latest_order_flow',
        'warm_start_candles', 'warm_start_all',
        'get_status', 'check_staleness',
        'clear_symbol', 'clear_all'
    )

    # Define proxy methods for clean IDE support
    def update_tick(self, tick):
        return self._callmethod('update_tick', (tick,))

    def update_candle_1m(self, candle):
        return self._callmethod('update_candle_1m', (candle,))

    def update_order_flow(self, metrics):
        return self._callmethod('update_order_flow', (metrics,))

    def get_latest_tick(self, symbol):
        return self._callmethod('get_latest_tick', (symbol,))

    def get_latest_candles(self, symbol, limit=100):
        return self._callmethod('get_latest_candles', (symbol, limit))

    def get_latest_order_flow(self, symbol):
        return self._callmethod('get_latest_order_flow', (symbol,))

    def warm_start_candles(self, symbol, candles):
        return self._callmethod('warm_start_candles', (symbol, candles))

    def warm_start_all(self, symbols, db_fetch_func, limit=100):
        return self._callmethod('warm_start_all', (symbols, db_fetch_func, limit))

    def get_status(self):
        return self._callmethod('get_status')

    def check_staleness(self, symbol, max_age_seconds=None):
        return self._callmethod('check_staleness', (symbol, max_age_seconds))

    def clear_symbol(self, symbol):
        return self._callmethod('clear_symbol', (symbol,))

    def clear_all(self):
        return self._callmethod('clear_all')


# Singleton instance (lives in the manager server process)
_datahub_singleton = None
_singleton_lock = threading.Lock()

def _get_datahub_singleton():
    """
    Factory function that returns the singleton DataHub instance.

    This runs in the manager server process and ensures all clients
    get the same DataHub instance.
    """
    global _datahub_singleton
    if _datahub_singleton is None:
        with _singleton_lock:
            if _datahub_singleton is None:
                _datahub_singleton = DataHub()
    return _datahub_singleton


class DataHubManager(BaseManager):
    """Custom manager for DataHub."""
    pass


def start_data_hub_manager(
    address: tuple = ('127.0.0.1', 50000),
    authkey: bytes = b'forex_scalper_2025'
) -> DataHubManager:
    """
    Start DataHub manager server.

    Args:
        address: (host, port) tuple
        authkey: Authentication key for clients

    Returns:
        DataHubManager instance
    """
    # Register with singleton factory (server-side)
    DataHubManager.register('DataHub', callable=_get_datahub_singleton, proxytype=DataHubProxy)

    manager = DataHubManager(address=address, authkey=authkey)
    manager.start()
    logger.info(f"✅ DataHub manager started at {address}")
    return manager


def connect_to_data_hub(
    address: tuple = ('127.0.0.1', 50000),
    authkey: bytes = b'forex_scalper_2025'
) -> DataHub:
    """
    Connect to existing DataHub manager (from subprocess).

    Args:
        address: (host, port) tuple
        authkey: Authentication key

    Returns:
        DataHub proxy object
    """
    # Register without callable (client-side)
    DataHubManager.register('DataHub', proxytype=DataHubProxy)

    manager = DataHubManager(address=address, authkey=authkey)
    manager.connect()
    hub = manager.DataHub()
    logger.info(f"✅ Connected to DataHub at {address}")
    return hub


def get_data_hub_from_env() -> Optional[DataHub]:
    """
    Get DataHub connection from environment variables.

    Looks for:
    - DATA_HUB_HOST (default: 127.0.0.1)
    - DATA_HUB_PORT (default: 50000)
    - DATA_HUB_AUTHKEY (default: forex_scalper_2025)

    Returns:
        DataHub proxy or None if env vars not set
    """
    host = os.getenv('DATA_HUB_HOST', '127.0.0.1')
    port = int(os.getenv('DATA_HUB_PORT', '50000'))
    authkey = os.getenv('DATA_HUB_AUTHKEY', 'forex_scalper_2025').encode()

    try:
        return connect_to_data_hub(address=(host, port), authkey=authkey)
    except Exception as e:
        logger.error(f"Failed to connect to DataHub: {e}")
        return None


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test DataHub locally
    print("\n" + "="*80)
    print("DataHub Test")
    print("="*80)

    hub = DataHub()

    # Test tick update
    tick = Tick(
        symbol='EUR_USD',
        bid=1.0500,
        ask=1.0510,
        mid=1.0505,
        spread=1.0,
        timestamp=datetime.utcnow()
    )
    hub.update_tick(tick)
    print(f"\n✅ Tick updated: {tick.symbol}")

    # Test candle update
    candle = Candle(
        symbol='EUR_USD',
        timestamp=datetime.utcnow(),
        open=1.0500,
        high=1.0520,
        low=1.0495,
        close=1.0510,
        volume=1000.0
    )
    hub.update_candle_1m(candle)
    print(f"✅ Candle updated: {candle.symbol}")

    # Test retrieval
    retrieved_tick = hub.get_latest_tick('EUR_USD')
    print(f"\n✅ Retrieved tick: {retrieved_tick.bid}/{retrieved_tick.ask}")

    retrieved_candles = hub.get_latest_candles('EUR_USD', limit=10)
    print(f"✅ Retrieved {len(retrieved_candles)} candles")

    # Test status
    status = hub.get_status()
    print(f"\n📊 DataHub Status:")
    print(f"   Symbols: {status['symbols_tracked']}")
    print(f"   Stats: {status['stats']}")
