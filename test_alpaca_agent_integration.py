"""
Test Alpaca Agent Integration

Test that agents can analyze stocks and generate Alpaca trading signals.
"""

from alpaca_concurrent_worker import AlpacaConcurrentWorker


def test_single_stock_analysis():
    """Test analyzing a single stock."""

    print("=" * 80)
    print("ALPACA AGENT INTEGRATION TEST")
    print("=" * 80)

    print("\n📋 Test Plan:")
    print("   1. Initialize Alpaca worker")
    print("   2. Analyze AAPL using multi-agent system")
    print("   3. Generate trading signal (if conditions met)")
    print("   4. Show how order would be executed")

    print("\n" + "-" * 80)
    print("STEP 1: Initialize Worker")
    print("-" * 80)

    # Initialize worker with just AAPL for testing
    worker = AlpacaConcurrentWorker(
        api_key="PKD4NWI6WBWHDL3IXNQ55WX77F",
        api_secret="CjTudarcJqnc5mHy4xGmJ98iMjQsgDwNMfZk4acmGKbp",
        risk_per_trade=0.01,  # 1% risk
        max_positions=5,
        auto_trading=False,  # Don't execute yet
        max_workers=1,
        symbols=['AAPL']  # Test with just Apple
    )

    print("\n" + "-" * 80)
    print("STEP 2: Analyze AAPL")
    print("-" * 80)

    # Run one cycle
    print("\n🔬 Running analysis...")
    worker.run_once()

    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)

    print("\n💡 How it works:")
    print("   1. ✅ Agents analyze AAPL technical indicators")
    print("   2. ✅ Agents detect trends, momentum, support/resistance")
    print("   3. ✅ Agents make trading decision (BUY/SELL/HOLD)")
    print("   4. ✅ Signal converted to Alpaca format")
    print("   5. ⏸️  Order execution (disabled for test)")

    print("\n🎯 Next steps:")
    print("   - Review agent reasoning")
    print("   - If signal generated, check R:R ratio")
    print("   - Enable auto_trading=True to execute")
    print("   - Add more symbols to trade portfolio")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    test_single_stock_analysis()
