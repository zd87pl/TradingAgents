"""
Unit Tests for Signal Deduplicator
===================================
"""

import pytest
import asyncio
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from autonomous.core.signal_deduplicator import (
    SignalDeduplicator,
    SignalFingerprint,
    SmartSignalAggregator
)
from autonomous.data_aggregator import MarketSignal


class TestSignalFingerprint:
    """Test signal fingerprint generation."""

    def test_fingerprint_creation(self):
        """Test creating signal fingerprints."""
        fp = SignalFingerprint(
            ticker="NVDA",
            signal_type="congressional",
            action="BUY",
            source_id="pelosi_2024-01-01",
            date="2024-01-01"
        )

        hash1 = fp.hash()
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex length

        # Same data should produce same hash
        fp2 = SignalFingerprint(
            ticker="NVDA",
            signal_type="congressional",
            action="BUY",
            source_id="pelosi_2024-01-01",
            date="2024-01-01"
        )
        assert fp2.hash() == hash1

        # Different data should produce different hash
        fp3 = SignalFingerprint(
            ticker="MSFT",  # Different ticker
            signal_type="congressional",
            action="BUY",
            source_id="pelosi_2024-01-01",
            date="2024-01-01"
        )
        assert fp3.hash() != hash1


class TestSignalDeduplicator:
    """Test signal deduplication functionality."""

    @pytest.mark.asyncio
    async def test_duplicate_detection_local(self):
        """Test duplicate detection with local cache."""
        deduplicator = SignalDeduplicator(cache=None)  # Use local cache

        signal = MarketSignal(
            ticker="NVDA",
            signal_type="congressional",
            action="BUY",
            confidence=85.0,
            data={"trades": [{"politician": "Test", "date": "2024-01-01"}]},
            timestamp=datetime.now()
        )

        # First occurrence should not be duplicate
        is_dup = await deduplicator.is_duplicate(signal)
        assert is_dup is False

        # Same signal should be duplicate
        is_dup = await deduplicator.is_duplicate(signal)
        assert is_dup is True

        # Different signal should not be duplicate
        signal2 = MarketSignal(
            ticker="MSFT",  # Different ticker
            signal_type="congressional",
            action="BUY",
            confidence=85.0,
            data={"trades": [{"politician": "Test", "date": "2024-01-01"}]},
            timestamp=datetime.now()
        )
        is_dup = await deduplicator.is_duplicate(signal2)
        assert is_dup is False

    @pytest.mark.asyncio
    async def test_duplicate_detection_redis(self, mock_redis_cache):
        """Test duplicate detection with Redis cache."""
        mock_redis_cache.redis.exists = AsyncMock(side_effect=[False, True])
        mock_redis_cache.redis.setex = AsyncMock()

        deduplicator = SignalDeduplicator(cache=mock_redis_cache, ttl_days=7)

        signal = MarketSignal(
            ticker="NVDA",
            signal_type="insider",
            action="SELL",
            confidence=75.0,
            data={"insider_name": "CEO", "net_buying": -1000000},
            timestamp=datetime.now()
        )

        # First check - not duplicate
        is_dup = await deduplicator.is_duplicate(signal)
        assert is_dup is False
        mock_redis_cache.redis.setex.assert_called_once()

        # Second check - is duplicate
        is_dup = await deduplicator.is_duplicate(signal)
        assert is_dup is True

    @pytest.mark.asyncio
    async def test_filter_duplicates(self, mock_redis_cache):
        """Test filtering duplicate signals from a list."""
        mock_redis_cache.redis.exists = AsyncMock(side_effect=[False, False, True, False])
        mock_redis_cache.redis.setex = AsyncMock()

        deduplicator = SignalDeduplicator(cache=mock_redis_cache)

        signals = [
            MarketSignal(
                ticker="NVDA",
                signal_type="congressional",
                action="BUY",
                confidence=85.0,
                data={"trades": [{"politician": "Pelosi", "date": "2024-01-01"}]},
                timestamp=datetime.now()
            ),
            MarketSignal(
                ticker="MSFT",
                signal_type="insider",
                action="SELL",
                confidence=70.0,
                data={"insider_name": "CFO", "net_buying": -500000},
                timestamp=datetime.now()
            ),
            MarketSignal(
                ticker="NVDA",  # Duplicate
                signal_type="congressional",
                action="BUY",
                confidence=85.0,
                data={"trades": [{"politician": "Pelosi", "date": "2024-01-01"}]},
                timestamp=datetime.now()
            ),
            MarketSignal(
                ticker="AAPL",
                signal_type="technical",
                action="BUY",
                confidence=65.0,
                data={"rsi": 30, "ma_signal": "bullish"},
                timestamp=datetime.now()
            )
        ]

        unique_signals = await deduplicator.filter_duplicates(signals)

        # Should filter out one duplicate
        assert len(unique_signals) == 3
        assert all(s.ticker != "NVDA" or i == 0 for i, s in enumerate(unique_signals))

    @pytest.mark.asyncio
    async def test_mark_processed(self, mock_redis_cache):
        """Test marking signal as processed."""
        mock_redis_cache.redis.setex = AsyncMock()

        deduplicator = SignalDeduplicator(cache=mock_redis_cache, ttl_days=5)

        signal = MarketSignal(
            ticker="TSLA",
            signal_type="earnings",
            action="HOLD",
            confidence=60.0,
            data={"earnings_date": "2024-01-15"},
            timestamp=datetime.now()
        )

        await deduplicator.mark_processed(signal)

        # Should have called setex with TTL
        mock_redis_cache.redis.setex.assert_called_once()
        call_args = mock_redis_cache.redis.setex.call_args
        assert call_args[0][1] == 5 * 24 * 3600  # 5 days in seconds

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_redis_cache):
        """Test getting deduplication statistics."""
        mock_redis_cache.redis.keys = AsyncMock(return_value=["key1", "key2", "key3"])

        deduplicator = SignalDeduplicator(cache=mock_redis_cache)
        stats = await deduplicator.get_stats()

        assert stats["backend"] == "redis"
        assert stats["processed_count"] == 3
        assert stats["ttl_days"] == 7

    @pytest.mark.asyncio
    async def test_clear_history(self, mock_redis_cache):
        """Test clearing deduplication history."""
        mock_redis_cache.redis.keys = AsyncMock(return_value=["key1", "key2"])
        mock_redis_cache.redis.delete = AsyncMock()

        deduplicator = SignalDeduplicator(cache=mock_redis_cache)
        await deduplicator.clear()

        mock_redis_cache.redis.keys.assert_called_once_with("signal:processed:*")
        mock_redis_cache.redis.delete.assert_called_once_with("key1", "key2")


class TestSmartSignalAggregator:
    """Test smart signal aggregation."""

    @pytest.mark.asyncio
    async def test_aggregate_signals(self, mock_redis_cache):
        """Test aggregating signals with deduplication."""
        mock_redis_cache.redis.exists = AsyncMock(return_value=False)
        mock_redis_cache.redis.setex = AsyncMock()

        deduplicator = SignalDeduplicator(cache=mock_redis_cache)
        aggregator = SmartSignalAggregator(deduplicator)

        new_signals = [
            MarketSignal(
                ticker="NVDA",
                signal_type="congressional",
                action="BUY",
                confidence=85.0,
                data={},
                timestamp=datetime.now()
            ),
            MarketSignal(
                ticker="NVDA",
                signal_type="insider",
                action="BUY",
                confidence=70.0,
                data={},
                timestamp=datetime.now()
            ),
            MarketSignal(
                ticker="NVDA",
                signal_type="technical",
                action="SELL",
                confidence=60.0,
                data={},
                timestamp=datetime.now()
            ),
            MarketSignal(
                ticker="MSFT",
                signal_type="congressional",
                action="BUY",
                confidence=75.0,
                data={},
                timestamp=datetime.now()
            )
        ]

        aggregated = await aggregator.aggregate_signals(new_signals)

        # Should keep highest confidence per ticker/action
        assert len(aggregated) == 3  # NVDA BUY (best), NVDA SELL, MSFT BUY

        # Should be sorted by confidence
        assert aggregated[0].confidence == 85.0  # NVDA BUY congressional
        assert aggregated[1].confidence == 75.0  # MSFT BUY
        assert aggregated[2].confidence == 60.0  # NVDA SELL

    @pytest.mark.asyncio
    async def test_merge_with_existing(self, mock_redis_cache):
        """Test merging new signals with existing ones."""
        mock_redis_cache.redis.exists = AsyncMock(return_value=False)
        mock_redis_cache.redis.setex = AsyncMock()

        deduplicator = SignalDeduplicator(cache=mock_redis_cache)
        aggregator = SmartSignalAggregator(deduplicator)

        existing = [
            MarketSignal(
                ticker="AAPL",
                signal_type="technical",
                action="BUY",
                confidence=70.0,
                data={},
                timestamp=datetime.now() - timedelta(hours=1)
            )
        ]

        new_signals = [
            MarketSignal(
                ticker="AAPL",
                signal_type="congressional",
                action="BUY",
                confidence=90.0,  # Higher confidence
                data={},
                timestamp=datetime.now()
            ),
            MarketSignal(
                ticker="GOOGL",
                signal_type="insider",
                action="SELL",
                confidence=80.0,
                data={},
                timestamp=datetime.now()
            )
        ]

        aggregated = await aggregator.aggregate_signals(new_signals, existing)

        # Should have 2 signals: AAPL BUY (best) and GOOGL SELL
        assert len(aggregated) == 2
        assert aggregated[0].ticker == "AAPL"
        assert aggregated[0].confidence == 90.0  # Chose higher confidence
        assert aggregated[1].ticker == "GOOGL"