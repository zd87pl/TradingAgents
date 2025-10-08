"""
Distributed Rate Limiter
========================

Redis-backed rate limiting to prevent API bans across multiple instances.
"""

import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import hashlib
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    max_requests: int
    window_seconds: int
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_capacity: Optional[int] = None  # For token bucket


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


class DistributedRateLimiter:
    """
    Distributed rate limiter using Redis for coordination across instances.
    """

    def __init__(self, cache: Optional['RedisCache'] = None):
        """
        Initialize rate limiter.

        Args:
            cache: Redis cache instance (optional, falls back to in-memory)
        """
        self.cache = cache
        self.local_limits: Dict[str, Dict] = {}  # Fallback for non-distributed

    async def acquire(self,
                     identifier: str,
                     config: RateLimitConfig) -> bool:
        """
        Acquire permission to make a request.

        Args:
            identifier: Unique identifier (e.g., "perplexity:api_key_hash")
            config: Rate limit configuration

        Returns:
            True if request allowed

        Raises:
            RateLimitExceeded: If rate limit exceeded
        """
        if self.cache and self.cache.connected:
            return await self._acquire_distributed(identifier, config)
        else:
            return self._acquire_local(identifier, config)

    async def _acquire_distributed(self,
                                  identifier: str,
                                  config: RateLimitConfig) -> bool:
        """
        Distributed rate limiting using Redis.
        """
        if config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return await self._sliding_window_redis(identifier, config)
        elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return await self._token_bucket_redis(identifier, config)
        else:
            return await self._fixed_window_redis(identifier, config)

    async def _sliding_window_redis(self,
                                   identifier: str,
                                   config: RateLimitConfig) -> bool:
        """
        Sliding window rate limiting using Redis sorted sets.
        """
        now = time.time()
        window_start = now - config.window_seconds
        key = f"ratelimit:sliding:{identifier}"

        # Remove old entries
        await self.cache.redis.zremrangebyscore(key, 0, window_start)

        # Count current requests in window
        current_count = await self.cache.redis.zcard(key)

        if current_count >= config.max_requests:
            # Get oldest request time to calculate retry_after
            oldest = await self.cache.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1] + config.window_seconds - now) + 1
            else:
                retry_after = config.window_seconds

            raise RateLimitExceeded(
                f"Rate limit exceeded: {current_count}/{config.max_requests} requests",
                retry_after=retry_after
            )

        # Add current request
        await self.cache.redis.zadd(key, {str(now): now})
        await self.cache.redis.expire(key, config.window_seconds)

        logger.debug(f"Rate limit {identifier}: {current_count + 1}/{config.max_requests}")
        return True

    async def _token_bucket_redis(self,
                                 identifier: str,
                                 config: RateLimitConfig) -> bool:
        """
        Token bucket rate limiting for burst capacity.
        """
        now = time.time()
        key = f"ratelimit:bucket:{identifier}"

        # Lua script for atomic token bucket operations
        lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local burst = tonumber(ARGV[4])

        local bucket = redis.call('HGETALL', key)
        local tokens = max_tokens
        local last_refill = now

        if #bucket > 0 then
            for i = 1, #bucket, 2 do
                if bucket[i] == 'tokens' then
                    tokens = tonumber(bucket[i + 1])
                elseif bucket[i] == 'last_refill' then
                    last_refill = tonumber(bucket[i + 1])
                end
            end

            -- Refill tokens
            local elapsed = now - last_refill
            local new_tokens = tokens + (elapsed * refill_rate)
            tokens = math.min(new_tokens, burst or max_tokens)
        end

        if tokens >= 1 then
            -- Consume token
            redis.call('HSET', key, 'tokens', tokens - 1, 'last_refill', now)
            redis.call('EXPIRE', key, max_tokens * 2)  -- Expire after 2x window
            return 1
        else
            -- Calculate retry_after
            local retry_after = math.ceil((1 - tokens) / refill_rate)
            return retry_after
        end
        """

        refill_rate = config.max_requests / config.window_seconds
        burst_capacity = config.burst_capacity or config.max_requests

        result = await self.cache.redis.eval(
            lua_script,
            1,
            key,
            config.max_requests,
            refill_rate,
            now,
            burst_capacity
        )

        if result == 1:
            return True
        else:
            raise RateLimitExceeded(
                f"Token bucket exhausted for {identifier}",
                retry_after=int(result)
            )

    async def _fixed_window_redis(self,
                                 identifier: str,
                                 config: RateLimitConfig) -> bool:
        """
        Fixed window rate limiting (simplest but has edge cases).
        """
        window = int(time.time() / config.window_seconds)
        key = f"ratelimit:fixed:{identifier}:{window}"

        # Increment counter
        count = await self.cache.redis.incr(key)

        # Set expiry on first request
        if count == 1:
            await self.cache.redis.expire(key, config.window_seconds)

        if count > config.max_requests:
            ttl = await self.cache.redis.ttl(key)
            raise RateLimitExceeded(
                f"Fixed window limit exceeded: {count}/{config.max_requests}",
                retry_after=ttl or config.window_seconds
            )

        return True

    def _acquire_local(self, identifier: str, config: RateLimitConfig) -> bool:
        """
        Local in-memory rate limiting (fallback when Redis unavailable).
        """
        now = time.time()

        if identifier not in self.local_limits:
            self.local_limits[identifier] = {
                'requests': [],
                'tokens': config.max_requests
            }

        limit_data = self.local_limits[identifier]

        if config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            # Remove old requests
            window_start = now - config.window_seconds
            limit_data['requests'] = [
                t for t in limit_data['requests']
                if t > window_start
            ]

            if len(limit_data['requests']) >= config.max_requests:
                retry_after = int(limit_data['requests'][0] + config.window_seconds - now) + 1
                raise RateLimitExceeded(
                    f"Local rate limit exceeded for {identifier}",
                    retry_after=retry_after
                )

            limit_data['requests'].append(now)
            return True

        return True  # Simplified for other strategies

    async def reset(self, identifier: str):
        """
        Reset rate limit for an identifier.

        Args:
            identifier: Unique identifier to reset
        """
        if self.cache and self.cache.connected:
            # Clear all rate limit keys for this identifier
            keys = await self.cache.redis.keys(f"ratelimit:*:{identifier}*")
            if keys:
                await self.cache.redis.delete(*keys)
        else:
            # Clear local limits
            if identifier in self.local_limits:
                del self.local_limits[identifier]

    async def get_status(self, identifier: str, config: RateLimitConfig) -> Dict[str, Any]:
        """
        Get current rate limit status.

        Returns:
            Dictionary with current count, limit, and reset time
        """
        if self.cache and self.cache.connected:
            if config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                key = f"ratelimit:sliding:{identifier}"
                now = time.time()
                window_start = now - config.window_seconds

                # Clean and count
                await self.cache.redis.zremrangebyscore(key, 0, window_start)
                current = await self.cache.redis.zcard(key)

                # Get oldest entry for reset time
                oldest = await self.cache.redis.zrange(key, 0, 0, withscores=True)
                reset_time = None
                if oldest:
                    reset_time = int(oldest[0][1] + config.window_seconds)

                return {
                    'current': current,
                    'limit': config.max_requests,
                    'remaining': max(0, config.max_requests - current),
                    'reset_at': reset_time,
                    'strategy': config.strategy.value
                }

        # Fallback for local limits
        if identifier in self.local_limits:
            limit_data = self.local_limits[identifier]
            current = len(limit_data.get('requests', []))
            return {
                'current': current,
                'limit': config.max_requests,
                'remaining': max(0, config.max_requests - current),
                'reset_at': None,
                'strategy': 'local'
            }

        return {
            'current': 0,
            'limit': config.max_requests,
            'remaining': config.max_requests,
            'reset_at': None,
            'strategy': config.strategy.value
        }


class APIRateLimiter:
    """
    Convenience class for API-specific rate limiting.
    """

    # Common API rate limits
    LIMITS = {
        'perplexity': RateLimitConfig(max_requests=50, window_seconds=60),
        'openai': RateLimitConfig(max_requests=60, window_seconds=60, burst_capacity=10),
        'alpha_vantage': RateLimitConfig(max_requests=5, window_seconds=60),  # Free tier
        'alpha_vantage_premium': RateLimitConfig(max_requests=75, window_seconds=60),
        'polygon': RateLimitConfig(max_requests=5, window_seconds=60),
        'finnhub': RateLimitConfig(max_requests=60, window_seconds=60),
        'quiver': RateLimitConfig(max_requests=100, window_seconds=60),
        'discord_webhook': RateLimitConfig(max_requests=5, window_seconds=2),
        'telegram': RateLimitConfig(max_requests=30, window_seconds=1),
    }

    def __init__(self, cache: Optional['RedisCache'] = None):
        """Initialize API rate limiter"""
        self.limiter = DistributedRateLimiter(cache)

    async def acquire_api(self, api_name: str, api_key_hash: Optional[str] = None) -> bool:
        """
        Acquire permission for an API call.

        Args:
            api_name: Name of the API (e.g., 'perplexity')
            api_key_hash: Optional hash of API key for per-key limiting

        Returns:
            True if request allowed

        Raises:
            RateLimitExceeded: If rate limit exceeded
        """
        if api_name not in self.LIMITS:
            logger.warning(f"No rate limit configured for API: {api_name}")
            return True

        # Create identifier
        if api_key_hash:
            identifier = f"{api_name}:{api_key_hash[:8]}"
        else:
            identifier = api_name

        config = self.LIMITS[api_name]
        return await self.limiter.acquire(identifier, config)

    async def with_retry(self,
                        api_name: str,
                        func,
                        *args,
                        max_retries: int = 3,
                        **kwargs):
        """
        Execute function with automatic rate limit retry.

        Args:
            api_name: Name of the API
            func: Async function to execute
            max_retries: Maximum retry attempts
            *args, **kwargs: Arguments for func

        Returns:
            Result of func
        """
        for attempt in range(max_retries):
            try:
                # Acquire rate limit
                await self.acquire_api(api_name)

                # Execute function
                return await func(*args, **kwargs)

            except RateLimitExceeded as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limit hit for {api_name}, waiting {e.retry_after}s")
                    await asyncio.sleep(e.retry_after)
                else:
                    raise
            except Exception as e:
                logger.error(f"API call failed: {e}")
                raise

        raise RuntimeError(f"Failed after {max_retries} retries")