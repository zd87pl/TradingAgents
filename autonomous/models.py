"""
Shared Data Models
==================

Common data structures used across the autonomous trading system.
This module prevents circular dependencies between components.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class TradingRecommendation:
    """Complete trading recommendation with entry/exit points"""
    ticker: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    current_price: float
    entry_price_min: float
    entry_price_max: float
    target_price_1: float
    target_price_2: float
    stop_loss: float
    confidence: float  # 0-100
    position_size: float  # Percentage of portfolio
    reasoning: str
    data_sources: List[str]
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    timestamp: datetime
