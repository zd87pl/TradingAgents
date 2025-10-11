"""
Integration Tests for Signal Processing Pipeline
================================================

Tests the full flow from data aggregation through signal processing.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from autonomous.data_aggregator import DataAggregator, MarketSignal
from autonomous.signal_processor import SignalProcessor, TradingRecommendation
from autonomous.core.signal_deduplicator import SignalDeduplicator
from autonomous.core.circuit_breaker import CircuitBreakerRegistry
from autonomous.core.rate_limiter import DistributedRateLimiter


class TestSignalPipeline:
    """Test complete signal processing pipeline."""

    @pytest.mark.asyncio
    async def test_congressional_trade_to_recommendation(self, test_config):
        """Test flow from congressional trade detection to trading recommendation."""
        # Setup
        aggregator = DataAggregator(test_config)
        processor = SignalProcessor(aggregator, test_config)

        # Mock congressional trades
        with patch.object(aggregator, 'fetch_congressional_trades') as mock_congress:
            mock_congress.return_value = [
                Mock(
                    politician="Nancy Pelosi",
                    ticker="NVDA",
                    action="purchase",
                    amount_range="$1M-$5M",
                    transaction_date=datetime.now() - timedelta(days=2),
                    filing_date=datetime.now(),
                    party="D",
                    state="CA",
                    chamber="house"
                )
            ]

            # Mock market sentiment
            with patch.object(aggregator, 'fetch_market_sentiment') as mock_sentiment:
                mock_sentiment.return_value = {
                    'ticker': 'NVDA',
                    'overall_sentiment': 'positive',
                    'sentiment_score': 0.7
                }

                # Mock technical levels
                with patch.object(processor, '_calculate_technical_levels_sync') as mock_tech:
                    mock_tech.return_value = {
                        'current_price': 500.0,
                        'resistance_1': 520.0,
                        'resistance_2': 540.0,
                        'support_1': 480.0,
                        'support_2': 460.0,
                        'rsi': 45.0
                    }

                    # Mock TradingAgents analysis
                    with patch.object(processor.trading_agents, 'propagate') as mock_ai:
                        mock_ai.return_value = ("", "Strong BUY signal based on fundamentals")

                        # Execute pipeline
                        signals = await aggregator.aggregate_signals(["NVDA"])
                        assert len(signals) > 0

                        recommendations = await processor.process_signals(["NVDA"])
                        assert len(recommendations) > 0

                        rec = recommendations[0]
                        assert rec.ticker == "NVDA"
                        assert rec.action == "BUY"
                        assert rec.confidence >= 70  # High confidence from congressional trade

    @pytest.mark.asyncio
    async def test_deduplication_in_pipeline(self, test_config, mock_redis_cache):
        """Test that duplicate signals are filtered in the pipeline."""
        # Setup with deduplication
        aggregator = DataAggregator(test_config)
        aggregator.cache = mock_redis_cache

        # Mock to return duplicate signals
        duplicate_signal = MarketSignal(
            ticker="MSFT",
            signal_type="insider",
            action="BUY",
            confidence=80.0,
            data={"insider_name": "CEO", "net_buying": 1000000},
            timestamp=datetime.now()
        )

        with patch.object(aggregator, 'fetch_insider_trades') as mock_insider:
            mock_insider.return_value = [
                Mock(
                    insider_name="CEO",
                    ticker="MSFT",
                    action="Buy",
                    shares=10000,
                    value=1000000,
                    transaction_date=datetime.now() - timedelta(days=5),
                    position="CEO"
                )
            ]

            # Configure deduplicator mock
            mock_redis_cache.redis.exists = AsyncMock(side_effect=[False, True])  # First new, then duplicate
            mock_redis_cache.redis.setex = AsyncMock()

            # First aggregation
            signals1 = await aggregator.aggregate_signals(["MSFT"])
            initial_count = len(signals1)

            # Second aggregation (should deduplicate)
            signals2 = await aggregator.aggregate_signals(["MSFT"])

            # Should have same or fewer signals due to deduplication
            assert len(signals2) <= initial_count

    @pytest.mark.asyncio
    async def test_circuit_breaker_protection(self, test_config):
        """Test circuit breaker protects against failing data sources."""
        aggregator = DataAggregator(test_config)

        # Simulate news API failures
        with patch('autonomous.data_aggregator.get_news') as mock_news:
            mock_news.side_effect = Exception("API Error")

            # Should handle gracefully without crashing
            sentiment = await aggregator.fetch_market_sentiment("AAPL")

            # Should return default sentiment when news fails
            assert sentiment['overall_sentiment'] == 'neutral'
            assert sentiment['sentiment_score'] == 0.0

    @pytest.mark.asyncio
    async def test_async_performance(self, test_config):
        """Test that async processing is non-blocking."""
        processor = SignalProcessor(Mock(), test_config)

        # Mock slow operations
        with patch.object(processor, '_calculate_technical_levels_sync') as mock_tech:
            # Simulate slow calculation
            def slow_calc(ticker):
                import time
                time.sleep(0.1)  # Simulate 100ms processing
                return {'current_price': 100.0}

            mock_tech.side_effect = slow_calc

            with patch.object(processor.trading_agents, 'propagate') as mock_ai:
                # Simulate slow AI
                def slow_ai(ticker, date):
                    import time
                    time.sleep(0.1)  # Simulate 100ms processing
                    return ("", "BUY")

                mock_ai.side_effect = slow_ai

                # Process multiple tickers concurrently
                start_time = asyncio.get_event_loop().time()

                tasks = [
                    processor.calculate_technical_levels("AAPL"),
                    processor.calculate_technical_levels("GOOGL"),
                    processor.calculate_technical_levels("MSFT")
                ]

                results = await asyncio.gather(*tasks)

                elapsed = asyncio.get_event_loop().time() - start_time

                # Should complete in ~100ms (concurrent) not 300ms (sequential)
                assert elapsed < 0.2  # Allow some overhead
                assert len(results) == 3

    @pytest.mark.asyncio
    async def test_multi_signal_aggregation(self, test_config):
        """Test aggregating signals from multiple sources."""
        aggregator = DataAggregator(test_config)

        # Mock multiple data sources
        with patch.object(aggregator, 'fetch_congressional_trades') as mock_congress:
            mock_congress.return_value = [
                Mock(ticker="TSLA", action="purchase", politician="Test1",
                     amount_range="$100K", transaction_date=datetime.now() - timedelta(days=1),
                     filing_date=datetime.now(), party="D", state="CA", chamber="house")
            ]

            with patch.object(aggregator, 'fetch_insider_trades') as mock_insider:
                mock_insider.return_value = [
                    Mock(ticker="TSLA", action="Buy", insider_name="CEO",
                         shares=50000, value=10000000,
                         transaction_date=datetime.now() - timedelta(days=3),
                         position="CEO")
                ]

                with patch.object(aggregator, 'fetch_market_sentiment') as mock_sentiment:
                    mock_sentiment.return_value = {
                        'overall_sentiment': 'positive',
                        'sentiment_score': 0.8
                    }

                    # Aggregate all signals
                    signals = await aggregator.aggregate_signals(["TSLA"])

                    # Should have multiple signal types
                    signal_types = {s.signal_type for s in signals}
                    assert "congressional" in signal_types
                    assert "insider" in signal_types

                    # All should be for TSLA
                    assert all(s.ticker == "TSLA" for s in signals)

                    # Should be sorted by confidence
                    confidences = [s.confidence for s in signals]
                    assert confidences == sorted(confidences, reverse=True)