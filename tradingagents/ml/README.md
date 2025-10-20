# Machine Learning Module

This directory contains ML models and infrastructure for advanced AI-powered options trading.

## Structure

```
ml/
├── __init__.py              # Module initialization
├── README.md                # This file
├── runpod_client.py         # RunPod Serverless API client
├── features.py              # Feature engineering for options trading
├── models/                  # ML model implementations (Phase 1.4+)
│   ├── strategy_classifier.py    # XGBoost strategy classifier
│   ├── ppo_agent.py              # PPO RL agent (Phase 2)
│   ├── iv_predictor.py           # IV surface forecasting (Phase 3)
│   └── ensemble.py               # Ensemble meta-learner (Phase 3)
├── training/                # Training scripts (Phase 1.4+)
│   ├── train_xgboost.py
│   ├── train_ppo.py
│   └── backtest.py
└── deployment/              # RunPod deployment handlers
    ├── strategy_handler.py       # XGBoost inference handler
    └── ppo_handler.py            # RL agent inference handler
```

## Components

### 1. RunPod Client (`runpod_client.py`)

Handles communication with RunPod Serverless endpoints:

```python
from tradingagents.ml import RunPodClient

client = RunPodClient(
    endpoint_id="your-endpoint-id",
    api_key="your-api-key"
)

# Run inference (blocking)
result = client.run({
    "action": "predict_strategy",
    "data": {...}
})

# Or async
job_id = client.run_async({...})
result = client.wait_for_completion(job_id)
```

**Features:**
- Async job submission with polling
- Automatic retries and error handling
- Result caching (15-minute TTL)
- Timeout management
- Health checks

### 2. Feature Engineering (`features.py`)

Converts raw market data into ML-ready features:

```python
from tradingagents.ml.features import OptionsFeatureEngineer

engineer = OptionsFeatureEngineer()

features = engineer.get_latest_features(
    price_df=price_history,
    options_data=options_metrics,
    current_price=current_price
)
```

**Feature Categories:**

**Technical Indicators:**
- Moving averages (SMA/EMA: 10, 20, 50)
- Volatility (10, 20, 30-day rolling)
- RSI (14-period)
- ATR (14-period)
- Volume ratios

**Options-Specific:**
- IV rank and percentile
- Current IV vs Historical Volatility ratio
- Put/Call ratio
- ATM option prices
- Total volume and open interest
- Greeks exposure

**Market Regime:**
- Trend strength and direction
- Volatility regime (high/low)
- Price position in 60-day range
- SMA crossovers

### 3. ML Models (Coming in Phase 1.4+)

**Phase 1: XGBoost Strategy Classifier**
- Multi-class classification (5 strategies)
- Input: ~40 engineered features
- Output: Strategy recommendation with confidence
- Deployment: RunPod Serverless

**Phase 2: PPO Reinforcement Learning Agent**
- Continuous action space (strategy + sizing)
- Reward: Sharpe ratio - drawdown penalty
- Training: Parallel environments
- Deployment: RunPod Serverless for inference

**Phase 3: Advanced Models**
- LSTM/Transformer for IV surface prediction
- VAE for market regime detection
- GNN for correlation analysis
- Ensemble meta-learner

## RunPod Integration

### Deployment Workflow

1. **Train Model Locally:**
   ```bash
   python tradingagents/ml/training/train_xgboost.py
   ```

2. **Create RunPod Handler:**
   See `deployment/strategy_handler.py`

3. **Deploy to RunPod:**
   ```bash
   cd tradingagents/ml/deployment
   runpod deploy strategy-classifier
   ```

4. **Use in Trading System:**
   ```python
   from tradingagents.ml import RunPodClient

   client = RunPodClient(endpoint_id="...", api_key="...")
   prediction = client.run({
       "action": "predict_strategy",
       "features": features_dict
   })
   ```

### Cost Optimization

- **Inference:** ~$0.0001 per request (200ms @ $1.89/hr on A100)
- **Training:** ~$20-40 per XGBoost experiment
- **Caching:** 15-minute cache reduces redundant calls
- **Batching:** Process multiple symbols in one request

## Development Roadmap

### Phase 1.3 (Current) ✅
- [x] RunPod client implementation
- [x] Feature engineering framework
- [x] Infrastructure setup

### Phase 1.4 (Next)
- [ ] XGBoost training pipeline
- [ ] Strategy classifier implementation
- [ ] RunPod deployment handler
- [ ] Backtesting framework
- [ ] Integration with options analyst

### Phase 2
- [ ] OpenAI Gym trading environment
- [ ] PPO agent implementation
- [ ] Parallel training infrastructure
- [ ] Advanced reward engineering

### Phase 3
- [ ] IV surface forecasting (LSTM/Transformer)
- [ ] Market regime detection (VAE)
- [ ] Correlation analysis (GNN)
- [ ] Ensemble system

## Testing

```bash
# Test RunPod client
python -m tradingagents.ml.runpod_client

# Test feature engineering
python -m tradingagents.ml.features

# Run ML model tests (when implemented)
pytest tradingagents/ml/tests/
```

## Configuration

ML configuration will be added to `tradingagents/default_config.py`:

```python
DEFAULT_CONFIG = {
    ...
    "ml_models": {
        "enabled": True,
        "use_runpod": True,
        "runpod_endpoint_id": "your-endpoint-id",
        "runpod_api_key": "your-api-key",
        "model_type": "xgboost",  # xgboost, ppo, ensemble
        "fallback_to_rules": True,  # Use rule-based if ML fails
    }
}
```

## Resources

- [RunPod Serverless Docs](https://docs.runpod.io/serverless/overview)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [Stable Baselines3 (PPO)](https://stable-baselines3.readthedocs.io/)
- [Options Trading Greeks](https://www.investopedia.com/trading/using-the-greeks-to-understand-options/)

## Contributing

When adding new ML models:
1. Create model class in `models/`
2. Add training script in `training/`
3. Create RunPod handler in `deployment/`
4. Update this README
5. Add tests in `tests/`
6. Update configuration in `default_config.py`
