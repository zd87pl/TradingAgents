"""
Unified Configuration System
============================

Extends TradingAgents DEFAULT_CONFIG with autonomous trading features.
Single source of truth for all configuration.
"""

import os
from tradingagents.default_config import DEFAULT_CONFIG

# Extend the default config with autonomous features
UNIFIED_CONFIG = DEFAULT_CONFIG.copy()

# Add autonomous trading configuration
UNIFIED_CONFIG.update({
    # === Autonomous System Settings ===
    "autonomous_enabled": True,
    "scheduler_interval_minutes": 30,  # How often to run monitoring tasks

    # === API Keys (loaded from environment) ===
    "alpha_vantage_api_key": os.getenv("ALPHA_VANTAGE_API_KEY"),
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "perplexity_api_key": os.getenv("PERPLEXITY_API_KEY"),
    "quiver_api_key": os.getenv("QUIVER_API_KEY"),  # For congressional trades

    # === IBKR Configuration ===
    "ibkr_enabled": os.getenv("IBKR_ENABLED", "false").lower() == "true",
    "ibkr_host": os.getenv("IBKR_HOST", "127.0.0.1"),
    "ibkr_port": int(os.getenv("IBKR_PORT", "7497")),
    "ibkr_client_id": int(os.getenv("IBKR_CLIENT_ID", "1")),
    "ibkr_account": os.getenv("IBKR_ACCOUNT", ""),

    # === Database Configuration ===
    "database_enabled": os.getenv("DATABASE_ENABLED", "false").lower() == "true",
    "database_url": os.getenv(
        "DATABASE_URL",
        "postgresql://trading:trading@localhost:5432/tradingagents"
    ),

    # === Redis Cache Configuration ===
    "redis_enabled": os.getenv("REDIS_ENABLED", "false").lower() == "true",
    "redis_host": os.getenv("REDIS_HOST", "localhost"),
    "redis_port": int(os.getenv("REDIS_PORT", "6379")),
    "redis_db": int(os.getenv("REDIS_DB", "0")),
    "redis_password": os.getenv("REDIS_PASSWORD", ""),

    # === Alert Configuration ===
    "alerts_enabled": True,
    "alert_channels": {
        "email": {
            "enabled": os.getenv("EMAIL_ALERTS_ENABLED", "false").lower() == "true",
            "smtp_host": os.getenv("SMTP_HOST", ""),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "smtp_user": os.getenv("SMTP_USER", ""),
            "smtp_password": os.getenv("SMTP_PASSWORD", ""),
            "recipient": os.getenv("ALERT_EMAIL", ""),
        },
        "discord": {
            "enabled": os.getenv("DISCORD_ALERTS_ENABLED", "false").lower() == "true",
            "webhook_url": os.getenv("DISCORD_WEBHOOK_URL", ""),
        },
        "telegram": {
            "enabled": os.getenv("TELEGRAM_ALERTS_ENABLED", "false").lower() == "true",
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        },
    },

    # === Risk Management Settings ===
    "risk_management": {
        "max_position_size": 0.20,  # 20% per position
        "max_daily_loss": 0.05,  # 5% daily loss limit
        "max_total_exposure": 1.0,  # 100% portfolio exposure
        "max_concentration": 0.30,  # 30% in single stock
        "max_sector_exposure": 0.40,  # 40% per sector
        "max_correlation": 0.70,  # Max correlation between positions
        "max_volatility": 0.30,  # 30% annualized volatility
        "min_sharpe_ratio": 0.5,  # Minimum Sharpe ratio
        "stop_loss_percent": 0.08,  # 8% stop loss
        "take_profit_percent": 0.15,  # 15% take profit
    },

    # === Perplexity AI Settings ===
    "perplexity_model": "sonar",  # General Perplexity model (not finance-specific)
    "perplexity_max_tokens": 1000,
    "perplexity_temperature": 0.2,

    # === Portfolio Configuration ===
    "portfolio_tickers": ["AVGO", "MSFT", "MU", "NVDA", "TSM"],  # User's IBKR positions
    "watchlist_tickers": [],  # Additional tickers to monitor

    # === Data Aggregation Settings ===
    "data_aggregation": {
        "congressional_trades_enabled": True,
        "insider_trades_enabled": True,
        "earnings_calendar_enabled": True,
        "sentiment_analysis_enabled": True,
        "congressional_lookback_days": 30,
        "insider_lookback_days": 90,
        "earnings_lookahead_days": 30,
    },

    # === Performance Settings ===
    "async_enabled": True,
    "max_concurrent_requests": 10,
    "request_timeout_seconds": 30,
    "cache_ttl_seconds": 3600,  # 1 hour cache
})

# Function to get the unified config
def get_unified_config():
    """
    Get the unified configuration combining TradingAgents and Autonomous settings.

    Returns:
        dict: Complete configuration dictionary
    """
    return UNIFIED_CONFIG.copy()

# Function to update config at runtime
def update_config(updates: dict):
    """
    Update configuration values at runtime.

    Args:
        updates: Dictionary of configuration updates
    """
    UNIFIED_CONFIG.update(updates)

# Validate critical configurations
def validate_config():
    """
    Validate that critical configuration values are present.

    Raises:
        ValueError: If critical configuration is missing
    """
    critical_keys = []

    # Only require OpenAI key if using OpenAI models
    if UNIFIED_CONFIG.get("llm_provider") == "openai":
        critical_keys.append("openai_api_key")

    # Check if we have at least one data source configured
    if not UNIFIED_CONFIG.get("alpha_vantage_api_key"):
        print("Warning: Alpha Vantage API key not configured")

    missing_keys = [key for key in critical_keys if not UNIFIED_CONFIG.get(key)]

    if missing_keys:
        raise ValueError(f"Missing critical configuration: {', '.join(missing_keys)}")

    return True

# Export the main config
CONFIG = UNIFIED_CONFIG