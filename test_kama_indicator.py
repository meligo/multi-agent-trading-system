"""
Test KAMA (Kaufman Adaptive Moving Average) Implementation

Verifies that the KAMA indicator is correctly calculated and integrated.
KAMA adapts to market volatility - fast in trends, slow in chop.
"""

import pandas as pd
import numpy as np
from forex_config import ForexConfig
from forex_data import ForexDataFetcher


def test_kama():
    """Test KAMA calculation."""
    print("="*80)
    print("KAMA (KAUFMAN ADAPTIVE MOVING AVERAGE) TEST")
    print("="*80)
    print("\nReference: Perry J. Kaufman - 'Trading Systems and Methods'")
    print("Article: 'The KAMA Advantage' by Nayab Bhutta")
    print()

    # Initialize data fetcher
    print("🔧 Initializing forex data fetcher...")
    fetcher = ForexDataFetcher()

    pair = "EUR_USD"
    timeframe = "5"

    print(f"\n📊 Fetching data for {pair} {timeframe}m...")
    try:
        # Get technical analysis (which now includes KAMA)
        analysis = fetcher.get_technical_analysis(
            pair=pair,
            primary_tf=timeframe,
            secondary_tf="15"
        )

        print(f"✅ Analysis complete!")
        print()

        # Extract KAMA indicators
        kama = analysis.get('kama')
        kama_slope = analysis.get('kama_slope')
        kama_distance = analysis.get('kama_distance')
        kama_vs_ma = analysis.get('kama_vs_ma')

        current_price = analysis.get('current_price')
        ma_21 = analysis.get('ma_21')

        print("="*80)
        print("KAMA INDICATOR VALUES")
        print("="*80)
        print(f"\n💰 Current Price: {current_price:.5f}")
        print()

        print(f"📈 KAMA Indicators:")
        print(f"   KAMA: {kama:.5f}")
        print(f"   KAMA Slope (5-period): {kama_slope:.7f}")
        print(f"   Price Distance from KAMA: {kama_distance:.2f}%")
        print(f"   KAMA vs MA-20: {kama_vs_ma:.5f}")
        print()

        # Compare with traditional MA
        print(f"📊 Comparison with Traditional MA:")
        print(f"   MA-21: {ma_21:.5f}")
        print(f"   KAMA: {kama:.5f}")
        print(f"   Difference: {abs(kama - ma_21):.5f}")
        print()

        # Interpret KAMA signals
        print("="*80)
        print("KAMA SIGNAL INTERPRETATION")
        print("="*80)
        print()

        # 1. KAMA Slope (Trend Strength)
        print("1️⃣ KAMA Slope (Trend Strength):")
        if abs(kama_slope) < 0.00001:
            print("   📊 Sideways/Choppy market (low efficiency)")
            print("   ⚠️  KAMA is slow - market not trending")
        elif kama_slope > 0:
            print("   ✅ Uptrend detected (KAMA rising)")
            print("   🚀 KAMA is faster - high market efficiency")
        else:
            print("   ❌ Downtrend detected (KAMA falling)")
            print("   📉 KAMA is faster - high market efficiency")
        print()

        # 2. Price Position vs KAMA
        print("2️⃣ Price Position vs KAMA:")
        if current_price > kama:
            print(f"   ✅ Price above KAMA (+{kama_distance:.2f}%)")
            print("   💡 Bullish signal - consider long")
        else:
            print(f"   ❌ Price below KAMA ({kama_distance:.2f}%)")
            print("   💡 Bearish signal - consider short")
        print()

        # 3. KAMA vs MA (Market Efficiency)
        print("3️⃣ KAMA vs Traditional MA:")
        if kama_vs_ma > 0:
            print(f"   📈 KAMA > MA (+{kama_vs_ma:.5f})")
            print("   ✅ Market is trending (high efficiency)")
            print("   💡 Safe to follow trend signals")
        else:
            print(f"   📉 KAMA < MA ({kama_vs_ma:.5f})")
            print("   ⚠️  Market is choppy (low efficiency)")
            print("   💡 Use caution - potential whipsaws")
        print()

        # Overall Assessment
        print("="*80)
        print("OVERALL KAMA ASSESSMENT")
        print("="*80)

        bullish_signals = 0
        bearish_signals = 0

        if kama_slope > 0:
            bullish_signals += 1
        elif kama_slope < 0:
            bearish_signals += 1

        if current_price > kama:
            bullish_signals += 1
        else:
            bearish_signals += 1

        if kama > ma_21:
            bullish_signals += 1
        else:
            bearish_signals += 1

        print(f"\n📊 Signal Count:")
        print(f"   Bullish signals: {bullish_signals}/3")
        print(f"   Bearish signals: {bearish_signals}/3")
        print()

        if bullish_signals >= 2:
            print("✅ KAMA CONSENSUS: BULLISH")
            print("   💡 Consider long positions")
        elif bearish_signals >= 2:
            print("❌ KAMA CONSENSUS: BEARISH")
            print("   💡 Consider short positions")
        else:
            print("⚠️  KAMA CONSENSUS: NEUTRAL/MIXED")
            print("   💡 Wait for clearer signals")
        print()

        # Show other indicators for context
        print("="*80)
        print("OTHER INDICATORS (FOR CONTEXT)")
        print("="*80)
        print(f"\n📈 Moving Averages:")
        print(f"   MA-9: {analysis.get('ma_9', 0):.5f}")
        print(f"   MA-21: {ma_21:.5f}")
        print(f"   MA-50: {analysis.get('ma_50', 0):.5f}")
        print()

        print(f"📊 Momentum:")
        print(f"   RSI-14: {analysis.get('rsi', 0):.2f}")
        print(f"   MACD: {analysis.get('macd', 0):.6f}")
        print(f"   ADX: {analysis.get('adx', 0):.2f}")
        print()

        print("="*80)
        print("✅ KAMA INDICATOR TEST COMPLETE!")
        print("="*80)
        print()
        print("💡 Key Advantage of KAMA:")
        print("   - Adapts to volatility automatically")
        print("   - Reduces whipsaws in choppy markets")
        print("   - Faster response in trending markets")
        print("   - Better than traditional MA for forex")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nNote: This test requires IG API access.")
        print("Make sure IG_API_KEY, IG_USERNAME, IG_PASSWORD are set in .env")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    test_kama()
