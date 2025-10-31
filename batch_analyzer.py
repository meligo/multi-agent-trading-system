#!/usr/bin/env python3
"""
Batch Stock Analyzer - Analyze multiple stocks from watchlist.txt

Usage:
    python batch_analyzer.py                    # Analyze all stocks in watchlist.txt
    python batch_analyzer.py --date 2024-09-15  # Use specific date
    python batch_analyzer.py --limit 5          # Analyze only first 5 stocks
    python batch_analyzer.py --parallel 3       # Analyze 3 stocks in parallel
"""

import sys
import os
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box

console = Console()


def load_watchlist(file_path: str = "watchlist.txt") -> List[str]:
    """Load stock tickers from watchlist file."""
    tickers = []

    if not Path(file_path).exists():
        console.print(f"[red]✗ Watchlist file not found: {file_path}[/red]")
        console.print("[yellow]Creating default watchlist.txt...[/yellow]")
        with open(file_path, "w") as f:
            f.write("# Add stock tickers here, one per line\n")
            f.write("NVDA\n")
            f.write("AAPL\n")
            f.write("MSFT\n")
        return ["NVDA", "AAPL", "MSFT"]

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith("#"):
                # Extract ticker (first word before any comment)
                ticker = line.split()[0].split("#")[0].strip().upper()
                if ticker:
                    tickers.append(ticker)

    return tickers


def analyze_stock(ticker: str, trade_date: str) -> Dict:
    """Analyze a single stock and return results."""
    try:
        # Import here to avoid issues with parallel execution
        from main import run_analysis

        start_time = time.time()
        result = run_analysis(ticker, trade_date)
        elapsed_time = time.time() - start_time

        return {
            "ticker": ticker,
            "success": True,
            "signal": result.get("signal", "UNKNOWN"),
            "decision": result.get("final_decision", "No decision"),
            "elapsed_time": elapsed_time,
            "error": None
        }

    except Exception as e:
        return {
            "ticker": ticker,
            "success": False,
            "signal": "ERROR",
            "decision": str(e)[:100],
            "elapsed_time": 0,
            "error": str(e)
        }


def format_results_table(results: List[Dict]) -> Table:
    """Create a formatted table of results."""
    table = Table(
        title="📊 Batch Analysis Results",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta"
    )

    table.add_column("Ticker", style="cyan", justify="center", width=10)
    table.add_column("Signal", justify="center", width=10)
    table.add_column("Decision Summary", style="white", width=60)
    table.add_column("Time", justify="right", width=10)
    table.add_column("Status", justify="center", width=10)

    # Sort by signal priority: BUY > HOLD > SELL > ERROR
    signal_priority = {"BUY": 0, "HOLD": 1, "SELL": 2, "ERROR": 3, "UNKNOWN": 4}
    sorted_results = sorted(results, key=lambda x: signal_priority.get(x["signal"], 5))

    for result in sorted_results:
        ticker = result["ticker"]
        signal = result["signal"]
        decision = result["decision"][:60] if result["decision"] else "N/A"
        elapsed = f"{result['elapsed_time']:.1f}s"

        # Color code signals
        if signal == "BUY":
            signal_style = "[bold green]BUY ⬆[/bold green]"
            status = "[green]✓[/green]"
        elif signal == "SELL":
            signal_style = "[bold red]SELL ⬇[/bold red]"
            status = "[green]✓[/green]"
        elif signal == "HOLD":
            signal_style = "[bold yellow]HOLD ⏸[/bold yellow]"
            status = "[green]✓[/green]"
        elif signal == "ERROR":
            signal_style = "[red]ERROR ✗[/red]"
            status = "[red]✗[/red]"
        else:
            signal_style = "[dim]UNKNOWN ?[/dim]"
            status = "[yellow]?[/yellow]"

        table.add_row(ticker, signal_style, decision, elapsed, status)

    return table


def save_results(results: List[Dict], output_file: str = None):
    """Save results to JSON and CSV files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_file = output_file or f"results/batch_analysis_{timestamp}.json"
    Path(json_file).parent.mkdir(exist_ok=True)

    with open(json_file, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "total_stocks": len(results),
            "successful": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "results": results
        }, f, indent=2)

    # Save CSV
    csv_file = json_file.replace(".json", ".csv")
    with open(csv_file, "w") as f:
        f.write("Ticker,Signal,Decision,Time (s),Status,Error\n")
        for r in results:
            status = "Success" if r["success"] else "Failed"
            error = (r.get("error") or "").replace(",", ";")  # Escape commas, handle None
            decision = (r["decision"] or "").replace(",", ";")[:100]
            f.write(f"{r['ticker']},{r['signal']},{decision},{r['elapsed_time']:.1f},{status},{error}\n")

    console.print(f"\n[green]✓ Results saved:[/green]")
    console.print(f"  JSON: {json_file}")
    console.print(f"  CSV:  {csv_file}")


def main():
    parser = argparse.ArgumentParser(description="Batch analyze stocks from watchlist")
    parser.add_argument("--watchlist", default="watchlist.txt", help="Path to watchlist file")
    parser.add_argument("--date", default=None, help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of stocks to analyze")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel analyses (1=sequential)")
    parser.add_argument("--output", default=None, help="Output file path")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between analyses (seconds)")
    args = parser.parse_args()

    # Setup configuration
    Config.setup()
    Config.validate()

    # Load watchlist
    console.print(Panel.fit("📋 Loading Watchlist", style="bold blue"))
    tickers = load_watchlist(args.watchlist)

    if not tickers:
        console.print("[red]✗ No tickers found in watchlist[/red]")
        return

    if args.limit:
        tickers = tickers[:args.limit]

    console.print(f"[green]✓ Loaded {len(tickers)} tickers:[/green] {', '.join(tickers)}\n")

    # Determine date
    trade_date = args.date or datetime.now().strftime("%Y-%m-%d")
    console.print(f"[cyan]Analysis Date:[/cyan] {trade_date}\n")

    # Analyze stocks
    results = []

    console.print(Panel.fit("🔍 Starting Batch Analysis", style="bold blue"))

    if args.parallel > 1:
        # Parallel execution
        console.print(f"[yellow]Running {args.parallel} analyses in parallel...[/yellow]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Analyzing stocks...", total=len(tickers))

            with ThreadPoolExecutor(max_workers=args.parallel) as executor:
                futures = {executor.submit(analyze_stock, ticker, trade_date): ticker
                          for ticker in tickers}

                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    progress.advance(task)

                    # Show quick result
                    signal_emoji = {"BUY": "⬆", "SELL": "⬇", "HOLD": "⏸", "ERROR": "✗"}.get(result["signal"], "?")
                    console.print(f"  {result['ticker']}: {result['signal']} {signal_emoji}")
    else:
        # Sequential execution
        console.print("[yellow]Running sequential analysis...[/yellow]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Analyzing stocks...", total=len(tickers))

            for i, ticker in enumerate(tickers):
                progress.update(task, description=f"[cyan]Analyzing {ticker}...")
                result = analyze_stock(ticker, trade_date)
                results.append(result)
                progress.advance(task)

                # Show result
                signal_emoji = {"BUY": "⬆", "SELL": "⬇", "HOLD": "⏸", "ERROR": "✗"}.get(result["signal"], "?")
                console.print(f"  {result['ticker']}: {result['signal']} {signal_emoji}")

                # Delay between requests (except for last one)
                if i < len(tickers) - 1 and args.delay > 0:
                    time.sleep(args.delay)

    # Display results table
    console.print("\n")
    table = format_results_table(results)
    console.print(table)

    # Summary statistics
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    buy_signals = sum(1 for r in results if r["signal"] == "BUY")
    sell_signals = sum(1 for r in results if r["signal"] == "SELL")
    hold_signals = sum(1 for r in results if r["signal"] == "HOLD")
    errors = sum(1 for r in results if not r["success"])
    total_time = sum(r["elapsed_time"] for r in results)

    console.print("\n" + "="*80)
    console.print(Panel.fit(
        f"[bold]Summary:[/bold]\n"
        f"Total Analyzed: {total}\n"
        f"Successful: {successful} | Failed: {errors}\n"
        f"[green]BUY: {buy_signals}[/green] | [yellow]HOLD: {hold_signals}[/yellow] | [red]SELL: {sell_signals}[/red]\n"
        f"Total Time: {total_time:.1f}s | Avg: {total_time/total:.1f}s per stock",
        title="📊 Analysis Summary",
        style="bold cyan"
    ))

    # Save results
    save_results(results, args.output)

    console.print("\n[bold green]✓ Batch analysis complete![/bold green]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
