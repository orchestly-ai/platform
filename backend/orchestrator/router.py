"""
Task Router - Routes tasks to appropriate agents based on capabilities and load.
"""

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from backend.shared.models import Task, TaskStatus, AgentStatus, AgentConfig, AgentState
from backend.orchestrator.registry import AgentRegistry, get_registry

logger = logging.getLogger(__name__)


class RoutingStrategy:
    """Base class for routing strategies."""

    async def select_agent(
        self,
        task: Task,
        available: List[Tuple[AgentConfig, AgentState]],
    ) -> Optional[UUID]:
        """
        Select best agent for task from pre-fetched available agents.

        Args:
            task: Task to route
            available: List of (config, state) tuples for available agents

        Returns:
            Selected agent ID or None
        """
        raise NotImplementedError


class RoundRobinStrategy(RoutingStrategy):
    """Round-robin routing across available agents."""

    def __init__(self):
        self._counters = {}
        self._lock: Optional[asyncio.Lock] = None

    async def select_agent(
        self,
        task: Task,
        available: List[Tuple[AgentConfig, AgentState]],
    ) -> Optional[UUID]:
        """Select agent using round-robin (thread-safe with asyncio.Lock)."""
        if not available:
            return None

        capability = task.capability

        # Lazy-init the lock (asyncio.Lock requires a running event loop on Python 3.9)
        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            counter = self._counters.get(capability, 0)
            config, _ = available[counter % len(available)]
            self._counters[capability] = counter + 1

        return config.agent_id


class LoadBasedStrategy(RoutingStrategy):
    """Route to agent with lowest current load."""

    async def select_agent(
        self,
        task: Task,
        available: List[Tuple[AgentConfig, AgentState]],
    ) -> Optional[UUID]:
        """Select agent with fewest active tasks (uses pre-fetched states, no extra queries)."""
        if not available:
            return None

        # Sort by active_tasks ascending
        best = min(available, key=lambda pair: pair[1].active_tasks)
        return best[0].agent_id


class RandomStrategy(RoutingStrategy):
    """Random routing (for testing/comparison)."""

    async def select_agent(
        self,
        task: Task,
        available: List[Tuple[AgentConfig, AgentState]],
    ) -> Optional[UUID]:
        """Select random agent."""
        if not available:
            return None

        config, _ = random.choice(available)
        return config.agent_id


class TaskRouter:
    """
    Routes tasks to appropriate agents.

    Supports multiple routing strategies:
    - Round Robin (default)
    - Load-Based (route to least busy)
    - Random (for testing)
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        strategy: str = "round_robin"
    ):
        """
        Initialize task router.

        Args:
            registry: Agent registry (default: global registry)
            strategy: Routing strategy name
                - "round_robin": Distribute evenly
                - "load_based": Route to least busy
                - "random": Random selection
        """
        self.registry = registry or get_registry()

        # Initialize strategy
        strategies = {
            "round_robin": RoundRobinStrategy(),
            "load_based": LoadBasedStrategy(),
            "random": RandomStrategy(),
        }

        if strategy not in strategies:
            raise ValueError(f"Unknown routing strategy: {strategy}")

        self.strategy = strategies[strategy]
        self.strategy_name = strategy

    async def route_task(self, task: Task) -> Optional[UUID]:
        """
        Route task to best available agent.

        Uses a single joined query instead of N+1 per-agent lookups.

        Args:
            task: Task to route

        Returns:
            Agent ID to assign task to, or None if no agents available

        Raises:
            ValueError: If task is invalid
        """
        if not task.capability:
            raise ValueError("Task must have a capability")

        # Single joined query: find all available agents with capacity + within cost limits
        available = await self.registry.get_available_agents(
            task.capability,
        )

        if not available:
            logger.warning(f"No agents available for capability: {task.capability}")
            return None

        # Use strategy to select agent (pre-fetched states, no extra queries)
        selected_agent = await self.strategy.select_agent(task, available)

        if selected_agent:
            logger.info(f"Routed task {task.task_id} -> Agent {selected_agent} (strategy={self.strategy_name}, capability={task.capability})")

        return selected_agent

    async def assign_task(self, task_id: UUID, agent_id: UUID) -> None:
        """
        Assign task to agent (atomic DB update).

        Args:
            task_id: Task ID
            agent_id: Agent ID
        """
        await self.registry.adjust_active_tasks(agent_id, delta=1)

    async def complete_task(self, task_id: UUID, agent_id: UUID, cost: float) -> None:
        """
        Mark task as complete in a single DB session (atomic — all or nothing).

        Args:
            task_id: Task ID
            agent_id: Agent ID
            cost: Task execution cost (USD)
        """
        async with self.registry._session() as session:
            await self.registry.adjust_active_tasks(agent_id, delta=-1, db=session)
            await self.registry.increment_task_count(agent_id, completed=True, db=session)
            await self.registry.update_cost(agent_id, cost, db=session)

    async def fail_task(self, task_id: UUID, agent_id: UUID) -> None:
        """
        Mark task as failed in a single DB session (atomic — all or nothing).

        Args:
            task_id: Task ID
            agent_id: Agent ID
        """
        async with self.registry._session() as session:
            await self.registry.adjust_active_tasks(agent_id, delta=-1, db=session)
            await self.registry.increment_task_count(agent_id, completed=False, db=session)


# Global router instance
_router: Optional[TaskRouter] = None


def get_router(strategy: str = "round_robin") -> TaskRouter:
    """Get or create global task router instance."""
    global _router
    if _router is None:
        _router = TaskRouter(strategy=strategy)
    elif strategy != _router.strategy_name:
        logger.warning(f"get_router called with strategy='{strategy}' but router already initialized with '{_router.strategy_name}'")
    return _router
