"""
Circuit Breaker Service Tests

Tests for ROADMAP.md Section: Recursive Loop & Cost Runaway Circuit Breaker

Test Coverage:
- Token velocity detection
- Cost velocity detection (kill action)
- Tool loop detection
- Batch operation bypass
- Recursion depth limits
- Metrics recording and persistence
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

from backend.shared.circuit_breaker_service import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerResult,
    CircuitBreakerAction,
    BatchOperationConfig,
    ExecutionMetrics,
    validate_batch_config,
    get_circuit_breaker
)


class MockDBSession:
    """Mock database session for testing."""

    def __init__(self):
        self.executions = {}

    async def execute(self, query):
        """Mock execute that returns empty results."""
        return MockResult(None)

    async def flush(self):
        """Mock flush."""
        pass


class MockResult:
    """Mock query result."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.fixture
def db_session():
    """Create a mock database session."""
    return MockDBSession()


@pytest.fixture
def circuit_breaker(db_session):
    """Create a circuit breaker with default config."""
    return CircuitBreaker(db_session)


@pytest.fixture
def strict_config():
    """Create a strict circuit breaker config for testing."""
    return CircuitBreakerConfig(
        token_velocity_per_minute=1000,  # Very low for testing
        cost_velocity_per_minute=0.10,   # $0.10/min
        same_tool_consecutive_limit=3,
        total_tool_calls_per_execution=10,
        total_llm_calls_per_execution=50,  # Higher to allow velocity tests
        max_recursion_depth=3
    )


@pytest.fixture
def strict_circuit_breaker(db_session, strict_config):
    """Create a circuit breaker with strict limits for testing."""
    return CircuitBreaker(db_session, strict_config)


# =============================================================================
# Token Velocity Tests
# =============================================================================

@pytest.mark.asyncio
async def test_normal_token_velocity_proceeds(circuit_breaker):
    """Normal token usage should proceed."""
    execution_id = uuid4()

    # Simulate normal usage
    await circuit_breaker.record_llm_call(execution_id, tokens_used=1000, cost=0.01)

    result = await circuit_breaker.check_before_llm_call(execution_id, estimated_tokens=1000)

    assert result.proceed is True
    assert result.action == CircuitBreakerAction.PROCEED


@pytest.mark.asyncio
async def test_high_token_velocity_triggers_suspension(strict_circuit_breaker):
    """High token velocity should trigger suspension."""
    execution_id = uuid4()

    # Simulate high velocity: 5000 tokens quickly (exceeds 1000/min limit)
    for _ in range(5):
        await strict_circuit_breaker.record_llm_call(execution_id, tokens_used=1000, cost=0.001)

    # Check should trigger token velocity limit
    result = await strict_circuit_breaker.check_before_llm_call(execution_id)

    # Should trigger because 5000 tokens in ~0 time exceeds 1000/min
    assert result.proceed is False
    assert result.action == CircuitBreakerAction.SUSPEND_FOR_APPROVAL
    assert "token velocity" in result.reason.lower() or "velocity" in result.reason.lower()


@pytest.mark.asyncio
async def test_batch_bypass_allows_high_token_velocity(strict_circuit_breaker):
    """Batch operations with bypass should proceed despite high velocity."""
    execution_id = uuid4()

    # Simulate high velocity
    for _ in range(10):
        await strict_circuit_breaker.record_llm_call(execution_id, tokens_used=1000, cost=0.01)

    # Use batch config with bypass
    batch_config = BatchOperationConfig(
        bypass_circuit_breaker=True,
        elevated_token_limit=100_000,
        audit_reason="Quarterly report generation - 500 documents"
    )

    result = await strict_circuit_breaker.check_before_llm_call(
        execution_id,
        batch_config=batch_config
    )

    assert result.proceed is True


# =============================================================================
# Cost Velocity Tests
# =============================================================================

@pytest.mark.asyncio
async def test_cost_runaway_triggers_kill(db_session):
    """Cost runaway should trigger KILL action (most severe)."""
    # Use custom config with high token limit but low cost limit
    config = CircuitBreakerConfig(
        token_velocity_per_minute=100_000,  # High token limit
        cost_velocity_per_minute=0.10,       # Low cost limit: $0.10/min
        total_llm_calls_per_execution=100,
    )
    circuit_breaker = CircuitBreaker(db_session, config)
    execution_id = uuid4()

    # Simulate cost runaway: $1.00 very quickly (10x the $0.10/min limit)
    # Keep tokens low so token velocity doesn't trigger first
    for _ in range(10):
        await circuit_breaker.record_llm_call(execution_id, tokens_used=100, cost=0.10)

    result = await circuit_breaker.check_before_llm_call(execution_id)

    assert result.proceed is False
    assert result.action == CircuitBreakerAction.KILL
    assert "cost" in result.reason.lower()


@pytest.mark.asyncio
async def test_normal_cost_proceeds(circuit_breaker):
    """Normal cost usage should proceed."""
    execution_id = uuid4()

    # Simulate normal cost
    await circuit_breaker.record_llm_call(execution_id, tokens_used=1000, cost=0.01)

    result = await circuit_breaker.check_before_llm_call(execution_id)

    assert result.proceed is True
    assert result.action == CircuitBreakerAction.PROCEED


# =============================================================================
# Tool Loop Detection Tests
# =============================================================================

@pytest.mark.asyncio
async def test_tool_loop_detection_identical_params(strict_circuit_breaker):
    """Same tool with identical params 4x should trigger KILL (3 in history + current)."""
    execution_id = uuid4()
    tool_name = "search_database"
    params = {"query": "SELECT * FROM users", "limit": 100}

    # Call same tool 4 times with identical params
    # The check looks at history, so need 3 recorded calls before the 4th triggers
    for i in range(4):
        result = await strict_circuit_breaker.check_before_tool_call(
            execution_id, tool_name, params
        )
        if i < 3:
            # First 3 calls pass (history has 0, 1, 2 identical calls)
            assert result.proceed is True
        else:
            # Fourth call should trigger (history has 3 identical calls)
            assert result.proceed is False
            assert result.action == CircuitBreakerAction.KILL
            assert "loop" in result.reason.lower() or "identical" in result.reason.lower()


@pytest.mark.asyncio
async def test_tool_consecutive_limit(strict_circuit_breaker):
    """Same tool called consecutively should trigger suspension."""
    execution_id = uuid4()
    tool_name = "send_email"

    # Call same tool 4 times with different params (limit is 3 consecutive)
    # Recording happens after check, so need 3 in history before 4th triggers
    for i in range(4):
        result = await strict_circuit_breaker.check_before_tool_call(
            execution_id,
            tool_name,
            {"recipient": f"user{i}@example.com"}
        )
        if i < 3:
            # First 3 calls pass (history has 0, 1, 2 consecutive)
            assert result.proceed is True
        else:
            # Fourth consecutive call should trigger (3 in history >= limit of 3)
            assert result.proceed is False
            assert result.action == CircuitBreakerAction.SUSPEND_FOR_APPROVAL
            assert "consecutive" in result.reason.lower() or "loop" in result.reason.lower()


@pytest.mark.asyncio
async def test_different_tools_reset_counter(strict_circuit_breaker):
    """Different tools should reset the consecutive counter."""
    execution_id = uuid4()

    # Call tool A twice
    await strict_circuit_breaker.check_before_tool_call(
        execution_id, "tool_a", {"x": 1}
    )
    await strict_circuit_breaker.check_before_tool_call(
        execution_id, "tool_a", {"x": 2}
    )

    # Call different tool B
    await strict_circuit_breaker.check_before_tool_call(
        execution_id, "tool_b", {"y": 1}
    )

    # Call tool A again - counter should reset
    result = await strict_circuit_breaker.check_before_tool_call(
        execution_id, "tool_a", {"x": 3}
    )

    assert result.proceed is True


@pytest.mark.asyncio
async def test_total_tool_call_limit(strict_circuit_breaker):
    """Total tool calls should be limited."""
    execution_id = uuid4()

    # Call different tools up to the limit (10)
    for i in range(11):
        result = await strict_circuit_breaker.check_before_tool_call(
            execution_id,
            f"tool_{i}",  # Different tool each time
            {"index": i}
        )
        if i < 10:
            assert result.proceed is True
        else:
            assert result.proceed is False
            assert result.action == CircuitBreakerAction.SUSPEND_FOR_APPROVAL
            assert "limit reached" in result.reason.lower()


# =============================================================================
# LLM Call Limit Tests
# =============================================================================

@pytest.mark.asyncio
async def test_llm_call_limit(db_session):
    """LLM calls should be limited."""
    # Use config with high velocity limits but low LLM call limit
    config = CircuitBreakerConfig(
        token_velocity_per_minute=1_000_000,  # Very high
        cost_velocity_per_minute=1000.0,       # Very high
        total_llm_calls_per_execution=5,       # Low limit for testing
    )
    circuit_breaker = CircuitBreaker(db_session, config)
    execution_id = uuid4()

    # Make calls up to the limit (5)
    for i in range(6):
        # Record call first
        await circuit_breaker.record_llm_call(execution_id, tokens_used=100, cost=0.001)

        # Then check (LLM call count is already incremented)
        result = await circuit_breaker.check_before_llm_call(execution_id)

        if i < 4:
            # Calls 0-4: count is 1-5, limit is 5, so first 4 checks pass
            assert result.proceed is True
        else:
            # Call 5+: count exceeds limit
            assert result.proceed is False
            assert result.action == CircuitBreakerAction.SUSPEND_FOR_APPROVAL
            assert "limit" in result.reason.lower()


# =============================================================================
# Recursion Depth Tests
# =============================================================================

@pytest.mark.asyncio
async def test_recursion_depth_limit(strict_circuit_breaker):
    """Recursion depth should be limited."""
    execution_id = uuid4()

    # Set recursion depth beyond limit (3)
    await strict_circuit_breaker.record_recursion_depth(execution_id, depth=5)

    result = await strict_circuit_breaker.check_before_llm_call(execution_id)

    assert result.proceed is False
    assert result.action == CircuitBreakerAction.SUSPEND_FOR_APPROVAL
    assert "recursion" in result.reason.lower()


@pytest.mark.asyncio
async def test_normal_recursion_depth_proceeds(strict_circuit_breaker):
    """Normal recursion depth should proceed."""
    execution_id = uuid4()

    await strict_circuit_breaker.record_recursion_depth(execution_id, depth=2)

    result = await strict_circuit_breaker.check_before_llm_call(execution_id)

    assert result.proceed is True


# =============================================================================
# Batch Configuration Tests
# =============================================================================

def test_validate_batch_config_requires_admin():
    """Batch bypass requires ADMIN permission."""
    batch_config = BatchOperationConfig(
        bypass_circuit_breaker=True,
        audit_reason="Test"
    )

    # Without permission
    with pytest.raises(PermissionError):
        validate_batch_config(batch_config, {"USER", "EDITOR"})

    # With ADMIN permission
    validate_batch_config(batch_config, {"ADMIN"})

    # With specific bypass permission
    validate_batch_config(batch_config, {"CIRCUIT_BREAKER_BYPASS"})


def test_validate_batch_config_requires_reason():
    """Batch bypass requires audit reason."""
    batch_config = BatchOperationConfig(
        bypass_circuit_breaker=True,
        audit_reason=""  # Empty reason
    )

    with pytest.raises(ValueError):
        validate_batch_config(batch_config, {"ADMIN"})


def test_batch_config_without_bypass_needs_no_permission():
    """Batch config without bypass needs no special permission."""
    batch_config = BatchOperationConfig(
        bypass_circuit_breaker=False
    )

    # Should not raise
    validate_batch_config(batch_config, {"USER"})


# =============================================================================
# Metrics Tests
# =============================================================================

@pytest.mark.asyncio
async def test_metrics_accumulate(circuit_breaker):
    """Metrics should accumulate across calls."""
    execution_id = uuid4()

    # Record multiple calls
    await circuit_breaker.record_llm_call(execution_id, tokens_used=100, cost=0.01)
    await circuit_breaker.record_llm_call(execution_id, tokens_used=200, cost=0.02)
    await circuit_breaker.record_llm_call(execution_id, tokens_used=300, cost=0.03)

    metrics = await circuit_breaker._get_execution_metrics(execution_id)

    assert metrics.total_tokens == 600
    assert abs(metrics.total_cost - 0.06) < 0.0001
    assert metrics.llm_call_count == 3


@pytest.mark.asyncio
async def test_cache_cleared_on_completion(circuit_breaker):
    """Cache should be clearable after execution completes."""
    execution_id = uuid4()

    await circuit_breaker.record_llm_call(execution_id, tokens_used=100, cost=0.01)

    # Verify cached
    assert execution_id in circuit_breaker._metrics_cache

    # Clear cache
    circuit_breaker.clear_execution_cache(execution_id)

    # Verify cleared
    assert execution_id not in circuit_breaker._metrics_cache


# =============================================================================
# Result Serialization Tests
# =============================================================================

def test_result_to_dict():
    """CircuitBreakerResult should serialize to dict."""
    result = CircuitBreakerResult(
        proceed=False,
        action=CircuitBreakerAction.SUSPEND_FOR_APPROVAL,
        reason="Test reason",
        metrics={"test": 123}
    )

    d = result.to_dict()

    assert d["proceed"] is False
    assert d["action"] == "suspend_for_approval"
    assert d["reason"] == "Test reason"
    assert d["metrics"]["test"] == 123


# =============================================================================
# Edge Cases
# =============================================================================

@pytest.mark.asyncio
async def test_new_execution_has_zero_metrics(circuit_breaker):
    """New execution should start with zero metrics."""
    execution_id = uuid4()

    metrics = await circuit_breaker._get_execution_metrics(execution_id)

    assert metrics.total_tokens == 0
    assert metrics.total_cost == 0.0
    assert metrics.llm_call_count == 0
    assert metrics.tool_call_count == 0


@pytest.mark.asyncio
async def test_params_hash_consistency(circuit_breaker):
    """Same params should produce same hash."""
    params1 = {"a": 1, "b": 2, "c": {"nested": "value"}}
    params2 = {"c": {"nested": "value"}, "a": 1, "b": 2}  # Different order

    hash1 = circuit_breaker._hash_params(params1)
    hash2 = circuit_breaker._hash_params(params2)

    assert hash1 == hash2


@pytest.mark.asyncio
async def test_empty_tool_history(circuit_breaker):
    """Empty tool history should not cause errors."""
    execution_id = uuid4()

    history = await circuit_breaker._get_recent_tool_calls(execution_id)

    assert history == []


# =============================================================================
# Integration-style Tests
# =============================================================================

@pytest.mark.asyncio
async def test_full_execution_flow(db_session):
    """Test a realistic execution flow."""
    # Use reasonable limits for a normal flow test
    config = CircuitBreakerConfig(
        token_velocity_per_minute=50_000,  # Default production limit
        cost_velocity_per_minute=5.0,
        total_llm_calls_per_execution=50,
        total_tool_calls_per_execution=100,
    )
    circuit_breaker = CircuitBreaker(db_session, config)
    execution_id = uuid4()

    # Start execution
    result = await circuit_breaker.check_before_llm_call(execution_id)
    assert result.proceed is True

    # Record LLM call
    await circuit_breaker.record_llm_call(execution_id, tokens_used=500, cost=0.005)

    # Tool call
    result = await circuit_breaker.check_before_tool_call(
        execution_id, "search", {"query": "test"}
    )
    assert result.proceed is True

    # Another LLM call
    result = await circuit_breaker.check_before_llm_call(execution_id)
    assert result.proceed is True
    await circuit_breaker.record_llm_call(execution_id, tokens_used=500, cost=0.005)

    # Verify metrics accumulated
    metrics = await circuit_breaker._get_execution_metrics(execution_id)
    assert metrics.total_tokens == 1000
    assert metrics.llm_call_count == 2
    assert metrics.tool_call_count == 1

    # Cleanup
    circuit_breaker.clear_execution_cache(execution_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
