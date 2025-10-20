"""
Options data provider using yfinance.
Provides options chains, implied volatility, Greeks, and related metrics.
"""

from typing import Annotated, Optional, Dict, List
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm


def get_options_chain(
    symbol: Annotated[str, "ticker symbol of the company"],
    expiration_date: Annotated[
        str, "Specific expiration date (YYYY-MM-DD), or 'next' for nearest expiration"
    ] = "next",
):
    """
    Get the full options chain (calls and puts) for a given symbol and expiration.

    Returns:
        Formatted string with calls and puts data including:
        - Strike prices
        - Last price, bid, ask
        - Volume and open interest
        - Implied volatility
        - In-the-money status
    """
    try:
        ticker = yf.Ticker(symbol.upper())

        # Get available expiration dates
        expirations = ticker.options

        if not expirations:
            return f"No options data available for {symbol}"

        # Select expiration date
        if expiration_date == "next":
            selected_exp = expirations[0]
        else:
            # Try to find exact match or closest date
            selected_exp = None
            for exp in expirations:
                if exp == expiration_date:
                    selected_exp = exp
                    break

            if not selected_exp:
                # Find closest date
                exp_dates = [datetime.strptime(exp, "%Y-%m-%d") for exp in expirations]
                target_date = datetime.strptime(expiration_date, "%Y-%m-%d")
                closest_idx = min(range(len(exp_dates)), key=lambda i: abs(exp_dates[i] - target_date))
                selected_exp = expirations[closest_idx]

        # Get options chain
        opt = ticker.option_chain(selected_exp)
        calls = opt.calls
        puts = opt.puts

        # Get current stock price for reference
        current_price = ticker.history(period="1d")["Close"].iloc[-1]

        # Format output
        output = f"# Options Chain for {symbol.upper()}\n"
        output += f"# Current Stock Price: ${current_price:.2f}\n"
        output += f"# Expiration Date: {selected_exp}\n"
        output += f"# Available Expirations: {', '.join(expirations[:5])}{'...' if len(expirations) > 5 else ''}\n"
        output += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        output += "=== CALLS ===\n"
        if not calls.empty:
            # Select relevant columns
            call_cols = ['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility', 'inTheMoney']
            calls_display = calls[call_cols].copy()
            calls_display['moneyness'] = (current_price / calls_display['strike'] - 1) * 100
            calls_display = calls_display.round(2)
            output += calls_display.to_string() + "\n\n"
        else:
            output += "No call options available\n\n"

        output += "=== PUTS ===\n"
        if not puts.empty:
            # Select relevant columns
            put_cols = ['strike', 'lastPrice', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility', 'inTheMoney']
            puts_display = puts[put_cols].copy()
            puts_display['moneyness'] = (puts_display['strike'] / current_price - 1) * 100
            puts_display = puts_display.round(2)
            output += puts_display.to_string() + "\n\n"
        else:
            output += "No put options available\n\n"

        return output

    except Exception as e:
        return f"Error fetching options chain for {symbol}: {str(e)}"


def get_historical_volatility(
    symbol: Annotated[str, "ticker symbol of the company"],
    period_days: Annotated[int, "Number of days to calculate historical volatility"] = 30,
    end_date: Annotated[str, "End date in YYYY-MM-DD format (default: today)"] = None,
) -> str:
    """
    Calculate historical volatility (standard deviation of returns) over a specified period.

    Returns annualized volatility percentage.
    """
    try:
        ticker = yf.Ticker(symbol.upper())

        # Determine date range
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end = datetime.now()

        start = end - timedelta(days=period_days + 10)  # Extra days to ensure enough data

        # Fetch historical data
        hist = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

        if hist.empty or len(hist) < period_days:
            return f"Insufficient data to calculate {period_days}-day historical volatility for {symbol}"

        # Calculate daily returns
        hist = hist.tail(period_days)
        returns = np.log(hist['Close'] / hist['Close'].shift(1)).dropna()

        # Calculate annualized volatility (assuming 252 trading days)
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)

        # Also calculate some percentile info
        vol_20d = returns.tail(20).std() * np.sqrt(252) if len(returns) >= 20 else None

        output = f"# Historical Volatility for {symbol.upper()}\n"
        output += f"# Period: {period_days} days ending {end.strftime('%Y-%m-%d')}\n"
        output += f"# Annualized Volatility: {annual_vol*100:.2f}%\n"
        if vol_20d:
            output += f"# Recent 20-day Annualized Volatility: {vol_20d*100:.2f}%\n"
        output += f"# Daily Volatility: {daily_vol*100:.2f}%\n"
        output += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        return output

    except Exception as e:
        return f"Error calculating historical volatility for {symbol}: {str(e)}"


def get_implied_volatility_rank(
    symbol: Annotated[str, "ticker symbol of the company"],
    current_date: Annotated[str, "Current date in YYYY-MM-DD format"] = None,
) -> str:
    """
    Calculate IV Rank: where current IV stands relative to its 52-week range.
    IV Rank = (Current IV - 52w Low IV) / (52w High IV - 52w Low IV) * 100

    Also provides IV Percentile and current ATM implied volatility.
    """
    try:
        ticker = yf.Ticker(symbol.upper())

        # Get current options data
        expirations = ticker.options
        if not expirations:
            return f"No options data available for {symbol}"

        # Use 30-45 day expiration (most liquid and representative)
        target_days = 30
        current = datetime.now() if not current_date else datetime.strptime(current_date, "%Y-%m-%d")

        selected_exp = None
        min_diff = float('inf')
        for exp in expirations:
            exp_date = datetime.strptime(exp, "%Y-%m-%d")
            days_diff = (exp_date - current).days
            if 20 <= days_diff <= 60 and abs(days_diff - target_days) < min_diff:
                min_diff = abs(days_diff - target_days)
                selected_exp = exp

        if not selected_exp:
            selected_exp = expirations[0]

        opt = ticker.option_chain(selected_exp)

        # Get current stock price
        current_price = ticker.history(period="1d")["Close"].iloc[-1]

        # Find ATM option IV (closest to current price)
        calls = opt.calls
        if calls.empty:
            return f"No options data available for {symbol}"

        atm_idx = (calls['strike'] - current_price).abs().idxmin()
        current_iv = calls.loc[atm_idx, 'impliedVolatility']

        # Calculate 52-week IV range (approximate using historical data)
        # In production, you'd store historical IV data
        # For now, we'll use a simplified approach with historical volatility as proxy
        end = current
        start = end - timedelta(days=365)

        hist = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

        if hist.empty or len(hist) < 100:
            return f"Insufficient historical data to calculate IV rank for {symbol}"

        # Calculate rolling 30-day HV as IV proxy over the year
        returns = np.log(hist['Close'] / hist['Close'].shift(1)).dropna()
        rolling_vol = returns.rolling(window=30).std() * np.sqrt(252)

        iv_low = rolling_vol.min()
        iv_high = rolling_vol.max()

        # Calculate IV Rank
        if iv_high > iv_low:
            iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
        else:
            iv_rank = 50.0  # Default if no range

        # Calculate IV Percentile (what % of days had lower IV)
        iv_percentile = (rolling_vol < current_iv).sum() / len(rolling_vol) * 100

        output = f"# Implied Volatility Analysis for {symbol.upper()}\n"
        output += f"# Current Stock Price: ${current_price:.2f}\n"
        output += f"# Using Expiration: {selected_exp}\n"
        output += f"# Current ATM Implied Volatility: {current_iv*100:.2f}%\n"
        output += f"# 52-Week IV Range: {iv_low*100:.2f}% - {iv_high*100:.2f}%\n"
        output += f"# IV Rank: {iv_rank:.1f} (0=lowest in year, 100=highest)\n"
        output += f"# IV Percentile: {iv_percentile:.1f}%\n"
        output += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        if iv_rank > 75:
            output += "Interpretation: IV is VERY HIGH (top 25% of yearly range) - consider selling premium\n"
        elif iv_rank > 50:
            output += "Interpretation: IV is ELEVATED (above median) - neutral to selling premium\n"
        elif iv_rank > 25:
            output += "Interpretation: IV is MODERATE (below median) - neutral conditions\n"
        else:
            output += "Interpretation: IV is LOW (bottom 25% of yearly range) - consider buying premium\n"

        return output

    except Exception as e:
        return f"Error calculating IV rank for {symbol}: {str(e)}"


def calculate_greeks(
    symbol: Annotated[str, "ticker symbol of the company"],
    strike: Annotated[float, "Option strike price"],
    expiration_date: Annotated[str, "Expiration date in YYYY-MM-DD format"],
    option_type: Annotated[str, "Option type: 'call' or 'put'"],
    current_date: Annotated[str, "Current date in YYYY-MM-DD format (default: today)"] = None,
) -> str:
    """
    Calculate option Greeks using Black-Scholes model.

    Returns: Delta, Gamma, Theta, Vega, Rho

    Note: Uses yfinance data for stock price and implied volatility.
    Risk-free rate is approximated (in production, use actual treasury rates).
    """
    try:
        ticker = yf.Ticker(symbol.upper())

        # Get current stock price
        current_price = ticker.history(period="1d")["Close"].iloc[-1]

        # Get options data for IV
        opt = ticker.option_chain(expiration_date)

        if option_type.lower() == 'call':
            options_df = opt.calls
        else:
            options_df = opt.puts

        # Find the specific option
        option_row = options_df[options_df['strike'] == strike]

        if option_row.empty:
            return f"No {option_type} option found at strike ${strike} for {symbol}"

        iv = option_row.iloc[0]['impliedVolatility']
        option_price = option_row.iloc[0]['lastPrice']

        # Calculate time to expiration
        if current_date:
            current = datetime.strptime(current_date, "%Y-%m-%d")
        else:
            current = datetime.now()

        exp = datetime.strptime(expiration_date, "%Y-%m-%d")
        time_to_exp = (exp - current).days / 365.0

        if time_to_exp <= 0:
            return f"Option has already expired or expires today"

        # Risk-free rate (approximate - in production use actual rates)
        risk_free_rate = 0.05  # 5% assumption

        # Black-Scholes Greeks
        S = current_price
        K = strike
        T = time_to_exp
        r = risk_free_rate
        sigma = iv

        # Calculate d1 and d2
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type.lower() == 'call':
            # Call Greeks
            delta = norm.cdf(d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                    - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365  # Daily theta
            rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100  # Per 1% change
        else:
            # Put Greeks
            delta = norm.cdf(d1) - 1
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                    + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365  # Daily theta
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100  # Per 1% change

        # Gamma and Vega are same for calls and puts
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100  # Per 1% change in IV

        output = f"# Greeks for {symbol.upper()} ${strike} {option_type.upper()}\n"
        output += f"# Expiration: {expiration_date} ({time_to_exp*365:.0f} days)\n"
        output += f"# Current Stock Price: ${S:.2f}\n"
        output += f"# Strike Price: ${K:.2f}\n"
        output += f"# Implied Volatility: {sigma*100:.2f}%\n"
        output += f"# Option Price: ${option_price:.2f}\n"
        output += f"# Moneyness: {((S/K - 1)*100):+.2f}%\n\n"

        output += "=== GREEKS ===\n"
        output += f"Delta: {delta:.4f} (${delta*100:.2f} change per $1 stock move)\n"
        output += f"Gamma: {gamma:.4f} (delta changes by {gamma:.4f} per $1 stock move)\n"
        output += f"Theta: {theta:.4f} (${theta*100:.2f} time decay per day)\n"
        output += f"Vega: {vega:.4f} (${vega*100:.2f} change per 1% IV move)\n"
        output += f"Rho: {rho:.4f} (${rho*100:.2f} change per 1% interest rate move)\n\n"

        output += "=== INTERPRETATIONS ===\n"
        output += f"Directional Exposure: {'Bullish' if delta > 0 else 'Bearish'} (delta={delta:.2f})\n"
        output += f"Gamma Risk: {'High' if abs(gamma) > 0.01 else 'Moderate' if abs(gamma) > 0.005 else 'Low'}\n"
        output += f"Time Decay: ${abs(theta)*100:.2f}/day {'(losing)' if theta < 0 else '(gaining)'}\n"
        output += f"IV Sensitivity: {'High' if vega > 0.2 else 'Moderate' if vega > 0.1 else 'Low'}\n"

        return output

    except Exception as e:
        return f"Error calculating Greeks for {symbol}: {str(e)}"


def get_options_summary(
    symbol: Annotated[str, "ticker symbol of the company"],
    current_date: Annotated[str, "Current date in YYYY-MM-DD format (default: today)"] = None,
) -> str:
    """
    Get a comprehensive options trading summary including:
    - Current stock price and trend
    - IV rank and percentile
    - Most liquid options expirations
    - ATM option prices and Greeks
    - Put/Call ratio
    - Unusual options activity indicators

    This is a high-level tool for the options analyst agent.
    """
    try:
        ticker = yf.Ticker(symbol.upper())

        # Current date
        if current_date:
            current = datetime.strptime(current_date, "%Y-%m-%d")
        else:
            current = datetime.now()

        # Get current stock info
        hist = ticker.history(period="5d")
        if hist.empty:
            return f"No data available for {symbol}"

        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) >= 2 else current_price
        price_change = ((current_price / prev_price) - 1) * 100

        # Get options expirations
        expirations = ticker.options
        if not expirations:
            return f"No options data available for {symbol}"

        # Analyze nearest expiration for liquid strikes
        opt = ticker.option_chain(expirations[0])
        calls = opt.calls
        puts = opt.puts

        if calls.empty or puts.empty:
            return f"Incomplete options data for {symbol}"

        # Find ATM strikes
        atm_call_idx = (calls['strike'] - current_price).abs().idxmin()
        atm_put_idx = (puts['strike'] - current_price).abs().idxmin()

        atm_call = calls.loc[atm_call_idx]
        atm_put = puts.loc[atm_put_idx]

        # Calculate Put/Call ratio
        total_call_vol = calls['volume'].sum()
        total_put_vol = puts['volume'].sum()
        put_call_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else 0

        # Calculate total open interest
        total_call_oi = calls['openInterest'].sum()
        total_put_oi = puts['openInterest'].sum()

        # Get IV info
        current_iv = atm_call['impliedVolatility']

        # Format output
        output = f"# OPTIONS SUMMARY: {symbol.upper()}\n"
        output += f"# Date: {current.strftime('%Y-%m-%d')}\n"
        output += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        output += "=== STOCK INFORMATION ===\n"
        output += f"Current Price: ${current_price:.2f}\n"
        output += f"Daily Change: {price_change:+.2f}%\n\n"

        output += "=== VOLATILITY ===\n"
        output += f"ATM Implied Volatility: {current_iv*100:.2f}%\n"

        # Quick HV calculation
        returns = np.log(hist['Close'] / hist['Close'].shift(1)).dropna()
        if len(returns) >= 2:
            recent_hv = returns.std() * np.sqrt(252)
            output += f"Recent Historical Volatility: {recent_hv*100:.2f}%\n"
            output += f"IV vs HV: {((current_iv/recent_hv - 1)*100):+.2f}%\n"
        output += "\n"

        output += "=== OPTIONS ACTIVITY ===\n"
        output += f"Put/Call Volume Ratio: {put_call_ratio:.2f} "
        if put_call_ratio > 1.5:
            output += "(Bearish - High put buying)\n"
        elif put_call_ratio < 0.67:
            output += "(Bullish - High call buying)\n"
        else:
            output += "(Neutral)\n"

        output += f"Total Call Volume: {total_call_vol:,.0f}\n"
        output += f"Total Put Volume: {total_put_vol:,.0f}\n"
        output += f"Total Call Open Interest: {total_call_oi:,.0f}\n"
        output += f"Total Put Open Interest: {total_put_oi:,.0f}\n\n"

        output += "=== ATM OPTIONS (Nearest Expiration) ===\n"
        output += f"Expiration: {expirations[0]}\n"
        output += f"\nATM Call (${atm_call['strike']:.2f}):\n"
        output += f"  Price: ${atm_call['lastPrice']:.2f}\n"
        output += f"  Bid/Ask: ${atm_call['bid']:.2f}/${atm_call['ask']:.2f}\n"
        output += f"  Volume: {atm_call['volume']:,.0f}\n"
        output += f"  Open Interest: {atm_call['openInterest']:,.0f}\n"
        output += f"  IV: {atm_call['impliedVolatility']*100:.2f}%\n"

        output += f"\nATM Put (${atm_put['strike']:.2f}):\n"
        output += f"  Price: ${atm_put['lastPrice']:.2f}\n"
        output += f"  Bid/Ask: ${atm_put['bid']:.2f}/${atm_put['ask']:.2f}\n"
        output += f"  Volume: {atm_put['volume']:,.0f}\n"
        output += f"  Open Interest: {atm_put['openInterest']:,.0f}\n"
        output += f"  IV: {atm_put['impliedVolatility']*100:.2f}%\n\n"

        output += "=== AVAILABLE EXPIRATIONS ===\n"
        output += f"Near-term: {', '.join(expirations[:3])}\n"
        output += f"Total expirations available: {len(expirations)}\n"

        return output

    except Exception as e:
        return f"Error generating options summary for {symbol}: {str(e)}"
