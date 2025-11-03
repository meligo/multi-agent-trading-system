#!/usr/bin/env python3
"""
Scalping Engine CLI

Command-line interface for the fast momentum scalping system.

Usage:
    python scalping_cli.py --run          # Start scalping engine
    python scalping_cli.py --test PAIR    # Test analysis on single pair
    python scalping_cli.py --config       # Show configuration
    python scalping_cli.py --backtest     # Run historical backtest (TODO)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from scalping_config import ScalpingConfig
from scalping_engine import ScalpingEngine
from forex_data import ForexAnalyzer  # Use existing forex data fetcher


def print_banner():
    """Print ASCII banner."""
    print("\n" + "="*80)
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                    SCALPING ENGINE v1.0                        ║
    ║              Fast Momentum Scalping System                     ║
    ║                  10-20 Minute Trades                           ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    print("="*80 + "\n")


def show_config():
    """Display current configuration."""
    print_banner()
    ScalpingConfig.display()
    print("\nConfiguration file: scalping_config.py")
    print("Modify settings there to customize the strategy.")


def test_pair(pair: str):
    """Test analysis on a single pair without executing."""
    print_banner()
    print(f"🧪 TESTING ANALYSIS: {pair}")
    print("="*80 + "\n")

    try:
        # Initialize engine
        print("Initializing engine...")
        engine = ScalpingEngine()

        # Set up data fetcher
        from unified_data_fetcher import UnifiedDataFetcher
        from data_hub import get_data_hub_from_env
        from scalping_config import ScalpingConfig

        # Initialize DataHub
        data_hub = get_data_hub_from_env()

        # Initialize unified data fetcher
        data_fetcher = UnifiedDataFetcher(data_hub=data_hub)
        engine.set_data_fetcher(data_fetcher)

        # Run analysis
        scalp_setup = engine.analyze_pair(pair)

        if scalp_setup and scalp_setup.approved:
            print("\n" + "="*80)
            print("✅ SCALP SETUP APPROVED")
            print("="*80)
            print(f"Pair: {scalp_setup.pair}")
            print(f"Direction: {scalp_setup.direction}")
            print(f"Entry: {scalp_setup.entry_price:.5f}")
            print(f"TP: {scalp_setup.take_profit:.5f} (+{ScalpingConfig.TAKE_PROFIT_PIPS} pips)")
            print(f"SL: {scalp_setup.stop_loss:.5f} (-{ScalpingConfig.STOP_LOSS_PIPS} pips)")
            print(f"Confidence: {scalp_setup.confidence*100:.0f}%")
            print(f"Risk Tier: {scalp_setup.risk_tier}")
            print(f"Spread: {scalp_setup.spread:.1f} pips")
            print(f"\nReasoning:")
            for reason in scalp_setup.reasoning:
                print(f"  • {reason}")

            # Run risk management
            print("\n" + "="*80)
            print("⚠️  RISK MANAGEMENT SIMULATION")
            print("="*80)
            execute, position_size = engine.run_risk_management(scalp_setup)

            if execute:
                print(f"\n✅ WOULD EXECUTE:")
                print(f"   Position Size: {position_size:.2f} lots")
                print(f"   Risk: ${position_size * ScalpingConfig.STOP_LOSS_PIPS * 10:.2f}")
                print(f"   Potential Profit: ${position_size * ScalpingConfig.TAKE_PROFIT_PIPS * 10:.2f}")
            else:
                print(f"\n❌ WOULD NOT EXECUTE (failed risk checks)")

        else:
            print("\n❌ No tradeable setup found")
            if scalp_setup:
                print(f"Reason: {scalp_setup.reasoning[0] if scalp_setup.reasoning else 'Unknown'}")

    except KeyboardInterrupt:
        print("\n\n⏹️  Test cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def run_engine():
    """Run the scalping engine (LIVE MODE)."""
    print_banner()

    # Confirm live mode
    print("⚠️  WARNING: You are about to start LIVE SCALPING MODE")
    print(f"   Strategy: Fast Momentum ({ScalpingConfig.MAX_TRADE_DURATION_MINUTES}-min trades)")
    print(f"   Pairs: {', '.join(ScalpingConfig.SCALPING_PAIRS)}")
    print(f"   Max Trades/Day: {ScalpingConfig.MAX_TRADES_PER_DAY}")
    print(f"   Position Size: {ScalpingConfig.TIER1_SIZE} lots (Tier 1)")
    print(f"   Risk per Trade: ~${ScalpingConfig.TIER1_SIZE * ScalpingConfig.STOP_LOSS_PIPS * 10:.2f}")
    print()

    # Check if demo mode
    if ScalpingConfig.IG_DEMO:
        print("✅ DEMO MODE - Using IG Demo Account")
    else:
        print("🚨 LIVE MODE - Using REAL MONEY!")
        response = input("\nType 'CONFIRM' to proceed with LIVE trading: ")
        if response != "CONFIRM":
            print("❌ Cancelled")
            return

    print("\n" + "="*80)
    print("🚀 Starting Scalping Engine...")
    print("="*80 + "\n")

    try:
        # Initialize engine
        engine = ScalpingEngine()

        # Set up data fetcher
        from forex_data import ForexAnalyzer

        print("Connecting to IG Markets...")
        data_fetcher = ForexAnalyzer(
            api_key=ScalpingConfig.IG_API_KEY,
            username=ScalpingConfig.IG_USERNAME,
            password=ScalpingConfig.IG_PASSWORD,
            acc_number=ScalpingConfig.IG_ACC_NUMBER,
            demo=ScalpingConfig.IG_DEMO
        )
        engine.set_data_fetcher(data_fetcher)

        print("✅ Connected")
        print("\nPress Ctrl+C to stop\n")

        # Run engine
        engine.run()

    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping engine...")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scalping Engine - Fast Momentum Scalping System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show configuration
  python scalping_cli.py --config

  # Test analysis on EUR/USD without trading
  python scalping_cli.py --test EUR_USD

  # Start the scalping engine (LIVE)
  python scalping_cli.py --run

  # Run in demo mode (set IG_DEMO=true in .env)
  python scalping_cli.py --run
        """
    )

    parser.add_argument(
        '--config',
        action='store_true',
        help='Show current configuration'
    )

    parser.add_argument(
        '--test',
        type=str,
        metavar='PAIR',
        help='Test analysis on a single pair (e.g., EUR_USD)'
    )

    parser.add_argument(
        '--run',
        action='store_true',
        help='Start the scalping engine (LIVE MODE)'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate configuration only'
    )

    args = parser.parse_args()

    # No arguments - show help
    if not any([args.config, args.test, args.run, args.validate]):
        print_banner()
        parser.print_help()
        return

    # Route to appropriate function
    if args.config:
        show_config()
    elif args.validate:
        print_banner()
        try:
            ScalpingConfig.validate()
            print("✅ Configuration valid")
        except ValueError as e:
            print(f"❌ Configuration errors:\n{e}")
            sys.exit(1)
    elif args.test:
        test_pair(args.test)
    elif args.run:
        run_engine()


if __name__ == "__main__":
    main()
