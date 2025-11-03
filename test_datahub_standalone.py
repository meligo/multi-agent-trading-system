#!/usr/bin/env python3
"""
Standalone DataHub Test

Tests DataHub components independently before full system integration.
"""

import logging
import time
from datetime import datetime
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_models():
    """Test 1: Market data models"""
    print("\n" + "="*80)
    print("TEST 1: Market Data Models")
    print("="*80)

    from market_data_models import Tick, Candle, OrderFlowMetrics

    # Test Tick
    tick = Tick(
        symbol='EUR_USD',
        bid=1.0500,
        ask=1.0510,
        mid=0.0,  # Should auto-calculate
        spread=0.0,  # Should auto-calculate
        timestamp=datetime.utcnow()
    )
    print(f"✅ Tick created: {tick.symbol} bid={tick.bid} ask={tick.ask} mid={tick.mid} spread={tick.spread:.1f} pips")
    assert tick.mid == 1.0505, "Mid calculation failed"
    assert tick.spread == 10.0, "Spread calculation failed"  # (1.0510 - 1.0500) / 0.0001 = 10 pips

    # Test Candle
    candle = Candle(
        symbol='EUR_USD',
        timestamp=datetime.utcnow(),
        open=1.0500,
        high=1.0520,
        low=1.0495,
        close=1.0510,
        volume=1000.0
    )
    print(f"✅ Candle created: {candle.symbol} O={candle.open} H={candle.high} L={candle.low} C={candle.close}")
    assert candle.is_complete(), "Candle validation failed"

    # Test OrderFlowMetrics
    metrics = OrderFlowMetrics(
        symbol='EUR_USD',
        futures_symbol='6E',
        timestamp=datetime.utcnow(),
        net_volume_delta=1000.0,
        ofi_60s=500.0,
        buy_volume=5000.0,
        sell_volume=4000.0,
        total_volume=9000.0
    )
    print(f"✅ OrderFlowMetrics created: {metrics.symbol} bias={metrics.order_flow_bias} OFI={metrics.ofi_60s}")
    assert metrics.order_flow_bias == 'bullish', "Order flow bias calculation failed"

    print("✅ All models working correctly!\n")
    return True


def test_datahub_local():
    """Test 2: DataHub (local, no manager)"""
    print("\n" + "="*80)
    print("TEST 2: DataHub (Local)")
    print("="*80)

    from data_hub import DataHub
    from market_data_models import Tick, Candle

    hub = DataHub(max_candles=100)
    print(f"✅ DataHub created")

    # Test tick storage
    tick = Tick(
        symbol='EUR_USD',
        bid=1.0500,
        ask=1.0510,
        mid=1.0505,
        spread=1.0,
        timestamp=datetime.utcnow()
    )
    hub.update_tick(tick)
    print(f"✅ Tick stored")

    # Test tick retrieval
    retrieved_tick = hub.get_latest_tick('EUR_USD')
    assert retrieved_tick is not None, "Tick retrieval failed"
    assert retrieved_tick.bid == 1.0500, "Tick data mismatch"
    print(f"✅ Tick retrieved: bid={retrieved_tick.bid}")

    # Test candle storage
    for i in range(5):
        candle = Candle(
            symbol='EUR_USD',
            timestamp=datetime.utcnow(),
            open=1.0500 + i*0.0001,
            high=1.0520 + i*0.0001,
            low=1.0495 + i*0.0001,
            close=1.0510 + i*0.0001,
            volume=1000.0
        )
        hub.update_candle_1m(candle)
        time.sleep(0.01)
    print(f"✅ 5 candles stored")

    # Test candle retrieval
    candles = hub.get_latest_candles('EUR_USD', limit=10)
    assert len(candles) == 5, f"Expected 5 candles, got {len(candles)}"
    print(f"✅ Candles retrieved: {len(candles)} candles")

    # Test status
    status = hub.get_status()
    print(f"✅ Status: {status['symbols_tracked']}, {status['stats']}")

    print("✅ DataHub working correctly!\n")
    return True


def test_datahub_manager():
    """Test 3: DataHub Manager (multi-process)"""
    print("\n" + "="*80)
    print("TEST 3: DataHub Manager (Multi-Process)")
    print("="*80)

    from data_hub import start_data_hub_manager, connect_to_data_hub
    from market_data_models import Tick, Candle
    import multiprocessing

    # Start manager
    print("🚀 Starting DataHub manager...")
    manager = start_data_hub_manager(
        address=('127.0.0.1', 50001),  # Use different port to avoid conflicts
        authkey=b'test_key_123'
    )
    hub = manager.DataHub()
    print(f"✅ DataHub manager started")

    # Test from main process
    tick = Tick(
        symbol='GBP_USD',
        bid=1.2500,
        ask=1.2510,
        mid=1.2505,
        spread=1.0,
        timestamp=datetime.utcnow()
    )
    hub.update_tick(tick)
    print(f"✅ Tick stored from main process")

    # Test retrieval
    retrieved = hub.get_latest_tick('GBP_USD')
    assert retrieved is not None, "Manager tick retrieval failed"
    print(f"✅ Tick retrieved from main process: bid={retrieved.bid}")

    # Test from same process (multi-process pickling is complex in tests)
    # In production, subprocesses connect via get_data_hub_from_env()
    try:
        # Simulate subprocess connection
        hub_client = connect_to_data_hub(
            address=('127.0.0.1', 50001),
            authkey=b'test_key_123'
        )
        tick = hub_client.get_latest_tick('GBP_USD')
        if tick and tick.bid == 1.2500:
            print(f"✅ Client connection retrieved tick successfully!")
        else:
            print(f"❌ Client tick retrieval failed")
            return False
    except Exception as e:
        print(f"❌ Client connection error: {e}")
        return False

    # Shutdown manager
    manager.shutdown()
    print(f"✅ Manager shutdown")

    print("✅ DataHub Manager working correctly!\n")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print(" DataHub Standalone Test Suite")
    print("="*80)

    results = []

    try:
        results.append(("Models", test_models()))
    except Exception as e:
        print(f"❌ Models test failed: {e}")
        results.append(("Models", False))

    try:
        results.append(("DataHub Local", test_datahub_local()))
    except Exception as e:
        print(f"❌ DataHub Local test failed: {e}")
        results.append(("DataHub Local", False))

    try:
        results.append(("DataHub Manager", test_datahub_manager()))
    except Exception as e:
        print(f"❌ DataHub Manager test failed: {e}")
        results.append(("DataHub Manager", False))

    # Summary
    print("\n" + "="*80)
    print(" Test Results Summary")
    print("="*80)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:8} {name}")

    all_passed = all(result[1] for result in results)
    print("="*80)

    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("\nDataHub is ready for integration!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("\nPlease fix issues before integrating.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
