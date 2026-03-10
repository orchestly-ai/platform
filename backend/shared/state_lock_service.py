"""
State Locking Service - OCC + Distributed Locks

Implements ROADMAP.md Section: Multi-Agent Conflict Resolution (State Locking)

Features:
- Optimistic Concurrency Control (OCC) for low-contention resources
- Distributed Redis locks for high-contention resources
- SmartLockManager: Adaptive strategy based on conflict rate
- Thundering herd prevention for global variables

Key Design Decisions (from ROADMAP.md):
- OCC = "optimistic" - assume conflicts are rare, retry if they happen
- Distributed Lock = "pessimistic" - acquire exclusive access before modifying
- Global Project Variables = ALWAYS use Distributed Lock (high contention by definition)
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from uuid import UUID
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources with different locking strategies."""
    AGENT_STATE = "agent_state"           # OCC preferred
    WORKFLOW_EXECUTION = "workflow_execution"  # OCC preferred
    SHARED_VARIABLE = "shared_variable"   # Depends on contention
    GLOBAL_PROJECT_VARIABLE = "global_project_variable"  # Always distributed lock
    INTEGRATION_STATE = "integration_state"  # OCC preferred


class LockStrategy(Enum):
    """Locking strategy used."""
    OCC = "occ"
    DISTRIBUTED = "distributed"


@dataclass
class WriteResult:
    """Result of a state write operation."""
    success: bool
    new_version: Optional[int] = None
    conflict: bool = False
    strategy_used: LockStrategy = LockStrategy.OCC
    retries: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "new_version": self.new_version,
            "conflict": self.conflict,
            "strategy_used": self.strategy_used.value,
            "retries": self.retries,
            "error": self.error
        }


@dataclass
class LockInfo:
    """Information about an acquired lock."""
    resource_id: str
    owner_id: str
    acquired_at: datetime
    expires_at: datetime
    strategy: LockStrategy

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


@dataclass
class ContentionMetrics:
    """Track conflict rates for adaptive strategy selection."""
    resource_id: str
    conflicts_in_window: int = 0
    total_operations: int = 0
    window_start: datetime = field(default_factory=datetime.utcnow)
    last_conflict: Optional[datetime] = None

    @property
    def conflict_rate(self) -> float:
        if self.total_operations == 0:
            return 0.0
        return self.conflicts_in_window / self.total_operations


class ConflictError(Exception):
    """Raised when optimistic lock detects a conflict."""
    def __init__(self, message: str, expected_version: int, actual_version: int):
        super().__init__(message)
        self.expected_version = expected_version
        self.actual_version = actual_version


class LockAcquisitionError(Exception):
    """Raised when unable to acquire a distributed lock."""
    def __init__(self, resource_id: str, timeout: int):
        super().__init__(f"Failed to acquire lock for {resource_id} within {timeout}s")
        self.resource_id = resource_id
        self.timeout = timeout


class OptimisticStateLock:
    """
    Optimistic Concurrency Control for agent-specific state.

    Use when:
    - Agent-specific state (low contention)
    - Low-contention shared state
    - Short-running updates
    - Idempotent operations
    """

    def __init__(self, db=None):
        self.db = db
        # In-memory state cache for demo/testing (production uses DB)
        self._state_cache: Dict[str, Tuple[Dict, int]] = {}

    async def read_state(self, resource_id: str) -> Tuple[Dict, int]:
        """
        Read state and its version.

        Returns:
            Tuple of (state_dict, version)
        """
        if self.db:
            try:
                from sqlalchemy import text
                result = await self.db.execute(
                    text("""
                        SELECT execution_state, state_version
                        FROM workflow_executions
                        WHERE execution_id = :resource_id
                    """),
                    {"resource_id": resource_id}
                )
                row = result.fetchone()
                if row:
                    state = row[0] if isinstance(row[0], dict) else json.loads(row[0] or '{}')
                    return state, row[1] or 1
            except Exception as e:
                logger.warning(f"DB read failed, using cache: {e}")

        # Fallback to in-memory cache
        if resource_id in self._state_cache:
            return self._state_cache[resource_id]
        return {}, 1

    async def write_state(
        self,
        resource_id: str,
        new_state: Dict,
        expected_version: int
    ) -> WriteResult:
        """
        Write state with optimistic concurrency control.

        Args:
            resource_id: Resource identifier
            new_state: New state to write
            expected_version: Version we expect (from read_state)

        Returns:
            WriteResult with success/conflict status
        """
        if self.db:
            try:
                from sqlalchemy import text
                result = await self.db.execute(
                    text("""
                        UPDATE workflow_executions SET
                            execution_state = :new_state,
                            state_version = state_version + 1,
                            updated_at = :now
                        WHERE execution_id = :resource_id
                        AND state_version = :expected_version
                        RETURNING state_version
                    """),
                    {
                        "resource_id": resource_id,
                        "new_state": json.dumps(new_state),
                        "expected_version": expected_version,
                        "now": datetime.utcnow()
                    }
                )
                row = result.fetchone()
                if row:
                    await self.db.commit()
                    return WriteResult(
                        success=True,
                        new_version=row[0],
                        strategy_used=LockStrategy.OCC
                    )
                else:
                    # Conflict detected
                    current_state, current_version = await self.read_state(resource_id)
                    return WriteResult(
                        success=False,
                        conflict=True,
                        new_version=current_version,
                        strategy_used=LockStrategy.OCC,
                        error=f"Version conflict: expected {expected_version}, got {current_version}"
                    )
            except Exception as e:
                logger.warning(f"DB write failed, using cache: {e}")

        # Fallback to in-memory cache
        current_state, current_version = await self.read_state(resource_id)

        if current_version != expected_version:
            return WriteResult(
                success=False,
                conflict=True,
                new_version=current_version,
                strategy_used=LockStrategy.OCC,
                error=f"Version conflict: expected {expected_version}, got {current_version}"
            )

        new_version = current_version + 1
        self._state_cache[resource_id] = (new_state, new_version)

        logger.debug(f"OCC write success: {resource_id} v{expected_version} -> v{new_version}")
        return WriteResult(
            success=True,
            new_version=new_version,
            strategy_used=LockStrategy.OCC
        )

    async def write_with_retry(
        self,
        resource_id: str,
        update_fn: Callable[[Dict], Dict],
        max_retries: int = 3,
        backoff_base: float = 0.1
    ) -> WriteResult:
        """
        Read-modify-write with automatic retry on conflict.

        Args:
            resource_id: Resource identifier
            update_fn: Function that takes current state and returns new state
            max_retries: Maximum number of retries on conflict
            backoff_base: Base delay for exponential backoff

        Returns:
            WriteResult with retry count
        """
        retries = 0
        last_error = None

        while retries <= max_retries:
            current_state, version = await self.read_state(resource_id)
            new_state = update_fn(current_state)

            result = await self.write_state(resource_id, new_state, version)
            result.retries = retries

            if result.success:
                return result

            if result.conflict:
                retries += 1
                last_error = result.error
                if retries <= max_retries:
                    # Exponential backoff with jitter
                    delay = backoff_base * (2 ** retries) + (time.time() % 0.1)
                    logger.debug(f"OCC conflict on {resource_id}, retry {retries}/{max_retries} after {delay:.2f}s")
                    await asyncio.sleep(delay)
            else:
                # Non-conflict error
                return result

        return WriteResult(
            success=False,
            conflict=True,
            retries=max_retries,  # Return the actual retry count, not incremented counter
            strategy_used=LockStrategy.OCC,
            error=f"Max retries exceeded ({max_retries}). Last error: {last_error}"
        )


class DistributedLock:
    """
    Redis-based distributed locks for high-contention resources.

    Use when:
    - Global project variables
    - High-contention shared state (>5 conflicts in 10s)
    - Long-running updates
    - Non-idempotent operations
    """

    LOCK_TTL_SECONDS = 30
    DEFAULT_TIMEOUT = 10

    def __init__(self, redis_client=None):
        self.redis = redis_client
        # In-memory lock storage for demo/testing
        self._locks: Dict[str, LockInfo] = {}
        # Lazy initialization of asyncio.Lock for Python 3.9 compatibility
        self._lock_mutex: Optional[asyncio.Lock] = None

    @property
    def lock_mutex(self) -> asyncio.Lock:
        """Lazily initialize the asyncio.Lock for Python 3.9 compatibility."""
        if self._lock_mutex is None:
            self._lock_mutex = asyncio.Lock()
        return self._lock_mutex

    async def acquire(
        self,
        resource_id: str,
        owner_id: str,
        timeout: int = None
    ) -> bool:
        """
        Acquire a distributed lock.

        Args:
            resource_id: Resource to lock
            owner_id: Unique identifier for lock owner (agent_id)
            timeout: Seconds to wait for lock (default: 10)

        Returns:
            True if lock acquired, False if timeout
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        lock_key = f"lock:{resource_id}"
        end_time = time.time() + timeout

        if self.redis:
            while time.time() < end_time:
                try:
                    acquired = await self.redis.set(
                        lock_key,
                        owner_id,
                        nx=True,  # Only set if not exists
                        ex=self.LOCK_TTL_SECONDS
                    )
                    if acquired:
                        logger.debug(f"Distributed lock acquired: {resource_id} by {owner_id}")
                        return True
                except Exception as e:
                    logger.warning(f"Redis lock error: {e}")

                await asyncio.sleep(0.1)
            return False

        # Fallback to in-memory locks
        while time.time() < end_time:
            async with self.lock_mutex:
                # Check if existing lock is expired
                if resource_id in self._locks:
                    existing = self._locks[resource_id]
                    if existing.is_expired():
                        del self._locks[resource_id]

                # Try to acquire
                if resource_id not in self._locks:
                    self._locks[resource_id] = LockInfo(
                        resource_id=resource_id,
                        owner_id=owner_id,
                        acquired_at=datetime.utcnow(),
                        expires_at=datetime.utcnow() + timedelta(seconds=self.LOCK_TTL_SECONDS),
                        strategy=LockStrategy.DISTRIBUTED
                    )
                    logger.debug(f"In-memory lock acquired: {resource_id} by {owner_id}")
                    return True

            await asyncio.sleep(0.1)

        logger.warning(f"Lock acquisition timeout: {resource_id} by {owner_id}")
        return False

    async def release(self, resource_id: str, owner_id: str) -> bool:
        """
        Release a distributed lock (only if we own it).

        Args:
            resource_id: Resource to unlock
            owner_id: Lock owner (must match acquire)

        Returns:
            True if released, False if not owner
        """
        lock_key = f"lock:{resource_id}"

        if self.redis:
            # Lua script for atomic check-and-delete
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            end
            return 0
            """
            try:
                result = await self.redis.eval(script, 1, lock_key, owner_id)
                released = result == 1
                if released:
                    logger.debug(f"Distributed lock released: {resource_id} by {owner_id}")
                return released
            except Exception as e:
                logger.warning(f"Redis release error: {e}")
                return False

        # Fallback to in-memory locks
        async with self.lock_mutex:
            if resource_id in self._locks:
                if self._locks[resource_id].owner_id == owner_id:
                    del self._locks[resource_id]
                    logger.debug(f"In-memory lock released: {resource_id} by {owner_id}")
                    return True
        return False

    async def extend(self, resource_id: str, owner_id: str, extra_seconds: int = 30) -> bool:
        """Extend lock TTL (for long-running operations)."""
        lock_key = f"lock:{resource_id}"

        if self.redis:
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            end
            return 0
            """
            try:
                result = await self.redis.eval(
                    script, 1, lock_key, owner_id, self.LOCK_TTL_SECONDS + extra_seconds
                )
                return result == 1
            except Exception as e:
                logger.warning(f"Redis extend error: {e}")
                return False

        # Fallback to in-memory
        async with self.lock_mutex:
            if resource_id in self._locks:
                if self._locks[resource_id].owner_id == owner_id:
                    self._locks[resource_id].expires_at += timedelta(seconds=extra_seconds)
                    return True
        return False


class SmartLockManager:
    """
    Adaptive locking strategy manager.

    Chooses between OCC and Distributed Lock based on:
    - Resource type (global vars always use distributed)
    - Contention history (>5 conflicts in 10s → switch to distributed)

    From ROADMAP.md:
    "If 50 agents all try to update a single 'Global Project Variable,'
    OCC's write_with_retry will cause a massive CPU spike and database
    contention as all 50 agents retry simultaneously."
    """

    HIGH_CONTENTION_THRESHOLD = 5  # conflicts in window
    CONTENTION_WINDOW_SECONDS = 10
    OCC_MAX_RETRIES = 3

    def __init__(self, db=None, redis_client=None):
        self.occ = OptimisticStateLock(db)
        self.distributed = DistributedLock(redis_client)
        self._contention_metrics: Dict[str, ContentionMetrics] = {}
        # Lazy initialization of asyncio.Lock for Python 3.9 compatibility
        self._metrics_lock: Optional[asyncio.Lock] = None

    @property
    def metrics_lock(self) -> asyncio.Lock:
        """Lazily initialize the asyncio.Lock for Python 3.9 compatibility."""
        if self._metrics_lock is None:
            self._metrics_lock = asyncio.Lock()
        return self._metrics_lock

    async def update_state(
        self,
        resource_id: str,
        resource_type: ResourceType,
        update_fn: Callable[[Dict], Dict],
        agent_id: str
    ) -> WriteResult:
        """
        Update state using the appropriate locking strategy.

        Args:
            resource_id: Resource identifier
            resource_type: Type of resource (determines default strategy)
            update_fn: Function that takes current state and returns new state
            agent_id: Agent performing the update

        Returns:
            WriteResult with strategy used and retry count
        """
        # Rule: Global variables ALWAYS use distributed lock
        if resource_type == ResourceType.GLOBAL_PROJECT_VARIABLE:
            logger.debug(f"Using distributed lock for global variable: {resource_id}")
            return await self._update_with_distributed_lock(
                resource_id, update_fn, agent_id
            )

        # Check contention history
        is_high_contention = await self._is_high_contention(resource_id)

        if is_high_contention:
            logger.info(f"High contention detected for {resource_id}, using distributed lock")
            return await self._update_with_distributed_lock(
                resource_id, update_fn, agent_id
            )

        # Default: use OCC for low-contention resources
        result = await self.occ.write_with_retry(
            resource_id, update_fn, max_retries=self.OCC_MAX_RETRIES
        )

        # Track conflicts for adaptive strategy
        await self._record_operation(resource_id, result.conflict)

        # If OCC failed due to conflicts, retry with distributed lock
        if not result.success and result.conflict:
            logger.info(f"OCC failed for {resource_id}, falling back to distributed lock")
            return await self._update_with_distributed_lock(
                resource_id, update_fn, agent_id
            )

        return result

    async def _update_with_distributed_lock(
        self,
        resource_id: str,
        update_fn: Callable[[Dict], Dict],
        agent_id: str
    ) -> WriteResult:
        """Update with distributed lock (pessimistic)."""
        acquired = await self.distributed.acquire(resource_id, agent_id)

        if not acquired:
            return WriteResult(
                success=False,
                strategy_used=LockStrategy.DISTRIBUTED,
                error=f"Failed to acquire lock for {resource_id}"
            )

        try:
            # Read current state
            current_state, version = await self.occ.read_state(resource_id)

            # Apply update
            new_state = update_fn(current_state)

            # Write (version check still applies for safety)
            result = await self.occ.write_state(resource_id, new_state, version)
            result.strategy_used = LockStrategy.DISTRIBUTED

            return result
        finally:
            await self.distributed.release(resource_id, agent_id)

    async def _is_high_contention(self, resource_id: str) -> bool:
        """Check if resource has high contention rate."""
        async with self.metrics_lock:
            if resource_id not in self._contention_metrics:
                return False

            metrics = self._contention_metrics[resource_id]

            # Reset window if expired
            window_age = (datetime.utcnow() - metrics.window_start).total_seconds()
            if window_age > self.CONTENTION_WINDOW_SECONDS:
                metrics.conflicts_in_window = 0
                metrics.total_operations = 0
                metrics.window_start = datetime.utcnow()
                return False

            return metrics.conflicts_in_window >= self.HIGH_CONTENTION_THRESHOLD

    async def _record_operation(self, resource_id: str, had_conflict: bool) -> None:
        """Record operation for contention tracking."""
        async with self.metrics_lock:
            if resource_id not in self._contention_metrics:
                self._contention_metrics[resource_id] = ContentionMetrics(
                    resource_id=resource_id
                )

            metrics = self._contention_metrics[resource_id]

            # Reset window if expired
            window_age = (datetime.utcnow() - metrics.window_start).total_seconds()
            if window_age > self.CONTENTION_WINDOW_SECONDS:
                metrics.conflicts_in_window = 0
                metrics.total_operations = 0
                metrics.window_start = datetime.utcnow()

            metrics.total_operations += 1
            if had_conflict:
                metrics.conflicts_in_window += 1
                metrics.last_conflict = datetime.utcnow()

    async def get_contention_stats(self, resource_id: str) -> Optional[ContentionMetrics]:
        """Get contention statistics for a resource."""
        async with self.metrics_lock:
            return self._contention_metrics.get(resource_id)

    def clear_metrics(self) -> None:
        """Clear all contention metrics (for testing)."""
        self._contention_metrics.clear()


# Convenience functions for common operations

async def with_optimistic_lock(
    resource_id: str,
    update_fn: Callable[[Dict], Dict],
    db=None,
    max_retries: int = 3
) -> WriteResult:
    """
    Execute an update with optimistic locking.

    Example:
        result = await with_optimistic_lock(
            "workflow:123",
            lambda state: {**state, "status": "completed"},
            db=session
        )
    """
    occ = OptimisticStateLock(db)
    return await occ.write_with_retry(resource_id, update_fn, max_retries)


async def with_distributed_lock(
    resource_id: str,
    operation: Callable,
    owner_id: str,
    redis_client=None,
    timeout: int = 10
) -> Any:
    """
    Execute an operation with distributed locking.

    Example:
        result = await with_distributed_lock(
            "global:counter",
            lambda: increment_counter(),
            agent_id="agent-123",
            redis_client=redis
        )
    """
    lock = DistributedLock(redis_client)

    acquired = await lock.acquire(resource_id, owner_id, timeout)
    if not acquired:
        raise LockAcquisitionError(resource_id, timeout)

    try:
        if asyncio.iscoroutinefunction(operation):
            return await operation()
        return operation()
    finally:
        await lock.release(resource_id, owner_id)


# Singleton instance
_smart_lock_manager: Optional[SmartLockManager] = None


def get_smart_lock_manager(
    db=None,
    redis_client=None
) -> SmartLockManager:
    """Get or create the SmartLockManager singleton."""
    global _smart_lock_manager
    if _smart_lock_manager is None:
        _smart_lock_manager = SmartLockManager(db, redis_client)
    return _smart_lock_manager


def reset_smart_lock_manager() -> None:
    """Reset the singleton (for testing)."""
    global _smart_lock_manager
    _smart_lock_manager = None
