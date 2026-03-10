"""
Agent Registry Service

Central service for managing AI agents, approvals, policies, and analytics.
Follows the service layer pattern established in the codebase.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, cast, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import selectinload

from backend.shared.agent_registry_models import (
    AgentRegistry, AgentApproval, AgentPolicy, AgentUsageLog,
    AgentStatus, DeploymentStatus, SensitivityLevel, ApprovalStatus,
    PolicyType, EnforcementLevel,
    AgentRegistryCreate, AgentRegistryUpdate, AgentRegistryResponse,
    ApprovalRequest, ApprovalDecision,
    PolicyCreate, PolicyResponse,
    AgentSearchFilters, AgentStats
)
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class AgentRegistryService:
    """
    Agent Registry Service

    Features:
    - Agent registration and lifecycle management
    - Agent discovery and search
    - Capability tagging and categorization
    - Cost and usage tracking
    - Ownership and team management
    """

    def __init__(self):
        try:
            self.audit_logger = get_audit_logger()
        except RuntimeError:
            # Audit logger not initialized (demo mode)
            self.audit_logger = None

    async def register_agent(
        self,
        agent_data: AgentRegistryCreate,
        db: AsyncSession,
        user_id: str
    ) -> AgentRegistryResponse:
        """
        Register a new agent in the registry.

        Args:
            agent_data: Agent registration data
            db: AsyncSession
            user_id: ID of user registering the agent

        Returns:
            Created agent registry entry
        """
        logger.info(f"Registering agent: {agent_data.name}")

        # Check if agent_id already exists
        existing = await self.get_agent(agent_data.agent_id, db)
        if existing:
            raise ValueError(f"Agent with ID '{agent_data.agent_id}' already exists")

        # Fetch organization_id from user (in production this would come from auth context)
        from backend.shared.rbac_models import UserModel
        result = await db.execute(select(UserModel).where(UserModel.user_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User '{user_id}' not found")

        organization_id = user.organization_id

        # Create agent registry entry
        agent = AgentRegistry(
            agent_id=agent_data.agent_id,
            name=agent_data.name,
            description=agent_data.description,
            version=agent_data.version,
            owner_user_id=agent_data.owner_user_id,
            owner_team_id=agent_data.owner_team_id,
            organization_id=organization_id,
            category=agent_data.category,
            tags=agent_data.tags,
            sensitivity=agent_data.sensitivity,
            status=AgentStatus.DRAFT if agent_data.requires_approval else AgentStatus.ACTIVE,
            deployment_status=DeploymentStatus.NOT_DEPLOYED,
            data_sources_allowed=agent_data.data_sources_allowed,
            permissions=agent_data.permissions,
            requires_approval=agent_data.requires_approval,
            created_at=datetime.now()
        )

        db.add(agent)
        await db.commit()
        await db.refresh(agent)

        # Audit log
        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type=AuditEventType.AGENT_REGISTERED,
                user_id=user_id,
                organization_id=agent.organization_id,
                resource_type="agent",
                resource_id=agent.agent_id,
                details={
                    "agent_name": agent.name,
                    "category": agent.category,
                    "sensitivity": agent.sensitivity,
                    "requires_approval": agent.requires_approval
                },
                severity=AuditSeverity.INFO,
                db=db
            )

        logger.info(f"✓ Agent registered: {agent.agent_id}")
        return self._to_response(agent)

    async def get_agent(
        self,
        agent_id: str,
        db: AsyncSession
    ) -> Optional[AgentRegistryResponse]:
        """Get agent by ID"""
        stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        return self._to_response(agent)

    async def update_agent(
        self,
        agent_id: str,
        update_data: AgentRegistryUpdate,
        db: AsyncSession,
        user_id: str
    ) -> AgentRegistryResponse:
        """Update agent metadata"""
        stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Update fields (allowlist prevents mass-assignment attacks)
        _ALLOWED_AGENT_FIELDS = {
            "name", "description", "version", "category", "tags",
            "sensitivity", "data_sources_allowed", "permissions", "status",
        }
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if field in _ALLOWED_AGENT_FIELDS:
                setattr(agent, field, value)

        agent.updated_at = datetime.now()

        await db.commit()
        await db.refresh(agent)

        # Audit log
        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type=AuditEventType.AGENT_UPDATED,
                user_id=user_id,
                organization_id=agent.organization_id,
                resource_type="agent",
                resource_id=agent.agent_id,
                details={"updated_fields": list(update_dict.keys())},
                severity=AuditSeverity.INFO,
                db=db
            )

        return self._to_response(agent)

    async def delete_agent(
        self,
        agent_id: str,
        db: AsyncSession,
        user_id: str
    ) -> None:
        """Delete agent from registry"""
        stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Audit log before deletion
        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type=AuditEventType.AGENT_DELETED,
                user_id=user_id,
                organization_id=agent.organization_id,
                resource_type="agent",
                resource_id=agent.agent_id,
                details={"agent_name": agent.name},
                severity=AuditSeverity.WARNING,
                db=db
            )

        await db.delete(agent)
        await db.commit()

        logger.info(f"✓ Agent deleted: {agent_id}")

    async def search_agents(
        self,
        filters: AgentSearchFilters,
        organization_id: str,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0
    ) -> List[AgentRegistryResponse]:
        """
        Search agents with filters.

        Supports filtering by:
        - Text query (name/description)
        - Owner user/team
        - Category
        - Tags
        - Status
        - Sensitivity
        - Cost range
        """
        stmt = select(AgentRegistry).where(
            AgentRegistry.organization_id == organization_id
        )

        # Apply filters
        if filters.query:
            stmt = stmt.where(
                or_(
                    AgentRegistry.name.ilike(f"%{filters.query}%"),
                    AgentRegistry.description.ilike(f"%{filters.query}%")
                )
            )

        if filters.owner_user_id:
            stmt = stmt.where(AgentRegistry.owner_user_id == filters.owner_user_id)

        if filters.owner_team_id:
            stmt = stmt.where(AgentRegistry.owner_team_id == filters.owner_team_id)

        if filters.category:
            stmt = stmt.where(AgentRegistry.category == filters.category)

        if filters.tags:
            # Match agents that have ANY of the specified tags
            # Cast VARCHAR[] to TEXT[] for proper operator support
            tag_conditions = [
                cast(AgentRegistry.tags, ARRAY(Text)).op('@>')(cast([tag], ARRAY(Text)))
                for tag in filters.tags
            ]
            stmt = stmt.where(or_(*tag_conditions))

        if filters.status:
            stmt = stmt.where(AgentRegistry.status == filters.status)

        if filters.sensitivity:
            stmt = stmt.where(AgentRegistry.sensitivity == filters.sensitivity)

        if filters.min_cost is not None:
            stmt = stmt.where(AgentRegistry.total_cost_usd >= Decimal(str(filters.min_cost)))

        if filters.max_cost is not None:
            stmt = stmt.where(AgentRegistry.total_cost_usd <= Decimal(str(filters.max_cost)))

        # Order by most recently updated
        stmt = stmt.order_by(desc(AgentRegistry.updated_at))
        stmt = stmt.limit(limit).offset(offset)

        result = await db.execute(stmt)
        agents = result.scalars().all()

        return [self._to_response(agent) for agent in agents]

    async def find_duplicate_capabilities(
        self,
        organization_id: str,
        db: AsyncSession
    ) -> Dict[str, List[AgentRegistryResponse]]:
        """
        Find agents with duplicate capabilities (same tags).

        Returns:
            Dictionary mapping capability tag to list of agents with that capability
        """
        stmt = select(AgentRegistry).where(
            and_(
                AgentRegistry.organization_id == organization_id,
                AgentRegistry.tags.isnot(None)
            )
        )
        result = await db.execute(stmt)
        agents = result.scalars().all()

        # Group by tags
        capability_map: Dict[str, List[AgentRegistryResponse]] = {}
        for agent in agents:
            if agent.tags:
                for tag in agent.tags:
                    if tag not in capability_map:
                        capability_map[tag] = []
                    capability_map[tag].append(self._to_response(agent))

        # Filter to only duplicates (2+ agents)
        duplicates = {
            tag: agents_list
            for tag, agents_list in capability_map.items()
            if len(agents_list) > 1
        }

        return duplicates

    async def get_registry_stats(
        self,
        organization_id: str,
        db: AsyncSession
    ) -> AgentStats:
        """Get registry statistics for organization"""

        # Count by status
        stmt = select(
            func.count(AgentRegistry.agent_id).label("total"),
            func.count(AgentRegistry.agent_id).filter(AgentRegistry.status == AgentStatus.ACTIVE).label("active"),
            func.count(AgentRegistry.agent_id).filter(AgentRegistry.status == AgentStatus.PENDING_APPROVAL).label("pending"),
            func.count(AgentRegistry.agent_id).filter(AgentRegistry.status == AgentStatus.DEPRECATED).label("deprecated"),
            func.count(AgentRegistry.agent_id).filter(AgentRegistry.status == AgentStatus.RETIRED).label("retired"),
            func.count(func.distinct(AgentRegistry.owner_team_id)).label("total_teams"),
            func.sum(AgentRegistry.total_cost_usd).label("total_cost"),
            func.avg(AgentRegistry.success_rate).label("avg_success_rate")
        ).where(AgentRegistry.organization_id == organization_id)

        result = await db.execute(stmt)
        row = result.first()

        return AgentStats(
            total_agents=row.total or 0,
            active_agents=row.active or 0,
            pending_approval=row.pending or 0,
            deprecated_agents=row.deprecated or 0,
            retired_agents=row.retired or 0,
            total_teams=row.total_teams or 0,
            total_monthly_cost_usd=float(row.total_cost or 0),
            avg_success_rate=float(row.avg_success_rate or 0)
        )

    async def update_agent_metrics(
        self,
        agent_id: str,
        execution_time_ms: int,
        input_tokens: int,
        output_tokens: int,
        model_used: str,
        provider: str,
        success: bool,
        db: AsyncSession,
        # Legacy parameters for backward compatibility
        tokens_used: int = None,
        cost_usd: Decimal = None
    ) -> None:
        """Update agent execution metrics (token-based tracking)"""
        stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            logger.warning(f"Agent '{agent_id}' not found for metrics update")
            return

        # Update token metrics
        agent.total_executions += 1
        agent.total_input_tokens += input_tokens
        agent.total_output_tokens += output_tokens
        agent.last_active_at = datetime.now()

        # Track primary model and provider (most used)
        if not agent.primary_model:
            agent.primary_model = model_used
            agent.primary_provider = provider

        # Update average response time
        if agent.avg_response_time_ms:
            agent.avg_response_time_ms = int(
                (agent.avg_response_time_ms * (agent.total_executions - 1) + execution_time_ms)
                / agent.total_executions
            )
        else:
            agent.avg_response_time_ms = execution_time_ms

        # Update success rate
        if agent.success_rate:
            total_successes = (agent.success_rate / 100) * (agent.total_executions - 1)
            if success:
                total_successes += 1
            agent.success_rate = Decimal(str((total_successes / agent.total_executions) * 100))
        else:
            agent.success_rate = Decimal("100.0") if success else Decimal("0.0")

        await db.commit()

    def _to_response(self, agent: AgentRegistry) -> AgentRegistryResponse:
        """Convert ORM model to Pydantic response"""
        return AgentRegistryResponse(
            agent_id=agent.agent_id,
            name=agent.name,
            description=agent.description,
            version=agent.version,
            owner_user_id=agent.owner_user_id,
            owner_team_id=agent.owner_team_id,
            organization_id=agent.organization_id,
            category=agent.category,
            tags=agent.tags,
            sensitivity=agent.sensitivity,
            status=agent.status,
            deployment_status=agent.deployment_status,
            data_sources_allowed=agent.data_sources_allowed,
            permissions=agent.permissions,
            total_executions=agent.total_executions,
            total_cost_usd=float(agent.total_cost_usd) if agent.total_cost_usd else 0.0,  # Legacy
            total_input_tokens=agent.total_input_tokens,
            total_output_tokens=agent.total_output_tokens,
            primary_model=agent.primary_model,
            primary_provider=agent.primary_provider,
            avg_response_time_ms=agent.avg_response_time_ms,
            success_rate=float(agent.success_rate) if agent.success_rate else None,
            requires_approval=agent.requires_approval,
            approved_by=agent.approved_by,
            approved_at=agent.approved_at,
            sunset_date=agent.sunset_date,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            last_active_at=agent.last_active_at
        )


# Singleton instance
_agent_registry_service: Optional[AgentRegistryService] = None


def get_agent_registry_service() -> AgentRegistryService:
    """Get singleton AgentRegistryService instance"""
    global _agent_registry_service
    if _agent_registry_service is None:
        _agent_registry_service = AgentRegistryService()
    return _agent_registry_service
