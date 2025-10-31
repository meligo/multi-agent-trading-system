"""Main entry point for the trading system."""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from .core.config import load_config
from .core.state import create_initial_state
from .core.memory import MemoryManager
from .core.logging_config import setup_logging, get_logger
from .tools.toolkit import Toolkit

logger = get_logger(__name__)


def analyze_stock(
    ticker: str,
    trade_date: Optional[str] = None,
    config_path: Optional[str] = None,
    env: str = "default"
) -> dict:
    """
    Analyze a stock using the multi-agent system.

    Args:
        ticker: Stock ticker symbol
        trade_date: Date for analysis (defaults to yesterday)
        config_path: Path to configuration file
        env: Environment (default, development, production)

    Returns:
        Analysis results
    """
    # Load configuration
    config = load_config(config_path=config_path, env=env)
    setup_logging(level=config.observability.log_level)

    logger.info(f"Starting analysis for {ticker}")

    # Default to yesterday if no date provided
    if not trade_date:
        trade_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Initialize components
    memory_manager = MemoryManager(config)
    toolkit = Toolkit(config)

    # Create initial state
    state = create_initial_state(ticker=ticker, trade_date=trade_date)

    # TODO: Build and execute the workflow graph
    # This is where the LangGraph workflow would be constructed and run
    logger.info("Workflow execution not yet implemented")

    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "status": "pending_implementation",
        "message": "Full workflow implementation coming soon"
    }


def main():
    """Command-line entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-Agent Trading System"
    )
    parser.add_argument(
        "ticker",
        type=str,
        help="Stock ticker symbol"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Trade date (YYYY-MM-DD), defaults to yesterday"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--env",
        type=str,
        default="default",
        choices=["default", "development", "production"],
        help="Environment"
    )

    args = parser.parse_args()

    try:
        result = analyze_stock(
            ticker=args.ticker,
            trade_date=args.date,
            config_path=args.config,
            env=args.env
        )

        print(f"\nAnalysis Result:")
        print(f"Ticker: {result['ticker']}")
        print(f"Date: {result['trade_date']}")
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")

        return 0

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
