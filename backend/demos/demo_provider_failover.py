#!/usr/bin/env python3
"""
Demo: LLM Provider Failover

Demonstrates automatic failover between LLM providers when one fails.

Features demonstrated:
1. Primary provider failure detection
2. Automatic failover to backup provider
3. Circuit breaker pattern
4. Cost tracking across providers
5. Latency monitoring

Usage:
    python demo_provider_failover.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
import random
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class ProviderStatus(Enum):
    """Provider health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, block requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class LLMProvider:
    """LLM Provider configuration"""
    name: str
    priority: int  # Lower = higher priority
    cost_per_1k_tokens: float
    avg_latency_ms: int
    status: ProviderStatus = ProviderStatus.HEALTHY
    failure_count: int = 0
    success_count: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_open_until: Optional[datetime] = None


@dataclass
class ProviderPool:
    """Pool of LLM providers with failover support"""
    providers: List[LLMProvider] = field(default_factory=list)
    failure_threshold: int = 3
    circuit_reset_seconds: int = 30

    def add_provider(self, provider: LLMProvider):
        """Add provider to pool"""
        self.providers.append(provider)
        self.providers.sort(key=lambda p: p.priority)

    def get_available_providers(self) -> List[LLMProvider]:
        """Get providers sorted by priority, excluding failed ones"""
        now = datetime.utcnow()
        available = []

        for p in self.providers:
            # Check if circuit breaker allows requests
            if p.circuit_state == CircuitState.OPEN:
                if p.circuit_open_until and now >= p.circuit_open_until:
                    # Try half-open
                    p.circuit_state = CircuitState.HALF_OPEN
                    available.append(p)
            else:
                available.append(p)

        return available

    def record_success(self, provider: LLMProvider):
        """Record successful request"""
        provider.success_count += 1
        provider.failure_count = 0

        if provider.circuit_state == CircuitState.HALF_OPEN:
            provider.circuit_state = CircuitState.CLOSED
            print(f"  ✅ Circuit CLOSED for {provider.name} (recovered)")

    def record_failure(self, provider: LLMProvider):
        """Record failed request and update circuit breaker"""
        provider.failure_count += 1

        if provider.failure_count >= self.failure_threshold:
            provider.circuit_state = CircuitState.OPEN
            provider.circuit_open_until = datetime.utcnow()
            # Add reset time
            from datetime import timedelta
            provider.circuit_open_until += timedelta(seconds=self.circuit_reset_seconds)
            print(f"  🔴 Circuit OPEN for {provider.name} (failures: {provider.failure_count})")


class SmartRouter:
    """Intelligent LLM request router with failover"""

    def __init__(self, pool: ProviderPool):
        self.pool = pool
        self.total_requests = 0
        self.failed_requests = 0
        self.total_cost = 0.0
        self.provider_usage: Dict[str, int] = {}

    async def route_request(self, prompt: str, simulate_failures: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Route request with automatic failover.

        Args:
            prompt: The prompt to send
            simulate_failures: Dict of provider_name -> failure_probability
        """
        self.total_requests += 1
        simulate_failures = simulate_failures or {}

        available = self.pool.get_available_providers()

        if not available:
            self.failed_requests += 1
            return {
                "success": False,
                "error": "All providers unavailable",
                "provider": None
            }

        # Try providers in priority order
        for provider in available:
            try:
                result = await self._try_provider(provider, prompt, simulate_failures)
                if result["success"]:
                    return result
            except Exception as e:
                print(f"  ⚠️  {provider.name} failed: {e}")
                continue

        self.failed_requests += 1
        return {
            "success": False,
            "error": "All providers failed",
            "provider": None
        }

    async def _try_provider(
        self,
        provider: LLMProvider,
        prompt: str,
        simulate_failures: Dict[str, float]
    ) -> Dict[str, Any]:
        """Try a single provider"""

        # Simulate provider behavior
        failure_prob = simulate_failures.get(provider.name, 0.0)

        # Simulate latency
        latency = provider.avg_latency_ms + random.randint(-100, 100)
        await asyncio.sleep(latency / 1000)

        # Check for simulated failure
        if random.random() < failure_prob:
            self.pool.record_failure(provider)
            raise Exception(f"Simulated failure (prob={failure_prob})")

        # Success!
        self.pool.record_success(provider)

        # Calculate cost (simulated tokens)
        tokens = len(prompt.split()) * 3
        cost = (tokens / 1000) * provider.cost_per_1k_tokens
        self.total_cost += cost

        # Track usage
        self.provider_usage[provider.name] = self.provider_usage.get(provider.name, 0) + 1

        return {
            "success": True,
            "provider": provider.name,
            "latency_ms": latency,
            "tokens": tokens,
            "cost": cost,
            "response": f"Response from {provider.name}: Processed '{prompt[:30]}...'"
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics"""
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (self.total_requests - self.failed_requests) / self.total_requests * 100 if self.total_requests > 0 else 0,
            "total_cost": round(self.total_cost, 4),
            "provider_usage": self.provider_usage,
            "provider_status": {
                p.name: {
                    "status": p.status.value,
                    "circuit": p.circuit_state.value,
                    "failures": p.failure_count,
                    "successes": p.success_count
                }
                for p in self.pool.providers
            }
        }


async def demo_basic_failover():
    """Demo: Basic failover when primary fails"""
    print("\n" + "="*60)
    print("Demo 1: Basic Provider Failover")
    print("="*60)

    # Setup providers
    pool = ProviderPool(failure_threshold=3)
    pool.add_provider(LLMProvider(
        name="OpenAI",
        priority=1,
        cost_per_1k_tokens=0.03,
        avg_latency_ms=500
    ))
    pool.add_provider(LLMProvider(
        name="Anthropic",
        priority=2,
        cost_per_1k_tokens=0.025,
        avg_latency_ms=600
    ))
    pool.add_provider(LLMProvider(
        name="DeepSeek",
        priority=3,
        cost_per_1k_tokens=0.001,
        avg_latency_ms=400
    ))

    router = SmartRouter(pool)

    # Simulate requests with OpenAI failures
    print("\n📡 Sending 10 requests with OpenAI at 80% failure rate...")

    for i in range(10):
        result = await router.route_request(
            f"Request {i+1}: Generate a short story",
            simulate_failures={"OpenAI": 0.8}  # 80% failure
        )
        status = "✅" if result["success"] else "❌"
        provider = result.get("provider", "None")
        print(f"  Request {i+1}: {status} Provider: {provider}")
        await asyncio.sleep(0.1)

    # Print stats
    stats = router.get_stats()
    print(f"\n📊 Results:")
    print(f"  Success Rate: {stats['success_rate']:.1f}%")
    print(f"  Total Cost: ${stats['total_cost']:.4f}")
    print(f"  Provider Usage: {stats['provider_usage']}")
    print(f"  Provider Status:")
    for name, status in stats['provider_status'].items():
        print(f"    {name}: circuit={status['circuit']}, failures={status['failures']}")


async def demo_circuit_breaker():
    """Demo: Circuit breaker opens and recovers"""
    print("\n" + "="*60)
    print("Demo 2: Circuit Breaker Pattern")
    print("="*60)

    # Setup with short circuit reset
    pool = ProviderPool(failure_threshold=3, circuit_reset_seconds=2)
    pool.add_provider(LLMProvider(
        name="Primary",
        priority=1,
        cost_per_1k_tokens=0.03,
        avg_latency_ms=300
    ))
    pool.add_provider(LLMProvider(
        name="Backup",
        priority=2,
        cost_per_1k_tokens=0.02,
        avg_latency_ms=400
    ))

    router = SmartRouter(pool)

    print("\n📡 Phase 1: Primary failing (100% failure)...")
    for i in range(5):
        result = await router.route_request(
            f"Request {i+1}",
            simulate_failures={"Primary": 1.0}  # Always fail
        )
        print(f"  Request {i+1}: Provider={result.get('provider', 'None')}")

    print("\n⏳ Waiting 3 seconds for circuit reset...")
    await asyncio.sleep(3)

    print("\n📡 Phase 2: Primary recovered (0% failure)...")
    for i in range(5):
        result = await router.route_request(
            f"Request {i+6}",
            simulate_failures={}  # No failures
        )
        print(f"  Request {i+6}: Provider={result.get('provider', 'None')}")

    stats = router.get_stats()
    print(f"\n📊 Final Status:")
    for name, status in stats['provider_status'].items():
        print(f"  {name}: circuit={status['circuit']}, successes={status['successes']}")


async def demo_cost_optimization():
    """Demo: Cost-aware failover"""
    print("\n" + "="*60)
    print("Demo 3: Cost-Optimized Failover")
    print("="*60)

    # Setup with cost-ordered priorities
    pool = ProviderPool()
    pool.add_provider(LLMProvider(
        name="DeepSeek (Cheap)",
        priority=1,
        cost_per_1k_tokens=0.001,
        avg_latency_ms=500
    ))
    pool.add_provider(LLMProvider(
        name="Anthropic (Medium)",
        priority=2,
        cost_per_1k_tokens=0.015,
        avg_latency_ms=400
    ))
    pool.add_provider(LLMProvider(
        name="OpenAI (Premium)",
        priority=3,
        cost_per_1k_tokens=0.03,
        avg_latency_ms=300
    ))

    router = SmartRouter(pool)

    print("\n📡 Sending 20 requests (cheapest provider first)...")

    for i in range(20):
        # DeepSeek fails 30%, Anthropic fails 10%
        result = await router.route_request(
            "Generate a detailed analysis of market trends for Q4",
            simulate_failures={
                "DeepSeek (Cheap)": 0.3,
                "Anthropic (Medium)": 0.1
            }
        )

    stats = router.get_stats()
    print(f"\n📊 Cost Analysis:")
    print(f"  Total Requests: {stats['total_requests']}")
    print(f"  Total Cost: ${stats['total_cost']:.4f}")
    print(f"  Average Cost/Request: ${stats['total_cost']/stats['total_requests']:.4f}")
    print(f"\n  Provider Distribution:")
    for provider, count in sorted(stats['provider_usage'].items(), key=lambda x: -x[1]):
        print(f"    {provider}: {count} requests")


async def demo_multi_region():
    """Demo: Multi-region failover"""
    print("\n" + "="*60)
    print("Demo 4: Multi-Region Failover")
    print("="*60)

    # Setup regional providers
    pool = ProviderPool(failure_threshold=2)
    pool.add_provider(LLMProvider(
        name="US-East (Primary)",
        priority=1,
        cost_per_1k_tokens=0.02,
        avg_latency_ms=50
    ))
    pool.add_provider(LLMProvider(
        name="US-West (Secondary)",
        priority=2,
        cost_per_1k_tokens=0.02,
        avg_latency_ms=100
    ))
    pool.add_provider(LLMProvider(
        name="EU-West (Tertiary)",
        priority=3,
        cost_per_1k_tokens=0.025,
        avg_latency_ms=200
    ))

    router = SmartRouter(pool)

    print("\n📡 Simulating regional outage (US-East down)...")

    for i in range(10):
        result = await router.route_request(
            f"Request {i+1}",
            simulate_failures={"US-East (Primary)": 1.0}
        )
        latency = result.get("latency_ms", 0)
        provider = result.get("provider", "None")
        print(f"  Request {i+1}: {provider} ({latency}ms)")

    stats = router.get_stats()
    print(f"\n📊 Regional Distribution:")
    for provider, count in stats['provider_usage'].items():
        print(f"  {provider}: {count} requests")


async def main():
    """Run all demos"""
    print("="*60)
    print("🔄 LLM Provider Failover Demo")
    print("="*60)
    print("\nThis demo shows automatic failover between LLM providers")
    print("when providers fail or become unavailable.")

    await demo_basic_failover()
    await demo_circuit_breaker()
    await demo_cost_optimization()
    await demo_multi_region()

    print("\n" + "="*60)
    print("✅ All demos completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
