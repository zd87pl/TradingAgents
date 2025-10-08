"""
Signal Deduplicator
===================

Prevents duplicate market signals from being processed multiple times.
"""

import hashlib
import logging
from typing import Optional, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)


@dataclass
class SignalFingerprint:
    """Unique identifier for a signal"""
    ticker: str
    signal_type: str  # 'congressional', 'insider', 'earnings', etc.
    action: str  # 'BUY', 'SELL', 'HOLD'
    source_id: str  # Unique identifier from source (e.g., trade ID)
    date: str  # Date of the signal origin (not processing time)

    def hash(self) -> str:
        """Generate unique hash for this signal"""
        data = f"{self.ticker}:{self.signal_type}:{self.action}:{self.source_id}:{self.date}"
        return hashlib.sha256(data.encode()).hexdigest()


class SignalDeduplicator:
    """
    Deduplicates market signals to prevent reprocessing.
    """

    def __init__(self, cache: Optional['RedisCache'] = None, ttl_days: int = 7):
        """
        Initialize signal deduplicator.

        Args:
            cache: Redis cache for distributed deduplication
            ttl_days: How long to remember processed signals
        """
        self.cache = cache
        self.ttl_seconds = ttl_days * 24 * 3600
        self.local_cache: Set[str] = set()  # Fallback for non-distributed

    async def is_duplicate(self, signal: 'MarketSignal') -> bool:
        """
        Check if a signal has already been processed.

        Args:
            signal: Market signal to check

        Returns:
            True if duplicate (already processed), False if new
        """
        fingerprint = self._create_fingerprint(signal)
        signal_hash = fingerprint.hash()

        if self.cache and self.cache.connected:
            return await self._check_distributed(signal_hash)
        else:
            return self._check_local(signal_hash)

    def _create_fingerprint(self, signal: 'MarketSignal') -> SignalFingerprint:
        """
        Create fingerprint from market signal.
        """
        # Extract unique identifiers from signal data
        source_id = self._extract_source_id(signal)

        return SignalFingerprint(
            ticker=signal.ticker,
            signal_type=signal.signal_type,
            action=signal.action,
            source_id=source_id,
            date=signal.timestamp.date().isoformat()
        )

    def _extract_source_id(self, signal: 'MarketSignal') -> str:
        """
        Extract unique source identifier from signal data.
        """
        if signal.signal_type == 'congressional':
            # Use politician and date as unique ID
            if 'trades' in signal.data and signal.data['trades']:
                first_trade = signal.data['trades'][0]
                return f"{first_trade.get('politician', '')}_{first_trade.get('date', '')}"

        elif signal.signal_type == 'insider':
            # Use insider name and transaction details
            return f"{signal.data.get('insider_name', '')}_{signal.data.get('net_buying', 0)}"

        elif signal.signal_type == 'earnings':
            # Use earnings date as ID
            return signal.data.get('earnings_date', '')

        elif signal.signal_type == 'technical':
            # Use indicator values as ID
            return f"{signal.data.get('rsi', 0)}_{signal.data.get('ma_signal', '')}"

        # Default: use hash of entire data
        return hashlib.md5(json.dumps(signal.data, sort_keys=True).encode()).hexdigest()

    async def _check_distributed(self, signal_hash: str) -> bool:
        """
        Check for duplicate using Redis.
        """
        key = f"signal:processed:{signal_hash}"

        try:
            # Check if exists
            exists = await self.cache.redis.exists(key)

            if not exists:
                # Mark as processed with TTL
                await self.cache.redis.setex(key, self.ttl_seconds, "1")
                logger.debug(f"New signal recorded: {signal_hash[:8]}")
                return False  # Not a duplicate

            logger.debug(f"Duplicate signal detected: {signal_hash[:8]}")
            return True  # Is a duplicate

        except Exception as e:
            logger.error(f"Redis check failed, using local cache: {e}")
            return self._check_local(signal_hash)

    def _check_local(self, signal_hash: str) -> bool:
        """
        Check for duplicate using local memory.
        """
        if signal_hash in self.local_cache:
            logger.debug(f"Local duplicate detected: {signal_hash[:8]}")
            return True

        self.local_cache.add(signal_hash)

        # Limit local cache size
        if len(self.local_cache) > 10000:
            # Remove oldest entries (simple FIFO)
            self.local_cache = set(list(self.local_cache)[-5000:])

        return False

    async def mark_processed(self, signal: 'MarketSignal'):
        """
        Mark a signal as processed (alternative API).

        Args:
            signal: Signal to mark as processed
        """
        fingerprint = self._create_fingerprint(signal)
        signal_hash = fingerprint.hash()

        if self.cache and self.cache.connected:
            key = f"signal:processed:{signal_hash}"
            await self.cache.redis.setex(key, self.ttl_seconds, "1")
        else:
            self.local_cache.add(signal_hash)

    async def filter_duplicates(self, signals: List['MarketSignal']) -> List['MarketSignal']:
        """
        Filter out duplicate signals from a list.

        Args:
            signals: List of market signals

        Returns:
            List of unique (non-duplicate) signals
        """
        unique_signals = []

        for signal in signals:
            if not await self.is_duplicate(signal):
                unique_signals.append(signal)

        logger.info(f"Filtered {len(signals) - len(unique_signals)} duplicate signals "
                   f"({len(unique_signals)} unique)")

        return unique_signals

    async def get_stats(self) -> dict:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with stats
        """
        stats = {
            'backend': 'redis' if (self.cache and self.cache.connected) else 'local',
            'ttl_days': self.ttl_seconds // (24 * 3600)
        }

        if self.cache and self.cache.connected:
            try:
                # Count processed signals in Redis
                keys = await self.cache.redis.keys("signal:processed:*")
                stats['processed_count'] = len(keys)
            except Exception as e:
                logger.error(f"Failed to get Redis stats: {e}")
                stats['processed_count'] = 0
        else:
            stats['processed_count'] = len(self.local_cache)

        return stats

    async def clear(self):
        """
        Clear all deduplication history.
        """
        if self.cache and self.cache.connected:
            try:
                keys = await self.cache.redis.keys("signal:processed:*")
                if keys:
                    await self.cache.redis.delete(*keys)
                logger.info(f"Cleared {len(keys)} processed signal records")
            except Exception as e:
                logger.error(f"Failed to clear Redis: {e}")

        self.local_cache.clear()


class SmartSignalAggregator:
    """
    Aggregates signals with deduplication and priority handling.
    """

    def __init__(self, deduplicator: SignalDeduplicator):
        """
        Initialize smart aggregator.

        Args:
            deduplicator: Signal deduplicator instance
        """
        self.deduplicator = deduplicator

    async def aggregate_signals(self,
                               new_signals: List['MarketSignal'],
                               existing_signals: List['MarketSignal'] = None) -> List['MarketSignal']:
        """
        Aggregate signals with deduplication.

        Args:
            new_signals: Newly generated signals
            existing_signals: Existing signals to merge with

        Returns:
            Aggregated unique signals sorted by confidence
        """
        all_signals = new_signals.copy()

        if existing_signals:
            all_signals.extend(existing_signals)

        # Filter duplicates
        unique_signals = await self.deduplicator.filter_duplicates(all_signals)

        # Group by ticker
        ticker_signals = {}
        for signal in unique_signals:
            if signal.ticker not in ticker_signals:
                ticker_signals[signal.ticker] = []
            ticker_signals[signal.ticker].append(signal)

        # For each ticker, keep highest confidence signals per action
        aggregated = []
        for ticker, signals in ticker_signals.items():
            # Group by action
            action_signals = {}
            for signal in signals:
                if signal.action not in action_signals:
                    action_signals[signal.action] = []
                action_signals[signal.action].append(signal)

            # Keep best signal per action
            for action, action_group in action_signals.items():
                # Sort by confidence and keep top signal
                best_signal = max(action_group, key=lambda s: s.confidence)
                aggregated.append(best_signal)

        # Sort final list by confidence
        aggregated.sort(key=lambda s: s.confidence, reverse=True)

        logger.info(f"Aggregated {len(all_signals)} signals to {len(aggregated)} unique high-confidence signals")

        return aggregated