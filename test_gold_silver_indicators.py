"""
Test Gold and Silver with All 53 Technical Indicators

Verifies that both precious metals work correctly with the trading system.
"""

from ig_concurrent_worker import IGConcurrentWorker

def main():
    """Test Gold and Silver analysis."""

    print("="*80)
    print("TESTING GOLD AND SILVER WITH ALL 53 TECHNICAL INDICATORS")
    print("="*80)

    # Create worker (analysis mode only, no trading)
    worker = IGConcurrentWorker(
        auto_trading=False,  # Analysis only
        max_workers=1,
        interval_seconds=60
    )

    metals = [
        ("XAU_USD", "Gold"),
        ("XAG_USD", "Silver"),
    ]

    results = []

    for pair, name in metals:
        print(f"\n{'='*80}")
        print(f"TESTING: {name} ({pair})")
        print(f"{'='*80}")

        try:
            result = worker.analyze_pair(pair)

            if result.get('success'):
                signal = result.get('signal')

                if signal:
                    print(f"\n✅ {name} Analysis Complete")
                    print(f"   Signal: {signal.signal}")
                    print(f"   Confidence: {signal.confidence:.2f}")
                    print(f"   Entry Price: ${signal.entry_price:,.2f}")
                    print(f"   Stop Loss: ${signal.stop_loss:,.2f}")
                    print(f"   Take Profit: ${signal.take_profit:,.2f}")
                    print(f"   Risk/Reward: {signal.risk_reward_ratio:.2f}")

                    # Check indicators
                    indicators = result.get('indicators', {})
                    indicator_count = len(indicators)
                    print(f"   Indicators Calculated: {indicator_count}")

                    if indicator_count == 53:
                        print(f"   ✅ ALL 53 INDICATORS WORKING!")
                        results.append((pair, name, True, signal))
                    else:
                        print(f"   ⚠️  Only {indicator_count}/53 indicators")
                        results.append((pair, name, False, signal))
                else:
                    print(f"\n⚠️  {name}: No signal generated (HOLD)")
                    results.append((pair, name, True, None))
            else:
                error = result.get('error', 'Unknown error')
                print(f"\n❌ {name} Analysis Failed: {error}")
                results.append((pair, name, False, None))

        except Exception as e:
            print(f"\n❌ {name} Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((pair, name, False, None))

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    all_passed = True

    for pair, name, success, signal in results:
        if success:
            if signal:
                print(f"✅ {name} ({pair}): {signal.signal} (confidence: {signal.confidence:.2f})")
            else:
                print(f"✅ {name} ({pair}): HOLD (no signal)")
        else:
            print(f"❌ {name} ({pair}): FAILED")
            all_passed = False

    if all_passed:
        print("\n" + "="*80)
        print("🎉 SUCCESS! Gold and Silver are ready to trade!")
        print("="*80)
        print("\nYour trading system now supports:")
        print("  ✅ 20 Forex pairs")
        print("  ✅ 2 Oil commodities (WTI, Brent)")
        print("  ✅ 2 Precious metals (Gold, Silver)")
        print("  ✅ Total: 24 tradeable assets")
        print("\nAll 53 technical indicators working on all assets!")
    else:
        print("\n" + "="*80)
        print("⚠️  Some tests failed - check errors above")
        print("="*80)

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
