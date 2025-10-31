"""
IG WebSocket Collector

Connects to IG Lightstreamer WebSocket and streams real-time forex data.
Stores all completed candles in database for trading bot to use.

NO quota usage - runs indefinitely!
"""

import time
import sys
from datetime import datetime
from typing import Dict, List
from forex_config import ForexConfig
from forex_database import ForexDatabase

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

    def __init__(self):
        """Initialize WebSocket collector."""
        if not TRADING_IG_AVAILABLE:
            raise ImportError("trading_ig library required. Install with: pip install trading-ig")

        self.ig_service = None
        self.db = ForexDatabase()
        self.pairs = ForexConfig.FOREX_PAIRS  # Fixed: Use FOREX_PAIRS instead of PAIRS
        self.subscriptions = []

        # Statistics
        self.candles_received = 0
        self.start_time = datetime.now()

        print("="*80)
        print("IG WEBSOCKET COLLECTOR")
        print("="*80)
        print(f"\nPairs to monitor: {len(self.pairs)}")
        print(f"Timeframes: 5m, 15m")
        print(f"Storage: Database at {self.db.db_path}")

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

            # Store in database
            self.db.store_candle(pair, timeframe, candle, source='websocket')

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
