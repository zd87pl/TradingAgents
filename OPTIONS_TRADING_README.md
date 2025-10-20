# Options Call Recommender System

## Overview

A sophisticated options analysis system that combines **Michael Burry's deep value investing** principles with **momentum/growth analysis** to provide actionable call options recommendations for Interactive Brokers (IBKR).

## Features

### Trading Philosophy

The system synthesizes two legendary trading approaches:

1. **Michael Burry's Value Approach**:
   - Focus on intrinsic value and margin of safety
   - Analyze fundamentals: EV/EBITDA, P/E, P/B, Free Cash Flow
   - Look for contrarian opportunities
   - Assess absolute value, not relative to peers
   - Emphasize downside protection

2. **Growth & Momentum Analysis**:
   - High-conviction growth opportunities
   - Strong technical momentum and trends
   - Market sentiment and catalysts
   - Competitive positioning
   - Asymmetric risk/reward setups

### Core Capabilities

- **Comprehensive Options Chain Analysis**: Analyzes all available call options across multiple expiration dates
- **Greeks Calculation**: Black-Scholes model for Delta, Gamma, Vega, Theta, Rho
- **Intelligent Scoring System**: Multi-factor scoring based on:
  - Delta (directional exposure)
  - Time to expiration
  - Liquidity (volume + open interest)
  - Bid-ask spreads
  - Implied volatility
  - Premium efficiency

- **Position Sizing**: Automatic position sizing based on available capital (default 7.5% allocation)
- **Profit Scenarios**: Calculates P/L for multiple price target scenarios
- **IBKR-Ready Output**: Formatted order details ready for Interactive Brokers execution

## Installation

### Quick Start (Standalone Version)

```bash
# Install dependencies
pip install pandas numpy scipy yfinance

# Run the standalone version
python options_recommender_standalone.py TICKER CAPITAL
```

### Example

```bash
# Analyze NFLX with $10,000 capital
python options_recommender_standalone.py NFLX 10000

# Analyze AAPL with $25,000 capital
python options_recommender_standalone.py AAPL 25000

# Analyze TSLA with $50,000 capital
python options_recommender_standalone.py TSLA 50000
```

## System Architecture

```
options_recommender_standalone.py (Main Entry Point)
│
├── OptionsDataFetcher
│   ├── Fetches stock prices and options chains from yfinance
│   ├── Filters options (OTM, liquidity)
│   ├── Calculates Black-Scholes Greeks
│   └── Enriches options data
│
└── OptionsStrategist
    ├── Analyzes complete options chain
    ├── Scores options using multi-factor model
    ├── Calculates position sizing
    ├── Generates profit/loss scenarios
    └── Produces recommendations
```

## Output Format

The system provides:

### 1. Stock Overview
- Current price
- Market cap, P/E ratios
- 52-week high/low
- Sector and industry

### 2. Top 3 Options Recommendations

For each recommendation:

**Option Details:**
- Strike price and moneyness (% OTM)
- Expiration date and days to expiration
- Premium (bid/ask/mid)

**Greeks & Risk Metrics:**
- Delta (directional sensitivity)
- Theta (daily time decay)
- Implied Volatility

**Position Sizing:**
- Recommended number of contracts
- Total cost and % of capital
- Maximum loss
- Break-even price and required move

**Profit Scenarios:**
- 10% stock move scenario
- 20% stock move scenario
- 30% stock move scenario
- Break-even scenario

**Liquidity Metrics:**
- Volume
- Open Interest

**Trade Rationale:**
- AI-generated explanation of why this option is recommended

### 3. IBKR Order Format

Ready-to-use order details:
- Ticker
- Action: BUY TO OPEN
- Option Type: CALL
- Strike & Expiration
- Recommended quantity
- Suggested limit price

## Scoring Methodology

The system uses a weighted composite score (0-100):

| Factor | Weight | Optimal Range |
|--------|--------|---------------|
| Delta | 25% | 0.30 - 0.70 |
| Time to Exp | 20% | 30-120 days |
| Liquidity | 20% | Higher is better |
| Bid-Ask Spread | 15% | < 3% |
| Implied Volatility | 10% | 20-50% |
| Premium Efficiency | 10% | 1-5% of strike |

## Position Sizing Rules

Based on sound risk management principles:

- **Conservative**: 5% of capital per position
- **Moderate**: 7.5% of capital per position (default)
- **Aggressive**: 10% of capital per position

Example with $10,000 capital (7.5% allocation):
- Max position cost: $750
- If premium is $2.50/share: Floor(750 / 250) = 3 contracts
- Actual cost: 3 × 100 × $2.50 = $750

## Files Created

### Core System Files

1. **`tradingagents/dataflows/options_data.py`** (350 lines)
   - Options data fetching module
   - Black-Scholes Greeks calculation
   - Options chain filtering and enrichment

2. **`tradingagents/agents/analysts/company_profile_analyst.py`** (150 lines)
   - Company profile analysis agent
   - Combines value and growth analysis
   - Uses LangChain for LLM-powered analysis

3. **`tradingagents/agents/options/options_strategist.py`** (600 lines)
   - Core options strategy engine
   - Multi-factor scoring system
   - Position sizing and profit calculations
   - Recommendation generation

4. **`tradingagents/agents/options/__init__.py`**
   - Module initialization

5. **`options_recommender.py`** (450 lines)
   - Full-featured CLI with Rich terminal output
   - Integrates with TradingAgents framework
   - Report generation and saving

6. **`options_recommender_standalone.py`** (650 lines)
   - **Standalone version with zero TradingAgents dependencies**
   - Self-contained, easy to run
   - All features included
   - **Recommended for most users**

## Usage Examples

### Basic Usage

```bash
python options_recommender_standalone.py NFLX 10000
```

### Advanced Usage

```python
from options_recommender_standalone import OptionsStrategist

# Create strategist
strategist = OptionsStrategist(ticker="NFLX", capital=10000)

# Analyze options
results = strategist.analyze_options_chain()

# Get recommendations
if results['success']:
    recommendations = results['recommendations']
    for rec in recommendations:
        print(f"Strike: ${rec['strike']:.2f}")
        print(f"Expiration: {rec['expiration']}")
        print(f"Contracts: {rec['recommended_contracts']}")
        print(f"Total Cost: ${rec['total_cost']:,.2f}")
        print()
```

## Risk Warnings

⚠️ **IMPORTANT DISCLAIMERS**:

1. **Options trading involves significant risk**
   - You can lose 100% of your investment
   - Options can expire worthless

2. **This tool provides analysis only, NOT investment advice**
   - Past performance does not guarantee future results
   - Always do your own due diligence

3. **Consult with a licensed financial advisor** before making any trading decisions

4. **Market conditions change rapidly**
   - Prices shown are historical
   - Always verify current prices before trading

5. **Execution risks**
   - Slippage can occur
   - Use limit orders, not market orders
   - Monitor bid-ask spreads

## Best Practices for IBKR Execution

1. **Always use LIMIT orders**
   - Start at mid-price (bid + ask) / 2
   - Adjust if not filled within 30 seconds

2. **Check liquidity before trading**
   - Minimum 50+ open interest
   - Minimum 10+ daily volume
   - Bid-ask spread < 10%

3. **Time your entries**
   - Avoid first 30 minutes after market open
   - Best liquidity typically 10:00 AM - 3:30 PM ET

4. **Use contingent orders**
   - Set stop-loss at 50% of premium paid
   - Consider profit targets (100%, 200% ROI)

5. **Diversify**
   - Don't put all capital in one position
   - Spread across multiple tickers
   - Use different expiration dates

## Troubleshooting

### "No options data available"
- Check if ticker has options (some stocks don't)
- Verify ticker symbol is correct
- Try again later (API rate limits)

### "HTTP Error 403"
- Yahoo Finance may be blocking requests
- Wait a few minutes and retry
- Consider using a VPN if persistent

### Module errors
```bash
# Install missing dependencies
pip install pandas numpy scipy yfinance

# For enhanced output
pip install rich
```

## Future Enhancements

Potential improvements:

1. **Multi-leg strategies**
   - Vertical spreads
   - Calendar spreads
   - Iron condors

2. **Real-time data**
   - WebSocket connections
   - Live Greeks updates

3. **Backtesting**
   - Historical performance analysis
   - Strategy optimization

4. **Portfolio management**
   - Track multiple positions
   - P/L monitoring
   - Portfolio Greeks

5. **Advanced analysis**
   - Earnings date awareness
   - Ex-dividend date handling
   - Corporate action adjustments

## Technical Details

### Greeks Calculation

Black-Scholes formula implementation:

```
d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d2 = d1 - σ√T

Delta = N(d1)
Gamma = N'(d1) / (S × σ × √T)
Vega = S × N'(d1) × √T / 100
Theta = [-S × N'(d1) × σ / (2√T) - r × K × e^(-rT) × N(d2)] / 365
Rho = K × T × e^(-rT) × N(d2) / 100

Where:
S = Stock price
K = Strike price
T = Time to expiration (years)
σ = Implied volatility
r = Risk-free rate (5%)
N(x) = Standard normal CDF
N'(x) = Standard normal PDF
```

### Scoring Algorithm

Composite score calculation:

```python
composite_score = (
    delta_score × 0.25 +
    time_score × 0.20 +
    liquidity_score × 0.20 +
    spread_score × 0.15 +
    iv_score × 0.10 +
    premium_score × 0.10
)
```

## Support

For issues or questions:

1. Check this README first
2. Review error messages carefully
3. Ensure all dependencies are installed
4. Try the standalone version if framework version fails

## License

Part of the TradingAgents framework.

## Acknowledgments

- **Michael Burry**: Value investing principles
- **Julian Petroulas**: Momentum trading approach
- **yfinance**: Options data provider
- **scipy**: Statistical functions for Greeks calculation

---

**Remember**: Options trading requires knowledge, experience, and discipline. Start small, learn continuously, and never risk more than you can afford to lose.
