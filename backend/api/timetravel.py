"""
Time-Travel Debugging API

REST endpoints for time-travel debugging capabilities:
- Timeline navigation
- Execution snapshots
- Execution comparison
- Execution replay

Competitive advantage: AgentOps has this feature - this is our answer.
Solves Pain Point #3: "Debugging Hell" in production AI agents.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime

from backend.database.session import get_db
from backend.shared.timetravel_service import (
    SnapshotCaptureService,
    TimelineBuilderService,
    ComparisonEngine,
    ReplayEngine
)
from backend.shared.timetravel_models import (
    SnapshotType, ComparisonResult,
    ExecutionSnapshotModel, ExecutionTimelineModel,
    ExecutionComparisonModel, ExecutionReplayModel
)
from backend.shared.auth_utils import get_current_organization
from sqlalchemy import select, and_, desc


router = APIRouter(prefix="/api/v1/timetravel", tags=["time-travel-debugging"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SnapshotResponse(BaseModel):
    """Response model for execution snapshot"""
    snapshot_id: UUID
    execution_id: UUID
    snapshot_type: str
    sequence_number: int
    timestamp: datetime
    node_id: Optional[str] = None
    node_type: Optional[str] = None
    input_state: Optional[dict] = None
    output_state: Optional[dict] = None
    variables: Optional[dict] = None
    context: Optional[dict] = None
    duration_ms: Optional[float] = None
    cost: float = 0.0
    tokens_used: Optional[int] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None

    class Config:
        from_attributes = True


class TimelineResponse(BaseModel):
    """Response model for execution timeline"""
    timeline_id: UUID
    execution_id: UUID
    total_snapshots: int
    total_nodes: int
    total_duration_ms: float
    total_cost: float
    snapshot_ids: List[UUID]
    node_sequence: List[str]
    decision_points: Optional[dict] = None
    critical_path: Optional[List[str]] = None
    bottlenecks: Optional[dict] = None
    errors: Optional[List[dict]] = None
    llm_calls: Optional[List[dict]] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ComparisonResponse(BaseModel):
    """Response model for execution comparison"""
    comparison_id: UUID
    execution_a_id: UUID
    execution_b_id: UUID
    result: str
    differences: dict
    node_by_node_diff: Optional[List[dict]] = None
    similarity_score: Optional[float] = None
    cost_delta: Optional[float] = None
    duration_delta_ms: Optional[float] = None
    root_cause: Optional[str] = None
    recommendations: Optional[List[str]] = None

    class Config:
        from_attributes = True


class CreateComparisonRequest(BaseModel):
    """Request to create execution comparison"""
    execution_a_id: UUID = Field(..., description="First execution to compare")
    execution_b_id: UUID = Field(..., description="Second execution to compare")
    name: Optional[str] = Field(None, description="Comparison name")
    description: Optional[str] = Field(None, description="Comparison description")


class CreateReplayRequest(BaseModel):
    """Request to create execution replay"""
    source_execution_id: UUID = Field(..., description="Source execution to replay")
    workflow_id: UUID = Field(..., description="Workflow ID")
    replay_mode: str = Field(
        "exact",
        description="Replay mode: exact, modified_input, step_by_step, breakpoint"
    )
    input_modifications: Optional[dict] = Field(None, description="Modified inputs")
    breakpoints: Optional[List[str]] = Field(None, description="Node IDs for breakpoints")
    skip_nodes: Optional[List[str]] = Field(None, description="Node IDs to skip")


class ReplayResponse(BaseModel):
    """Response model for replay"""
    replay_id: UUID
    source_execution_id: UUID
    workflow_id: UUID
    replay_mode: str
    status: str
    new_execution_id: Optional[UUID] = None
    matched_original: Optional[bool] = None

    class Config:
        from_attributes = True


# ============================================================================
# Timeline Navigation Endpoints
# ============================================================================

@router.get(
    "/executions/{execution_id}/timeline",
    response_model=TimelineResponse,
    summary="Get execution timeline",
    description="Get complete timeline for an execution with snapshots, analysis, and navigation"
)
async def get_execution_timeline(
    execution_id: UUID,
    rebuild: bool = Query(False, description="Force rebuild timeline from snapshots"),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Get or build execution timeline.

    The timeline provides:
    - Complete snapshot sequence
    - Node execution order
    - Decision points (if/switch nodes)
    - Bottleneck analysis
    - Critical path
    - Error summary
    - LLM call summary
    """
    timeline_service = TimelineBuilderService(db)

    if rebuild:
        # Force rebuild
        timeline = await timeline_service.build_timeline(execution_id)
    else:
        # Get existing or build
        timeline = await timeline_service.get_timeline(execution_id)
        if not timeline:
            timeline = await timeline_service.build_timeline(execution_id)

    # Verify organization access
    stmt = select(ExecutionTimelineModel).where(
        and_(
            ExecutionTimelineModel.execution_id == execution_id,
            ExecutionTimelineModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    timeline_model = result.scalar_one_or_none()

    if not timeline_model:
        raise HTTPException(status_code=404, detail="Timeline not found or access denied")

    return TimelineResponse(
        timeline_id=timeline.timeline_id,
        execution_id=timeline.execution_id,
        total_snapshots=timeline.total_snapshots,
        total_nodes=timeline.total_nodes,
        total_duration_ms=timeline.total_duration_ms,
        total_cost=timeline.total_cost,
        snapshot_ids=timeline.snapshot_ids,
        node_sequence=timeline.node_sequence,
        decision_points=timeline.decision_points,
        critical_path=getattr(timeline, 'critical_path', None),
        bottlenecks=timeline.bottlenecks,
        errors=timeline.errors,
        llm_calls=getattr(timeline, 'llm_calls', None),
        started_at=timeline.started_at,
        completed_at=timeline.completed_at
    )


@router.get(
    "/executions/{execution_id}/snapshots",
    response_model=List[SnapshotResponse],
    summary="Get execution snapshots",
    description="Get all snapshots for an execution in chronological order"
)
async def get_execution_snapshots(
    execution_id: UUID,
    snapshot_type: Optional[str] = Query(None, description="Filter by snapshot type"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    limit: int = Query(100, ge=1, le=1000, description="Max snapshots to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Get snapshots for an execution with optional filtering.

    Supports filtering by:
    - Snapshot type (execution_start, node_start, llm_call, etc.)
    - Node ID
    - Pagination
    """
    # Build query
    query = select(ExecutionSnapshotModel).where(
        and_(
            ExecutionSnapshotModel.execution_id == execution_id,
            ExecutionSnapshotModel.organization_id == organization_id
        )
    )

    if snapshot_type:
        query = query.where(ExecutionSnapshotModel.snapshot_type == snapshot_type)

    if node_id:
        query = query.where(ExecutionSnapshotModel.node_id == node_id)

    query = query.order_by(ExecutionSnapshotModel.sequence_number)
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    snapshots = result.scalars().all()

    return [SnapshotResponse.model_validate(s) for s in snapshots]


@router.get(
    "/executions/{execution_id}/snapshots/{sequence_number}",
    response_model=SnapshotResponse,
    summary="Navigate to specific snapshot",
    description="Get snapshot at specific sequence number (timeline navigation)"
)
async def navigate_to_snapshot(
    execution_id: UUID,
    sequence_number: int,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Navigate to specific snapshot in timeline.

    This is the core time-travel navigation endpoint - allows stepping
    through execution history by sequence number.
    """
    timeline_service = TimelineBuilderService(db)

    snapshot = await timeline_service.navigate_to_snapshot(execution_id, sequence_number)

    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Verify organization access
    stmt = select(ExecutionSnapshotModel).where(
        and_(
            ExecutionSnapshotModel.snapshot_id == snapshot.snapshot_id,
            ExecutionSnapshotModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="Access denied")

    return SnapshotResponse.model_validate(model)


@router.get(
    "/executions/{execution_id}/snapshots/node/{node_id}",
    response_model=List[SnapshotResponse],
    summary="Get snapshots for specific node",
    description="Get all snapshots for a specific node (useful for analyzing node behavior)"
)
async def get_node_snapshots(
    execution_id: UUID,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Get all snapshots for a specific node.

    Useful for analyzing:
    - Node start/complete/error states
    - Input/output changes
    - Performance across multiple executions
    """
    stmt = select(ExecutionSnapshotModel).where(
        and_(
            ExecutionSnapshotModel.execution_id == execution_id,
            ExecutionSnapshotModel.node_id == node_id,
            ExecutionSnapshotModel.organization_id == organization_id
        )
    ).order_by(ExecutionSnapshotModel.sequence_number)

    result = await db.execute(stmt)
    snapshots = result.scalars().all()

    return [SnapshotResponse.model_validate(s) for s in snapshots]


# ============================================================================
# Execution Comparison Endpoints
# ============================================================================

@router.post(
    "/comparisons",
    response_model=ComparisonResponse,
    summary="Compare two executions",
    description="Create side-by-side comparison of two workflow executions"
)
async def create_comparison(
    request: CreateComparisonRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Compare two workflow executions side-by-side.

    Generates:
    - Output differences
    - Execution path differences
    - Cost and duration deltas
    - Node-by-node comparison
    - Root cause analysis
    - Recommendations
    """
    comparison_engine = ComparisonEngine(db)

    comparison = await comparison_engine.compare_executions(
        execution_a_id=request.execution_a_id,
        execution_b_id=request.execution_b_id,
        organization_id=organization_id,
        name=request.name,
        description=request.description
    )

    return ComparisonResponse(
        comparison_id=comparison.comparison_id,
        execution_a_id=comparison.execution_a_id,
        execution_b_id=comparison.execution_b_id,
        result=comparison.result.value,
        differences=comparison.differences,
        node_by_node_diff=getattr(comparison, 'node_by_node_diff', None),
        similarity_score=comparison.similarity_score,
        cost_delta=comparison.cost_delta,
        duration_delta_ms=comparison.duration_delta_ms,
        root_cause=comparison.root_cause,
        recommendations=comparison.recommendations
    )


@router.get(
    "/comparisons/{comparison_id}",
    response_model=ComparisonResponse,
    summary="Get comparison details",
    description="Retrieve existing execution comparison"
)
async def get_comparison(
    comparison_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Get details of existing comparison."""
    stmt = select(ExecutionComparisonModel).where(
        and_(
            ExecutionComparisonModel.comparison_id == comparison_id,
            ExecutionComparisonModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    return ComparisonResponse.model_validate(comparison)


@router.get(
    "/comparisons",
    response_model=List[ComparisonResponse],
    summary="List comparisons",
    description="List all execution comparisons for organization"
)
async def list_comparisons(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """List all comparisons for the organization."""
    stmt = select(ExecutionComparisonModel).where(
        ExecutionComparisonModel.organization_id == organization_id
    ).order_by(desc(ExecutionComparisonModel.created_at)).limit(limit).offset(offset)

    result = await db.execute(stmt)
    comparisons = result.scalars().all()

    return [ComparisonResponse.model_validate(c) for c in comparisons]


# ============================================================================
# Execution Replay Endpoints
# ============================================================================

@router.post(
    "/replays",
    response_model=ReplayResponse,
    summary="Create execution replay",
    description="Create a replay configuration for re-executing a workflow"
)
async def create_replay(
    request: CreateReplayRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Create a replay configuration.

    Replay modes:
    - exact: Replay with exact same inputs
    - modified_input: Replay with modified inputs (for testing fixes)
    - step_by_step: Pause after each node
    - breakpoint: Pause at specified nodes
    """
    replay_engine = ReplayEngine(db)

    replay_id = await replay_engine.create_replay(
        source_execution_id=request.source_execution_id,
        organization_id=organization_id,
        workflow_id=request.workflow_id,
        replay_mode=request.replay_mode,
        input_modifications=request.input_modifications,
        breakpoints=request.breakpoints,
        skip_nodes=request.skip_nodes
    )

    # Fetch created replay
    stmt = select(ExecutionReplayModel).where(
        ExecutionReplayModel.replay_id == replay_id
    )
    result = await db.execute(stmt)
    replay = result.scalar_one()

    return ReplayResponse.model_validate(replay)


@router.post(
    "/replays/{replay_id}/execute",
    response_model=ReplayResponse,
    summary="Execute replay",
    description="Execute a configured replay (starts new workflow execution)"
)
async def execute_replay(
    replay_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Execute a configured replay.

    This starts a new workflow execution based on the replay configuration.
    Returns the new execution ID.
    """
    # Verify access
    stmt = select(ExecutionReplayModel).where(
        and_(
            ExecutionReplayModel.replay_id == replay_id,
            ExecutionReplayModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    replay = result.scalar_one_or_none()

    if not replay:
        raise HTTPException(status_code=404, detail="Replay not found")

    if replay.status != "pending":
        raise HTTPException(status_code=400, detail=f"Replay already {replay.status}")

    # Execute replay (workflow service is obtained internally by ReplayEngine)
    replay_engine = ReplayEngine(db)
    new_execution_id = await replay_engine.execute_replay(replay_id, None)

    # Update and return
    stmt = select(ExecutionReplayModel).where(
        ExecutionReplayModel.replay_id == replay_id
    )
    result = await db.execute(stmt)
    updated_replay = result.scalar_one()

    return ReplayResponse.model_validate(updated_replay)


@router.get(
    "/replays/{replay_id}",
    response_model=ReplayResponse,
    summary="Get replay status",
    description="Get status and details of a replay"
)
async def get_replay(
    replay_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """Get replay details and status."""
    stmt = select(ExecutionReplayModel).where(
        and_(
            ExecutionReplayModel.replay_id == replay_id,
            ExecutionReplayModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    replay = result.scalar_one_or_none()

    if not replay:
        raise HTTPException(status_code=404, detail="Replay not found")

    return ReplayResponse.model_validate(replay)


@router.get(
    "/replays",
    response_model=List[ReplayResponse],
    summary="List replays",
    description="List all execution replays for organization"
)
async def list_replays(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """List all replays for the organization."""
    query = select(ExecutionReplayModel).where(
        ExecutionReplayModel.organization_id == organization_id
    )

    if status:
        query = query.where(ExecutionReplayModel.status == status)

    query = query.order_by(desc(ExecutionReplayModel.created_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    replays = result.scalars().all()

    return [ReplayResponse.model_validate(r) for r in replays]


# ============================================================================
# Analysis Endpoints
# ============================================================================

@router.get(
    "/executions/{execution_id}/analysis/bottlenecks",
    summary="Get execution bottlenecks",
    description="Identify performance bottlenecks in execution"
)
async def get_execution_bottlenecks(
    execution_id: UUID,
    threshold_percentage: float = Query(10.0, ge=1.0, le=100.0, description="Minimum % of total time to be considered bottleneck"),
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Analyze execution to identify bottlenecks.

    Returns nodes that took more than threshold_percentage of total execution time.
    """
    timeline_service = TimelineBuilderService(db)

    timeline = await timeline_service.get_timeline(execution_id)
    if not timeline:
        timeline = await timeline_service.build_timeline(execution_id)

    # Verify access
    stmt = select(ExecutionTimelineModel).where(
        and_(
            ExecutionTimelineModel.execution_id == execution_id,
            ExecutionTimelineModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Timeline not found or access denied")

    return {
        "execution_id": str(execution_id),
        "total_duration_ms": timeline.total_duration_ms,
        "threshold_percentage": threshold_percentage,
        "bottlenecks": timeline.bottlenecks,
        "critical_path": getattr(timeline, 'critical_path', [])
    }


@router.get(
    "/executions/{execution_id}/analysis/decision-points",
    summary="Get execution decision points",
    description="Get all decision points (if/switch nodes) in execution"
)
async def get_execution_decision_points(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Get all decision points in execution.

    Shows which branches were taken at if/switch nodes.
    """
    timeline_service = TimelineBuilderService(db)

    timeline = await timeline_service.get_timeline(execution_id)
    if not timeline:
        timeline = await timeline_service.build_timeline(execution_id)

    # Verify access
    stmt = select(ExecutionTimelineModel).where(
        and_(
            ExecutionTimelineModel.execution_id == execution_id,
            ExecutionTimelineModel.organization_id == organization_id
        )
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Timeline not found or access denied")

    return {
        "execution_id": str(execution_id),
        "decision_points": timeline.decision_points
    }


@router.get(
    "/executions/{execution_id}/analysis/llm-calls",
    summary="Get LLM call summary",
    description="Get summary of all LLM API calls in execution"
)
async def get_llm_calls_summary(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: str = Depends(get_current_organization)
):
    """
    Get summary of all LLM API calls in execution.

    Shows models used, tokens, costs for each LLM call.
    """
    # Fetch LLM call snapshots
    stmt = select(ExecutionSnapshotModel).where(
        and_(
            ExecutionSnapshotModel.execution_id == execution_id,
            ExecutionSnapshotModel.snapshot_type == SnapshotType.LLM_CALL.value,
            ExecutionSnapshotModel.organization_id == organization_id
        )
    ).order_by(ExecutionSnapshotModel.sequence_number)

    result = await db.execute(stmt)
    llm_snapshots = result.scalars().all()

    total_cost = sum(s.cost for s in llm_snapshots if s.cost)
    total_tokens = sum(s.tokens_used for s in llm_snapshots if s.tokens_used)

    calls = [
        {
            "sequence_number": s.sequence_number,
            "model": s.llm_model,
            "tokens": s.tokens_used,
            "cost": s.cost,
            "duration_ms": s.duration_ms,
            "prompt_preview": s.llm_prompt[:100] + "..." if s.llm_prompt and len(s.llm_prompt) > 100 else s.llm_prompt
        }
        for s in llm_snapshots
    ]

    return {
        "execution_id": str(execution_id),
        "total_llm_calls": len(llm_snapshots),
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "calls": calls
    }
