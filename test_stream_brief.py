"""Quick test of streaming service"""
import logging
import sys
import time
from threading import Thread
from ig_stream_service import IGForexStreamService
from lightstreamer.client import LightstreamerClient, ConsoleLoggerProvider, ConsoleLogLevel

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
)

# Enable Lightstreamer logging
loggerProvider = ConsoleLoggerProvider(ConsoleLogLevel.WARN)
LightstreamerClient.setLoggerProvider(loggerProvider)

print("="*80)
print("IG STREAMING TEST (10 seconds)")
print("="*80)

# Counter for prices received
prices_received = []

def on_price(pair, bid, ask, timestamp):
    """Callback for price updates"""
    if pair not in prices_received:
        prices_received.append(pair)
        print(f"✅ {pair}: Bid {bid:.5f} | Ask {ask:.5f}")

# Create and connect
stream = IGForexStreamService(price_callback=on_price)

try:
    stream.connect()
    print("\n✅ Connected! Streaming prices...")
    print("Waiting 10 seconds for price updates...\n")

    # Wait 10 seconds
    time.sleep(10)

    # Show summary
    all_prices = stream.get_all_prices()
    print(f"\n\n📊 SUMMARY:")
    print(f"   Pairs streaming: {len(all_prices)}/28")
    print(f"   Pairs received: {len(prices_received)}")

    # Show first 5 pairs with latest prices
    if all_prices:
        print(f"\n   Latest prices (sample):")
        for i, (pair, data) in enumerate(list(all_prices.items())[:5]):
            if data['mid']:
                print(f"      {pair}: {data['mid']:.5f} @ {data['timestamp']}")

    stream.disconnect()
    print("\n✅ Test complete!")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    stream.disconnect()

print("="*80)
