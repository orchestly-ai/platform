"""
Time-Travel Debugging - Data Models

Enables rewinding and replaying agent executions for debugging:
- Execution snapshots at every step
- State capture for all variables
- Timeline navigation
- Side-by-side execution comparison
- Root cause analysis

Competitive advantage: AgentOps has this, it's critical for production debugging.
This solves pain point #3: "Debugging Hell"
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Text, Integer,
    ForeignKey, Index, Float, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY, JSONB

from backend.database.session import Base


class SnapshotType(Enum):
    """Type of execution snapshot"""
    EXECUTION_START = "execution_start"
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    NODE_ERROR = "node_error"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_FAILED = "execution_failed"
    STATE_CHANGE = "state_change"
    LLM_CALL = "llm_call"
    HTTP_REQUEST = "http_request"
    DECISION_POINT = "decision_point"


class ComparisonResult(Enum):
    """Result of comparing two snapshots"""
    IDENTICAL = "identical"
    DIFFERENT_OUTPUT = "different_output"
    DIFFERENT_PATH = "different_path"
    DIFFERENT_ERROR = "different_error"
    DIFFERENT_COST = "different_cost"
    DIFFERENT_DURATION = "different_duration"


class ExecutionSnapshotModel(Base):
    """
    Execution snapshot - captures state at a specific point in time.

    Stores complete execution context at each step, enabling time-travel debugging.
    """
    __tablename__ = "execution_snapshots"

    # Primary key
    snapshot_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Execution reference
    execution_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    workflow_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    organization_id = Column(String(255), nullable=False, index=True)

    # Snapshot metadata
    snapshot_type = Column(String(50), nullable=False)
    sequence_number = Column(Integer, nullable=False)  # Order within execution
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Node context (if snapshot is for a node)
    node_id = Column(String(255), nullable=True, index=True)
    node_type = Column(String(50), nullable=True)
    node_name = Column(String(255), nullable=True)

    # State capture
    input_state = Column(JSONB, nullable=True)
    # Complete input to this step

    output_state = Column(JSONB, nullable=True)
    # Output from this step

    variables = Column(JSONB, nullable=True)
    # All workflow variables at this point

    context = Column(JSONB, nullable=True)
    # Execution context (previous node outputs, etc.)

    # Performance metrics
    duration_ms = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    cpu_usage_percent = Column(Float, nullable=True)

    # Cost tracking
    cost = Column(Float, nullable=False, default=0.0)
    tokens_used = Column(Integer, nullable=True)

    # LLM-specific data (if applicable)
    llm_model = Column(String(100), nullable=True)
    llm_prompt = Column(Text, nullable=True)
    llm_response = Column(Text, nullable=True)
    llm_extra_metadata = Column(JSONB, nullable=True)

    # HTTP-specific data (if applicable)
    http_method = Column(String(10), nullable=True)
    http_url = Column(String(512), nullable=True)
    http_status_code = Column(Integer, nullable=True)
    http_request = Column(JSONB, nullable=True)
    http_response = Column(JSONB, nullable=True)

    # Error information
    error_message = Column(Text, nullable=True)
    error_type = Column(String(255), nullable=True)
    error_stack_trace = Column(Text, nullable=True)

    # Metadata
    extra_metadata = Column(JSONB, nullable=True)
    tags = Column(ARRAY(String), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_snapshot_execution', 'execution_id'),
        Index('idx_snapshot_workflow', 'workflow_id'),
        Index('idx_snapshot_org', 'organization_id'),
        Index('idx_snapshot_node', 'node_id'),
        Index('idx_snapshot_sequence', 'execution_id', 'sequence_number'),
        Index('idx_snapshot_timestamp', 'timestamp'),
        Index('idx_snapshot_type', 'snapshot_type'),
    )

    def __repr__(self):
        return f"<ExecutionSnapshot(id={self.snapshot_id}, type={self.snapshot_type}, node={self.node_id})>"


class ExecutionTimelineModel(Base):
    """
    Execution timeline - organizes snapshots into navigable timeline.

    Provides indexed view of execution for fast timeline navigation.
    """
    __tablename__ = "execution_timelines"

    # Primary key
    timeline_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Execution reference
    execution_id = Column(PG_UUID(as_uuid=True), nullable=False, unique=True, index=True)
    workflow_id = Column(PG_UUID(as_uuid=True), nullable=False)
    organization_id = Column(String(255), nullable=False, index=True)

    # Timeline metadata
    total_snapshots = Column(Integer, nullable=False, default=0)
    total_nodes = Column(Integer, nullable=False, default=0)
    total_duration_ms = Column(Float, nullable=False, default=0.0)
    total_cost = Column(Float, nullable=False, default=0.0)

    # Timeline structure
    snapshot_ids = Column(ARRAY(PG_UUID(as_uuid=True)), nullable=False, default=list)
    # Ordered list of snapshot IDs

    node_sequence = Column(ARRAY(String), nullable=False, default=list)
    # Ordered list of node IDs executed

    decision_points = Column(JSONB, nullable=True)
    # {node_id: {condition: bool, branches: [...]}}

    critical_path = Column(ARRAY(String), nullable=True)
    # Longest execution path

    # Analysis results
    bottlenecks = Column(JSONB, nullable=True)
    # {node_id: {duration_ms: X, reason: "..."}}

    errors = Column(JSONB, nullable=True)
    # [{snapshot_id: X, node_id: Y, error: "..."}]

    llm_calls = Column(JSONB, nullable=True)
    # [{snapshot_id: X, model: Y, cost: Z, tokens: T}]

    # Timestamps
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_timeline_execution', 'execution_id'),
        Index('idx_timeline_org', 'organization_id'),
        Index('idx_timeline_started', 'started_at'),
    )

    def __repr__(self):
        return f"<ExecutionTimeline(id={self.timeline_id}, execution={self.execution_id})>"


class ExecutionComparisonModel(Base):
    """
    Execution comparison - compare two execution runs side-by-side.

    Enables A/B testing, regression detection, and performance analysis.
    """
    __tablename__ = "execution_comparisons"

    # Primary key
    comparison_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Executions being compared
    execution_a_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    execution_b_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Comparison metadata
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Comparison results
    result = Column(String(50), nullable=False)  # ComparisonResult enum

    differences = Column(JSONB, nullable=False, default=dict)
    # {
    #   "output": {"a": X, "b": Y, "diff": Z},
    #   "nodes_executed": {"a": [..], "b": [..]},
    #   "cost": {"a": X, "b": Y, "delta": Z},
    #   "duration": {"a": X, "b": Y, "delta": Z}
    # }

    node_by_node_diff = Column(JSONB, nullable=True)
    # [{node_id: X, a_output: Y, b_output: Z, status: "different"}]

    # Metrics
    similarity_score = Column(Float, nullable=True)  # 0.0 - 1.0

    cost_delta = Column(Float, nullable=True)
    duration_delta_ms = Column(Float, nullable=True)

    # Analysis
    root_cause = Column(Text, nullable=True)
    recommendations = Column(ARRAY(String), nullable=True)

    # Metadata
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_comparison_org', 'organization_id'),
        Index('idx_comparison_exec_a', 'execution_a_id'),
        Index('idx_comparison_exec_b', 'execution_b_id'),
        Index('idx_comparison_created', 'created_at'),
    )

    def __repr__(self):
        return f"<ExecutionComparison(id={self.comparison_id}, result={self.result})>"


class ExecutionReplayModel(Base):
    """
    Execution replay - stores configuration for replaying an execution.

    Enables reproducing issues by replaying with same or modified inputs.
    """
    __tablename__ = "execution_replays"

    # Primary key
    replay_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Source execution
    source_execution_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    workflow_id = Column(PG_UUID(as_uuid=True), nullable=False)

    # Replay configuration
    replay_mode = Column(String(50), nullable=False)
    # "exact" | "modified_input" | "step_by_step" | "breakpoint"

    input_modifications = Column(JSONB, nullable=True)
    # Modified inputs for replay

    breakpoints = Column(ARRAY(String), nullable=True)
    # Node IDs where to pause

    skip_nodes = Column(ARRAY(String), nullable=True)
    # Node IDs to skip

    # Replay result
    new_execution_id = Column(PG_UUID(as_uuid=True), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    # "pending" | "running" | "completed" | "failed"

    # Comparison with original
    matched_original = Column(Boolean, nullable=True)
    differences_found = Column(JSONB, nullable=True)

    # Metadata
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_replay_org', 'organization_id'),
        Index('idx_replay_source', 'source_execution_id'),
        Index('idx_replay_created', 'created_at'),
    )

    def __repr__(self):
        return f"<ExecutionReplay(id={self.replay_id}, mode={self.replay_mode})>"


# Dataclasses for application logic

@dataclass
class ExecutionSnapshot:
    """Execution snapshot data structure"""
    snapshot_id: UUID
    execution_id: UUID
    snapshot_type: SnapshotType
    sequence_number: int
    timestamp: datetime

    node_id: Optional[str] = None
    node_type: Optional[str] = None
    input_state: Optional[Dict[str, Any]] = None
    output_state: Optional[Dict[str, Any]] = None
    variables: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None

    duration_ms: Optional[float] = None
    cost: float = 0.0
    tokens_used: Optional[int] = None

    error_message: Optional[str] = None
    error_type: Optional[str] = None


@dataclass
class ExecutionTimeline:
    """Execution timeline data structure"""
    timeline_id: UUID
    execution_id: UUID
    total_snapshots: int
    total_nodes: int
    total_duration_ms: float
    total_cost: float

    snapshot_ids: List[UUID] = field(default_factory=list)
    node_sequence: List[str] = field(default_factory=list)
    decision_points: Dict[str, Any] = field(default_factory=dict)
    bottlenecks: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ExecutionComparison:
    """Execution comparison data structure"""
    comparison_id: UUID
    execution_a_id: UUID
    execution_b_id: UUID
    result: ComparisonResult

    differences: Dict[str, Any] = field(default_factory=dict)
    similarity_score: Optional[float] = None
    cost_delta: Optional[float] = None
    duration_delta_ms: Optional[float] = None
    root_cause: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)


# Snapshot type configurations

SNAPSHOT_TYPE_CONFIGS = {
    "execution_start": {
        "name": "Execution Started",
        "icon": "▶️",
        "color": "#4CAF50",
        "critical": True
    },
    "node_start": {
        "name": "Node Started",
        "icon": "🔵",
        "color": "#2196F3",
        "critical": False
    },
    "node_complete": {
        "name": "Node Completed",
        "icon": "✅",
        "color": "#4CAF50",
        "critical": False
    },
    "node_error": {
        "name": "Node Error",
        "icon": "❌",
        "color": "#F44336",
        "critical": True
    },
    "execution_complete": {
        "name": "Execution Completed",
        "icon": "🏁",
        "color": "#4CAF50",
        "critical": True
    },
    "execution_failed": {
        "name": "Execution Failed",
        "icon": "💥",
        "color": "#F44336",
        "critical": True
    },
    "llm_call": {
        "name": "LLM API Call",
        "icon": "🤖",
        "color": "#9C27B0",
        "critical": False
    },
    "decision_point": {
        "name": "Decision Point",
        "icon": "🔀",
        "color": "#FF9800",
        "critical": True
    }
}
