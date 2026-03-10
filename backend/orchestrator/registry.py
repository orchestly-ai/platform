"""
Agent Registry - Manages registered agents and their capabilities.

Uses PostgreSQL for persistence with in-memory caching for performance.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, delete, and_, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from backend.shared.models import AgentConfig, AgentState, AgentStatus, AgentCapability
from backend.shared.config import get_settings
from backend.database.models import AgentModel, AgentStateModel
from backend.database.session import AsyncSessionLocal


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


class AgentRegistry:
    """
    Manages agent registration and lifecycle.

    Features:
    - Register/deregister agents (persisted to PostgreSQL)
    - Track agent status and health
    - Find agents by capability (with in-memory index for performance)
    - Monitor agent heartbeats

    Architecture:
    - Primary storage: PostgreSQL (AgentModel, AgentStateModel)
    - Cache: In-memory capability index for fast lookups
    - Cache is rebuilt on startup and updated on registration changes
    """

    def __init__(self):
        """Initialize agent registry."""
        self.settings = get_settings()

        # In-memory capability index for fast lookups (synced with DB)
        # Uses Set[UUID] for O(1) add/remove/contains instead of List
        self._capability_index: Dict[Tuple[str, str], Set[UUID]] = {}

        # Track if cache has been initialized
        self._cache_initialized = False
        self._cache_init_lock: Optional[asyncio.Lock] = None

    @asynccontextmanager
    async def _session(self, db: Optional[AsyncSession] = None) -> AsyncIterator[AsyncSession]:
        """Context manager for database sessions with proper commit/rollback."""
        if db is not None:
            yield db
        else:
            async with AsyncSessionLocal() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

    async def _ensure_cache_initialized(self, db: AsyncSession) -> None:
        """Ensure capability index cache is initialized from database (lock prevents duplicate work)."""
        if self._cache_initialized:
            return

        # Lazy-init the lock (asyncio.Lock requires a running event loop on Python 3.9)
        if self._cache_init_lock is None:
            self._cache_init_lock = asyncio.Lock()

        async with self._cache_init_lock:
            # Double-check after acquiring lock
            if self._cache_initialized:
                return

            # Load all active agents and build capability index (keyed by org_id)
            stmt = select(AgentModel).where(AgentModel.status == AgentStatus.ACTIVE.value)
            result = await db.execute(stmt)
            agents = result.scalars().all()

            self._capability_index = {}
            for agent in agents:
                org_id = agent.organization_id or "default"
                for cap in agent.capabilities:
                    cap_name = cap.get("name") if isinstance(cap, dict) else cap
                    if cap_name:
                        cache_key = (org_id, cap_name)
                        if cache_key not in self._capability_index:
                            self._capability_index[cache_key] = set()
                        self._capability_index[cache_key].add(agent.agent_id)

            self._cache_initialized = True
            logger.info(f"Agent registry cache initialized with {len(agents)} agents")

    def _update_capability_index(self, agent_id: UUID, capabilities: List, organization_id: str = "default", add: bool = True) -> None:
        """Update in-memory capability index (per-org scoped). O(1) per capability via Set."""
        for cap in capabilities:
            cap_name = cap.name if hasattr(cap, 'name') else (cap.get("name") if isinstance(cap, dict) else cap)
            if not cap_name:
                continue

            cache_key = (organization_id, cap_name)
            if add:
                if cache_key not in self._capability_index:
                    self._capability_index[cache_key] = set()
                self._capability_index[cache_key].add(agent_id)
            else:
                if cache_key in self._capability_index:
                    self._capability_index[cache_key].discard(agent_id)

    async def register_agent(self, config: AgentConfig, db: Optional[AsyncSession] = None) -> UUID:
        """
        Register a new agent.

        Args:
            config: Agent configuration
            db: Optional database session (creates new one if not provided)

        Returns:
            Agent ID (UUID)

        Raises:
            ValueError: If agent name already exists
        """
        async with self._session(db) as session:
            await self._ensure_cache_initialized(session)

            # Check if name already exists within the same organization
            stmt = select(AgentModel).where(
                and_(
                    AgentModel.organization_id == config.organization_id,
                    AgentModel.name == config.name
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                raise ValueError(f"Agent with name '{config.name}' already exists in organization '{config.organization_id}'")

            agent_id = config.agent_id

            # Convert capabilities to JSON-serializable format
            capabilities_json = [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "input_schema": cap.input_schema,
                    "output_schema": cap.output_schema,
                }
                for cap in config.capabilities
            ]

            # Create agent model
            agent_model = AgentModel(
                agent_id=agent_id,
                organization_id=config.organization_id,
                name=config.name,
                framework=config.framework.value if hasattr(config.framework, 'value') else config.framework,
                version=config.version,
                capabilities=capabilities_json,
                max_concurrent_tasks=config.max_concurrent_tasks,
                cost_limit_daily=config.cost_limit_daily,
                cost_limit_monthly=config.cost_limit_monthly,
                llm_provider=config.llm_provider,
                llm_model=config.llm_model,
                extra_metadata=config.metadata,
                status=AgentStatus.ACTIVE,
                created_at=_utcnow(),
                updated_at=_utcnow(),
                last_heartbeat=_utcnow(),
            )

            # Create agent state
            state_model = AgentStateModel(
                agent_id=agent_id,
                organization_id=config.organization_id,
                active_tasks=0,
                tasks_completed=0,
                tasks_failed=0,
                total_cost_today=0.0,
                total_cost_month=0.0,
                updated_at=_utcnow(),
            )

            session.add(agent_model)
            session.add(state_model)

            # Update in-memory capability index
            self._update_capability_index(agent_id, config.capabilities, organization_id=config.organization_id, add=True)

            logger.info(f"Registered agent: {config.name} ({agent_id}) in org {config.organization_id}, capabilities: {[c.name for c in config.capabilities]}")

            return agent_id

    async def deregister_agent(self, agent_id: UUID, db: Optional[AsyncSession] = None) -> None:
        """
        Deregister an agent.

        Args:
            agent_id: Agent ID to deregister
            db: Optional database session
        """
        async with self._session(db) as session:
            # Get agent for capability index update
            stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
            result = await session.execute(stmt)
            agent = result.scalar_one_or_none()

            if not agent:
                return

            # Update capability index
            self._update_capability_index(agent_id, agent.capabilities, organization_id=agent.organization_id or "default", add=False)

            # Delete agent state first (foreign key)
            await session.execute(delete(AgentStateModel).where(AgentStateModel.agent_id == agent_id))

            # Delete agent
            await session.execute(delete(AgentModel).where(AgentModel.agent_id == agent_id))

            logger.info(f"Deregistered agent: {agent.name} ({agent_id})")

    async def get_agent(self, agent_id: UUID, db: Optional[AsyncSession] = None) -> Optional[AgentConfig]:
        """
        Get agent configuration.

        Args:
            agent_id: Agent ID
            db: Optional database session

        Returns:
            Agent configuration or None if not found
        """
        async with self._session(db) as session:
            stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
            result = await session.execute(stmt)
            agent = result.scalar_one_or_none()

            if not agent:
                return None

            return self._model_to_config(agent)

    async def get_agent_state(self, agent_id: UUID, db: Optional[AsyncSession] = None) -> Optional[AgentState]:
        """
        Get agent runtime state.

        Args:
            agent_id: Agent ID
            db: Optional database session

        Returns:
            Agent state or None if not found
        """
        async with self._session(db) as session:
            stmt = select(AgentModel).options(selectinload(AgentModel.state)).where(AgentModel.agent_id == agent_id)
            result = await session.execute(stmt)
            agent = result.scalar_one_or_none()

            if not agent or not agent.state:
                return None

            return AgentState(
                agent_id=agent_id,
                status=agent.status,
                started_at=agent.created_at,
                last_heartbeat=agent.last_heartbeat,
                active_tasks=agent.state.active_tasks,
                tasks_completed=agent.state.tasks_completed,
                tasks_failed=agent.state.tasks_failed,
                total_cost_today=agent.state.total_cost_today,
                total_cost_month=agent.state.total_cost_month,
            )

    async def list_agents(
        self,
        status: Optional[AgentStatus] = None,
        organization_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> List[AgentConfig]:
        """
        List agents, filtered by organization and optionally by status.

        Args:
            status: Filter by status (optional) - can be string or AgentStatus enum
            organization_id: Filter by organization (required for tenant isolation)
            db: Optional database session

        Returns:
            List of agent configurations
        """
        async with self._session(db) as session:
            stmt = select(AgentModel)

            # Filter by organization for tenant isolation
            if organization_id:
                stmt = stmt.where(AgentModel.organization_id == organization_id)

            if status:
                if isinstance(status, str):
                    stmt = stmt.where(AgentModel.status == status)
                else:
                    stmt = stmt.where(AgentModel.status == status.value)

            result = await session.execute(stmt)
            agents = result.scalars().all()

            return [self._model_to_config(a) for a in agents]

    async def find_agents_by_capability(
        self,
        capability: str,
        organization_id: Optional[str] = None,
        status: Optional[AgentStatus] = AgentStatus.ACTIVE,
        db: Optional[AsyncSession] = None
    ) -> List[UUID]:
        """
        Find all agents that can handle a specific capability within an organization.

        Uses in-memory capability index for fast lookups.

        Args:
            capability: Capability name
            organization_id: Organization ID for tenant isolation
            status: Filter by status (default: ACTIVE only)
            db: Optional database session

        Returns:
            List of agent IDs
        """
        async with self._session(db) as session:
            await self._ensure_cache_initialized(session)

            # Get from org-scoped in-memory index
            cache_key = (organization_id or "default", capability)
            agent_ids = self._capability_index.get(cache_key, [])

            if not status:
                return list(agent_ids)

            if not agent_ids:
                return []

            status_value = status.value if hasattr(status, 'value') else status
            stmt = select(AgentModel.agent_id).where(
                and_(
                    AgentModel.agent_id.in_(agent_ids),
                    AgentModel.status == status_value
                )
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_available_agents(
        self,
        capability: str,
        organization_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> List[Tuple[AgentConfig, AgentState]]:
        """
        Get all agents available for a capability in a single joined query.

        Filters by: ACTIVE status, within capacity, within cost limits.
        Replaces the N+1 pattern of get_agent + get_agent_state + check_cost_limit per agent.

        Args:
            capability: Required capability name
            organization_id: Organization ID for tenant isolation
            db: Optional database session

        Returns:
            List of (AgentConfig, AgentState) tuples for available agents
        """
        async with self._session(db) as session:
            await self._ensure_cache_initialized(session)

            # Get candidate agent_ids from in-memory index
            cache_key = (organization_id or "default", capability)
            candidate_ids = self._capability_index.get(cache_key, set())
            if not candidate_ids:
                return []

            now = _utcnow()

            # Single joined query: agents + states, filtered by status + capacity + cost
            stmt = (
                select(AgentModel, AgentStateModel)
                .join(AgentStateModel, AgentModel.agent_id == AgentStateModel.agent_id)
                .where(
                    and_(
                        AgentModel.agent_id.in_(candidate_ids),
                        AgentModel.status == AgentStatus.ACTIVE.value,
                        AgentStateModel.active_tasks < AgentModel.max_concurrent_tasks,
                    )
                )
            )
            result = await session.execute(stmt)
            rows = result.all()

            available = []
            for agent, state in rows:
                # Check cost limits (accounting for day/month rollover)
                cost_today = state.total_cost_today
                cost_month = state.total_cost_month

                if state.cost_last_reset_day and state.cost_last_reset_day.date() < now.date():
                    cost_today = 0.0
                if state.cost_last_reset_month and (
                    state.cost_last_reset_month.year < now.year
                    or state.cost_last_reset_month.month < now.month
                ):
                    cost_month = 0.0

                if cost_today >= agent.cost_limit_daily or cost_month >= agent.cost_limit_monthly:
                    continue

                config = self._model_to_config(agent)
                agent_state = AgentState(
                    agent_id=agent.agent_id,
                    status=agent.status,
                    started_at=agent.created_at,
                    last_heartbeat=agent.last_heartbeat,
                    active_tasks=state.active_tasks,
                    tasks_completed=state.tasks_completed,
                    tasks_failed=state.tasks_failed,
                    total_cost_today=state.total_cost_today,
                    total_cost_month=state.total_cost_month,
                )
                available.append((config, agent_state))

            return available

    async def update_agent_status(
        self,
        agent_id: UUID,
        status: AgentStatus,
        error_message: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> None:
        """
        Update agent status.

        Args:
            agent_id: Agent ID
            status: New status
            error_message: Error message if status is ERROR
            db: Optional database session
        """
        async with self._session(db) as session:
            stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
            result = await session.execute(stmt)
            agent = result.scalar_one_or_none()

            if not agent:
                return

            agent.status = status
            agent.updated_at = _utcnow()
            if error_message:
                agent.extra_metadata = agent.extra_metadata or {}
                agent.extra_metadata["last_error"] = error_message

            # Invalidate capability index when agent becomes non-active
            if status not in (AgentStatus.ACTIVE, AgentStatus.IDLE):
                self._update_capability_index(
                    agent_id, agent.capabilities,
                    organization_id=agent.organization_id or "default", add=False
                )

            logger.debug(f"Agent {agent_id}: Status changed to {status.value}")

    async def update_heartbeat(self, agent_id: UUID, db: Optional[AsyncSession] = None) -> None:
        """
        Update agent heartbeat timestamp.

        Args:
            agent_id: Agent ID
            db: Optional database session
        """
        async with self._session(db) as session:
            stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
            result = await session.execute(stmt)
            agent = result.scalar_one_or_none()

            if not agent:
                return

            agent.last_heartbeat = _utcnow()

            # If agent was in error, mark as active
            if agent.status == AgentStatus.ERROR:
                agent.status = AgentStatus.ACTIVE
                if agent.extra_metadata:
                    agent.extra_metadata.pop("last_error", None)

    async def adjust_active_tasks(self, agent_id: UUID, delta: int, db: Optional[AsyncSession] = None) -> None:
        """
        Atomically adjust active_tasks counter using SQL arithmetic (no read-modify-write race).

        Args:
            agent_id: Agent ID
            delta: Amount to adjust (+1 for assign, -1 for complete/fail)
            db: Optional database session
        """
        async with self._session(db) as session:
            if delta >= 0:
                await session.execute(
                    update(AgentStateModel)
                    .where(AgentStateModel.agent_id == agent_id)
                    .values(
                        active_tasks=AgentStateModel.active_tasks + delta,
                        updated_at=_utcnow(),
                    )
                )
            else:
                # Floor at 0 to prevent negative values
                await session.execute(
                    update(AgentStateModel)
                    .where(AgentStateModel.agent_id == agent_id)
                    .values(
                        active_tasks=func.greatest(0, AgentStateModel.active_tasks + delta),
                        updated_at=_utcnow(),
                    )
                )

    async def increment_task_count(
        self,
        agent_id: UUID,
        completed: bool = True,
        db: Optional[AsyncSession] = None
    ) -> None:
        """
        Increment task completion or failure count.

        Args:
            agent_id: Agent ID
            completed: True for completion, False for failure
            db: Optional database session
        """
        async with self._session(db) as session:
            if completed:
                await session.execute(
                    update(AgentStateModel)
                    .where(AgentStateModel.agent_id == agent_id)
                    .values(
                        tasks_completed=AgentStateModel.tasks_completed + 1,
                        updated_at=_utcnow(),
                    )
                )
            else:
                await session.execute(
                    update(AgentStateModel)
                    .where(AgentStateModel.agent_id == agent_id)
                    .values(
                        tasks_failed=AgentStateModel.tasks_failed + 1,
                        updated_at=_utcnow(),
                    )
                )

    async def update_cost(self, agent_id: UUID, cost: float, db: Optional[AsyncSession] = None) -> None:
        """
        Add cost to agent's running total, resetting daily/monthly counters as needed.

        Args:
            agent_id: Agent ID
            cost: Cost in USD to add
            db: Optional database session
        """
        async with self._session(db) as session:
            stmt = select(AgentStateModel).where(AgentStateModel.agent_id == agent_id)
            result = await session.execute(stmt)
            state = result.scalar_one_or_none()

            if not state:
                return

            now = _utcnow()

            # Reset daily cost if day has changed
            if state.cost_last_reset_day is None or state.cost_last_reset_day.date() < now.date():
                state.total_cost_today = 0.0
                state.cost_last_reset_day = now

            # Reset monthly cost if month has changed
            if state.cost_last_reset_month is None or (
                state.cost_last_reset_month.year < now.year
                or state.cost_last_reset_month.month < now.month
            ):
                state.total_cost_month = 0.0
                state.cost_last_reset_month = now

            state.total_cost_today += cost
            state.total_cost_month += cost
            state.updated_at = now

    async def check_cost_limit(self, agent_id: UUID, db: Optional[AsyncSession] = None) -> bool:
        """
        Check if agent is within cost limits, accounting for day/month rollovers.

        Args:
            agent_id: Agent ID
            db: Optional database session

        Returns:
            True if within limits, False if exceeded
        """
        async with self._session(db) as session:
            stmt = select(AgentModel).options(selectinload(AgentModel.state)).where(AgentModel.agent_id == agent_id)
            result = await session.execute(stmt)
            agent = result.scalar_one_or_none()

            if not agent or not agent.state:
                return False

            now = _utcnow()
            cost_today = agent.state.total_cost_today
            cost_month = agent.state.total_cost_month

            # Account for day rollover — if last reset was a different day, cost is effectively 0
            if agent.state.cost_last_reset_day and agent.state.cost_last_reset_day.date() < now.date():
                cost_today = 0.0

            # Account for month rollover
            if agent.state.cost_last_reset_month and (
                agent.state.cost_last_reset_month.year < now.year
                or agent.state.cost_last_reset_month.month < now.month
            ):
                cost_month = 0.0

            # Check daily limit
            if cost_today >= agent.cost_limit_daily:
                logger.warning(f"Agent {agent_id}: Daily cost limit exceeded (${cost_today:.2f} / ${agent.cost_limit_daily:.2f})")
                return False

            # Check monthly limit
            if cost_month >= agent.cost_limit_monthly:
                logger.warning(f"Agent {agent_id}: Monthly cost limit exceeded (${cost_month:.2f} / ${agent.cost_limit_monthly:.2f})")
                return False

            return True

    async def get_agent_metrics(self, agent_id: UUID, db: Optional[AsyncSession] = None) -> Optional[Dict]:
        """
        Get agent metrics summary.

        Args:
            agent_id: Agent ID
            db: Optional database session

        Returns:
            Metrics dictionary or None
        """
        async with self._session(db) as session:
            stmt = select(AgentModel).options(selectinload(AgentModel.state)).where(AgentModel.agent_id == agent_id)
            result = await session.execute(stmt)
            agent = result.scalar_one_or_none()

            if not agent or not agent.state:
                return None

            return {
                "agent_id": str(agent_id),
                "name": agent.name,
                "status": agent.status.value,
                "tasks_completed": agent.state.tasks_completed,
                "tasks_failed": agent.state.tasks_failed,
                "success_rate": (
                    agent.state.tasks_completed / (agent.state.tasks_completed + agent.state.tasks_failed)
                    if (agent.state.tasks_completed + agent.state.tasks_failed) > 0
                    else 0.0
                ),
                "cost_today": agent.state.total_cost_today,
                "cost_month": agent.state.total_cost_month,
                "cost_limit_daily": agent.cost_limit_daily,
                "cost_limit_monthly": agent.cost_limit_monthly,
                "active_tasks": agent.state.active_tasks,
                "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
            }

    async def cleanup_stale_agents(self, timeout_seconds: int = 300, db: Optional[AsyncSession] = None) -> int:
        """
        Mark agents as ERROR if no heartbeat for timeout period.

        Args:
            timeout_seconds: Heartbeat timeout (default: 5 minutes)
            db: Optional database session

        Returns:
            Number of agents marked as stale
        """
        async with self._session(db) as session:
            now = _utcnow()
            cutoff = now - timedelta(seconds=timeout_seconds)

            # Single UPDATE instead of loading all agents into memory
            result = await session.execute(
                update(AgentModel)
                .where(
                    and_(
                        AgentModel.status == AgentStatus.ACTIVE.value,
                        AgentModel.last_heartbeat.isnot(None),
                        AgentModel.last_heartbeat < cutoff,
                    )
                )
                .values(
                    status=AgentStatus.ERROR.value,
                    updated_at=now,
                )
            )
            stale_count = result.rowcount

            if stale_count > 0:
                logger.info(f"Marked {stale_count} stale agents as ERROR (heartbeat older than {timeout_seconds}s)")

            return stale_count

    def _model_to_config(self, agent: AgentModel) -> AgentConfig:
        """Convert database model to AgentConfig."""
        # Convert capabilities from JSON to AgentCapability objects
        capabilities = []
        for cap in agent.capabilities:
            if isinstance(cap, dict):
                capabilities.append(AgentCapability(
                    name=cap.get("name", ""),
                    description=cap.get("description", "No description"),
                    input_schema=cap.get("input_schema") or cap.get("parameters"),
                    output_schema=cap.get("output_schema"),
                ))
            else:
                # String capability - convert to AgentCapability with default description
                capabilities.append(AgentCapability(
                    name=str(cap),
                    description=f"Capability: {cap}"
                ))

        return AgentConfig(
            agent_id=agent.agent_id,
            organization_id=agent.organization_id,
            name=agent.name,
            framework=agent.framework,
            version=agent.version,
            capabilities=capabilities,
            max_concurrent_tasks=agent.max_concurrent_tasks,
            cost_limit_daily=agent.cost_limit_daily,
            cost_limit_monthly=agent.cost_limit_monthly,
            llm_provider=agent.llm_provider,
            llm_model=agent.llm_model or "gpt-4",  # Default if None
            metadata=agent.extra_metadata or {},
        )


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get or create global agent registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
