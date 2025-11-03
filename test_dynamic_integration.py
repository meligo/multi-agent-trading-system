"""
Test Dynamic SL/TP Integration

Quick test to verify the dynamic SL/TP system is properly integrated
into the scalping agents without errors.
"""

import sys
from scalping_config import ScalpingConfig
from langchain_openai import ChatOpenAI

# Test 1: Configuration loads
print("=" * 80)
print("TEST 1: Configuration Loading")
print("=" * 80)

try:
    print(f"✅ Dynamic SL/TP Enabled: {ScalpingConfig.DYNAMIC_SLTP_ENABLED}")
    print(f"✅ ATR Period: {ScalpingConfig.ATR_PERIOD}")
    print(f"✅ ATR Multiplier SL: {ScalpingConfig.ATR_MULTIPLIER_SL}")
    print(f"✅ ATR Multiplier TP: {ScalpingConfig.ATR_MULTIPLIER_TP}")
    print(f"✅ Min SL: {ScalpingConfig.MIN_SL_PIPS} pips")
    print(f"✅ Max SL: {ScalpingConfig.MAX_SL_PIPS} pips")
    print(f"✅ Min TP: {ScalpingConfig.MIN_TP_PIPS} pips")
    print(f"✅ Max TP: {ScalpingConfig.MAX_TP_PIPS} pips")
    print("\n✅ Configuration loaded successfully\n")
except Exception as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

# Test 2: DynamicSLTPCalculator import
print("=" * 80)
print("TEST 2: Dynamic SL/TP Calculator Import")
print("=" * 80)

try:
    from dynamic_sltp import DynamicSLTPCalculator
    print("✅ DynamicSLTPCalculator imported successfully")

    # Test instantiation
    calc = DynamicSLTPCalculator(
        atr_period=ScalpingConfig.ATR_PERIOD,
        atr_mult_sl=ScalpingConfig.ATR_MULTIPLIER_SL,
        atr_mult_tp=ScalpingConfig.ATR_MULTIPLIER_TP
    )
    print(f"✅ Calculator instantiated: {calc}")
    print()
except Exception as e:
    print(f"❌ Import/instantiation error: {e}")
    sys.exit(1)

# Test 3: ScalpValidator imports and instantiates
print("=" * 80)
print("TEST 3: Scalping Agents Integration")
print("=" * 80)

try:
    from scalping_agents import ScalpValidator

    # Mock LLM for testing
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Instantiate ScalpValidator
    validator = ScalpValidator(llm)
    print(f"✅ ScalpValidator instantiated: {validator.name}")
    print(f"✅ Has sltp_calculator: {hasattr(validator, 'sltp_calculator')}")

    if hasattr(validator, 'sltp_calculator'):
        print(f"✅ Calculator config: ATR={validator.sltp_calculator.atr_period}, "
              f"SL={validator.sltp_calculator.atr_mult_sl}x, "
              f"TP={validator.sltp_calculator.atr_mult_tp}x")
    print()
except Exception as e:
    print(f"❌ Integration error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test with mock data
print("=" * 80)
print("TEST 4: Calculate Dynamic SL/TP with Mock Data")
print("=" * 80)

try:
    # Create mock candles (1-minute EUR/USD data)
    mock_candles = []
    base_price = 1.10000
    for i in range(20):
        candle = {
            'timestamp': f"2025-01-01 12:{i:02d}:00",
            'open': base_price + (i * 0.00010),
            'high': base_price + (i * 0.00010) + 0.00020,
            'low': base_price + (i * 0.00010) - 0.00015,
            'close': base_price + (i * 0.00010) + 0.00005,
            'volume': 100
        }
        mock_candles.append(candle)

    # Calculate dynamic levels
    levels = calc.calculate_sltp(
        entry_price=1.10200,
        direction='long',
        pair='EUR_USD',
        candles=mock_candles,
        spread=0.8,
        use_structure=True
    )

    print(f"✅ Calculation successful!")
    print(f"   Entry Price: {1.10200:.5f}")
    print(f"   SL Price: {levels.sl_price:.5f} ({levels.sl_pips:.1f} pips)")
    print(f"   TP Price: {levels.tp_price:.5f} ({levels.tp_pips:.1f} pips)")
    print(f"   Risk:Reward: 1:{levels.metadata['risk_reward']:.2f}")
    print(f"   Method: {levels.method}")
    print(f"   Confidence: {levels.confidence:.0%}")
    print(f"   ATR: {levels.metadata.get('atr_pips', 0):.2f} pips")
    print()
except Exception as e:
    print(f"❌ Calculation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# All tests passed
print("=" * 80)
print("✅ ALL TESTS PASSED - Dynamic SL/TP Integration Complete!")
print("=" * 80)
print("\n🎉 The dynamic SL/TP system is successfully integrated!")
print("\n📋 Next Steps:")
print("   1. Run scalping engine in test mode to verify in action")
print("   2. Monitor the comparison logs (Hardcoded vs Dynamic)")
print("   3. Paper trade for 1-2 weeks to validate performance")
print("   4. Deploy to live if win rate improves to 45-55%+")
print()
print(f"🔧 Configuration Status:")
print(f"   - Dynamic SL/TP: {'ENABLED' if ScalpingConfig.DYNAMIC_SLTP_ENABLED else 'DISABLED'}")
print(f"   - Hardcoded fallback: TP={ScalpingConfig.TAKE_PROFIT_PIPS} / SL={ScalpingConfig.STOP_LOSS_PIPS} pips")
print(f"   - Safety limits: SL {ScalpingConfig.MIN_SL_PIPS}-{ScalpingConfig.MAX_SL_PIPS} pips, TP {ScalpingConfig.MIN_TP_PIPS}-{ScalpingConfig.MAX_TP_PIPS} pips")
print()
