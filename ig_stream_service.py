"""
IG Streaming Service using Lightstreamer

Streams real-time price data for all 28 forex pairs.
"""

import logging
import sys
from typing import Dict, Callable, Optional
from datetime import datetime
from threading import Lock

from lightstreamer.client import (
    LightstreamerClient,
    Subscription,
    ConsoleLoggerProvider,
    ConsoleLogLevel,
    SubscriptionListener,
    ItemUpdate,
)

from trading_ig import IGService, IGStreamService
from forex_config import ForexConfig

logger = logging.getLogger(__name__)


class ForexStreamListener(SubscriptionListener):
    """Listener for forex price updates."""

    def __init__(self, callback: Optional[Callable] = None):
        """
        Initialize listener.

        Args:
            callback: Optional function to call on price updates
                     Signature: callback(pair, bid, ask, timestamp)
        """
        self.callback = callback
        self.latest_prices: Dict[str, Dict] = {}
        self.lock = Lock()

    def onItemUpdate(self, update: ItemUpdate):
        """Handle price update from Lightstreamer."""
        try:
            # Extract EPIC from item name (format: MARKET:CS.D.EURUSD.TODAY.IP)
            epic = update.getItemName().replace("MARKET:", "")

            # Get pair name from EPIC
            pair = self._epic_to_pair(epic)
            if not pair:
                return

            # Extract price data
            bid = update.getValue('BID')
            ask = update.getValue('OFFER')
            timestamp = update.getValue('UPDATE_TIME')

            # Store latest prices
            with self.lock:
                self.latest_prices[pair] = {
                    'bid': float(bid) if bid else None,
                    'ask': float(ask) if ask else None,
                    'mid': (float(bid) + float(ask)) / 2 if bid and ask else None,
                    'timestamp': timestamp,
                    'high': update.getValue('HIGH'),
                    'low': update.getValue('LOW'),
                    'change': update.getValue('CHANGE'),
                    'change_pct': update.getValue('CHANGE_PCT'),
                }

            # Call callback if provided
            if self.callback and bid and ask:
                self.callback(pair, float(bid), float(ask), timestamp)

        except Exception as e:
            logger.error(f"Error processing price update: {e}")

    def _epic_to_pair(self, epic: str) -> Optional[str]:
        """Convert EPIC to pair name."""
        for pair, pair_epic in ForexConfig.IG_EPIC_MAP.items():
            if pair_epic == epic:
                return pair
        return None

    def get_latest_price(self, pair: str) -> Optional[Dict]:
        """Get latest price for a pair."""
        with self.lock:
            return self.latest_prices.get(pair)

    def get_all_prices(self) -> Dict[str, Dict]:
        """Get all latest prices."""
        with self.lock:
            return self.latest_prices.copy()

    def onSubscription(self):
        logger.info("✅ Forex stream subscribed successfully")

    def onSubscriptionError(self, code, message):
        logger.error(f"❌ Forex stream subscription error: {code} - {message}")

    def onUnsubscription(self):
        logger.info("Forex stream unsubscribed")


class IGForexStreamService:
    """
    IG Streaming Service for real-time forex data.

    Connects to IG Markets Lightstreamer API and streams prices for all 28 pairs.
    """

    def __init__(self, api_key: str = None, username: str = None, password: str = None,
                 acc_number: str = None, price_callback: Optional[Callable] = None):
        """
        Initialize streaming service.

        Args:
            api_key: IG API key
            username: IG username
            password: IG password
            acc_number: IG account number
            price_callback: Optional callback for price updates
        """
        self.api_key = api_key or ForexConfig.IG_API_KEY
        self.username = username or ForexConfig.IG_USERNAME
        self.password = password or ForexConfig.IG_PASSWORD
        self.acc_number = acc_number or ForexConfig.IG_ACC_NUMBER
        self.acc_type = "DEMO" if ForexConfig.IG_DEMO else "LIVE"

        # Create IG service
        self.ig_service = IGService(
            username=self.username,
            password=self.password,
            api_key=self.api_key,
            acc_type=self.acc_type,
            acc_number=self.acc_number
        )

        # Create stream service
        self.ig_stream_service = IGStreamService(self.ig_service)

        # Create listener
        self.market_listener = ForexStreamListener(callback=price_callback)

        # Subscription objects
        self.market_subscription = None
        self.account_subscription = None

        self._connected = False

    def connect(self):
        """Connect to streaming service."""
        try:
            # Create session
            self.ig_stream_service.create_session()
            logger.info(f"✅ IG stream session created ({self.acc_type})")

            # Get all forex EPICs from config (use .TODAY.IP spreadbet EPICs)
            all_epics = list(ForexConfig.IG_EPIC_MAP.values())

            # Create market subscription for all 28 pairs
            self.market_subscription = Subscription(
                mode="MERGE",
                items=[f"MARKET:{epic}" for epic in all_epics],
                fields=[
                    "UPDATE_TIME",
                    "BID",
                    "OFFER",
                    "CHANGE",
                    "MARKET_STATE",
                    "CHANGE_PCT",
                    "HIGH",
                    "LOW",
                ],
            )

            # Add listener
            self.market_subscription.addListener(self.market_listener)

            # Subscribe
            self.ig_stream_service.subscribe(self.market_subscription)
            logger.info(f"✅ Subscribed to {len(all_epics)} forex pairs")

            # Optional: Subscribe to account updates
            self.account_subscription = Subscription(
                mode="MERGE",
                items=[f"ACCOUNT:{self.acc_number}"],
                fields=["FUNDS", "MARGIN", "AVAILABLE_TO_DEAL", "PNL", "EQUITY", "EQUITY_USED"],
            )

            self.ig_stream_service.subscribe(self.account_subscription)
            logger.info(f"✅ Subscribed to account updates")

            self._connected = True

        except Exception as e:
            logger.error(f"❌ Failed to connect to stream: {e}")
            raise

    def disconnect(self):
        """Disconnect from streaming service."""
        if self._connected:
            try:
                self.ig_stream_service.disconnect()
                logger.info("✅ Disconnected from IG stream")
                self._connected = False
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def get_latest_price(self, pair: str) -> Optional[Dict]:
        """Get latest price for a pair."""
        return self.market_listener.get_latest_price(pair)

    def get_all_prices(self) -> Dict[str, Dict]:
        """Get all latest prices."""
        return self.market_listener.get_all_prices()


# Test
if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Enable Lightstreamer logging
    loggerProvider = ConsoleLoggerProvider(ConsoleLogLevel.INFO)
    LightstreamerClient.setLoggerProvider(loggerProvider)

    print("="*80)
    print("IG FOREX STREAMING TEST")
    print("="*80)

    # Price callback
    def on_price_update(pair, bid, ask, timestamp):
        print(f"📊 {pair}: Bid {bid:.5f} | Ask {ask:.5f} | Time {timestamp}")

    # Create stream service
    stream = IGForexStreamService(price_callback=on_price_update)

    try:
        # Connect
        stream.connect()

        print("\n✅ Connected! Streaming prices for 28 forex pairs...")
        print("Press Ctrl+C to stop\n")

        # Keep running
        import time
        while True:
            time.sleep(1)

            # Show summary every 10 seconds
            # prices = stream.get_all_prices()
            # if prices:
            #     print(f"\n📈 Tracking {len(prices)} pairs")

    except KeyboardInterrupt:
        print("\n\n⚠️ Stopping stream...")
        stream.disconnect()
        print("✅ Disconnected")

    except Exception as e:
        print(f"❌ Error: {e}")
        stream.disconnect()
