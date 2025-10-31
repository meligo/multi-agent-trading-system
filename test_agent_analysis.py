"""
Test Agent Analysis Flow

Quick test to verify the generate_signal_with_details() method works correctly.
"""

from forex_config import ForexConfig
from forex_agents import ForexTradingSystem

def test_agent_flow():
    """Test the complete agent analysis flow."""
    print("🔄 Testing Agent Analysis Flow...")
    print("=" * 80)

    # Initialize system
    system = ForexTradingSystem(
        api_key=ForexConfig.FINNHUB_API_KEY,
        openai_api_key=ForexConfig.OPENAI_API_KEY
    )

    # Test with EUR/USD
    test_pair = 'EUR_USD'
    print(f"\n📊 Analyzing {test_pair}...\n")

    try:
        # Get complete agent flow
        details = system.generate_signal_with_details(test_pair, '5', '1')

        # Verify structure
        assert 'pair' in details, "Missing 'pair' in details"
        assert 'analysis' in details, "Missing 'analysis' in details"
        assert 'price_action' in details, "Missing 'price_action' in details"
        assert 'momentum' in details, "Missing 'momentum' in details"
        assert 'decision' in details, "Missing 'decision' in details"
        assert 'signal' in details, "Missing 'signal' in details"

        print("✅ Step 1: Technical Analysis")
        analysis = details['analysis']
        print(f"   Current Price: {analysis['current_price']:.5f}")
        print(f"   5m Trend: {analysis['trend_primary']}")
        print(f"   1m Trend: {analysis['trend_secondary']}")
        print(f"   Total Indicators: {len(analysis['indicators'])}")

        # Check for new indicators
        indicators = analysis['indicators']
        print(f"   OBV Z-Score: {indicators.get('obv_zscore', 'N/A')}")
        print(f"   VPVR POC: {indicators.get('vpvr_poc', 'N/A')}")
        print(f"   IB Range: {indicators.get('ib_range', 'N/A')}")
        print(f"   FVG Bull: {indicators.get('fvg_bull', 'N/A')}")

        print("\n✅ Step 2: Price Action Agent")
        price_action = details['price_action']
        print(f"   Setup Detected: {price_action.get('has_setup', False)}")
        print(f"   Setup Type: {price_action.get('setup_type', 'N/A')}")
        print(f"   Confidence: {price_action.get('confidence', 0)}%")

        print("\n✅ Step 3: Momentum Agent")
        momentum = details['momentum']
        print(f"   Strong Momentum: {momentum.get('strong_momentum', False)}")
        print(f"   Direction: {momentum.get('direction', 'N/A')}")
        print(f"   Confidence: {momentum.get('confidence', 0)}%")

        print("\n✅ Step 4: Decision Maker")
        decision = details['decision']
        print(f"   Final Signal: {decision.get('signal', 'HOLD')}")
        print(f"   Confidence: {decision.get('confidence', 0)}%")

        print("\n✅ Step 5: Trading Signal")
        signal = details['signal']
        if signal:
            print(f"   ✅ TRADEABLE SIGNAL GENERATED")
            print(f"   Entry: {signal.entry_price:.5f}")
            print(f"   Stop Loss: {signal.stop_loss:.5f}")
            print(f"   Take Profit: {signal.take_profit:.5f}")
            print(f"   R:R Ratio: {signal.risk_reward_ratio:.2f}:1")
        else:
            print(f"   ⏸️ NO TRADEABLE SIGNAL")
            print(f"   Reason: {decision.get('signal', 'HOLD')} or confidence too low")

        print("\n" + "=" * 80)
        print("✅ All tests passed! Agent analysis flow is working correctly.")
        print("\n💡 The dashboard is ready to use:")
        print("   streamlit run paper_trading_dashboard_v2.py")

        return True

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_agent_flow()
