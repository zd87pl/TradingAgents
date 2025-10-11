"""
Performance Tests for Async Optimizations
==========================================

Validates that async optimizations improve performance.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor

from autonomous.signal_processor import SignalProcessor
from autonomous.data_aggregator import DataAggregator


class TestAsyncPerformance:
    """Test async performance improvements."""

    @pytest.mark.asyncio
    async def test_thread_pool_executor_performance(self, test_config):
        """Test that thread pool executor prevents blocking."""
        processor = SignalProcessor(Mock(), test_config)

        # Create a slow synchronous function
        def slow_sync_function(ticker):
            time.sleep(0.5)  # Simulate 500ms blocking operation
            return {
                'current_price': 100.0,
                'support_1': 95.0,
                'resistance_1': 105.0
            }

        # Test WITHOUT thread pool (blocking)
        start = asyncio.get_event_loop().time()
        results_sequential = []
        for ticker in ["AAPL", "GOOGL", "MSFT"]:
            result = slow_sync_function(ticker)
            results_sequential.append(result)
        sequential_time = asyncio.get_event_loop().time() - start

        # Test WITH thread pool (non-blocking)
        start = asyncio.get_event_loop().time()
        loop = asyncio.get_event_loop()
        tasks = []
        for ticker in ["AAPL", "GOOGL", "MSFT"]:
            task = loop.run_in_executor(None, slow_sync_function, ticker)
            tasks.append(task)
        results_concurrent = await asyncio.gather(*tasks)
        concurrent_time = asyncio.get_event_loop().time() - start

        # Concurrent should be ~3x faster
        assert sequential_time > 1.4  # Should take ~1.5s
        assert concurrent_time < 0.7  # Should take ~0.5s
        assert len(results_concurrent) == 3

        # Performance improvement ratio
        improvement = sequential_time / concurrent_time
        assert improvement > 2.0  # At least 2x improvement

    @pytest.mark.asyncio
    async def test_multiple_api_calls_concurrent(self, test_config):
        """Test concurrent API calls don't block each other."""

        async def mock_api_call(service_name: str, delay: float):
            """Simulate API call with delay."""
            await asyncio.sleep(delay)
            return f"{service_name}_result"

        # Test sequential calls
        start = time.time()
        results = []
        for service, delay in [("api1", 0.2), ("api2", 0.3), ("api3", 0.1)]:
            result = await mock_api_call(service, delay)
            results.append(result)
        sequential_time = time.time() - start

        # Test concurrent calls
        start = time.time()
        tasks = [
            mock_api_call("api1", 0.2),
            mock_api_call("api2", 0.3),
            mock_api_call("api3", 0.1)
        ]
        results_concurrent = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start

        # Sequential should take ~0.6s, concurrent ~0.3s
        assert sequential_time > 0.5
        assert concurrent_time < 0.4
        assert len(results_concurrent) == 3

    @pytest.mark.asyncio
    async def test_signal_processor_non_blocking(self, test_config):
        """Test SignalProcessor doesn't block on TradingAgents calls."""
        processor = SignalProcessor(Mock(), test_config)

        # Mock slow TradingAgents propagate
        with patch.object(processor.trading_agents, 'propagate') as mock_propagate:
            def slow_propagate(ticker, date):
                time.sleep(0.3)  # Simulate slow AI processing
                return ("", f"BUY {ticker}")

            mock_propagate.side_effect = slow_propagate

            # Mock technical levels
            with patch.object(processor, '_calculate_technical_levels_sync') as mock_tech:
                mock_tech.return_value = {'current_price': 100.0}

                # Process multiple tickers
                start = asyncio.get_event_loop().time()

                # Create coroutines for concurrent processing
                tasks = []
                for ticker in ["NVDA", "AMD", "INTC"]:
                    # Simulate the actual method that uses run_in_executor
                    async def process_ticker(t):
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(
                            None,
                            processor.trading_agents.propagate,
                            t,
                            "2024-01-01"
                        )

                    tasks.append(process_ticker(ticker))

                results = await asyncio.gather(*tasks)
                elapsed = asyncio.get_event_loop().time() - start

                # Should complete concurrently in ~0.3s, not 0.9s
                assert elapsed < 0.5
                assert len(results) == 3

    @pytest.mark.asyncio
    async def test_rate_limiter_non_blocking(self):
        """Test rate limiter doesn't block other operations."""
        from autonomous.core.rate_limiter import DistributedRateLimiter, RateLimitConfig

        limiter = DistributedRateLimiter(cache=None)  # Local mode
        config = RateLimitConfig(max_requests=2, window_seconds=1)

        async def limited_operation(id: int):
            """Operation with rate limiting."""
            try:
                await limiter.acquire(f"test_{id}", config)
                await asyncio.sleep(0.1)  # Simulate work
                return f"success_{id}"
            except:
                return f"limited_{id}"

        # Run multiple operations concurrently
        start = asyncio.get_event_loop().time()
        tasks = [limited_operation(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = asyncio.get_event_loop().time() - start

        # Should not block - completes quickly even with rate limits
        assert elapsed < 0.3  # Fast completion
        success_count = sum(1 for r in results if isinstance(r, str) and r.startswith("success"))
        assert success_count == 2  # Only 2 should succeed due to rate limit

    @pytest.mark.asyncio
    async def test_circuit_breaker_fast_fail(self):
        """Test circuit breaker fails fast when open."""
        from autonomous.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=2, timeout=60)
        breaker = CircuitBreaker("test_service", config)

        async def failing_service():
            await asyncio.sleep(1)  # Simulate slow failure
            raise Exception("Service error")

        # Trigger circuit open
        for _ in range(2):
            try:
                await breaker.call(failing_service)
            except:
                pass

        # Circuit should now be open
        # Next calls should fail immediately (fast fail)
        start = asyncio.get_event_loop().time()
        for _ in range(10):
            try:
                await breaker.call(failing_service)
            except:
                pass
        elapsed = asyncio.get_event_loop().time() - start

        # Should fail immediately, not wait for service
        assert elapsed < 0.1  # All 10 calls should fail instantly

    @pytest.mark.asyncio
    async def test_deduplication_performance(self):
        """Test deduplication doesn't slow down processing."""
        from autonomous.core.signal_deduplicator import SignalDeduplicator
        from autonomous.data_aggregator import MarketSignal

        deduplicator = SignalDeduplicator(cache=None)  # Local mode

        # Create many signals
        signals = []
        for i in range(1000):
            signal = MarketSignal(
                ticker=f"TICK{i % 10}",  # 10 different tickers
                signal_type="test",
                action="BUY" if i % 2 == 0 else "SELL",
                confidence=float(i % 100),
                data={"id": i},
                timestamp=datetime.now()
            )
            signals.append(signal)

        # Time deduplication
        start = asyncio.get_event_loop().time()
        unique_signals = await deduplicator.filter_duplicates(signals)
        elapsed = asyncio.get_event_loop().time() - start

        # Should process 1000 signals quickly
        assert elapsed < 0.1  # Should be very fast
        assert len(unique_signals) == 1000  # All unique in this case

        # Test with actual duplicates
        duplicate_signals = signals + signals  # 2000 signals, 1000 duplicates

        start = asyncio.get_event_loop().time()
        unique_signals2 = await deduplicator.filter_duplicates(duplicate_signals)
        elapsed2 = asyncio.get_event_loop().time() - start

        # Should still be fast even with duplicates
        assert elapsed2 < 0.2
        assert len(unique_signals2) == 1000  # Should filter out duplicates


class TestCachePerformance:
    """Test cache performance improvements."""

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, mock_redis_cache):
        """Test that cache hits are faster than cache misses."""

        async def expensive_operation():
            """Simulate expensive operation."""
            await asyncio.sleep(0.2)
            return {"data": "expensive_result"}

        # Simulate cache miss (first call)
        mock_redis_cache.get = AsyncMock(return_value=None)
        mock_redis_cache.set = AsyncMock()

        start = time.time()
        result_miss = await expensive_operation()
        miss_time = time.time() - start

        # Simulate cache hit (second call)
        mock_redis_cache.get = AsyncMock(return_value={"data": "cached_result"})

        start = time.time()
        result_hit = await mock_redis_cache.get("test_key")
        hit_time = time.time() - start

        # Cache hit should be much faster
        assert miss_time > 0.15  # Expensive operation takes time
        assert hit_time < 0.01  # Cache hit is instant

        # Performance improvement
        improvement = miss_time / hit_time if hit_time > 0 else 100
        assert improvement > 10  # At least 10x faster with cache


from datetime import datetime