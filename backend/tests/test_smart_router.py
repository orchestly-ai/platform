"""
SmartRouter Service Tests

Tests for ROADMAP.md Section: Provider Outage Failover Strategy

Test Coverage:
- Basic routing with different strategies
- Failover on provider failure
- Circuit breaker opening after consecutive failures
- Circuit breaker reset after timeout
- Mid-stream failover with state
- Health tracking and metrics
- Cost and latency optimized routing
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path

# Add backend directory to path
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
    ProviderStatus,
    ProviderError,
    UniversalRequest,
    UniversalResponse,
    ExecutionState,
    get_smart_router,
    reset_smart_router,
)


@pytest.fixture
def smart_router():
    """Create a fresh SmartRouter instance for testing."""
    reset_smart_router()
    return SmartRouter(db=None, provider_clients={})


@pytest.fixture
def org_config():
    """Create a default org routing config."""
    return OrgRoutingConfig(
        org_id="test-org",
        routing_strategy=RoutingStrategy.PRIMARY_WITH_BACKUP,
        primary_provider="openai",
        primary_model="gpt-4",
        backup_provider="anthropic",
        backup_model="claude-3-sonnet",
    )


@pytest.fixture
def universal_request():
    """Create a sample universal request."""
    return UniversalRequest(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ],
        tools=[],
        model="gpt-4",
    )


# =============================================================================
# Basic Routing Tests
# =============================================================================

@pytest.mark.asyncio
async def test_route_primary_only(smart_router, org_config, universal_request):
    """PRIMARY_ONLY strategy should only return primary provider."""
    org_config.routing_strategy = RoutingStrategy.PRIMARY_ONLY

    decision = await smart_router.route_request(universal_request, org_config)

    assert decision.provider == "openai"
    assert decision.model == "gpt-4"
    assert decision.fallback_provider is None
    assert decision.strategy_used == RoutingStrategy.PRIMARY_ONLY


@pytest.mark.asyncio
async def test_route_primary_with_backup(smart_router, org_config, universal_request):
    """PRIMARY_WITH_BACKUP should include fallback provider."""
    org_config.routing_strategy = RoutingStrategy.PRIMARY_WITH_BACKUP

    decision = await smart_router.route_request(universal_request, org_config)

    assert decision.provider == "openai"
    assert decision.model == "gpt-4"
    assert decision.fallback_provider == "anthropic"
    assert decision.fallback_model == "claude-3-sonnet"
    assert decision.strategy_used == RoutingStrategy.PRIMARY_WITH_BACKUP


@pytest.mark.asyncio
async def test_route_switches_to_backup_when_primary_unhealthy(smart_router, org_config, universal_request):
    """Should route to backup when primary circuit is open."""
    org_config.routing_strategy = RoutingStrategy.PRIMARY_WITH_BACKUP

    # Open circuit for primary provider
    smart_router.provider_health["openai"] = ProviderHealth(
        provider="openai",
        circuit_open=True,
        circuit_open_until=datetime.utcnow() + timedelta(minutes=1)
    )

    decision = await smart_router.route_request(universal_request, org_config)

    assert decision.provider == "anthropic"
    assert decision.model == "claude-3-sonnet"
    assert decision.reason == "primary_circuit_open"


# =============================================================================
# Failover Tests
# =============================================================================

@pytest.mark.asyncio
async def test_failover_on_provider_error(smart_router, universal_request):
    """Should failover to backup when primary fails."""
    # Create a mock that fails on first call, succeeds on second
    call_count = 0

    async def mock_call_provider(provider, model, request, **kwargs):
        nonlocal call_count
        call_count += 1
        if provider == "openai":
            raise ProviderError(
                provider="openai",
                error_type="timeout",
                message="Request timed out"
            )
        return UniversalResponse(
            content="Response from anthropic",
            provider=provider,
            model=model,
            latency_ms=100,
        )

    smart_router._call_provider = mock_call_provider

    routing = RoutingDecision(
        provider="openai",
        model="gpt-4",
        fallback_provider="anthropic",
        fallback_model="claude-3-sonnet",
    )

    response = await smart_router.execute_with_failover(universal_request, routing)

    assert response.provider == "anthropic"
    assert response.metadata.get("failover") is True
    assert response.metadata.get("original_provider") == "openai"
    assert smart_router._failover_count == 1


@pytest.mark.asyncio
async def test_no_failover_without_backup(smart_router, universal_request):
    """Should raise error when primary fails and no backup configured."""
    async def mock_call_provider(provider, model, request, **kwargs):
        raise ProviderError(
            provider=provider,
            error_type="server_error",
            message="Internal server error"
        )

    smart_router._call_provider = mock_call_provider

    routing = RoutingDecision(
        provider="openai",
        model="gpt-4",
        fallback_provider=None,  # No backup
    )

    with pytest.raises(ProviderError):
        await smart_router.execute_with_failover(universal_request, routing)


@pytest.mark.asyncio
async def test_failover_fails_when_backup_circuit_open(smart_router, universal_request):
    """Should fail when both primary fails and backup circuit is open."""
    async def mock_call_provider(provider, model, request, **kwargs):
        raise ProviderError(provider=provider, error_type="timeout", message="Timeout")

    smart_router._call_provider = mock_call_provider

    # Open circuit for backup
    smart_router.provider_health["anthropic"] = ProviderHealth(
        provider="anthropic",
        circuit_open=True,
        circuit_open_until=datetime.utcnow() + timedelta(minutes=1)
    )

    routing = RoutingDecision(
        provider="openai",
        model="gpt-4",
        fallback_provider="anthropic",
        fallback_model="claude-3-sonnet",
    )

    with pytest.raises(ProviderError) as exc_info:
        await smart_router.execute_with_failover(universal_request, routing)

    assert exc_info.value.error_type == "circuit_open"


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

@pytest.mark.asyncio
async def test_circuit_opens_after_consecutive_failures(smart_router):
    """Circuit should open after 5 consecutive failures."""
    provider = "openai"

    # Record 5 consecutive failures
    for i in range(5):
        await smart_router._record_failure(
            provider,
            ProviderError(provider=provider, error_type="timeout", message="Timeout")
        )

    health = smart_router.get_provider_health(provider)

    assert health is not None
    assert health.circuit_open is True
    assert health.consecutive_failures == 5
    assert not await smart_router._is_provider_healthy(provider)


@pytest.mark.asyncio
async def test_circuit_resets_after_timeout(smart_router):
    """Circuit should half-open after reset timeout."""
    provider = "openai"

    # Open circuit with expired timeout
    smart_router.provider_health[provider] = ProviderHealth(
        provider=provider,
        circuit_open=True,
        circuit_open_until=datetime.utcnow() - timedelta(seconds=1),  # Expired
        consecutive_failures=5
    )

    # Check should return True (circuit transitions to half-open)
    is_healthy = await smart_router._is_provider_healthy(provider)

    assert is_healthy is True
    assert smart_router.provider_health[provider].circuit_open is False
    assert smart_router.provider_health[provider].consecutive_failures == 0


@pytest.mark.asyncio
async def test_success_resets_consecutive_failures(smart_router):
    """Success should reset consecutive failure count."""
    provider = "openai"

    # Add some failures (but not enough to open circuit)
    for _ in range(3):
        await smart_router._record_failure(
            provider,
            ProviderError(provider=provider, error_type="timeout", message="Timeout")
        )

    assert smart_router.provider_health[provider].consecutive_failures == 3

    # Record success
    await smart_router._record_success(provider, latency_ms=100)

    assert smart_router.provider_health[provider].consecutive_failures == 0
    assert smart_router.provider_health[provider].total_successes == 1


@pytest.mark.asyncio
async def test_manual_circuit_reset(smart_router):
    """Should be able to manually reset circuit."""
    provider = "openai"

    # Open circuit
    smart_router.provider_health[provider] = ProviderHealth(
        provider=provider,
        circuit_open=True,
        circuit_open_until=datetime.utcnow() + timedelta(minutes=5),
        consecutive_failures=5
    )

    # Manual reset
    result = smart_router.reset_circuit(provider)

    assert result is True
    assert smart_router.provider_health[provider].circuit_open is False
    assert smart_router.provider_health[provider].consecutive_failures == 0


# =============================================================================
# Routing Strategy Tests
# =============================================================================

@pytest.mark.asyncio
async def test_best_available_selects_healthiest(smart_router, org_config, universal_request):
    """BEST_AVAILABLE should select provider with best health score."""
    org_config.routing_strategy = RoutingStrategy.BEST_AVAILABLE

    # Set up health metrics - anthropic has better success rate
    smart_router.provider_health["openai"] = ProviderHealth(
        provider="openai",
        total_successes=80,
        total_failures=20,
        avg_latency_ms=150,
    )
    smart_router.provider_health["anthropic"] = ProviderHealth(
        provider="anthropic",
        total_successes=95,
        total_failures=5,
        avg_latency_ms=100,
    )

    decision = await smart_router.route_request(universal_request, org_config)

    # Anthropic should be selected (higher success rate, lower latency)
    assert decision.provider == "anthropic"
    assert decision.strategy_used == RoutingStrategy.BEST_AVAILABLE


@pytest.mark.asyncio
async def test_cost_optimized_selects_cheapest(smart_router, org_config, universal_request):
    """COST_OPTIMIZED should select cheapest healthy provider."""
    org_config.routing_strategy = RoutingStrategy.COST_OPTIMIZED
    org_config.fallback_chain = [
        {"provider": "deepseek", "model": "deepseek-chat"}
    ]

    decision = await smart_router.route_request(universal_request, org_config)

    # DeepSeek should be selected (cheapest in pricing table)
    assert decision.provider == "deepseek"
    assert decision.model == "deepseek-chat"
    assert decision.strategy_used == RoutingStrategy.COST_OPTIMIZED


@pytest.mark.asyncio
async def test_latency_optimized_selects_fastest(smart_router, org_config, universal_request):
    """LATENCY_OPTIMIZED should select lowest latency provider."""
    org_config.routing_strategy = RoutingStrategy.LATENCY_OPTIMIZED

    # Set up latency metrics
    smart_router.provider_health["openai"] = ProviderHealth(
        provider="openai",
        avg_latency_ms=200,
        last_latencies=[200],
    )
    smart_router.provider_health["anthropic"] = ProviderHealth(
        provider="anthropic",
        avg_latency_ms=50,
        last_latencies=[50],
    )

    decision = await smart_router.route_request(universal_request, org_config)

    assert decision.provider == "anthropic"
    assert decision.strategy_used == RoutingStrategy.LATENCY_OPTIMIZED


# =============================================================================
# Health Tracking Tests
# =============================================================================

@pytest.mark.asyncio
async def test_latency_tracking(smart_router):
    """Should track rolling average latency."""
    provider = "openai"

    # Record multiple latencies
    for latency in [100, 150, 200, 150, 100]:
        await smart_router._record_success(provider, latency_ms=latency)

    health = smart_router.get_provider_health(provider)

    assert health is not None
    assert health.avg_latency_ms == 140  # Average of [100, 150, 200, 150, 100]
    assert len(health.last_latencies) == 5


@pytest.mark.asyncio
async def test_get_all_health(smart_router):
    """Should return health for all tracked providers."""
    # Record some activity
    await smart_router._record_success("openai", 100)
    await smart_router._record_failure(
        "anthropic",
        ProviderError(provider="anthropic", error_type="timeout", message="Timeout")
    )

    all_health = smart_router.get_all_health()

    assert "openai" in all_health
    assert "anthropic" in all_health
    assert all_health["openai"]["status"] == "healthy"
    assert all_health["anthropic"]["consecutive_failures"] == 1


@pytest.mark.asyncio
async def test_get_metrics(smart_router, universal_request):
    """Should return router metrics."""
    # Execute some requests
    smart_router._total_requests = 100
    smart_router._failover_count = 5

    metrics = smart_router.get_metrics()

    assert metrics["total_requests"] == 100
    assert metrics["failover_count"] == 5
    assert metrics["failover_rate"] == "5.0%"


# =============================================================================
# Mid-Stream Failover Tests
# =============================================================================

@pytest.mark.asyncio
async def test_mid_stream_failover_renormalizes(smart_router, universal_request):
    """Should renormalize conversation history when failing over mid-stream."""
    execution_state = ExecutionState(
        execution_id=uuid4(),
        conversation_history=[
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ],
        current_provider="openai",
    )

    call_count = 0

    async def mock_call_provider(provider, model, request, **kwargs):
        nonlocal call_count
        call_count += 1
        if provider == "openai":
            raise ProviderError(provider="openai", error_type="timeout", message="Timeout")
        return UniversalResponse(
            content="Response",
            provider=provider,
            model=model,
            latency_ms=100,
        )

    smart_router._call_provider = mock_call_provider

    routing = RoutingDecision(
        provider="openai",
        model="gpt-4",
        fallback_provider="anthropic",
        fallback_model="claude-3-sonnet",
    )

    response = await smart_router.execute_with_failover(
        universal_request, routing, execution_state
    )

    assert response.provider == "anthropic"
    assert response.metadata.get("failover") is True


# =============================================================================
# Provider Health Status Tests
# =============================================================================

def test_provider_health_status_healthy():
    """Healthy provider should have HEALTHY status."""
    health = ProviderHealth(
        provider="openai",
        consecutive_failures=0,
    )
    assert health.status == ProviderStatus.HEALTHY


def test_provider_health_status_degraded():
    """Provider with 3+ failures should be DEGRADED."""
    health = ProviderHealth(
        provider="openai",
        consecutive_failures=3,
    )
    assert health.status == ProviderStatus.DEGRADED


def test_provider_health_status_circuit_open():
    """Provider with open circuit should have CIRCUIT_OPEN status."""
    health = ProviderHealth(
        provider="openai",
        circuit_open=True,
    )
    assert health.status == ProviderStatus.CIRCUIT_OPEN


def test_provider_health_success_rate():
    """Should calculate correct success rate."""
    health = ProviderHealth(
        provider="openai",
        total_successes=90,
        total_failures=10,
    )
    assert health.success_rate == 0.9


def test_provider_health_success_rate_no_calls():
    """Success rate should be 1.0 with no calls."""
    health = ProviderHealth(provider="openai")
    assert health.success_rate == 1.0


# =============================================================================
# Serialization Tests
# =============================================================================

def test_routing_decision_to_dict():
    """RoutingDecision should serialize to dict."""
    decision = RoutingDecision(
        provider="openai",
        model="gpt-4",
        fallback_provider="anthropic",
        fallback_model="claude-3-sonnet",
        reason="test_reason",
        strategy_used=RoutingStrategy.PRIMARY_WITH_BACKUP,
    )

    d = decision.to_dict()

    assert d["provider"] == "openai"
    assert d["model"] == "gpt-4"
    assert d["fallback_provider"] == "anthropic"
    assert d["strategy_used"] == "primary_backup"


def test_provider_health_to_dict():
    """ProviderHealth should serialize to dict."""
    health = ProviderHealth(
        provider="openai",
        consecutive_failures=2,
        total_successes=100,
        total_failures=5,
        avg_latency_ms=123.456,
    )

    d = health.to_dict()

    assert d["provider"] == "openai"
    assert d["consecutive_failures"] == 2
    assert d["success_rate"] == "95.2%"
    assert d["avg_latency_ms"] == 123.46


# =============================================================================
# Edge Cases
# =============================================================================

@pytest.mark.asyncio
async def test_route_with_empty_fallback_chain(smart_router, org_config, universal_request):
    """Should handle routing with empty fallback chain."""
    org_config.routing_strategy = RoutingStrategy.BEST_AVAILABLE
    org_config.fallback_chain = []

    decision = await smart_router.route_request(universal_request, org_config)

    assert decision.provider is not None
    assert decision.strategy_used == RoutingStrategy.BEST_AVAILABLE


@pytest.mark.asyncio
async def test_clear_health_metrics_single_provider(smart_router):
    """Should clear metrics for a single provider."""
    await smart_router._record_success("openai", 100)
    await smart_router._record_success("anthropic", 100)

    smart_router.clear_health_metrics("openai")

    assert "openai" not in smart_router.provider_health
    assert "anthropic" in smart_router.provider_health


@pytest.mark.asyncio
async def test_clear_health_metrics_all(smart_router):
    """Should clear metrics for all providers."""
    await smart_router._record_success("openai", 100)
    await smart_router._record_success("anthropic", 100)

    smart_router.clear_health_metrics()

    assert len(smart_router.provider_health) == 0


@pytest.mark.asyncio
async def test_reset_nonexistent_circuit(smart_router):
    """Resetting nonexistent circuit should return False."""
    result = smart_router.reset_circuit("nonexistent")
    assert result is False


# =============================================================================
# Singleton Tests
# =============================================================================

def test_get_smart_router_singleton():
    """get_smart_router should return singleton."""
    reset_smart_router()

    router1 = get_smart_router()
    router2 = get_smart_router()

    assert router1 is router2

    reset_smart_router()


def test_reset_smart_router():
    """reset_smart_router should clear singleton."""
    router1 = get_smart_router()
    reset_smart_router()
    router2 = get_smart_router()

    assert router1 is not router2

    reset_smart_router()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
