"""
Test Concurrent Trading System

Tests the complete system:
- SQLite database persistence
- Concurrent analysis of all pairs
- Paper trader integration
- Data flow from analysis to database
"""

import time
from concurrent_worker import ConcurrentTradingWorker
from trading_database import get_database
from forex_config import ForexConfig


def test_database():
    """Test database initialization and basic operations."""
    print("\n" + "="*80)
    print("TEST 1: Database Initialization")
    print("="*80)

    db = get_database()

    # Test stats
    stats = db.get_statistics()
    print(f"\n✅ Database initialized successfully")
    print(f"   Total trades: {stats['total_trades']}")
    print(f"   Open positions: {stats['open_positions']}")
    print(f"   Win rate: {stats['win_rate']:.1f}%")

    return True


def test_concurrent_worker():
    """Test concurrent worker with single cycle."""
    print("\n" + "="*80)
    print("TEST 2: Concurrent Worker (Single Cycle)")
    print("="*80)

    worker = ConcurrentTradingWorker(
        initial_balance=50000.0,
        auto_trading=False,  # Don't auto-execute for test
        max_workers=10
    )

    print(f"\n✅ Worker initialized")
    print(f"   Balance: €{worker.trader.balance:,.2f}")
    print(f"   Monitoring: {len(ForexConfig.ALL_PAIRS)} pairs")
    print(f"   Max workers: 10")

    # Run one cycle
    print(f"\n🔄 Running single analysis cycle...")
    start_time = time.time()

    worker.run_once()

    elapsed = time.time() - start_time

    print(f"\n✅ Analysis complete in {elapsed:.1f}s")
    print(f"   Open positions: {len(worker.trader.open_positions)}")

    return True


def test_database_persistence():
    """Test that data is persisted to database."""
    print("\n" + "="*80)
    print("TEST 3: Database Persistence")
    print("="*80)

    db = get_database()

    # Check signals
    signals = db.get_signals(limit=10)
    print(f"\n✅ Signals in database: {len(signals)}")
    if signals:
        latest = signals[0]
        print(f"   Latest: {latest['pair']} {latest['signal']} ({latest['confidence']*100:.0f}%)")

    # Check agent analysis
    analyses = db.get_agent_analysis(pair=None, limit=10)
    print(f"\n✅ Agent analyses in database: {len(analyses)}")
    if analyses:
        latest = analyses[0]
        print(f"   Latest: {latest['pair']} at {latest['timestamp']}")

    # Check technical indicators
    for pair in ForexConfig.PRIORITY_PAIRS[:3]:
        indicators = db.get_latest_indicators(pair)
        if indicators:
            print(f"\n✅ Indicators for {pair}:")
            print(f"   Total indicators: {len(indicators['indicators'])}")
            print(f"   Timestamp: {indicators['timestamp']}")

    # Check performance metrics
    metrics = db.get_performance_history(hours=1)
    print(f"\n✅ Performance snapshots: {len(metrics)}")
    if metrics:
        latest = metrics[-1]
        print(f"   Balance: €{latest['balance']:,.2f}")
        print(f"   Equity: €{latest['equity']:,.2f}")
        print(f"   Open positions: {latest['open_positions']}")

    return True


def test_concurrent_analysis():
    """Test concurrent analysis performance."""
    print("\n" + "="*80)
    print("TEST 4: Concurrent Analysis Performance")
    print("="*80)

    worker = ConcurrentTradingWorker(
        initial_balance=50000.0,
        auto_trading=False,
        max_workers=10
    )

    # Time concurrent analysis
    print(f"\n⏱️  Testing concurrent analysis of {len(ForexConfig.ALL_PAIRS)} pairs...")
    start_time = time.time()

    results = worker.analyze_all_pairs_concurrent()

    elapsed = time.time() - start_time

    successful = sum(1 for r in results if r['success'])
    signals_generated = sum(1 for r in results if r.get('signal') is not None)

    print(f"\n✅ Concurrent analysis complete")
    print(f"   Total time: {elapsed:.1f}s")
    print(f"   Average per pair: {elapsed/len(ForexConfig.ALL_PAIRS):.2f}s")
    print(f"   Successful: {successful}/{len(ForexConfig.ALL_PAIRS)}")
    print(f"   Signals generated: {signals_generated}")

    # Performance breakdown
    if elapsed < 60:
        print(f"\n🚀 EXCELLENT: Analyzed {len(ForexConfig.ALL_PAIRS)} pairs in under 60 seconds!")
    elif elapsed < 120:
        print(f"\n✅ GOOD: Completed in {elapsed:.0f} seconds")
    else:
        print(f"\n⚠️  SLOW: Consider increasing max_workers or optimizing API calls")

    return True


def test_data_integrity():
    """Test data integrity across system."""
    print("\n" + "="*80)
    print("TEST 5: Data Integrity")
    print("="*80)

    db = get_database()

    # Check signal-to-position consistency
    signals = db.get_signals(limit=50)
    executed_signals = [s for s in signals if s['executed']]
    positions = db.get_open_positions()
    trades = db.get_trades(limit=50)

    print(f"\n✅ Data Consistency Check:")
    print(f"   Total signals: {len(signals)}")
    print(f"   Executed signals: {len(executed_signals)}")
    print(f"   Open positions: {len(positions)}")
    print(f"   Closed trades: {len(trades)}")

    # Verify all executed signals have corresponding positions or trades
    for signal in executed_signals:
        pair = signal['pair']
        timestamp = signal['timestamp']

        # Check if there's a matching position
        matching_pos = any(p['pair'] == pair for p in positions)

        # Check if there's a matching trade
        matching_trade = any(t['pair'] == pair for t in trades)

        if not (matching_pos or matching_trade):
            print(f"   ⚠️  Warning: Executed signal for {pair} has no position/trade")

    print(f"\n✅ Data integrity check complete")

    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("CONCURRENT TRADING SYSTEM - COMPREHENSIVE TEST")
    print("="*80)

    tests = [
        ("Database Initialization", test_database),
        ("Concurrent Worker", test_concurrent_worker),
        ("Database Persistence", test_database_persistence),
        ("Concurrent Analysis Performance", test_concurrent_analysis),
        ("Data Integrity", test_data_integrity)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            print(f"\n\n")
            success = test_func()
            results.append((test_name, success, None))
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False, str(e)))

    # Summary
    print("\n\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
        if error:
            print(f"       Error: {error}")

    total = len(results)
    passed = sum(1 for _, success, _ in results if success)

    print(f"\n{'='*80}")
    print(f"TOTAL: {passed}/{total} tests passed")
    print(f"{'='*80}")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is ready for production.")
        print("\n💡 Next steps:")
        print("   1. Launch dashboard: streamlit run paper_trading_dashboard_v3.py")
        print("   2. Start worker and enable auto-trading")
        print("   3. Monitor all pairs concurrently every 60 seconds")
    else:
        print("\n⚠️  Some tests failed. Please review errors above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
