"""
Shared State Manager - Context Passing & Session State

Implements ROADMAP.md Section: Shared State Manager (Critical for Multi-Agent)

Features:
- Workflow-scoped context (data shared between nodes in a workflow)
- Agent-scoped context (data for a specific agent)
- Global context (data shared across all workflows)
- TTL support for automatic cleanup
- Integration with state locking service for distributed locks

Key Use Cases:
- Pass output from Node A to input of Node B
- Share session data across multiple agents
- Maintain conversation context in multi-turn workflows
- Store temporary computation results

Design Principles (from ROADMAP.md):
- NOT in the critical path - failures should not block execution
- Observable - all state changes are logged
- TTL-based cleanup - no manual memory management
- Scoped isolation - workflow state doesn't leak across workflows
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass, field

from backend.shared.state_lock_service import (
    SmartLockManager,
    ResourceType,
    with_distributed_lock
)

logger = logging.getLogger(__name__)


class StateScope(Enum):
    """Scope for state storage."""
    WORKFLOW = "workflow"  # Isolated to specific workflow execution
    AGENT = "agent"        # Isolated to specific agent
    GLOBAL = "global"      # Shared across all workflows (use sparingly!)
    SESSION = "session"    # User session (for multi-turn conversations)


@dataclass
class StateEntry:
    """An entry in the state store."""
    key: str
    value: Any
    scope: StateScope
    scope_id: str  # workflow_id, agent_id, session_id, or "global"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "key": self.key,
            "value": self.value,
            "scope": self.scope.value,
            "scope_id": self.scope_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata
        }


@dataclass
class StateSnapshot:
    """A snapshot of state at a point in time."""
    scope: StateScope
    scope_id: str
    entries: Dict[str, Any]
    captured_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scope": self.scope.value,
            "scope_id": self.scope_id,
            "entries": self.entries,
            "captured_at": self.captured_at.isoformat()
        }


class SharedStateManager:
    """
    Shared State Manager for cross-node/agent context passing.

    Usage:
        # Workflow-scoped state
        manager = SharedStateManager(redis_client)
        await manager.set("user_input", "Hello", scope=StateScope.WORKFLOW, scope_id=workflow_id)
        value = await manager.get("user_input", scope=StateScope.WORKFLOW, scope_id=workflow_id)

        # Agent-scoped state
        await manager.set("last_action", "processed", scope=StateScope.AGENT, scope_id=agent_id)

        # Global state (use distributed lock automatically)
        await manager.set("api_rate_limit", 1000, scope=StateScope.GLOBAL)
    """

    # Default TTLs for each scope
    DEFAULT_TTLS = {
        StateScope.WORKFLOW: timedelta(hours=24),
        StateScope.AGENT: timedelta(hours=1),
        StateScope.GLOBAL: None,  # No TTL
        StateScope.SESSION: timedelta(hours=12)
    }

    def __init__(
        self,
        redis_client=None,
        db=None,
        lock_manager: Optional[SmartLockManager] = None
    ):
        """
        Initialize Shared State Manager.

        Args:
            redis_client: Redis client for storage
            db: Database session for persistence
            lock_manager: SmartLockManager instance (created if not provided)
        """
        self.redis = redis_client
        self.db = db
        self.lock_manager = lock_manager or SmartLockManager(db, redis_client)

        # In-memory fallback for testing/development
        self._memory_store: Dict[str, StateEntry] = {}
        # Lazy initialization of asyncio.Lock for Python 3.9 compatibility
        self._store_lock: Optional[asyncio.Lock] = None

    @property
    def store_lock(self) -> asyncio.Lock:
        """Lazily initialize the asyncio.Lock for Python 3.9 compatibility."""
        if self._store_lock is None:
            self._store_lock = asyncio.Lock()
        return self._store_lock

    def _make_key(self, key: str, scope: StateScope, scope_id: str) -> str:
        """Generate Redis key for state entry."""
        return f"state:{scope.value}:{scope_id}:{key}"

    async def set(
        self,
        key: str,
        value: Any,
        scope: StateScope = StateScope.WORKFLOW,
        scope_id: str = "default",
        ttl: Optional[timedelta] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Set a value in the state store.

        Args:
            key: State key
            value: Value to store (will be JSON serialized)
            scope: State scope (workflow, agent, global, session)
            scope_id: Scope identifier (workflow_id, agent_id, etc.)
            ttl: Time-to-live (uses default if not specified)
            metadata: Optional metadata for tracking

        Returns:
            True if successful

        Example:
            # Node A stores output
            await state.set("user_message", "Hello", scope=StateScope.WORKFLOW, scope_id=workflow_id)

            # Node B retrieves it
            message = await state.get("user_message", scope=StateScope.WORKFLOW, scope_id=workflow_id)
        """
        # Use default TTL if not specified
        if ttl is None:
            ttl = self.DEFAULT_TTLS.get(scope)

        expires_at = datetime.utcnow() + ttl if ttl else None

        entry = StateEntry(
            key=key,
            value=value,
            scope=scope,
            scope_id=scope_id,
            expires_at=expires_at,
            metadata=metadata or {}
        )

        redis_key = self._make_key(key, scope, scope_id)

        # Global state uses distributed lock to prevent thundering herd
        if scope == StateScope.GLOBAL:
            try:
                async def store_operation():
                    return await self._store_entry(redis_key, entry, ttl)

                result = await with_distributed_lock(
                    resource_id=f"global_state:{key}",
                    operation=store_operation,
                    owner_id=f"state_manager_{scope_id}",
                    redis_client=self.redis
                )
                logger.debug(f"Set global state {key} with distributed lock")
                return result
            except Exception as e:
                logger.warning(f"Failed to set global state with lock: {e}")
                return await self._store_entry(redis_key, entry, ttl)

        return await self._store_entry(redis_key, entry, ttl)

    async def _store_entry(
        self,
        redis_key: str,
        entry: StateEntry,
        ttl: Optional[timedelta]
    ) -> bool:
        """Store entry in Redis or fallback to memory."""
        print(f"[StateManager] _store_entry called:", flush=True)
        print(f"[StateManager]   redis_key: {redis_key}", flush=True)
        print(f"[StateManager]   entry.key: {entry.key}", flush=True)
        print(f"[StateManager]   has redis: {self.redis is not None}", flush=True)

        # Try Redis first
        if self.redis:
            try:
                serialized = json.dumps(entry.to_dict())
                if ttl:
                    await self.redis.setex(
                        redis_key,
                        int(ttl.total_seconds()),
                        serialized
                    )
                else:
                    await self.redis.set(redis_key, serialized)

                print(f"[StateManager] Successfully stored in Redis: {redis_key}", flush=True)
                logger.debug(
                    f"Stored state: {entry.key} (scope={entry.scope.value}, "
                    f"ttl={ttl.total_seconds() if ttl else 'none'}s)"
                )
                return True
            except Exception as e:
                print(f"[StateManager] Redis store failed: {e}", flush=True)
                logger.warning(f"Redis store failed, using memory: {e}")

        # Fallback to in-memory store
        async with self.store_lock:
            self._memory_store[redis_key] = entry
            print(f"[StateManager] Stored in memory: {redis_key}", flush=True)
            print(f"[StateManager] Memory store now has {len(self._memory_store)} entries", flush=True)
            logger.debug(f"Stored in memory: {entry.key}")
            return True

    async def get(
        self,
        key: str,
        scope: StateScope = StateScope.WORKFLOW,
        scope_id: str = "default",
        default: Any = None
    ) -> Any:
        """
        Get a value from the state store.

        Args:
            key: State key
            scope: State scope
            scope_id: Scope identifier
            default: Default value if key not found

        Returns:
            Stored value or default

        Example:
            user_input = await state.get("user_input", scope=StateScope.WORKFLOW, scope_id=workflow_id)
        """
        redis_key = self._make_key(key, scope, scope_id)

        print(f"[StateManager] get called:", flush=True)
        print(f"[StateManager]   key: {key}", flush=True)
        print(f"[StateManager]   redis_key: {redis_key}", flush=True)
        print(f"[StateManager]   scope_id: {scope_id}", flush=True)
        print(f"[StateManager]   has redis: {self.redis is not None}", flush=True)

        # Try Redis first
        if self.redis:
            try:
                serialized = await self.redis.get(redis_key)
                if serialized:
                    entry_dict = json.loads(serialized)
                    entry = StateEntry(
                        key=entry_dict["key"],
                        value=entry_dict["value"],
                        scope=StateScope(entry_dict["scope"]),
                        scope_id=entry_dict["scope_id"],
                        created_at=datetime.fromisoformat(entry_dict["created_at"]),
                        updated_at=datetime.fromisoformat(entry_dict["updated_at"]),
                        expires_at=datetime.fromisoformat(entry_dict["expires_at"]) if entry_dict["expires_at"] else None,
                        metadata=entry_dict.get("metadata", {})
                    )

                    # Check expiration
                    if entry.is_expired():
                        await self.delete(key, scope, scope_id)
                        logger.debug(f"State expired: {key}")
                        return default

                    logger.debug(f"Retrieved state: {key} (scope={scope.value})")
                    return entry.value
            except Exception as e:
                logger.warning(f"Redis get failed, using memory: {e}")

        # Fallback to in-memory store
        print(f"[StateManager] Checking memory store...", flush=True)
        print(f"[StateManager] Memory store has {len(self._memory_store)} entries", flush=True)
        print(f"[StateManager] Memory store keys: {list(self._memory_store.keys())}", flush=True)
        async with self.store_lock:
            entry = self._memory_store.get(redis_key)
            if entry:
                print(f"[StateManager] Found in memory: {redis_key}", flush=True)
                if entry.is_expired():
                    print(f"[StateManager] Entry expired!", flush=True)
                    del self._memory_store[redis_key]
                    return default
                print(f"[StateManager] Returning value: {entry.value}", flush=True)
                return entry.value
            else:
                print(f"[StateManager] NOT found in memory: {redis_key}", flush=True)

        logger.debug(f"State not found: {key}, returning default")
        return default

    async def delete(
        self,
        key: str,
        scope: StateScope = StateScope.WORKFLOW,
        scope_id: str = "default"
    ) -> bool:
        """
        Delete a value from the state store.

        Args:
            key: State key
            scope: State scope
            scope_id: Scope identifier

        Returns:
            True if deleted
        """
        redis_key = self._make_key(key, scope, scope_id)

        # Try Redis first
        if self.redis:
            try:
                deleted = await self.redis.delete(redis_key)
                logger.debug(f"Deleted state: {key} (scope={scope.value})")
                return deleted > 0
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        # Fallback to in-memory store
        async with self.store_lock:
            if redis_key in self._memory_store:
                del self._memory_store[redis_key]
                return True

        return False

    async def get_all(
        self,
        scope: StateScope = StateScope.WORKFLOW,
        scope_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Get all values for a scope.

        Args:
            scope: State scope
            scope_id: Scope identifier

        Returns:
            Dictionary of all key-value pairs

        Example:
            # Get all workflow state
            workflow_state = await state.get_all(StateScope.WORKFLOW, workflow_id)
        """
        pattern = f"state:{scope.value}:{scope_id}:*"
        result = {}

        # Try Redis first
        if self.redis:
            try:
                keys = await self.redis.keys(pattern)
                for redis_key in keys:
                    serialized = await self.redis.get(redis_key)
                    if serialized:
                        entry_dict = json.loads(serialized)
                        entry = StateEntry(
                            key=entry_dict["key"],
                            value=entry_dict["value"],
                            scope=StateScope(entry_dict["scope"]),
                            scope_id=entry_dict["scope_id"],
                            created_at=datetime.fromisoformat(entry_dict["created_at"]),
                            updated_at=datetime.fromisoformat(entry_dict["updated_at"]),
                            expires_at=datetime.fromisoformat(entry_dict["expires_at"]) if entry_dict["expires_at"] else None,
                            metadata=entry_dict.get("metadata", {})
                        )

                        if not entry.is_expired():
                            result[entry.key] = entry.value

                logger.debug(f"Retrieved all state for {scope.value}:{scope_id}: {len(result)} entries")
                return result
            except Exception as e:
                logger.warning(f"Redis get_all failed: {e}")

        # Fallback to in-memory store
        async with self.store_lock:
            prefix = f"state:{scope.value}:{scope_id}:"
            for redis_key, entry in self._memory_store.items():
                if redis_key.startswith(prefix):
                    if not entry.is_expired():
                        result[entry.key] = entry.value
                    else:
                        # Clean up expired entries
                        del self._memory_store[redis_key]

        return result

    async def clear(
        self,
        scope: StateScope = StateScope.WORKFLOW,
        scope_id: str = "default"
    ) -> int:
        """
        Clear all state for a scope.

        Args:
            scope: State scope
            scope_id: Scope identifier

        Returns:
            Number of entries deleted

        Example:
            # Clear workflow state when workflow completes
            await state.clear(StateScope.WORKFLOW, workflow_id)
        """
        pattern = f"state:{scope.value}:{scope_id}:*"
        count = 0

        # Try Redis first
        if self.redis:
            try:
                keys = await self.redis.keys(pattern)
                if keys:
                    count = await self.redis.delete(*keys)
                logger.info(f"Cleared {count} state entries for {scope.value}:{scope_id}")
                return count
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")

        # Fallback to in-memory store
        async with self.store_lock:
            prefix = f"state:{scope.value}:{scope_id}:"
            keys_to_delete = [k for k in self._memory_store.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._memory_store[key]
                count += 1

        return count

    async def snapshot(
        self,
        scope: StateScope = StateScope.WORKFLOW,
        scope_id: str = "default"
    ) -> StateSnapshot:
        """
        Create a snapshot of all state for a scope.

        Useful for time-travel debugging and rollback.

        Args:
            scope: State scope
            scope_id: Scope identifier

        Returns:
            StateSnapshot with all current state
        """
        entries = await self.get_all(scope, scope_id)
        return StateSnapshot(
            scope=scope,
            scope_id=scope_id,
            entries=entries
        )

    async def restore_snapshot(self, snapshot: StateSnapshot) -> int:
        """
        Restore state from a snapshot.

        Args:
            snapshot: StateSnapshot to restore

        Returns:
            Number of entries restored
        """
        count = 0
        for key, value in snapshot.entries.items():
            await self.set(
                key=key,
                value=value,
                scope=snapshot.scope,
                scope_id=snapshot.scope_id
            )
            count += 1

        logger.info(f"Restored {count} state entries from snapshot")
        return count

    async def exists(
        self,
        key: str,
        scope: StateScope = StateScope.WORKFLOW,
        scope_id: str = "default"
    ) -> bool:
        """
        Check if a key exists in the state store.

        Args:
            key: State key
            scope: State scope
            scope_id: Scope identifier

        Returns:
            True if key exists
        """
        redis_key = self._make_key(key, scope, scope_id)

        if self.redis:
            try:
                exists = await self.redis.exists(redis_key)
                return exists > 0
            except Exception as e:
                logger.warning(f"Redis exists failed: {e}")

        async with self.store_lock:
            return redis_key in self._memory_store

    async def keys(
        self,
        scope: StateScope = StateScope.WORKFLOW,
        scope_id: str = "default"
    ) -> List[str]:
        """
        Get all keys for a scope.

        Args:
            scope: State scope
            scope_id: Scope identifier

        Returns:
            List of all keys
        """
        pattern = f"state:{scope.value}:{scope_id}:*"
        result = []

        if self.redis:
            try:
                redis_keys = await self.redis.keys(pattern)
                for redis_key in redis_keys:
                    # Extract the actual key from redis_key
                    # Format: state:workflow:workflow_123:user_input
                    # Extract: user_input
                    parts = redis_key.split(":")
                    if len(parts) >= 4:
                        result.append(":".join(parts[3:]))
                return result
            except Exception as e:
                logger.warning(f"Redis keys failed: {e}")

        async with self.store_lock:
            prefix = f"state:{scope.value}:{scope_id}:"
            for redis_key in self._memory_store.keys():
                if redis_key.startswith(prefix):
                    entry = self._memory_store[redis_key]
                    if not entry.is_expired():
                        result.append(entry.key)

        return result


# Singleton instance
_shared_state_manager: Optional[SharedStateManager] = None


def get_shared_state_manager(
    redis_client=None,
    db=None,
    lock_manager: Optional[SmartLockManager] = None
) -> SharedStateManager:
    """Get or create the SharedStateManager singleton."""
    global _shared_state_manager
    if _shared_state_manager is None:
        _shared_state_manager = SharedStateManager(redis_client, db, lock_manager)
    return _shared_state_manager


def reset_shared_state_manager() -> None:
    """Reset the singleton (for testing)."""
    global _shared_state_manager
    _shared_state_manager = None
