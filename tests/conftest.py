"""
Pytest Configuration and Shared Fixtures
========================================
"""

import pytest
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure event loop for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mock Redis Cache
@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache for testing."""
    cache = Mock()
    cache.connected = True
    cache.redis = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.exists = AsyncMock(return_value=False)
    cache.delete = AsyncMock(return_value=True)
    return cache


# Mock Market Signal
@pytest.fixture
def sample_market_signal():
    """Create a sample market signal for testing."""
    from autonomous.data_aggregator import MarketSignal
    return MarketSignal(
        ticker="NVDA",
        signal_type="congressional",
        action="BUY",
        confidence=85.0,
        data={
            "trades": [
                {
                    "politician": "Nancy Pelosi",
                    "amount": "$1M-$5M",
                    "date": datetime.now().isoformat()
                }
            ]
        },
        timestamp=datetime.now()
    )


# Mock API Responses
@pytest.fixture
def mock_perplexity_response():
    """Mock Perplexity API response."""
    return {
        "id": "test-123",
        "model": "sonar",
        "choices": [
            {
                "message": {
                    "content": "NVIDIA stock analysis: Strong buy signal based on AI growth."
                },
                "finish_reason": "stop"
            }
        ]
    }


# Mock Configuration
@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "alpha_vantage_api_key": "test_key",
        "openai_api_key": "test_key",
        "perplexity_api_key": "test_key",
        "deep_think_llm": "gpt-4o-mini",
        "quick_think_llm": "gpt-4o-mini",
        "backend_url": "https://api.openai.com/v1",
        "risk_management": {
            "max_position_size": 0.20,
            "max_daily_loss": 0.05,
            "max_concentration": 0.30
        },
        "portfolio_tickers": ["NVDA", "MSFT", "AAPL"],
        "redis_enabled": False,
        "database_enabled": False
    }


# Mock Database Manager
@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    db = Mock()
    db.get_session = Mock()
    db.get_active_positions = AsyncMock(return_value=[])
    db.save_position = AsyncMock()
    db.save_order = AsyncMock()
    return db


# Mock IBKR Connector
@pytest.fixture
def mock_ibkr():
    """Mock IBKR connector."""
    ibkr = Mock()
    ibkr.connected = True
    ibkr.sync_portfolio = AsyncMock(return_value={})
    ibkr.place_order = AsyncMock(return_value="ORDER-123")
    ibkr.get_order_status = AsyncMock(return_value="FILLED")
    return ibkr


# Mock TradingAgentsGraph
@pytest.fixture
def mock_trading_agents_graph():
    """Mock TradingAgentsGraph to avoid OpenAI initialization."""
    graph = Mock()
    graph.propagate = Mock(return_value=("", "BUY NVDA"))
    graph.deep_thinking_llm = Mock()
    graph.quick_thinking_llm = Mock()
    return graph


# Test Data Fixtures
@pytest.fixture
def portfolio_positions():
    """Sample portfolio positions."""
    return {
        "NVDA": {"shares": 100, "avg_cost": 450.00, "current_price": 500.00},
        "MSFT": {"shares": 50, "avg_cost": 350.00, "current_price": 380.00},
        "AAPL": {"shares": 75, "avg_cost": 175.00, "current_price": 190.00}
    }