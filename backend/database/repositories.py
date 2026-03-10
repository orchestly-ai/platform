"""
Database Repositories

Data access layer for agents, tasks, and metrics.
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from uuid import UUID

from sqlalchemy import select, update, delete, and_, or_, func, cast, literal
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import (
    AgentModel, AgentStateModel, TaskModel, TaskExecutionModel,
    MetricModel, AlertModel, APIKeyModel
)
# WorkflowModel and WorkflowExecutionModel are in shared/workflow_models.py
from backend.shared.workflow_models import WorkflowModel, WorkflowExecutionModel
from backend.shared.models import (
    AgentConfig, AgentState, AgentStatus, AgentCapability,
    Task, TaskStatus, TaskPriority
)


class AgentRepository:
    """
    Repository for agent operations.

    Handles CRUD operations and queries for agents.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, config: AgentConfig) -> UUID:
        """
        Create new agent.

        Args:
            config: Agent configuration

        Returns:
            Agent ID
        """
        # Create agent model
        agent = AgentModel(
            agent_id=config.agent_id,
            name=config.name,
            framework=config.framework,
            version=config.version,
            capabilities=[
                {"name": cap.name, "description": cap.description}
                for cap in config.capabilities
            ],
            max_concurrent_tasks=config.max_concurrent_tasks,
            cost_limit_daily=config.cost_limit_daily,
            cost_limit_monthly=config.cost_limit_monthly,
            llm_provider=config.llm_provider,
            llm_model=config.llm_model,
            metadata=config.metadata,
        )

        # Create agent state
        state = AgentStateModel(agent_id=config.agent_id)

        self.db.add(agent)
        self.db.add(state)
        await self.db.flush()

        return agent.agent_id

    async def get(self, agent_id: UUID) -> Optional[AgentConfig]:
        """
        Get agent by ID.

        Args:
            agent_id: Agent ID

        Returns:
            Agent configuration or None
        """
        result = await self.db.execute(
            select(AgentModel).where(AgentModel.agent_id == agent_id)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        return self._to_config(agent)

    async def get_by_name(self, name: str) -> Optional[AgentConfig]:
        """
        Get agent by name.

        Args:
            name: Agent name

        Returns:
            Agent configuration or None
        """
        result = await self.db.execute(
            select(AgentModel).where(AgentModel.name == name)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        return self._to_config(agent)

    async def list_all(
        self,
        status: Optional[AgentStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AgentConfig]:
        """
        List all agents.

        Args:
            status: Filter by status (optional)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of agent configurations
        """
        query = select(AgentModel)

        if status:
            query = query.where(AgentModel.status == status)

        query = query.limit(limit).offset(offset).order_by(AgentModel.created_at.desc())

        result = await self.db.execute(query)
        agents = result.scalars().all()

        return [self._to_config(agent) for agent in agents]

    async def find_by_capability(
        self,
        capability: str,
        status: Optional[AgentStatus] = None
    ) -> List[UUID]:
        """
        Find agents by capability.

        Args:
            capability: Capability name
            status: Filter by status (optional)

        Returns:
            List of agent IDs
        """
        query = select(AgentModel.agent_id).where(
            AgentModel.capabilities.op('@>')(cast(f'[{{"name": "{capability}"}}]', JSONB))
        )

        if status:
            query = query.where(AgentModel.status == status)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_status(self, agent_id: UUID, status: AgentStatus) -> bool:
        """
        Update agent status.

        Args:
            agent_id: Agent ID
            status: New status

        Returns:
            True if updated
        """
        result = await self.db.execute(
            update(AgentModel)
            .where(AgentModel.agent_id == agent_id)
            .values(status=status, updated_at=datetime.utcnow())
        )

        return result.rowcount > 0

    async def update_heartbeat(self, agent_id: UUID) -> bool:
        """
        Update agent heartbeat timestamp.

        Args:
            agent_id: Agent ID

        Returns:
            True if updated
        """
        result = await self.db.execute(
            update(AgentModel)
            .where(AgentModel.agent_id == agent_id)
            .values(last_heartbeat=datetime.utcnow(), updated_at=datetime.utcnow())
        )

        return result.rowcount > 0

    async def delete(self, agent_id: UUID) -> bool:
        """
        Delete agent.

        Args:
            agent_id: Agent ID

        Returns:
            True if deleted
        """
        result = await self.db.execute(
            delete(AgentModel).where(AgentModel.agent_id == agent_id)
        )

        return result.rowcount > 0

    async def get_state(self, agent_id: UUID) -> Optional[AgentState]:
        """
        Get agent state.

        Args:
            agent_id: Agent ID

        Returns:
            Agent state or None
        """
        result = await self.db.execute(
            select(AgentStateModel).where(AgentStateModel.agent_id == agent_id)
        )
        state_model = result.scalar_one_or_none()

        if not state_model:
            return None

        # Get agent config for status
        agent_result = await self.db.execute(
            select(AgentModel).where(AgentModel.agent_id == agent_id)
        )
        agent = agent_result.scalar_one_or_none()

        if not agent:
            return None

        return AgentState(
            agent_id=agent_id,
            status=agent.status,
            active_tasks=state_model.active_tasks,
            tasks_completed=state_model.tasks_completed,
            tasks_failed=state_model.tasks_failed,
            total_cost_today=state_model.total_cost_today,
            total_cost_month=state_model.total_cost_month,
            last_heartbeat=agent.last_heartbeat,
        )

    async def update_state(
        self,
        agent_id: UUID,
        active_tasks: Optional[int] = None,
        tasks_completed: Optional[int] = None,
        tasks_failed: Optional[int] = None,
        cost_delta: Optional[float] = None
    ) -> bool:
        """
        Update agent state.

        Args:
            agent_id: Agent ID
            active_tasks: New active task count (optional)
            tasks_completed: Increment completed count (optional)
            tasks_failed: Increment failed count (optional)
            cost_delta: Cost to add (optional)

        Returns:
            True if updated
        """
        # Build update values
        values = {"updated_at": datetime.utcnow()}

        if active_tasks is not None:
            values["active_tasks"] = active_tasks

        if tasks_completed is not None:
            values["tasks_completed"] = AgentStateModel.tasks_completed + tasks_completed

        if tasks_failed is not None:
            values["tasks_failed"] = AgentStateModel.tasks_failed + tasks_failed

        if cost_delta is not None:
            values["total_cost_today"] = AgentStateModel.total_cost_today + cost_delta
            values["total_cost_month"] = AgentStateModel.total_cost_month + cost_delta

        result = await self.db.execute(
            update(AgentStateModel)
            .where(AgentStateModel.agent_id == agent_id)
            .values(**values)
        )

        return result.rowcount > 0

    async def find_stale_agents(self, stale_threshold_seconds: int = 300) -> List[UUID]:
        """
        Find agents that haven't sent heartbeat recently.

        Args:
            stale_threshold_seconds: Threshold in seconds

        Returns:
            List of stale agent IDs
        """
        cutoff = datetime.utcnow() - timedelta(seconds=stale_threshold_seconds)

        result = await self.db.execute(
            select(AgentModel.agent_id).where(
                and_(
                    AgentModel.status == AgentStatus.ACTIVE,
                    or_(
                        AgentModel.last_heartbeat < cutoff,
                        AgentModel.last_heartbeat.is_(None)
                    )
                )
            )
        )

        return list(result.scalars().all())

    def _to_config(self, agent: AgentModel) -> AgentConfig:
        """Convert database model to AgentConfig."""
        return AgentConfig(
            agent_id=agent.agent_id,
            name=agent.name,
            framework=agent.framework,
            version=agent.version,
            capabilities=[
                AgentCapability(name=cap["name"], description=cap.get("description", ""))
                for cap in agent.capabilities
            ],
            max_concurrent_tasks=agent.max_concurrent_tasks,
            cost_limit_daily=agent.cost_limit_daily,
            cost_limit_monthly=agent.cost_limit_monthly,
            llm_provider=agent.llm_provider,
            llm_model=agent.llm_model,
            metadata=agent.metadata or {},
        )


class TaskRepository:
    """
    Repository for task operations.

    Handles CRUD operations and queries for tasks.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, task: Task) -> UUID:
        """
        Create new task.

        Args:
            task: Task configuration

        Returns:
            Task ID
        """
        task_model = TaskModel(
            task_id=task.task_id,
            capability=task.capability,
            priority=task.priority,
            input_data=task.input.data,
            timeout_seconds=task.timeout_seconds,
            max_retries=task.max_retries,
            estimated_cost=task.estimated_cost,
        )

        self.db.add(task_model)
        await self.db.flush()

        return task_model.task_id

    async def get(self, task_id: UUID) -> Optional[Task]:
        """
        Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None
        """
        result = await self.db.execute(
            select(TaskModel).where(TaskModel.task_id == task_id)
        )
        task_model = result.scalar_one_or_none()

        if not task_model:
            return None

        return self._to_task(task_model)

    async def update_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        assigned_agent_id: Optional[UUID] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update task status.

        Args:
            task_id: Task ID
            status: New status
            assigned_agent_id: Agent assignment (optional)
            error_message: Error message (optional)

        Returns:
            True if updated
        """
        values = {"status": status, "updated_at": datetime.utcnow()}

        if assigned_agent_id is not None:
            values["assigned_agent_id"] = assigned_agent_id

        if status == TaskStatus.RUNNING and "started_at" not in values:
            values["started_at"] = datetime.utcnow()

        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            values["completed_at"] = datetime.utcnow()

        if error_message:
            values["error_message"] = error_message

        result = await self.db.execute(
            update(TaskModel)
            .where(TaskModel.task_id == task_id)
            .values(**values)
        )

        return result.rowcount > 0

    async def complete(
        self,
        task_id: UUID,
        output_data: Dict,
        actual_cost: float
    ) -> bool:
        """
        Mark task as completed.

        Args:
            task_id: Task ID
            output_data: Task output
            actual_cost: Execution cost

        Returns:
            True if updated
        """
        result = await self.db.execute(
            update(TaskModel)
            .where(TaskModel.task_id == task_id)
            .values(
                status=TaskStatus.COMPLETED,
                output_data=output_data,
                actual_cost=actual_cost,
                completed_at=datetime.utcnow(),
            )
        )

        return result.rowcount > 0

    async def fail(
        self,
        task_id: UUID,
        error_message: str,
        increment_retry: bool = True
    ) -> bool:
        """
        Mark task as failed.

        Args:
            task_id: Task ID
            error_message: Error description
            increment_retry: Whether to increment retry count

        Returns:
            True if updated
        """
        values = {
            "status": TaskStatus.FAILED,
            "error_message": error_message,
            "completed_at": datetime.utcnow(),
        }

        if increment_retry:
            values["retry_count"] = TaskModel.retry_count + 1

        result = await self.db.execute(
            update(TaskModel)
            .where(TaskModel.task_id == task_id)
            .values(**values)
        )

        return result.rowcount > 0

    async def list_by_status(
        self,
        status: TaskStatus,
        capability: Optional[str] = None,
        limit: int = 100
    ) -> List[Task]:
        """
        List tasks by status.

        Args:
            status: Task status
            capability: Filter by capability (optional)
            limit: Maximum results

        Returns:
            List of tasks
        """
        query = select(TaskModel).where(TaskModel.status == status)

        if capability:
            query = query.where(TaskModel.capability == capability)

        query = query.limit(limit).order_by(TaskModel.created_at.asc())

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return [self._to_task(task) for task in tasks]

    async def list_by_agent(
        self,
        agent_id: UUID,
        status: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> List[Task]:
        """
        List tasks assigned to agent.

        Args:
            agent_id: Agent ID
            status: Filter by status (optional)
            limit: Maximum results

        Returns:
            List of tasks
        """
        query = select(TaskModel).where(TaskModel.assigned_agent_id == agent_id)

        if status:
            query = query.where(TaskModel.status == status)

        query = query.limit(limit).order_by(TaskModel.created_at.desc())

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return [self._to_task(task) for task in tasks]

    def _to_task(self, task_model: TaskModel) -> Task:
        """Convert database model to Task."""
        from backend.shared.models import TaskInput, TaskOutput

        return Task(
            task_id=task_model.task_id,
            capability=task_model.capability,
            input=TaskInput(data=task_model.input_data),
            output=TaskOutput(data=task_model.output_data) if task_model.output_data else None,
            priority=task_model.priority,
            status=task_model.status,
            assigned_agent_id=task_model.assigned_agent_id,
            timeout_seconds=task_model.timeout_seconds,
            max_retries=task_model.max_retries,
            retry_count=task_model.retry_count,
            estimated_cost=task_model.estimated_cost,
            actual_cost=task_model.actual_cost,
            created_at=task_model.created_at,
            started_at=task_model.started_at,
            completed_at=task_model.completed_at,
            error_message=task_model.error_message,
        )


class WorkflowRepository:
    """
    Repository for workflow operations.

    Handles CRUD operations for workflows and their executions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        nodes: List[Dict],
        edges: List[Dict],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        is_template: bool = False,
        organization_id: str = "default"
    ) -> UUID:
        """
        Create new workflow.

        Args:
            name: Workflow name
            nodes: List of workflow nodes (React Flow format)
            edges: List of workflow edges (React Flow format)
            description: Optional description
            tags: Optional tags
            created_by: Creator identifier
            is_template: Whether this is a template
            organization_id: Organization ID (defaults to "default")

        Returns:
            Workflow ID
        """
        workflow = WorkflowModel(
            name=name,
            description=description,
            tags=tags or [],
            nodes=nodes,
            edges=edges,
            created_by=created_by,
            is_template=is_template,
            organization_id=organization_id,
        )

        self.db.add(workflow)
        await self.db.commit()
        await self.db.refresh(workflow)

        return workflow.workflow_id

    async def get(self, workflow_id: UUID) -> Optional[Dict]:
        """
        Get workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow dict or None
        """
        result = await self.db.execute(
            select(WorkflowModel).where(WorkflowModel.workflow_id == workflow_id)
        )
        workflow = result.scalar_one_or_none()

        if not workflow:
            return None

        return self._to_dict(workflow)

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        is_template: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None
    ) -> List[Dict]:
        """
        List workflows with filters.

        Args:
            limit: Maximum results
            offset: Offset for pagination
            is_template: Filter by template flag
            tags: Filter by tags
            created_by: Filter by creator

        Returns:
            List of workflow dicts
        """
        query = select(WorkflowModel)

        # Apply filters
        if is_template is not None:
            query = query.where(WorkflowModel.is_template == is_template)

        if created_by:
            query = query.where(WorkflowModel.created_by == created_by)

        if tags:
            # PostgreSQL JSONB array contains check
            # Skip for SQLite (not supported)
            use_sqlite = os.getenv("USE_SQLITE", "").lower() == "true"
            if not use_sqlite:
                for tag in tags:
                    query = query.where(WorkflowModel.tags.contains([tag]))

        query = query.order_by(WorkflowModel.updated_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        workflows = result.scalars().all()

        return [self._to_dict(w) for w in workflows]

    async def update(
        self,
        workflow_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        nodes: Optional[List[Dict]] = None,
        edges: Optional[List[Dict]] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Update workflow.

        Args:
            workflow_id: Workflow ID
            name: New name (optional)
            description: New description (optional)
            nodes: New nodes (optional)
            edges: New edges (optional)
            tags: New tags (optional)

        Returns:
            True if updated
        """
        values = {"updated_at": datetime.utcnow()}

        if name is not None:
            values["name"] = name
        if description is not None:
            values["description"] = description
        if nodes is not None:
            values["nodes"] = nodes
        if edges is not None:
            values["edges"] = edges
        if tags is not None:
            values["tags"] = tags

        result = await self.db.execute(
            update(WorkflowModel)
            .where(WorkflowModel.workflow_id == workflow_id)
            .values(**values)
        )

        await self.db.commit()
        return result.rowcount > 0

    async def delete(self, workflow_id: UUID) -> bool:
        """
        Delete workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deleted
        """
        result = await self.db.execute(
            delete(WorkflowModel).where(WorkflowModel.workflow_id == workflow_id)
        )

        await self.db.commit()
        return result.rowcount > 0

    async def increment_execution_count(self, workflow_id: UUID) -> bool:
        """
        Increment execution count for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if updated
        """
        result = await self.db.execute(
            update(WorkflowModel)
            .where(WorkflowModel.workflow_id == workflow_id)
            .values(
                execution_count=WorkflowModel.execution_count + 1,
                last_executed_at=datetime.utcnow()
            )
        )

        await self.db.commit()
        return result.rowcount > 0

    async def update_statistics(
        self,
        workflow_id: UUID,
        total_cost: float,
        average_execution_time: float
    ) -> bool:
        """
        Update workflow statistics.

        Args:
            workflow_id: Workflow ID
            total_cost: Total accumulated cost
            average_execution_time: Average execution time in seconds

        Returns:
            True if updated
        """
        result = await self.db.execute(
            update(WorkflowModel)
            .where(WorkflowModel.workflow_id == workflow_id)
            .values(
                total_cost=total_cost,
                average_execution_time=average_execution_time
            )
        )

        await self.db.commit()
        return result.rowcount > 0

    def _to_dict(self, workflow: WorkflowModel) -> Dict:
        """Convert workflow model to dict."""
        return {
            "id": str(workflow.workflow_id),
            "name": workflow.name,
            "description": workflow.description,
            "tags": workflow.tags or [],
            "nodes": workflow.nodes,
            "edges": workflow.edges,
            "version": workflow.version,
            "isTemplate": workflow.is_template,
            "createdBy": workflow.created_by,
            "createdAt": workflow.created_at.isoformat(),
            "updatedAt": workflow.updated_at.isoformat(),
            "metadata": {
                "executionCount": workflow.execution_count,
                "totalCost": workflow.total_cost,
                "averageExecutionTime": workflow.average_execution_time,
                "lastExecuted": workflow.last_executed_at.isoformat() if workflow.last_executed_at else None,
            }
        }


class APIKeyRepository:
    """
    Repository for API key operations.

    Handles CRUD operations and queries for API keys with support for:
    - Key creation with SHA-256 hashing
    - Key verification (including previous key during rotation)
    - Rate limiting and quota tracking
    - IP whitelisting
    - Key rotation with grace period
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        organization_id: str,
        name: str,
        key_hash: str,
        key_prefix: str,
        permissions: Optional[List[str]] = None,
        rate_limit_per_second: int = 100,
        monthly_quota: Optional[int] = None,
        ip_whitelist: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None,
        created_by: Optional[str] = None
    ) -> int:
        """
        Create new API key.

        Args:
            organization_id: Organization ID
            name: Descriptive name for the key
            key_hash: SHA-256 hash of the key
            key_prefix: Key prefix for display (e.g., "ao_live_abc1")
            permissions: List of permission strings
            rate_limit_per_second: Rate limit (default: 100)
            monthly_quota: Monthly request quota (None = unlimited)
            ip_whitelist: List of allowed IP addresses (None = all allowed)
            expires_at: Expiration timestamp
            created_by: User ID who created the key

        Returns:
            API key ID
        """
        api_key = APIKeyModel(
            organization_id=organization_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            permissions=permissions or [],
            rate_limit_per_second=rate_limit_per_second,
            monthly_quota=monthly_quota,
            ip_whitelist=ip_whitelist or [],
            expires_at=expires_at,
            created_by=created_by,
            is_active=True,
        )

        self.db.add(api_key)
        await self.db.flush()

        return api_key.id

    async def get_by_id(self, key_id: int) -> Optional[APIKeyModel]:
        """
        Get API key by ID.

        Args:
            key_id: API key ID

        Returns:
            API key model or None
        """
        result = await self.db.execute(
            select(APIKeyModel).where(APIKeyModel.id == key_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> Optional[APIKeyModel]:
        """
        Get API key by hash.

        Args:
            key_hash: SHA-256 hash of the key

        Returns:
            API key model or None
        """
        result = await self.db.execute(
            select(APIKeyModel).where(APIKeyModel.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def verify_key(self, key_hash: str) -> Optional[Dict]:
        """
        Verify API key and return key details if valid.

        Checks both current key hash and previous key hash (for rotation grace period).

        Args:
            key_hash: SHA-256 hash of the key to verify

        Returns:
            Dict with key details if valid, None otherwise
        """
        now = datetime.utcnow()

        # Check current key
        result = await self.db.execute(
            select(APIKeyModel).where(
                and_(
                    APIKeyModel.key_hash == key_hash,
                    APIKeyModel.is_active == True,
                    or_(
                        APIKeyModel.expires_at.is_(None),
                        APIKeyModel.expires_at > now
                    )
                )
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key:
            # Update last_used_at
            await self.update_last_used(api_key.id)
            return self._to_dict(api_key)

        # Check previous key (during rotation grace period)
        result = await self.db.execute(
            select(APIKeyModel).where(
                and_(
                    APIKeyModel.previous_key_hash == key_hash,
                    APIKeyModel.is_active == True,
                    APIKeyModel.previous_key_expires_at.is_not(None),
                    APIKeyModel.previous_key_expires_at > now
                )
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key:
            # Update last_used_at
            await self.update_last_used(api_key.id)
            return self._to_dict(api_key)

        return None

    async def list_by_organization(
        self,
        organization_id: str,
        include_inactive: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        List API keys for organization.

        Args:
            organization_id: Organization ID
            include_inactive: Include inactive/revoked keys
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of API key dicts
        """
        query = select(APIKeyModel).where(APIKeyModel.organization_id == organization_id)

        if not include_inactive:
            query = query.where(APIKeyModel.is_active == True)

        query = query.order_by(APIKeyModel.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        api_keys = result.scalars().all()

        return [self._to_dict(key) for key in api_keys]

    async def update_last_used(self, key_id: int) -> bool:
        """
        Update last_used_at timestamp.

        Args:
            key_id: API key ID

        Returns:
            True if updated
        """
        result = await self.db.execute(
            update(APIKeyModel)
            .where(APIKeyModel.id == key_id)
            .values(last_used_at=datetime.utcnow())
        )

        return result.rowcount > 0

    async def revoke(self, key_id: int, revoked_by: Optional[str] = None) -> bool:
        """
        Revoke API key.

        Args:
            key_id: API key ID
            revoked_by: User ID who revoked the key

        Returns:
            True if revoked
        """
        result = await self.db.execute(
            update(APIKeyModel)
            .where(APIKeyModel.id == key_id)
            .values(
                is_active=False,
                revoked_at=datetime.utcnow(),
                revoked_by=revoked_by
            )
        )

        return result.rowcount > 0

    async def rotate(
        self,
        key_id: int,
        new_key_hash: str,
        new_key_prefix: str,
        grace_period_hours: int = 24
    ) -> bool:
        """
        Rotate API key with grace period.

        Moves current key to previous_key_hash and sets new key as current.
        Previous key remains valid for grace_period_hours.

        Args:
            key_id: API key ID
            new_key_hash: SHA-256 hash of new key
            new_key_prefix: Prefix of new key for display
            grace_period_hours: Hours to keep old key valid (default: 24)

        Returns:
            True if rotated
        """
        # Get current key
        api_key = await self.get_by_id(key_id)
        if not api_key:
            return False

        # Calculate grace period expiration
        previous_key_expires_at = datetime.utcnow() + timedelta(hours=grace_period_hours)

        # Rotate the key
        result = await self.db.execute(
            update(APIKeyModel)
            .where(APIKeyModel.id == key_id)
            .values(
                previous_key_hash=api_key.key_hash,
                previous_key_expires_at=previous_key_expires_at,
                key_hash=new_key_hash,
                key_prefix=new_key_prefix
            )
        )

        return result.rowcount > 0

    async def update_rate_limit(self, key_id: int, rate_limit_per_second: int) -> bool:
        """
        Update rate limit for API key.

        Args:
            key_id: API key ID
            rate_limit_per_second: New rate limit

        Returns:
            True if updated
        """
        result = await self.db.execute(
            update(APIKeyModel)
            .where(APIKeyModel.id == key_id)
            .values(rate_limit_per_second=rate_limit_per_second)
        )

        return result.rowcount > 0

    async def update_ip_whitelist(self, key_id: int, ip_whitelist: List[str]) -> bool:
        """
        Update IP whitelist for API key.

        Args:
            key_id: API key ID
            ip_whitelist: List of allowed IP addresses

        Returns:
            True if updated
        """
        result = await self.db.execute(
            update(APIKeyModel)
            .where(APIKeyModel.id == key_id)
            .values(ip_whitelist=ip_whitelist)
        )

        return result.rowcount > 0

    def _to_dict(self, api_key: APIKeyModel) -> Dict:
        """Convert API key model to dict."""
        return {
            "id": api_key.id,
            "organization_id": api_key.organization_id,
            "name": api_key.name,
            "key_prefix": api_key.key_prefix,
            "permissions": api_key.permissions or [],
            "rate_limit_per_second": api_key.rate_limit_per_second,
            "monthly_quota": api_key.monthly_quota,
            "ip_whitelist": api_key.ip_whitelist or [],
            "is_active": api_key.is_active,
            "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
            "created_by": api_key.created_by,
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            "revoked_at": api_key.revoked_at.isoformat() if api_key.revoked_at else None,
            "revoked_by": api_key.revoked_by,
            "has_previous_key": api_key.previous_key_hash is not None,
            "previous_key_expires_at": api_key.previous_key_expires_at.isoformat() if api_key.previous_key_expires_at else None,
        }
