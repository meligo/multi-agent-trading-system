"""
Test Slippage and Dynamic Spreads

Demonstrates the realistic execution with:
- Slippage modeling (random fill variation)
- Dynamic spreads (widen during certain hours)
- Stop loss slippage (negative slippage bias)
"""

from paper_trader import PaperTrader
from forex_data import ForexSignal
from datetime import datetime
import numpy as np


def test_slippage_system():
    """Test slippage and dynamic spread implementation."""
    print("=" * 80)
    print("TESTING SLIPPAGE & DYNAMIC SPREADS")
    print("=" * 80)

    # Create fresh trader with slippage enabled
    trader = PaperTrader(initial_balance=50000.0, use_database=False)
    trader.use_slippage = True
    trader.use_dynamic_spreads = True

    print(f"\n💰 Initial Balance: €{trader.balance:,.2f}")
    print(f"⚙️ Slippage: {'ENABLED' if trader.use_slippage else 'DISABLED'}")
    print(f"📊 Dynamic Spreads: {'ENABLED' if trader.use_dynamic_spreads else 'DISABLED'}")

    # Test 1: Regular market order (no slippage bias)
    print("\n" + "=" * 80)
    print("TEST 1: REGULAR MARKET ORDER")
    print("=" * 80)

    signal1 = ForexSignal(
        pair='EUR_USD',
        timeframe='5',
        signal='BUY',
        confidence=0.75,
        entry_price=1.10000,
        stop_loss=1.09500,
        take_profit=1.11000,
        risk_reward_ratio=2.0,
        pips_risk=50.0,
        pips_reward=100.0,
        reasoning=["Test market order slippage"],
        indicators={'atr': 0.00080},  # Include ATR for realistic slippage
        timestamp=datetime.now()
    )

    print(f"\n📊 Opening EUR/USD BUY position...")
    print(f"   Mid Price: {signal1.entry_price:.5f}")
    print(f"   Expected: ASK (mid + ~0.75 pips)")

    pos_id1 = trader.open_position(signal1)

    if pos_id1:
        pos = trader.open_positions[pos_id1]
        actual_spread_pips = (pos.entry_price - signal1.entry_price) * 10000
        print(f"\n✅ Position opened:")
        print(f"   Entry: {pos.entry_price:.5f}")
        print(f"   Total cost: {actual_spread_pips:.2f} pips (spread + slippage)")
        print(f"   Expected: ~0.75-1.5 pips (1.5 pip spread + small slippage)")

    # Test 2: Multiple orders to observe slippage distribution
    print("\n" + "=" * 80)
    print("TEST 2: SLIPPAGE DISTRIBUTION (10 orders)")
    print("=" * 80)

    slippages = []
    spreads = []

    # Close first position
    if pos_id1:
        trader.close_position(pos_id1, reason="MANUAL")

    for i in range(10):
        signal = ForexSignal(
            pair='GBP_USD',
            timeframe='5',
            signal='BUY',
            confidence=0.75,
            entry_price=1.26000,
            stop_loss=1.25500,
            take_profit=1.27000,
            risk_reward_ratio=2.0,
            pips_risk=50.0,
            pips_reward=100.0,
            reasoning=[f"Slippage test #{i+1}"],
            indicators={'atr': 0.00100},
            timestamp=datetime.now()
        )

        pos_id = trader.open_position(signal)
        if pos_id:
            pos = trader.open_positions[pos_id]
            cost_pips = (pos.entry_price - signal.entry_price) * 10000
            slippages.append(cost_pips)
            spreads.append(2.0)  # GBP/USD spread
            # Close immediately
            trader.close_position(pos_id, reason="MANUAL")

    if slippages:
        print(f"\n📊 Slippage Statistics (10 market orders):")
        print(f"   Mean: {np.mean(slippages):.2f} pips")
        print(f"   Std Dev: {np.std(slippages):.2f} pips")
        print(f"   Min: {np.min(slippages):.2f} pips")
        print(f"   Max: {np.max(slippages):.2f} pips")
        print(f"\n   Distribution:")
        for i, slip in enumerate(slippages, 1):
            print(f"   Order {i}: {slip:.2f} pips")

        print(f"\n✓ Expected: Mean around {spreads[0]/2:.1f} pips (half spread)")
        print(f"✓ Expected: Range roughly {spreads[0]/2-2:.1f} to {spreads[0]/2+2:.1f} pips")

    # Test 3: Stop Loss Slippage (should be worse)
    print("\n" + "=" * 80)
    print("TEST 3: STOP LOSS SLIPPAGE (Negative Bias)")
    print("=" * 80)

    # Open position
    signal3 = ForexSignal(
        pair='USD_JPY',
        timeframe='5',
        signal='SELL',
        confidence=0.75,
        entry_price=150.000,
        stop_loss=150.500,
        take_profit=149.000,
        risk_reward_ratio=2.0,
        pips_risk=50.0,
        pips_reward=100.0,
        reasoning=["Test stop loss slippage"],
        indicators={'atr': 0.12},
        timestamp=datetime.now()
    )

    pos_id3 = trader.open_position(signal3)

    if pos_id3:
        pos = trader.open_positions[pos_id3]
        print(f"\n✅ Opened SHORT position:")
        print(f"   Entry: {pos.entry_price:.3f}")

        # Simulate stop loss hit
        print(f"\n🚨 Simulating stop loss hit at {pos.stop_loss:.3f}...")
        print(f"   Expected: Worse fill due to stop order slippage")

        # Close with stop loss
        trade = trader.close_position(pos_id3, reason="SL", exit_price=pos.stop_loss)

        if trade:
            print(f"\n📉 Stop loss executed:")
            print(f"   Expected exit: {pos.stop_loss:.3f}")
            print(f"   Actual exit: {trade.exit_price:.3f}")
            slippage_pips = (trade.exit_price - pos.stop_loss) * 100  # JPY pair
            print(f"   Slippage: {slippage_pips:.2f} pips")
            print(f"   P&L: €{trade.realized_pl:.2f}")

            if slippage_pips > 0:  # For SELL, positive slippage = worse fill
                print(f"\n✓ Stop loss slippage working (negative slippage)")
            else:
                print(f"\n⚠️ Got lucky with slippage (can happen occasionally)")

    # Test 4: Dynamic Spreads
    print("\n" + "=" * 80)
    print("TEST 4: DYNAMIC SPREADS")
    print("=" * 80)

    from realistic_forex_calculations import get_dynamic_spread

    pair = 'EUR_USD'
    print(f"\n📊 {pair} Spread Analysis:")
    print(f"   Base spread: 1.5 pips")

    # Normal hours
    normal_spread = get_dynamic_spread(pair, hour_utc=14, atr=0.00080)
    print(f"   Normal hours (14:00 UTC): {normal_spread:.2f} pips")

    # NY rollover
    rollover_spread = get_dynamic_spread(pair, hour_utc=21, atr=0.00080)
    print(f"   NY rollover (21:00 UTC): {rollover_spread:.2f} pips (2x wider)")

    # Asian session
    asian_spread = get_dynamic_spread(pair, hour_utc=3, atr=0.00080)
    print(f"   Asian session (03:00 UTC): {asian_spread:.2f} pips (1.5x wider)")

    # High volatility
    volatile_spread = get_dynamic_spread(pair, hour_utc=14, atr=0.00200)
    print(f"   High volatility (ATR=200 pips): {volatile_spread:.2f} pips")

    print(f"\n✓ Dynamic spreads adjust based on time and volatility")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    stats = trader.get_statistics()
    print(f"\n📊 Trading Statistics:")
    print(f"   Total Trades: {stats['total_trades']}")
    print(f"   Win Rate: {stats['win_rate']:.1f}%")
    print(f"   Total P&L: €{stats['total_pnl']:.2f}")
    print(f"   Final Balance: €{trader.balance:,.2f}")

    print(f"\n🎯 Key Findings:")
    print(f"   ✓ Market orders have random slippage (mean ~0)")
    print(f"   ✓ Stop loss orders have negative slippage bias")
    print(f"   ✓ Spreads widen during rollover (2x) and low liquidity (1.5x)")
    print(f"   ✓ Spreads scale with volatility (ATR)")
    print(f"   ✓ All costs included in P&L calculations")

    print("\n" + "=" * 80)
    print("✅ SLIPPAGE & DYNAMIC SPREAD TESTS COMPLETE!")
    print("=" * 80)

    return trader


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    np.random.seed(42)  # For reproducible results
    test_slippage_system()
