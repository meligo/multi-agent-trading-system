# Provider-Specific WebSocket Configuration Guide

## 1. IG Markets (Lightstreamer Protocol)

### Connection Details

```python
# Configuration for IG Markets WebSocket
IG_CONFIG = {
    'api_key': 'YOUR_API_KEY',
    'cst_token': None,  # Received after login
    'security_token': None,  # Received after login
    'api_url': 'https://demo-api.ig.com/gateway/deal',
    'stream_url': 'https://demo-apd.marketdatasystems.com',
    'timeout': 30,
    'max_connections': 40,  # IG limit per account
}

# Lightstreamer connection setup
LIGHTSTREAMER_CONFIG = {
    'controlLink': 'https://demo-apd.marketdatasystems.com',
    'dataLink': 'https://demo-apd.marketdatasystems.com',
    'pollingInterval': 0,  # No polling, WebSocket only
    'reverseHeartbeatInterval': 5000,  # Keep-alive every 5s
    'transportTimeout': 30000,
}
```

### Implementation Example

```python
import requests
from lightstreamer_client import LightstreamerClient, Subscription, ConnectionDetails

class IGMarketsConnection:
    def __init__(self, api_key, username, password):
        self.api_key = api_key
        self.username = username
        self.password = password
        self.cst_token = None
        self.security_token = None
        self.client = None

    async def authenticate(self):
        """Login to IG Markets and get tokens"""
        response = requests.post(
            'https://demo-api.ig.com/gateway/deal/session',
            headers={
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            },
            json={
                'identifier': self.username,
                'password': self.password
            }
        )

        if response.status_code == 200:
            data = response.json()
            self.cst_token = response.headers['CST']
            self.security_token = response.headers['X-SECURITY-TOKEN']
            print(f"Authenticated. Account ID: {data['accountId']}")
            return True

        raise Exception(f"Authentication failed: {response.text}")

    def setup_stream(self):
        """Setup Lightstreamer connection"""
        # Connection details
        connection_details = ConnectionDetails()
        connection_details.user = self.username
        connection_details.server_address = "https://demo-apd.marketdatasystems.com"
        connection_details.adapter_set = "DEFAULT"

        # Create client
        self.client = LightstreamerClient()
        self.client.connection_details = connection_details

        # Add listener
        self.client.add_listener(ConnectionListener(self))

        # Connect
        self.client.connect()

    def subscribe_to_prices(self, symbols):
        """Subscribe to real-time price updates"""
        subscription = Subscription(
            mode="MERGE",
            items=[f"CS.D.{symbol}.CFD.IP" for symbol in symbols],
            fields=["BID", "ASK", "CHANGE", "CHANGE_PCT", "UPDATE_TIME"]
        )

        subscription.add_listener(PriceListener(self))
        self.client.subscribe(subscription)

        return subscription

    def unsubscribe(self, subscription):
        """Unsubscribe from updates"""
        self.client.unsubscribe(subscription)

class PriceListener:
    def __init__(self, connection):
        self.connection = connection

    def on_item_update(self, update):
        """Called when price update received"""
        symbol = update.get_value("BID")
        bid = update.get_value("BID")
        ask = update.get_value("ASK")
        timestamp = datetime.now()

        print(f"[{timestamp}] {symbol} - Bid: {bid}, Ask: {ask}")

class ConnectionListener:
    def __init__(self, connection):
        self.connection = connection

    def on_connection_established(self):
        print("Connected to Lightstreamer")

    def on_connection_closed(self):
        print("Disconnected from Lightstreamer")

# Usage
async def example_ig_streaming():
    ig = IGMarketsConnection(
        api_key='YOUR_KEY',
        username='YOUR_USERNAME',
        password='YOUR_PASSWORD'
    )

    await ig.authenticate()
    ig.setup_stream()

    # Subscribe to forex pairs
    subscription = ig.subscribe_to_prices(['EURUSD', 'GBPUSD', 'USDJPY'])

    # Stream for 5 minutes
    await asyncio.sleep(300)

    ig.unsubscribe(subscription)
    ig.client.disconnect()
```

### Rate Limits & Constraints

- **Max Connections:** 40 per account
- **Update Frequency:** Real-time (subsecond)
- **Symbols per Connection:** Multiple on single stream
- **Data Cost:** Included with IG account
- **Keep-Alive:** Required every 5 seconds (auto-handled by Lightstreamer)

---

## 2. Finnhub WebSocket API

### Connection Details

```python
FINNHUB_CONFIG = {
    'api_key': 'YOUR_FINNHUB_API_KEY',
    'websocket_url': 'wss://ws.finnhub.io?token=YOUR_TOKEN',
    'max_symbols': 50,  # Recommended limit per connection
    'reconnect_interval': 5,
    'supported_types': [
        'trade',        # Real-time trades
        'quote',        # Level 1 quotes
        'candle',       # OHLC updates
    ]
}
```

### Implementation Example

```python
import websocket
import json
import threading

class FinnhubWebSocket:
    def __init__(self, api_key):
        self.api_key = api_key
        self.ws = None
        self.subscriptions = set()

    def on_message(self, ws, message):
        """Handle incoming messages"""
        data = json.loads(message)

        if 'data' in data:
            for item in data['data']:
                self.handle_market_data(item)

    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("Connection closed")

    def on_open(self, ws):
        print("Connected to Finnhub")

        # Resubscribe to previous symbols
        for symbol in self.subscriptions:
            self.subscribe(symbol)

    def handle_market_data(self, data):
        """Process market data update"""
        if data['type'] == 'trade':
            print(
                f"Trade: {data['s']} @ {data['p']} "
                f"(qty: {data['v']}) at {data['t']}"
            )
        elif data['type'] == 'quote':
            print(
                f"Quote: {data['s']} - "
                f"Bid: {data.get('bp')} Ask: {data.get('ap')}"
            )

    def subscribe(self, symbol, data_type='trade'):
        """Subscribe to symbol"""
        message = {
            'type': 'subscribe',
            'symbol': symbol
        }

        if self.ws and self.ws.sock:
            self.ws.send(json.dumps(message))
            self.subscriptions.add(symbol)
            print(f"Subscribed to {symbol}")

    def unsubscribe(self, symbol):
        """Unsubscribe from symbol"""
        message = {
            'type': 'unsubscribe',
            'symbol': symbol
        }

        if self.ws and self.ws.sock:
            self.ws.send(json.dumps(message))
            self.subscriptions.discard(symbol)
            print(f"Unsubscribed from {symbol}")

    def connect(self):
        """Establish WebSocket connection"""
        url = f"wss://ws.finnhub.io?token={self.api_key}"

        self.ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        # Run in thread
        thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={'ping_interval': 30}
        )
        thread.daemon = True
        thread.start()

    def close(self):
        """Close connection"""
        if self.ws:
            self.ws.close()

# Usage
finnhub = FinnhubWebSocket('YOUR_API_KEY')
finnhub.connect()

# Wait for connection
time.sleep(2)

# Subscribe to symbols
finnhub.subscribe('EURUSD')
finnhub.subscribe('GBPUSD')
finnhub.subscribe('AAPL')

# Keep running
time.sleep(60)

finnhub.close()
```

### Message Types

```python
# Trade message
{
    'type': 'trade',
    's': 'EURUSD',      # Symbol
    'p': 1.0950,        # Price
    'v': 1500000,       # Volume
    't': 1234567890000  # Timestamp
}

# Quote message (Level 1)
{
    'type': 'quote',
    's': 'EURUSD',
    'bp': 1.0949,       # Bid price
    'bs': 10000000,     # Bid size
    'ap': 1.0951,       # Ask price
    'as': 10000000,     # Ask size
    't': 1234567890000
}

# Candle message (OHLC)
{
    'type': 'candle',
    's': 'EURUSD',
    'o': 1.0945,        # Open
    'h': 1.0960,        # High
    'l': 1.0940,        # Low
    'c': 1.0955,        # Close
    'v': 15000000,      # Volume
    't': 1234567890     # Unix timestamp
}
```

### Rate Limits

- **Standard Plan:** 60 WebSocket connections max
- **Premium Plan:** Higher limits available
- **Symbols per Connection:** Up to 50 recommended
- **Message Rate:** Real-time, no throttling
- **Data Cost:** Included with subscription

---

## 3. Coinbase Exchange API

### Connection Details

```python
COINBASE_CONFIG = {
    'api_key': 'YOUR_API_KEY',
    'api_secret': 'YOUR_SECRET',
    'api_url': 'https://api.exchange.coinbase.com',
    'websocket_url': 'wss://ws-feed.exchange.coinbase.com',
    'sandbox_url': 'wss://ws-feed-sandbox.exchange.coinbase.com',
}
```

### Implementation Example

```python
import hmac
import hashlib
import base64
import time
import json
from datetime import datetime
import websocket

class CoinbaseWebSocket:
    def __init__(self, api_key, api_secret, api_passphrase, use_sandbox=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.use_sandbox = use_sandbox

        self.ws_url = (
            'wss://ws-feed-sandbox.exchange.coinbase.com'
            if use_sandbox else
            'wss://ws-feed.exchange.coinbase.com'
        )

        self.ws = None
        self.subscriptions = set()

    def generate_auth_headers(self, timestamp):
        """Generate authentication headers for WebSocket"""
        message = f"{timestamp}GET/users/self/verify"
        auth_bytes = message.encode('ascii')
        signature = hmac.new(
            base64.b64decode(self.api_secret),
            auth_bytes,
            hashlib.sha256
        )
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        return {
            'signature': signature_b64,
            'key': self.api_key,
            'passphrase': self.api_passphrase,
            'timestamp': timestamp
        }

    def on_message(self, ws, message):
        """Handle incoming messages"""
        data = json.loads(message)

        if data['type'] == 'match':
            self.handle_trade(data)
        elif data['type'] == 'heartbeat':
            pass  # Just a keep-alive
        elif data['type'] == 'snapshot':
            self.handle_snapshot(data)
        elif data['type'] == 'l2update':
            self.handle_order_book_update(data)

    def handle_trade(self, data):
        """Process trade data"""
        print(
            f"Trade: {data['product_id']} "
            f"@ ${data['price']} (qty: {data['last_size']}) "
            f"- {data['side']}"
        )

    def handle_snapshot(self, data):
        """Process order book snapshot"""
        print(f"Order book snapshot for {data['product_id']}")

    def handle_order_book_update(self, data):
        """Process order book update"""
        for change in data['changes']:
            side, price, size = change
            print(f"Book update: {side} @ {price} x {size}")

    def subscribe(self, product_ids):
        """Subscribe to product channels"""
        timestamp = str(time.time())
        auth_headers = self.generate_auth_headers(timestamp)

        subscribe_message = {
            'type': 'subscribe',
            'product_ids': product_ids,
            'channels': [
                'matches',           # Trade messages
                'level2',            # Order book updates
                'ticker',            # Ticker updates
                'heartbeat'          # Keep-alive
            ],
            'signature': auth_headers['signature'],
            'key': auth_headers['key'],
            'passphrase': auth_headers['passphrase'],
            'timestamp': auth_headers['timestamp']
        }

        self.ws.send(json.dumps(subscribe_message))
        self.subscriptions.update(product_ids)

    def on_open(self, ws):
        print("Connected to Coinbase WebSocket")

        # Subscribe to products
        self.subscribe(['BTC-USD', 'ETH-USD', 'EURUSD-USD'])

    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("Connection closed")

    def connect(self):
        """Establish WebSocket connection"""
        websocket.enableTrace(False)

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self.ws.run_forever(ping_interval=30)

    def close(self):
        """Close connection"""
        if self.ws:
            self.ws.close()

# Usage
cb = CoinbaseWebSocket(
    api_key='YOUR_KEY',
    api_secret='YOUR_SECRET',
    api_passphrase='YOUR_PASSPHRASE',
    use_sandbox=True
)

cb.connect()
```

### Supported Products

```python
# Common forex pairs on Coinbase
FOREX_PRODUCTS = [
    'EUR-USD',
    'GBP-USD',
    'JPY-USD',
    'AUD-USD',
    'CAD-USD',
    'CHF-USD',
    'CNY-USD',
    'INR-USD',
    'MXN-USD',
    'SGD-USD',
    'HKD-USD',
    'NOK-USD',
    'SEK-USD',
    'NZD-USD'
]
```

### Rate Limits

- **WebSocket Connections:** Multiple concurrent allowed
- **Message Frequency:** Real-time
- **Products per Subscribe:** Unlimited
- **Channels:** Multiple channels per subscription
- **Data Cost:** Free for basic market data

---

## 4. CCXT Pro (Multi-Exchange)

### Configuration for Multiple Exchanges

```python
import ccxt.pro

# Generic CCXT Pro configuration
CCXT_CONFIG = {
    'binance': {
        'enableRateLimit': True,
        'options': {
            'tradesLimit': 1000,
            'OHLCVLimit': 1000,
            'ordersLimit': 1000,
            'newUpdates': False,
        }
    },
    'kraken': {
        'enableRateLimit': True,
        'options': {
            'tradesLimit': 1000,
            'OHLCVLimit': 1000,
        }
    },
    'coinbase': {
        'enableRateLimit': True,
        'options': {
            'tradesLimit': 1000,
            'OHLCVLimit': 1000,
        }
    },
    'kucoin': {
        'enableRateLimit': True,
        'options': {
            'tradesLimit': 1000,
            'OHLCVLimit': 1000,
        }
    }
}

class CCXTProStreamer:
    def __init__(self, exchange_name='binance'):
        exchange_config = CCXT_CONFIG.get(exchange_name, {})
        self.exchange = getattr(ccxt.pro, exchange_name)(exchange_config)

    async def stream_ohlcv(self, symbol, timeframe='1m'):
        """Stream OHLCV candles"""
        while True:
            try:
                if self.exchange.has['watchOHLCV']:
                    candles = await self.exchange.watch_ohlcv(
                        symbol,
                        timeframe
                    )

                    for candle in candles:
                        yield candle

                else:
                    # Watch trades and build OHLCV locally
                    trades = await self.exchange.watch_trades(symbol)
                    ohlcv = self.exchange.build_ohlcvc(trades, timeframe)

                    for candle in ohlcv:
                        yield candle

            except Exception as e:
                print(f"Stream error: {e}")
                await asyncio.sleep(5)

    async def stream_orderbook(self, symbol, limit=20):
        """Stream order book updates"""
        while True:
            try:
                if self.exchange.has['watchOrderBook']:
                    orderbook = await self.exchange.watch_order_book(
                        symbol,
                        limit
                    )

                    yield orderbook

            except Exception as e:
                print(f"Order book stream error: {e}")
                await asyncio.sleep(5)

    async def stream_trades(self, symbol):
        """Stream individual trades"""
        while True:
            try:
                if self.exchange.has['watchTrades']:
                    trades = await self.exchange.watch_trades(symbol)

                    for trade in trades:
                        yield trade

            except Exception as e:
                print(f"Trade stream error: {e}")
                await asyncio.sleep(5)

    async def close(self):
        await self.exchange.close()

# Usage
async def main():
    streamer = CCXTProStreamer('binance')

    async for candle in streamer.stream_ohlcv('BTC/USDT', '1m'):
        print(f"Candle: {candle}")

    await streamer.close()

asyncio.run(main())
```

### Supported Exchanges (WebSocket)

```python
CCXT_PRO_EXCHANGES = [
    'binance', 'binanceusdm', 'binancecoinm',
    'kraken', 'coinbase', 'kucoin', 'kucoinfutures',
    'bybit', 'okx', 'deribit', 'gate', 'htx',
    'bitfinex', 'bitmex', 'bitget', 'mexc', 'phemex',
    'upbit', 'bithumb', 'bitmart', 'blofin',
    'alpaca', 'woo', 'paradex', 'hyperliquid'
]
```

---

## Comparison Table: Provider Selection

| Provider | Best For | Max Connections | Latency | Cost | Setup Complexity |
|----------|----------|-----------------|---------|------|------------------|
| **IG Markets** | Professional forex | 40 | Sub-100ms | Included | Medium |
| **Finnhub** | Stock + forex data | 60 | 100-500ms | Subscription | Low |
| **Coinbase** | Crypto + forex | Unlimited | 50-200ms | Free | Low |
| **CCXT Pro** | Multi-exchange | Varies | 100-500ms | Free | High |

---

## Migration Checklist: REST to WebSocket

### Phase 1: Setup (Week 1)
- [ ] Choose provider(s)
- [ ] Get API credentials
- [ ] Test connection in sandbox/demo
- [ ] Implement connection management
- [ ] Set up logging/monitoring

### Phase 2: Bootstrap (Week 2)
- [ ] Fetch 30 days historical data (REST)
- [ ] Store in cache (Redis)
- [ ] Store in database (TimescaleDB)
- [ ] Implement TTL cleanup

### Phase 3: Streaming (Week 3)
- [ ] Connect to WebSocket
- [ ] Stream new candles
- [ ] Implement gap detection
- [ ] Implement backfill logic

### Phase 4: Optimization (Week 4)
- [ ] Tune cache settings
- [ ] Monitor latency/errors
- [ ] Optimize database queries
- [ ] Load test with multiple symbols

---

## Troubleshooting Guide

### Common Issues & Solutions

**Issue: Connection drops frequently**
```python
# Solution: Increase keep-alive frequency
connection_config['keep_alive_interval'] = 10  # From 30 seconds

# Implement exponential backoff
backoff = 0.1
while connection_failed:
    try:
        await connect()
        backoff = 0.1
    except:
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)
```

**Issue: Missing candles / data gaps**
```python
# Solution: Detect and backfill gaps
def detect_gaps(candles, expected_interval):
    gaps = []
    for i in range(len(candles) - 1):
        current_time = candles[i][0]
        next_time = candles[i+1][0]
        gap = (next_time - current_time)

        if gap > expected_interval * 1.5:
            gaps.append((current_time, next_time))

    return gaps

# Backfill detected gaps
for from_time, to_time in gaps:
    await backfill_via_rest_api(from_time, to_time)
```

**Issue: High memory usage**
```python
# Solution: Implement aggressive TTL cleanup
async def cleanup_cache():
    cutoff = now() - timedelta(days=30)

    deleted = await db.delete_many({
        'timestamp': {'$lt': cutoff}
    })

    print(f"Cleaned {deleted} old records")
```

