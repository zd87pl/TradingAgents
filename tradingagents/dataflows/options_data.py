"""
Options data fetching module for TradingAgents
Supports fetching options chains, Greeks, and implied volatility
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.stats import norm


class OptionsDataFetcher:
    """Fetches and processes options data for analysis"""

    def __init__(self, ticker: str):
        """
        Initialize options data fetcher

        Args:
            ticker: Stock ticker symbol (e.g., 'NFLX', 'AAPL')
        """
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)
        self._stock_price = None
        self._options_expirations = None

    @property
    def stock_price(self) -> float:
        """Get current stock price"""
        if self._stock_price is None:
            try:
                hist = self.stock.history(period="1d")
                if not hist.empty:
                    self._stock_price = hist['Close'].iloc[-1]
                else:
                    # Fallback to info
                    info = self.stock.info
                    self._stock_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            except Exception as e:
                print(f"Error fetching stock price: {e}")
                self._stock_price = 0
        return self._stock_price

    @property
    def options_expirations(self) -> List[str]:
        """Get available options expiration dates"""
        if self._options_expirations is None:
            try:
                self._options_expirations = list(self.stock.options)
            except Exception as e:
                print(f"Error fetching options expirations: {e}")
                self._options_expirations = []
        return self._options_expirations

    def get_options_chain(self, expiration_date: str = None) -> Dict[str, pd.DataFrame]:
        """
        Get options chain for a specific expiration date

        Args:
            expiration_date: Expiration date in 'YYYY-MM-DD' format.
                           If None, uses the nearest expiration.

        Returns:
            Dictionary with 'calls' and 'puts' DataFrames
        """
        try:
            if expiration_date is None:
                if not self.options_expirations:
                    return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
                expiration_date = self.options_expirations[0]

            options = self.stock.option_chain(expiration_date)

            # Add days to expiration
            exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
            days_to_exp = (exp_date - datetime.now()).days

            calls = options.calls.copy()
            puts = options.puts.copy()

            calls['daysToExpiration'] = days_to_exp
            puts['daysToExpiration'] = days_to_exp
            calls['expirationDate'] = expiration_date
            puts['expirationDate'] = expiration_date

            return {'calls': calls, 'puts': puts}

        except Exception as e:
            print(f"Error fetching options chain for {expiration_date}: {e}")
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}

    def get_all_call_options(self, max_expirations: int = 6) -> pd.DataFrame:
        """
        Get all call options across multiple expiration dates

        Args:
            max_expirations: Maximum number of expiration dates to fetch

        Returns:
            DataFrame with all call options
        """
        all_calls = []

        for exp_date in self.options_expirations[:max_expirations]:
            chain = self.get_options_chain(exp_date)
            if not chain['calls'].empty:
                all_calls.append(chain['calls'])

        if all_calls:
            return pd.concat(all_calls, ignore_index=True)
        else:
            return pd.DataFrame()

    def filter_otm_calls(self, calls_df: pd.DataFrame,
                        min_strike_pct: float = 1.0,
                        max_strike_pct: float = 1.3) -> pd.DataFrame:
        """
        Filter out-of-the-money (OTM) call options

        Args:
            calls_df: DataFrame of call options
            min_strike_pct: Minimum strike as % of current price (1.0 = at the money)
            max_strike_pct: Maximum strike as % of current price (1.3 = 30% OTM)

        Returns:
            Filtered DataFrame
        """
        if calls_df.empty:
            return calls_df

        current_price = self.stock_price
        min_strike = current_price * min_strike_pct
        max_strike = current_price * max_strike_pct

        filtered = calls_df[
            (calls_df['strike'] >= min_strike) &
            (calls_df['strike'] <= max_strike)
        ].copy()

        # Add moneyness indicator
        filtered['moneyness'] = filtered['strike'] / current_price
        filtered['currentStockPrice'] = current_price

        return filtered

    def calculate_black_scholes_greeks(self,
                                       strike: float,
                                       time_to_exp: float,
                                       volatility: float,
                                       option_type: str = 'call') -> Dict[str, float]:
        """
        Calculate Black-Scholes Greeks

        Args:
            strike: Strike price
            time_to_exp: Time to expiration in years
            volatility: Implied volatility (as decimal, e.g., 0.25 for 25%)
            option_type: 'call' or 'put'

        Returns:
            Dictionary with delta, gamma, vega, theta, rho
        """
        S = self.stock_price
        K = strike
        T = time_to_exp
        sigma = volatility
        r = 0.05  # Risk-free rate (5%)

        if T <= 0 or sigma <= 0:
            return {
                'delta': 0.0,
                'gamma': 0.0,
                'vega': 0.0,
                'theta': 0.0,
                'rho': 0.0
            }

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type == 'call':
            delta = norm.cdf(d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                    - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
            rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
        else:  # put
            delta = -norm.cdf(-d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                    + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100

        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100

        return {
            'delta': round(delta, 4),
            'gamma': round(gamma, 6),
            'vega': round(vega, 4),
            'theta': round(theta, 4),
            'rho': round(rho, 4)
        }

    def enrich_options_with_greeks(self, options_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add calculated Greeks to options DataFrame

        Args:
            options_df: Options DataFrame

        Returns:
            DataFrame with added Greek columns
        """
        if options_df.empty:
            return options_df

        enriched = options_df.copy()

        # Calculate Greeks for each option
        greeks_list = []
        for _, row in enriched.iterrows():
            time_to_exp = row['daysToExpiration'] / 365.0
            iv = row.get('impliedVolatility', 0.3)  # Default to 30% if not available

            greeks = self.calculate_black_scholes_greeks(
                strike=row['strike'],
                time_to_exp=time_to_exp,
                volatility=iv,
                option_type='call'
            )
            greeks_list.append(greeks)

        greeks_df = pd.DataFrame(greeks_list)
        enriched = pd.concat([enriched.reset_index(drop=True), greeks_df], axis=1)

        return enriched

    def get_recommended_expirations(self,
                                   min_days: int = 30,
                                   max_days: int = 180) -> List[str]:
        """
        Get recommended expiration dates for options trading

        Args:
            min_days: Minimum days to expiration
            max_days: Maximum days to expiration

        Returns:
            List of expiration dates
        """
        recommended = []

        for exp_date in self.options_expirations:
            exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')
            days = (exp_dt - datetime.now()).days

            if min_days <= days <= max_days:
                recommended.append(exp_date)

        return recommended

    def get_stock_info(self) -> Dict:
        """Get comprehensive stock information"""
        try:
            info = self.stock.info
            return {
                'symbol': self.ticker,
                'currentPrice': self.stock_price,
                'marketCap': info.get('marketCap', 0),
                'peRatio': info.get('trailingPE', 0),
                'forwardPE': info.get('forwardPE', 0),
                'pegRatio': info.get('pegRatio', 0),
                'priceToBook': info.get('priceToBook', 0),
                'beta': info.get('beta', 0),
                'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh', 0),
                'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow', 0),
                'averageVolume': info.get('averageVolume', 0),
                'dividendYield': info.get('dividendYield', 0),
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
            }
        except Exception as e:
            print(f"Error fetching stock info: {e}")
            return {'symbol': self.ticker, 'currentPrice': self.stock_price}


def get_options_data(ticker: str,
                     expiration_date: str = None,
                     option_type: str = 'calls') -> pd.DataFrame:
    """
    Convenience function to get options data

    Args:
        ticker: Stock ticker symbol
        expiration_date: Optional expiration date
        option_type: 'calls' or 'puts'

    Returns:
        DataFrame with options data
    """
    fetcher = OptionsDataFetcher(ticker)
    chain = fetcher.get_options_chain(expiration_date)
    return chain.get(option_type, pd.DataFrame())
