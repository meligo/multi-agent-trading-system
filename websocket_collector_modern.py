#!/usr/bin/env python3
"""
IG WebSocket Collector (Modern API)

Uses IGStreamService + StreamingManager for real-time tick data.
Aggregates ticks into 1-minute candles for scalping.
"""

import time
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from collections import defaultdict
from forex_config import ForexConfig

# DataHub integration
try:
    from data_hub import get_data_hub_from_env
    from market_data_models import Tick, Candle
    DATA_HUB_AVAILABLE = True
except ImportError:
    DATA_HUB_AVAILABLE = False
    print("⚠️  DataHub not available")

# Modern trading_ig API
try:
    from trading_ig import IGService, IGStreamService
    from trading_ig.streamer.manager import StreamingManager
    TRADING_IG_AVAILABLE = True
except ImportError:
    TRADING_IG_AVAILABLE = False
    print("❌ trading_ig library not available")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModernWebSocketCollector:
    """
    Modern WebSocket collector using IGStreamService.

    Subscribes to TICK data and aggregates into 1-minute candles.
    """

    def __init__(self, data_hub=None):
        """Initialize collector."""
        if not TRADING_IG_AVAILABLE:
            raise ImportError("trading_ig required")

        # Get pairs from config (use scalping pairs if available)
        try:
            from scalping_config import SCALPING_PAIRS
            self.pairs = SCALPING_PAIRS  # Just 3 pairs for scalping
            logger.info(f"Using scalping pairs: {self.pairs}")
        except ImportError:
            self.pairs = ForexConfig.FOREX_PAIRS[:3]  # Limit to 3 pairs
            logger.info(f"Using first 3 forex pairs: {self.pairs}")

        # IG Services
        self.ig_service = None
        self.ig_stream = None
        self.stream_manager = None

        # DataHub
        self.data_hub = data_hub
        if self.data_hub is None and DATA_HUB_AVAILABLE:
            try:
                self.data_hub = get_data_hub_from_env()
                logger.info("✅ DataHub connected")
            except Exception as e:
                logger.warning(f"⚠️  DataHub not available: {e}")

        # Tick aggregation for 1-minute candles
        self.forming_candles: Dict[str, Dict] = {}
        self.latest_ticks: Dict[str, Dict] = {}

        # Statistics
        self.ticks_received = 0
        self.candles_completed = 0
        self.start_time = datetime.now()

    def connect(self):
        """Connect to IG streaming API."""
        logger.info("🔌 Connecting to IG...")

        try:
            # Create IG service
            self.ig_service = IGService(
                username=ForexConfig.IG_USERNAME,
                password=ForexConfig.IG_PASSWORD,
                api_key=ForexConfig.IG_API_KEY,
                acc_type='DEMO' if ForexConfig.IG_DEMO else 'LIVE',
                acc_number=ForexConfig.IG_ACC_NUMBER
            )

            # Create stream service
            self.ig_stream = IGStreamService(self.ig_service)
            self.ig_stream.create_session(version="2")

            # Create streaming manager
            self.stream_manager = StreamingManager(self.ig_stream)

            logger.info("✅ Connected to IG API")
            logger.info(f"   Account: {'DEMO' if ForexConfig.IG_DEMO else 'LIVE'}")
            logger.info(f"   Username: {ForexConfig.IG_USERNAME}")

        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            logger.error("Check: IG_USERNAME, IG_PASSWORD, IG_API_KEY in .env")
            raise

    def subscribe_to_pairs(self):
        """Subscribe to tick data for all pairs."""
        logger.info(f"📡 Subscribing to {len(self.pairs)} pairs...")

        for pair in self.pairs:
            try:
                epic = self._get_epic(pair)

                # Subscribe to tick data
                self.stream_manager.start_tick_subscription(epic)
                logger.info(f"   ✅ {pair} ({epic})")

            except Exception as e:
                logger.error(f"   ❌ {pair} subscription failed: {e}")

        logger.info("✅ All subscriptions active!")
        logger.info(f"   {len(self.pairs)} pairs × TICK data = Real-time streaming")

    def _get_epic(self, pair: str) -> str:
        """Convert pair to IG EPIC format."""
        if pair in ForexConfig.IG_EPIC_MAP:
            return ForexConfig.IG_EPIC_MAP[pair]

        # Fallback: construct EPIC
        clean_pair = pair.replace("_", "")
        return f"CS.D.{clean_pair}.TODAY.IP"

    def _epic_to_pair(self, epic: str) -> Optional[str]:
        """Convert EPIC back to pair format."""
        # Reverse lookup
        for pair, pair_epic in ForexConfig.IG_EPIC_MAP.items():
            if pair_epic == epic:
                return pair

        # Fallback: parse EPIC (CS.D.EURUSD.TODAY.IP -> EUR_USD)
        parts = epic.split('.')
        if len(parts) >= 3:
            currency_str = parts[2]  # EURUSD
            if len(currency_str) == 6:
                return f"{currency_str[:3]}_{currency_str[3:]}"

        return None

    def process_ticks(self):
        """Process tick data and aggregate into 1-minute candles."""
        logger.info("⚙️  Starting tick processing loop...")

        last_status = time.time()
        status_interval = 60  # Print status every 60 seconds

        try:
            while True:
                for pair in self.pairs:
                    try:
                        epic = self._get_epic(pair)
                        ticker = self.stream_manager.ticker(epic)

                        # Get latest tick data
                        if ticker and hasattr(ticker, 'bid') and hasattr(ticker, 'offer'):
                            bid = float(ticker.bid) if ticker.bid else None
                            ask = float(ticker.offer) if ticker.offer else None

                            if bid and ask:
                                self._process_tick(pair, bid, ask)

                    except Exception as e:
                        if self.ticks_received % 100 == 0:  # Log occasionally
                            logger.warning(f"⚠️  Error processing {pair}: {e}")

                # Periodic status
                if time.time() - last_status > status_interval:
                    self._print_status()
                    last_status = time.time()

                # Small sleep to avoid hammering CPU
                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("\n🛑 Stopping collector...")
            self._print_status()

    def _process_tick(self, pair: str, bid: float, ask: float):
        """Process a single tick and aggregate into candles."""
        mid = (bid + ask) / 2.0
        timestamp = datetime.utcnow()

        # Calculate spread in pips
        # IG quotes prices in different formats depending on pair:
        # - EUR/USD: scaled format (11514.9 = 1.15149), 1 unit = 0.1 pips
        # - GBP/USD: normal format (1.31283), 1 pip = 0.0001
        # - USD/JPY: normal format (154.13), 1 pip = 0.01
        if 'JPY' in pair:
            # JPY pairs: normal format, 1 pip = 0.01
            spread = (ask - bid) / 0.01
        elif pair == 'EUR_USD':
            # EUR/USD only: IG scaled format
            # bid=11514.9, ask=11515.5 means 1.15149 to 1.15155
            # So 1 unit in IG format = 0.1 pips
            spread = (ask - bid) / 10.0
        else:
            # GBP/USD and others: normal format, 1 pip = 0.0001
            spread = (ask - bid) / 0.0001

        # Store latest tick
        self.latest_ticks[pair] = {
            'bid': bid,
            'ask': ask,
            'mid': mid,
            'spread': spread,
            'timestamp': timestamp
        }

        self.ticks_received += 1

        # Push to DataHub
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
                if self.ticks_received % 100 == 0:
                    logger.warning(f"⚠️  DataHub tick update failed: {e}")

        # Aggregate into 1-minute candle
        self._aggregate_tick_to_candle(pair, mid, timestamp)

        # Log first few ticks
        if self.ticks_received <= 10:
            logger.info(f"📊 {pair}: bid={bid:.5f}, ask={ask:.5f}, spread={spread:.1f} pips")

    def _aggregate_tick_to_candle(self, pair: str, price: float, timestamp: datetime):
        """Aggregate tick into 1-minute candle."""
        # Get current minute boundary
        minute_start = timestamp.replace(second=0, microsecond=0)

        # Check if we need to start a new candle
        if pair not in self.forming_candles or self.forming_candles[pair].get('timestamp') != minute_start:
            # Finalize previous candle if exists
            if pair in self.forming_candles and self.forming_candles[pair]:
                self._finalize_candle(pair)

            # Start new candle
            self.forming_candles[pair] = {
                'timestamp': minute_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'tick_count': 1
            }
        else:
            # Update existing candle
            candle = self.forming_candles[pair]
            candle['high'] = max(candle['high'], price)
            candle['low'] = min(candle['low'], price)
            candle['close'] = price
            candle['tick_count'] += 1

    def _finalize_candle(self, pair: str):
        """Finalize a completed 1-minute candle."""
        if pair not in self.forming_candles:
            return

        candle_data = self.forming_candles[pair]

        # Create Candle object
        candle = Candle(
            symbol=pair,
            timestamp=candle_data['timestamp'],
            open=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close'],
            volume=float(candle_data['tick_count'])  # Use tick count as volume
        )

        # Push to DataHub
        if self.data_hub:
            try:
                self.data_hub.update_candle_1m(candle)
                self.candles_completed += 1

                logger.info(f"🕯️  {pair} 1m candle: O={candle.open:.5f} H={candle.high:.5f} L={candle.low:.5f} C={candle.close:.5f} ({candle.volume:.0f} ticks)")

            except Exception as e:
                logger.warning(f"⚠️  DataHub candle update failed for {pair}: {e}")

    def _print_status(self):
        """Print collector status."""
        runtime_min = (datetime.now() - self.start_time).total_seconds() / 60
        tick_rate = self.ticks_received / runtime_min if runtime_min > 0 else 0

        logger.info("="*80)
        logger.info(f"📊 WEBSOCKET STATUS")
        logger.info(f"   Runtime: {runtime_min:.1f} minutes")
        logger.info(f"   Ticks: {self.ticks_received:,} ({tick_rate:.1f}/min)")
        logger.info(f"   Candles: {self.candles_completed:,}")
        logger.info(f"   Pairs: {len(self.pairs)}")

        # Show latest spreads
        logger.info(f"\n   Latest Spreads:")
        for pair, tick_data in self.latest_ticks.items():
            logger.info(f"      {pair}: {tick_data['spread']:.1f} pips @ {tick_data['mid']:.5f}")

        logger.info("="*80)

    def get_latest_tick(self, symbol: str) -> Optional[Dict]:
        """Get latest tick for a symbol (for UnifiedDataFetcher compatibility)."""
        return self.latest_ticks.get(symbol)

    def get_latest_candles(self, symbol: str, timeframe: str = "1m", bars: int = 100) -> Optional[list]:
        """Get latest candles from DataHub."""
        if not self.data_hub:
            return None

        try:
            candles = self.data_hub.get_latest_candles(symbol, limit=bars)
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
            logger.warning(f"⚠️  Failed to get candles from DataHub: {e}")
            return None

    def run_forever(self):
        """Run collector indefinitely."""
        logger.info("="*80)
        logger.info("🚀 MODERN IG WEBSOCKET COLLECTOR")
        logger.info("="*80)

        try:
            # Connect
            self.connect()

            # Subscribe
            self.subscribe_to_pairs()

            # Process ticks
            logger.info("\n⚡ Collector running - processing ticks...")
            logger.info("   Press Ctrl+C to stop\n")

            self.process_ticks()

        except KeyboardInterrupt:
            logger.info("\n🛑 Stopping...")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            raise
        finally:
            # Cleanup
            if self.stream_manager:
                try:
                    self.stream_manager.stop_subscriptions()
                    logger.info("✅ Subscriptions stopped")
                except:
                    pass

            logger.info("👋 Collector stopped")


def main():
    """Main entry point."""
    # Check config
    if not ForexConfig.IG_API_KEY:
        logger.error("❌ IG_API_KEY not set in .env")
        sys.exit(1)

    if not ForexConfig.IG_USERNAME:
        logger.error("❌ IG_USERNAME not set in .env")
        sys.exit(1)

    if not ForexConfig.IG_PASSWORD:
        logger.error("❌ IG_PASSWORD not set in .env")
        sys.exit(1)

    # Create and run collector
    try:
        collector = ModernWebSocketCollector()
        collector.run_forever()
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    main()
