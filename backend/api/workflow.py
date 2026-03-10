"""
Visual DAG Builder - Workflow REST API

Complete API for workflow management and execution:
- CRUD operations for workflows
- Workflow execution with real-time status
- Template marketplace
- Workflow analytics and monitoring

Integrates with:
- workflow_models.py: Data models
- workflow_service.py: Execution engine
- cost_service.py: Cost tracking
- audit_logger.py: Audit logging
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload

from backend.database.session import get_db
from backend.shared.workflow_models import (
    WorkflowModel, WorkflowExecutionModel, WorkflowTemplateModel,
    WorkflowStatus, ExecutionStatus, NodeType,
    Workflow, WorkflowExecution, WorkflowTemplate,
    WorkflowNode, WorkflowEdge
)
from backend.shared.workflow_service import WorkflowExecutionEngine
from backend.shared.audit_logger import AuditLogger, AuditEventType
from backend.shared.cost_service import CostService
from backend.shared.auth import (
    get_current_user,
    get_current_user_id,
    get_current_organization_id,
    AuthenticatedUser,
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class NodePositionRequest(BaseModel):
    """Node position in canvas"""
    x: float
    y: float


class NodeRequest(BaseModel):
    """Workflow node request"""
    id: str
    type: str  # NodeType enum value
    position: NodePositionRequest
    data: Dict[str, Any]
    label: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class EdgeRequest(BaseModel):
    """Workflow edge request"""
    id: str
    source: str
    target: str
    source_handle: Optional[str] = "out"
    target_handle: Optional[str] = "in"
    label: Optional[str] = None
    animated: bool = False


class WorkflowCreateRequest(BaseModel):
    """Create workflow request"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    nodes: List[NodeRequest]
    edges: List[EdgeRequest]
    variables: Optional[Dict[str, Any]] = None
    environment: str = "development"
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    max_execution_time_seconds: int = 3600
    retry_on_failure: bool = True
    max_retries: int = 3


class WorkflowUpdateRequest(BaseModel):
    """Update workflow request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    nodes: Optional[List[NodeRequest]] = None
    edges: Optional[List[EdgeRequest]] = None
    variables: Optional[Dict[str, Any]] = None
    environment: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None  # WorkflowStatus enum value


class WorkflowExecuteRequest(BaseModel):
    """Execute workflow request"""
    input_data: Dict[str, Any] = Field(default_factory=dict)
    variables: Optional[Dict[str, Any]] = None  # Override workflow variables


class WorkflowResponse(BaseModel):
    """Workflow response"""
    workflow_id: str
    organization_id: str
    name: str
    description: Optional[str]
    tags: List[str]
    status: str
    version: int
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    variables: Dict[str, Any]
    environment: str
    trigger_type: Optional[str]
    trigger_config: Optional[Dict[str, Any]]
    max_execution_time_seconds: int
    retry_on_failure: bool
    max_retries: int
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_execution_time_seconds: Optional[float]
    total_cost: float
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class ExecutionResponse(BaseModel):
    """Workflow execution response"""
    execution_id: str
    workflow_id: str
    workflow_version: int
    organization_id: str
    status: str
    triggered_by: Optional[str]
    trigger_source: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    error_node_id: Optional[str]
    retry_count: int
    node_states: Dict[str, Dict[str, Any]]
    node_executions: Optional[List[Dict[str, Any]]] = None  # Step-by-step execution data for debugger
    total_cost: float
    total_tokens: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateResponse(BaseModel):
    """Workflow template response"""
    template_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    tags: List[str]
    thumbnail_url: Optional[str]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    variables: Dict[str, Any]
    use_count: int
    rating: Optional[float]
    is_public: bool
    is_featured: bool
    created_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# ROUTER
# =============================================================================

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


# =============================================================================
# WORKFLOW CRUD ENDPOINTS
# =============================================================================

@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    request: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id)
):
    """
    Create a new workflow.

    Creates a visual workflow with nodes and edges that can be executed.
    """
    # Convert request to database model
    workflow = WorkflowModel(
        workflow_id=uuid4(),
        organization_id=organization_id,
        name=request.name,
        description=request.description,
        tags=request.tags or [],
        status=WorkflowStatus.DRAFT.value,
        version=1,
        nodes=[{
            "id": n.id,
            "type": n.type,
            "position": {"x": n.position.x, "y": n.position.y},
            "data": n.data,
            "label": n.label,
            "width": n.width,
            "height": n.height
        } for n in request.nodes],
        edges=[{
            "id": e.id,
            "source": e.source,
            "target": e.target,
            "sourceHandle": e.source_handle,
            "targetHandle": e.target_handle,
            "label": e.label,
            "animated": e.animated
        } for e in request.edges],
        variables=request.variables or {},
        environment=request.environment,
        trigger_type=request.trigger_type,
        trigger_config=request.trigger_config,
        max_execution_time_seconds=request.max_execution_time_seconds,
        retry_on_failure=request.retry_on_failure,
        max_retries=request.max_retries,
        created_by=user_id,
        updated_by=user_id
    )

    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_event(
        event_type=AuditEventType.WORKFLOW_CREATED,
        organization_id=organization_id,
        user_id=user_id,
        resource_type="workflow",
        resource_id=str(workflow.workflow_id),
        details={
            "workflow_name": workflow.name,
            "node_count": len(request.nodes),
            "edge_count": len(request.edges)
        }
    )

    return WorkflowResponse.from_orm(workflow)


@router.get("", response_model=List[WorkflowResponse])
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    List workflows for the organization.

    Supports filtering by status, tags, and environment.
    """
    query = select(WorkflowModel).where(
        WorkflowModel.organization_id == organization_id
    )

    # Apply filters
    if status:
        query = query.where(WorkflowModel.status == status)
    if environment:
        query = query.where(WorkflowModel.environment == environment)
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        query = query.where(WorkflowModel.tags.overlap(tag_list))

    # Pagination
    query = query.order_by(WorkflowModel.created_at.desc())
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    workflows = result.scalars().all()

    return [WorkflowResponse.from_orm(w) for w in workflows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    Get workflow by ID.

    Returns the complete workflow definition including nodes and edges.
    """
    query = select(WorkflowModel).where(
        and_(
            WorkflowModel.workflow_id == workflow_id,
            WorkflowModel.organization_id == organization_id
        )
    )

    result = await db.execute(query)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return WorkflowResponse.from_orm(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    request: WorkflowUpdateRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id)
):
    """
    Update workflow.

    Updates workflow metadata, nodes, edges, or configuration.
    Increments version number on successful update.
    """
    # Get existing workflow
    query = select(WorkflowModel).where(
        and_(
            WorkflowModel.workflow_id == workflow_id,
            WorkflowModel.organization_id == organization_id
        )
    )
    result = await db.execute(query)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Update fields
    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.description is not None:
        update_data["description"] = request.description
    if request.tags is not None:
        update_data["tags"] = request.tags
    if request.variables is not None:
        update_data["variables"] = request.variables
    if request.environment is not None:
        update_data["environment"] = request.environment
    if request.trigger_type is not None:
        update_data["trigger_type"] = request.trigger_type
    if request.trigger_config is not None:
        update_data["trigger_config"] = request.trigger_config
    if request.status is not None:
        update_data["status"] = request.status

    # Update nodes and edges
    if request.nodes is not None:
        update_data["nodes"] = [{
            "id": n.id,
            "type": n.type,
            "position": {"x": n.position.x, "y": n.position.y},
            "data": n.data,
            "label": n.label,
            "width": n.width,
            "height": n.height
        } for n in request.nodes]
    if request.edges is not None:
        update_data["edges"] = [{
            "id": e.id,
            "source": e.source,
            "target": e.target,
            "sourceHandle": e.source_handle,
            "targetHandle": e.target_handle,
            "label": e.label,
            "animated": e.animated
        } for e in request.edges]

    # Increment version and update timestamp
    update_data["version"] = workflow.version + 1
    update_data["updated_at"] = datetime.utcnow()
    update_data["updated_by"] = user_id

    # Apply updates
    for key, value in update_data.items():
        setattr(workflow, key, value)

    await db.commit()
    await db.refresh(workflow)

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_event(
        event_type=AuditEventType.WORKFLOW_UPDATED,
        organization_id=organization_id,
        user_id=user_id,
        resource_type="workflow",
        resource_id=str(workflow_id),
        details={
            "new_version": workflow.version,
            "updated_fields": list(update_data.keys())
        }
    )

    return WorkflowResponse.from_orm(workflow)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete workflow.

    Permanently deletes the workflow and all execution history.
    """
    # Check workflow exists
    query = select(WorkflowModel).where(
        and_(
            WorkflowModel.workflow_id == workflow_id,
            WorkflowModel.organization_id == organization_id
        )
    )
    result = await db.execute(query)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow_name = workflow.name

    # Delete executions first
    await db.execute(
        delete(WorkflowExecutionModel).where(
            WorkflowExecutionModel.workflow_id == workflow_id
        )
    )

    # Delete workflow
    await db.delete(workflow)
    await db.commit()

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_event(
        event_type=AuditEventType.WORKFLOW_DELETED,
        organization_id=organization_id,
        user_id=user_id,
        resource_type="workflow",
        resource_id=str(workflow_id),
        details={"workflow_name": workflow_name}
    )

    return None


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse, status_code=201)
async def duplicate_workflow(
    workflow_id: UUID,
    name: Optional[str] = Query(None, description="Name for duplicated workflow"),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id)
):
    """
    Duplicate workflow.

    Creates a copy of the workflow with a new ID.
    """
    # Get original workflow
    query = select(WorkflowModel).where(
        and_(
            WorkflowModel.workflow_id == workflow_id,
            WorkflowModel.organization_id == organization_id
        )
    )
    result = await db.execute(query)
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Create duplicate
    duplicate = WorkflowModel(
        workflow_id=uuid4(),
        organization_id=organization_id,
        name=name or f"{original.name} (Copy)",
        description=original.description,
        tags=original.tags,
        status=WorkflowStatus.DRAFT.value,
        version=1,
        nodes=original.nodes,
        edges=original.edges,
        variables=original.variables,
        environment=original.environment,
        trigger_type=original.trigger_type,
        trigger_config=original.trigger_config,
        max_execution_time_seconds=original.max_execution_time_seconds,
        retry_on_failure=original.retry_on_failure,
        max_retries=original.max_retries,
        created_by=user_id,
        updated_by=user_id
    )

    db.add(duplicate)
    await db.commit()
    await db.refresh(duplicate)

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_event(
        event_type=AuditEventType.WORKFLOW_CREATED,
        organization_id=organization_id,
        user_id=user_id,
        resource_type="workflow",
        resource_id=str(duplicate.workflow_id),
        details={
            "workflow_name": duplicate.name,
            "duplicated_from": str(workflow_id)
        }
    )

    return WorkflowResponse.from_orm(duplicate)


# =============================================================================
# WORKFLOW EXECUTION ENDPOINTS
# =============================================================================

@router.post("/{workflow_id}/execute", response_model=ExecutionResponse, status_code=202)
async def execute_workflow(
    workflow_id: UUID,
    request: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id)
):
    """
    Execute workflow.

    Starts workflow execution in the background and returns execution ID.
    Use GET /executions/{execution_id} to check status.
    """
    # Get workflow
    query = select(WorkflowModel).where(
        and_(
            WorkflowModel.workflow_id == workflow_id,
            WorkflowModel.organization_id == organization_id
        )
    )
    result = await db.execute(query)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.status == WorkflowStatus.ARCHIVED.value:
        raise HTTPException(status_code=400, detail="Cannot execute archived workflow")

    # Create execution record
    execution = WorkflowExecutionModel(
        execution_id=uuid4(),
        workflow_id=workflow_id,
        workflow_version=workflow.version,
        organization_id=organization_id,
        triggered_by=user_id,
        trigger_source="manual",
        status=ExecutionStatus.PENDING.value,
        input_data=request.input_data,
        node_states={}
    )

    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Convert to domain model
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
        variables=request.variables or workflow.variables,
        environment=workflow.environment,
        max_execution_time_seconds=workflow.max_execution_time_seconds,
        retry_on_failure=workflow.retry_on_failure,
        max_retries=workflow.max_retries
    )

    # Execute in background
    async def run_execution():
        """Background task to execute workflow"""
        engine = WorkflowExecutionEngine()

        # Create new DB session for background task
        from backend.database.session import get_async_session
        async with get_async_session() as bg_db:
            try:
                # Pass execution_id to update the existing execution record
                # The engine's execute_workflow method needs the correct signature
                await engine.execute_workflow_with_existing(
                    workflow=workflow_obj,
                    execution_id=execution.execution_id,
                    input_data=request.input_data or {},
                    triggered_by=user_id or "system",
                    db=bg_db
                )
            except Exception as e:
                import traceback
                print(f"Workflow execution failed: {e}")
                traceback.print_exc()
                # Update execution status to failed
                try:
                    from sqlalchemy import update
                    stmt = update(WorkflowExecutionModel).where(
                        WorkflowExecutionModel.execution_id == execution.execution_id
                    ).values(
                        status=ExecutionStatus.FAILED.value,
                        error_message=str(e),
                        completed_at=datetime.utcnow()
                    )
                    await bg_db.execute(stmt)
                    await bg_db.commit()
                except Exception as update_err:
                    print(f"Failed to update execution status: {update_err}")

    background_tasks.add_task(run_execution)

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_event(
        event_type=AuditEventType.WORKFLOW_EXECUTED,
        organization_id=organization_id,
        user_id=user_id,
        resource_type="workflow_execution",
        resource_id=str(execution.execution_id),
        details={
            "workflow_id": str(workflow_id),
            "workflow_name": workflow.name
        }
    )

    return ExecutionResponse.from_orm(execution)


@router.get("/{workflow_id}/executions", response_model=List[ExecutionResponse])
async def list_workflow_executions(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    List executions for a workflow.

    Returns execution history with status, timing, and cost information.
    """
    query = select(WorkflowExecutionModel).where(
        and_(
            WorkflowExecutionModel.workflow_id == workflow_id,
            WorkflowExecutionModel.organization_id == organization_id
        )
    )

    if status:
        query = query.where(WorkflowExecutionModel.status == status)

    query = query.order_by(WorkflowExecutionModel.created_at.desc())
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    executions = result.scalars().all()

    return [ExecutionResponse.from_orm(e) for e in executions]


# =============================================================================
# ALL EXECUTIONS ENDPOINTS (across all workflows)
# =============================================================================

class ExecutionListResponse(BaseModel):
    """Response for execution list with workflow name"""
    execution_id: str
    workflow_id: str
    workflow_name: Optional[str]
    workflow_version: int
    organization_id: str
    status: str
    triggered_by: Optional[str]
    trigger_source: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    error_node_id: Optional[str]
    retry_count: int
    node_states: Dict[str, Dict[str, Any]]
    node_executions: Optional[List[Dict[str, Any]]] = None  # Step-by-step execution data for debugger
    total_cost: float
    total_tokens: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/executions", response_model=List[ExecutionListResponse])
async def list_all_executions(
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    status: Optional[str] = Query(None, description="Filter by status"),
    workflow_id: Optional[UUID] = Query(None, description="Filter by workflow ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    List all executions across all workflows.

    Returns execution history with workflow names for the dashboard executions page.
    """
    # Build query with workflow join to get workflow names
    from sqlalchemy import join

    # Join executions with workflows to get workflow names
    query = select(
        WorkflowExecutionModel,
        WorkflowModel.name.label('workflow_name')
    ).select_from(
        join(
            WorkflowExecutionModel,
            WorkflowModel,
            WorkflowExecutionModel.workflow_id == WorkflowModel.workflow_id,
            isouter=True
        )
    ).where(
        WorkflowExecutionModel.organization_id == organization_id
    )

    if status:
        query = query.where(WorkflowExecutionModel.status == status)
    if workflow_id:
        query = query.where(WorkflowExecutionModel.workflow_id == workflow_id)

    query = query.order_by(WorkflowExecutionModel.created_at.desc())
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    rows = result.all()

    executions = []
    for row in rows:
        execution = row[0]  # WorkflowExecutionModel
        workflow_name = row[1]  # workflow_name from join

        executions.append(ExecutionListResponse(
            execution_id=str(execution.execution_id),
            workflow_id=str(execution.workflow_id),
            workflow_name=workflow_name,
            workflow_version=execution.workflow_version,
            organization_id=execution.organization_id,
            status=execution.status,
            triggered_by=execution.triggered_by,
            trigger_source=execution.trigger_source,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            duration_seconds=execution.duration_seconds,
            input_data=execution.input_data,
            output_data=execution.output_data,
            error_message=execution.error_message,
            error_node_id=execution.error_node_id,
            retry_count=execution.retry_count,
            node_states=execution.node_states or {},
            node_executions=execution.node_executions or [],  # Step-by-step data for debugger
            total_cost=execution.total_cost or 0.0,
            total_tokens=execution.total_tokens,
            created_at=execution.created_at
        ))

    return executions


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    Get execution by ID.

    Returns detailed execution information including node states and errors.
    """
    query = select(WorkflowExecutionModel).where(
        and_(
            WorkflowExecutionModel.execution_id == execution_id,
            WorkflowExecutionModel.organization_id == organization_id
        )
    )

    result = await db.execute(query)
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return ExecutionResponse.from_orm(execution)


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id)
):
    """
    Cancel running execution.

    Attempts to cancel a running workflow execution.
    """
    query = select(WorkflowExecutionModel).where(
        and_(
            WorkflowExecutionModel.execution_id == execution_id,
            WorkflowExecutionModel.organization_id == organization_id
        )
    )

    result = await db.execute(query)
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.status not in [ExecutionStatus.PENDING.value, ExecutionStatus.RUNNING.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel execution with status {execution.status}"
        )

    # Update status
    execution.status = ExecutionStatus.CANCELLED.value
    execution.completed_at = datetime.utcnow()
    execution.duration_seconds = (
        (execution.completed_at - execution.started_at).total_seconds()
        if execution.started_at else 0
    )

    await db.commit()
    await db.refresh(execution)

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_event(
        event_type=AuditEventType.WORKFLOW_FAILED,  # Using FAILED for cancelled
        organization_id=organization_id,
        user_id=user_id,
        resource_type="workflow_execution",
        resource_id=str(execution_id),
        details={"reason": "cancelled_by_user"}
    )

    return ExecutionResponse.from_orm(execution)


# =============================================================================
# TEMPLATE MARKETPLACE ENDPOINTS
# =============================================================================

@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    is_featured: Optional[bool] = Query(None, description="Filter featured templates"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    List workflow templates.

    Browse the template marketplace for pre-built workflows.
    """
    query = select(WorkflowTemplateModel).where(
        WorkflowTemplateModel.is_public == True
    )

    if category:
        query = query.where(WorkflowTemplateModel.category == category)
    if is_featured is not None:
        query = query.where(WorkflowTemplateModel.is_featured == is_featured)
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        query = query.where(WorkflowTemplateModel.tags.overlap(tag_list))

    query = query.order_by(WorkflowTemplateModel.use_count.desc())
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    templates = result.scalars().all()

    return [TemplateResponse.from_orm(t) for t in templates]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get template by ID.

    Returns complete template definition.
    """
    query = select(WorkflowTemplateModel).where(
        WorkflowTemplateModel.template_id == template_id
    )

    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateResponse.from_orm(template)


@router.post("/templates/{template_id}/use", response_model=WorkflowResponse, status_code=201)
async def create_workflow_from_template(
    template_id: UUID,
    name: str = Query(..., description="Name for new workflow"),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id)
):
    """
    Create workflow from template.

    Instantiates a template as a new workflow.
    """
    # Get template
    query = select(WorkflowTemplateModel).where(
        WorkflowTemplateModel.template_id == template_id
    )
    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Create workflow from template
    workflow = WorkflowModel(
        workflow_id=uuid4(),
        organization_id=organization_id,
        name=name,
        description=template.description,
        tags=template.tags,
        status=WorkflowStatus.DRAFT.value,
        version=1,
        nodes=template.nodes,
        edges=template.edges,
        variables=template.variables,
        created_by=user_id,
        updated_by=user_id,
        metadata={"template_id": str(template_id)}
    )

    db.add(workflow)

    # Increment template use count
    template.use_count += 1

    await db.commit()
    await db.refresh(workflow)

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_event(
        event_type=AuditEventType.WORKFLOW_CREATED,
        organization_id=organization_id,
        user_id=user_id,
        resource_type="workflow",
        resource_id=str(workflow.workflow_id),
        details={
            "workflow_name": workflow.name,
            "from_template": str(template_id),
            "template_name": template.name
        }
    )

    return WorkflowResponse.from_orm(workflow)


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@router.get("/{workflow_id}/analytics")
async def get_workflow_analytics(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id)
):
    """
    Get workflow analytics.

    Returns execution statistics, cost analysis, and performance metrics.
    """
    # Get workflow
    workflow_query = select(WorkflowModel).where(
        and_(
            WorkflowModel.workflow_id == workflow_id,
            WorkflowModel.organization_id == organization_id
        )
    )
    workflow_result = await db.execute(workflow_query)
    workflow = workflow_result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get execution statistics
    executions_query = select(
        func.count(WorkflowExecutionModel.execution_id).label("total_count"),
        func.count(
            WorkflowExecutionModel.execution_id
        ).filter(
            WorkflowExecutionModel.status == ExecutionStatus.COMPLETED.value
        ).label("success_count"),
        func.count(
            WorkflowExecutionModel.execution_id
        ).filter(
            WorkflowExecutionModel.status == ExecutionStatus.FAILED.value
        ).label("failed_count"),
        func.avg(WorkflowExecutionModel.duration_seconds).label("avg_duration"),
        func.sum(WorkflowExecutionModel.total_cost).label("total_cost"),
        func.avg(WorkflowExecutionModel.total_cost).label("avg_cost")
    ).where(
        WorkflowExecutionModel.workflow_id == workflow_id
    )

    stats_result = await db.execute(executions_query)
    stats = stats_result.one()

    # Recent executions
    recent_query = select(WorkflowExecutionModel).where(
        WorkflowExecutionModel.workflow_id == workflow_id
    ).order_by(
        WorkflowExecutionModel.created_at.desc()
    ).limit(10)

    recent_result = await db.execute(recent_query)
    recent_executions = recent_result.scalars().all()

    return {
        "workflow_id": str(workflow_id),
        "workflow_name": workflow.name,
        "statistics": {
            "total_executions": stats.total_count or 0,
            "successful_executions": stats.success_count or 0,
            "failed_executions": stats.failed_count or 0,
            "success_rate": (
                (stats.success_count / stats.total_count * 100)
                if stats.total_count else 0
            ),
            "avg_duration_seconds": float(stats.avg_duration) if stats.avg_duration else 0,
            "total_cost": float(stats.total_cost) if stats.total_cost else 0,
            "avg_cost": float(stats.avg_cost) if stats.avg_cost else 0
        },
        "recent_executions": [
            {
                "execution_id": str(e.execution_id),
                "status": e.status,
                "duration_seconds": e.duration_seconds,
                "total_cost": e.total_cost,
                "created_at": e.created_at.isoformat()
            }
            for e in recent_executions
        ]
    }
