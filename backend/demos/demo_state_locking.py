#!/usr/bin/env python3
"""
Demo: State Locking - OCC + Distributed Locks

Shows the state locking mechanisms from ROADMAP.md:
1. Optimistic Concurrency Control (OCC) - for low-contention resources
2. Distributed Locks - for high-contention resources
3. SmartLockManager - adaptive strategy based on contention

Reference: ROADMAP.md Section "Multi-Agent Conflict Resolution (State Locking)"

Key Design Decisions:
- OCC = "optimistic" - assume conflicts are rare, retry if they happen
- Distributed Lock = "pessimistic" - acquire exclusive access before modifying
- Global Project Variables = ALWAYS use Distributed Lock (high contention by definition)
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

from backend.shared.state_lock_service import (
    OptimisticStateLock,
    DistributedLock,
    SmartLockManager,
    ResourceType,
    LockStrategy,
    with_optimistic_lock,
    with_distributed_lock,
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


async def demo_occ_basic():
    """Demo 1: Basic OCC operations."""
    print_header("Demo 1: Basic Optimistic Concurrency Control (OCC)")
    print("\nOCC is ideal for low-contention resources where conflicts are rare.")
    print("It's fast because it doesn't acquire locks - just checks versions.\n")

    occ = OptimisticStateLock(db=None)
    resource_id = f"agent-state:{uuid4()}"

    # Read initial state
    print("1. Reading initial state...")
    state, version = await occ.read_state(resource_id)
    print(f"   State: {state}, Version: {version}")

    # Write new state
    print("\n2. Writing new state with version check...")
    new_state = {"agent_id": "agent-123", "status": "running", "progress": 0.5}
    result = await occ.write_state(resource_id, new_state, version)
    print_result("Write result", result)

    # Read updated state
    print("\n3. Reading updated state...")
    state, version = await occ.read_state(resource_id)
    print(f"   State: {state}")
    print(f"   Version: {version}")

    # Simulate conflict
    print("\n4. Simulating version conflict...")
    print("   (Trying to write with old version 1, but current is 2)")
    result = await occ.write_state(resource_id, {"conflict": True}, expected_version=1)
    print_result("Write result (expected failure)", result)

    print("\n[OK] OCC prevents data corruption by detecting version conflicts!")


async def demo_occ_retry():
    """Demo 2: OCC with automatic retry."""
    print_header("Demo 2: OCC with Automatic Retry")
    print("\nwrite_with_retry handles conflicts automatically with exponential backoff.\n")

    occ = OptimisticStateLock(db=None)
    resource_id = f"counter:{uuid4()}"

    # Initialize counter
    await occ.write_state(resource_id, {"counter": 0}, 1)

    print("1. Incrementing counter 5 times with write_with_retry...")
    for i in range(5):
        result = await occ.write_with_retry(
            resource_id,
            lambda s: {"counter": s.get("counter", 0) + 1},
            max_retries=3
        )
        print(f"   Increment {i+1}: success={result.success}, retries={result.retries}")

    state, version = await occ.read_state(resource_id)
    print(f"\n2. Final state: counter={state['counter']}, version={version}")

    print("\n[OK] write_with_retry handles transient conflicts gracefully!")


async def demo_distributed_lock():
    """Demo 3: Distributed locking for high-contention resources."""
    print_header("Demo 3: Distributed Locks")
    print("\nDistributed locks are required for:")
    print("  - Global project variables")
    print("  - High-contention shared resources")
    print("  - Non-idempotent operations\n")

    lock = DistributedLock(redis_client=None)
    resource_id = "global:project-counter"

    print("1. Agent-1 acquiring lock...")
    acquired = await lock.acquire(resource_id, "agent-1", timeout=5)
    print(f"   Lock acquired: {acquired}")

    print("\n2. Agent-2 trying to acquire same lock (should fail after timeout)...")
    acquired2 = await lock.acquire(resource_id, "agent-2", timeout=1)
    print(f"   Lock acquired: {acquired2} (expected False)")

    print("\n3. Agent-1 releasing lock...")
    released = await lock.release(resource_id, "agent-1")
    print(f"   Lock released: {released}")

    print("\n4. Agent-2 trying again (should succeed now)...")
    acquired3 = await lock.acquire(resource_id, "agent-2", timeout=1)
    print(f"   Lock acquired: {acquired3}")

    await lock.release(resource_id, "agent-2")

    print("\n[OK] Distributed locks serialize access to shared resources!")


async def demo_smart_lock_manager():
    """Demo 4: SmartLockManager adaptive strategy."""
    print_header("Demo 4: SmartLockManager - Adaptive Strategy")
    print("\nSmartLockManager automatically chooses the best strategy:")
    print("  - OCC for low-contention resources")
    print("  - Distributed lock for high-contention or global variables\n")

    manager = SmartLockManager(db=None, redis_client=None)

    # 1. Agent-specific state (uses OCC)
    print("1. Updating agent-specific state (should use OCC)...")
    result = await manager.update_state(
        f"agent:{uuid4()}",
        ResourceType.AGENT_STATE,
        lambda s: {"status": "running", "updated_at": str(datetime.utcnow())},
        "agent-1"
    )
    print(f"   Strategy used: {result.strategy_used.value}")
    print(f"   Success: {result.success}")

    # 2. Global project variable (always uses distributed lock)
    print("\n2. Updating global project variable (should use Distributed Lock)...")
    result = await manager.update_state(
        "global:project-settings",
        ResourceType.GLOBAL_PROJECT_VARIABLE,
        lambda s: {"theme": "dark", "version": 2},
        "agent-1"
    )
    print(f"   Strategy used: {result.strategy_used.value}")
    print(f"   Success: {result.success}")

    # 3. Simulate high contention
    print("\n3. Simulating high contention on shared resource...")
    shared_resource = f"shared:{uuid4()}"

    print(f"   Recording {manager.HIGH_CONTENTION_THRESHOLD + 1} conflicts...")
    for _ in range(manager.HIGH_CONTENTION_THRESHOLD + 1):
        await manager._record_operation(shared_resource, had_conflict=True)

    stats = await manager.get_contention_stats(shared_resource)
    print(f"   Conflicts in window: {stats.conflicts_in_window}")
    print(f"   Contention rate: {stats.conflict_rate:.0%}")

    print("\n4. Updating high-contention resource (should use Distributed Lock)...")
    result = await manager.update_state(
        shared_resource,
        ResourceType.SHARED_VARIABLE,
        lambda s: {"high_contention": True},
        "agent-1"
    )
    print(f"   Strategy used: {result.strategy_used.value}")
    print(f"   Success: {result.success}")

    print("\n[OK] SmartLockManager adapts to prevent thundering herd!")


async def demo_concurrent_agents():
    """Demo 5: Multiple agents updating shared state."""
    print_header("Demo 5: Concurrent Agent Updates")
    print("\nSimulating 5 agents updating a shared counter concurrently.\n")

    occ = OptimisticStateLock(db=None)
    resource_id = f"shared-counter:{uuid4()}"

    # Initialize
    await occ.write_state(resource_id, {"counter": 0}, 1)

    async def agent_increment(agent_id: str):
        """Each agent increments the counter."""
        result = await occ.write_with_retry(
            resource_id,
            lambda s: {"counter": s.get("counter", 0) + 1},
            max_retries=10
        )
        return agent_id, result

    print("1. Launching 5 concurrent agent updates...")
    results = await asyncio.gather(*[
        agent_increment(f"agent-{i}") for i in range(5)
    ])

    print("\n2. Results:")
    total_retries = 0
    for agent_id, result in results:
        print(f"   {agent_id}: success={result.success}, retries={result.retries}")
        total_retries += result.retries

    state, version = await occ.read_state(resource_id)
    print(f"\n3. Final counter value: {state['counter']} (expected: 5)")
    print(f"   Total retries across all agents: {total_retries}")
    print(f"   Final version: {version}")

    assert state["counter"] == 5, "Counter should be exactly 5!"
    print("\n[OK] All concurrent updates succeeded with conflict resolution!")


async def demo_lock_use_cases():
    """Demo 6: When to use OCC vs Distributed Locks."""
    print_header("Demo 6: Strategy Selection Guide")
    print("\nFrom ROADMAP.md - When to Use Each Strategy:\n")

    print("┌─────────────────────────────────┬─────────┬─────────────────────┐")
    print("│ Scenario                        │ Use OCC │ Use Distributed Lock│")
    print("├─────────────────────────────────┼─────────┼─────────────────────┤")
    print("│ Agent-specific state            │   ✅    │         ❌          │")
    print("│ Low-contention shared state     │   ✅    │         ❌          │")
    print("│ Short-running updates           │   ✅    │         ❌          │")
    print("│ Idempotent operations           │   ✅    │         ❌          │")
    print("│ Global project variables        │   ❌    │         ✅          │")
    print("│ High-contention shared state    │   ❌    │         ✅          │")
    print("│ Long-running updates            │   ❌    │         ✅          │")
    print("│ Non-idempotent operations       │   ❌    │         ✅          │")
    print("└─────────────────────────────────┴─────────┴─────────────────────┘")

    print("\nRule of Thumb:")
    print("  - OCC = 'optimistic' - assume conflicts are rare, retry if they happen")
    print("  - Distributed Lock = 'pessimistic' - acquire exclusive access first")
    print("  - Global Project Variables = ALWAYS use Distributed Lock")

    print("\n" + "-" * 60)
    print("SmartLockManager automates this decision!")
    print("It tracks contention rates and switches strategy dynamically.")
    print("-" * 60)


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  STATE LOCKING DEMO")
    print("  OCC + Distributed Locks for Multi-Agent Conflict Resolution")
    print("=" * 60)
    print("\nReference: ROADMAP.md Section 'Multi-Agent Conflict Resolution'")

    try:
        await demo_occ_basic()
        await demo_occ_retry()
        await demo_distributed_lock()
        await demo_smart_lock_manager()
        await demo_concurrent_agents()
        await demo_lock_use_cases()

        print("\n" + "=" * 60)
        print("  ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nKey Takeaways:")
        print("  1. OCC is fast and efficient for low-contention scenarios")
        print("  2. Distributed locks prevent thundering herd on global variables")
        print("  3. SmartLockManager adapts automatically based on contention")
        print("  4. Both strategies ensure data consistency in multi-agent systems")
        print()

    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
