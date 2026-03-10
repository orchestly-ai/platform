"""
Audit Logging Models

Comprehensive audit trail for compliance, security, and debugging.
Addresses the #1 production pain point: auditability crisis.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, JSON, Enum as SQLEnum,
    ForeignKey, Index, Text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, INET, JSONB

from backend.database.session import Base


class AuditEventType(Enum):
    """Types of auditable events"""
    # Authentication & Authorization
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_TOKEN_CREATED = "auth.token_created"
    AUTH_TOKEN_REVOKED = "auth.token_revoked"

    # User Management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_ROLE_CHANGED = "user.role_changed"

    # Agent Lifecycle
    AGENT_REGISTERED = "agent.registered"
    AGENT_UPDATED = "agent.updated"
    AGENT_DELETED = "agent.deleted"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_HEARTBEAT = "agent.heartbeat"

    # Task Lifecycle
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_RETRIED = "task.retried"

    # Workflow Operations
    WORKFLOW_CREATED = "workflow.created"
    WORKFLOW_UPDATED = "workflow.updated"
    WORKFLOW_DELETED = "workflow.deleted"
    WORKFLOW_EXECUTED = "workflow.executed"
    WORKFLOW_EXPORTED = "workflow.exported"
    WORKFLOW_IMPORTED = "workflow.imported"

    # Cost & Billing
    COST_LIMIT_WARNING = "cost.limit_warning"
    COST_LIMIT_EXCEEDED = "cost.limit_exceeded"
    COST_BUDGET_SET = "cost.budget_set"
    COST_FORECAST_GENERATED = "cost.forecast_generated"

    # Configuration Changes
    CONFIG_UPDATED = "config.updated"
    CONFIG_EXPORTED = "config.exported"
    CONFIG_IMPORTED = "config.imported"

    # Data Access
    DATA_READ = "data.read"
    DATA_EXPORT = "data.export"
    DATA_DELETE = "data.delete"

    # System Events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    SYSTEM_ALERT = "system.alert"

    # Security Events
    SECURITY_ACCESS_DENIED = "security.access_denied"
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    SECURITY_KEY_ROTATED = "security.key_rotated"
    SECURITY_POLICY_VIOLATED = "security.policy_violated"

    # Agent Registry & Governance
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    POLICY_CREATED = "policy.created"
    POLICY_UPDATED = "policy.updated"
    POLICY_DELETED = "policy.deleted"
    POLICY_VIOLATED = "policy.violated"


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    DEBUG = "DEBUG"        # Verbose debugging info
    INFO = "INFO"          # Normal operations
    NOTICE = "NOTICE"      # Significant events
    WARNING = "WARNING"    # Potentially problematic
    ERROR = "ERROR"        # Errors that require attention
    CRITICAL = "CRITICAL"  # Critical security/compliance events


class AuditEventModel(Base):
    """
    Comprehensive audit log model.

    Tracks all system events for compliance, security, and debugging.
    Designed for SOC 2, HIPAA, and GDPR compliance.
    """
    __tablename__ = "audit_events"

    # Primary key
    event_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Event classification
    # Using String instead of SQLEnum to avoid recursion issues with asyncpg
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="INFO", index=True)

    # Timestamp (partition key for time-series)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Actor (who performed the action)
    user_id = Column(String(255), nullable=True, index=True)  # User ID or service account
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(100), nullable=True)

    # Session info
    session_id = Column(String(255), nullable=True, index=True)
    request_id = Column(String(255), nullable=True, index=True)  # For tracing

    # Network info
    ip_address = Column(INET, nullable=True, index=True)
    user_agent = Column(String(512), nullable=True)

    # Resource (what was affected)
    resource_type = Column(String(100), nullable=True, index=True)  # agent, task, workflow, user
    resource_id = Column(String(255), nullable=True, index=True)
    resource_name = Column(String(255), nullable=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)  # create, update, delete, execute, etc.
    description = Column(Text, nullable=False)

    # Changes (for UPDATE events)
    changes = Column(JSON, nullable=True)  # {field: {old: value, new: value}}

    # Request/Response
    request_data = Column(JSON, nullable=True)  # Input parameters
    response_data = Column(JSON, nullable=True)  # Output/result

    # Outcome
    success = Column(Boolean, nullable=False, default=True, index=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(100), nullable=True)

    # Cost impact (if applicable)
    cost_impact = Column(Float, nullable=True)

    # Additional context
    tags = Column(JSONB, nullable=True)  # JSONB for GIN indexing
    extra_metadata = Column("metadata", JSON, nullable=True)  # Maps to DB column 'metadata'

    # Compliance markers
    pii_accessed = Column(Boolean, nullable=False, default=False, index=True)  # GDPR/HIPAA
    sensitive_action = Column(Boolean, nullable=False, default=False, index=True)  # SOC 2

    # Retention
    retention_days = Column(Integer, nullable=False, default=2555)  # 7 years default for compliance

    # Related events (for causality chains)
    parent_event_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    correlation_id = Column(String(255), nullable=True, index=True)  # Group related events

    # Indexes for common query patterns
    __table_args__ = (
        # Time-series queries
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_timestamp_type', 'timestamp', 'event_type'),

        # User activity
        Index('idx_audit_user_time', 'user_id', 'timestamp'),
        Index('idx_audit_user_action', 'user_id', 'action'),

        # Resource tracking
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_resource_time', 'resource_type', 'resource_id', 'timestamp'),

        # Security queries
        Index('idx_audit_security', 'severity', 'success', 'timestamp'),
        Index('idx_audit_failed_auth', 'event_type', 'success', 'ip_address'),

        # Compliance queries
        Index('idx_audit_pii', 'pii_accessed', 'timestamp'),
        Index('idx_audit_sensitive', 'sensitive_action', 'timestamp'),

        # Correlation
        Index('idx_audit_correlation', 'correlation_id', 'timestamp'),
        Index('idx_audit_parent', 'parent_event_id'),

        # Session tracking
        Index('idx_audit_session', 'session_id', 'timestamp'),

        # Tags (GIN index for JSONB)
        Index('idx_audit_tags', 'tags', postgresql_using='gin', postgresql_ops={'tags': 'jsonb_path_ops'}),
    )

    def __repr__(self):
        return f"<AuditEvent(id={self.event_id}, type={self.event_type}, user={self.user_id}, resource={self.resource_type}:{self.resource_id})>"


@dataclass
class AuditEvent:
    """
    Audit event data structure (for creating audit logs).
    """
    event_type: AuditEventType
    action: str
    description: str

    # Optional fields
    severity: AuditSeverity = AuditSeverity.INFO
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None

    session_id: Optional[str] = None
    request_id: Optional[str] = None

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None

    changes: Optional[Dict[str, Any]] = None
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None

    success: bool = True
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    cost_impact: Optional[float] = None

    tags: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    pii_accessed: bool = False
    sensitive_action: bool = False

    parent_event_id: Optional[UUID] = None
    correlation_id: Optional[str] = None

    retention_days: int = 2555  # 7 years

    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: UUID = field(default_factory=uuid4)


@dataclass
class AuditQuery:
    """Query parameters for searching audit logs"""

    # Time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Filters
    event_types: Optional[list[AuditEventType]] = None
    user_ids: Optional[list[str]] = None
    resource_types: Optional[list[str]] = None
    resource_ids: Optional[list[str]] = None
    actions: Optional[list[str]] = None
    severities: Optional[list[AuditSeverity]] = None

    # Success filter
    success_only: Optional[bool] = None
    failures_only: bool = False

    # Compliance filters
    pii_accessed: Optional[bool] = None
    sensitive_only: bool = False

    # Correlation
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_event_id: Optional[UUID] = None

    # Pagination
    limit: int = 100
    offset: int = 0

    # Sorting
    sort_by: str = "timestamp"
    sort_order: str = "desc"  # asc or desc


@dataclass
class AuditReport:
    """Audit report summary"""

    total_events: int
    event_type_breakdown: Dict[str, int]
    severity_breakdown: Dict[str, int]
    user_activity: Dict[str, int]
    resource_activity: Dict[str, int]
    success_rate: float
    pii_access_count: int
    sensitive_action_count: int
    time_range: tuple[datetime, datetime]

    # Top items
    most_active_users: list[tuple[str, int]]
    most_accessed_resources: list[tuple[str, int]]
    most_common_errors: list[tuple[str, int]]

    generated_at: datetime = field(default_factory=datetime.utcnow)
