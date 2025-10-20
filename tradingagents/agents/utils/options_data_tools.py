from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_options_chain(
    symbol: Annotated[str, "ticker symbol of the company"],
    expiration_date: Annotated[
        str, "Specific expiration date (YYYY-MM-DD), or 'next' for nearest expiration"
    ] = "next",
) -> str:
    """
    Get the full options chain (calls and puts) for a given symbol and expiration.

    Returns formatted data with:
    - Strike prices
    - Last price, bid, ask spreads
    - Volume and open interest
    - Implied volatility for each strike
    - In-the-money status
    - Moneyness (% from current price)

    Args:
        symbol (str): Ticker symbol (e.g., AAPL, TSLA)
        expiration_date (str): 'next' for nearest, or specific date like '2024-03-15'

    Returns:
        str: Formatted options chain with calls and puts

    Example:
        get_options_chain("AAPL", "next")
        get_options_chain("TSLA", "2024-03-15")
    """
    return route_to_vendor("get_options_chain", symbol, expiration_date)


@tool
def get_historical_volatility(
    symbol: Annotated[str, "ticker symbol of the company"],
    period_days: Annotated[int, "Number of days to calculate historical volatility"] = 30,
    end_date: Annotated[str, "End date in YYYY-MM-DD format (default: today)"] = None,
) -> str:
    """
    Calculate historical volatility (annualized standard deviation of returns).

    Historical volatility measures actual price fluctuations over a past period.
    Compare this to implied volatility to identify opportunities:
    - If IV > HV: Options may be expensive (sell premium)
    - If HV > IV: Options may be cheap (buy premium)

    Args:
        symbol (str): Ticker symbol
        period_days (int): Lookback period (default: 30 days)
        end_date (str): Optional end date, defaults to today

    Returns:
        str: Annualized volatility percentage with recent trends

    Example:
        get_historical_volatility("AAPL", 30)
        get_historical_volatility("NVDA", 60, "2024-01-15")
    """
    if end_date is None:
        return route_to_vendor("get_historical_volatility", symbol, period_days)
    else:
        return route_to_vendor("get_historical_volatility", symbol, period_days, end_date)


@tool
def get_implied_volatility_rank(
    symbol: Annotated[str, "ticker symbol of the company"],
    current_date: Annotated[str, "Current date in YYYY-MM-DD format"] = None,
) -> str:
    """
    Calculate IV Rank and IV Percentile - critical metrics for options strategy selection.

    IV Rank = (Current IV - 52w Low IV) / (52w High IV - 52w Low IV) * 100
    IV Percentile = % of days in past year with IV below current level

    Strategy recommendations:
    - IV Rank > 75: SELL premium (iron condors, credit spreads, covered calls)
    - IV Rank 50-75: NEUTRAL (consider both buyers/sellers strategies)
    - IV Rank 25-50: MODERATE (slight preference for buying)
    - IV Rank < 25: BUY premium (long calls/puts, debit spreads, straddles)

    Args:
        symbol (str): Ticker symbol
        current_date (str): Optional reference date, defaults to today

    Returns:
        str: IV rank, IV percentile, current IV, 52w range, and interpretation

    Example:
        get_implied_volatility_rank("AAPL")
        get_implied_volatility_rank("TSLA", "2024-01-15")
    """
    if current_date is None:
        return route_to_vendor("get_implied_volatility_rank", symbol)
    else:
        return route_to_vendor("get_implied_volatility_rank", symbol, current_date)


@tool
def calculate_greeks(
    symbol: Annotated[str, "ticker symbol of the company"],
    strike: Annotated[float, "Option strike price"],
    expiration_date: Annotated[str, "Expiration date in YYYY-MM-DD format"],
    option_type: Annotated[str, "Option type: 'call' or 'put'"],
    current_date: Annotated[str, "Current date in YYYY-MM-DD format (default: today)"] = None,
) -> str:
    """
    Calculate option Greeks using Black-Scholes model.

    Greeks measure option price sensitivity to various factors:
    - Delta: Change in option price per $1 stock move (directional exposure)
    - Gamma: Rate of delta change (acceleration of option price)
    - Theta: Time decay per day (how much you lose/gain daily)
    - Vega: Sensitivity to 1% IV change (volatility exposure)
    - Rho: Sensitivity to 1% interest rate change

    Use Greeks for:
    - Portfolio hedging (maintain delta neutral)
    - Risk management (avoid excessive gamma/vega)
    - Strategy selection (high theta for sellers, high gamma for scalpers)

    Args:
        symbol (str): Ticker symbol
        strike (float): Strike price (e.g., 175.0)
        expiration_date (str): Expiration like '2024-03-15'
        option_type (str): 'call' or 'put'
        current_date (str): Optional, defaults to today

    Returns:
        str: All Greeks with interpretations and risk metrics

    Example:
        calculate_greeks("AAPL", 180.0, "2024-03-15", "call")
        calculate_greeks("TSLA", 200.0, "2024-04-19", "put")
    """
    if current_date is None:
        return route_to_vendor("calculate_greeks", symbol, strike, expiration_date, option_type)
    else:
        return route_to_vendor("calculate_greeks", symbol, strike, expiration_date, option_type, current_date)


@tool
def get_options_summary(
    symbol: Annotated[str, "ticker symbol of the company"],
    current_date: Annotated[str, "Current date in YYYY-MM-DD format (default: today)"] = None,
) -> str:
    """
    Get a comprehensive options trading summary - USE THIS FIRST for quick overview.

    This is the most important tool for options analysis. It provides:
    - Current stock price and recent trend
    - IV rank and percentile (strategy selection guide)
    - ATM call and put prices with Greeks preview
    - Put/Call ratio (sentiment indicator)
    - Total volume and open interest (liquidity check)
    - Available expirations
    - IV vs HV comparison

    Start with this tool to understand the options landscape, then use specialized
    tools for deeper analysis.

    Args:
        symbol (str): Ticker symbol
        current_date (str): Optional reference date

    Returns:
        str: Comprehensive options summary with all key metrics

    Example:
        get_options_summary("AAPL")
        get_options_summary("NVDA", "2024-01-15")
    """
    if current_date is None:
        return route_to_vendor("get_options_summary", symbol)
    else:
        return route_to_vendor("get_options_summary", symbol, current_date)
