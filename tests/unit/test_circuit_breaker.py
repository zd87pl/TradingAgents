"""
Unit Tests for Circuit Breaker
===============================
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock

from autonomous.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitOpenError,
    CircuitBreakerRegistry,
    circuit_breaker
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_successful_calls(self):
        """Test circuit breaker with successful calls."""
        breaker = CircuitBreaker("test_service")

        # Create a mock async function
        async def mock_func():
            return "success"

        # Should allow calls when closed
        for _ in range(5):
            result = await breaker.call(mock_func)
            assert result == "success"

        assert breaker.stats.state == CircuitState.CLOSED
        assert breaker.stats.success_count == 5
        assert breaker.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_on_failures(self):
        """Test circuit opens after threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=1)
        breaker = CircuitBreaker("test_service", config)

        # Create a failing async function
        async def failing_func():
            raise Exception("Service error")

        # First 3 failures should be allowed
        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(failing_func)

        # Circuit should now be open
        assert breaker.stats.state == CircuitState.OPEN

        # Next call should fail immediately with CircuitOpenError
        with pytest.raises(CircuitOpenError) as exc_info:
            await breaker.call(failing_func)

        assert "Circuit breaker 'test_service' is OPEN" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        """Test circuit recovery through half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout=1
        )
        breaker = CircuitBreaker("test_service", config)

        call_count = 0

        async def intermittent_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Service error")
            return "success"

        # Trigger circuit open
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(intermittent_func)

        assert breaker.stats.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Circuit should transition to half-open on next call
        result = await breaker.call(intermittent_func)
        assert result == "success"
        assert breaker.stats.state == CircuitState.HALF_OPEN

        # One more success should close the circuit
        result = await breaker.call(intermittent_func)
        assert result == "success"
        assert breaker.stats.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        """Test failure in half-open state reopens circuit."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=1)
        breaker = CircuitBreaker("test_service", config)

        async def failing_func():
            raise Exception("Service error")

        # Open circuit
        with pytest.raises(Exception):
            await breaker.call(failing_func)

        assert breaker.stats.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Failure in half-open should reopen
        with pytest.raises(Exception):
            await breaker.call(failing_func)

        assert breaker.stats.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_statistics_tracking(self):
        """Test circuit breaker statistics."""
        breaker = CircuitBreaker("test_service")

        async def mixed_func():
            if breaker.stats.total_calls % 2 == 0:
                return "success"
            raise Exception("Error")

        # Make some calls
        for i in range(5):
            try:
                await breaker.call(mixed_func)
            except:
                pass

        stats = breaker.get_stats()

        assert stats["name"] == "test_service"
        assert stats["total_calls"] == 5
        assert stats["total_successes"] == 3
        assert stats["total_failures"] == 2
        assert stats["failure_rate"] == 40.0

    @pytest.mark.asyncio
    async def test_circuit_reset(self):
        """Test resetting circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test_service", config)

        async def failing_func():
            raise Exception("Error")

        # Open the circuit
        with pytest.raises(Exception):
            await breaker.call(failing_func)

        assert breaker.stats.state == CircuitState.OPEN

        # Reset
        breaker.reset()

        assert breaker.stats.state == CircuitState.CLOSED
        assert breaker.stats.failure_count == 0
        assert breaker.stats.total_calls == 0


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""

    @pytest.mark.asyncio
    async def test_get_or_create(self):
        """Test getting or creating circuit breakers."""
        registry = CircuitBreakerRegistry()

        # First call creates
        breaker1 = registry.get_or_create("service1")
        assert breaker1.name == "service1"

        # Second call returns same instance
        breaker2 = registry.get_or_create("service1")
        assert breaker1 is breaker2

        # Different service gets new breaker
        breaker3 = registry.get_or_create("service2")
        assert breaker3.name == "service2"
        assert breaker3 is not breaker1

    @pytest.mark.asyncio
    async def test_registry_call(self):
        """Test calling through registry."""
        registry = CircuitBreakerRegistry()

        async def test_func():
            return "result"

        result = await registry.call("test_service", test_func)
        assert result == "result"

        # Check breaker was created
        assert "test_service" in registry.breakers

    @pytest.mark.asyncio
    async def test_get_all_stats(self):
        """Test getting stats for all breakers."""
        registry = CircuitBreakerRegistry()

        # Create some breakers
        registry.get_or_create("service1")
        registry.get_or_create("service2")

        stats = registry.get_all_stats()

        assert "service1" in stats
        assert "service2" in stats
        assert stats["service1"]["name"] == "service1"
        assert stats["service2"]["name"] == "service2"

    @pytest.mark.asyncio
    async def test_reset_all(self):
        """Test resetting all circuit breakers."""
        registry = CircuitBreakerRegistry()

        async def failing_func():
            raise Exception("Error")

        # Open some circuits
        for service in ["service1", "service2"]:
            try:
                config = CircuitBreakerConfig(failure_threshold=1)
                await registry.call(service, failing_func, config=config)
            except:
                pass

        # Both should be open
        assert registry.breakers["service1"].stats.state == CircuitState.OPEN
        assert registry.breakers["service2"].stats.state == CircuitState.OPEN

        # Reset all
        registry.reset_all()

        # All should be closed
        assert registry.breakers["service1"].stats.state == CircuitState.CLOSED
        assert registry.breakers["service2"].stats.state == CircuitState.CLOSED


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator."""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator functionality."""
        call_count = 0

        @circuit_breaker(name="decorated_service", failure_threshold=2)
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Error")
            return "success"

        # First two calls fail
        for _ in range(2):
            with pytest.raises(Exception):
                await decorated_func()

        # Third call should be blocked
        with pytest.raises(CircuitOpenError):
            await decorated_func()

    @pytest.mark.asyncio
    async def test_decorator_stats_access(self):
        """Test accessing stats through decorated function."""

        @circuit_breaker(name="stats_service")
        async def func_with_stats():
            return "result"

        await func_with_stats()

        # Should have stats method
        stats = func_with_stats.get_circuit_stats()
        assert stats["name"] == "stats_service"
        assert stats["total_calls"] == 1
        assert stats["total_successes"] == 1