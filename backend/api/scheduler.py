"""
Scheduler API Endpoints

Provides REST API for managing scheduled workflows:
- CRUD operations for schedules
- External trigger endpoint for BYOS mode
- Execution history
- Organization limits management
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Header, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.shared.scheduler_service import (
    SchedulerService,
    SchedulerError,
    ScheduleLimitExceeded,
    InvalidCronExpression,
    ScheduleNotFound,
)
from backend.shared.scheduler_models import (
    ScheduleType,
    ScheduleStatus,
    COMMON_CRON_EXPRESSIONS,
    SCHEDULE_TIER_CONFIGS,
)
from backend.shared.workflow_models import (
    WorkflowModel, WorkflowExecutionModel,
    Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution,
    WorkflowStatus, ExecutionStatus, NodeType
)
from backend.services.workflow_executor import WorkflowExecutor

router = APIRouter(prefix="/api/schedules", tags=["Schedules"])


# ==================== Request/Response Models ====================

class CreateScheduleRequest(BaseModel):
    """Request to create a new schedule"""
    workflow_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

    schedule_type: str = Field(..., description="cron, interval, or once")
    cron_expression: Optional[str] = Field(None, description="Cron expression (e.g., '0 9 * * *')")
    interval_seconds: Optional[int] = Field(None, ge=60, description="Interval in seconds")
    run_at: Optional[datetime] = Field(None, description="Specific datetime for one-time runs")

    timezone: str = Field(default="UTC")
    input_data: Optional[dict] = Field(default_factory=dict)

    # BYOS mode
    external_scheduler: bool = Field(
        default=False,
        description="If true, use external scheduler (BYOS mode)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Daily Report Generator",
                "schedule_type": "cron",
                "cron_expression": "0 9 * * *",
                "timezone": "America/New_York",
                "input_data": {"report_type": "daily_summary"}
            }
        }


class UpdateScheduleRequest(BaseModel):
    """Request to update a schedule"""
    name: Optional[str] = None
    description: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    timezone: Optional[str] = None
    input_data: Optional[dict] = None
    status: Optional[str] = None


class ScheduleResponse(BaseModel):
    """Response model for a schedule"""
    schedule_id: UUID
    workflow_id: UUID
    organization_id: str
    name: str
    description: Optional[str]

    schedule_type: str
    cron_expression: Optional[str]
    interval_seconds: Optional[int]
    run_at: Optional[datetime]
    timezone: str

    status: str
    input_data: dict

    # Execution info
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    next_run_at: Optional[datetime]

    # Statistics
    total_runs: int
    successful_runs: int
    failed_runs: int
    total_cost: float

    # BYOS
    external_scheduler: bool
    external_trigger_url: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScheduleHistoryResponse(BaseModel):
    """Response model for execution history"""
    history_id: UUID
    schedule_id: UUID
    workflow_id: UUID
    execution_id: Optional[UUID]

    scheduled_for: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]

    status: str
    trigger_source: str
    error_message: Optional[str]
    cost: float
    tokens_used: Optional[int]

    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationLimitsResponse(BaseModel):
    """Response model for organization limits"""
    organization_id: str
    tier: str
    max_schedules: int
    min_interval_seconds: int
    max_concurrent_executions: int
    current_schedule_count: int
    executions_this_month: int
    cost_this_month: float
    per_execution_cost: float

    class Config:
        from_attributes = True


class ExternalTriggerRequest(BaseModel):
    """Request for external trigger (BYOS)"""
    input_data: Optional[dict] = None


class CronHelpersResponse(BaseModel):
    """Response with common cron expressions"""
    expressions: dict
    tier_limits: dict


# ==================== Dependency ====================

async def get_scheduler_service(db=Depends(get_db)) -> SchedulerService:
    return SchedulerService(db)


def get_organization_id(x_organization_id: str = Header(...)) -> str:
    """Extract organization ID from header"""
    return x_organization_id


# ==================== Endpoints ====================

@router.post("", response_model=ScheduleResponse)
async def create_schedule(
    request: CreateScheduleRequest,
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """
    Create a new scheduled workflow.

    Supports three schedule types:
    - **cron**: Standard cron expressions (e.g., "0 9 * * *" for 9 AM daily)
    - **interval**: Fixed interval in seconds (minimum depends on tier)
    - **once**: One-time execution at a specific datetime

    For BYOS (Bring Your Own Scheduler) mode, set `external_scheduler: true`.
    You'll receive a trigger URL that your scheduler (EventBridge, Cloud Scheduler, etc.) can call.
    """
    try:
        schedule = await service.create_schedule(
            organization_id=organization_id,
            workflow_id=request.workflow_id,
            name=request.name,
            description=request.description,
            schedule_type=ScheduleType(request.schedule_type),
            cron_expression=request.cron_expression,
            interval_seconds=request.interval_seconds,
            run_at=request.run_at,
            timezone=request.timezone,
            input_data=request.input_data,
            external_scheduler=request.external_scheduler,
        )

        return _schedule_to_response(schedule)

    except ScheduleLimitExceeded as e:
        raise HTTPException(status_code=402, detail=str(e))
    except InvalidCronExpression as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SchedulerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ScheduleResponse])
async def list_schedules(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """List all schedules for the organization"""
    status_enum = ScheduleStatus(status) if status else None
    schedules = await service.get_schedules_for_organization(
        organization_id=organization_id,
        status=status_enum,
        limit=limit,
        offset=offset,
    )
    return [_schedule_to_response(s) for s in schedules]


@router.get("/helpers", response_model=CronHelpersResponse)
async def get_cron_helpers():
    """
    Get common cron expressions and tier limits.

    Useful for building schedule UIs with preset options.
    """
    return CronHelpersResponse(
        expressions=COMMON_CRON_EXPRESSIONS,
        tier_limits=SCHEDULE_TIER_CONFIGS,
    )


@router.get("/limits", response_model=OrganizationLimitsResponse)
async def get_organization_limits(
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """Get schedule limits and usage for the organization"""
    limits = await service._get_or_create_limits(organization_id)
    return OrganizationLimitsResponse(
        organization_id=limits.organization_id,
        tier=limits.tier,
        max_schedules=limits.max_schedules,
        min_interval_seconds=limits.min_interval_seconds,
        max_concurrent_executions=limits.max_concurrent_executions,
        current_schedule_count=limits.current_schedule_count,
        executions_this_month=limits.executions_this_month,
        cost_this_month=limits.cost_this_month,
        per_execution_cost=limits.per_execution_cost,
    )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """Get a specific schedule"""
    schedule = await service.get_schedule(schedule_id)
    if not schedule or schedule.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _schedule_to_response(schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    request: UpdateScheduleRequest,
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """Update a schedule"""
    # Verify ownership
    schedule = await service.get_schedule(schedule_id)
    if not schedule or schedule.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    try:
        updates = request.model_dump(exclude_unset=True)
        schedule = await service.update_schedule(schedule_id, **updates)
        return _schedule_to_response(schedule)

    except InvalidCronExpression as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SchedulerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: UUID,
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """Delete a schedule"""
    schedule = await service.get_schedule(schedule_id)
    if not schedule or schedule.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await service.delete_schedule(schedule_id)
    return {"status": "deleted", "schedule_id": str(schedule_id)}


@router.post("/{schedule_id}/pause", response_model=ScheduleResponse)
async def pause_schedule(
    schedule_id: UUID,
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """Pause a schedule"""
    schedule = await service.get_schedule(schedule_id)
    if not schedule or schedule.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule = await service.pause_schedule(schedule_id)
    return _schedule_to_response(schedule)


@router.post("/{schedule_id}/resume", response_model=ScheduleResponse)
async def resume_schedule(
    schedule_id: UUID,
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """Resume a paused schedule"""
    schedule = await service.get_schedule(schedule_id)
    if not schedule or schedule.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule = await service.resume_schedule(schedule_id)
    return _schedule_to_response(schedule)


@router.get("/{schedule_id}/history", response_model=List[ScheduleHistoryResponse])
async def get_schedule_history(
    schedule_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """Get execution history for a schedule"""
    schedule = await service.get_schedule(schedule_id)
    if not schedule or schedule.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    history = await service.get_execution_history(
        schedule_id=schedule_id,
        limit=limit,
        offset=offset,
    )
    return [_history_to_response(h) for h in history]


@router.post("/{schedule_id}/regenerate-token")
async def regenerate_trigger_token(
    schedule_id: UUID,
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """
    Regenerate the external trigger token for BYOS mode.

    Use this if you need to rotate the token for security reasons.
    """
    schedule = await service.get_schedule(schedule_id)
    if not schedule or schedule.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if not schedule.external_scheduler:
        raise HTTPException(
            status_code=400,
            detail="This schedule is not in BYOS mode"
        )

    new_token = await service.regenerate_trigger_token(schedule_id)
    return {
        "schedule_id": str(schedule_id),
        "trigger_url": f"/api/schedules/trigger/{new_token}",
    }


# ==================== External Trigger Endpoint ====================

@router.post("/trigger/{trigger_token}")
async def external_trigger(
    trigger_token: str,
    background_tasks: BackgroundTasks,
    request: Optional[ExternalTriggerRequest] = None,
    service: SchedulerService = Depends(get_scheduler_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a scheduled workflow externally (BYOS mode).

    This endpoint is called by external schedulers (AWS EventBridge, GCP Cloud Scheduler,
    Kubernetes CronJob, etc.) to trigger workflow execution.

    The trigger token is provided when creating a schedule with `external_scheduler: true`.
    """
    schedule = await service.trigger_by_token(
        trigger_token=trigger_token,
        input_data=request.input_data if request else None,
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Invalid or inactive trigger token")

    # Get the workflow to execute
    query = select(WorkflowModel).where(WorkflowModel.workflow_id == schedule.workflow_id)
    result = await db.execute(query)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.status == WorkflowStatus.ARCHIVED.value:
        raise HTTPException(status_code=400, detail="Cannot execute archived workflow")

    # Merge input data from schedule and request
    input_data = schedule.input_data or {}
    if request and request.input_data:
        input_data.update(request.input_data)

    # Create execution record
    execution = WorkflowExecutionModel(
        execution_id=uuid4(),
        workflow_id=schedule.workflow_id,
        workflow_version=workflow.version,
        organization_id=schedule.organization_id,
        triggered_by="scheduler",
        trigger_source=f"schedule:{schedule.schedule_id}",
        status=ExecutionStatus.PENDING.value,
        input_data=input_data,
        node_states={}
    )

    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Convert workflow to domain model
    workflow_nodes = [
        WorkflowNode(
            id=n["id"],
            type=NodeType(n["type"]),
            position=n["position"],
            data=n["data"],
            label=n.get("label")
        )
        for n in workflow.nodes
    ]

    workflow_edges = [
        WorkflowEdge(
            id=e["id"],
            source=e["source"],
            target=e["target"],
            source_handle=e.get("sourceHandle", "out"),
            target_handle=e.get("targetHandle", "in"),
            label=e.get("label"),
            animated=e.get("animated", False)
        )
        for e in workflow.edges
    ]

    workflow_obj = Workflow(
        workflow_id=workflow.workflow_id,
        organization_id=workflow.organization_id,
        name=workflow.name,
        description=workflow.description,
        status=WorkflowStatus(workflow.status),
        version=workflow.version,
        nodes=workflow_nodes,
        edges=workflow_edges,
        variables=workflow.variables,
        environment=workflow.environment,
        max_execution_time_seconds=workflow.max_execution_time_seconds,
        retry_on_failure=workflow.retry_on_failure,
        max_retries=workflow.max_retries
    )

    # Execute in background
    async def run_scheduled_execution():
        """Background task to execute scheduled workflow"""
        engine = WorkflowExecutor()

        # Create new DB session for background task
        from backend.database.session import get_async_session
        async with get_async_session() as bg_db:
            try:
                await engine.execute_workflow(
                    workflow=workflow_obj,
                    execution=WorkflowExecution(
                        execution_id=execution.execution_id,
                        workflow_id=schedule.workflow_id,
                        workflow_version=workflow.version,
                        organization_id=schedule.organization_id,
                        status=ExecutionStatus.PENDING,
                        triggered_by="scheduler",
                        trigger_source=f"schedule:{schedule.schedule_id}",
                        input_data=input_data
                    ),
                    db=bg_db
                )
            except Exception as e:
                print(f"Scheduled workflow execution failed: {e}")

    background_tasks.add_task(run_scheduled_execution)

    return {
        "status": "triggered",
        "schedule_id": str(schedule.schedule_id),
        "workflow_id": str(schedule.workflow_id),
        "execution_id": str(execution.execution_id),
        "message": "Workflow execution started",
    }


# ==================== Workflow-specific Endpoints ====================

@router.get("/workflow/{workflow_id}", response_model=List[ScheduleResponse])
async def get_schedules_for_workflow(
    workflow_id: UUID,
    organization_id: str = Depends(get_organization_id),
    service: SchedulerService = Depends(get_scheduler_service),
):
    """Get all schedules for a specific workflow"""
    schedules = await service.get_schedules_for_workflow(workflow_id)

    # Filter to organization
    schedules = [s for s in schedules if s.organization_id == organization_id]
    return [_schedule_to_response(s) for s in schedules]


# ==================== Helpers ====================

def _schedule_to_response(schedule) -> ScheduleResponse:
    """Convert schedule model to response"""
    trigger_url = None
    if schedule.external_scheduler and schedule.external_trigger_token:
        trigger_url = f"/api/schedules/trigger/{schedule.external_trigger_token}"

    return ScheduleResponse(
        schedule_id=schedule.schedule_id,
        workflow_id=schedule.workflow_id,
        organization_id=schedule.organization_id,
        name=schedule.name,
        description=schedule.description,
        schedule_type=schedule.schedule_type,
        cron_expression=schedule.cron_expression,
        interval_seconds=schedule.interval_seconds,
        run_at=schedule.run_at,
        timezone=schedule.timezone,
        status=schedule.status,
        input_data=schedule.input_data or {},
        last_run_at=schedule.last_run_at,
        last_run_status=schedule.last_run_status,
        next_run_at=schedule.next_run_at,
        total_runs=schedule.total_runs,
        successful_runs=schedule.successful_runs,
        failed_runs=schedule.failed_runs,
        total_cost=schedule.total_cost,
        external_scheduler=schedule.external_scheduler,
        external_trigger_url=trigger_url,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _history_to_response(history) -> ScheduleHistoryResponse:
    """Convert history model to response"""
    return ScheduleHistoryResponse(
        history_id=history.history_id,
        schedule_id=history.schedule_id,
        workflow_id=history.workflow_id,
        execution_id=history.execution_id,
        scheduled_for=history.scheduled_for,
        started_at=history.started_at,
        completed_at=history.completed_at,
        duration_seconds=history.duration_seconds,
        status=history.status,
        trigger_source=history.trigger_source,
        error_message=history.error_message,
        cost=history.cost,
        tokens_used=history.tokens_used,
        created_at=history.created_at,
    )
