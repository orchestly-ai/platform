"""
Cache Service for Agent Orchestration Platform

Provides Redis-based caching with:
- Entity caching
- Query result caching
- Rate limiting
- Cost tracking
"""

import json
import hashlib
from typing import Any, Optional, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from functools import wraps

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    redis = None

from backend.shared.config import settings


# Type variable for generic cache
T = TypeVar("T")


class CacheService:
    """Main cache service with Redis backend."""

    def __init__(self):
        """Initialize cache service."""
        self._client: Optional[redis.Redis] = None
        self._enabled = HAS_REDIS and settings.REDIS_HOST

    async def connect(self):
        """Connect to Redis."""
        if not self._enabled:
            return

        self._client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            max_connections=50,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._client is not None

    # =========================================================================
    # Basic Operations
    # =========================================================================

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception:
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """Set value in cache."""
        if not self._client:
            return False
        try:
            if ttl_seconds:
                await self._client.setex(key, ttl_seconds, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._client:
            return False
        try:
            return await self._client.exists(key) > 0
        except Exception:
            return False

    # =========================================================================
    # JSON Operations
    # =========================================================================

    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from cache."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """Set JSON value in cache."""
        try:
            json_str = json.dumps(value, default=str)
            return await self.set(key, json_str, ttl_seconds)
        except (TypeError, ValueError):
            return False

    # =========================================================================
    # Entity Caching
    # =========================================================================

    async def get_entity(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[dict]:
        """Get entity from cache."""
        key = f"{entity_type}:{entity_id}"
        return await self.get_json(key)

    async def set_entity(
        self,
        entity_type: str,
        entity_id: str,
        data: dict,
        ttl_seconds: int = 300
    ) -> bool:
        """Set entity in cache."""
        key = f"{entity_type}:{entity_id}"
        return await self.set_json(key, data, ttl_seconds)

    async def delete_entity(
        self,
        entity_type: str,
        entity_id: str
    ) -> bool:
        """Delete entity from cache."""
        key = f"{entity_type}:{entity_id}"
        return await self.delete(key)

    async def get_or_fetch_entity(
        self,
        entity_type: str,
        entity_id: str,
        fetch_func: Callable,
        ttl_seconds: int = 300
    ) -> Optional[dict]:
        """Get entity from cache or fetch from database."""
        cached = await self.get_entity(entity_type, entity_id)
        if cached:
            return cached

        data = await fetch_func()
        if data:
            await self.set_entity(entity_type, entity_id, data, ttl_seconds)
        return data

    # =========================================================================
    # Permission Caching
    # =========================================================================

    async def get_permissions(self, user_id: str) -> Optional[set]:
        """Get user permissions from cache."""
        if not self._client:
            return None
        try:
            perms = await self._client.smembers(f"perms:{user_id}")
            return perms if perms else None
        except Exception:
            return None

    async def set_permissions(
        self,
        user_id: str,
        permissions: set,
        ttl_seconds: int = 300
    ) -> bool:
        """Set user permissions in cache."""
        if not self._client:
            return False
        try:
            key = f"perms:{user_id}"
            await self._client.delete(key)
            if permissions:
                await self._client.sadd(key, *permissions)
                await self._client.expire(key, ttl_seconds)
            return True
        except Exception:
            return False

    async def invalidate_permissions(self, user_id: str) -> bool:
        """Invalidate user permission cache."""
        return await self.delete(f"perms:{user_id}")

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check rate limit.

        Returns:
            tuple: (allowed, current_count)
        """
        if not self._client:
            return True, 0

        try:
            full_key = f"ratelimit:{key}"
            current = await self._client.incr(full_key)

            if current == 1:
                await self._client.expire(full_key, window_seconds)

            return current <= limit, current
        except Exception:
            return True, 0

    async def get_rate_limit_remaining(
        self,
        key: str,
        limit: int
    ) -> int:
        """Get remaining rate limit."""
        if not self._client:
            return limit

        try:
            current = await self._client.get(f"ratelimit:{key}")
            return max(0, limit - int(current or 0))
        except Exception:
            return limit

    # =========================================================================
    # Cost Tracking
    # =========================================================================

    async def increment_cost(
        self,
        org_id: str,
        amount: float,
        date: Optional[str] = None
    ) -> float:
        """Increment daily cost for organization."""
        if not self._client:
            return 0.0

        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            key = f"cost:{org_id}:{date}"
            new_value = await self._client.incrbyfloat(key, amount)
            # Set TTL of 48 hours for cost tracking
            await self._client.expire(key, 48 * 60 * 60)
            return new_value
        except Exception:
            return 0.0

    async def get_daily_cost(
        self,
        org_id: str,
        date: Optional[str] = None
    ) -> float:
        """Get daily cost for organization."""
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        value = await self.get(f"cost:{org_id}:{date}")
        return float(value) if value else 0.0

    async def get_monthly_cost(self, org_id: str) -> float:
        """Get monthly cost for organization."""
        if not self._client:
            return 0.0

        try:
            # Get all daily costs for current month
            now = datetime.utcnow()
            total = 0.0

            for day in range(1, now.day + 1):
                date = f"{now.year}-{now.month:02d}-{day:02d}"
                cost = await self.get_daily_cost(org_id, date)
                total += cost

            return total
        except Exception:
            return 0.0

    # =========================================================================
    # Pattern Operations
    # =========================================================================

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        if not self._client:
            return 0

        try:
            count = 0
            async for key in self._client.scan_iter(pattern):
                await self._client.delete(key)
                count += 1
            return count
        except Exception:
            return 0

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict:
        """Check cache health."""
        if not self._client:
            return {"status": "disabled", "error": "Redis not configured"}

        try:
            await self._client.ping()
            info = await self._client.info("stats")
            return {
                "status": "healthy",
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Global cache instance
cache_service = CacheService()


def get_cache() -> CacheService:
    """Get cache service instance."""
    return cache_service


# =========================================================================
# Cache Decorator
# =========================================================================

def cached(
    key_prefix: str,
    ttl_seconds: int = 300,
    key_builder: Optional[Callable] = None
):
    """
    Decorator for caching function results.

    Args:
        key_prefix: Prefix for cache key
        ttl_seconds: Time to live in seconds
        key_builder: Optional function to build cache key from args
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            if not cache.is_connected:
                return await func(*args, **kwargs)

            # Build cache key
            if key_builder:
                key = f"{key_prefix}:{key_builder(*args, **kwargs)}"
            else:
                # Default: hash all arguments
                arg_hash = hashlib.md5(
                    json.dumps([str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]).encode()
                ).hexdigest()[:16]
                key = f"{key_prefix}:{arg_hash}"

            # Check cache
            cached = await cache.get_json(key)
            if cached is not None:
                return cached

            # Execute and cache
            result = await func(*args, **kwargs)
            await cache.set_json(key, result, ttl_seconds)
            return result

        return wrapper
    return decorator
