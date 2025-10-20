#!/usr/bin/env python3
"""
Standalone Options Call Recommender
No external trading agents dependencies required

Usage:
    python options_recommender_standalone.py TICKER CAPITAL

Example:
    python options_recommender_standalone.py NFLX 10000
"""

import argparse
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os

# Core imports
import pandas as pd
import yfinance as yf
from scipy.stats import norm
import numpy as np

# Rich for terminal output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Note: Install 'rich' for better terminal output: pip install rich")


# ============================================================================
# OPTIONS DATA FETCHER
# ============================================================================

class OptionsDataFetcher:
    """Fetches and processes options data for analysis"""

    def __init__(self, ticker: str):
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
        """Get options chain for a specific expiration date"""
        try:
            if expiration_date is None:
                if not self.options_expirations:
                    return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
                expiration_date = self.options_expirations[0]

            options = self.stock.option_chain(expiration_date)
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
        """Get all call options across multiple expiration dates"""
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
        """Filter out-of-the-money (OTM) call options"""
        if calls_df.empty:
            return calls_df

        current_price = self.stock_price
        min_strike = current_price * min_strike_pct
        max_strike = current_price * max_strike_pct

        filtered = calls_df[
            (calls_df['strike'] >= min_strike) &
            (calls_df['strike'] <= max_strike)
        ].copy()

        filtered['moneyness'] = filtered['strike'] / current_price
        filtered['currentStockPrice'] = current_price

        return filtered

    def calculate_black_scholes_greeks(self,
                                       strike: float,
                                       time_to_exp: float,
                                       volatility: float) -> Dict[str, float]:
        """Calculate Black-Scholes Greeks"""
        S = self.stock_price
        K = strike
        T = time_to_exp
        sigma = volatility
        r = 0.05

        if T <= 0 or sigma <= 0:
            return {'delta': 0.0, 'gamma': 0.0, 'vega': 0.0, 'theta': 0.0, 'rho': 0.0}

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        delta = norm.cdf(d1)
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
        rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
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
        """Add calculated Greeks to options DataFrame"""
        if options_df.empty:
            return options_df

        enriched = options_df.copy()
        greeks_list = []

        for _, row in enriched.iterrows():
            time_to_exp = row['daysToExpiration'] / 365.0
            iv = row.get('impliedVolatility', 0.3)
            greeks = self.calculate_black_scholes_greeks(row['strike'], time_to_exp, iv)
            greeks_list.append(greeks)

        greeks_df = pd.DataFrame(greeks_list)
        enriched = pd.concat([enriched.reset_index(drop=True), greeks_df], axis=1)
        return enriched

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
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
            }
        except Exception as e:
            print(f"Error fetching stock info: {e}")
            return {'symbol': self.ticker, 'currentPrice': self.stock_price}


# ============================================================================
# OPTIONS STRATEGIST
# ============================================================================

class OptionsStrategist:
    """Analyzes options chains and recommends optimal call strategies"""

    def __init__(self, ticker: str, capital: float):
        self.ticker = ticker.upper()
        self.capital = capital
        self.fetcher = OptionsDataFetcher(ticker)
        self.stock_price = self.fetcher.stock_price

    def analyze_options_chain(self) -> Dict:
        """Analyze the full options chain and identify optimal strategies"""
        all_calls = self.fetcher.get_all_call_options(max_expirations=8)

        if all_calls.empty:
            return {'success': False, 'error': 'No options data available for this ticker'}

        # Filter for liquid options
        liquid_calls = all_calls[
            (all_calls['volume'] > 10) |
            (all_calls['openInterest'] > 50)
        ].copy()

        if liquid_calls.empty:
            liquid_calls = all_calls.copy()

        # Filter for reasonable strikes (5% to 30% OTM)
        otm_calls = self.fetcher.filter_otm_calls(liquid_calls, min_strike_pct=1.05, max_strike_pct=1.30)

        if otm_calls.empty:
            otm_calls = self.fetcher.filter_otm_calls(liquid_calls, min_strike_pct=0.95, max_strike_pct=1.40)

        # Enrich with Greeks
        enriched_calls = self.fetcher.enrich_options_with_greeks(otm_calls)

        # Score each option
        scored_options = self._score_options(enriched_calls)

        # Get top recommendations
        top_recommendations = self._get_top_recommendations(scored_options)

        return {
            'success': True,
            'stock_price': self.stock_price,
            'total_options_analyzed': len(all_calls),
            'liquid_options': len(liquid_calls),
            'suitable_options': len(scored_options),
            'recommendations': top_recommendations
        }

    def _score_options(self, options_df: pd.DataFrame) -> pd.DataFrame:
        """Score options based on multiple criteria"""
        if options_df.empty:
            return options_df

        scored = options_df.copy()

        # Delta score (prefer 0.30 to 0.70)
        scored['delta_score'] = scored['delta'].apply(
            lambda d: 100 if 0.30 <= d <= 0.70 else
                     80 if 0.20 <= d < 0.30 or 0.70 < d <= 0.80 else
                     50 if 0.10 <= d < 0.20 or 0.80 < d <= 0.90 else 20
        )

        # Time score (prefer 30-120 days)
        scored['time_score'] = scored['daysToExpiration'].apply(
            lambda d: 100 if 30 <= d <= 120 else
                     80 if 20 <= d < 30 or 120 < d <= 180 else
                     50 if 10 <= d < 20 or 180 < d <= 270 else 20
        )

        # Liquidity score
        scored['liquidity'] = scored['volume'].fillna(0) + scored['openInterest'].fillna(0)
        max_liquidity = scored['liquidity'].max()
        if max_liquidity > 0:
            scored['liquidity_score'] = (scored['liquidity'] / max_liquidity * 100).clip(0, 100)
        else:
            scored['liquidity_score'] = 0

        # Spread score
        scored['mid_price'] = (scored['bid'] + scored['ask']) / 2
        scored['spread_pct'] = ((scored['ask'] - scored['bid']) / scored['mid_price'] * 100).fillna(100)
        scored['spread_score'] = scored['spread_pct'].apply(
            lambda s: 100 if s < 3 else 80 if s < 5 else 60 if s < 10 else 40 if s < 15 else 20
        )

        # IV score
        scored['iv'] = scored['impliedVolatility'].fillna(0.3)
        scored['iv_score'] = scored['iv'].apply(
            lambda iv: 100 if 0.20 <= iv <= 0.50 else
                      80 if 0.15 <= iv < 0.20 or 0.50 < iv <= 0.70 else 60
        )

        # Premium efficiency
        scored['premium_pct'] = (scored['lastPrice'] / scored['strike'] * 100).fillna(0)
        scored['premium_score'] = scored['premium_pct'].apply(
            lambda p: 100 if 1 <= p <= 5 else
                     80 if 0.5 <= p < 1 or 5 < p <= 8 else 60
        )

        # Composite score
        scored['composite_score'] = (
            scored['delta_score'] * 0.25 +
            scored['time_score'] * 0.20 +
            scored['liquidity_score'] * 0.20 +
            scored['spread_score'] * 0.15 +
            scored['iv_score'] * 0.10 +
            scored['premium_score'] * 0.10
        )

        return scored.sort_values('composite_score', ascending=False)

    def _get_top_recommendations(self, scored_options: pd.DataFrame, n_recommendations: int = 3) -> List[Dict]:
        """Get top N recommendations with detailed analysis"""
        if scored_options.empty:
            return []

        recommendations = []

        for idx, row in scored_options.head(n_recommendations).iterrows():
            contracts, total_cost, contracts_percentage = self._calculate_position_size(
                row['lastPrice'], row['strike']
            )

            breakeven = row['strike'] + row['lastPrice']
            breakeven_pct = ((breakeven / self.stock_price) - 1) * 100

            profit_scenarios = self._calculate_profit_scenarios(
                row['strike'], row['lastPrice'], contracts, row['daysToExpiration']
            )

            recommendation = {
                'rank': len(recommendations) + 1,
                'strike': row['strike'],
                'expiration': row['expirationDate'],
                'days_to_expiration': row['daysToExpiration'],
                'premium': row['lastPrice'],
                'bid': row['bid'],
                'ask': row['ask'],
                'mid_price': row['mid_price'],
                'current_stock_price': self.stock_price,
                'moneyness': row['moneyness'],
                'moneyness_pct': (row['moneyness'] - 1) * 100,
                'delta': row['delta'],
                'gamma': row['gamma'],
                'vega': row['vega'],
                'theta': row['theta'],
                'implied_volatility': row['iv'],
                'volume': row['volume'],
                'open_interest': row['openInterest'],
                'bid_ask_spread': row['ask'] - row['bid'],
                'spread_pct': row['spread_pct'],
                'recommended_contracts': contracts,
                'total_cost': total_cost,
                'capital_deployed_pct': contracts_percentage,
                'breakeven_price': breakeven,
                'breakeven_pct_move': breakeven_pct,
                'max_loss': total_cost,
                'max_loss_pct': contracts_percentage,
                'profit_scenarios': profit_scenarios,
                'composite_score': row['composite_score'],
                'delta_score': row['delta_score'],
                'time_score': row['time_score'],
                'liquidity_score': row['liquidity_score'],
                'rationale': self._generate_rationale(row, profit_scenarios)
            }

            recommendations.append(recommendation)

        return recommendations

    def _calculate_position_size(self, premium: float, strike: float) -> Tuple[int, float, float]:
        """Calculate recommended position size"""
        max_position_cost = self.capital * 0.075
        cost_per_contract = premium * 100
        max_contracts = int(max_position_cost / cost_per_contract)
        contracts = max(1, max_contracts)
        total_cost = contracts * cost_per_contract
        percentage = (total_cost / self.capital) * 100
        return contracts, total_cost, percentage

    def _calculate_profit_scenarios(self, strike: float, premium: float,
                                    contracts: int, days_to_exp: int) -> Dict[str, Dict]:
        """Calculate profit/loss scenarios at different price levels"""
        scenarios = {}
        price_moves = {
            'conservative_10pct': self.stock_price * 1.10,
            'moderate_20pct': self.stock_price * 1.20,
            'aggressive_30pct': self.stock_price * 1.30,
            'breakeven': strike + premium,
        }

        for scenario_name, target_price in price_moves.items():
            if target_price > strike:
                intrinsic_value = target_price - strike
                profit_per_share = intrinsic_value - premium
                total_profit = profit_per_share * contracts * 100
                roi = (profit_per_share / premium) * 100
            else:
                total_profit = -premium * contracts * 100
                roi = -100

            scenarios[scenario_name] = {
                'target_price': round(target_price, 2),
                'price_move_pct': round(((target_price / self.stock_price) - 1) * 100, 2),
                'profit_loss': round(total_profit, 2),
                'roi_pct': round(roi, 2)
            }

        return scenarios

    def _generate_rationale(self, option_row: pd.Series, scenarios: Dict) -> str:
        """Generate trade rationale text"""
        delta = option_row['delta']
        dte = option_row['daysToExpiration']
        moneyness_pct = (option_row['moneyness'] - 1) * 100

        rationale_parts = []

        if delta >= 0.70:
            rationale_parts.append(f"High delta ({delta:.2f}) provides strong directional exposure")
        elif delta >= 0.50:
            rationale_parts.append(f"Moderate delta ({delta:.2f}) balances probability and leverage")
        else:
            rationale_parts.append(f"Lower delta ({delta:.2f}) offers asymmetric payoff")

        if dte <= 45:
            rationale_parts.append(f"Short-term expiration ({dte} days) suits near-term catalyst plays")
        elif dte <= 90:
            rationale_parts.append(f"Medium-term expiration ({dte} days) allows trend development")
        else:
            rationale_parts.append(f"Longer-term expiration ({dte} days) reduces time decay pressure")

        moderate_scenario = scenarios.get('moderate_20pct', {})
        if moderate_scenario.get('roi_pct', 0) > 0:
            rationale_parts.append(f"20% stock move could yield {moderate_scenario['roi_pct']:.0f}% ROI")

        return ". ".join(rationale_parts) + "."


# ============================================================================
# DISPLAY FUNCTIONS
# ============================================================================

def display_results(ticker: str, capital: float, analysis_results: Dict):
    """Display results to terminal"""
    if not analysis_results.get('success'):
        print(f"\nERROR: {analysis_results.get('error', 'Unknown error')}\n")
        return

    stock_price = analysis_results['stock_price']
    recommendations = analysis_results['recommendations']

    print(f"\n{'='*80}")
    print(f"OPTIONS CALL RECOMMENDATIONS FOR {ticker}")
    print(f"{'='*80}")
    print(f"Current Stock Price: ${stock_price:.2f}")
    print(f"Available Capital: ${capital:,.2f}")
    print(f"Total Options Analyzed: {analysis_results['total_options_analyzed']}")
    print(f"Suitable Options Found: {analysis_results['suitable_options']}")
    print(f"{'='*80}\n")

    for rec in recommendations:
        print(f"\n{'─'*80}")
        print(f"RECOMMENDATION #{rec['rank']}: {rec['expiration']} ${rec['strike']:.2f} Call")
        print(f"{'─'*80}")

        print(f"\nOption Details:")
        print(f"  Strike Price: ${rec['strike']:.2f} ({rec['moneyness_pct']:.1f}% OTM)")
        print(f"  Expiration: {rec['expiration']} ({rec['days_to_expiration']} days)")
        print(f"  Premium: ${rec['premium']:.2f}")
        print(f"  Bid/Ask: ${rec['bid']:.2f} / ${rec['ask']:.2f}")

        print(f"\nGreeks & Risk:")
        print(f"  Delta: {rec['delta']:.3f} (${rec['delta']:.2f} move per $1 stock move)")
        print(f"  Theta: ${rec['theta']:.2f}/day (time decay)")
        print(f"  Implied Volatility: {rec['implied_volatility']*100:.1f}%")

        print(f"\nPosition Sizing:")
        print(f"  Recommended Contracts: {rec['recommended_contracts']}")
        print(f"  Total Cost: ${rec['total_cost']:,.2f} ({rec['capital_deployed_pct']:.1f}% of capital)")
        print(f"  Max Loss: ${rec['max_loss']:,.2f}")
        print(f"  Break-even Price: ${rec['breakeven_price']:.2f} (+{rec['breakeven_pct_move']:.1f}%)")

        print(f"\nProfit Scenarios:")
        for scenario_name, scenario in rec['profit_scenarios'].items():
            print(f"  {scenario_name.replace('_', ' ').title()}: " +
                  f"${scenario['target_price']:.2f} (+{scenario['price_move_pct']:.1f}%) → " +
                  f"${scenario['profit_loss']:,.2f} ({scenario['roi_pct']:.0f}% ROI)")

        print(f"\nLiquidity:")
        print(f"  Volume: {rec['volume']:.0f} | Open Interest: {rec['open_interest']:.0f}")

        print(f"\nRationale:")
        print(f"  {rec['rationale']}")

        print(f"\nScore: {rec['composite_score']:.1f}/100")

    print(f"\n{'='*80}")
    print("IBKR ORDER FORMAT (Top Recommendation)")
    print(f"{'='*80}")
    top_rec = recommendations[0]
    print(f"""
Ticker: {ticker}
Action: BUY TO OPEN
Option Type: CALL
Strike: ${top_rec['strike']:.2f}
Expiration: {top_rec['expiration']}
Quantity: {top_rec['recommended_contracts']} contracts
Order Type: LIMIT
Limit Price: ${top_rec['mid_price']:.2f}

Estimated Total Cost: ${top_rec['total_cost']:,.2f}

TIP: Use LIMIT order at mid-price (${top_rec['mid_price']:.2f}) or between bid and mid
""")

    print(f"{'='*80}")
    print("RISK WARNING")
    print(f"{'='*80}")
    print("""
Options trading involves significant risk. You can lose 100% of your investment.
This tool provides analysis only, not investment advice.
Consult with a financial advisor before trading.
""")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Options Call Recommender - Value & Momentum Analysis"
    )
    parser.add_argument("ticker", type=str, help="Stock ticker symbol (e.g., NFLX)")
    parser.add_argument("capital", type=float, help="Capital to deploy (e.g., 10000)")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    capital = args.capital

    if capital <= 0:
        print("ERROR: Capital must be positive")
        sys.exit(1)

    if capital < 500:
        print("WARNING: Capital less than $500 may limit options choices\n")

    print(f"\nAnalyzing options for {ticker} with ${capital:,.2f} capital...\n")

    try:
        strategist = OptionsStrategist(ticker=ticker, capital=capital)
        analysis_results = strategist.analyze_options_chain()
        display_results(ticker, capital, analysis_results)

    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
