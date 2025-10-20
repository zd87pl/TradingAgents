# Options Trading with TradingAgents

## Overview

TradingAgents now includes a sophisticated **Options Analyst** that provides AI-powered options strategy recommendations based on:
- Implied Volatility (IV) analysis
- Greeks calculations
- Market regime detection
- Risk-adjusted return optimization

This guide covers setup, usage, and advanced features including RunPod Serverless integration for ML-powered recommendations.

---

## Quick Start

### 1. Basic Usage (Rule-Based Analysis)

```python
from tradingagents import TradingAgentsGraph
from datetime import datetime

# Initialize with options analyst enabled (default)
graph = TradingAgentsGraph(
    selected_analysts=["market", "fundamentals", "options"]
)

# Run analysis
final_state, decision = graph.propagate(
    company_name="AAPL",
    trade_date=datetime.now().strftime("%Y-%m-%d")
)

# Access options recommendations
print(final_state["options_report"])
```

### 2. Configuration

Edit `tradingagents/default_config.py`:

```python
DEFAULT_CONFIG = {
    ...
    "options_trading": {
        "enabled": True,  # Enable/disable options analyst
        "min_liquidity_volume": 100,  # Minimum volume filter
        "min_liquidity_oi": 1000,  # Minimum open interest
        "preferred_dte_min": 20,  # Days to expiration range
        "preferred_dte_max": 60,
    }
}
```

---

## Features

### Options Analyst Capabilities

1. **Volatility Analysis**
   - IV Rank (0-100 scale)
   - IV Percentile
   - IV vs Historical Volatility comparison
   - Volatility regime classification

2. **Strategy Recommendations**
   - Top 3 strategies based on current market conditions
   - Specific strikes and expirations
   - Maximum profit/loss calculations
   - Breakeven points
   - Probability of profit estimates

3. **Greeks Analysis**
   - Delta (directional exposure)
   - Gamma (delta sensitivity)
   - Theta (time decay)
   - Vega (volatility sensitivity)
   - Rho (interest rate sensitivity)

4. **Risk Assessment**
   - Position sizing recommendations
   - Stop-loss levels
   - Portfolio Greeks exposure
   - Liquidity warnings

### Available Tools

The Options Analyst has access to 5 tools:

```python
# 1. Comprehensive Overview (start here)
get_options_summary(symbol="AAPL")

# 2. Full Options Chain
get_options_chain(symbol="AAPL", expiration_date="2024-03-15")

# 3. Historical Volatility
get_historical_volatility(symbol="AAPL", period_days=30)

# 4. IV Rank & Percentile
get_implied_volatility_rank(symbol="AAPL")

# 5. Greeks Calculation
calculate_greeks(
    symbol="AAPL",
    strike=180.0,
    expiration_date="2024-03-15",
    option_type="call"
)
```

---

## Strategy Selection Logic

### IV-Based Strategy Selection

The Options Analyst uses IV Rank to determine optimal strategies:

| IV Rank | Environment | Recommended Strategies |
|---------|-------------|------------------------|
| > 75 | Very High IV | **SELL PREMIUM**: Iron Condor, Credit Spreads, Covered Calls |
| 50-75 | Elevated IV | **NEUTRAL TO SELLING**: Short Strangles, Calendar Spreads |
| 25-50 | Moderate IV | **NEUTRAL**: Debit Spreads, Butterflies |
| < 25 | Low IV | **BUY PREMIUM**: Long Calls/Puts, Debit Spreads, Long Straddles |

### Example Output

```markdown
## OPTIONS SUMMARY: AAPL
Date: 2024-01-15

### Options Market Overview
- Current IV Rank: 45 (MODERATE)
- IV vs HV: IV 28% vs HV 25% (+12% premium)
- Put/Call Ratio: 0.85 (Neutral bullish)
- ATM Call IV: 28.5%
- ATM Put IV: 29.2%

### Recommended Strategies

#### 1. Bull Call Spread (MODERATE RISK)
- **Strikes**: Buy $180 Call / Sell $185 Call
- **Expiration**: 2024-02-16 (32 DTE)
- **Entry**: $2.50 debit
- **Max Profit**: $2.50 ($250 per contract) at $185+
- **Max Loss**: $2.50 ($250 per contract)
- **Breakeven**: $182.50
- **Greeks**: Delta +0.45, Theta -0.05, Vega +0.15
- **Probability of Profit**: ~55%

**Reasoning**: Moderate IV environment with slight bullish bias. Limited risk debit spread captures upside while limiting cost.

#### 2. Iron Condor (LOW RISK)
...

#### 3. Calendar Spread (LOW RISK)
...

### Risk Assessment
- **Position Size**: 2-3% of portfolio max
- **Stop Loss**: Close at 50% loss ($1.25 on spread)
- **Catalysts**: Earnings on 2024-02-01 (watch IV expansion)

### Summary Table

| Strategy | Entry | Max Profit | Max Loss | Risk Level | POF |
|----------|-------|------------|----------|------------|-----|
| Bull Call Spread | $2.50 | $2.50 | $2.50 | Medium | 55% |
| Iron Condor | $1.20 | $1.20 | $3.80 | Low | 65% |
| Calendar Spread | $0.80 | $1.50 | $0.80 | Low | 58% |
```

---

## Advanced: RunPod Serverless ML Integration

For production-grade, GPU-accelerated strategy selection, integrate with RunPod Serverless.

### Setup

1. **Install Dependencies**
   ```bash
   pip install runpod xgboost scikit-learn
   ```

2. **Configure RunPod**
   ```python
   DEFAULT_CONFIG = {
       ...
       "ml_models": {
           "enabled": True,
           "use_runpod": True,
           "runpod_endpoint_id": "your-endpoint-id",
           "runpod_api_key": "your-api-key",  # Or set RUNPOD_API_KEY env var
           "model_type": "xgboost",
           "fallback_to_rules": True,
       }
   }
   ```

3. **Deploy XGBoost Model to RunPod**
   ```bash
   # Train model
   python tradingagents/ml/training/train_xgboost.py

   # Deploy to RunPod
   cd tradingagents/ml/deployment
   runpod deploy strategy-classifier
   ```

### ML-Enhanced Workflow

When ML is enabled, the Options Analyst:

1. Collects market data (IV, HV, price action, Greeks)
2. Engineers ~40 features
3. Calls RunPod endpoint for ML prediction
4. Combines ML prediction with LLM reasoning
5. Generates final recommendation

**Benefits:**
- **Accuracy**: ML models trained on historical data learn complex patterns
- **Speed**: GPU inference in 50-200ms
- **Adaptability**: Models can be retrained on new data
- **Cost**: ~$0.0001 per prediction (essentially free)

### Usage with ML

```python
from tradingagents import TradingAgentsGraph
from tradingagents.ml import RunPodClient

# Initialize with ML config
config = {
    "ml_models": {
        "enabled": True,
        "use_runpod": True,
        "runpod_endpoint_id": "abc123",
        "runpod_api_key": "your-key",
        "model_type": "xgboost",
    }
}

graph = TradingAgentsGraph(config=config)

# ML predictions will be automatically integrated
final_state, decision = graph.propagate("AAPL", "2024-01-15")

# Options report now includes ML confidence scores
print(final_state["options_report"])
```

---

## Data Sources

### Current: yfinance (Free)

**Pros:**
- Free, no API key needed
- Good for testing and development
- Decent options data coverage

**Cons:**
- Limited historical options data
- No real-time Greeks
- Occasional rate limiting

### Future: Polygon.io (Production)

**Pros:**
- Full historical options data (back to 2009)
- Real-time Greeks and IV surfaces
- Professional-grade reliability

**Cons:**
- Requires paid subscription ($200/month+)

To switch to Polygon.io (when implemented):

```python
DEFAULT_CONFIG = {
    "data_vendors": {
        "options_data": "polygon",
    }
}
```

---

## Best Practices

### 1. Liquidity First
Always check volume and open interest before trading:
```python
# The analyst automatically filters by these:
"min_liquidity_volume": 100,
"min_liquidity_oi": 1000,
```

### 2. Understand IV Rank
IV Rank is your north star:
- **High IV** (>75): Time to SELL premium
- **Low IV** (<25): Time to BUY premium
- **Don't fight the tape**: Selling premium in low IV or buying in high IV reduces edge

### 3. Risk Management
- Never risk more than 2-5% of portfolio on single trade
- Use defined-risk strategies (spreads, not naked options)
- Set stop-loss at 50% of max profit or 2x debit paid

### 4. Time Decay
- Theta works for you when selling, against you when buying
- 30-45 DTE is the sweet spot for theta decay sellers
- Avoid last week before expiration (high gamma risk)

### 5. Greeks Portfolio Management
Monitor total portfolio exposure:
- **Delta**: Total directional risk
- **Gamma**: Risk of delta changes
- **Vega**: Volatility exposure
- **Theta**: Daily time decay (income for sellers)

---

## Troubleshooting

### "No options data available"
- Check if the stock has liquid options (large-cap stocks usually do)
- Verify yfinance can access options data (some stocks have restricted data)
- Try a different symbol (AAPL, SPY, TSLA are always liquid)

### "Insufficient data for IV rank"
- Requires at least 100 days of price history
- Check if stock is newly listed

### "All strategies show high risk"
- May indicate insufficient liquidity
- Lower min_liquidity filters in config
- Choose more liquid underlying

### ML Model Timeout
- Check RunPod endpoint is running
- Verify API key is correct
- Enable fallback_to_rules for graceful degradation

---

## Roadmap

### Phase 1 (Current) ✅
- [x] Options data tools (yfinance)
- [x] Options Analyst agent
- [x] IV-based strategy selection
- [x] Greeks calculation
- [x] RunPod integration framework

### Phase 2 (Next)
- [ ] XGBoost strategy classifier
- [ ] Backtesting framework
- [ ] Historical options data support
- [ ] ML model training pipeline

### Phase 3 (Future)
- [ ] Deep RL agent (PPO) for dynamic strategy selection
- [ ] IV surface forecasting (LSTM/Transformer)
- [ ] Portfolio optimization with Greeks constraints
- [ ] Multi-leg position management

---

## API Reference

### Options Tools

#### `get_options_summary(symbol, current_date=None)`
Get comprehensive options overview.

**Returns:**
- Stock price and trend
- IV rank and percentile
- Put/Call ratio
- ATM option prices and Greeks
- Available expirations

#### `get_options_chain(symbol, expiration_date="next")`
Get full options chain for an expiration.

**Parameters:**
- `expiration_date`: "next" for nearest, or "YYYY-MM-DD" for specific date

**Returns:**
- All strikes (calls and puts)
- Bid/ask/last prices
- Volume and open interest
- Implied volatility
- Moneyness

#### `get_historical_volatility(symbol, period_days=30, end_date=None)`
Calculate annualized historical volatility.

**Returns:**
- 30-day annualized HV
- Recent 20-day HV
- Daily volatility

#### `get_implied_volatility_rank(symbol, current_date=None)`
Calculate IV Rank and IV Percentile.

**Returns:**
- Current ATM IV
- 52-week IV range
- IV Rank (0-100)
- IV Percentile
- Interpretation (high/low/moderate)

#### `calculate_greeks(symbol, strike, expiration_date, option_type, current_date=None)`
Calculate Black-Scholes Greeks for specific option.

**Parameters:**
- `option_type`: "call" or "put"

**Returns:**
- Delta, Gamma, Theta, Vega, Rho
- Interpretations
- Risk metrics

---

## Examples

### Example 1: High IV Environment

```python
# TSLA with IV Rank 85 (very high)
graph = TradingAgentsGraph()
state, _ = graph.propagate("TSLA", "2024-01-15")

# Options Analyst will recommend:
# 1. Iron Condor (collect premium from both sides)
# 2. Bear Call Spread (if slightly bearish)
# 3. Covered Call (if holding shares)
```

### Example 2: Low IV Environment

```python
# AAPL with IV Rank 15 (very low)
graph = TradingAgentsGraph()
state, _ = graph.propagate("AAPL", "2024-01-15")

# Options Analyst will recommend:
# 1. Long Call (cheap premium, directional play)
# 2. Bull Call Spread (lower cost, defined risk)
# 3. Long Straddle (anticipate volatility expansion)
```

### Example 3: Earnings Play

```python
# NVDA before earnings (IV likely elevated)
graph = TradingAgentsGraph()
state, _ = graph.propagate("NVDA", "2024-02-20")  # Day before earnings

# Options Analyst will likely recommend:
# - Avoiding high IV strategies (don't buy expensive premium)
# - Calendar spreads (profit from IV crush after earnings)
# - Or staying out entirely if IV too high
```

---

## Resources

- [Options Trading Greeks](https://www.investopedia.com/trading/using-the-greeks-to-understand-options/)
- [Implied Volatility Explained](https://www.investopedia.com/terms/i/iv.asp)
- [Options Strategies Guide](https://www.optionsplaybook.com/option-strategies/)
- [RunPod Serverless Docs](https://docs.runpod.io/serverless/overview)

---

## Support

For issues or questions:
1. Check this guide first
2. Review logs in `eval_results/{symbol}/TradingAgentsStrategy_logs/`
3. Open an issue on GitHub with:
   - Symbol and date tested
   - Error message or unexpected behavior
   - Configuration used

---

**Last Updated**: 2025-10-20
**Version**: 1.0.0 (Phase 1 - Rule-Based Options Analysis)
