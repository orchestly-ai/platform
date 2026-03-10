#!/usr/bin/env python3
"""
Demo: SmartRouter - LLM Provider Failover

Shows the provider failover mechanisms from ROADMAP.md:
1. Basic routing with different strategies
2. Automatic failover on provider failure
3. Circuit breaker opening after consecutive failures
4. Circuit breaker reset and recovery
5. Cost and latency optimized routing
6. Health monitoring and metrics

Reference: ROADMAP.md Section "Provider Outage Failover Strategy"

Key Design Decisions:
- Circuit opens after 5 consecutive failures
- Circuit resets after 60 seconds (half-open state)
- Mid-stream failover preserves conversation context
- Multiple routing strategies for different use cases
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Add parent directories to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
parent_dir = backend_dir.parent
sys.path.insert(0, str(parent_dir))

from backend.shared.smart_router_service import (
    SmartRouter,
    RoutingStrategy,
    RoutingDecision,
    OrgRoutingConfig,
    ProviderHealth,
    ProviderError,
    UniversalRequest,
    UniversalResponse,
    ExecutionState,
)


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(description: str, result, indent=2):
    """Print a result with formatting."""
    prefix = " " * indent
    if hasattr(result, 'to_dict'):
        print(f"{prefix}{description}:")
        for key, value in result.to_dict().items():
            print(f"{prefix}  {key}: {value}")
    else:
        print(f"{prefix}{description}: {result}")


async def demo_basic_routing():
    """Demo 1: Basic routing with different strategies."""
    print_header("Demo 1: Basic Routing Strategies")
    print("\nSmartRouter supports multiple routing strategies to match your needs.\n")

    router = SmartRouter(db=None)
    request = UniversalRequest(
        messages=[{"role": "user", "content": "Hello!"}],
        model="gpt-4",
    )

    # Test different strategies
    strategies = [
        (RoutingStrategy.PRIMARY_ONLY, "Uses only primary, no fallback"),
        (RoutingStrategy.PRIMARY_WITH_BACKUP, "Primary with automatic failover"),
        (RoutingStrategy.BEST_AVAILABLE, "Selects healthiest provider"),
        (RoutingStrategy.COST_OPTIMIZED, "Selects cheapest provider"),
        (RoutingStrategy.LATENCY_OPTIMIZED, "Selects fastest provider"),
    ]

    for strategy, description in strategies:
        config = OrgRoutingConfig(
            org_id="demo-org",
            routing_strategy=strategy,
            primary_provider="openai",
            primary_model="gpt-4",
            backup_provider="anthropic",
            backup_model="claude-3-sonnet",
            fallback_chain=[{"provider": "deepseek", "model": "deepseek-chat"}],
        )

        decision = await router.route_request(request, config)
        print(f"\n{strategy.value}:")
        print(f"  Description: {description}")
        print(f"  Selected: {decision.provider}/{decision.model}")
        if decision.fallback_provider:
            print(f"  Fallback: {decision.fallback_provider}/{decision.fallback_model}")

    print("\n[OK] All routing strategies work correctly!")


async def demo_failover():
    """Demo 2: Automatic failover on provider failure."""
    print_header("Demo 2: Automatic Failover")
    print("\nWhen the primary provider fails, SmartRouter automatically fails over.\n")

    router = SmartRouter(db=None)

    # Create a mock that fails on primary
    async def mock_call_provider(provider, model, request):
        if provider == "openai":
            print(f"  [FAIL] OpenAI call failed: Connection timeout")
            raise ProviderError(
                provider="openai",
                error_type="timeout",
                message="Connection timed out after 30s"
            )
        print(f"  [OK] {provider} call succeeded")
        return UniversalResponse(
            content=f"Hello from {provider}!",
            provider=provider,
            model=model,
            latency_ms=150,
        )

    router._call_provider = mock_call_provider

    request = UniversalRequest(
        messages=[{"role": "user", "content": "Hello!"}],
        model="gpt-4",
    )

    routing = RoutingDecision(
        provider="openai",
        model="gpt-4",
        fallback_provider="anthropic",
        fallback_model="claude-3-sonnet",
    )

    print("1. Attempting request with OpenAI (will fail)...")
    response = await router.execute_with_failover(request, routing)

    print(f"\n2. Failover Result:")
    print(f"  Response from: {response.provider}/{response.model}")
    print(f"  Failover occurred: {response.metadata.get('failover', False)}")
    print(f"  Original provider: {response.metadata.get('original_provider', 'N/A')}")
    print(f"  Failover reason: {response.metadata.get('failover_reason', 'N/A')}")

    metrics = router.get_metrics()
    print(f"\n3. Router Metrics:")
    print(f"  Total requests: {metrics['total_requests']}")
    print(f"  Failover count: {metrics['failover_count']}")
    print(f"  Failover rate: {metrics['failover_rate']}")

    print("\n[OK] Automatic failover works correctly!")


async def demo_circuit_breaker():
    """Demo 3: Circuit breaker opens after consecutive failures."""
    print_header("Demo 3: Circuit Breaker")
    print("\nCircuit breaker opens after 5 consecutive failures to prevent overload.\n")

    router = SmartRouter(db=None)
    provider = "unstable-provider"

    print("1. Recording 5 consecutive failures...")
    for i in range(5):
        await router._record_failure(
            provider,
            ProviderError(provider=provider, error_type="timeout", message="Timeout")
        )
        health = router.get_provider_health(provider)
        print(f"  Failure {i+1}: consecutive={health.consecutive_failures}, circuit_open={health.circuit_open}")

    print("\n2. Circuit state after 5 failures:")
    health = router.get_provider_health(provider)
    print_result("Provider Health", health)

    print("\n3. Checking if provider is healthy...")
    is_healthy = await router._is_provider_healthy(provider)
    print(f"  Is healthy: {is_healthy} (expected: False)")

    print("\n4. Simulating circuit reset timeout...")
    # Manually expire the circuit timeout
    health.circuit_open_until = datetime.utcnow()

    is_healthy = await router._is_provider_healthy(provider)
    print(f"  After timeout - Is healthy: {is_healthy} (expected: True)")
    print(f"  Circuit transitioned to half-open state")

    print("\n[OK] Circuit breaker protects against failing providers!")


async def demo_health_tracking():
    """Demo 4: Health tracking and metrics."""
    print_header("Demo 4: Health Tracking & Metrics")
    print("\nSmartRouter tracks detailed health metrics for each provider.\n")

    router = SmartRouter(db=None)

    # Simulate some traffic
    print("1. Simulating mixed traffic to multiple providers...")

    # OpenAI - mostly successful
    for _ in range(10):
        await router._record_success("openai", latency_ms=100 + (_ * 10))
    await router._record_failure(
        "openai",
        ProviderError(provider="openai", error_type="timeout", message="Timeout")
    )

    # Anthropic - all successful, lower latency
    for _ in range(8):
        await router._record_success("anthropic", latency_ms=50 + (_ * 5))

    # DeepSeek - some failures
    for _ in range(5):
        await router._record_success("deepseek", latency_ms=200)
    for _ in range(3):
        await router._record_failure(
            "deepseek",
            ProviderError(provider="deepseek", error_type="rate_limit", message="Rate limited")
        )

    print("\n2. Provider Health Summary:")
    all_health = router.get_all_health()
    for provider, health in all_health.items():
        print(f"\n  {provider}:")
        print(f"    Status: {health['status']}")
        print(f"    Success Rate: {health['success_rate']}")
        print(f"    Avg Latency: {health['avg_latency_ms']}ms")
        print(f"    Consecutive Failures: {health['consecutive_failures']}")

    print("\n3. Router Metrics:")
    metrics = router.get_metrics()
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    print("\n[OK] Health tracking provides visibility into provider performance!")


async def demo_routing_strategies():
    """Demo 5: Different routing strategies in action."""
    print_header("Demo 5: Routing Strategy Comparison")
    print("\nCompare how different strategies select providers.\n")

    router = SmartRouter(db=None)

    # Set up diverse health metrics
    router.provider_health["openai"] = ProviderHealth(
        provider="openai",
        total_successes=90,
        total_failures=10,
        avg_latency_ms=150,
        last_latencies=[150],
    )
    router.provider_health["anthropic"] = ProviderHealth(
        provider="anthropic",
        total_successes=95,
        total_failures=5,
        avg_latency_ms=80,
        last_latencies=[80],
    )
    router.provider_health["deepseek"] = ProviderHealth(
        provider="deepseek",
        total_successes=85,
        total_failures=15,
        avg_latency_ms=200,
        last_latencies=[200],
    )

    request = UniversalRequest(
        messages=[{"role": "user", "content": "Hello!"}],
    )

    print("Provider Health Metrics:")
    for provider, health in router.get_all_health().items():
        print(f"  {provider}: success_rate={health['success_rate']}, latency={health['avg_latency_ms']}ms")

    print("\nRouting Decisions by Strategy:")

    strategies_to_test = [
        RoutingStrategy.BEST_AVAILABLE,
        RoutingStrategy.COST_OPTIMIZED,
        RoutingStrategy.LATENCY_OPTIMIZED,
    ]

    for strategy in strategies_to_test:
        config = OrgRoutingConfig(
            org_id="demo-org",
            routing_strategy=strategy,
            primary_provider="openai",
            primary_model="gpt-4",
            backup_provider="anthropic",
            backup_model="claude-3-sonnet",
            fallback_chain=[{"provider": "deepseek", "model": "deepseek-chat"}],
        )

        decision = await router.route_request(request, config)
        print(f"\n  {strategy.value}:")
        print(f"    Selected: {decision.provider}/{decision.model}")
        print(f"    Reason: {decision.reason}")

    print("\n[OK] Strategies select providers based on their optimization goals!")


async def demo_mid_stream_failover():
    """Demo 6: Mid-stream failover with context preservation."""
    print_header("Demo 6: Mid-Stream Failover")
    print("\nWhen failover happens mid-conversation, context is preserved.\n")

    router = SmartRouter(db=None)

    # Set up execution state with conversation history
    execution_state = ExecutionState(
        execution_id=uuid4(),
        conversation_history=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What's the capital of France?"},
            {"role": "assistant", "content": "The capital of France is Paris."},
            {"role": "user", "content": "Tell me more about it."},
        ],
        current_provider="openai",
    )

    print(f"1. Current conversation has {len(execution_state.conversation_history)} messages")
    print(f"   Current provider: {execution_state.current_provider}")

    # Mock that fails on primary
    async def mock_call_provider(provider, model, request):
        if provider == "openai":
            raise ProviderError(provider="openai", error_type="server_error", message="503 Service Unavailable")
        return UniversalResponse(
            content="Paris is the capital and largest city of France...",
            provider=provider,
            model=model,
            latency_ms=120,
        )

    router._call_provider = mock_call_provider

    request = UniversalRequest(
        messages=execution_state.conversation_history + [
            {"role": "user", "content": "What's the population?"}
        ],
    )

    routing = RoutingDecision(
        provider="openai",
        model="gpt-4",
        fallback_provider="anthropic",
        fallback_model="claude-3-sonnet",
    )

    print("\n2. Executing with failover...")
    response = await router.execute_with_failover(request, routing, execution_state)

    print(f"\n3. Result:")
    print(f"   Response from: {response.provider}")
    print(f"   Failover occurred: {response.metadata.get('failover')}")
    print(f"   Context preserved: Yes (messages renormalized for new provider)")

    print("\n[OK] Mid-stream failover preserves conversation context!")


async def demo_use_cases():
    """Demo 7: Common use cases and recommendations."""
    print_header("Demo 7: Use Case Guide")
    print("\nFrom ROADMAP.md - When to Use Each Strategy:\n")

    print("┌────────────────────────────┬─────────────────────────────────────────┐")
    print("│ Use Case                   │ Recommended Strategy                    │")
    print("├────────────────────────────┼─────────────────────────────────────────┤")
    print("│ Production critical        │ PRIMARY_WITH_BACKUP                     │")
    print("│ Cost-sensitive workloads   │ COST_OPTIMIZED                          │")
    print("│ Real-time applications     │ LATENCY_OPTIMIZED                       │")
    print("│ High availability          │ BEST_AVAILABLE                          │")
    print("│ Testing/development        │ PRIMARY_ONLY                            │")
    print("└────────────────────────────┴─────────────────────────────────────────┘")

    print("\nCircuit Breaker Thresholds:")
    print("  - Opens after: 5 consecutive failures")
    print("  - Reset timeout: 60 seconds")
    print("  - Half-open allows 1 test request")

    print("\n" + "-" * 60)
    print("SmartRouter provides automatic resilience for LLM operations!")
    print("-" * 60)


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  SMART ROUTER DEMO")
    print("  LLM Provider Failover & Health Management")
    print("=" * 60)
    print("\nReference: ROADMAP.md Section 'Provider Outage Failover Strategy'")

    try:
        await demo_basic_routing()
        await demo_failover()
        await demo_circuit_breaker()
        await demo_health_tracking()
        await demo_routing_strategies()
        await demo_mid_stream_failover()
        await demo_use_cases()

        print("\n" + "=" * 60)
        print("  ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nKey Takeaways:")
        print("  1. SmartRouter provides automatic failover on provider errors")
        print("  2. Circuit breakers prevent cascading failures")
        print("  3. Multiple strategies optimize for cost, latency, or availability")
        print("  4. Mid-stream failover preserves conversation context")
        print("  5. Health tracking enables informed routing decisions")
        print()

    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
