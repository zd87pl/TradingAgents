"""
Unit Tests for Rate Limiter
============================
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock

from autonomous.core.rate_limiter import (
    DistributedRateLimiter,
    RateLimitConfig,
    RateLimitStrategy,
    RateLimitExceeded,
    APIRateLimiter
)


class TestDistributedRateLimiter:
    """Test distributed rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_sliding_window_local(self):
        """Test sliding window rate limiting with local fallback."""
        limiter = DistributedRateLimiter(cache=None)  # Use local fallback
        config = RateLimitConfig(max_requests=3, window_seconds=1)

        # Should allow first 3 requests
        for i in range(3):
            result = await limiter.acquire("test_api", config)
            assert result is True

        # 4th request should fail
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.acquire("test_api", config)

        assert exc_info.value.retry_after > 0

        # Wait for window to expire
        await asyncio.sleep(1.1)

        # Should allow request again
        result = await limiter.acquire("test_api", config)
        assert result is True

    @pytest.mark.asyncio
    async def test_sliding_window_redis(self, mock_redis_cache):
        """Test sliding window with Redis backend."""
        mock_redis_cache.redis.zremrangebyscore = AsyncMock()
        mock_redis_cache.redis.zcard = AsyncMock(return_value=2)  # 2 requests already
        mock_redis_cache.redis.zadd = AsyncMock()
        mock_redis_cache.redis.expire = AsyncMock()
        mock_redis_cache.redis.zrange = AsyncMock(return_value=[])

        limiter = DistributedRateLimiter(cache=mock_redis_cache)
        config = RateLimitConfig(max_requests=3, window_seconds=60)

        # Should allow (2 existing + 1 new = 3 total)
        result = await limiter.acquire("test_api", config)
        assert result is True
        mock_redis_cache.redis.zadd.assert_called_once()

        # Next request should fail (would be 4th)
        mock_redis_cache.redis.zcard.return_value = 3
        with pytest.raises(RateLimitExceeded):
            await limiter.acquire("test_api", config)

    @pytest.mark.asyncio
    async def test_token_bucket_burst(self, mock_redis_cache):
        """Test token bucket with burst capacity."""
        # Mock Redis eval for Lua script
        mock_redis_cache.redis.eval = AsyncMock(return_value=1)  # Success

        limiter = DistributedRateLimiter(cache=mock_redis_cache)
        config = RateLimitConfig(
            max_requests=10,
            window_seconds=60,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            burst_capacity=20
        )

        # Should allow request
        result = await limiter.acquire("test_api", config)
        assert result is True

        # Test exhaustion
        mock_redis_cache.redis.eval.return_value = 5  # Retry after 5 seconds
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.acquire("test_api", config)
        assert exc_info.value.retry_after == 5

    @pytest.mark.asyncio
    async def test_reset_limits(self, mock_redis_cache):
        """Test resetting rate limits."""
        mock_redis_cache.redis.keys = AsyncMock(return_value=["key1", "key2"])
        mock_redis_cache.redis.delete = AsyncMock()

        limiter = DistributedRateLimiter(cache=mock_redis_cache)
        await limiter.reset("test_api")

        mock_redis_cache.redis.keys.assert_called_once()
        mock_redis_cache.redis.delete.assert_called_once_with("key1", "key2")

    @pytest.mark.asyncio
    async def test_get_status(self, mock_redis_cache):
        """Test getting rate limit status."""
        mock_redis_cache.redis.zremrangebyscore = AsyncMock()
        mock_redis_cache.redis.zcard = AsyncMock(return_value=7)
        mock_redis_cache.redis.zrange = AsyncMock(return_value=[(b"123", 100.0)])

        limiter = DistributedRateLimiter(cache=mock_redis_cache)
        config = RateLimitConfig(max_requests=10, window_seconds=60)

        status = await limiter.get_status("test_api", config)

        assert status["current"] == 7
        assert status["limit"] == 10
        assert status["remaining"] == 3
        assert status["strategy"] == "sliding_window"


class TestAPIRateLimiter:
    """Test API-specific rate limiter."""

    @pytest.mark.asyncio
    async def test_acquire_api(self, mock_redis_cache):
        """Test API-specific rate limiting."""
        limiter = APIRateLimiter(cache=mock_redis_cache)

        # Mock successful acquisition
        mock_redis_cache.redis.zcard = AsyncMock(return_value=0)
        mock_redis_cache.redis.zadd = AsyncMock()
        mock_redis_cache.redis.expire = AsyncMock()
        mock_redis_cache.redis.zremrangebyscore = AsyncMock()

        # Test known API
        result = await limiter.acquire_api("perplexity", "api_key_hash")
        assert result is True

        # Test unknown API (should allow)
        result = await limiter.acquire_api("unknown_api")
        assert result is True

    @pytest.mark.asyncio
    async def test_with_retry(self, mock_redis_cache):
        """Test automatic retry on rate limit."""
        limiter = APIRateLimiter(cache=mock_redis_cache)

        # Create a mock async function
        mock_func = AsyncMock(return_value="success")

        # First attempt fails with rate limit, second succeeds
        mock_redis_cache.redis.zcard = AsyncMock(side_effect=[5, 0])  # Over limit, then under
        mock_redis_cache.redis.zadd = AsyncMock()
        mock_redis_cache.redis.expire = AsyncMock()
        mock_redis_cache.redis.zremrangebyscore = AsyncMock()
        mock_redis_cache.redis.zrange = AsyncMock(return_value=[(b"123", time.time())])

        result = await limiter.with_retry("perplexity", mock_func, max_retries=2)
        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_configs(self):
        """Test predefined API rate limit configurations."""
        limiter = APIRateLimiter(cache=None)

        # Check that common APIs have configs
        assert "perplexity" in limiter.LIMITS
        assert "openai" in limiter.LIMITS
        assert "alpha_vantage" in limiter.LIMITS

        # Verify Perplexity config
        perplexity_config = limiter.LIMITS["perplexity"]
        assert perplexity_config.max_requests == 50
        assert perplexity_config.window_seconds == 60

        # Verify Alpha Vantage free tier
        av_config = limiter.LIMITS["alpha_vantage"]
        assert av_config.max_requests == 5  # Free tier limit
        assert av_config.window_seconds == 60