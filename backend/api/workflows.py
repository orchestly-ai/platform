"""
Workflow API Endpoints

REST API for workflow management and execution.
"""

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Body
from typing import List, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field
import json

from backend.database.session import get_db
from backend.database.repositories import WorkflowRepository
from backend.services.workflow_executor import get_executor, ExecutionEvent
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.shared.workflow_models import WorkflowExecutionModel, WorkflowModel
from backend.shared.auth import verify_jwt_token


# Pydantic models for request/response
class IntegrationConfig(BaseModel):
    """Integration node configuration."""
    integrationType: Optional[str] = None
    action: Optional[str] = None
    parameters: Optional[dict] = None
    credentials: Optional[str] = None

    class Config:
        extra = "allow"  # Allow extra fields


class WorkflowNodeData(BaseModel):
    """Node data structure."""
    label: str
    type: str
    agentId: Optional[str] = None
    capabilities: Optional[List[str]] = None
    llmModel: Optional[str] = None
    tools: Optional[List[str]] = None
    config: Optional[dict] = None
    status: Optional[str] = None
    cost: Optional[float] = None
    executionTime: Optional[float] = None
    error: Optional[str] = None
    # Integration node configuration
    integrationConfig: Optional[IntegrationConfig] = None
    # Trigger node configuration
    triggerConfig: Optional[dict] = None
    # Condition node configuration
    conditionConfig: Optional[dict] = None

    class Config:
        extra = "allow"  # Allow extra fields we haven't explicitly defined


class WorkflowNodePosition(BaseModel):
    """Node position."""
    x: float
    y: float


class WorkflowNode(BaseModel):
    """Workflow node."""
    id: str
    type: str
    position: WorkflowNodePosition
    data: WorkflowNodeData


class WorkflowEdgeData(BaseModel):
    """Edge data structure."""
    messageFormat: Optional[str] = None
    retryPolicy: Optional[dict] = None
    condition: Optional[str] = None


class WorkflowEdge(BaseModel):
    """Workflow edge/connection."""
    id: str
    source: str
    target: str
    label: Optional[str] = None
    type: Optional[str] = None
    animated: Optional[bool] = None
    data: Optional[WorkflowEdgeData] = None


class WorkflowCreate(BaseModel):
    """Request to create workflow."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    createdBy: Optional[str] = None
    isTemplate: bool = False


class WorkflowUpdate(BaseModel):
    """Request to update workflow."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    nodes: Optional[List[WorkflowNode]] = None
    edges: Optional[List[WorkflowEdge]] = None


class WorkflowResponse(BaseModel):
    """Workflow response."""
    id: str
    name: str
    description: Optional[str]
    tags: List[str]
    nodes: List[dict]
    edges: List[dict]
    version: int
    isTemplate: bool
    createdBy: Optional[str]
    createdAt: str
    updatedAt: str
    metadata: dict


class WorkflowListResponse(BaseModel):
    """List of workflows response."""
    workflows: List[WorkflowResponse]
    total: int
    limit: int
    offset: int


# Create router
router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("", response_model=dict, status_code=201)
async def create_workflow(
    workflow: WorkflowCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create new workflow.

    Args:
        workflow: Workflow data

    Returns:
        Created workflow with ID
    """
    repo = WorkflowRepository(db)

    # Convert nodes and edges to dicts
    nodes_dict = [node.dict() for node in workflow.nodes]
    edges_dict = [edge.dict() for edge in workflow.edges]

    try:
        workflow_id = await repo.create(
            name=workflow.name,
            description=workflow.description,
            tags=workflow.tags,
            nodes=nodes_dict,
            edges=edges_dict,
            created_by=workflow.createdBy,
            is_template=workflow.isTemplate
        )

        # Fetch the created workflow
        created_workflow = await repo.get(workflow_id)

        return created_workflow

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {str(e)}")


@router.get("", response_model=dict)
async def list_workflows(
    limit: int = 100,
    offset: int = 0,
    isTemplate: Optional[bool] = None,
    tags: Optional[str] = None,
    createdBy: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List workflows with optional filters.

    Args:
        limit: Maximum results (default 100)
        offset: Pagination offset (default 0)
        isTemplate: Filter by template flag
        tags: Comma-separated tags to filter by
        createdBy: Filter by creator

    Returns:
        List of workflows
    """
    repo = WorkflowRepository(db)

    # Parse tags if provided
    tag_list = tags.split(",") if tags else None

    try:
        workflows = await repo.list(
            limit=limit,
            offset=offset,
            is_template=isTemplate,
            tags=tag_list,
            created_by=createdBy
        )

        return {
            "workflows": workflows,
            "total": len(workflows),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")


@router.get("/executions", response_model=list)
async def list_all_executions(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List all workflow executions across all workflows.

    Args:
        limit: Maximum results (default 100)
        offset: Pagination offset (default 0)
        status: Optional status filter (pending, running, completed, failed)

    Returns:
        List of workflow executions with workflow names
    """
    try:
        # Build query - select all columns needed for the executions page
        stmt = select(
            WorkflowExecutionModel.execution_id,
            WorkflowExecutionModel.workflow_id,
            WorkflowExecutionModel.workflow_version,
            WorkflowExecutionModel.organization_id,
            WorkflowExecutionModel.status,
            WorkflowExecutionModel.triggered_by,
            WorkflowExecutionModel.trigger_source,
            WorkflowExecutionModel.started_at,
            WorkflowExecutionModel.completed_at,
            WorkflowExecutionModel.duration_seconds,
            WorkflowExecutionModel.input_data,
            WorkflowExecutionModel.output_data,
            WorkflowExecutionModel.error_message,
            WorkflowExecutionModel.error_node_id,
            WorkflowExecutionModel.retry_count,
            WorkflowExecutionModel.node_states,
            WorkflowExecutionModel.node_executions,
            WorkflowExecutionModel.total_cost,
            WorkflowExecutionModel.total_tokens,
            WorkflowExecutionModel.created_at,
            WorkflowModel.name.label('workflow_name')
        ).outerjoin(
            WorkflowModel,
            WorkflowExecutionModel.workflow_id == WorkflowModel.workflow_id
        )

        # Apply status filter if provided
        if status:
            stmt = stmt.where(WorkflowExecutionModel.status == status)

        # Order by most recent first
        stmt = stmt.order_by(desc(WorkflowExecutionModel.started_at))

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(stmt)
        rows = result.all()

        # Format response with all fields needed by frontend
        executions = []
        for row in rows:
            executions.append({
                "execution_id": str(row.execution_id),
                "workflow_id": str(row.workflow_id),
                "workflow_name": row.workflow_name or "Unsaved Workflow",
                "workflow_version": row.workflow_version or 1,
                "organization_id": row.organization_id or "",
                "status": row.status,
                "triggered_by": row.triggered_by,
                "trigger_source": row.trigger_source,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "duration_seconds": row.duration_seconds,
                "input_data": row.input_data,
                "output_data": row.output_data,
                "error_message": row.error_message,
                "error_node_id": row.error_node_id,
                "retry_count": row.retry_count or 0,
                "node_states": row.node_states or {},
                "node_executions": row.node_executions or [],
                "total_cost": row.total_cost or 0.0,
                "total_tokens": row.total_tokens,
                "created_at": row.created_at.isoformat() if row.created_at else row.started_at.isoformat() if row.started_at else None,
            })

        return executions

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list executions: {str(e)}")


@router.get("/{workflow_id}", response_model=dict)
async def get_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get workflow by ID.

    Args:
        workflow_id: Workflow UUID

    Returns:
        Workflow data
    """
    repo = WorkflowRepository(db)

    try:
        workflow = await repo.get(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        return workflow

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow: {str(e)}")


@router.put("/{workflow_id}", response_model=dict)
async def update_workflow(
    workflow_id: UUID,
    update: WorkflowUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update workflow.

    Args:
        workflow_id: Workflow UUID
        update: Update data

    Returns:
        Updated workflow
    """
    repo = WorkflowRepository(db)

    # Convert nodes and edges to dicts if provided
    nodes_dict = [node.dict() for node in update.nodes] if update.nodes else None
    edges_dict = [edge.dict() for edge in update.edges] if update.edges else None

    try:
        success = await repo.update(
            workflow_id=workflow_id,
            name=update.name,
            description=update.description,
            nodes=nodes_dict,
            edges=edges_dict,
            tags=update.tags
        )

        if not success:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Fetch updated workflow
        workflow = await repo.get(workflow_id)
        return workflow

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update workflow: {str(e)}")


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete workflow.

    Args:
        workflow_id: Workflow UUID

    Returns:
        No content (204)
    """
    repo = WorkflowRepository(db)

    try:
        success = await repo.delete(workflow_id)

        if not success:
            raise HTTPException(status_code=404, detail="Workflow not found")

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete workflow: {str(e)}")


@router.post("/{workflow_id}/clone", response_model=dict, status_code=201)
async def clone_workflow(
    workflow_id: UUID,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Clone existing workflow.

    Args:
        workflow_id: Workflow UUID to clone
        name: Optional new name (defaults to "Copy of {original_name}")

    Returns:
        Cloned workflow
    """
    repo = WorkflowRepository(db)

    try:
        # Get original workflow
        original = await repo.get(workflow_id)

        if not original:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Create clone with new name
        clone_name = name or f"Copy of {original['name']}"

        new_workflow_id = await repo.create(
            name=clone_name,
            description=original.get("description"),
            tags=original.get("tags", []),
            nodes=original["nodes"],
            edges=original["edges"],
            created_by=original.get("createdBy"),
            is_template=False  # Clones are never templates
        )

        # Fetch the cloned workflow
        cloned_workflow = await repo.get(new_workflow_id)
        return cloned_workflow

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clone workflow: {str(e)}")


class ExecuteWorkflowRequest(BaseModel):
    """Request body for workflow execution."""
    input: Optional[dict] = Field(default=None, description="Input data for the workflow")

    class Config:
        extra = "allow"


@router.post("/{workflow_id}/execute", response_model=dict, status_code=201)
async def execute_workflow_rest(
    workflow_id: UUID,
    request: ExecuteWorkflowRequest = Body(default=ExecuteWorkflowRequest()),
    db: AsyncSession = Depends(get_db),
    token_payload: dict = Depends(verify_jwt_token)
):
    """
    Execute workflow via REST API (returns execution ID immediately).

    For real-time updates, use the WebSocket endpoint instead.
    This endpoint starts the execution and returns the execution ID,
    but doesn't wait for completion.
    """
    try:
        # Import here to avoid circular dependency
        from backend.shared.workflow_service import get_workflow_service

        # Get workflow service
        service = get_workflow_service()

        # Extract input data from request body
        input_data = request.input or {}

        # Get user ID from JWT token
        user_id = token_payload.get("sub", "anonymous")

        # Start execution (this will run in background)
        execution = await service.execute_workflow(
            workflow_id=workflow_id,
            input_data=input_data,
            triggered_by=user_id,
            db=db
        )

        return {
            "execution_id": str(execution.execution_id),
            "status": execution.status.value,
            "message": "Workflow execution started"
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute workflow: {str(e)}")


@router.websocket("/temp/execute")
async def execute_temp_workflow_ws(websocket: WebSocket):
    """
    Execute temporary (unsaved) workflow with real-time status updates via WebSocket.

    This endpoint is for testing workflows that haven't been saved yet.
    Persists execution to database for history tracking.

    WebSocket Protocol:
    - Client connects to /api/workflows/temp/execute
    - Client sends {"action": "start", "workflow": {...}} to start execution
    - Server sends execution events as JSON
    - Client can send {"action": "stop"} to stop execution

    Event Types:
    - execution_started: Workflow started
    - node_status_changed: Node status updated
    - execution_completed: Workflow completed successfully
    - execution_failed: Workflow execution failed
    """
    import traceback
    import sys
    from datetime import datetime
    from uuid import uuid4
    from backend.database.session import AsyncSessionLocal

    # Use print for guaranteed output (bypasses logging config)
    def log(msg: str, level: str = "INFO"):
        print(f"[WS-EXEC] [{level}] {msg}", flush=True)

    log("WebSocket endpoint hit - accepting connection")

    try:
        await websocket.accept()
        log("Connection accepted successfully")
    except Exception as e:
        log(f"Failed to accept connection: {e}", "ERROR")
        traceback.print_exc()
        return

    execution_record = None
    db_session = None
    node_states = {}
    node_executions = []  # Track step-by-step events for debugger
    total_cost = 0.0
    start_time = datetime.utcnow()

    try:
        # Wait for client to send workflow data
        log("Waiting for workflow data from client...")
        data = await websocket.receive_text()
        log(f"Received data ({len(data)} bytes): {data[:200]}...")

        message = json.loads(data)
        log(f"Parsed message - action={message.get('action')}")

        if message.get("action") != "start":
            log(f"Invalid action: {message.get('action')}", "WARNING")
            await websocket.send_json({
                "event_type": "error",
                "message": "Expected 'start' action with workflow data"
            })
            return

        workflow_data = message.get("workflow")
        if not workflow_data:
            log("No workflow data provided", "WARNING")
            await websocket.send_json({
                "event_type": "error",
                "message": "No workflow data provided"
            })
            return

        nodes = workflow_data.get('nodes', [])
        edges = workflow_data.get('edges', [])
        input_data = message.get('inputData', {})
        log(f"Workflow has {len(nodes)} nodes, {len(edges)} edges, input: {input_data}")

        # Generate temporary workflow ID
        temp_workflow_id = uuid4()
        execution_id = uuid4()
        log(f"Generated temp workflow ID: {temp_workflow_id}, execution ID: {execution_id}")

        # Create execution record in database
        try:
            db_session = AsyncSessionLocal()
            execution_record = WorkflowExecutionModel(
                execution_id=execution_id,
                workflow_id=temp_workflow_id,
                workflow_version=1,
                organization_id="default-org",
                triggered_by="user",
                trigger_source="manual",
                status="running",
                started_at=start_time,
                input_data=input_data,
                node_states={},
                node_executions=[],
                total_cost=0.0
            )
            db_session.add(execution_record)
            await db_session.commit()
            log(f"Created execution record: {execution_id}")
        except Exception as e:
            log(f"Failed to create execution record: {e}", "WARNING")
            # Continue without database persistence

        # Callback to send updates to WebSocket and track state
        async def send_update(event: ExecutionEvent):
            nonlocal node_states, node_executions, total_cost
            try:
                log(f"Sending event: {event.event_type}")
                await websocket.send_json(event.to_dict())

                # Track node states for database
                if event.node_id and event.status:
                    node_states[event.node_id] = {
                        "status": event.status.value if hasattr(event.status, 'value') else str(event.status),
                        "duration": event.execution_time,
                        "cost": event.cost,
                        "output": event.data
                    }
                    if event.cost:
                        total_cost += event.cost

                # Track step-by-step execution for debugger (format matches ExecutionStep type)
                # Map status to frontend expected values: 'completed', 'failed', 'pending', 'running'
                raw_status = event.status.value if hasattr(event.status, 'value') else str(event.status) if event.status else "pending"
                status_map = {
                    "success": "completed",
                    "completed": "completed",
                    "error": "failed",
                    "failed": "failed",
                    "running": "running",
                    "in_progress": "running",
                    "pending": "pending",
                }
                mapped_status = status_map.get(raw_status.lower(), raw_status)

                # Only track actual execution events, not initial "pending" status notifications
                # Skip events that are just marking nodes as "waiting to execute"
                is_execution_event = (
                    event.event_type in ["node_started", "node_completed", "node_failed", "execution_started", "execution_completed"] or
                    mapped_status in ["running", "completed", "failed"]
                )

                if is_execution_event:
                    node_executions.append({
                        "id": len(node_executions),  # Numeric ID as expected by frontend
                        "name": event.message or event.node_id or event.event_type,
                        "timestamp": datetime.utcnow().isoformat(),
                        "duration": f"{event.execution_time}ms" if event.execution_time else "-",
                        "status": mapped_status,
                        "state": {
                            "input": json.dumps(event.data.get("input")) if event.data and event.data.get("input") else None,
                            "output": json.dumps(event.data) if event.data else None,
                            "model": event.actual_model,
                            "tokens": None,
                            "cost": event.cost,
                        }
                    })
            except Exception as e:
                log(f"Failed to send update: {e}", "ERROR")

        # Get executor with detailed error handling
        # CRITICAL: Pass db_session so routing_resolver can be created for LLM execution
        log("Getting workflow executor...")
        try:
            executor = get_executor(db=db_session)
            log(f"Got executor: {type(executor).__name__}")
        except Exception as e:
            log(f"Failed to get executor: {e}", "ERROR")
            traceback.print_exc()
            await websocket.send_json({
                "event_type": "error",
                "message": f"Failed to initialize executor: {str(e)}"
            })
            return

        # Execute workflow
        log("Starting workflow execution...")
        execution_error = None
        try:
            await executor.execute_workflow(
                workflow_id=temp_workflow_id,
                workflow_data=workflow_data,
                send_update=send_update,
                input_data=input_data
            )
            log("Workflow execution completed successfully")
        except Exception as e:
            log(f"Workflow execution failed: {e}", "ERROR")
            traceback.print_exc()
            execution_error = str(e)
            await websocket.send_json({
                "event_type": "execution_failed",
                "message": f"Workflow execution failed: {str(e)}"
            })

        # Update execution record with final state
        if db_session and execution_record:
            try:
                end_time = datetime.utcnow()
                execution_record.status = "failed" if execution_error else "completed"
                execution_record.completed_at = end_time
                execution_record.duration_seconds = (end_time - start_time).total_seconds()
                execution_record.node_states = node_states
                execution_record.node_executions = node_executions  # For debugger time-travel
                execution_record.total_cost = total_cost
                execution_record.error_message = execution_error

                # Debug: Log what we're saving
                log(f"[DEBUG] Saving execution - node_states keys: {list(node_states.keys())}")
                log(f"[DEBUG] Saving execution - node_executions count: {len(node_executions)}")

                # Set output_data from the last node's output (or all node outputs)
                # Collect all node outputs (check for None explicitly, not just truthiness)
                output_data = {}
                for node_id, state in node_states.items():
                    if state.get("output") is not None:
                        output_data[node_id] = state["output"]

                # If no outputs from node_states, try to get from the last node_execution
                if not output_data and node_executions:
                    last_exec = node_executions[-1]
                    if last_exec.get("state", {}).get("output"):
                        output_data["final_output"] = json.loads(last_exec["state"]["output"])

                execution_record.output_data = output_data if output_data else {"status": "completed", "message": "Workflow executed successfully"}

                log(f"[DEBUG] output_data being saved: {list(output_data.keys()) if output_data else 'None'}")

                await db_session.commit()
                log(f"Updated execution record: {execution_id} - {execution_record.status}")
            except Exception as e:
                log(f"Failed to update execution record: {e}", "WARNING")

    except WebSocketDisconnect:
        log("Client disconnected")
    except json.JSONDecodeError as e:
        log(f"Invalid JSON from client: {e}", "ERROR")
        try:
            await websocket.send_json({
                "event_type": "error",
                "message": f"Invalid JSON: {str(e)}"
            })
        except:
            pass
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        traceback.print_exc()
        try:
            await websocket.send_json({
                "event_type": "error",
                "message": f"Server error: {str(e)}"
            })
        except Exception as send_error:
            log(f"Failed to send error message: {send_error}", "ERROR")
    finally:
        # Close database session
        if db_session:
            try:
                await db_session.close()
            except:
                pass
        try:
            log("Closing WebSocket connection")
            await websocket.close()
        except Exception as close_error:
            log(f"Error closing connection: {close_error}", "ERROR")


@router.websocket("/{workflow_id}/execute")
async def execute_workflow_ws(
    websocket: WebSocket,
    workflow_id: UUID,
):
    """
    Execute workflow with real-time status updates via WebSocket.
    Persists execution to database for history tracking.

    WebSocket Protocol:
    - Client connects to /api/workflows/{workflow_id}/execute
    - Server sends execution events as JSON
    - Client can send {"action": "stop"} to stop execution

    Event Types:
    - execution_started: Workflow started
    - node_status_changed: Node status updated
    - execution_completed: Workflow completed successfully
    - execution_failed: Workflow execution failed
    """
    import traceback
    from datetime import datetime
    from uuid import uuid4
    from backend.database.session import AsyncSessionLocal

    def log(msg: str, level: str = "INFO"):
        print(f"[WS-EXEC-SAVED] [{level}] {msg}", flush=True)

    await websocket.accept()

    execution_record = None
    db_session = None
    node_states = {}
    node_executions = []  # Track step-by-step events for debugger
    total_cost = 0.0
    start_time = datetime.utcnow()

    try:
        # Wait for client to send workflow data
        data = await websocket.receive_text()
        message = json.loads(data)

        if message.get("action") != "start":
            await websocket.send_json({
                "event_type": "error",
                "message": "Expected 'start' action with workflow data"
            })
            return

        workflow_data = message.get("workflow")
        if not workflow_data:
            await websocket.send_json({
                "event_type": "error",
                "message": "No workflow data provided"
            })
            return

        input_data = message.get('inputData', {})
        execution_id = uuid4()
        log(f"Starting execution {execution_id} for workflow {workflow_id}, input: {input_data}")

        # Create execution record in database
        try:
            db_session = AsyncSessionLocal()
            execution_record = WorkflowExecutionModel(
                execution_id=execution_id,
                workflow_id=workflow_id,
                workflow_version=1,
                organization_id="default-org",
                triggered_by="user",
                trigger_source="manual",
                status="running",
                started_at=start_time,
                input_data=input_data,
                node_states={},
                node_executions=[],
                total_cost=0.0
            )
            db_session.add(execution_record)
            await db_session.commit()
            log(f"Created execution record: {execution_id}")
        except Exception as e:
            log(f"Failed to create execution record: {e}", "WARNING")

        # Callback to send updates to WebSocket and track state
        async def send_update(event: ExecutionEvent):
            nonlocal node_states, node_executions, total_cost
            try:
                await websocket.send_json(event.to_dict())

                # Track node states for database
                if event.node_id and event.status:
                    node_states[event.node_id] = {
                        "status": event.status.value if hasattr(event.status, 'value') else str(event.status),
                        "duration": event.execution_time,
                        "cost": event.cost,
                        "output": event.data
                    }
                    if event.cost:
                        total_cost += event.cost

                # Track step-by-step execution for debugger (format matches ExecutionStep type)
                # Map status to frontend expected values: 'completed', 'failed', 'pending', 'running'
                raw_status = event.status.value if hasattr(event.status, 'value') else str(event.status) if event.status else "pending"
                status_map = {
                    "success": "completed",
                    "completed": "completed",
                    "error": "failed",
                    "failed": "failed",
                    "running": "running",
                    "in_progress": "running",
                    "pending": "pending",
                }
                mapped_status = status_map.get(raw_status.lower(), raw_status)

                # Only track actual execution events, not initial "pending" status notifications
                # Skip events that are just marking nodes as "waiting to execute"
                is_execution_event = (
                    event.event_type in ["node_started", "node_completed", "node_failed", "execution_started", "execution_completed"] or
                    mapped_status in ["running", "completed", "failed"]
                )

                if is_execution_event:
                    node_executions.append({
                        "id": len(node_executions),  # Numeric ID as expected by frontend
                        "name": event.message or event.node_id or event.event_type,
                        "timestamp": datetime.utcnow().isoformat(),
                        "duration": f"{event.execution_time}ms" if event.execution_time else "-",
                        "status": mapped_status,
                        "state": {
                            "input": json.dumps(event.data.get("input")) if event.data and event.data.get("input") else None,
                            "output": json.dumps(event.data) if event.data else None,
                            "model": event.actual_model,
                            "tokens": None,
                            "cost": event.cost,
                        }
                    })
            except Exception as e:
                log(f"Failed to send update: {e}", "ERROR")

        # Execute workflow
        # CRITICAL: Pass db_session so routing_resolver can be created for LLM execution
        executor = get_executor(db=db_session)
        execution_error = None
        try:
            await executor.execute_workflow(
                workflow_id=workflow_id,
                workflow_data=workflow_data,
                send_update=send_update,
                input_data=input_data
            )
            log("Workflow execution completed successfully")
        except Exception as e:
            log(f"Workflow execution failed: {e}", "ERROR")
            execution_error = str(e)
            await websocket.send_json({
                "event_type": "execution_failed",
                "message": f"Workflow execution failed: {str(e)}"
            })

        # Update execution record with final state
        if db_session and execution_record:
            try:
                end_time = datetime.utcnow()
                execution_record.status = "failed" if execution_error else "completed"
                execution_record.completed_at = end_time
                execution_record.duration_seconds = (end_time - start_time).total_seconds()
                execution_record.node_states = node_states
                execution_record.node_executions = node_executions  # For debugger time-travel
                execution_record.total_cost = total_cost
                execution_record.error_message = execution_error

                # Debug: Log what we're saving
                log(f"[DEBUG] Saving execution - node_states keys: {list(node_states.keys())}")
                log(f"[DEBUG] Saving execution - node_executions count: {len(node_executions)}")

                # Set output_data from the last node's output (or all node outputs)
                # Collect all node outputs (check for None explicitly, not just truthiness)
                output_data = {}
                for node_id, state in node_states.items():
                    if state.get("output") is not None:
                        output_data[node_id] = state["output"]

                # If no outputs from node_states, try to get from the last node_execution
                if not output_data and node_executions:
                    last_exec = node_executions[-1]
                    if last_exec.get("state", {}).get("output"):
                        output_data["final_output"] = json.loads(last_exec["state"]["output"])

                execution_record.output_data = output_data if output_data else {"status": "completed", "message": "Workflow executed successfully"}

                log(f"[DEBUG] output_data being saved: {list(output_data.keys()) if output_data else 'None'}")

                await db_session.commit()
                log(f"Updated execution record: {execution_id} - {execution_record.status}")
            except Exception as e:
                log(f"Failed to update execution record: {e}", "WARNING")

    except WebSocketDisconnect:
        print(f"Client disconnected from workflow {workflow_id} execution")
    except Exception as e:
        traceback.print_exc()
        try:
            await websocket.send_json({
                "event_type": "error",
                "message": f"Execution error: {str(e)}"
            })
        except:
            pass
    finally:
        # Close database session
        if db_session:
            try:
                await db_session.close()
            except:
                pass
        try:
            await websocket.close()
        except:
            pass
