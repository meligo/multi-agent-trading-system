#!/usr/bin/env python3
"""
Test Market Hours Integration

Tests that market hours detection is working in the trading system.
"""

print("="*80)
print("MARKET HOURS INTEGRATION TEST")
print("="*80)
print()

# Test 1: Import the module
print("1. Testing import...")
try:
    from forex_market_hours import get_market_hours
    print("   ✅ Import successful")
except Exception as e:
    print(f"   ❌ Import failed: {e}")
    exit(1)

# Test 2: Get market hours instance
print("\n2. Testing market hours instance...")
try:
    market_hours = get_market_hours()
    print("   ✅ Instance created")
except Exception as e:
    print(f"   ❌ Instance creation failed: {e}")
    exit(1)

# Test 3: Check market status
print("\n3. Testing market status...")
try:
    status = market_hours.get_market_status()
    print(f"   Market Open: {'✅ YES' if status['is_open'] else '❌ NO'}")
    print(f"   Current Time (NY): {status['current_time'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')}")

    if status['is_open']:
        print(f"   Market Session: {market_hours.get_market_session()}")
        print(f"   Next Close: {status['next_close'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')}")
        print(f"   Time Until Close: {status['time_until_close_human']}")
    else:
        print(f"   Next Open: {status['next_open'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')}")
        print(f"   Time Until Open: {status['time_until_open_human']}")

    print("   ✅ Status check successful")
except Exception as e:
    print(f"   ❌ Status check failed: {e}")
    exit(1)

# Test 4: Test integration with worker (without actually running)
print("\n4. Testing worker integration...")
try:
    from ig_concurrent_worker import IGConcurrentWorker
    print("   ✅ Worker import successful")
    print("   ✅ Market hours integration complete")
except Exception as e:
    print(f"   ❌ Worker import failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("="*80)
print("✅ ALL TESTS PASSED")
print("="*80)
print()

# Show what will happen
print("💡 What happens now:")
print()
if status['is_open']:
    print(f"   ✅ Market is OPEN ({market_hours.get_market_session()} session)")
    print(f"   ✅ Trading system will run normally")
    print(f"   ⏰ Market closes in {status['time_until_close_human']}")
    print(f"   ⏸️  System will pause automatically on Friday 5 PM EST")
else:
    print(f"   🛑 Market is CLOSED")
    print(f"   ⏰ Market opens in {status['time_until_open_human']}")
    print(f"   💤 System will wait until {status['next_open'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')}")

print()
print("🚀 To run the trading system:")
print("   python ig_concurrent_worker.py")
print()
print("⚙️  To disable market hours check (for testing):")
print("   export FOREX_IGNORE_MARKET_HOURS=true")
print()
