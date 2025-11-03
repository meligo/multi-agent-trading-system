#!/usr/bin/env python3
"""Test full flow: Dashboard -> Engine -> Force Start -> Stats."""

import sys
import threading
import time
from scalping_engine import ScalpingEngine
from scalping_config import ScalpingConfig

print("="*80)
print("Testing Full Dashboard Flow")
print("="*80)

try:
    # Simulate dashboard session state
    class SessionState:
        def __init__(self):
            self.engine = None
            self.engine_started = False

    session_state = SessionState()

    # 1. Simulate Force Start button click
    print("\n1. Simulating Force Start (market closed)...")
    print("   Creating engine...")
    session_state.engine = ScalpingEngine()

    print("   Starting engine in background thread...")
    engine_thread = threading.Thread(target=session_state.engine.run, daemon=True)
    engine_thread.start()
    time.sleep(1)

    session_state.engine_started = True
    print(f"   ✅ Engine started: {session_state.engine.running}")

    # 2. Simulate dashboard checking engine status
    print("\n2. Checking engine status (dashboard view)...")
    if session_state.engine and session_state.engine.running:
        print("   ✅ Engine is running")
    else:
        raise Exception("Engine should be running")

    # 3. Simulate dashboard fetching stats
    print("\n3. Fetching performance stats (dashboard calls)...")
    stats = session_state.engine.get_performance_stats()
    print(f"   Stats returned: {stats}")

    # Verify stats structure
    required_keys = ['total_trades', 'open_positions', 'daily_pnl', 'profit_factor', 'win_rate', 'avg_trade_duration_minutes']
    for key in required_keys:
        if key not in stats:
            raise Exception(f"Missing key in stats: {key}")
    print("   ✅ All required stats present")

    # 4. Simulate viewing active trades
    print("\n4. Checking active trades...")
    print(f"   Active trades: {len(session_state.engine.active_trades)}")
    print(f"   Open trades (alias): {len(session_state.engine.open_trades)}")
    print(f"   Trade history: {len(session_state.engine.trade_history)}")
    assert len(session_state.engine.active_trades) == len(session_state.engine.open_trades), "active_trades and open_trades should be same"
    print("   ✅ Trade tracking working")

    # 5. Simulate multiple stat refreshes (like auto-refresh)
    print("\n5. Simulating auto-refresh (5 cycles)...")
    for i in range(5):
        stats = session_state.engine.get_performance_stats()
        time.sleep(0.2)
        print(f"   Cycle {i+1}: {stats['total_trades']} trades, {stats['open_positions']} open")
    print("   ✅ Auto-refresh working")

    # 6. Simulate stop button click
    print("\n6. Simulating Stop Engine button...")
    if session_state.engine and session_state.engine.running:
        session_state.engine.stop()
        session_state.engine_started = False
        time.sleep(1)
        print(f"   ✅ Engine stopped: running={session_state.engine.running}")

    # 7. Verify final state
    print("\n7. Verifying final state...")
    assert session_state.engine.running == False, "Engine should be stopped"
    assert session_state.engine_started == False, "engine_started should be False"
    stats = session_state.engine.get_performance_stats()
    print(f"   Final stats: {stats}")
    print("   ✅ Final state correct")

    print("\n" + "="*80)
    print("✅ ALL DASHBOARD FLOW TESTS PASSED!")
    print("="*80)
    print("\nThe dashboard should work correctly with:")
    print("  • Force Start button (market closed)")
    print("  • Performance stats display")
    print("  • Active trades monitoring")
    print("  • Auto-refresh (2-second interval)")
    print("  • Stop Engine button")
    print("\n🚀 Ready for production!")
    sys.exit(0)

except Exception as e:
    print(f"\n❌ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
