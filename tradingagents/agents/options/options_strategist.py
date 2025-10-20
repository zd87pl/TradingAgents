"""
Options Strategist Agent
Analyzes options chains and recommends optimal call strategies
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from tradingagents.dataflows.options_data import OptionsDataFetcher
import numpy as np


class OptionsStrategist:
    """
    Combines company analysis with options chain analysis
    to recommend specific call option strategies
    """

    def __init__(self, ticker: str, capital: float, company_analysis: str = ""):
        """
        Initialize options strategist

        Args:
            ticker: Stock ticker symbol
            capital: Total capital available for deployment
            company_analysis: Company profile analysis from analyst
        """
        self.ticker = ticker.upper()
        self.capital = capital
        self.company_analysis = company_analysis
        self.fetcher = OptionsDataFetcher(ticker)
        self.stock_price = self.fetcher.stock_price

    def analyze_options_chain(self) -> Dict[str, any]:
        """
        Analyze the full options chain and identify optimal strategies

        Returns:
            Analysis results with recommendations
        """
        # Get all call options
        all_calls = self.fetcher.get_all_call_options(max_expirations=8)

        if all_calls.empty:
            return {
                'success': False,
                'error': 'No options data available for this ticker'
            }

        # Filter for liquid options (volume > 10, open interest > 50)
        liquid_calls = all_calls[
            (all_calls['volume'] > 10) |
            (all_calls['openInterest'] > 50)
        ].copy()

        if liquid_calls.empty:
            # Fallback to all calls if liquidity filter is too strict
            liquid_calls = all_calls.copy()

        # Filter for reasonable strikes (5% to 30% OTM)
        otm_calls = self.fetcher.filter_otm_calls(
            liquid_calls,
            min_strike_pct=1.05,
            max_strike_pct=1.30
        )

        if otm_calls.empty:
            # Fallback to wider range
            otm_calls = self.fetcher.filter_otm_calls(
                liquid_calls,
                min_strike_pct=0.95,
                max_strike_pct=1.40
            )

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
            'recommendations': top_recommendations,
            'all_scored_options': scored_options
        }

    def _score_options(self, options_df: pd.DataFrame) -> pd.DataFrame:
        """
        Score options based on multiple criteria

        Scoring factors:
        1. Delta (prefer 0.30-0.70 for good leverage + probability)
        2. Implied volatility (prefer moderate, not too high)
        3. Volume/Open Interest (liquidity)
        4. Time to expiration (30-120 days preferred)
        5. Bid-ask spread (tighter is better)
        6. Premium cost (reasonable premium/strike ratio)

        Args:
            options_df: DataFrame with options and Greeks

        Returns:
            DataFrame with scores
        """
        if options_df.empty:
            return options_df

        scored = options_df.copy()

        # Delta score (prefer 0.30 to 0.70)
        scored['delta_score'] = scored['delta'].apply(
            lambda d: 100 if 0.30 <= d <= 0.70 else
                     80 if 0.20 <= d < 0.30 or 0.70 < d <= 0.80 else
                     50 if 0.10 <= d < 0.20 or 0.80 < d <= 0.90 else
                     20
        )

        # Time score (prefer 30-120 days)
        scored['time_score'] = scored['daysToExpiration'].apply(
            lambda d: 100 if 30 <= d <= 120 else
                     80 if 20 <= d < 30 or 120 < d <= 180 else
                     50 if 10 <= d < 20 or 180 < d <= 270 else
                     20
        )

        # Liquidity score (volume + open interest)
        scored['liquidity'] = scored['volume'].fillna(0) + scored['openInterest'].fillna(0)
        max_liquidity = scored['liquidity'].max()
        if max_liquidity > 0:
            scored['liquidity_score'] = (scored['liquidity'] / max_liquidity * 100).clip(0, 100)
        else:
            scored['liquidity_score'] = 0

        # Spread score (bid-ask spread as % of mid-price)
        scored['mid_price'] = (scored['bid'] + scored['ask']) / 2
        scored['spread_pct'] = ((scored['ask'] - scored['bid']) / scored['mid_price'] * 100).fillna(100)
        scored['spread_score'] = scored['spread_pct'].apply(
            lambda s: 100 if s < 3 else
                     80 if s < 5 else
                     60 if s < 10 else
                     40 if s < 15 else
                     20
        )

        # IV score (prefer moderate IV, not too high)
        scored['iv'] = scored['impliedVolatility'].fillna(0.3)
        scored['iv_score'] = scored['iv'].apply(
            lambda iv: 100 if 0.20 <= iv <= 0.50 else
                      80 if 0.15 <= iv < 0.20 or 0.50 < iv <= 0.70 else
                      60 if 0.10 <= iv < 0.15 or 0.70 < iv <= 1.00 else
                      40
        )

        # Premium efficiency (premium as % of strike)
        scored['premium_pct'] = (scored['lastPrice'] / scored['strike'] * 100).fillna(0)
        scored['premium_score'] = scored['premium_pct'].apply(
            lambda p: 100 if 1 <= p <= 5 else
                     80 if 0.5 <= p < 1 or 5 < p <= 8 else
                     60 if 0.2 <= p < 0.5 or 8 < p <= 12 else
                     40
        )

        # Weighted composite score
        scored['composite_score'] = (
            scored['delta_score'] * 0.25 +
            scored['time_score'] * 0.20 +
            scored['liquidity_score'] * 0.20 +
            scored['spread_score'] * 0.15 +
            scored['iv_score'] * 0.10 +
            scored['premium_score'] * 0.10
        )

        # Sort by composite score
        scored = scored.sort_values('composite_score', ascending=False)

        return scored

    def _get_top_recommendations(self, scored_options: pd.DataFrame,
                                 n_recommendations: int = 3) -> List[Dict]:
        """
        Get top N recommendations with detailed analysis

        Args:
            scored_options: DataFrame with scored options
            n_recommendations: Number of recommendations to return

        Returns:
            List of recommendation dictionaries
        """
        if scored_options.empty:
            return []

        recommendations = []

        for idx, row in scored_options.head(n_recommendations).iterrows():
            # Calculate position sizing
            contracts, total_cost, contracts_percentage = self._calculate_position_size(
                premium=row['lastPrice'],
                strike=row['strike']
            )

            # Calculate break-even
            breakeven = row['strike'] + row['lastPrice']
            breakeven_pct = ((breakeven / self.stock_price) - 1) * 100

            # Calculate potential profit scenarios
            profit_scenarios = self._calculate_profit_scenarios(
                strike=row['strike'],
                premium=row['lastPrice'],
                contracts=contracts,
                days_to_exp=row['daysToExpiration']
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

                # Greeks
                'delta': row['delta'],
                'gamma': row['gamma'],
                'vega': row['vega'],
                'theta': row['theta'],
                'implied_volatility': row['iv'],

                # Liquidity
                'volume': row['volume'],
                'open_interest': row['openInterest'],
                'bid_ask_spread': row['ask'] - row['bid'],
                'spread_pct': row['spread_pct'],

                # Position sizing
                'recommended_contracts': contracts,
                'total_cost': total_cost,
                'capital_deployed_pct': contracts_percentage,

                # Risk metrics
                'breakeven_price': breakeven,
                'breakeven_pct_move': breakeven_pct,
                'max_loss': total_cost,
                'max_loss_pct': contracts_percentage,

                # Profit scenarios
                'profit_scenarios': profit_scenarios,

                # Scores
                'composite_score': row['composite_score'],
                'delta_score': row['delta_score'],
                'time_score': row['time_score'],
                'liquidity_score': row['liquidity_score'],

                # Trade rationale
                'rationale': self._generate_rationale(row, profit_scenarios)
            }

            recommendations.append(recommendation)

        return recommendations

    def _calculate_position_size(self, premium: float, strike: float) -> Tuple[int, float, float]:
        """
        Calculate recommended position size based on capital and risk management

        Risk management rules:
        - Burry style: Never risk more than 5% of capital on single position
        - Petroulas style: High conviction = up to 10% of capital
        - Default: 5-7.5% of capital per position

        Args:
            premium: Option premium per share
            strike: Strike price

        Returns:
            Tuple of (contracts, total_cost, percentage_of_capital)
        """
        # Calculate max position size (7.5% of capital for options)
        max_position_cost = self.capital * 0.075

        # Cost per contract (100 shares)
        cost_per_contract = premium * 100

        # Max contracts based on capital allocation
        max_contracts = int(max_position_cost / cost_per_contract)

        # Ensure at least 1 contract
        contracts = max(1, max_contracts)

        # Calculate actual cost
        total_cost = contracts * cost_per_contract

        # Percentage of capital
        percentage = (total_cost / self.capital) * 100

        return contracts, total_cost, percentage

    def _calculate_profit_scenarios(self,
                                    strike: float,
                                    premium: float,
                                    contracts: int,
                                    days_to_exp: int) -> Dict[str, Dict]:
        """
        Calculate profit/loss scenarios at different price levels

        Args:
            strike: Strike price
            premium: Option premium
            contracts: Number of contracts
            days_to_exp: Days to expiration

        Returns:
            Dictionary with scenarios
        """
        scenarios = {}

        # Define price scenarios
        price_moves = {
            'conservative_10pct': self.stock_price * 1.10,
            'moderate_20pct': self.stock_price * 1.20,
            'aggressive_30pct': self.stock_price * 1.30,
            'breakeven': strike + premium,
        }

        for scenario_name, target_price in price_moves.items():
            if target_price > strike:
                # In the money
                intrinsic_value = target_price - strike
                profit_per_share = intrinsic_value - premium
                total_profit = profit_per_share * contracts * 100
                roi = (profit_per_share / premium) * 100
            else:
                # Out of the money - total loss
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
        """
        Generate trade rationale text

        Args:
            option_row: Option data row
            scenarios: Profit scenarios

        Returns:
            Rationale text
        """
        strike = option_row['strike']
        delta = option_row['delta']
        dte = option_row['daysToExpiration']
        moneyness_pct = (option_row['moneyness'] - 1) * 100

        rationale_parts = []

        # Delta interpretation
        if delta >= 0.70:
            rationale_parts.append(f"High delta ({delta:.2f}) provides strong directional exposure")
        elif delta >= 0.50:
            rationale_parts.append(f"Moderate delta ({delta:.2f}) balances probability and leverage")
        elif delta >= 0.30:
            rationale_parts.append(f"Lower delta ({delta:.2f}) offers asymmetric payoff with lower probability")
        else:
            rationale_parts.append(f"Low delta ({delta:.2f}) is speculative but offers high leverage")

        # Time frame
        if dte <= 45:
            rationale_parts.append(f"Short-term expiration ({dte} days) suits near-term catalyst plays")
        elif dte <= 90:
            rationale_parts.append(f"Medium-term expiration ({dte} days) allows trend development")
        else:
            rationale_parts.append(f"Longer-term expiration ({dte} days) reduces time decay pressure")

        # Moneyness
        if moneyness_pct < 2:
            rationale_parts.append(f"Near ATM strike ({moneyness_pct:.1f}% OTM) requires minimal move")
        elif moneyness_pct < 10:
            rationale_parts.append(f"Slightly OTM ({moneyness_pct:.1f}%) balances cost and upside")
        else:
            rationale_parts.append(f"Further OTM ({moneyness_pct:.1f}%) offers cheaper entry with higher upside")

        # Profit scenario highlight
        moderate_scenario = scenarios.get('moderate_20pct', {})
        if moderate_scenario.get('roi_pct', 0) > 0:
            rationale_parts.append(
                f"20% stock move could yield {moderate_scenario['roi_pct']:.0f}% ROI"
            )

        return ". ".join(rationale_parts) + "."

    def generate_summary_report(self, analysis_results: Dict) -> str:
        """
        Generate a markdown summary report

        Args:
            analysis_results: Results from analyze_options_chain()

        Returns:
            Markdown formatted report
        """
        if not analysis_results.get('success'):
            return f"## Error\n\n{analysis_results.get('error', 'Unknown error')}"

        stock_price = analysis_results['stock_price']
        recommendations = analysis_results['recommendations']

        report = f"""# Options Call Recommendations for {self.ticker}

## Market Overview
- **Current Stock Price**: ${stock_price:.2f}
- **Available Capital**: ${self.capital:,.2f}
- **Total Options Analyzed**: {analysis_results['total_options_analyzed']}
- **Suitable Options Found**: {analysis_results['suitable_options']}

## Recommended Call Options

"""

        for rec in recommendations:
            report += f"""### Recommendation #{rec['rank']}: {rec['expiration']} ${rec['strike']} Call

**Option Details:**
- Strike Price: ${rec['strike']:.2f} ({rec['moneyness_pct']:.1f}% OTM)
- Expiration: {rec['expiration']} ({rec['days_to_expiration']} days)
- Premium: ${rec['premium']:.2f}
- Bid/Ask: ${rec['bid']:.2f} / ${rec['ask']:.2f} (spread: ${rec['bid_ask_spread']:.2f})

**Greeks & Risk:**
- Delta: {rec['delta']:.3f} (for every $1 move in stock, option moves ${rec['delta']:.2f})
- Gamma: {rec['gamma']:.4f}
- Theta: ${rec['theta']:.2f}/day (time decay)
- Vega: {rec['vega']:.2f}
- Implied Volatility: {rec['implied_volatility']*100:.1f}%

**Position Sizing:**
- Recommended Contracts: {rec['recommended_contracts']}
- Total Cost: ${rec['total_cost']:,.2f} ({rec['capital_deployed_pct']:.1f}% of capital)
- Max Loss: ${rec['max_loss']:,.2f}
- Break-even Price: ${rec['breakeven_price']:.2f} ({rec['breakeven_pct_move']:.1f}% move required)

**Profit Scenarios:**
"""
            for scenario_name, scenario in rec['profit_scenarios'].items():
                report += f"- **{scenario_name.replace('_', ' ').title()}** (${scenario['target_price']:.2f}, +{scenario['price_move_pct']:.1f}%): ${scenario['profit_loss']:,.2f} ({scenario['roi_pct']:.0f}% ROI)\n"

            report += f"""
**Liquidity:**
- Volume: {rec['volume']:.0f}
- Open Interest: {rec['open_interest']:.0f}

**Trade Rationale:**
{rec['rationale']}

**Overall Score:** {rec['composite_score']:.1f}/100

---

"""

        report += """
## Risk Warnings

1. **Maximum Loss**: You can lose 100% of premium paid if stock doesn't reach strike by expiration
2. **Time Decay**: Options lose value daily (theta decay), especially in last 30 days
3. **Volatility Risk**: IV crush after earnings can reduce option value even if stock moves favorably
4. **Liquidity**: Check bid-ask spread before trading; wide spreads increase execution costs

## Next Steps for IBKR Execution

1. Log into Interactive Brokers TWS or IBKR Mobile
2. Search for ticker: {self.ticker}
3. Navigate to Options Chain
4. Select the recommended expiration date and strike
5. Review live bid/ask before placing order
6. Use limit orders (not market orders) for better execution
7. Consider the recommendations above as starting points; adjust based on your risk tolerance

---

*Generated using TradingAgents Options Analyzer*
*Combining Michael Burry's Value Principles with Momentum Analysis*
"""

        return report
