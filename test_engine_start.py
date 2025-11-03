#!/usr/bin/env python3
"""Test ScalpingEngine initialization and start."""

import sys
import threading
import time
from scalping_engine import ScalpingEngine

print("="*80)
print("Testing ScalpingEngine Start")
print("="*80)

try:
    # Create engine
    print("\n1. Creating ScalpingEngine...")
    engine = ScalpingEngine()
    print("✅ Engine created successfully")

    # Check attributes
    print("\n2. Checking required attributes...")
    assert hasattr(engine, 'running'), "Missing 'running' attribute"
    assert hasattr(engine, 'trade_history'), "Missing 'trade_history' attribute"
    assert hasattr(engine, 'open_trades'), "Missing 'open_trades' attribute"
    assert hasattr(engine, 'active_trades'), "Missing 'active_trades' attribute"
    print("✅ All required attributes present")

    # Check initial values
    print("\n3. Checking initial values...")
    print(f"   running: {engine.running}")
    print(f"   trade_history: {engine.trade_history}")
    print(f"   open_trades: {engine.open_trades}")
    print(f"   active_trades: {engine.active_trades}")
    assert engine.running == False, "Engine should not be running initially"
    assert isinstance(engine.trade_history, list), "trade_history should be a list"
    assert isinstance(engine.open_trades, dict), "open_trades should be a dict"
    assert len(engine.trade_history) == 0, "trade_history should be empty"
    assert len(engine.open_trades) == 0, "open_trades should be empty"
    print("✅ Initial values correct")

    # Test get_performance_stats
    print("\n4. Testing get_performance_stats()...")
    stats = engine.get_performance_stats()
    print(f"   Stats: {stats}")
    assert 'total_trades' in stats, "Missing 'total_trades' in stats"
    assert 'open_positions' in stats, "Missing 'open_positions' in stats"
    assert stats['total_trades'] == 0, "total_trades should be 0"
    assert stats['open_positions'] == 0, "open_positions should be 0"
    print("✅ get_performance_stats() works")

    # Start engine in background thread
    print("\n5. Starting engine in background thread...")
    engine_thread = threading.Thread(target=engine.run, daemon=True)
    engine_thread.start()
    time.sleep(1)  # Give it time to start

    print(f"   running: {engine.running}")
    assert engine.running == True, "Engine should be running"
    print("✅ Engine started successfully")

    # Stop engine
    print("\n6. Stopping engine...")
    engine.stop()
    time.sleep(1)
    print(f"   running: {engine.running}")
    assert engine.running == False, "Engine should not be running after stop"
    print("✅ Engine stopped successfully")

    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED!")
    print("="*80)
    sys.exit(0)

except Exception as e:
    print(f"\n❌ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
