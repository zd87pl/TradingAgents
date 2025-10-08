"""
Circuit Breaker Pattern
========================

Prevents cascading failures by stopping requests to failing services.
"""

import asyncio
import time
from typing import Optional, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures detected, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes in half-open before closing
    timeout: int = 60  # Seconds before trying half-open
    expected_exception: type = Exception  # Exception types to track


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    state_changes: list = field(default_factory=list)


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.

        Args:
            name: Name of the service
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs):
        """
        Call function through circuit breaker.

        Args:
            func: Async function to call
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Original exception: If function fails
        """
        async with self._lock:
            self._check_state()

        if self.stats.state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Service unavailable for {self._time_until_half_open():.0f}s"
            )

        try:
            # Execute the function
            result = await func(*args, **kwargs)

            async with self._lock:
                self._on_success()

            return result

        except self.config.expected_exception as e:
            async with self._lock:
                self._on_failure()
            raise

    def _check_state(self):
        """Check and update circuit state"""
        if self.stats.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.stats.last_failure_time:
                elapsed = time.time() - self.stats.last_failure_time
                if elapsed >= self.config.timeout:
                    self._transition_to(CircuitState.HALF_OPEN)

    def _on_success(self):
        """Handle successful call"""
        self.stats.success_count += 1
        self.stats.total_successes += 1
        self.stats.total_calls += 1
        self.stats.last_success_time = time.time()

        if self.stats.state == CircuitState.HALF_OPEN:
            if self.stats.success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def _on_failure(self):
        """Handle failed call"""
        self.stats.failure_count += 1
        self.stats.total_failures += 1
        self.stats.total_calls += 1
        self.stats.last_failure_time = time.time()

        if self.stats.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self.stats.state == CircuitState.CLOSED:
            if self.stats.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """Transition to new state"""
        old_state = self.stats.state
        self.stats.state = new_state

        # Reset counters
        if new_state == CircuitState.CLOSED:
            self.stats.failure_count = 0
            self.stats.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.stats.success_count = 0

        # Log transition
        transition = {
            'timestamp': datetime.now().isoformat(),
            'from': old_state.value,
            'to': new_state.value
        }
        self.stats.state_changes.append(transition)

        logger.info(f"Circuit breaker '{self.name}': {old_state.value} → {new_state.value}")

    def _time_until_half_open(self) -> float:
        """Calculate seconds until circuit can transition to half-open"""
        if self.stats.last_failure_time:
            elapsed = time.time() - self.stats.last_failure_time
            return max(0, self.config.timeout - elapsed)
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            'name': self.name,
            'state': self.stats.state.value,
            'failure_count': self.stats.failure_count,
            'success_count': self.stats.success_count,
            'total_calls': self.stats.total_calls,
            'total_failures': self.stats.total_failures,
            'total_successes': self.stats.total_successes,
            'failure_rate': (
                self.stats.total_failures / self.stats.total_calls * 100
                if self.stats.total_calls > 0 else 0
            ),
            'last_failure': (
                datetime.fromtimestamp(self.stats.last_failure_time).isoformat()
                if self.stats.last_failure_time else None
            ),
            'state_changes': self.stats.state_changes[-5:]  # Last 5 transitions
        }

    def reset(self):
        """Reset circuit breaker to closed state"""
        self.stats = CircuitBreakerStats()
        logger.info(f"Circuit breaker '{self.name}' reset")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    """

    def __init__(self):
        """Initialize registry"""
        self.breakers: Dict[str, CircuitBreaker] = {}

    def get_or_create(self,
                      name: str,
                      config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get existing or create new circuit breaker.

        Args:
            name: Service name
            config: Circuit breaker configuration

        Returns:
            Circuit breaker instance
        """
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, config)

        return self.breakers[name]

    async def call(self,
                  service_name: str,
                  func: Callable,
                  *args,
                  config: Optional[CircuitBreakerConfig] = None,
                  **kwargs):
        """
        Call function through circuit breaker for service.

        Args:
            service_name: Name of the service
            func: Async function to call
            config: Optional config override
            *args, **kwargs: Function arguments

        Returns:
            Function result
        """
        breaker = self.get_or_create(service_name, config)
        return await breaker.call(func, *args, **kwargs)

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all circuit breakers"""
        return {
            name: breaker.get_stats()
            for name, breaker in self.breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self.breakers.values():
            breaker.reset()


# Global registry instance
circuit_breaker_registry = CircuitBreakerRegistry()


def circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: int = 5,
    timeout: int = 60,
    expected_exception: type = Exception
):
    """
    Decorator for applying circuit breaker to async functions.

    Args:
        name: Circuit breaker name (defaults to function name)
        failure_threshold: Failures before opening
        timeout: Seconds before trying half-open
        expected_exception: Exception types to track

    Example:
        @circuit_breaker(name="alpha_vantage", failure_threshold=3)
        async def fetch_stock_data(ticker):
            return await api.get_stock(ticker)
    """
    def decorator(func):
        breaker_name = name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = CircuitBreakerConfig(
                failure_threshold=failure_threshold,
                timeout=timeout,
                expected_exception=expected_exception
            )

            return await circuit_breaker_registry.call(
                breaker_name,
                func,
                *args,
                config=config,
                **kwargs
            )

        # Add method to get stats
        wrapper.get_circuit_stats = lambda: circuit_breaker_registry.breakers[breaker_name].get_stats()

        return wrapper
    return decorator


# Convenience functions for common services
class ServiceBreakers:
    """Pre-configured circuit breakers for common services"""

    @staticmethod
    @circuit_breaker(name="perplexity", failure_threshold=5, timeout=60)
    async def call_perplexity(func, *args, **kwargs):
        """Circuit breaker for Perplexity API"""
        return await func(*args, **kwargs)

    @staticmethod
    @circuit_breaker(name="alpha_vantage", failure_threshold=3, timeout=30)
    async def call_alpha_vantage(func, *args, **kwargs):
        """Circuit breaker for Alpha Vantage API"""
        return await func(*args, **kwargs)

    @staticmethod
    @circuit_breaker(name="ibkr", failure_threshold=3, timeout=10)
    async def call_ibkr(func, *args, **kwargs):
        """Circuit breaker for IBKR connection"""
        return await func(*args, **kwargs)

    @staticmethod
    @circuit_breaker(name="openai", failure_threshold=5, timeout=60)
    async def call_openai(func, *args, **kwargs):
        """Circuit breaker for OpenAI API"""
        return await func(*args, **kwargs)