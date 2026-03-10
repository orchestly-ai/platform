"""
Visual DAG Builder - Workflow Models

Drag-and-drop workflow orchestration with:
- React Flow based visual canvas
- 400+ integration nodes (LLM, data, logic, control flow)
- Template marketplace
- One-click deployment
- Real-time execution monitoring

95% customer requirement, biggest competitive gap vs n8n.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

import os
from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Text, Integer,
    ForeignKey, Index, Float, Enum as SQLEnum, TypeDecorator
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY, JSONB

from backend.database.session import Base

# Database-agnostic UUID type that works with both PostgreSQL and SQLite
USE_SQLITE = os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes")


class UniversalUUID(TypeDecorator):
    """
    Platform-independent UUID type.
    Uses native UUID for PostgreSQL and String(36) for SQLite.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            return str(value) if value else None

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        else:
            from uuid import UUID as PyUUID
            return PyUUID(value) if isinstance(value, str) else value


class UniversalJSON(TypeDecorator):
    """
    Platform-independent JSON type.
    Uses JSONB for PostgreSQL (supports indexing) and JSON for SQLite.
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        else:
            from sqlalchemy import JSON
            return dialect.type_descriptor(JSON())


class WorkflowStatus(Enum):
    """Workflow execution status"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class NodeType(Enum):
    """Types of workflow nodes"""
    # Agent nodes
    AGENT_LLM = "agent_llm"
    AGENT_FUNCTION = "agent_function"
    AGENT_TOOL = "agent_tool"

    # Data nodes
    DATA_INPUT = "data_input"
    DATA_OUTPUT = "data_output"
    DATA_TRANSFORM = "data_transform"
    DATA_MERGE = "data_merge"
    DATA_SPLIT = "data_split"

    # Control flow
    CONTROL_IF = "control_if"
    CONTROL_SWITCH = "control_switch"
    CONTROL_LOOP = "control_loop"
    CONTROL_PARALLEL = "control_parallel"
    CONTROL_WAIT = "control_wait"

    # Integration nodes
    INTEGRATION_HTTP = "integration_http"
    INTEGRATION_DATABASE = "integration_database"
    INTEGRATION_STORAGE = "integration_storage"
    INTEGRATION_QUEUE = "integration_queue"
    INTEGRATION_WEBHOOK = "integration_webhook"

    # LLM providers
    LLM_OPENAI = "llm_openai"
    LLM_ANTHROPIC = "llm_anthropic"
    LLM_DEEPSEEK = "llm_deepseek"
    LLM_GOOGLE = "llm_google"

    # Utilities
    UTIL_LOGGER = "util_logger"
    UTIL_ERROR_HANDLER = "util_error_handler"
    UTIL_RETRY = "util_retry"
    UTIL_CACHE = "util_cache"

    # Visual Builder node types (aliases for compatibility)
    TRIGGER = "trigger"
    SUPERVISOR = "supervisor"
    WORKER = "worker"
    TOOL = "tool"
    INTEGRATION = "integration"
    CONDITION = "condition"
    INPUT = "input"
    OUTPUT = "output"
    HTTP = "http"
    WEBHOOK = "webhook"
    LLM = "llm"

    # Additional node types
    AI = "ai"  # Alias for LLM
    HITL = "hitl"  # Human-in-the-loop approval
    END = "end"  # Workflow end node


class ExecutionStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class WorkflowModel(Base):
    """
    Workflow definition.

    Stores the visual workflow graph (nodes + edges) and metadata.
    """
    __tablename__ = "workflows"

    # Primary key
    workflow_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(UniversalJSON(), nullable=True)  # JSONB for PostgreSQL, JSON for SQLite

    # Status
    status = Column(String(50), nullable=False, default=WorkflowStatus.DRAFT.value)
    version = Column(Integer, nullable=False, default=1)

    # Graph definition (React Flow format)
    nodes = Column(JSON, nullable=False, default=list)
    # [{"id": "node_1", "type": "agent_llm", "position": {"x": 100, "y": 100}, "data": {...}}]

    edges = Column(JSON, nullable=False, default=list)
    # [{"id": "edge_1", "source": "node_1", "target": "node_2", "sourceHandle": "out", "targetHandle": "in"}]

    # Execution settings
    max_execution_time_seconds = Column(Integer, nullable=False, default=3600)  # 1 hour
    retry_on_failure = Column(Boolean, nullable=False, default=True)
    max_retries = Column(Integer, nullable=False, default=3)

    # Variables and configuration
    variables = Column(JSON, nullable=True, default=dict)
    # {"api_key": "sk-...", "model": "gpt-4", ...}

    environment = Column(String(50), nullable=False, default="development")
    # development, staging, production

    # Triggers
    trigger_type = Column(String(50), nullable=True)
    # manual, schedule, webhook, event

    trigger_config = Column(JSON, nullable=True)
    # {"cron": "0 0 * * *", "webhook_secret": "...", ...}

    # Analytics
    total_executions = Column(Integer, nullable=False, default=0)
    successful_executions = Column(Integer, nullable=False, default=0)
    failed_executions = Column(Integer, nullable=False, default=0)
    avg_execution_time_seconds = Column(Float, nullable=True)
    average_execution_time = Column(Float, nullable=True)
    execution_count = Column(Integer, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0.0)
    last_executed_at = Column(DateTime, nullable=True)

    # Template flag
    is_template = Column(Boolean, nullable=False, default=False)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Foreign keys
    # sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')

    # Indexes
    __table_args__ = (
        Index('idx_workflow_org', 'organization_id'),
        Index('idx_workflow_status', 'status'),
        Index('idx_workflow_created', 'created_at'),
        Index('idx_workflow_tags', 'tags', postgresql_using='gin', postgresql_ops={'tags': 'jsonb_path_ops'}),
    )

    def __repr__(self):
        return f"<Workflow(id={self.workflow_id}, name={self.name})>"


class WorkflowExecutionModel(Base):
    """
    Workflow execution instance.

    Tracks a single execution of a workflow with inputs, outputs, and status.
    """
    __tablename__ = "workflow_executions"

    # Primary key
    execution_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Workflow
    workflow_id = Column(UniversalUUID(), nullable=False, index=True)
    workflow_version = Column(Integer, nullable=False)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Trigger
    triggered_by = Column(String(255), nullable=True)  # user_id or "system"
    trigger_source = Column(String(50), nullable=True)
    # manual, schedule, webhook, event

    # Status
    status = Column(String(50), nullable=False, default=ExecutionStatus.PENDING.value)

    # Timing
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Input/Output
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_node_id = Column(String(255), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Node execution state
    node_states = Column(JSON, nullable=True, default=dict)
    # {"node_1": {"status": "completed", "output": {...}, "duration": 1.5}, ...}

    node_executions = Column(JSON, nullable=False, default=dict)
    # Node execution tracking

    # Metrics
    total_cost = Column(Float, nullable=False, default=0.0)
    total_tokens = Column(Integer, nullable=True)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Foreign keys
    # sa.ForeignKeyConstraint(['workflow_id'], ['workflows.workflow_id'], ondelete='CASCADE')
    # sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')

    # Indexes
    __table_args__ = (
        Index('idx_exec_workflow', 'workflow_id'),
        Index('idx_exec_org', 'organization_id'),
        Index('idx_exec_status', 'status'),
        Index('idx_exec_created', 'created_at'),
        Index('idx_exec_started', 'started_at'),
    )

    def __repr__(self):
        return f"<WorkflowExecution(id={self.execution_id}, status={self.status})>"


class WorkflowTemplateModel(Base):
    """
    Workflow template for marketplace.

    Pre-built workflows that users can clone and customize.
    """
    __tablename__ = "workflow_templates"

    # Primary key
    template_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    # "data-processing", "llm-chains", "automation", "analytics", etc.

    tags = Column(UniversalJSON(), nullable=True)  # JSONB for PostgreSQL, JSON for SQLite

    # Preview
    thumbnail_url = Column(String(512), nullable=True)

    # Template content (same as workflow)
    nodes = Column(JSON, nullable=False)
    edges = Column(JSON, nullable=False)
    variables = Column(JSON, nullable=True, default=dict)

    # Popularity
    use_count = Column(Integer, nullable=False, default=0)
    rating = Column(Float, nullable=True)

    # Visibility
    is_public = Column(Boolean, nullable=False, default=True)
    is_featured = Column(Boolean, nullable=False, default=False)

    # Author
    created_by = Column(String(255), nullable=True)
    organization_id = Column(String(255), nullable=True)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_template_category', 'category'),
        Index('idx_template_public', 'is_public'),
        Index('idx_template_featured', 'is_featured'),
        Index('idx_template_tags', 'tags', postgresql_using='gin', postgresql_ops={'tags': 'jsonb_path_ops'}),
        {'extend_existing': True}
    )

    def __repr__(self):
        return f"<WorkflowTemplate(id={self.template_id}, name={self.name})>"


# Dataclasses for application logic

@dataclass
class WorkflowNode:
    """Workflow node definition"""
    id: str
    type: NodeType
    position: Dict[str, float]  # {"x": 100, "y": 200}
    data: Dict[str, Any]  # Node-specific configuration

    # Optional
    label: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class WorkflowEdge:
    """Workflow edge (connection between nodes)"""
    id: str
    source: str  # Source node ID
    target: str  # Target node ID

    # Optional
    source_handle: Optional[str] = "out"
    target_handle: Optional[str] = "in"
    label: Optional[str] = None
    animated: bool = False


@dataclass
class Workflow:
    """Workflow data structure"""
    workflow_id: UUID
    organization_id: str
    name: str
    description: Optional[str]
    status: WorkflowStatus
    version: int

    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]

    # Settings
    max_execution_time_seconds: int = 3600
    retry_on_failure: bool = True
    max_retries: int = 3

    variables: Dict[str, Any] = field(default_factory=dict)
    environment: str = "development"

    # Triggers
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None

    # Analytics
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_execution_time_seconds: Optional[float] = None
    total_cost: float = 0.0

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


@dataclass
class WorkflowExecution:
    """Workflow execution instance"""
    execution_id: UUID
    workflow_id: UUID
    workflow_version: int
    organization_id: str

    status: ExecutionStatus

    # Trigger
    triggered_by: Optional[str] = None
    trigger_source: Optional[str] = None

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Data
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None

    # Errors
    error_message: Optional[str] = None
    error_node_id: Optional[str] = None
    retry_count: int = 0

    # Node states
    node_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Metrics
    total_cost: float = 0.0
    total_tokens: Optional[int] = None

    created_at: Optional[datetime] = None


@dataclass
class WorkflowTemplate:
    """Workflow template"""
    template_id: UUID
    name: str
    description: Optional[str]
    category: Optional[str]
    tags: List[str]

    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    variables: Dict[str, Any] = field(default_factory=dict)

    thumbnail_url: Optional[str] = None
    use_count: int = 0
    rating: Optional[float] = None

    is_public: bool = True
    is_featured: bool = False

    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


# Node type configurations

NODE_TYPE_CONFIGS = {
    "agent_llm": {
        "name": "LLM Agent",
        "category": "agents",
        "icon": "🤖",
        "description": "Call an LLM with a prompt",
        "inputs": ["prompt", "context"],
        "outputs": ["response", "tokens"],
        "config_schema": {
            "model": "string",
            "temperature": "number",
            "max_tokens": "number"
        }
    },
    "data_transform": {
        "name": "Transform Data",
        "category": "data",
        "icon": "🔄",
        "description": "Transform data using Python code",
        "inputs": ["data"],
        "outputs": ["result"],
        "config_schema": {
            "code": "string"
        }
    },
    "control_if": {
        "name": "If/Else",
        "category": "control",
        "icon": "🔀",
        "description": "Branch based on condition",
        "inputs": ["condition"],
        "outputs": ["true", "false"],
        "config_schema": {
            "condition": "string"
        }
    },
    "llm_openai": {
        "name": "OpenAI",
        "category": "llm",
        "icon": "🧠",
        "description": "Call OpenAI API",
        "inputs": ["prompt"],
        "outputs": ["response"],
        "config_schema": {
            "model": "string",
            "api_key": "string"
        }
    }
}

# Template categories

TEMPLATE_CATEGORIES = [
    "Data Processing",
    "LLM Chains",
    "Automation",
    "Analytics",
    "Customer Support",
    "Content Generation",
    "Data Extraction",
    "Monitoring & Alerts"
]
