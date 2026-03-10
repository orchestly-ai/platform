"""
Rate Limiter for Sandbox API

Implements token bucket rate limiting for demo API keys.
Different limits for different API key tiers.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 500
    requests_per_day: int = 2000
    max_tokens_per_request: int = 4000
    max_cost_per_day: float = 1.00  # Demo budget


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: int
    tokens: float = field(default=0)
    last_refill: float = field(default_factory=time.time)
    refill_rate: float = 1.0  # tokens per second

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        now = time.time()
        elapsed = now - self.last_refill

        # Refill tokens
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_refill = now

        # Try to consume
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_wait_time(self, tokens: int = 1) -> float:
        """Get seconds to wait before tokens are available."""
        if self.tokens >= tokens:
            return 0
        return (tokens - self.tokens) / self.refill_rate


@dataclass
class UsageStats:
    """Track usage statistics."""
    requests_today: int = 0
    tokens_today: int = 0
    cost_today: float = 0.0
    last_request: Optional[datetime] = None
    reset_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(days=1))


class RateLimiter:
    """
    Rate limiter for sandbox API.

    Implements multiple rate limiting strategies:
    - Per-minute token bucket
    - Per-hour limits
    - Per-day limits
    - Per-request token limits
    - Daily cost budget
    """

    # Tier configurations
    TIERS = {
        "demo": RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=300,
            requests_per_day=1000,
            max_tokens_per_request=4000,
            max_cost_per_day=0.50,
        ),
        "trial": RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=600,
            requests_per_day=3000,
            max_tokens_per_request=8000,
            max_cost_per_day=2.00,
        ),
        "playground": RateLimitConfig(
            requests_per_minute=20,
            requests_per_hour=100,
            requests_per_day=500,
            max_tokens_per_request=2000,
            max_cost_per_day=0.25,
        ),
    }

    def __init__(self):
        """Initialize rate limiter."""
        # Token buckets per API key
        self._buckets: Dict[str, TokenBucket] = {}
        # Usage stats per API key
        self._usage: Dict[str, UsageStats] = defaultdict(UsageStats)
        # Request counts per hour
        self._hourly_counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

    def get_or_create_bucket(self, api_key: str, tier: str = "demo") -> TokenBucket:
        """Get or create a token bucket for an API key."""
        if api_key not in self._buckets:
            config = self.TIERS.get(tier, self.TIERS["demo"])
            # Set refill rate to requests_per_minute / 60 for per-second rate
            self._buckets[api_key] = TokenBucket(
                capacity=config.requests_per_minute,
                refill_rate=config.requests_per_minute / 60.0,
            )
        return self._buckets[api_key]

    def check_rate_limit(
        self,
        api_key: str,
        tier: str = "demo",
        tokens: int = 1,
        estimated_cost: float = 0.0,
    ) -> tuple:
        """
        Check if request is within rate limits.

        Args:
            api_key: The API key making the request
            tier: Rate limit tier
            tokens: Number of tokens this request will use
            estimated_cost: Estimated cost of this request

        Returns:
            Tuple of (allowed: bool, error_message: Optional[str], retry_after: Optional[int])
        """
        config = self.TIERS.get(tier, self.TIERS["demo"])
        bucket = self.get_or_create_bucket(api_key, tier)
        stats = self._usage[api_key]

        # Reset daily stats if needed
        now = datetime.utcnow()
        if now >= stats.reset_at:
            stats.requests_today = 0
            stats.tokens_today = 0
            stats.cost_today = 0.0
            stats.reset_at = now + timedelta(days=1)

        # Check per-minute rate (token bucket)
        if not bucket.consume():
            wait_time = bucket.get_wait_time()
            return (
                False,
                f"Rate limit exceeded. Too many requests per minute.",
                int(wait_time) + 1,
            )

        # Check hourly limit
        current_hour = now.hour
        hourly_count = self._hourly_counts[api_key][current_hour]
        if hourly_count >= config.requests_per_hour:
            minutes_until_next_hour = 60 - now.minute
            return (
                False,
                f"Hourly rate limit exceeded ({config.requests_per_hour}/hour).",
                minutes_until_next_hour * 60,
            )

        # Check daily limit
        if stats.requests_today >= config.requests_per_day:
            seconds_until_reset = (stats.reset_at - now).total_seconds()
            return (
                False,
                f"Daily rate limit exceeded ({config.requests_per_day}/day).",
                int(seconds_until_reset),
            )

        # Check token limit
        if tokens > config.max_tokens_per_request:
            return (
                False,
                f"Request exceeds max tokens ({config.max_tokens_per_request}).",
                None,
            )

        # Check cost budget
        if stats.cost_today + estimated_cost > config.max_cost_per_day:
            return (
                False,
                f"Daily cost budget exceeded (${config.max_cost_per_day:.2f}/day).",
                int((stats.reset_at - now).total_seconds()),
            )

        return (True, None, None)

    def record_usage(
        self,
        api_key: str,
        tokens: int = 0,
        cost: float = 0.0,
    ):
        """Record API usage for an API key."""
        stats = self._usage[api_key]
        stats.requests_today += 1
        stats.tokens_today += tokens
        stats.cost_today += cost
        stats.last_request = datetime.utcnow()

        # Update hourly count
        current_hour = datetime.utcnow().hour
        self._hourly_counts[api_key][current_hour] += 1

    def get_usage(self, api_key: str) -> Dict:
        """Get usage statistics for an API key."""
        stats = self._usage[api_key]
        return {
            "requests_today": stats.requests_today,
            "tokens_today": stats.tokens_today,
            "cost_today": round(stats.cost_today, 4),
            "last_request": stats.last_request.isoformat() if stats.last_request else None,
            "resets_at": stats.reset_at.isoformat(),
        }

    def get_limits(self, tier: str = "demo") -> Dict:
        """Get rate limit configuration for a tier."""
        config = self.TIERS.get(tier, self.TIERS["demo"])
        return {
            "tier": tier,
            "requests_per_minute": config.requests_per_minute,
            "requests_per_hour": config.requests_per_hour,
            "requests_per_day": config.requests_per_day,
            "max_tokens_per_request": config.max_tokens_per_request,
            "max_cost_per_day": config.max_cost_per_day,
        }


# Singleton
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
