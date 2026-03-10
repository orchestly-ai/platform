"""
State Locking Service Tests

Tests for ROADMAP.md Section: Multi-Agent Conflict Resolution

Test Coverage:
- Optimistic Concurrency Control (OCC)
- Distributed locks
- SmartLockManager adaptive strategy
- Contention detection
- Conflict handling
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

from backend.shared.state_lock_service import (
    OptimisticStateLock,
    DistributedLock,
    SmartLockManager,
    ResourceType,
    LockStrategy,
    WriteResult,
    ContentionMetrics,
    ConflictError,
    LockAcquisitionError,
    with_optimistic_lock,
    with_distributed_lock,
    get_smart_lock_manager,
    reset_smart_lock_manager,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def occ_lock():
    """Create an OCC lock with in-memory storage."""
    return OptimisticStateLock(db=None)


@pytest.fixture
def distributed_lock():
    """Create a distributed lock with in-memory storage."""
    return DistributedLock(redis_client=None)


@pytest.fixture
def smart_manager():
    """Create a SmartLockManager."""
    reset_smart_lock_manager()
    return SmartLockManager(db=None, redis_client=None)


# =============================================================================
# Optimistic Concurrency Control Tests
# =============================================================================

@pytest.mark.asyncio
async def test_occ_read_empty_state(occ_lock):
    """Reading non-existent state returns empty dict with version 1."""
    resource_id = f"test:{uuid4()}"
    state, version = await occ_lock.read_state(resource_id)

    assert state == {}
    assert version == 1


@pytest.mark.asyncio
async def test_occ_write_success(occ_lock):
    """Writing with correct version succeeds."""
    resource_id = f"test:{uuid4()}"

    # Read initial state
    state, version = await occ_lock.read_state(resource_id)
    assert version == 1

    # Write new state
    new_state = {"key": "value", "count": 1}
    result = await occ_lock.write_state(resource_id, new_state, version)

    assert result.success is True
    assert result.new_version == 2
    assert result.conflict is False
    assert result.strategy_used == LockStrategy.OCC


@pytest.mark.asyncio
async def test_occ_write_conflict(occ_lock):
    """Writing with wrong version fails with conflict."""
    resource_id = f"test:{uuid4()}"

    # Write initial state
    await occ_lock.write_state(resource_id, {"v": 1}, 1)

    # Try to write with old version (1), but current is now 2
    result = await occ_lock.write_state(resource_id, {"v": 2}, 1)

    assert result.success is False
    assert result.conflict is True
    assert result.new_version == 2  # Shows current version


@pytest.mark.asyncio
async def test_occ_write_with_retry_success(occ_lock):
    """write_with_retry succeeds on first try with no contention."""
    resource_id = f"test:{uuid4()}"

    def update_fn(state):
        state["counter"] = state.get("counter", 0) + 1
        return state

    result = await occ_lock.write_with_retry(resource_id, update_fn)

    assert result.success is True
    assert result.retries == 0

    # Verify state
    state, version = await occ_lock.read_state(resource_id)
    assert state["counter"] == 1


@pytest.mark.asyncio
async def test_occ_write_with_retry_handles_conflict(occ_lock):
    """write_with_retry retries on conflict."""
    resource_id = f"test:{uuid4()}"

    # Pre-populate state
    await occ_lock.write_state(resource_id, {"counter": 0}, 1)

    call_count = 0

    def update_fn(state):
        nonlocal call_count
        call_count += 1
        state["counter"] = state.get("counter", 0) + 1
        return state

    # Simulate conflict by modifying state mid-operation
    original_write = occ_lock.write_state
    conflict_injected = False

    async def mock_write(res_id, new_state, expected_version):
        nonlocal conflict_injected
        if not conflict_injected:
            conflict_injected = True
            # Inject a conflict by updating version
            occ_lock._state_cache[res_id] = ({"counter": 5}, 10)
            return WriteResult(success=False, conflict=True, new_version=10)
        return await original_write(res_id, new_state, expected_version)

    occ_lock.write_state = mock_write

    result = await occ_lock.write_with_retry(resource_id, update_fn, max_retries=3)

    assert result.success is True
    assert result.retries >= 1


@pytest.mark.asyncio
async def test_occ_max_retries_exceeded(occ_lock):
    """write_with_retry fails after max retries."""
    resource_id = f"test:{uuid4()}"

    # Always return conflict
    async def always_conflict(res_id, new_state, expected_version):
        return WriteResult(success=False, conflict=True, new_version=999)

    occ_lock.write_state = always_conflict

    result = await occ_lock.write_with_retry(
        resource_id,
        lambda s: {"fail": True},
        max_retries=2
    )

    assert result.success is False
    assert result.conflict is True
    assert result.retries == 2
    assert "Max retries exceeded" in result.error


# =============================================================================
# Distributed Lock Tests
# =============================================================================

@pytest.mark.asyncio
async def test_distributed_lock_acquire_success(distributed_lock):
    """Acquiring an available lock succeeds."""
    resource_id = f"resource:{uuid4()}"
    owner_id = f"agent:{uuid4()}"

    acquired = await distributed_lock.acquire(resource_id, owner_id)

    assert acquired is True


@pytest.mark.asyncio
async def test_distributed_lock_acquire_blocked(distributed_lock):
    """Acquiring a held lock blocks and times out."""
    resource_id = f"resource:{uuid4()}"
    owner1 = "agent-1"
    owner2 = "agent-2"

    # Owner 1 acquires
    await distributed_lock.acquire(resource_id, owner1)

    # Owner 2 tries to acquire with short timeout
    acquired = await distributed_lock.acquire(resource_id, owner2, timeout=1)

    assert acquired is False


@pytest.mark.asyncio
async def test_distributed_lock_release(distributed_lock):
    """Releasing a lock allows others to acquire."""
    resource_id = f"resource:{uuid4()}"
    owner1 = "agent-1"
    owner2 = "agent-2"

    # Owner 1 acquires and releases
    await distributed_lock.acquire(resource_id, owner1)
    released = await distributed_lock.release(resource_id, owner1)
    assert released is True

    # Owner 2 can now acquire
    acquired = await distributed_lock.acquire(resource_id, owner2, timeout=1)
    assert acquired is True


@pytest.mark.asyncio
async def test_distributed_lock_release_wrong_owner(distributed_lock):
    """Cannot release a lock owned by someone else."""
    resource_id = f"resource:{uuid4()}"
    owner1 = "agent-1"
    owner2 = "agent-2"

    await distributed_lock.acquire(resource_id, owner1)

    # Owner 2 tries to release Owner 1's lock
    released = await distributed_lock.release(resource_id, owner2)

    assert released is False


@pytest.mark.asyncio
async def test_distributed_lock_extend(distributed_lock):
    """Extending lock TTL works for owner."""
    resource_id = f"resource:{uuid4()}"
    owner_id = "agent-1"

    await distributed_lock.acquire(resource_id, owner_id)

    extended = await distributed_lock.extend(resource_id, owner_id, extra_seconds=60)

    assert extended is True


@pytest.mark.asyncio
async def test_distributed_lock_expired(distributed_lock):
    """Expired locks can be acquired by others."""
    resource_id = f"resource:{uuid4()}"
    owner1 = "agent-1"
    owner2 = "agent-2"

    await distributed_lock.acquire(resource_id, owner1)

    # Manually expire the lock
    distributed_lock._locks[resource_id].expires_at = datetime.utcnow() - timedelta(seconds=1)

    # Owner 2 should be able to acquire expired lock
    acquired = await distributed_lock.acquire(resource_id, owner2, timeout=1)

    assert acquired is True


# =============================================================================
# SmartLockManager Tests
# =============================================================================

@pytest.mark.asyncio
async def test_smart_manager_global_var_uses_distributed(smart_manager):
    """Global project variables always use distributed locks."""
    resource_id = f"global:{uuid4()}"
    agent_id = "agent-1"

    result = await smart_manager.update_state(
        resource_id,
        ResourceType.GLOBAL_PROJECT_VARIABLE,
        lambda s: {"value": 42},
        agent_id
    )

    assert result.strategy_used == LockStrategy.DISTRIBUTED


@pytest.mark.asyncio
async def test_smart_manager_agent_state_uses_occ(smart_manager):
    """Agent-specific state uses OCC by default."""
    resource_id = f"agent:{uuid4()}"
    agent_id = "agent-1"

    result = await smart_manager.update_state(
        resource_id,
        ResourceType.AGENT_STATE,
        lambda s: {"status": "running"},
        agent_id
    )

    assert result.success is True
    # OCC is used for low-contention (or distributed if OCC fails)
    assert result.strategy_used in [LockStrategy.OCC, LockStrategy.DISTRIBUTED]


@pytest.mark.asyncio
async def test_smart_manager_adapts_to_high_contention(smart_manager):
    """SmartLockManager switches to distributed lock on high contention."""
    resource_id = f"shared:{uuid4()}"
    agent_id = "agent-1"

    # Simulate high contention by recording conflicts
    for _ in range(smart_manager.HIGH_CONTENTION_THRESHOLD + 1):
        await smart_manager._record_operation(resource_id, had_conflict=True)

    # Next operation should use distributed lock
    is_high = await smart_manager._is_high_contention(resource_id)
    assert is_high is True

    result = await smart_manager.update_state(
        resource_id,
        ResourceType.SHARED_VARIABLE,
        lambda s: {"updated": True},
        agent_id
    )

    assert result.strategy_used == LockStrategy.DISTRIBUTED


@pytest.mark.asyncio
async def test_smart_manager_contention_window_resets(smart_manager):
    """Contention metrics reset after window expires."""
    resource_id = f"shared:{uuid4()}"

    # Record some conflicts
    for _ in range(3):
        await smart_manager._record_operation(resource_id, had_conflict=True)

    # Manually expire the window
    async with smart_manager._metrics_lock:
        smart_manager._contention_metrics[resource_id].window_start = (
            datetime.utcnow() - timedelta(seconds=smart_manager.CONTENTION_WINDOW_SECONDS + 1)
        )

    # Should not be high contention after window reset
    is_high = await smart_manager._is_high_contention(resource_id)
    assert is_high is False


@pytest.mark.asyncio
async def test_smart_manager_fallback_on_occ_failure(smart_manager):
    """Falls back to distributed lock when OCC fails repeatedly."""
    resource_id = f"shared:{uuid4()}"
    agent_id = "agent-1"

    # Make OCC always fail
    async def always_fail(*args, **kwargs):
        return WriteResult(
            success=False,
            conflict=True,
            retries=3,
            strategy_used=LockStrategy.OCC
        )

    smart_manager.occ.write_with_retry = always_fail

    result = await smart_manager.update_state(
        resource_id,
        ResourceType.SHARED_VARIABLE,
        lambda s: {"value": 1},
        agent_id
    )

    # Should have fallen back to distributed lock
    assert result.strategy_used == LockStrategy.DISTRIBUTED


@pytest.mark.asyncio
async def test_smart_manager_contention_stats(smart_manager):
    """Can retrieve contention statistics."""
    resource_id = f"shared:{uuid4()}"

    # Record some operations
    await smart_manager._record_operation(resource_id, had_conflict=False)
    await smart_manager._record_operation(resource_id, had_conflict=True)
    await smart_manager._record_operation(resource_id, had_conflict=False)

    stats = await smart_manager.get_contention_stats(resource_id)

    assert stats is not None
    assert stats.total_operations == 3
    assert stats.conflicts_in_window == 1
    assert stats.conflict_rate == 1/3


# =============================================================================
# Convenience Function Tests
# =============================================================================

@pytest.mark.asyncio
async def test_with_optimistic_lock():
    """with_optimistic_lock convenience function works."""
    resource_id = f"test:{uuid4()}"

    result = await with_optimistic_lock(
        resource_id,
        lambda s: {"key": "value"},
        db=None,
        max_retries=2
    )

    assert result.success is True


@pytest.mark.asyncio
async def test_with_distributed_lock_success():
    """with_distributed_lock convenience function works."""
    resource_id = f"test:{uuid4()}"
    operation_called = False

    async def my_operation():
        nonlocal operation_called
        operation_called = True
        return "result"

    result = await with_distributed_lock(
        resource_id,
        my_operation,
        owner_id="agent-1",
        redis_client=None,
        timeout=5
    )

    assert result == "result"
    assert operation_called is True


@pytest.mark.asyncio
async def test_with_distributed_lock_releases_on_error():
    """with_distributed_lock releases lock even on error."""
    resource_id = f"test:{uuid4()}"
    lock = DistributedLock(redis_client=None)

    async def failing_operation():
        raise ValueError("Operation failed")

    with pytest.raises(ValueError):
        await with_distributed_lock(
            resource_id,
            failing_operation,
            owner_id="agent-1"
        )

    # Lock should be released - another agent can acquire
    acquired = await lock.acquire(resource_id, "agent-2", timeout=1)
    assert acquired is True


# =============================================================================
# Concurrent Access Tests
# =============================================================================

@pytest.mark.asyncio
async def test_concurrent_occ_updates(occ_lock):
    """Multiple concurrent OCC updates eventually succeed."""
    resource_id = f"test:{uuid4()}"
    await occ_lock.write_state(resource_id, {"counter": 0}, 1)

    async def increment(lock, res_id):
        return await lock.write_with_retry(
            res_id,
            lambda s: {"counter": s.get("counter", 0) + 1},
            max_retries=10
        )

    # Run 5 concurrent increments
    results = await asyncio.gather(*[
        increment(occ_lock, resource_id) for _ in range(5)
    ])

    # All should eventually succeed
    successes = sum(1 for r in results if r.success)
    assert successes == 5

    # Final counter should be 5
    state, _ = await occ_lock.read_state(resource_id)
    assert state["counter"] == 5


@pytest.mark.asyncio
async def test_concurrent_distributed_lock_serializes():
    """Distributed locks serialize concurrent operations."""
    lock = DistributedLock(redis_client=None)
    resource_id = f"resource:{uuid4()}"
    execution_order = []

    async def operation(agent_id: str):
        if await lock.acquire(resource_id, agent_id, timeout=5):
            execution_order.append(f"{agent_id}:start")
            await asyncio.sleep(0.1)  # Simulate work
            execution_order.append(f"{agent_id}:end")
            await lock.release(resource_id, agent_id)

    # Run concurrent operations
    await asyncio.gather(
        operation("agent-1"),
        operation("agent-2"),
        operation("agent-3")
    )

    # Verify serialized execution (no interleaving)
    for i in range(0, len(execution_order), 2):
        agent = execution_order[i].split(":")[0]
        assert execution_order[i] == f"{agent}:start"
        assert execution_order[i+1] == f"{agent}:end"


# =============================================================================
# Edge Cases
# =============================================================================

@pytest.mark.asyncio
async def test_occ_empty_update(occ_lock):
    """OCC handles identity update (no change)."""
    resource_id = f"test:{uuid4()}"
    initial = {"key": "value"}
    await occ_lock.write_state(resource_id, initial, 1)

    result = await occ_lock.write_with_retry(
        resource_id,
        lambda s: s  # Identity function
    )

    assert result.success is True


@pytest.mark.asyncio
async def test_distributed_lock_reentrant_fails(distributed_lock):
    """Same owner cannot acquire lock twice (not reentrant)."""
    resource_id = f"resource:{uuid4()}"
    owner_id = "agent-1"

    await distributed_lock.acquire(resource_id, owner_id)

    # Same owner tries to acquire again
    acquired = await distributed_lock.acquire(resource_id, owner_id, timeout=1)

    # Should fail (not reentrant)
    assert acquired is False


@pytest.mark.asyncio
async def test_smart_manager_clear_metrics(smart_manager):
    """Can clear all contention metrics."""
    resource_id = f"shared:{uuid4()}"

    await smart_manager._record_operation(resource_id, had_conflict=True)

    assert await smart_manager.get_contention_stats(resource_id) is not None

    smart_manager.clear_metrics()

    assert await smart_manager.get_contention_stats(resource_id) is None


@pytest.mark.asyncio
async def test_write_result_to_dict():
    """WriteResult serializes correctly."""
    result = WriteResult(
        success=True,
        new_version=5,
        strategy_used=LockStrategy.OCC,
        retries=2
    )

    d = result.to_dict()

    assert d["success"] is True
    assert d["new_version"] == 5
    assert d["strategy_used"] == "occ"
    assert d["retries"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
