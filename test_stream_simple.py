"""Test streaming with just 2 major pairs"""
import logging
import sys
import time
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

logging.basicConfig(level=logging.INFO, format="%(message)s")

# Setup Lightstreamer logging
loggerProvider = ConsoleLoggerProvider(ConsoleLogLevel.INFO)
LightstreamerClient.setLoggerProvider(loggerProvider)

class SimpleListener(SubscriptionListener):
    def onItemUpdate(self, update: ItemUpdate):
        print(f"✅ {update.getItemName()}: Bid {update.getValue('BID')}, Offer {update.getValue('OFFER')}")

    def onSubscription(self):
        print("✅ Subscribed successfully!")

    def onSubscriptionError(self, code, message):
        print(f"❌ Subscription error: {code} - {message}")

    def onUnsubscription(self):
        print("Unsubscribed")

print("="*80)
print("SIMPLE STREAMING TEST (2 pairs)")
print("="*80)

# Create IG services
ig_service = IGService(
    username=ForexConfig.IG_USERNAME,
    password=ForexConfig.IG_PASSWORD,
    api_key=ForexConfig.IG_API_KEY,
    acc_type="DEMO",
    acc_number=ForexConfig.IG_ACC_NUMBER
)

ig_stream_service = IGStreamService(ig_service)
ig_stream_service.create_session()

print("✅ Stream session created\n")

# Subscribe to just 2 major pairs
test_epics = [
    "CS.D.EURUSD.TODAY.IP",
    "CS.D.GBPUSD.TODAY.IP",
]

subscription = Subscription(
    mode="MERGE",
    items=[f"MARKET:{epic}" for epic in test_epics],
    fields=["UPDATE_TIME", "BID", "OFFER"],
)

subscription.addListener(SimpleListener())

print(f"Subscribing to {len(test_epics)} pairs...")
ig_stream_service.subscribe(subscription)

print("Waiting 10 seconds...")
time.sleep(10)

print("\n✅ Disconnecting...")
ig_stream_service.disconnect()
print("="*80)
