"""
Forex CLI Analyzer

Command-line tool for quick forex analysis and signal generation.
"""

import argparse
import sys
from datetime import datetime
from typing import Optional
from forex_config import ForexConfig
from forex_agents import ForexTradingSystem, ForexSignal
import time


def print_banner():
    """Print ASCII banner."""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                  FOREX TRADING ANALYZER                        ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()


def print_signal(signal: ForexSignal):
    """Print formatted trading signal."""
    # Determine signal emoji
    if signal.signal == 'BUY':
        emoji = "🟢"
        action = "BUY"
    else:
        emoji = "🔴"
        action = "SELL"

    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                     FOREX TRADING SIGNAL                       ║")
    print("╠═══════════════════════════════════════════════════════════════╣")
    print(f"║ Pair:         {signal.pair:<50}║")
    print(f"║ Signal:       {emoji} {action:<45}║")
    print(f"║ Confidence:   {signal.confidence*100:.0f}%{' '*46}║")
    print("║                                                                ║")
    print(f"║ Entry:        {signal.entry_price:<50.5f}║")
    print(f"║ Stop Loss:    {signal.stop_loss:<25.5f} ({signal.pips_risk:<6.1f} pips){'║':>4}")
    print(f"║ Take Profit:  {signal.take_profit:<25.5f} ({signal.pips_reward:<6.1f} pips){'║':>4}")
    print(f"║ Risk/Reward:  {signal.risk_reward_ratio:.1f}:1{' '*46}║")
    print("║                                                                ║")
    print(f"║ Current Price:  {signal.entry_price:<47.5f}║")
    print("╠═══════════════════════════════════════════════════════════════╣")
    print("║ REASONING                                                      ║")
    print("╠═══════════════════════════════════════════════════════════════╣")
    for reason in signal.reasoning:
        # Wrap long text
        if len(reason) > 60:
            words = reason.split()
            line = "║ • "
            for word in words:
                if len(line) + len(word) + 1 > 63:
                    print(f"{line:<64}║")
                    line = "║   "
                line += word + " "
            if line.strip() != "║":
                print(f"{line:<64}║")
        else:
            print(f"║ • {reason:<60}║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    print(f"Timestamp: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")


def analyze_pair(system: ForexTradingSystem, pair: str, timeframe: str):
    """Analyze a single currency pair."""
    print(f"\nAnalyzing {pair} on {timeframe} chart...")
    print("─" * 65)

    try:
        # Generate signal
        start_time = time.time()
        signal = system.generate_signal(pair, timeframe, '1')
        elapsed = time.time() - start_time

        if signal:
            print_signal(signal)
        else:
            print("\n❌ No tradeable signal generated (HOLD)")
            print("   Market conditions not favorable for entry.")
            print()

        print(f"Analysis Time: {elapsed:.1f} seconds")

    except Exception as e:
        print(f"\n❌ Error analyzing {pair}: {e}")
        return


def analyze_all(system: ForexTradingSystem, timeframe: str):
    """Analyze all configured pairs."""
    print("\nAnalyzing all currency pairs (forex + commodities)...")
    print("═" * 65)

    signals = system.batch_analyze(ForexConfig.ALL_PAIRS)

    if signals:
        print(f"\n✓ Found {len(signals)} trading signals:\n")
        for signal in signals:
            print(f"  {signal}")
            print()
    else:
        print("\n❌ No trading signals found (all HOLD)")


def monitor_pair(system: ForexTradingSystem, pair: str, timeframe: str, interval: int):
    """Continuously monitor a pair."""
    print(f"\n🔍 Monitoring {pair} (refresh every {interval}s)")
    print("   Press Ctrl+C to stop...")
    print("═" * 65)

    try:
        while True:
            # Clear previous output (optional)
            print("\n" + "─" * 65)
            print(f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("─" * 65)

            analyze_pair(system, pair, timeframe)

            print(f"\nNext update in {interval} seconds...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n✓ Monitoring stopped.")


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Forex Trading Signal Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze EUR/USD on 5-minute chart
  python forex_analyzer.py --pair EUR_USD --timeframe 5m

  # Analyze Gold (commodity)
  python forex_analyzer.py --pair XAU_USD --timeframe 5m

  # Analyze all pairs (20 forex + 4 commodities)
  python forex_analyzer.py --all

  # Monitor GBP/USD with 60-second refresh
  python forex_analyzer.py --pair GBP_USD --monitor --interval 60

  # Quick analysis of priority pairs (includes XAU_USD)
  python forex_analyzer.py --priority
        """
    )

    parser.add_argument(
        '--pair',
        type=str,
        help='Currency pair to analyze (e.g., EUR_USD)'
    )

    parser.add_argument(
        '--timeframe',
        type=str,
        default='5m',
        choices=['1m', '5m', '15m'],
        help='Timeframe for analysis (default: 5m)'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Analyze all configured pairs'
    )

    parser.add_argument(
        '--priority',
        action='store_true',
        help='Analyze priority pairs only'
    )

    parser.add_argument(
        '--monitor',
        action='store_true',
        help='Continuously monitor the pair'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Monitoring refresh interval in seconds (default: 60)'
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Initialize system
    print("Initializing Forex Trading System...")
    try:
        system = ForexTradingSystem(
            api_key=ForexConfig.FINNHUB_API_KEY,
            openai_api_key=ForexConfig.OPENAI_API_KEY
        )
        print("✓ System initialized")
    except Exception as e:
        print(f"❌ Error initializing system: {e}")
        sys.exit(1)

    # Extract timeframe
    tf_map = {'1m': '1', '5m': '5', '15m': '15'}
    timeframe = tf_map.get(args.timeframe, '5')

    # Route to appropriate function
    if args.all:
        analyze_all(system, timeframe)
    elif args.priority:
        print("\nAnalyzing priority pairs...")
        print("═" * 65)
        signals = system.batch_analyze(ForexConfig.PRIORITY_PAIRS)
        if signals:
            print(f"\n✓ Found {len(signals)} trading signals")
        else:
            print("\n❌ No trading signals found")
    elif args.pair:
        if args.monitor:
            monitor_pair(system, args.pair, timeframe, args.interval)
        else:
            analyze_pair(system, args.pair, timeframe)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
