import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_dir": "/Users/yluo/Documents/Code/ScAI/FR1-data",
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "o4-mini",
    "quick_think_llm": "gpt-4o-mini",
    "backend_url": "https://api.openai.com/v1",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: yfinance, alpha_vantage, local
        "technical_indicators": "yfinance",  # Options: yfinance, alpha_vantage, local
        "fundamental_data": "alpha_vantage", # Options: openai, alpha_vantage, local
        "news_data": "alpha_vantage",        # Options: openai, alpha_vantage, google, local
        "options_data": "yfinance",          # Options: yfinance (polygon, cboe in future)
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
        # Example: "get_news": "openai",               # Override category default
    },
    # ML and RunPod configuration
    "ml_models": {
        "enabled": False,  # Enable ML-powered strategy recommendations
        "use_runpod": False,  # Use RunPod Serverless for inference
        "runpod_endpoint_id": "",  # Your RunPod endpoint ID
        "runpod_api_key": "",  # Your RunPod API key (or use env var RUNPOD_API_KEY)
        "model_type": "rule_based",  # Options: rule_based, xgboost, ppo, ensemble
        "fallback_to_rules": True,  # Fallback to rule-based if ML fails
        "cache_results": True,  # Cache ML inference results
        "cache_ttl": 900,  # Cache time-to-live in seconds (15 minutes)
    },
    # Options trading configuration
    "options_trading": {
        "enabled": True,  # Include options analyst in workflow
        "min_liquidity_volume": 100,  # Minimum option volume for recommendations
        "min_liquidity_oi": 1000,  # Minimum open interest
        "max_bid_ask_spread_pct": 5.0,  # Max bid-ask spread as % of option price
        "preferred_dte_min": 20,  # Preferred minimum days to expiration
        "preferred_dte_max": 60,  # Preferred maximum days to expiration
        "risk_free_rate": 0.05,  # Risk-free rate for Greeks calculation (5%)
        "default_strategies": [  # Default strategies to consider
            "bull_call_spread",
            "bear_put_spread",
            "iron_condor",
            "long_straddle",
            "covered_call",
        ],
    },
}
