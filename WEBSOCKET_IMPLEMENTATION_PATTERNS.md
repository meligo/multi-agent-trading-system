# WebSocket Implementation Patterns & Code Recipes

## Table of Contents
1. Connection Management Patterns
2. Cache Synchronization Patterns
3. Error Handling & Recovery
4. Multi-Symbol Streaming
5. Backfill Strategies
6. Rate Limit Handling
7. Monitoring & Observability

---

## 1. Connection Management Patterns

### Pattern 1: Persistent Connection with Keep-Alive

```python
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class WebSocketConnection:
    """
    Manages WebSocket connection with automatic keep-alive
    Prevents idle timeout by sending periodic ping frames
    """

    def __init__(self, ws_url: str, keep_alive_interval: int = 30):
        self.ws_url = ws_url
        self.keep_alive_interval = keep_alive_interval
        self.ws = None
        self.last_message_time = None
        self.connection_closed = False

    async def connect(self):
        """Establish connection with automatic keep-alive"""
        import websockets

        try:
            self.ws = await websockets.connect(self.ws_url)
            self.connection_closed = False
            self.last_message_time = datetime.now()
            logger.info(f"Connected to {self.ws_url}")

            # Start keep-alive task
            asyncio.create_task(self._keep_alive_loop())

            return self.ws
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

    async def _keep_alive_loop(self):
        """Send ping frames every N seconds to keep connection alive"""
        while not self.connection_closed:
            try:
                time_since_last = (datetime.now() - self.last_message_time).total_seconds()

                if time_since_last > self.keep_alive_interval:
                    await self.ws.ping()
                    logger.debug(f"Sent ping (last message {time_since_last:.0f}s ago)")

                await asyncio.sleep(self.keep_alive_interval)

            except Exception as e:
                logger.error(f"Keep-alive failed: {e}")
                break

    async def send(self, message: str):
        """Send message and update timestamp"""
        try:
            await self.ws.send(message)
            self.last_message_time = datetime.now()
        except Exception as e:
            logger.error(f"Send failed: {e}")
            raise

    async def receive(self):
        """Receive message and update timestamp"""
        try:
            message = await self.ws.recv()
            self.last_message_time = datetime.now()
            return message
        except Exception as e:
            logger.error(f"Receive failed: {e}")
            raise

    async def close(self):
        """Close connection gracefully"""
        self.connection_closed = True
        if self.ws:
            await self.ws.close()
        logger.info("Connection closed")
```

### Pattern 2: Connection Pool for Multiple Symbols

```python
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class SymbolSubscription:
    symbol: str
    timeframe: str
    handler: Callable

class WebSocketConnectionPool:
    """
    Manages multiple symbol subscriptions efficiently
    Each exchange may have connection limits (e.g., IG: 40 max)
    """

    def __init__(self, max_connections: int = 40):
        self.max_connections = max_connections
        self.connections: Dict[str, WebSocketConnection] = {}
        self.subscriptions: Dict[str, List[SymbolSubscription]] = {}
        self.connection_count = 0

    async def subscribe(self, symbol: str, timeframe: str,
                       handler: Callable, ws_url: str) -> bool:
        """
        Subscribe to symbol with auto-connection pooling
        Returns False if connection limit exceeded
        """

        if self.connection_count >= self.max_connections:
            logger.error(
                f"Connection pool full ({self.connection_count}/"
                f"{self.max_connections}). Cannot add {symbol}"
            )
            return False

        # Reuse existing connection or create new
        connection_id = f"{ws_url}:{symbol}"

        if connection_id not in self.connections:
            try:
                conn = WebSocketConnection(ws_url)
                await conn.connect()
                self.connections[connection_id] = conn
                self.connection_count += 1

                # Start listening task
                asyncio.create_task(
                    self._listen_loop(connection_id, handler)
                )

            except Exception as e:
                logger.error(f"Failed to create connection for {symbol}: {e}")
                return False

        # Track subscription
        if connection_id not in self.subscriptions:
            self.subscriptions[connection_id] = []

        self.subscriptions[connection_id].append(
            SymbolSubscription(symbol, timeframe, handler)
        )

        logger.info(f"Subscribed to {symbol} ({self.connection_count}/{self.max_connections})")
        return True

    async def _listen_loop(self, connection_id: str, handler: Callable):
        """Listen for messages on connection"""
        try:
            conn = self.connections[connection_id]
            while True:
                message = await conn.receive()

                # Route to all subscribed handlers for this connection
                for subscription in self.subscriptions.get(connection_id, []):
                    asyncio.create_task(
                        handler(subscription.symbol, subscription.timeframe, message)
                    )

        except Exception as e:
            logger.error(f"Listen loop failed for {connection_id}: {e}")
            # Cleanup
            if connection_id in self.connections:
                await self.connections[connection_id].close()
                del self.connections[connection_id]
                self.connection_count -= 1

    async def close_all(self):
        """Close all connections gracefully"""
        for conn in self.connections.values():
            await conn.close()
        self.connections.clear()
        self.subscriptions.clear()
        logger.info("All connections closed")
```

---

## 2. Cache Synchronization Patterns

### Pattern 3: Two-Layer Cache Sync

```python
from typing import Any, Dict, List
import json

class TwoLayerCache:
    """
    Synchronizes between:
    - Hot cache (Redis): Last 1 hour of data, instant access
    - Cold storage (TimescaleDB): All historical data

    Periodic sync ensures consistency and durability
    """

    def __init__(self, redis_client, db_client):
        self.redis = redis_client
        self.db = db_client
        self.sync_interval = 300  # Sync every 5 minutes
        self.pending_writes = []

    async def add_candle(self, symbol: str, timeframe: str, candle: List[float]):
        """
        Add candle to both layers
        Redis: immediate write for real-time access
        DB: queued for batch write
        """
        timestamp = datetime.fromtimestamp(candle[0] / 1000).isoformat()

        candle_data = {
            'o': candle[1],
            'h': candle[2],
            'l': candle[3],
            'c': candle[4],
            'v': candle[5],
        }

        # Write to hot cache immediately
        redis_key = f"ohlcv:{symbol}:{timeframe}:{timestamp}"
        await self.redis.setex(
            redis_key,
            30 * 24 * 3600,  # 30 day TTL
            json.dumps(candle_data)
        )

        # Queue for cold storage
        self.pending_writes.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'timeframe': timeframe,
            **candle_data
        })

        # Batch write when queue reaches threshold
        if len(self.pending_writes) >= 100:
            await self._flush_to_db()

    async def _flush_to_db(self):
        """Batch write pending data to database"""
        if not self.pending_writes:
            return

        try:
            await self.db.insert_many('ohlcv_data', self.pending_writes)
            logger.info(f"Flushed {len(self.pending_writes)} candles to database")
            self.pending_writes = []
        except Exception as e:
            logger.error(f"Database flush failed: {e}")
            # Keep pending data for retry

    async def sync_loop(self):
        """Periodic sync of pending writes"""
        while True:
            await asyncio.sleep(self.sync_interval)
            await self._flush_to_db()

    async def get_candle(self, symbol: str, timeframe: str,
                        timestamp: str, check_db: bool = True) -> Optional[Dict]:
        """
        Get candle with fallback strategy
        1. Try hot cache (Redis)
        2. Fall back to cold storage (TimescaleDB)
        """

        # Try hot cache first
        redis_key = f"ohlcv:{symbol}:{timeframe}:{timestamp}"
        data = await self.redis.get(redis_key)

        if data:
            return json.loads(data)

        # Fall back to database
        if check_db:
            db_result = await self.db.find_one('ohlcv_data', {
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': timestamp
            })
            if db_result:
                return db_result

        return None

    async def get_range(self, symbol: str, timeframe: str,
                       since: datetime, until: datetime) -> List[Dict]:
        """
        Get candles in time range
        Preferentially from cache, backfill from DB if needed
        """

        # Get from hot cache
        pattern = f"ohlcv:{symbol}:{timeframe}:*"
        keys = await self.redis.keys(pattern)

        cached_candles = []
        for key in keys:
            data = await self.redis.get(key)
            cached_candles.append(json.loads(data))

        # Query database for older data not in cache
        db_candles = await self.db.find('ohlcv_data', {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': {'$gte': since, '$lte': until}
        })

        # Combine and deduplicate
        all_candles = {c['timestamp']: c for c in cached_candles}
        for c in db_candles:
            if c['timestamp'] not in all_candles:
                all_candles[c['timestamp']] = c

        return sorted(all_candles.values(), key=lambda x: x['timestamp'])
```

### Pattern 4: Cache Invalidation Strategy

```python
from enum import Enum

class InvalidationStrategy(Enum):
    TTL = "ttl"              # Time-based expiry
    LRU = "lru"              # Least recently used
    SIZE_LIMIT = "size_limit"  # Maximum entries

class SmartCache:
    """
    Implements multiple cache invalidation strategies
    Prevents unbounded memory growth
    """

    def __init__(self, max_size: int = 100000, strategy: InvalidationStrategy = InvalidationStrategy.TTL):
        self.max_size = max_size
        self.strategy = strategy
        self.cache = {}
        self.access_times = {}
        self.creation_times = {}
        self.access_counts = {}

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set cache value with invalidation strategy"""

        now = datetime.now()

        # Check size limit
        if len(self.cache) >= self.max_size:
            if self.strategy == InvalidationStrategy.TTL:
                await self._evict_expired()
            elif self.strategy == InvalidationStrategy.LRU:
                await self._evict_lru()
            elif self.strategy == InvalidationStrategy.SIZE_LIMIT:
                await self._evict_oldest()

        self.cache[key] = value
        self.access_times[key] = now
        self.creation_times[key] = now
        self.access_counts[key] = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value with access time tracking"""

        if key not in self.cache:
            return None

        value = self.cache[key]
        self.access_times[key] = datetime.now()
        self.access_counts[key] += 1

        return value

    async def _evict_expired(self):
        """Remove expired entries (TTL strategy)"""
        now = datetime.now()
        ttl = timedelta(days=30)

        expired = [
            k for k, t in self.creation_times.items()
            if (now - t) > ttl
        ]

        for k in expired:
            del self.cache[k]
            del self.access_times[k]
            del self.creation_times[k]
            del self.access_counts[k]

        logger.info(f"Evicted {len(expired)} expired entries")

    async def _evict_lru(self):
        """Remove least recently used entries (LRU strategy)"""
        # Sort by access time, remove oldest 10%
        to_remove = int(self.max_size * 0.1)

        sorted_keys = sorted(
            self.access_times.items(),
            key=lambda x: x[1]
        )[:to_remove]

        for k, _ in sorted_keys:
            del self.cache[k]
            del self.access_times[k]
            del self.creation_times[k]
            del self.access_counts[k]

        logger.info(f"Evicted {len(sorted_keys)} LRU entries")

    async def _evict_oldest(self):
        """Remove oldest entries by creation time (FIFO strategy)"""
        to_remove = int(self.max_size * 0.1)

        sorted_keys = sorted(
            self.creation_times.items(),
            key=lambda x: x[1]
        )[:to_remove]

        for k, _ in sorted_keys:
            del self.cache[k]
            del self.access_times[k]
            del self.creation_times[k]
            del self.access_counts[k]

        logger.info(f"Evicted {len(sorted_keys)} oldest entries")
```

---

## 3. Error Handling & Recovery

### Pattern 5: Resilient Streaming with Exponential Backoff

```python
class ResilientStream:
    """
    Handles connection failures gracefully
    Implements exponential backoff for retries
    Detects and backfills missed data
    """

    def __init__(self, api_client, max_retries: int = 5):
        self.api = api_client
        self.max_retries = max_retries
        self.last_received_time = None
        self.backoff_base = 0.1  # Start at 100ms

    async def stream_with_recovery(self, symbol: str, timeframe: str):
        """
        Stream candles with automatic recovery
        Retries with exponential backoff on failure
        """

        retry_count = 0

        while retry_count < self.max_retries:
            try:
                async for candle in self.api.watch_ohlcv(symbol, timeframe):
                    # Reset retry counter on successful update
                    retry_count = 0
                    self.backoff_base = 0.1

                    # Check for gaps (missed candles)
                    current_time = candle[0]
                    if self.last_received_time:
                        gap_ms = current_time - self.last_received_time
                        expected_interval = self._get_interval_ms(timeframe)

                        if gap_ms > expected_interval * 1.5:  # Allow 50% variance
                            logger.warning(
                                f"Detected gap of {gap_ms}ms for {symbol} "
                                f"(expected {expected_interval}ms)"
                            )
                            # Backfill missing candles
                            await self._backfill_gap(
                                symbol, timeframe,
                                self.last_received_time,
                                current_time
                            )

                    self.last_received_time = current_time
                    yield candle

            except ConnectionError as e:
                retry_count += 1
                backoff = min(
                    self.backoff_base * (2 ** (retry_count - 1)),
                    60  # Cap at 60 seconds
                )
                logger.error(
                    f"Connection error (retry {retry_count}/{self.max_retries}): {e}. "
                    f"Retrying in {backoff:.1f}s..."
                )
                await asyncio.sleep(backoff)

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise

        raise Exception(
            f"Max retries ({self.max_retries}) exceeded. Stream failed."
        )

    async def _backfill_gap(self, symbol: str, timeframe: str,
                           from_time: int, to_time: int):
        """
        Backfill missing candles using REST API
        Used only when WebSocket gap detected
        """

        try:
            logger.info(f"Backfilling {symbol} {timeframe} from gap")

            candles = await self.api.fetch_ohlcv(
                symbol,
                timeframe,
                since=from_time + self._get_interval_ms(timeframe),
                limit=(to_time - from_time) // self._get_interval_ms(timeframe)
            )

            logger.info(f"Backfilled {len(candles)} missing candles")
            return candles

        except Exception as e:
            logger.error(f"Backfill failed: {e}")
            return []

    def _get_interval_ms(self, timeframe: str) -> int:
        """Convert timeframe string to milliseconds"""
        intervals = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
        }
        return intervals.get(timeframe, 60 * 1000)
```

---

## 4. Multi-Symbol Streaming

### Pattern 6: Concurrent Multi-Symbol Handler

```python
from concurrent.futures import as_completed
import asyncio

class MultiSymbolStreamManager:
    """
    Efficiently manages streaming for multiple symbols
    Handles each symbol in parallel with resource limits
    """

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.active_streams: Dict[str, asyncio.Task] = {}
        self.stream_semaphore = asyncio.Semaphore(max_concurrent)

    async def stream_multiple(self, symbols: List[str],
                             timeframe: str,
                             callback: Callable):
        """Stream multiple symbols concurrently"""

        tasks = [
            asyncio.create_task(
                self._stream_single(symbol, timeframe, callback)
            )
            for symbol in symbols
        ]

        self.active_streams = {s: t for s, t in zip(symbols, tasks)}

        # Wait for all or first exception
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Stream {symbol} failed: {result}")

    async def _stream_single(self, symbol: str, timeframe: str,
                            callback: Callable):
        """Stream single symbol with concurrency control"""

        async with self.stream_semaphore:
            logger.info(f"Starting stream for {symbol}")

            resilient = ResilientStream(self.api)

            try:
                async for candle in resilient.stream_with_recovery(
                    symbol, timeframe
                ):
                    await callback(symbol, timeframe, candle)

            except Exception as e:
                logger.error(f"Stream {symbol} terminated: {e}")
                raise

    async def stop_stream(self, symbol: str):
        """Stop streaming for specific symbol"""
        if symbol in self.active_streams:
            self.active_streams[symbol].cancel()
            del self.active_streams[symbol]
            logger.info(f"Stopped stream for {symbol}")

    async def stop_all_streams(self):
        """Stop all active streams"""
        for task in self.active_streams.values():
            task.cancel()

        # Wait for cancellation
        if self.active_streams:
            await asyncio.gather(
                *self.active_streams.values(),
                return_exceptions=True
            )

        self.active_streams.clear()
        logger.info("All streams stopped")
```

---

## 5. Backfill Strategies

### Pattern 7: Smart Backfill with Caching

```python
class SmartBackfiller:
    """
    Intelligently backfills missing data
    Caches backfill results to avoid duplicate requests
    Uses efficient batching
    """

    def __init__(self, api_client, cache):
        self.api = api_client
        self.cache = cache
        self.backfill_cache = {}  # Track completed backfills
        self.backfill_batch_size = 100

    async def backfill_gaps(self, symbol: str, timeframe: str,
                           from_time: datetime, to_time: datetime) -> List:
        """
        Backfill data for time range
        Uses cache to avoid duplicate requests
        """

        cache_key = f"backfill:{symbol}:{timeframe}:{from_time}:{to_time}"

        # Check if already backfilled
        if cache_key in self.backfill_cache:
            logger.debug(f"Using cached backfill for {cache_key}")
            return self.backfill_cache[cache_key]

        logger.info(
            f"Backfilling {symbol} {timeframe} "
            f"from {from_time} to {to_time}"
        )

        candles = []
        current_time = int(from_time.timestamp() * 1000)
        end_time = int(to_time.timestamp() * 1000)

        interval_ms = self._get_interval_ms(timeframe)

        # Fetch in batches
        while current_time < end_time:
            try:
                batch = await self.api.fetch_ohlcv(
                    symbol,
                    timeframe,
                    since=current_time,
                    limit=self.backfill_batch_size
                )

                if not batch:
                    break

                candles.extend(batch)

                # Move to next batch
                current_time = int(batch[-1][0]) + interval_ms

                # Rate limit protection
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Backfill failed at {current_time}: {e}")
                break

        # Cache result
        self.backfill_cache[cache_key] = candles
        logger.info(f"Backfilled {len(candles)} candles for {symbol}")

        return candles

    async def backfill_missing_candles(self, symbol: str, timeframe: str,
                                       cache: TwoLayerCache) -> int:
        """
        Identify and backfill missing candles in cache
        Compares cache contents with expected timeline
        """

        logger.info(f"Checking for missing candles in {symbol} {timeframe}")

        # Get current cache contents
        cached_candles = await cache.get_range(
            symbol, timeframe,
            datetime.now() - timedelta(days=30),
            datetime.now()
        )

        if not cached_candles:
            logger.warning(f"No cached candles for {symbol}")
            return 0

        # Find gaps
        interval_ms = self._get_interval_ms(timeframe)
        missing_ranges = []

        for i in range(len(cached_candles) - 1):
            current_time = cached_candles[i]['timestamp']
            next_time = cached_candles[i + 1]['timestamp']

            gap = (next_time - current_time).total_seconds() * 1000

            if gap > interval_ms * 1.5:  # Allow 50% variance
                missing_ranges.append((current_time, next_time))

        if not missing_ranges:
            logger.info(f"No gaps detected for {symbol}")
            return 0

        # Backfill each gap
        total_backfilled = 0
        for from_time, to_time in missing_ranges:
            backfilled = await self.backfill_gaps(
                symbol, timeframe, from_time, to_time
            )
            total_backfilled += len(backfilled)

            # Add to cache
            for candle in backfilled:
                await cache.add_candle(symbol, timeframe, candle)

        logger.info(f"Backfilled {total_backfilled} total candles")
        return total_backfilled

    def _get_interval_ms(self, timeframe: str) -> int:
        intervals = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
        }
        return intervals.get(timeframe, 60 * 1000)
```

---

## 6. Rate Limit Handling

### Pattern 8: Distributed Rate Limiter

```python
import time

class DistributedRateLimiter:
    """
    Tracks and enforces rate limits
    Supports multiple strategies: token bucket, sliding window
    """

    def __init__(self, requests_per_minute: int = 1200):
        self.rpm = requests_per_minute
        self.tokens = requests_per_minute
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self, num_tokens: int = 1) -> bool:
        """
        Try to acquire tokens
        Returns True if available, False if would exceed limit
        """

        async with self.lock:
            # Refill tokens based on elapsed time
            now = time.time()
            elapsed = now - self.last_refill
            refill_rate = self.rpm / 60  # tokens per second
            self.tokens = min(
                self.rpm,
                self.tokens + (elapsed * refill_rate)
            )
            self.last_refill = now

            if self.tokens >= num_tokens:
                self.tokens -= num_tokens
                return True

            return False

    async def wait_for_tokens(self, num_tokens: int = 1):
        """
        Wait until tokens available
        Blocking call
        """

        while not await self.acquire(num_tokens):
            # Calculate wait time
            tokens_needed = num_tokens - self.tokens
            refill_rate = self.rpm / 60
            wait_time = tokens_needed / refill_rate

            await asyncio.sleep(min(wait_time, 1.0))

    async def safe_api_call(self, api_func, *args,
                           cost: int = 1, **kwargs):
        """
        Make rate-limited API call
        Automatically waits if necessary
        """

        await self.wait_for_tokens(cost)
        return await api_func(*args, **kwargs)
```

---

## 7. Monitoring & Observability

### Pattern 9: Stream Health Monitoring

```python
from dataclasses import dataclass, field
from datetime import datetime
import statistics

@dataclass
class StreamMetrics:
    symbol: str
    timeframe: str
    messages_received: int = 0
    messages_processed: int = 0
    errors: int = 0
    backfills: int = 0
    last_message_time: Optional[datetime] = None
    connection_uptime: float = 0.0
    latencies: List[float] = field(default_factory=list)

    def get_summary(self) -> Dict:
        """Get metrics summary"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'messages_received': self.messages_received,
            'errors': self.errors,
            'error_rate': (
                self.errors / max(self.messages_received, 1) * 100
            ),
            'uptime_hours': self.connection_uptime / 3600,
            'avg_latency_ms': (
                statistics.mean(self.latencies) * 1000
                if self.latencies else 0
            ),
            'max_latency_ms': (
                max(self.latencies) * 1000
                if self.latencies else 0
            ),
        }

class StreamHealthMonitor:
    """Monitors health of streaming connections"""

    def __init__(self):
        self.metrics: Dict[str, StreamMetrics] = {}
        self.alert_thresholds = {
            'error_rate': 0.05,  # 5%
            'max_latency': 10.0,  # 10 seconds
        }

    def record_message(self, symbol: str, timeframe: str, latency: float):
        """Record received message"""
        key = f"{symbol}:{timeframe}"

        if key not in self.metrics:
            self.metrics[key] = StreamMetrics(symbol, timeframe)

        m = self.metrics[key]
        m.messages_received += 1
        m.messages_processed += 1
        m.last_message_time = datetime.now()
        m.latencies.append(latency)

        # Keep only last 100 latencies
        if len(m.latencies) > 100:
            m.latencies.pop(0)

    def record_error(self, symbol: str, timeframe: str):
        """Record error"""
        key = f"{symbol}:{timeframe}"

        if key not in self.metrics:
            self.metrics[key] = StreamMetrics(symbol, timeframe)

        self.metrics[key].errors += 1

        # Check if alert threshold exceeded
        m = self.metrics[key]
        if m.messages_received > 0:
            error_rate = m.errors / m.messages_received

            if error_rate > self.alert_thresholds['error_rate']:
                logger.warning(
                    f"High error rate for {symbol}: {error_rate * 100:.1f}%"
                )

    def record_backfill(self, symbol: str, timeframe: str):
        """Record backfill operation"""
        key = f"{symbol}:{timeframe}"

        if key in self.metrics:
            self.metrics[key].backfills += 1

    def get_health_report(self) -> Dict:
        """Generate health report for all streams"""
        return {
            key: m.get_summary()
            for key, m in self.metrics.items()
        }

    def alert_unhealthy_streams(self):
        """Log alerts for unhealthy streams"""
        for key, m in self.metrics.items():
            summary = m.get_summary()

            # Alert high latency
            if summary['avg_latency_ms'] > 5000:  # 5 seconds
                logger.warning(
                    f"High latency for {key}: "
                    f"{summary['avg_latency_ms']:.0f}ms avg"
                )

            # Alert no messages
            if m.messages_received == 0:
                logger.warning(f"No messages received for {key}")

            # Alert high error rate
            if summary['error_rate'] > 10:
                logger.error(
                    f"Critical error rate for {key}: "
                    f"{summary['error_rate']:.1f}%"
                )
```

---

## Summary Table: When to Use Each Pattern

| Pattern | Use Case | Pros | Cons |
|---------|----------|------|------|
| Keep-Alive | Idle timeout prevention | Simple, reliable | Low throughput |
| Connection Pool | Multiple symbols | Scales well | Complex |
| Two-Layer Cache | Historical + RT data | Fast + durable | Sync overhead |
| Cache Invalidation | Memory management | Prevents bloat | Configuration needed |
| Exponential Backoff | Error recovery | Reliable | Slower recovery |
| Multi-Symbol | Many subscriptions | Efficient | Resource management |
| Backfill | Gap handling | Complete data | REST API cost |
| Rate Limiter | API protection | Prevents blocks | Throughput limited |
| Health Monitor | Operations | Early warnings | CPU overhead |

---

## Quick Reference: Production Checklist

- [x] Connection keep-alive implemented
- [x] Connection pooling for concurrency limits
- [x] Two-layer cache (hot + cold)
- [x] Cache invalidation strategy
- [x] Exponential backoff for failures
- [x] Gap detection and backfilling
- [x] Multi-symbol concurrent handling
- [x] Rate limiting enforcement
- [x] Health monitoring and alerts
- [x] Error logging and recovery
- [x] Graceful shutdown procedures

