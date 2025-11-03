"""
IG WebSocket Collector

Connects to IG Lightstreamer WebSocket and streams real-time forex data.
Stores all completed candles in database for trading bot to use.

NO quota usage - runs indefinitely!
"""

import time
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from forex_config import ForexConfig
from forex_database import ForexDatabase

# Import DataHub and models
try:
    from data_hub import get_data_hub_from_env
    from market_data_models import Tick, Candle
    DATA_HUB_AVAILABLE = True
except ImportError:
    DATA_HUB_AVAILABLE = False
    print("⚠️  DataHub not available - running in legacy mode")

# Check if trading_ig is installed
try:
    from trading_ig import IGService
    from trading_ig.lightstreamer import Subscription
    TRADING_IG_AVAILABLE = True
except ImportError:
    TRADING_IG_AVAILABLE = False
    print("⚠️  trading_ig library not installed")
    print("   Install with: pip install trading-ig")


class ForexWebSocketCollector:
    """
    Real-time forex data collector using IG Lightstreamer WebSocket.

    Features:
    - Subscribes to all configured currency pairs
    - Streams 5-minute and 15-minute candles
    - Stores all candles in database
    - NO quota usage (WebSocket is unlimited)
    - Runs 24/5 during forex trading hours
    """

    def __init__(self, db_manager=None, persistence_manager=None, data_hub=None):
        """Initialize WebSocket collector.

        Args:
            db_manager: DatabaseManager instance (optional, for new PostgreSQL)
            persistence_manager: DataPersistenceManager instance (optional)
            data_hub: DataHub instance for real-time caching (optional)
        """
        if not TRADING_IG_AVAILABLE:
            raise ImportError("trading_ig library required. Install with: pip install trading-ig")

        self.ig_service = None
        self.db = ForexDatabase()  # Keep old database for backward compatibility
        self.pairs = ForexConfig.FOREX_PAIRS  # Fixed: Use FOREX_PAIRS instead of PAIRS
        self.subscriptions = []

        # New PostgreSQL persistence
        self.db_manager = db_manager
        self.persistence = persistence_manager
        self.persist_enabled = persistence_manager is not None

        # DataHub integration (try env if not provided)
        self.data_hub = data_hub
        if self.data_hub is None and DATA_HUB_AVAILABLE:
            self.data_hub = get_data_hub_from_env()

        # In-memory tick storage (for 1-minute candle aggregation)
        self.latest_ticks: Dict[str, Dict] = {}  # symbol -> {bid, ask, timestamp}
        self.forming_candles: Dict[str, Dict] = defaultdict(dict)  # symbol -> candle data

        # Statistics
        self.candles_received = 0
        self.ticks_received = 0
        self.start_time = datetime.now()

        print("="*80)
        print("IG WEBSOCKET COLLECTOR")
        print("="*80)
        print(f"\nPairs to monitor: {len(self.pairs)}")
        print(f"Timeframes: 5m, 15m")
        print(f"Storage: Database at {self.db.db_path}")
        print(f"DataHub: {'✅ Connected' if self.data_hub else '❌ Not available'}")

    def connect(self):
        """Connect to IG Lightstreamer WebSocket."""
        print("\n🔌 Connecting to IG...")

        try:
            # Create IG service
            self.ig_service = IGService(
                username=ForexConfig.IG_USERNAME,
                password=ForexConfig.IG_PASSWORD,
                api_key=ForexConfig.IG_API_KEY,
                acc_type='DEMO' if ForexConfig.IG_DEMO else 'LIVE'
            )

            # Create session
            self.ig_service.create_session()

            print("✅ Connected to IG API")
            print(f"   Account type: {'DEMO' if ForexConfig.IG_DEMO else 'LIVE'}")
            print(f"   Username: {ForexConfig.IG_USERNAME}")

        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("\nTroubleshooting:")
            print("1. Check IG_USERNAME, IG_PASSWORD, IG_API_KEY in .env")
            print("2. Verify IG account is active")
            print("3. Check IG_DEMO setting matches your account type")
            raise

    def subscribe_to_pairs(self):
        """Subscribe to all currency pairs on WebSocket."""
        print("\n📡 Subscribing to currency pairs...")

        # Subscribe to 5-minute candles
        print("\n   5-minute candles:")
        items_5m = []
        for pair in self.pairs:
            # Convert EUR_USD to IG format: CS.D.EURUSD.TODAY.IP
            epic = self._get_epic(pair)
            items_5m.append(f"CHART:{epic}:5MINUTE")

        subscription_5m = Subscription(
            mode="MERGE",
            items=items_5m,
            fields=["UTM", "OFR_OPEN", "OFR_HIGH", "OFR_LOW", "OFR_CLOSE", "CONS_END"]
        )

        subscription_5m.addlistener(self._on_5m_candle)

        try:
            self.ig_service.ls_client.subscribe(subscription_5m)
            self.subscriptions.append(subscription_5m)
            print(f"      ✅ Subscribed to {len(self.pairs)} pairs (5m)")
        except Exception as e:
            print(f"      ❌ Subscription failed: {e}")

        # Subscribe to 15-minute candles
        print("\n   15-minute candles:")
        items_15m = []
        for pair in self.pairs:
            epic = self._get_epic(pair)
            items_15m.append(f"CHART:{epic}:15MINUTE")

        subscription_15m = Subscription(
            mode="MERGE",
            items=items_15m,
            fields=["UTM", "OFR_OPEN", "OFR_HIGH", "OFR_LOW", "OFR_CLOSE", "CONS_END"]
        )

        subscription_15m.addlistener(self._on_15m_candle)

        try:
            self.ig_service.ls_client.subscribe(subscription_15m)
            self.subscriptions.append(subscription_15m)
            print(f"      ✅ Subscribed to {len(self.pairs)} pairs (15m)")
        except Exception as e:
            print(f"      ❌ Subscription failed: {e}")

        print(f"\n✅ WebSocket streaming active!")
        print(f"   Monitoring: {len(self.pairs)} pairs × 2 timeframes = {len(self.pairs)*2} streams")
        print(f"   NO quota usage - unlimited streaming! 📈")

    def _get_epic(self, pair: str) -> str:
        """Convert pair to IG EPIC format."""
        if pair in ForexConfig.IG_EPIC_MAP:
            return ForexConfig.IG_EPIC_MAP[pair]

        # Fallback: construct EPIC
        clean_pair = pair.replace("_", "")
        return f"CS.D.{clean_pair}.TODAY.IP"

    def _on_5m_candle(self, item_update):
        """Handle 5-minute candle updates."""
        self._process_candle(item_update, timeframe='5')

    def _on_15m_candle(self, item_update):
        """Handle 15-minute candle updates."""
        self._process_candle(item_update, timeframe='15')

    def _process_candle(self, item_update, timeframe: str):
        """
        Process and store a completed candle.

        Args:
            item_update: Lightstreamer update object
            timeframe: '5' or '15' minutes
        """
        try:
            # Extract item name (e.g., "CHART:CS.D.EURUSD.TODAY.IP:5MINUTE")
            item_name = item_update.get('name', '')

            # Parse EPIC from item name
            parts = item_name.split(':')
            if len(parts) < 2:
                return

            epic = parts[1]

            # Convert EPIC back to pair format
            pair = self._epic_to_pair(epic)
            if not pair:
                return

            # Check if candle is consolidated (complete)
            cons_end = item_update.get('CONS_END')
            if cons_end != '1':
                return  # Candle still forming, skip

            # Extract OHLC data
            timestamp_str = item_update.get('UTM', '')
            open_price = item_update.get('OFR_OPEN')
            high_price = item_update.get('OFR_HIGH')
            low_price = item_update.get('OFR_LOW')
            close_price = item_update.get('OFR_CLOSE')

            # Validate data
            if not all([timestamp_str, open_price, high_price, low_price, close_price]):
                return

            # Parse timestamp
            try:
                timestamp = int(timestamp_str) / 1000  # Convert ms to seconds
            except:
                timestamp = int(datetime.now().timestamp())

            # Create candle dict
            candle = {
                'timestamp': timestamp,
                'open': float(open_price),
                'high': float(high_price),
                'low': float(low_price),
                'close': float(close_price),
                'volume': 0.0  # IG doesn't provide volume for forex
            }

            # Store in old database (for backward compatibility)
            self.db.store_candle(pair, timeframe, candle, source='websocket')

            # Save tick to new PostgreSQL database (using close as representative tick)
            if self.persist_enabled:
                try:
                    # Create tick from candle close
                    bid = float(close_price) - 0.0001  # Approximate bid (spread ~1 pip)
                    ask = float(close_price) + 0.0001  # Approximate ask

                    asyncio.create_task(self.persistence.save_ig_tick(
                        symbol=pair,
                        timestamp=datetime.fromtimestamp(timestamp),
                        bid=bid,
                        ask=ask
                    ))
                except Exception as e:
                    print(f"⚠️  Failed to save IG tick: {e}")

            # Update statistics
            self.candles_received += 1

            # Log (but not too verbose)
            if self.candles_received % 10 == 0:
                runtime = (datetime.now() - self.start_time).total_seconds() / 60
                rate = self.candles_received / runtime if runtime > 0 else 0
                print(f"📊 Candles received: {self.candles_received:,} ({rate:.1f}/min)")
            else:
                timestamp_str = datetime.fromtimestamp(timestamp).strftime('%H:%M')
                print(f"   {pair} {timeframe}m @ {timestamp_str}: {close_price}")

        except Exception as e:
            print(f"⚠️  Error processing candle: {e}")

    def _epic_to_pair(self, epic: str) -> str:
        """Convert IG EPIC back to pair format."""
        # Reverse lookup in EPIC map
        for pair, pair_epic in ForexConfig.IG_EPIC_MAP.items():
            if pair_epic == epic:
                return pair

        # Fallback: parse EPIC
        # CS.D.EURUSD.TODAY.IP -> EUR_USD
        parts = epic.split('.')
        if len(parts) >= 3:
            currency_str = parts[2]  # EURUSD
            if len(currency_str) == 6:
                return f"{currency_str[:3]}_{currency_str[3:]}"

        return None

    def print_status(self):
        """Print collector status."""
        runtime = (datetime.now() - self.start_time).total_seconds() / 60

        print("\n" + "="*80)
        print("WEBSOCKET COLLECTOR STATUS")
        print("="*80)
        print(f"   Runtime: {runtime:.1f} minutes")
        print(f"   Candles received: {self.candles_received:,}")
        print(f"   Ticks received: {self.ticks_received:,}")
        print(f"   Rate: {self.candles_received/runtime:.1f} candles/min" if runtime > 0 else "   Rate: N/A")

        # Database stats
        db_stats = self.db.get_statistics()
        print(f"\n📊 Database Statistics:")
        print(f"   Total candles: {db_stats['total_candles']:,}")
        print(f"   Pairs: {db_stats['unique_pairs']}")
        print(f"   Date range: {db_stats['oldest_candle']} to {db_stats['newest_candle']}")

        if 'sources' in db_stats:
            print(f"\n   By source:")
            for source, count in db_stats['sources'].items():
                print(f"      {source}: {count:,}")

        print("="*80)

    # ========================================================================
    # RETRIEVAL METHODS (for UnifiedDataFetcher compatibility)
    # ========================================================================

    def get_latest_tick(self, symbol: str) -> Optional[Dict]:
        """
        Get latest tick for a symbol.

        Args:
            symbol: Trading pair (EUR_USD, GBP_USD, etc.)

        Returns:
            Dict with 'bid', 'ask', 'mid', 'spread', 'timestamp'
        """
        return self.latest_ticks.get(symbol)

    def get_latest_candles(self, symbol: str, timeframe: str = "1m", bars: int = 100) -> Optional[List]:
        """
        Get latest candles from DataHub (if available).

        Args:
            symbol: Trading pair
            timeframe: Currently only supports "1m"
            bars: Number of candles to return

        Returns:
            List of candle dicts or None
        """
        if not self.data_hub:
            return None

        try:
            candles = self.data_hub.get_latest_candles(symbol, limit=bars)
            # Convert Candle objects to dicts for compatibility
            return [
                {
                    'timestamp': c.timestamp,
                    'open': c.open,
                    'high': c.high,
                    'low': c.low,
                    'close': c.close,
                    'volume': c.volume
                }
                for c in candles
            ]
        except Exception as e:
            print(f"⚠️  Failed to get candles from DataHub: {e}")
            return None

    # ========================================================================
    # TICK PROCESSING (for DataHub updates)
    # ========================================================================

    def _process_tick_update(self, item_update):
        """
        Process tick update and push to DataHub.

        This handles real-time bid/ask updates for spread monitoring
        and 1-minute candle aggregation.
        """
        try:
            # Extract item name
            item_name = item_update.get('name', '')
            parts = item_name.split(':')
            if len(parts) < 2:
                return

            epic = parts[1]
            pair = self._epic_to_pair(epic)
            if not pair:
                return

            # Extract bid/ask
            bid = item_update.get('BID')
            ask = item_update.get('OFFER')  # IG uses OFFER for ask

            if not bid or not ask:
                return

            bid = float(bid)
            ask = float(ask)
            mid = (bid + ask) / 2.0

            # Calculate spread in pips
            pip_value = 0.01 if 'JPY' in pair else 0.0001
            spread = (ask - bid) / pip_value

            timestamp = datetime.utcnow()

            # Store in memory
            self.latest_ticks[pair] = {
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'spread': spread,
                'timestamp': timestamp
            }

            self.ticks_received += 1

            # Push to DataHub if available
            if self.data_hub:
                try:
                    tick = Tick(
                        symbol=pair,
                        bid=bid,
                        ask=ask,
                        mid=mid,
                        spread=spread,
                        timestamp=timestamp
                    )
                    self.data_hub.update_tick(tick)
                except Exception as e:
                    if self.ticks_received % 100 == 0:  # Log occasionally
                        print(f"⚠️  DataHub tick update failed: {e}")

            # Aggregate into 1-minute candles
            self._aggregate_tick_to_candle(pair, mid, timestamp)

        except Exception as e:
            print(f"⚠️  Error processing tick: {e}")

    def _aggregate_tick_to_candle(self, symbol: str, price: float, timestamp: datetime):
        """
        Aggregate ticks into 1-minute candles.

        Args:
            symbol: Trading pair
            price: Mid price
            timestamp: Tick timestamp
        """
        # Get current minute boundary
        minute_start = timestamp.replace(second=0, microsecond=0)

        # Initialize or update forming candle
        if symbol not in self.forming_candles or self.forming_candles[symbol].get('timestamp') != minute_start:
            # New candle - finalize previous if exists
            if symbol in self.forming_candles and self.forming_candles[symbol]:
                self._finalize_candle(symbol)

            # Start new candle
            self.forming_candles[symbol] = {
                'timestamp': minute_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'tick_count': 1
            }
        else:
            # Update existing candle
            candle = self.forming_candles[symbol]
            candle['high'] = max(candle['high'], price)
            candle['low'] = min(candle['low'], price)
            candle['close'] = price
            candle['tick_count'] += 1

    def _finalize_candle(self, symbol: str):
        """
        Finalize a completed 1-minute candle and push to DataHub.

        Args:
            symbol: Trading pair
        """
        if symbol not in self.forming_candles:
            return

        candle_data = self.forming_candles[symbol]

        # Create Candle object
        candle = Candle(
            symbol=symbol,
            timestamp=candle_data['timestamp'],
            open=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close'],
            volume=float(candle_data.get('tick_count', 0))  # Use tick count as proxy
        )

        # Push to DataHub
        if self.data_hub:
            try:
                self.data_hub.update_candle_1m(candle)
            except Exception as e:
                print(f"⚠️  DataHub candle update failed for {symbol}: {e}")

        # Also save to database (legacy)
        try:
            self.db.store_candle(
                symbol, '1',
                {
                    'timestamp': candle_data['timestamp'].timestamp(),
                    'open': candle_data['open'],
                    'high': candle_data['high'],
                    'low': candle_data['low'],
                    'close': candle_data['close'],
                    'volume': candle_data.get('tick_count', 0)
                },
                source='websocket_tick_aggregated'
            )
        except Exception as e:
            print(f"⚠️  Database candle save failed: {e}")

    def run_forever(self):
        """Keep collector running indefinitely."""
        print("\n" + "="*80)
        print("STARTING CONTINUOUS COLLECTION")
        print("="*80)
        print("\nWebSocket collector is now running...")
        print("Press Ctrl+C to stop")
        print("="*80)

        try:
            # Connect and subscribe
            self.connect()
            self.subscribe_to_pairs()

            # Print status every 5 minutes
            last_status = time.time()
            status_interval = 300  # 5 minutes

            # Keep alive
            while True:
                time.sleep(10)

                # Periodic status update
                if time.time() - last_status > status_interval:
                    self.print_status()
                    last_status = time.time()

        except KeyboardInterrupt:
            print("\n\n🛑 Stopping collector...")
            self.print_status()

            # Cleanup
            try:
                if self.ig_service:
                    self.ig_service.logout()
                    print("✅ Logged out from IG")
            except:
                pass

            print("\n👋 Collector stopped.")

        except Exception as e:
            print(f"\n❌ Collector error: {e}")
            print("\nCollector will restart automatically if run as daemon.")
            sys.exit(1)


def main():
    """Main entry point."""
    print("\n" + "="*80)
    print("IG WEBSOCKET COLLECTOR - REAL-TIME FOREX DATA")
    print("="*80)

    # Check configuration
    if not ForexConfig.IG_API_KEY:
        print("\n❌ Error: IG_API_KEY not set in .env")
        print("   Add: IG_API_KEY=your_key_here")
        sys.exit(1)

    if not ForexConfig.IG_USERNAME:
        print("\n❌ Error: IG_USERNAME not set in .env")
        print("   Add: IG_USERNAME=your_username")
        sys.exit(1)

    if not ForexConfig.IG_PASSWORD:
        print("\n❌ Error: IG_PASSWORD not set in .env")
        print("   Add: IG_PASSWORD=your_password")
        sys.exit(1)

    # Create and run collector
    try:
        collector = ForexWebSocketCollector()
        collector.run_forever()
    except Exception as e:
        print(f"\n❌ Failed to start collector: {e}")
        sys.exit(1)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    main()
