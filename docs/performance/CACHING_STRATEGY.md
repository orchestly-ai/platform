# Redis Caching Strategy

## Overview

Redis is used for caching frequently accessed data to reduce database load and improve response times.

## Cache Layers

### Layer 1: API Response Cache
Cache complete API responses for idempotent GET requests.

```python
from functools import wraps
import hashlib
import json

def cache_response(ttl_seconds: int = 300):
    """Cache API response decorator."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from request
            cache_key = f"api:{func.__name__}:{_hash_args(args, kwargs)}"

            # Check cache
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Execute and cache
            result = await func(*args, **kwargs)
            await redis.setex(cache_key, ttl_seconds, json.dumps(result))
            return result
        return wrapper
    return decorator
```

### Layer 2: Entity Cache
Cache individual entities by ID.

```python
class EntityCache:
    """Generic entity caching."""

    def __init__(self, redis_client, prefix: str, ttl: int = 600):
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = ttl

    async def get(self, entity_id: str):
        """Get entity from cache."""
        data = await self.redis.get(f"{self.prefix}:{entity_id}")
        return json.loads(data) if data else None

    async def set(self, entity_id: str, data: dict):
        """Set entity in cache."""
        await self.redis.setex(
            f"{self.prefix}:{entity_id}",
            self.ttl,
            json.dumps(data)
        )

    async def delete(self, entity_id: str):
        """Invalidate entity cache."""
        await self.redis.delete(f"{self.prefix}:{entity_id}")

    async def get_or_fetch(self, entity_id: str, fetch_func):
        """Get from cache or fetch from database."""
        cached = await self.get(entity_id)
        if cached:
            return cached

        data = await fetch_func(entity_id)
        if data:
            await self.set(entity_id, data)
        return data
```

### Layer 3: Query Result Cache
Cache query results for common filters.

```python
class QueryCache:
    """Cache for query results."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def get_list(
        self,
        cache_key: str,
        query_func,
        ttl: int = 300
    ):
        """Cache list query results."""
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        results = await query_func()
        await self.redis.setex(cache_key, ttl, json.dumps(results))
        return results

    async def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern."""
        async for key in self.redis.scan_iter(pattern):
            await self.redis.delete(key)
```

## Cached Data Types

### 1. Agent Registry (High Hit Rate)
```python
# Cache key: agent:registry:{org_id}:{agent_id}
# TTL: 5 minutes
# Invalidate on: agent update, agent delete

agent_cache = EntityCache(redis, "agent:registry", ttl=300)
```

### 2. RBAC Permissions (Very High Hit Rate)
```python
# Cache key: rbac:perms:{user_id}
# TTL: 5 minutes
# Invalidate on: role change, permission change

class PermissionCache:
    async def get_permissions(self, user_id: str) -> set:
        cached = await redis.smembers(f"rbac:perms:{user_id}")
        return cached or set()

    async def set_permissions(self, user_id: str, perms: set):
        key = f"rbac:perms:{user_id}"
        await redis.delete(key)
        if perms:
            await redis.sadd(key, *perms)
            await redis.expire(key, 300)
```

### 3. Workflow Templates (Medium Hit Rate)
```python
# Cache key: workflow:template:{template_id}
# TTL: 30 minutes
# Invalidate on: template update

template_cache = EntityCache(redis, "workflow:template", ttl=1800)
```

### 4. Cost Tracking (Real-time)
```python
# Cache key: cost:{org_id}:{date}
# TTL: No expiry (managed manually)
# Update on: every LLM call

class CostTracker:
    async def increment_cost(self, org_id: str, amount: float):
        date = datetime.utcnow().strftime("%Y-%m-%d")
        await redis.incrbyfloat(f"cost:{org_id}:{date}", amount)

    async def get_daily_cost(self, org_id: str) -> float:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        cost = await redis.get(f"cost:{org_id}:{date}")
        return float(cost) if cost else 0.0
```

### 5. Rate Limiting (Real-time)
```python
# Cache key: ratelimit:{org_id}:{window}
# TTL: Sliding window
# Update on: every request

class RateLimiter:
    async def check_limit(
        self,
        org_id: str,
        limit: int,
        window_seconds: int
    ) -> bool:
        key = f"ratelimit:{org_id}"
        current = await redis.incr(key)

        if current == 1:
            await redis.expire(key, window_seconds)

        return current <= limit
```

## Cache Invalidation Patterns

### 1. Event-Driven Invalidation
```python
async def on_agent_updated(agent_id: str, org_id: str):
    """Invalidate agent cache on update."""
    await agent_cache.delete(agent_id)
    await redis.delete(f"agent:list:{org_id}")
```

### 2. TTL-Based Expiration
```python
# Short TTL for frequently changing data
await redis.setex("dynamic_data", 60, value)  # 1 minute

# Longer TTL for stable data
await redis.setex("reference_data", 3600, value)  # 1 hour
```

### 3. Write-Through Cache
```python
async def update_agent(agent_id: str, data: dict, db):
    """Update database and cache atomically."""
    # Update database
    await db.execute(update(Agent).where(...).values(**data))
    await db.commit()

    # Update cache
    await agent_cache.set(agent_id, data)
```

## Redis Configuration

### Production Settings
```python
# backend/shared/cache.py
import redis.asyncio as redis

redis_client = redis.Redis(
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
```

### Redis Cluster (High Availability)
```python
from redis.asyncio.cluster import RedisCluster

redis_cluster = RedisCluster(
    host=settings.REDIS_CLUSTER_HOST,
    port=settings.REDIS_CLUSTER_PORT,
    password=settings.REDIS_PASSWORD,
    decode_responses=True,
)
```

## Monitoring

### Key Metrics
- `cache_hit_ratio` - Hits / (Hits + Misses)
- `cache_memory_bytes` - Memory used by cache
- `cache_evictions` - Keys evicted due to memory pressure

### Redis INFO Command
```python
async def get_cache_stats():
    info = await redis.info("stats")
    return {
        "hits": info["keyspace_hits"],
        "misses": info["keyspace_misses"],
        "hit_ratio": info["keyspace_hits"] / (info["keyspace_hits"] + info["keyspace_misses"]),
    }
```

## Best Practices

1. **Use appropriate TTLs** - Balance freshness vs. hit rate
2. **Monitor hit ratios** - Target 80%+ for frequently accessed data
3. **Implement cache stampede protection** - Use locks for expensive queries
4. **Use pipeline for batch operations** - Reduce round trips
5. **Set memory limits** - Prevent Redis from using all memory
