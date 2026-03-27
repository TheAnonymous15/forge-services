# -*- coding: utf-8 -*-
"""
ForgeForth Africa - Cache Service
==================================
Unified caching layer with SSL support for Redis connections.
"""
import logging
import json
from typing import Any, Optional, List
from datetime import timedelta
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('forgeforth.services.cache')


class CacheService:
    """
    Unified caching service with support for:
    - Simple key-value caching
    - Cache invalidation patterns
    - Cache warming
    - Distributed locking
    """

    # Default TTLs (in seconds)
    TTL_SHORT = 60          # 1 minute
    TTL_MEDIUM = 300        # 5 minutes
    TTL_LONG = 3600         # 1 hour
    TTL_DAY = 86400         # 24 hours

    # Cache key prefixes
    PREFIX_USER = 'user'
    PREFIX_PROFILE = 'profile'
    PREFIX_ORG = 'org'
    PREFIX_OPPORTUNITY = 'opp'
    PREFIX_SESSION = 'session'
    PREFIX_RATE_LIMIT = 'rate'
    PREFIX_LOCK = 'lock'

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            return cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache."""
        try:
            ttl = ttl or cls.TTL_MEDIUM
            cache.set(key, value, ttl)
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    @classmethod
    def delete(cls, key: str) -> bool:
        """Delete value from cache."""
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    @classmethod
    def delete_many(cls, keys: List[str]) -> bool:
        """Delete multiple values from cache."""
        try:
            cache.delete_many(keys)
            return True
        except Exception as e:
            logger.error(f"Cache delete_many error: {e}")
            return False

    @classmethod
    def delete_pattern(cls, pattern: str) -> int:
        """
        Delete all keys matching a pattern.
        Note: This is Redis-specific and may not work with all backends.
        """
        try:
            # Try to use Redis pattern deletion
            client = cache.client.get_client()
            if hasattr(client, 'keys'):
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
                    return len(keys)
            return 0
        except Exception as e:
            logger.warning(f"Pattern delete not supported: {e}")
            return 0

    @classmethod
    def get_or_set(cls, key: str, default_func, ttl: int = None):
        """
        Get value from cache, or compute and cache it.

        Args:
            key: Cache key
            default_func: Function to compute value if not cached
            ttl: Time to live in seconds
        """
        value = cls.get(key)
        if value is not None:
            return value

        value = default_func()
        cls.set(key, value, ttl)
        return value

    # =========================================================================
    # USER CACHING
    # =========================================================================

    @classmethod
    def get_user(cls, user_id: str) -> Optional[dict]:
        """Get cached user data."""
        return cls.get(f'{cls.PREFIX_USER}:{user_id}')

    @classmethod
    def set_user(cls, user_id: str, data: dict, ttl: int = None) -> bool:
        """Cache user data."""
        return cls.set(f'{cls.PREFIX_USER}:{user_id}', data, ttl or cls.TTL_MEDIUM)

    @classmethod
    def invalidate_user(cls, user_id: str) -> bool:
        """Invalidate user cache."""
        return cls.delete(f'{cls.PREFIX_USER}:{user_id}')

    # =========================================================================
    # PROFILE CACHING
    # =========================================================================

    @classmethod
    def get_profile(cls, user_id: str) -> Optional[dict]:
        """Get cached profile data."""
        return cls.get(f'{cls.PREFIX_PROFILE}:{user_id}')

    @classmethod
    def set_profile(cls, user_id: str, data: dict, ttl: int = None) -> bool:
        """Cache profile data."""
        return cls.set(f'{cls.PREFIX_PROFILE}:{user_id}', data, ttl or cls.TTL_MEDIUM)

    @classmethod
    def invalidate_profile(cls, user_id: str) -> bool:
        """Invalidate profile cache."""
        return cls.delete(f'{cls.PREFIX_PROFILE}:{user_id}')

    # =========================================================================
    # RATE LIMITING
    # =========================================================================

    @classmethod
    def check_rate_limit(cls, key: str, limit: int, window: int = 60) -> bool:
        """
        Check if rate limit is exceeded.

        Args:
            key: Unique identifier (e.g., user_id, IP)
            limit: Maximum requests allowed
            window: Time window in seconds

        Returns:
            True if within limit, False if exceeded
        """
        cache_key = f'{cls.PREFIX_RATE_LIMIT}:{key}'

        try:
            current = cache.get(cache_key, 0)
            if current >= limit:
                return False

            # Increment counter
            cache.set(cache_key, current + 1, window)
            return True
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True  # Fail open

    @classmethod
    def get_rate_limit_remaining(cls, key: str, limit: int) -> int:
        """Get remaining requests in rate limit window."""
        cache_key = f'{cls.PREFIX_RATE_LIMIT}:{key}'
        current = cache.get(cache_key, 0)
        return max(0, limit - current)

    # =========================================================================
    # DISTRIBUTED LOCKING
    # =========================================================================

    @classmethod
    def acquire_lock(cls, key: str, ttl: int = 30) -> bool:
        """
        Acquire a distributed lock.

        Args:
            key: Lock identifier
            ttl: Lock timeout in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        lock_key = f'{cls.PREFIX_LOCK}:{key}'

        try:
            # Try to set the lock (only if it doesn't exist)
            return cache.add(lock_key, '1', ttl)
        except Exception as e:
            logger.error(f"Lock acquire error: {e}")
            return False

    @classmethod
    def release_lock(cls, key: str) -> bool:
        """Release a distributed lock."""
        lock_key = f'{cls.PREFIX_LOCK}:{key}'
        return cls.delete(lock_key)

    @classmethod
    def with_lock(cls, key: str, func, ttl: int = 30, timeout: int = 10):
        """
        Execute function with distributed lock.

        Args:
            key: Lock identifier
            func: Function to execute
            ttl: Lock timeout
            timeout: Max time to wait for lock
        """
        import time
        start = time.time()

        while time.time() - start < timeout:
            if cls.acquire_lock(key, ttl):
                try:
                    return func()
                finally:
                    cls.release_lock(key)
            time.sleep(0.1)

        raise TimeoutError(f"Could not acquire lock: {key}")

    # =========================================================================
    # HEALTH CHECK
    # =========================================================================

    @classmethod
    def health_check(cls) -> dict:
        """Check cache health."""
        try:
            # Try a simple set/get
            test_key = '_health_check'
            cache.set(test_key, '1', 5)
            result = cache.get(test_key)
            cache.delete(test_key)

            return {
                'status': 'healthy' if result == '1' else 'degraded',
                'backend': cache.__class__.__name__,
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
            }

