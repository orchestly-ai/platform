"""
Database Models

SQLAlchemy ORM models for persistent storage.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, JSON, Enum,
    ForeignKey, Index, Text, TypeDecorator, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship

from backend.database.session import Base
from backend.shared.models import (
    AgentStatus, TaskStatus, TaskPriority, LLMProvider
)


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


class AgentModel(Base):
    """
    Agent database model.

    Stores agent configuration and registration information.
    """
    __tablename__ = "agents"

    # Primary key
    agent_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization (multi-tenancy) - references rbac_models.OrganizationModel
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # Agent configuration
    name = Column(String(255), nullable=False, index=True)
    framework = Column(String(50), nullable=False)
    version = Column(String(50), nullable=False)

    # Capabilities (stored as JSONB array for GIN indexing in PostgreSQL, JSON in SQLite)
    capabilities = Column(UniversalJSON(), nullable=False, default=list)

    # Capacity and limits
    max_concurrent_tasks = Column(Integer, nullable=False, default=5)
    cost_limit_daily = Column(Float, nullable=False, default=100.0)
    cost_limit_monthly = Column(Float, nullable=False, default=3000.0)

    # LLM configuration
    llm_provider = Column(Enum(LLMProvider), nullable=False, default=LLMProvider.OPENAI)
    llm_model = Column(String(100), nullable=True)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Status - Using VARCHAR to match existing database schema
    status = Column(String(20), nullable=False, default=AgentStatus.ACTIVE.value)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_heartbeat = Column(DateTime, nullable=True)

    # Relationships
    tasks = relationship("TaskModel", back_populates="agent", cascade="all, delete-orphan")
    state = relationship("AgentStateModel", back_populates="agent", uselist=False, cascade="all, delete-orphan")

    # Indexes and constraints
    __table_args__ = (
        # Agent name must be unique per organization (not globally)
        UniqueConstraint('organization_id', 'name', name='uq_agent_org_name'),
        Index('idx_agent_status', 'status'),
        Index('idx_agent_organization', 'organization_id'),
        Index('idx_agent_org_status', 'organization_id', 'status'),
        # GIN index on JSONB column with proper operator class
        Index('idx_agent_capabilities', 'capabilities', postgresql_using='gin', postgresql_ops={'capabilities': 'jsonb_path_ops'}),
    )

    def __repr__(self):
        return f"<Agent(id={self.agent_id}, name={self.name}, status={self.status})>"


class AgentStateModel(Base):
    """
    Agent runtime state.

    Tracks current execution state and metrics.
    """
    __tablename__ = "agent_states"

    # Primary key (one-to-one with Agent)
    agent_id = Column(PG_UUID(as_uuid=True), ForeignKey("agents.agent_id"), primary_key=True)

    # Organization (multi-tenancy) - denormalized for direct filtered queries
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=True, index=True)

    # Current state
    active_tasks = Column(Integer, nullable=False, default=0)
    tasks_completed = Column(Integer, nullable=False, default=0)
    tasks_failed = Column(Integer, nullable=False, default=0)

    # Cost tracking
    total_cost_today = Column(Float, nullable=False, default=0.0)
    total_cost_month = Column(Float, nullable=False, default=0.0)
    cost_last_reset_day = Column(DateTime, nullable=True)
    cost_last_reset_month = Column(DateTime, nullable=True)

    # Timestamps
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent = relationship("AgentModel", back_populates="state")

    def __repr__(self):
        return f"<AgentState(agent_id={self.agent_id}, active={self.active_tasks}, completed={self.tasks_completed})>"


class TaskModel(Base):
    """
    Task database model.

    Stores task configuration, status, and results.
    """
    __tablename__ = "tasks"

    # Primary key
    task_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization (multi-tenancy) - references rbac_models.OrganizationModel
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # Task configuration
    capability = Column(String(100), nullable=False, index=True)
    priority = Column(Enum(TaskPriority), nullable=False, default=TaskPriority.NORMAL)

    # Input/output
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON, nullable=True)

    # Task parameters
    timeout_seconds = Column(Integer, nullable=False, default=300)
    max_retries = Column(Integer, nullable=False, default=3)
    retry_count = Column(Integer, nullable=False, default=0)

    # Status - Using VARCHAR to match existing database schema
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING.value, index=True)

    # Assignment
    assigned_agent_id = Column(PG_UUID(as_uuid=True), ForeignKey("agents.agent_id"), nullable=True, index=True)

    # Cost tracking
    estimated_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    agent = relationship("AgentModel", back_populates="tasks")

    # Indexes
    __table_args__ = (
        Index('idx_task_capability_status', 'capability', 'status'),
        Index('idx_task_agent_status', 'assigned_agent_id', 'status'),
        Index('idx_task_created', 'created_at'),
        Index('idx_task_organization', 'organization_id'),
        Index('idx_task_org_status', 'organization_id', 'status'),
    )

    def __repr__(self):
        return f"<Task(id={self.task_id}, capability={self.capability}, status={self.status})>"


class TaskExecutionModel(Base):
    """
    Task execution history.

    Stores detailed execution logs for debugging and analytics.
    """
    __tablename__ = "task_executions"

    # Primary key
    execution_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization (multi-tenancy) - references rbac_models.OrganizationModel
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # Task reference
    task_id = Column(PG_UUID(as_uuid=True), ForeignKey("tasks.task_id"), nullable=False, index=True)
    agent_id = Column(PG_UUID(as_uuid=True), ForeignKey("agents.agent_id"), nullable=False, index=True)

    # Execution details
    attempt_number = Column(Integer, nullable=False, default=1)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Result
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)

    # Cost
    cost = Column(Float, nullable=True)

    # LLM usage
    llm_calls = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    # Logs and metadata
    logs = Column(JSON, nullable=True)
    extra_metadata = Column(JSON, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_execution_task', 'task_id'),
        Index('idx_execution_agent', 'agent_id'),
        Index('idx_execution_started', 'started_at'),
        Index('idx_execution_organization', 'organization_id'),
    )

    def __repr__(self):
        return f"<TaskExecution(id={self.execution_id}, task={self.task_id}, success={self.success})>"


class MetricModel(Base):
    """
    Time-series metrics (for future TimescaleDB migration).

    Stores aggregated metrics for analytics.
    """
    __tablename__ = "metrics"

    # Primary key
    metric_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization (multi-tenancy) - references rbac_models.OrganizationModel
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # Timestamp (will become hypertable partition key)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)  # agent, task, system

    # Reference IDs
    agent_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    task_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    capability = Column(String(100), nullable=True, index=True)

    # Metric value
    value = Column(Float, nullable=False)

    # Additional data
    tags = Column(JSON, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_metric_name_time', 'metric_name', 'timestamp'),
        Index('idx_metric_agent_time', 'agent_id', 'timestamp'),
        Index('idx_metric_capability_time', 'capability', 'timestamp'),
        Index('idx_metric_organization', 'organization_id'),
        Index('idx_metric_org_time', 'organization_id', 'timestamp'),
    )

    def __repr__(self):
        return f"<Metric(name={self.metric_name}, value={self.value}, timestamp={self.timestamp})>"


class AlertModel(Base):
    """
    Alert history.

    Stores all alerts for audit trail and analytics.
    """
    __tablename__ = "alerts"

    # Primary key
    alert_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization (multi-tenancy) - references rbac_models.OrganizationModel
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # Alert details
    alert_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)  # info, warning, critical
    message = Column(Text, nullable=False)

    # State
    state = Column(String(20), nullable=False, default='active', index=True)  # active, acknowledged, resolved

    # References
    agent_id = Column(PG_UUID(as_uuid=True), ForeignKey("agents.agent_id"), nullable=True, index=True)
    task_id = Column(PG_UUID(as_uuid=True), ForeignKey("tasks.task_id"), nullable=True, index=True)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_alert_type_state', 'alert_type', 'state'),
        Index('idx_alert_severity_created', 'severity', 'created_at'),
        Index('idx_alert_organization', 'organization_id'),
        Index('idx_alert_org_state', 'organization_id', 'state'),
    )

    def __repr__(self):
        return f"<Alert(id={self.alert_id}, type={self.alert_type}, severity={self.severity}, state={self.state})>"


class RouterModelModel(Base):
    """
    Router Model Definition.

    Stores available LLM models with costs, capabilities, and quality scores.
    """
    __tablename__ = "router_models"

    # Primary key
    id = Column(String(100), primary_key=True, default=lambda: str(uuid4()))

    # Organization
    organization_id = Column(String(100), nullable=False, index=True)

    # Model identification
    provider = Column(String(50), nullable=False)  # openai, anthropic, google
    model_name = Column(String(100), nullable=False)  # gpt-4o, claude-3-sonnet
    display_name = Column(String(255), nullable=True)

    # Status
    is_enabled = Column(Boolean, nullable=False, default=True)

    # Pricing
    cost_per_1k_input_tokens = Column(Float, nullable=True)
    cost_per_1k_output_tokens = Column(Float, nullable=True)

    # Capabilities
    max_tokens = Column(Integer, nullable=True)
    supports_vision = Column(Boolean, nullable=False, default=False)
    supports_tools = Column(Boolean, nullable=False, default=False)

    # Quality
    quality_score = Column(Float, nullable=False, default=0.8)  # 0-1 scale

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    health_metrics = relationship("RouterHealthMetricModel", back_populates="model", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_router_models_org', 'organization_id'),
        Index('idx_router_models_provider', 'provider'),
        Index('idx_router_models_enabled', 'is_enabled'),
    )

    def __repr__(self):
        return f"<RouterModel(id={self.id}, provider={self.provider}, model={self.model_name})>"


class RouterHealthMetricModel(Base):
    """
    Router Health Metrics.

    Tracks model performance metrics over time for intelligent routing.
    """
    __tablename__ = "router_health_metrics"

    # Primary key
    id = Column(String(100), primary_key=True, default=lambda: str(uuid4()))

    # Model reference
    model_id = Column(String(100), ForeignKey("router_models.id"), nullable=False, index=True)

    # Timestamp
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Latency metrics (milliseconds)
    latency_p50_ms = Column(Integer, nullable=True)
    latency_p95_ms = Column(Integer, nullable=True)
    latency_p99_ms = Column(Integer, nullable=True)

    # Reliability metrics
    success_rate = Column(Float, nullable=True)  # 0-1 scale
    error_count = Column(Integer, nullable=False, default=0)
    request_count = Column(Integer, nullable=False, default=0)

    # Health status
    is_healthy = Column(Boolean, nullable=False, default=True)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    model = relationship("RouterModelModel", back_populates="health_metrics")

    # Indexes
    __table_args__ = (
        Index('idx_health_model_time', 'model_id', 'timestamp'),
        Index('idx_health_timestamp', 'timestamp'),
    )

    def __repr__(self):
        return f"<RouterHealthMetric(model={self.model_id}, p50={self.latency_p50_ms}ms, healthy={self.is_healthy})>"


class RoutingStrategyModel(Base):
    """
    LLM Routing Strategy Configuration.

    Stores organization-specific routing strategy preferences with scope and fallback.
    """
    __tablename__ = "routing_strategies"

    # Primary key
    id = Column(String(100), primary_key=True, default=lambda: str(uuid4()))

    # Organization
    organization_id = Column(String(100), nullable=False, index=True)

    # Scope (organization-wide, workflow-specific, or agent-specific)
    scope_type = Column(String(50), nullable=False, default='organization')  # 'organization', 'workflow', 'agent'
    scope_id = Column(String(100), nullable=True)  # NULL for org-level, workflow_id or agent_id otherwise

    # Strategy configuration
    strategy_type = Column(String(50), nullable=False)  # 'cost', 'latency', 'quality', 'weighted_rr', 'custom'
    config = Column(Text, nullable=True)  # JSON config as TEXT for SQLite compatibility

    # Fallback
    fallback_strategy_id = Column(String(100), ForeignKey("routing_strategies.id"), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    model_weights = relationship("StrategyModelWeightModel", back_populates="strategy", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_routing_strategy_org', 'organization_id'),
        Index('idx_routing_scope', 'scope_type', 'scope_id'),
    )

    def __repr__(self):
        return f"<RoutingStrategy(id={self.id}, org={self.organization_id}, type={self.strategy_type})>"


class StrategyModelWeightModel(Base):
    """
    Strategy Model Weights.

    Stores model preferences per routing strategy for weighted/priority routing.
    """
    __tablename__ = "strategy_model_weights"

    # Primary key
    id = Column(String(100), primary_key=True, default=lambda: str(uuid4()))

    # References
    strategy_id = Column(String(100), ForeignKey("routing_strategies.id"), nullable=False, index=True)
    model_id = Column(String(100), ForeignKey("router_models.id"), nullable=False, index=True)

    # Weights and priority
    weight = Column(Float, nullable=False, default=1.0)  # For weighted round-robin
    priority = Column(Integer, nullable=False, default=0)  # For priority-based routing

    # Status
    is_enabled = Column(Boolean, nullable=False, default=True)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    strategy = relationship("RoutingStrategyModel", back_populates="model_weights")

    # Indexes
    __table_args__ = (
        Index('idx_strategy_weights_strategy', 'strategy_id'),
        Index('idx_strategy_weights_model', 'model_id'),
    )

    def __repr__(self):
        return f"<StrategyModelWeight(strategy={self.strategy_id}, model={self.model_id}, weight={self.weight})>"


# NOTE: WorkflowModel and WorkflowExecutionModel have been moved to
# backend/shared/workflow_models.py to avoid duplicate model definitions.
# Do NOT add them here - it causes SQLAlchemy mapper conflicts.

# NOTE: OrganizationModel is defined in backend/shared/rbac_models.py
# Do NOT add it here - it causes SQLAlchemy mapper conflicts.


class TeamMemberModel(Base):
    """
    Team Member database model.

    Stores team member information and roles.
    """
    __tablename__ = "team_members"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Organization reference (references rbac_models.OrganizationModel)
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # User information
    user_id = Column(String(100), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Role and status
    role = Column(String(50), nullable=False, default='member')  # admin, member, viewer
    status = Column(String(50), nullable=False, default='invited')  # invited, active, suspended

    # Timestamps
    invited_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    joined_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)

    # Relationships (OrganizationModel is in backend/shared/rbac_models.py)
    # Note: Don't define back_populates unless OrganizationModel also defines it

    # Indexes and constraints
    __table_args__ = (
        # Email must be unique per organization (not globally)
        UniqueConstraint('organization_id', 'email', name='uq_team_member_org_email'),
        Index('idx_team_member_org_email', 'organization_id', 'email'),
        Index('idx_team_member_status', 'status'),
    )

    def __repr__(self):
        return f"<TeamMember(id={self.id}, email={self.email}, role={self.role})>"


class APIKeyModel(Base):
    """
    API Key database model.

    Stores API keys for programmatic access with rate limiting, quotas, and rotation support.
    """
    __tablename__ = "api_keys"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Organization reference (references rbac_models.OrganizationModel)
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # Key information
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(20), nullable=False, index=True)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash

    # Permissions (JSONB array in PostgreSQL, JSON in SQLite)
    permissions = Column(UniversalJSON(), nullable=True, default=list)

    # Rate limiting and quotas
    rate_limit_per_second = Column(Integer, nullable=False, default=100)
    monthly_quota = Column(Integer, nullable=True)  # None = unlimited
    ip_whitelist = Column(UniversalJSON(), nullable=True, default=list)  # List of allowed IPs

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(String(100), nullable=True)

    # Key rotation support (for graceful key rotation with grace period)
    previous_key_hash = Column(String(64), nullable=True)  # SHA-256 hash of previous key
    previous_key_expires_at = Column(DateTime, nullable=True)  # When old key stops working

    # Relationships (OrganizationModel is in backend/shared/rbac_models.py)
    # Note: Don't define back_populates unless OrganizationModel also defines it

    # Indexes
    __table_args__ = (
        Index('idx_api_key_org_active', 'organization_id', 'is_active'),
        Index('idx_api_key_prefix', 'key_prefix'),
        Index('idx_api_keys_hash', 'key_hash'),
        Index('idx_api_keys_org', 'organization_id'),
    )

    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, active={self.is_active})>"
