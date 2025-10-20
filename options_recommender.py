#!/usr/bin/env python3
"""
Options Call Recommender
Combines Michael Burry's value investing with momentum analysis
to provide actionable options call recommendations for IBKR

Usage:
    python options_recommender.py TICKER CAPITAL [--date DATE]

Example:
    python options_recommender.py NFLX 10000
    python options_recommender.py AAPL 25000 --date 2024-05-10
"""

import argparse
import sys
from datetime import datetime
from typing import Dict, Optional
import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn

from tradingagents.agents.options.options_strategist import OptionsStrategist
from tradingagents.dataflows.options_data import OptionsDataFetcher
from tradingagents.default_config import DEFAULT_CONFIG


console = Console()


def validate_inputs(ticker: str, capital: float) -> bool:
    """
    Validate input parameters

    Args:
        ticker: Stock ticker symbol
        capital: Capital amount

    Returns:
        True if valid, False otherwise
    """
    if not ticker or len(ticker) > 5:
        console.print("[red]Error: Invalid ticker symbol[/red]")
        return False

    if capital <= 0:
        console.print("[red]Error: Capital must be positive[/red]")
        return False

    if capital < 500:
        console.print("[yellow]Warning: Capital less than $500 may limit options choices[/yellow]")

    return True


def display_stock_overview(fetcher: OptionsDataFetcher):
    """Display stock overview information"""
    info = fetcher.get_stock_info()

    table = Table(title=f"{info['symbol']} Stock Overview")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Current Price", f"${info['currentPrice']:.2f}")
    table.add_row("52-Week High", f"${info.get('fiftyTwoWeekHigh', 0):.2f}")
    table.add_row("52-Week Low", f"${info.get('fiftyTwoWeekLow', 0):.2f}")
    table.add_row("P/E Ratio", f"{info.get('peRatio', 0):.2f}")
    table.add_row("Forward P/E", f"{info.get('forwardPE', 0):.2f}")
    table.add_row("PEG Ratio", f"{info.get('pegRatio', 0):.2f}")
    table.add_row("Price/Book", f"{info.get('priceToBook', 0):.2f}")
    table.add_row("Beta", f"{info.get('beta', 0):.2f}")
    table.add_row("Sector", info.get('sector', 'Unknown'))
    table.add_row("Industry", info.get('industry', 'Unknown'))

    console.print(table)
    console.print()


def display_recommendations_table(recommendations: list):
    """Display recommendations in a table format"""
    table = Table(title="Top Options Call Recommendations")

    table.add_column("Rank", style="cyan", justify="center")
    table.add_column("Strike", style="green")
    table.add_column("Expiration", style="yellow")
    table.add_column("DTE", justify="center")
    table.add_column("Premium", style="magenta")
    table.add_column("Contracts", justify="center")
    table.add_column("Total Cost", style="red")
    table.add_column("Delta", justify="center")
    table.add_column("Score", justify="center")

    for rec in recommendations:
        table.add_row(
            str(rec['rank']),
            f"${rec['strike']:.2f}",
            rec['expiration'],
            str(rec['days_to_expiration']),
            f"${rec['premium']:.2f}",
            str(rec['recommended_contracts']),
            f"${rec['total_cost']:,.0f}",
            f"{rec['delta']:.2f}",
            f"{rec['composite_score']:.0f}"
        )

    console.print(table)
    console.print()


def display_detailed_recommendation(rec: Dict, rank: int):
    """Display detailed recommendation"""
    console.print(Panel(
        f"[bold cyan]Recommendation #{rank}[/bold cyan]\n"
        f"[yellow]{rec['expiration']}[/yellow] ${rec['strike']:.2f} Call",
        expand=False
    ))

    # Position Details
    position_table = Table(show_header=False, box=None)
    position_table.add_column("Field", style="cyan")
    position_table.add_column("Value", style="white")

    position_table.add_row("Strike Price", f"${rec['strike']:.2f} ({rec['moneyness_pct']:.1f}% OTM)")
    position_table.add_row("Premium", f"${rec['premium']:.2f}")
    position_table.add_row("Contracts", str(rec['recommended_contracts']))
    position_table.add_row("Total Cost", f"${rec['total_cost']:,.2f} ({rec['capital_deployed_pct']:.1f}% of capital)")
    position_table.add_row("Break-even", f"${rec['breakeven_price']:.2f} (+{rec['breakeven_pct_move']:.1f}%)")
    position_table.add_row("Max Loss", f"${rec['max_loss']:,.2f}")

    console.print(position_table)
    console.print()

    # Greeks
    greeks_table = Table(title="Greeks")
    greeks_table.add_column("Greek", style="cyan")
    greeks_table.add_column("Value", style="green")
    greeks_table.add_column("Interpretation", style="white")

    greeks_table.add_row(
        "Delta",
        f"{rec['delta']:.3f}",
        f"${rec['delta']:.2f} move per $1 stock move"
    )
    greeks_table.add_row(
        "Theta",
        f"${rec['theta']:.2f}",
        f"Daily time decay"
    )
    greeks_table.add_row(
        "Vega",
        f"{rec['vega']:.2f}",
        f"Sensitivity to volatility"
    )
    greeks_table.add_row(
        "IV",
        f"{rec['implied_volatility']*100:.1f}%",
        "Implied volatility"
    )

    console.print(greeks_table)
    console.print()

    # Profit Scenarios
    scenarios_table = Table(title="Profit/Loss Scenarios")
    scenarios_table.add_column("Scenario", style="cyan")
    scenarios_table.add_column("Target Price", style="yellow")
    scenarios_table.add_column("Move", justify="center")
    scenarios_table.add_column("P/L", justify="right")
    scenarios_table.add_column("ROI", justify="right")

    for scenario_name, scenario in rec['profit_scenarios'].items():
        pl_style = "green" if scenario['profit_loss'] > 0 else "red"
        scenarios_table.add_row(
            scenario_name.replace('_', ' ').title(),
            f"${scenario['target_price']:.2f}",
            f"+{scenario['price_move_pct']:.1f}%",
            f"[{pl_style}]${scenario['profit_loss']:,.0f}[/{pl_style}]",
            f"[{pl_style}]{scenario['roi_pct']:.0f}%[/{pl_style}]"
        )

    console.print(scenarios_table)
    console.print()

    # Rationale
    console.print(Panel(rec['rationale'], title="Trade Rationale", border_style="green"))
    console.print()


def format_for_ibkr(rec: Dict, ticker: str) -> str:
    """
    Format recommendation for IBKR execution

    Args:
        rec: Recommendation dictionary
        ticker: Stock ticker

    Returns:
        Formatted string for IBKR
    """
    ibkr_format = f"""
=== IBKR ORDER DETAILS ===

Ticker: {ticker}
Action: BUY TO OPEN
Option Type: CALL
Strike: ${rec['strike']:.2f}
Expiration: {rec['expiration']}
Quantity: {rec['recommended_contracts']} contracts
Order Type: LIMIT
Limit Price: ${rec['mid_price']:.2f} (or better)

Estimated Total Cost: ${rec['total_cost']:,.2f}

Notes:
- Use LIMIT order, not MARKET order
- Consider placing order at mid-price: ${rec['mid_price']:.2f}
- Current bid/ask: ${rec['bid']:.2f} / ${rec['ask']:.2f}
- Monitor for better fills between bid and mid-price
"""
    return ibkr_format


def save_report(report: str, ticker: str, output_dir: str = "reports"):
    """Save report to file"""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/{ticker}_options_analysis_{timestamp}.md"

    with open(filename, 'w') as f:
        f.write(report)

    console.print(f"[green]Report saved to: {filename}[/green]")
    return filename


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Options Call Recommender - Combining Value & Momentum Analysis"
    )
    parser.add_argument(
        "ticker",
        type=str,
        help="Stock ticker symbol (e.g., NFLX, AAPL)"
    )
    parser.add_argument(
        "capital",
        type=float,
        help="Capital to deploy (e.g., 10000)"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Analysis date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save report to file"
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Simple output without company analysis"
    )

    args = parser.parse_args()

    ticker = args.ticker.upper()
    capital = args.capital

    # Validate inputs
    if not validate_inputs(ticker, capital):
        sys.exit(1)

    # Display header
    console.print(Panel.fit(
        f"[bold cyan]Options Call Recommender[/bold cyan]\n"
        f"Ticker: {ticker}\n"
        f"Capital: ${capital:,.2f}\n"
        f"Date: {args.date}",
        border_style="cyan"
    ))
    console.print()

    try:
        # Step 1: Fetch stock data
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Fetching stock data...", total=None)

            fetcher = OptionsDataFetcher(ticker)

            if fetcher.stock_price == 0:
                console.print(f"[red]Error: Unable to fetch data for {ticker}[/red]")
                sys.exit(1)

            progress.update(task, completed=True)

        # Display stock overview
        display_stock_overview(fetcher)

        # Step 2: Analyze options
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing options chain...", total=None)

            strategist = OptionsStrategist(
                ticker=ticker,
                capital=capital,
                company_analysis=""  # Can be enhanced with LLM analysis
            )

            analysis_results = strategist.analyze_options_chain()
            progress.update(task, completed=True)

        if not analysis_results['success']:
            console.print(f"[red]Error: {analysis_results['error']}[/red]")
            sys.exit(1)

        recommendations = analysis_results['recommendations']

        if not recommendations:
            console.print("[yellow]No suitable options found for the given criteria[/yellow]")
            sys.exit(0)

        # Display summary table
        display_recommendations_table(recommendations)

        # Display detailed recommendations
        for i, rec in enumerate(recommendations[:3], 1):
            display_detailed_recommendation(rec, i)

            # IBKR format
            if i == 1:  # Show IBKR format for top recommendation
                ibkr_text = format_for_ibkr(rec, ticker)
                console.print(Panel(ibkr_text, title="IBKR Order Format (Top Pick)", border_style="yellow"))

        # Generate and optionally save full report
        full_report = strategist.generate_summary_report(analysis_results)

        if args.save:
            filename = save_report(full_report, ticker)
            console.print(f"\n[green]Full analysis saved to: {filename}[/green]")

        # Risk disclaimer
        console.print(Panel(
            "[bold red]RISK DISCLAIMER[/bold red]\n\n"
            "Options trading involves significant risk and is not suitable for all investors.\n"
            "You can lose 100% of your investment. This tool provides analysis only, not investment advice.\n"
            "Past performance does not guarantee future results.\n"
            "Consult with a financial advisor before trading.",
            border_style="red"
        ))

    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
