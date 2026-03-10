"""
Supervisor Orchestration API

REST endpoints for multi-agent coordination:
- Supervisor configuration
- Agent registry management
- Task execution
- Execution monitoring

Competitive advantage: AWS Agent Squad + Microsoft AutoGen patterns.
Solves complex multi-agent orchestration at scale.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime

from backend.database.session import get_db
from backend.shared.supervisor_service import SupervisorExecutionService
from backend.shared.supervisor_models import (
    SupervisorConfigModel, SupervisorExecutionModel,
    AgentRegistryModel, TaskAssignmentModel,
    SupervisorMode, RoutingStrategy, AgentRole, TaskStatus,
    SupervisorConfig
)
from backend.shared.auth_utils import get_current_organization
from sqlalchemy import select, and_, desc, update


router = APIRouter(prefix="/api/v1/supervisor", tags=["supervisor-orchestration"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSupervisorConfigRequest(BaseModel):
    """Request to create supervisor configuration"""
    name: str = Field(..., description="Supervisor name")
    description: Optional[str] = Field(None, description="Supervisor description")
    mode: str = Field(..., description="Orchestration mode")
    routing_strategy: str = Field("capability_match", description="Routing strategy")
    agent_pool: List[str] = Field(..., description="List of agent IDs")
    agent_capabilities: Optional[dict] = Field(None, description="Agent capabilities map")
    max_agents_concurrent: int = Field(3, description="Max concurrent agents")
    max_conversation_turns: Optional[int] = Field(None, description="Max turns for group chat")
    timeout_seconds: int = Field(300, description="Timeout in seconds")
    llm_model: Optional[str] = Field(None, description="LLM model for supervisor")
    llm_temperature: float = Field(0.7, description="LLM temperature")
    llm_system_prompt: Optional[str] = Field(None, description="System prompt")
    routing_rules: Optional[List[dict]] = Field(None, description="Custom routing rules")
    auto_decompose_tasks: bool = Field(True, description="Auto-decompose tasks")
    decomposition_prompt: Optional[str] = Field(None, description="Decomposition prompt")


class SupervisorConfigResponse(BaseModel):
    """Response model for supervisor configuration"""
    config_id: UUID
    organization_id: str
    name: str
    description: Optional[str]
    mode: str
    routing_strategy: str
    agent_pool: List[str]
    max_agents_concurrent: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ExecuteTaskRequest(BaseModel):
    """Request to execute task with supervisor"""
    config_id: UUID = Field(..., description="Supervisor config ID")
    task: str = Field(..., description="Task to execute")
    workflow_execution_id: Optional[UUID] = Field(None, description="Workflow execution ID")


class SupervisorExecutionResponse(BaseModel):
    """Response model for supervisor execution"""
    execution_id: UUID
    config_id: UUID
    status: str
    mode: str
    input_task: str
    output_result: Optional[dict]
    subtasks: Optional[List[dict]]
    agent_assignments: Optional[dict]
    routing_decisions: Optional[List[dict]]
    conversation_history: Optional[List[dict]]
    total_agents_used: Optional[int]
    total_turns: Optional[int]
    duration_ms: Optional[float]
    total_cost: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class RegisterAgentRequest(BaseModel):
    """Request to register new agent"""
    agent_id: str = Field(..., description="Unique agent ID")
    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    role: str = Field(..., description="Agent role")
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")
    specialization: Optional[str] = Field(None, description="Agent specialization")
    agent_type: Optional[str] = Field(None, description="Agent type")
    llm_model: Optional[str] = Field(None, description="LLM model")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    tools: List[str] = Field(default_factory=list, description="Available tools")
    max_concurrent_tasks: int = Field(5, description="Max concurrent tasks")


class AgentResponse(BaseModel):
    """Response model for agent"""
    agent_id: str
    organization_id: str
    name: str
    role: str
    capabilities: List[str]
    specialization: Optional[str]
    is_active: bool
    current_load: int
    max_concurrent_tasks: int
    total_tasks_completed: int
    success_rate: Optional[float]

    class Config:
        from_attributes = True


class TaskAssignmentResponse(BaseModel):
    """Response model for task assignment"""
    assignment_id: UUID
    execution_id: UUID
    agent_id: str
    task_id: str
    task_description: str
    status: str
    priority: int
    assigned_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[float]
    cost: float

    class Config:
        from_attributes = True


# ============================================================================
# Supervisor Configuration Endpoints
# ============================================================================

@router.post(
    "/configs",
    response_model=SupervisorConfigResponse,
    summary="Create supervisor configuration",
    description="Create new supervisor configuration for multi-agent orchestration"
)
async def create_supervisor_config(
    request: CreateSupervisorConfigRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Create supervisor configuration.

    Defines how supervisor will coordinate agents:
    - Orchestration mode (sequential, concurrent, group_chat, etc.)
    - Routing strategy (capability_match, load_balanced, etc.)
    - Agent pool
    - Execution settings
    """
    from uuid import uuid4

    config_model = SupervisorConfigModel(
        config_id=uuid4(),
        organization_id=organization_id,
        name=request.name,
        description=request.description,
        mode=request.mode,
        routing_strategy=request.routing_strategy,
        agent_pool=request.agent_pool,
        agent_capabilities=request.agent_capabilities,
        max_agents_concurrent=request.max_agents_concurrent,
        max_conversation_turns=request.max_conversation_turns,
        timeout_seconds=request.timeout_seconds,
        llm_model=request.llm_model,
        llm_temperature=request.llm_temperature,
        llm_system_prompt=request.llm_system_prompt,
        routing_rules=request.routing_rules,
        auto_decompose_tasks=request.auto_decompose_tasks,
        decomposition_prompt=request.decomposition_prompt,
        is_active=True
    )

    db.add(config_model)
    await db.commit()
    await db.refresh(config_model)

    return SupervisorConfigResponse.model_validate(config_model)


@router.get(
    "/configs/{config_id}",
    response_model=SupervisorConfigResponse,
    summary="Get supervisor configuration",
    description="Retrieve supervisor configuration details"
)
async def get_supervisor_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Get supervisor configuration details."""
    stmt = select(SupervisorConfigModel).where(
        and_(
            SupervisorConfigModel.config_id == config_id,
            SupervisorConfigModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Supervisor config not found")

    return SupervisorConfigResponse.model_validate(config)


@router.get(
    "/configs",
    response_model=List[SupervisorConfigResponse],
    summary="List supervisor configurations",
    description="List all supervisor configurations for organization"
)
async def list_supervisor_configs(
    active_only: bool = Query(True, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """List all supervisor configurations."""
    query = select(SupervisorConfigModel).where(
        SupervisorConfigModel.organization_id == organization_id
    )

    if active_only:
        query = query.where(SupervisorConfigModel.is_active == True)

    query = query.order_by(desc(SupervisorConfigModel.created_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    configs = result.scalars().all()

    return [SupervisorConfigResponse.model_validate(c) for c in configs]


@router.put(
    "/configs/{config_id}",
    response_model=SupervisorConfigResponse,
    summary="Update supervisor configuration",
    description="Update existing supervisor configuration"
)
async def update_supervisor_config(
    config_id: UUID,
    request: CreateSupervisorConfigRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Update supervisor configuration."""
    stmt = select(SupervisorConfigModel).where(
        and_(
            SupervisorConfigModel.config_id == config_id,
            SupervisorConfigModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Supervisor config not found")

    # Update fields
    config.name = request.name
    config.description = request.description
    config.mode = request.mode
    config.routing_strategy = request.routing_strategy
    config.agent_pool = request.agent_pool
    config.agent_capabilities = request.agent_capabilities
    config.max_agents_concurrent = request.max_agents_concurrent
    config.max_conversation_turns = request.max_conversation_turns
    config.timeout_seconds = request.timeout_seconds
    config.llm_model = request.llm_model
    config.llm_temperature = request.llm_temperature
    config.llm_system_prompt = request.llm_system_prompt
    config.routing_rules = request.routing_rules
    config.auto_decompose_tasks = request.auto_decompose_tasks
    config.decomposition_prompt = request.decomposition_prompt
    config.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(config)

    return SupervisorConfigResponse.model_validate(config)


@router.delete(
    "/configs/{config_id}",
    summary="Delete supervisor configuration",
    description="Deactivate supervisor configuration"
)
async def delete_supervisor_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Deactivate supervisor configuration."""
    stmt = update(SupervisorConfigModel).where(
        and_(
            SupervisorConfigModel.config_id == config_id,
            SupervisorConfigModel.organization_id == organization_id
        )
    ).values(is_active=False, updated_at=datetime.utcnow())

    await db.execute(stmt)
    await db.commit()

    return {"message": "Supervisor config deactivated"}


# ============================================================================
# Task Execution Endpoints
# ============================================================================

@router.post(
    "/execute",
    response_model=SupervisorExecutionResponse,
    summary="Execute task with supervisor",
    description="Execute task using supervisor orchestration"
)
async def execute_supervised_task(
    request: ExecuteTaskRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Execute task with supervisor orchestration.

    The supervisor will:
    1. Decompose task into subtasks (if configured)
    2. Route subtasks to best-fit agents
    3. Execute using configured mode (sequential, concurrent, etc.)
    4. Aggregate results
    """
    # Fetch config
    stmt = select(SupervisorConfigModel).where(
        and_(
            SupervisorConfigModel.config_id == request.config_id,
            SupervisorConfigModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    config_model = result.scalar_one_or_none()

    if not config_model:
        raise HTTPException(status_code=404, detail="Supervisor config not found")

    if not config_model.is_active:
        raise HTTPException(status_code=400, detail="Supervisor config is not active")

    # Convert to dataclass
    config = SupervisorConfig(
        config_id=config_model.config_id,
        organization_id=config_model.organization_id,
        name=config_model.name,
        mode=SupervisorMode(config_model.mode),
        routing_strategy=RoutingStrategy(config_model.routing_strategy),
        agent_pool=config_model.agent_pool,
        description=config_model.description,
        agent_capabilities=config_model.agent_capabilities,
        max_agents_concurrent=config_model.max_agents_concurrent,
        max_conversation_turns=config_model.max_conversation_turns,
        timeout_seconds=config_model.timeout_seconds,
        llm_model=config_model.llm_model,
        llm_temperature=config_model.llm_temperature,
        llm_system_prompt=config_model.llm_system_prompt,
        routing_rules=config_model.routing_rules,
        auto_decompose_tasks=config_model.auto_decompose_tasks,
        decomposition_prompt=config_model.decomposition_prompt
    )

    # Execute
    execution_service = SupervisorExecutionService(db)
    execution = await execution_service.execute_supervised_task(
        config=config,
        input_task=request.task,
        workflow_execution_id=request.workflow_execution_id
    )

    return SupervisorExecutionResponse(
        execution_id=execution.execution_id,
        config_id=execution.config_id,
        status=execution.status,
        mode=execution.mode.value,
        input_task=execution.input_task,
        output_result=execution.output_result,
        subtasks=execution.subtasks,
        agent_assignments=execution.agent_assignments,
        routing_decisions=execution.routing_decisions,
        conversation_history=execution.conversation_history,
        total_agents_used=execution.total_agents_used,
        total_turns=execution.total_turns,
        duration_ms=execution.duration_ms,
        total_cost=execution.total_cost,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        error_message=execution.error_message
    )


@router.get(
    "/executions/{execution_id}",
    response_model=SupervisorExecutionResponse,
    summary="Get execution details",
    description="Retrieve supervisor execution details"
)
async def get_supervisor_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Get supervisor execution details."""
    stmt = select(SupervisorExecutionModel).where(
        and_(
            SupervisorExecutionModel.execution_id == execution_id,
            SupervisorExecutionModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return SupervisorExecutionResponse.model_validate(execution)


@router.get(
    "/executions",
    response_model=List[SupervisorExecutionResponse],
    summary="List executions",
    description="List all supervisor executions"
)
async def list_supervisor_executions(
    config_id: Optional[UUID] = Query(None, description="Filter by config ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """List all supervisor executions."""
    query = select(SupervisorExecutionModel).where(
        SupervisorExecutionModel.organization_id == organization_id
    )

    if config_id:
        query = query.where(SupervisorExecutionModel.config_id == config_id)

    if status:
        query = query.where(SupervisorExecutionModel.status == status)

    query = query.order_by(desc(SupervisorExecutionModel.created_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    executions = result.scalars().all()

    return [SupervisorExecutionResponse.model_validate(e) for e in executions]


# ============================================================================
# Agent Registry Endpoints
# ============================================================================

@router.post(
    "/agents",
    response_model=AgentResponse,
    summary="Register agent",
    description="Register new agent in registry"
)
async def register_agent(
    request: RegisterAgentRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Register agent in registry.

    Makes agent available for supervisor orchestration.
    """
    # Check if agent already exists
    stmt = select(AgentRegistryModel).where(
        and_(
            AgentRegistryModel.agent_id == request.agent_id,
            AgentRegistryModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Agent already registered")

    agent_model = AgentRegistryModel(
        agent_id=request.agent_id,
        organization_id=organization_id,
        name=request.name,
        description=request.description,
        role=request.role,
        capabilities=request.capabilities,
        specialization=request.specialization,
        agent_type=request.agent_type,
        llm_model=request.llm_model,
        system_prompt=request.system_prompt,
        tools=request.tools,
        max_concurrent_tasks=request.max_concurrent_tasks,
        is_active=True,
        current_load=0,
        total_tasks_completed=0,
        total_tasks_failed=0
    )

    db.add(agent_model)
    await db.commit()
    await db.refresh(agent_model)

    return AgentResponse.model_validate(agent_model)


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent details",
    description="Retrieve agent details from registry"
)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Get agent details."""
    stmt = select(AgentRegistryModel).where(
        and_(
            AgentRegistryModel.agent_id == agent_id,
            AgentRegistryModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse.model_validate(agent)


@router.get(
    "/agents",
    response_model=List[AgentResponse],
    summary="List agents",
    description="List all registered agents"
)
async def list_agents(
    role: Optional[str] = Query(None, description="Filter by role"),
    active_only: bool = Query(True, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """List all registered agents."""
    query = select(AgentRegistryModel).where(
        AgentRegistryModel.organization_id == organization_id
    )

    if role:
        query = query.where(AgentRegistryModel.role == role)

    if active_only:
        query = query.where(AgentRegistryModel.is_active == True)

    query = query.order_by(AgentRegistryModel.name).limit(limit).offset(offset)

    result = await db.execute(query)
    agents = result.scalars().all()

    return [AgentResponse.model_validate(a) for a in agents]


@router.put(
    "/agents/{agent_id}/status",
    summary="Update agent status",
    description="Activate or deactivate agent"
)
async def update_agent_status(
    agent_id: str,
    is_active: bool = Query(..., description="Active status"),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Update agent active status."""
    stmt = update(AgentRegistryModel).where(
        and_(
            AgentRegistryModel.agent_id == agent_id,
            AgentRegistryModel.organization_id == organization_id
        )
    ).values(is_active=is_active, updated_at=datetime.utcnow())

    await db.execute(stmt)
    await db.commit()

    return {"message": f"Agent {'activated' if is_active else 'deactivated'}"}


# ============================================================================
# Task Assignment Endpoints
# ============================================================================

@router.get(
    "/executions/{execution_id}/tasks",
    response_model=List[TaskAssignmentResponse],
    summary="Get execution tasks",
    description="Get all task assignments for execution"
)
async def get_execution_tasks(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Get all task assignments for execution."""
    stmt = select(TaskAssignmentModel).where(
        and_(
            TaskAssignmentModel.execution_id == execution_id,
            TaskAssignmentModel.organization_id == organization_id
        )
    ).order_by(TaskAssignmentModel.assigned_at)

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return [TaskAssignmentResponse.model_validate(t) for t in tasks]


@router.get(
    "/agents/{agent_id}/tasks",
    response_model=List[TaskAssignmentResponse],
    summary="Get agent tasks",
    description="Get all tasks assigned to agent"
)
async def get_agent_tasks(
    agent_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Get all tasks assigned to agent."""
    query = select(TaskAssignmentModel).where(
        and_(
            TaskAssignmentModel.agent_id == agent_id,
            TaskAssignmentModel.organization_id == organization_id
        )
    )

    if status:
        query = query.where(TaskAssignmentModel.status == status)

    query = query.order_by(desc(TaskAssignmentModel.assigned_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    tasks = result.scalars().all()

    return [TaskAssignmentResponse.model_validate(t) for t in tasks]


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get(
    "/analytics/execution/{execution_id}",
    summary="Get execution analytics",
    description="Get detailed analytics for execution"
)
async def get_execution_analytics(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Get execution analytics.

    Returns:
    - Task breakdown
    - Agent utilization
    - Cost distribution
    - Performance metrics
    """
    # Fetch execution
    exec_stmt = select(SupervisorExecutionModel).where(
        and_(
            SupervisorExecutionModel.execution_id == execution_id,
            SupervisorExecutionModel.organization_id == organization_id
        )
    )
    exec_result = await db.execute(exec_stmt)
    execution = exec_result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Fetch task assignments
    tasks_stmt = select(TaskAssignmentModel).where(
        TaskAssignmentModel.execution_id == execution_id
    )
    tasks_result = await db.execute(tasks_stmt)
    tasks = tasks_result.scalars().all()

    # Calculate metrics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == "completed"])
    failed_tasks = len([t for t in tasks if t.status == "failed"])

    # Agent utilization
    agent_task_count = {}
    for task in tasks:
        agent_task_count[task.agent_id] = agent_task_count.get(task.agent_id, 0) + 1

    return {
        "execution_id": str(execution_id),
        "status": execution.status,
        "mode": execution.mode,
        "metrics": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": (completed_tasks / total_tasks) if total_tasks > 0 else 0,
            "total_agents_used": execution.total_agents_used,
            "total_cost": execution.total_cost,
            "duration_ms": execution.duration_ms
        },
        "agent_utilization": agent_task_count,
        "cost_by_agent": execution.cost_by_agent
    }
