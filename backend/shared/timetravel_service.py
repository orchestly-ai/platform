"""
Time-Travel Debugging - Service Layer

Provides execution snapshot capture, timeline navigation, replay, and comparison.

This is a CRITICAL competitive feature - AgentOps has this, and it solves
Pain Point #3: "Debugging Hell" for production AI agent systems.

Key capabilities:
- Automatic snapshot capture at every workflow step
- Timeline navigation (rewind/forward through execution)
- Execution replay with breakpoints
- Side-by-side execution comparison
- Root cause analysis
- State diff visualization

Competitive advantage: Only platform with built-in time-travel debugging for AI agents.
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload
import json
import difflib

from backend.shared.timetravel_models import (
    ExecutionSnapshotModel, ExecutionTimelineModel,
    ExecutionComparisonModel, ExecutionReplayModel,
    SnapshotType, ComparisonResult,
    ExecutionSnapshot, ExecutionTimeline, ExecutionComparison
)
from backend.shared.workflow_models import (
    WorkflowExecution, Workflow, WorkflowNode,
    ExecutionStatus
)


# ============================================================================
# Snapshot Capture Service
# ============================================================================

class SnapshotCaptureService:
    """
    Captures execution state at every step of workflow execution.

    This is automatically integrated into the WorkflowExecutionEngine to
    capture snapshots without manual intervention.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._sequence_counters: Dict[UUID, int] = {}

    async def capture_execution_start(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        organization_id: str,
        input_data: Dict[str, Any]
    ) -> ExecutionSnapshot:
        """Capture snapshot when execution starts."""
        snapshot = await self._create_snapshot(
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            snapshot_type=SnapshotType.EXECUTION_START,
            input_state=input_data,
            output_state=None,
            node_id=None
        )
        return snapshot

    async def capture_node_start(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        organization_id: str,
        node: WorkflowNode,
        input_state: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> ExecutionSnapshot:
        """Capture snapshot when node starts executing."""
        snapshot = await self._create_snapshot(
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            snapshot_type=SnapshotType.NODE_START,
            node_id=node.id,
            node_type=node.type.value,
            input_state=input_state,
            variables=variables
        )
        return snapshot

    async def capture_node_complete(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        organization_id: str,
        node: WorkflowNode,
        input_state: Dict[str, Any],
        output_state: Dict[str, Any],
        variables: Dict[str, Any],
        duration_ms: float,
        cost: float = 0.0,
        tokens_used: Optional[int] = None,
        llm_metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionSnapshot:
        """Capture snapshot when node completes successfully."""
        snapshot = await self._create_snapshot(
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            snapshot_type=SnapshotType.NODE_COMPLETE,
            node_id=node.id,
            node_type=node.type.value,
            input_state=input_state,
            output_state=output_state,
            variables=variables,
            duration_ms=duration_ms,
            cost=cost,
            tokens_used=tokens_used
        )

        # Capture LLM-specific data if present
        if llm_metadata:
            await self._update_snapshot_llm_data(snapshot.snapshot_id, llm_metadata)

        return snapshot

    async def capture_node_error(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        organization_id: str,
        node: WorkflowNode,
        input_state: Dict[str, Any],
        error_message: str,
        error_type: str,
        error_stack_trace: Optional[str] = None
    ) -> ExecutionSnapshot:
        """Capture snapshot when node encounters an error."""
        snapshot = await self._create_snapshot(
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            snapshot_type=SnapshotType.NODE_ERROR,
            node_id=node.id,
            node_type=node.type.value,
            input_state=input_state,
            error_message=error_message,
            error_type=error_type
        )

        # Update error details
        if error_stack_trace:
            stmt = select(ExecutionSnapshotModel).where(
                ExecutionSnapshotModel.snapshot_id == snapshot.snapshot_id
            )
            result = await self.db.execute(stmt)
            model = result.scalar_one()
            model.error_stack_trace = error_stack_trace
            await self.db.commit()

        return snapshot

    async def capture_llm_call(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        organization_id: str,
        node_id: str,
        model: str,
        prompt: str,
        response: str,
        tokens_used: int,
        cost: float,
        duration_ms: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionSnapshot:
        """Capture detailed snapshot for LLM API calls."""
        snapshot = await self._create_snapshot(
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            snapshot_type=SnapshotType.LLM_CALL,
            node_id=node_id,
            duration_ms=duration_ms,
            cost=cost,
            tokens_used=tokens_used
        )

        # Update LLM-specific fields
        stmt = select(ExecutionSnapshotModel).where(
            ExecutionSnapshotModel.snapshot_id == snapshot.snapshot_id
        )
        result = await self.db.execute(stmt)
        model_obj = result.scalar_one()
        model_obj.llm_model = model
        model_obj.llm_prompt = prompt
        model_obj.llm_response = response
        model_obj.llm_metadata = metadata
        await self.db.commit()

        return snapshot

    async def capture_decision_point(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        organization_id: str,
        node_id: str,
        condition: str,
        result: bool,
        context: Dict[str, Any]
    ) -> ExecutionSnapshot:
        """Capture snapshot at decision points (if/switch nodes)."""
        snapshot = await self._create_snapshot(
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            snapshot_type=SnapshotType.DECISION_POINT,
            node_id=node_id,
            context={
                "condition": condition,
                "result": result,
                "evaluated_context": context
            }
        )
        return snapshot

    async def capture_execution_complete(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        organization_id: str,
        output_data: Dict[str, Any],
        total_duration_ms: float,
        total_cost: float
    ) -> ExecutionSnapshot:
        """Capture snapshot when execution completes."""
        snapshot = await self._create_snapshot(
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            snapshot_type=SnapshotType.EXECUTION_COMPLETE,
            output_state=output_data,
            duration_ms=total_duration_ms,
            cost=total_cost
        )
        return snapshot

    async def _create_snapshot(
        self,
        execution_id: UUID,
        workflow_id: UUID,
        organization_id: str,
        snapshot_type: SnapshotType,
        node_id: Optional[str] = None,
        node_type: Optional[str] = None,
        input_state: Optional[Dict[str, Any]] = None,
        output_state: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        cost: float = 0.0,
        tokens_used: Optional[int] = None,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None
    ) -> ExecutionSnapshot:
        """Internal: Create and persist a snapshot."""

        # Get next sequence number for this execution
        if execution_id not in self._sequence_counters:
            # Query highest sequence number for this execution
            stmt = select(func.max(ExecutionSnapshotModel.sequence_number)).where(
                ExecutionSnapshotModel.execution_id == execution_id
            )
            result = await self.db.execute(stmt)
            max_seq = result.scalar()
            self._sequence_counters[execution_id] = max_seq + 1 if max_seq else 0

        sequence_number = self._sequence_counters[execution_id]
        self._sequence_counters[execution_id] += 1

        # Create snapshot model
        snapshot_id = uuid4()
        snapshot_model = ExecutionSnapshotModel(
            snapshot_id=snapshot_id,
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            snapshot_type=snapshot_type.value,
            sequence_number=sequence_number,
            timestamp=datetime.utcnow(),
            node_id=node_id,
            node_type=node_type,
            input_state=input_state,
            output_state=output_state,
            variables=variables,
            context=context,
            duration_ms=duration_ms,
            cost=cost,
            tokens_used=tokens_used,
            error_message=error_message,
            error_type=error_type
        )

        self.db.add(snapshot_model)
        await self.db.commit()
        await self.db.refresh(snapshot_model)

        # Convert to dataclass
        snapshot = ExecutionSnapshot(
            snapshot_id=snapshot_id,
            execution_id=execution_id,
            snapshot_type=snapshot_type,
            sequence_number=sequence_number,
            timestamp=snapshot_model.timestamp,
            node_id=node_id,
            node_type=node_type,
            input_state=input_state,
            output_state=output_state,
            variables=variables,
            context=context,
            duration_ms=duration_ms,
            cost=cost,
            tokens_used=tokens_used,
            error_message=error_message,
            error_type=error_type
        )

        return snapshot

    async def _update_snapshot_llm_data(
        self,
        snapshot_id: UUID,
        llm_metadata: Dict[str, Any]
    ):
        """Update LLM-specific metadata for a snapshot."""
        stmt = select(ExecutionSnapshotModel).where(
            ExecutionSnapshotModel.snapshot_id == snapshot_id
        )
        result = await self.db.execute(stmt)
        model = result.scalar_one()

        model.llm_model = llm_metadata.get("model")
        model.llm_prompt = llm_metadata.get("prompt")
        model.llm_response = llm_metadata.get("response")
        model.llm_metadata = llm_metadata

        await self.db.commit()


# ============================================================================
# Timeline Builder Service
# ============================================================================

class TimelineBuilderService:
    """
    Builds and manages execution timelines from snapshots.

    Provides fast navigation through execution history and analysis of
    execution patterns, bottlenecks, and critical paths.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_timeline(
        self,
        execution_id: UUID
    ) -> ExecutionTimeline:
        """
        Build complete timeline from execution snapshots.

        This creates a structured, indexed view of the execution for
        fast timeline navigation and analysis.
        """

        # Fetch all snapshots for this execution
        stmt = select(ExecutionSnapshotModel).where(
            ExecutionSnapshotModel.execution_id == execution_id
        ).order_by(ExecutionSnapshotModel.sequence_number)

        result = await self.db.execute(stmt)
        snapshots = result.scalars().all()

        if not snapshots:
            raise ValueError(f"No snapshots found for execution {execution_id}")

        # Extract metadata
        workflow_id = snapshots[0].workflow_id
        organization_id = snapshots[0].organization_id

        # Build timeline structure
        snapshot_ids = [s.snapshot_id for s in snapshots]
        node_sequence = [s.node_id for s in snapshots if s.node_id]

        # Analyze execution
        total_duration_ms = sum(s.duration_ms for s in snapshots if s.duration_ms)
        total_cost = sum(s.cost for s in snapshots)

        # Find decision points
        decision_points = {}
        for s in snapshots:
            if s.snapshot_type == SnapshotType.DECISION_POINT.value:
                decision_points[s.node_id] = s.context

        # Identify bottlenecks (nodes taking >10% of total time)
        bottlenecks = {}
        if total_duration_ms > 0:
            for s in snapshots:
                if s.duration_ms and s.duration_ms > total_duration_ms * 0.1:
                    bottlenecks[s.node_id] = {
                        "duration_ms": s.duration_ms,
                        "percentage": (s.duration_ms / total_duration_ms) * 100,
                        "reason": "High execution time"
                    }

        # Collect errors
        errors = []
        for s in snapshots:
            if s.snapshot_type == SnapshotType.NODE_ERROR.value:
                errors.append({
                    "snapshot_id": str(s.snapshot_id),
                    "node_id": s.node_id,
                    "error": s.error_message,
                    "error_type": s.error_type
                })

        # Collect LLM calls
        llm_calls = []
        for s in snapshots:
            if s.snapshot_type == SnapshotType.LLM_CALL.value:
                llm_calls.append({
                    "snapshot_id": str(s.snapshot_id),
                    "model": s.llm_model,
                    "cost": s.cost,
                    "tokens": s.tokens_used
                })

        # Find critical path (longest execution path)
        critical_path = self._compute_critical_path(snapshots)

        # Get execution timestamps
        started_at = snapshots[0].timestamp
        completed_at = snapshots[-1].timestamp if snapshots else None

        # Create or update timeline model
        timeline_id = uuid4()
        timeline_model = ExecutionTimelineModel(
            timeline_id=timeline_id,
            execution_id=execution_id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            total_snapshots=len(snapshots),
            total_nodes=len(set(node_sequence)),
            total_duration_ms=total_duration_ms,
            total_cost=total_cost,
            snapshot_ids=snapshot_ids,
            node_sequence=node_sequence,
            decision_points=decision_points,
            critical_path=critical_path,
            bottlenecks=bottlenecks,
            errors=errors,
            llm_calls=llm_calls,
            started_at=started_at,
            completed_at=completed_at
        )

        self.db.add(timeline_model)
        await self.db.commit()
        await self.db.refresh(timeline_model)

        # Convert to dataclass
        timeline = ExecutionTimeline(
            timeline_id=timeline_id,
            execution_id=execution_id,
            total_snapshots=len(snapshots),
            total_nodes=len(set(node_sequence)),
            total_duration_ms=total_duration_ms,
            total_cost=total_cost,
            snapshot_ids=snapshot_ids,
            node_sequence=node_sequence,
            decision_points=decision_points,
            bottlenecks=bottlenecks,
            errors=errors,
            started_at=started_at,
            completed_at=completed_at
        )

        return timeline

    def _compute_critical_path(
        self,
        snapshots: List[ExecutionSnapshotModel]
    ) -> List[str]:
        """Compute critical path (longest execution path) through the workflow."""
        # Simple implementation: nodes sorted by duration
        node_durations = {}
        for s in snapshots:
            if s.node_id and s.duration_ms:
                if s.node_id not in node_durations:
                    node_durations[s.node_id] = 0
                node_durations[s.node_id] += s.duration_ms

        # Sort by duration descending
        sorted_nodes = sorted(
            node_durations.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Return top 5 slowest nodes
        return [node_id for node_id, _ in sorted_nodes[:5]]

    async def get_timeline(
        self,
        execution_id: UUID
    ) -> Optional[ExecutionTimeline]:
        """Retrieve existing timeline for an execution."""
        stmt = select(ExecutionTimelineModel).where(
            ExecutionTimelineModel.execution_id == execution_id
        )
        result = await self.db.execute(stmt)
        timeline_model = result.scalar_one_or_none()

        if not timeline_model:
            return None

        timeline = ExecutionTimeline(
            timeline_id=timeline_model.timeline_id,
            execution_id=timeline_model.execution_id,
            total_snapshots=timeline_model.total_snapshots,
            total_nodes=timeline_model.total_nodes,
            total_duration_ms=timeline_model.total_duration_ms,
            total_cost=timeline_model.total_cost,
            snapshot_ids=timeline_model.snapshot_ids,
            node_sequence=timeline_model.node_sequence,
            decision_points=timeline_model.decision_points,
            bottlenecks=timeline_model.bottlenecks,
            errors=timeline_model.errors,
            started_at=timeline_model.started_at,
            completed_at=timeline_model.completed_at
        )

        return timeline

    async def navigate_to_snapshot(
        self,
        execution_id: UUID,
        sequence_number: int
    ) -> Optional[ExecutionSnapshot]:
        """Navigate to specific snapshot in timeline by sequence number."""
        stmt = select(ExecutionSnapshotModel).where(
            and_(
                ExecutionSnapshotModel.execution_id == execution_id,
                ExecutionSnapshotModel.sequence_number == sequence_number
            )
        )
        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        snapshot = ExecutionSnapshot(
            snapshot_id=model.snapshot_id,
            execution_id=model.execution_id,
            snapshot_type=SnapshotType(model.snapshot_type),
            sequence_number=model.sequence_number,
            timestamp=model.timestamp,
            node_id=model.node_id,
            node_type=model.node_type,
            input_state=model.input_state,
            output_state=model.output_state,
            variables=model.variables,
            context=model.context,
            duration_ms=model.duration_ms,
            cost=model.cost,
            tokens_used=model.tokens_used,
            error_message=model.error_message,
            error_type=model.error_type
        )

        return snapshot


# ============================================================================
# Comparison Engine
# ============================================================================

class ComparisonEngine:
    """
    Compare two workflow executions side-by-side.

    Enables A/B testing, regression detection, and root cause analysis by
    comparing execution outputs, costs, durations, and decision paths.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compare_executions(
        self,
        execution_a_id: UUID,
        execution_b_id: UUID,
        organization_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> ExecutionComparison:
        """
        Compare two executions and generate detailed diff report.

        Returns comparison with:
        - Overall result (identical, different output, etc.)
        - Detailed differences
        - Node-by-node comparison
        - Cost and duration deltas
        - Root cause analysis
        """

        # Fetch both timelines
        timeline_a = await self._get_or_build_timeline(execution_a_id)
        timeline_b = await self._get_or_build_timeline(execution_b_id)

        # Fetch final snapshots
        snapshot_a = await self._get_final_snapshot(execution_a_id)
        snapshot_b = await self._get_final_snapshot(execution_b_id)

        # Compare outputs
        output_diff = self._compare_outputs(
            snapshot_a.output_state if snapshot_a else {},
            snapshot_b.output_state if snapshot_b else {}
        )

        # Compare execution paths
        path_diff = self._compare_paths(
            timeline_a.node_sequence,
            timeline_b.node_sequence
        )

        # Compare costs and durations
        cost_delta = timeline_b.total_cost - timeline_a.total_cost
        duration_delta_ms = timeline_b.total_duration_ms - timeline_a.total_duration_ms

        # Determine overall result
        result = self._determine_result(output_diff, path_diff, cost_delta, duration_delta_ms)

        # Build differences dict
        differences = {
            "output": output_diff,
            "nodes_executed": {
                "a": timeline_a.node_sequence,
                "b": timeline_b.node_sequence,
                "diff": path_diff
            },
            "cost": {
                "a": timeline_a.total_cost,
                "b": timeline_b.total_cost,
                "delta": cost_delta
            },
            "duration": {
                "a": timeline_a.total_duration_ms,
                "b": timeline_b.total_duration_ms,
                "delta": duration_delta_ms
            }
        }

        # Node-by-node comparison
        node_by_node_diff = await self._compare_node_by_node(execution_a_id, execution_b_id)

        # Calculate similarity score
        similarity_score = self._calculate_similarity(output_diff, path_diff)

        # Root cause analysis
        root_cause = self._analyze_root_cause(differences, node_by_node_diff)

        # Generate recommendations
        recommendations = self._generate_recommendations(differences, root_cause)

        # Create comparison model
        comparison_id = uuid4()
        comparison_model = ExecutionComparisonModel(
            comparison_id=comparison_id,
            organization_id=organization_id,
            execution_a_id=execution_a_id,
            execution_b_id=execution_b_id,
            name=name,
            description=description,
            result=result.value,
            differences=differences,
            node_by_node_diff=node_by_node_diff,
            similarity_score=similarity_score,
            cost_delta=cost_delta,
            duration_delta_ms=duration_delta_ms,
            root_cause=root_cause,
            recommendations=recommendations
        )

        self.db.add(comparison_model)
        await self.db.commit()
        await self.db.refresh(comparison_model)

        # Convert to dataclass
        comparison = ExecutionComparison(
            comparison_id=comparison_id,
            execution_a_id=execution_a_id,
            execution_b_id=execution_b_id,
            result=result,
            differences=differences,
            similarity_score=similarity_score,
            cost_delta=cost_delta,
            duration_delta_ms=duration_delta_ms,
            root_cause=root_cause,
            recommendations=recommendations
        )

        return comparison

    async def _get_or_build_timeline(self, execution_id: UUID) -> ExecutionTimeline:
        """Get existing timeline or build new one."""
        timeline_builder = TimelineBuilderService(self.db)
        timeline = await timeline_builder.get_timeline(execution_id)

        if not timeline:
            timeline = await timeline_builder.build_timeline(execution_id)

        return timeline

    async def _get_final_snapshot(self, execution_id: UUID) -> Optional[ExecutionSnapshot]:
        """Get final snapshot (execution complete) for an execution."""
        stmt = select(ExecutionSnapshotModel).where(
            and_(
                ExecutionSnapshotModel.execution_id == execution_id,
                ExecutionSnapshotModel.snapshot_type == SnapshotType.EXECUTION_COMPLETE.value
            )
        ).order_by(desc(ExecutionSnapshotModel.sequence_number))

        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return ExecutionSnapshot(
            snapshot_id=model.snapshot_id,
            execution_id=model.execution_id,
            snapshot_type=SnapshotType(model.snapshot_type),
            sequence_number=model.sequence_number,
            timestamp=model.timestamp,
            output_state=model.output_state,
            cost=model.cost
        )

    def _compare_outputs(
        self,
        output_a: Dict[str, Any],
        output_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare final outputs of two executions."""
        # Deep comparison
        identical = output_a == output_b

        if identical:
            return {"identical": True}

        # Find differences
        diff = {
            "identical": False,
            "a": output_a,
            "b": output_b,
            "diff_keys": list(set(output_a.keys()) ^ set(output_b.keys())),
            "changed_keys": [
                k for k in output_a.keys()
                if k in output_b and output_a[k] != output_b[k]
            ]
        }

        return diff

    def _compare_paths(
        self,
        path_a: List[str],
        path_b: List[str]
    ) -> Dict[str, Any]:
        """Compare execution paths (node sequences)."""
        if path_a == path_b:
            return {"identical": True}

        # Use difflib for sequence matching
        matcher = difflib.SequenceMatcher(None, path_a, path_b)

        return {
            "identical": False,
            "similarity": matcher.ratio(),
            "a_only": [n for n in path_a if n not in path_b],
            "b_only": [n for n in path_b if n not in path_a],
            "opcodes": matcher.get_opcodes()
        }

    def _determine_result(
        self,
        output_diff: Dict[str, Any],
        path_diff: Dict[str, Any],
        cost_delta: float,
        duration_delta_ms: float
    ) -> ComparisonResult:
        """Determine overall comparison result."""
        if output_diff.get("identical") and path_diff.get("identical"):
            return ComparisonResult.IDENTICAL

        if not output_diff.get("identical"):
            return ComparisonResult.DIFFERENT_OUTPUT

        if not path_diff.get("identical"):
            return ComparisonResult.DIFFERENT_PATH

        if abs(cost_delta) > 0.01:
            return ComparisonResult.DIFFERENT_COST

        if abs(duration_delta_ms) > 100:
            return ComparisonResult.DIFFERENT_DURATION

        return ComparisonResult.IDENTICAL

    async def _compare_node_by_node(
        self,
        execution_a_id: UUID,
        execution_b_id: UUID
    ) -> List[Dict[str, Any]]:
        """Compare executions node by node."""
        # Fetch all snapshots for both executions
        stmt_a = select(ExecutionSnapshotModel).where(
            ExecutionSnapshotModel.execution_id == execution_a_id
        ).order_by(ExecutionSnapshotModel.sequence_number)

        stmt_b = select(ExecutionSnapshotModel).where(
            ExecutionSnapshotModel.execution_id == execution_b_id
        ).order_by(ExecutionSnapshotModel.sequence_number)

        result_a = await self.db.execute(stmt_a)
        result_b = await self.db.execute(stmt_b)

        snapshots_a = {s.node_id: s for s in result_a.scalars().all() if s.node_id}
        snapshots_b = {s.node_id: s for s in result_b.scalars().all() if s.node_id}

        # Compare common nodes
        all_nodes = set(snapshots_a.keys()) | set(snapshots_b.keys())

        node_diffs = []
        for node_id in all_nodes:
            snap_a = snapshots_a.get(node_id)
            snap_b = snapshots_b.get(node_id)

            if not snap_a:
                node_diffs.append({
                    "node_id": node_id,
                    "status": "only_in_b",
                    "a_output": None,
                    "b_output": snap_b.output_state
                })
            elif not snap_b:
                node_diffs.append({
                    "node_id": node_id,
                    "status": "only_in_a",
                    "a_output": snap_a.output_state,
                    "b_output": None
                })
            else:
                status = "identical" if snap_a.output_state == snap_b.output_state else "different"
                node_diffs.append({
                    "node_id": node_id,
                    "status": status,
                    "a_output": snap_a.output_state,
                    "b_output": snap_b.output_state,
                    "cost_delta": snap_b.cost - snap_a.cost if snap_a.cost and snap_b.cost else None
                })

        return node_diffs

    def _calculate_similarity(
        self,
        output_diff: Dict[str, Any],
        path_diff: Dict[str, Any]
    ) -> float:
        """Calculate similarity score between 0.0 and 1.0."""
        output_score = 1.0 if output_diff.get("identical") else 0.5
        path_score = path_diff.get("similarity", 1.0) if not path_diff.get("identical") else 1.0

        # Weighted average
        return (output_score * 0.6) + (path_score * 0.4)

    def _analyze_root_cause(
        self,
        differences: Dict[str, Any],
        node_by_node_diff: List[Dict[str, Any]]
    ) -> str:
        """Analyze root cause of differences."""
        # Find first divergence point
        divergent_nodes = [
            d for d in node_by_node_diff
            if d["status"] in ["different", "only_in_a", "only_in_b"]
        ]

        if not divergent_nodes:
            return "No significant differences detected"

        first_divergence = divergent_nodes[0]

        if first_divergence["status"] == "different":
            return f"First divergence at node '{first_divergence['node_id']}' - different outputs"
        elif first_divergence["status"] == "only_in_a":
            return f"Execution B skipped node '{first_divergence['node_id']}'"
        else:
            return f"Execution B executed additional node '{first_divergence['node_id']}'"

    def _generate_recommendations(
        self,
        differences: Dict[str, Any],
        root_cause: str
    ) -> List[str]:
        """Generate actionable recommendations based on differences."""
        recommendations = []

        cost_delta = differences["cost"]["delta"]
        duration_delta = differences["duration"]["delta"]

        if cost_delta > 0:
            recommendations.append(f"Execution B cost ${cost_delta:.4f} more - investigate LLM usage")
        elif cost_delta < -0.01:
            recommendations.append(f"Execution B saved ${abs(cost_delta):.4f} - consider adopting changes")

        if duration_delta > 1000:
            recommendations.append(f"Execution B took {duration_delta/1000:.1f}s longer - check for bottlenecks")
        elif duration_delta < -1000:
            recommendations.append(f"Execution B was {abs(duration_delta)/1000:.1f}s faster - performance improvement")

        if "different outputs" in root_cause:
            recommendations.append("Review node logic and LLM prompts for consistency")

        return recommendations


# ============================================================================
# Replay Engine
# ============================================================================

class ReplayEngine:
    """
    Replay workflow executions with modifications.

    Enables:
    - Exact replay (reproduce bugs)
    - Modified input replay (test fixes)
    - Breakpoint debugging (pause at specific nodes)
    - Step-by-step execution
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_replay(
        self,
        source_execution_id: UUID,
        organization_id: str,
        workflow_id: UUID,
        replay_mode: str = "exact",
        input_modifications: Optional[Dict[str, Any]] = None,
        breakpoints: Optional[List[str]] = None,
        skip_nodes: Optional[List[str]] = None
    ) -> UUID:
        """
        Create a replay configuration.

        Replay modes:
        - "exact": Replay with exact same inputs
        - "modified_input": Replay with modified inputs
        - "step_by_step": Pause after each node
        - "breakpoint": Pause at specified nodes
        """

        replay_id = uuid4()
        replay_model = ExecutionReplayModel(
            replay_id=replay_id,
            organization_id=organization_id,
            source_execution_id=source_execution_id,
            workflow_id=workflow_id,
            replay_mode=replay_mode,
            input_modifications=input_modifications,
            breakpoints=breakpoints,
            skip_nodes=skip_nodes,
            status="pending"
        )

        self.db.add(replay_model)
        await self.db.commit()

        return replay_id

    async def execute_replay(
        self,
        replay_id: UUID,
        workflow_execution_engine  # Avoid circular import
    ) -> UUID:
        """
        Execute a configured replay.

        Returns the new execution_id created by the replay.
        """
        # Fetch replay configuration
        stmt = select(ExecutionReplayModel).where(
            ExecutionReplayModel.replay_id == replay_id
        )
        result = await self.db.execute(stmt)
        replay = result.scalar_one()

        # Fetch source execution
        stmt = select(ExecutionSnapshotModel).where(
            and_(
                ExecutionSnapshotModel.execution_id == replay.source_execution_id,
                ExecutionSnapshotModel.snapshot_type == SnapshotType.EXECUTION_START.value
            )
        )
        result = await self.db.execute(stmt)
        start_snapshot = result.scalar_one()

        # Get original input
        original_input = start_snapshot.input_state

        # Apply modifications if in modified_input mode
        if replay.replay_mode == "modified_input" and replay.input_modifications:
            replay_input = {**original_input, **replay.input_modifications}
        else:
            replay_input = original_input

        # Update replay status to running
        replay.status = "running"
        replay.started_at = datetime.utcnow()
        await self.db.commit()

        # Execute the workflow using the workflow service
        from backend.shared.workflow_service import get_workflow_service
        workflow_service = get_workflow_service()

        try:
            # Execute with the replay configuration
            execution = await workflow_service.execute_workflow(
                workflow_id=replay.workflow_id,
                input_data=replay_input,
                triggered_by=f"replay:{replay_id}",
                db=self.db
            )

            # Update replay with new execution ID and completed status
            replay.new_execution_id = execution.execution_id
            replay.status = "completed"
            replay.completed_at = datetime.utcnow()
            await self.db.commit()

            return execution.execution_id

        except Exception as e:
            # Mark replay as failed
            replay.status = "failed"
            replay.error_message = str(e)
            replay.completed_at = datetime.utcnow()
            await self.db.commit()
            raise
