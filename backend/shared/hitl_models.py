"""
Human-in-the-Loop (HITL) Workflows - P1 Feature #4

Data models for approval gates, human reviews, and escalations.

Enables:
- Approval gates in workflows (pause for human decision)
- Timeout handling (auto-approve/reject)
- Escalation paths (if no response)
- Multi-channel notifications (Slack, email, SMS)
- Approval history and audit trail
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, JSON,
    ForeignKey, Enum as SQLEnum, Index, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum


from backend.database.base import Base


# ============================================================================
# Enums
# ============================================================================

class ApprovalStatus(str, Enum):
    """Status of approval request."""
    PENDING = "pending"  # Waiting for decision
    APPROVED = "approved"  # Human approved
    REJECTED = "rejected"  # Human rejected
    TIMEOUT_APPROVED = "timeout_approved"  # Auto-approved after timeout
    TIMEOUT_REJECTED = "timeout_rejected"  # Auto-rejected after timeout
    ESCALATED = "escalated"  # Escalated to another approver
    CANCELLED = "cancelled"  # Request cancelled


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    SMS = "sms"
    WEBHOOK = "webhook"
    IN_APP = "in_app"  # Dashboard notification


class EscalationTrigger(str, Enum):
    """When to trigger escalation."""
    TIMEOUT = "timeout"  # After timeout period
    REJECTION = "rejection"  # If rejected
    NO_RESPONSE = "no_response"  # If no response within time
    MANUAL = "manual"  # Manual escalation by user


class ApprovalPriority(str, Enum):
    """Priority level for approval requests."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Database Models
# ============================================================================

class ApprovalRequest(Base):
    """
    Approval request for human decision in workflow.

    Represents a pause point in workflow where human input is required.
    """
    __tablename__ = "approval_requests"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Request identification
    workflow_execution_id = Column(Integer, nullable=False, index=True)
    task_id = Column(Integer, nullable=True, index=True)
    node_id = Column(String(255), nullable=False)  # DAG node requiring approval

    # Content
    title = Column(String(500), nullable=False)  # e.g., "Approve $50K budget request"
    description = Column(Text, nullable=True)  # Detailed explanation
    context = Column(JSON, default=dict)  # Additional context for approver

    # Requestor
    requested_by_user_id = Column(String(255), nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)

    # Approval configuration
    required_approvers = Column(JSON, default=list)  # List of user IDs who can approve
    required_approval_count = Column(Integer, default=1)  # How many approvals needed
    priority = Column(SQLEnum(ApprovalPriority, name='approvalpriority', create_type=False, values_callable=lambda x: [e.value for e in x]), default=ApprovalPriority.MEDIUM, index=True)

    # Timeout configuration
    timeout_seconds = Column(Integer, nullable=True)  # Auto-action after timeout
    timeout_action = Column(String(50), nullable=True)  # "approve" or "reject"
    expires_at = Column(DateTime, nullable=True, index=True)

    # Status
    status = Column(SQLEnum(ApprovalStatus, name='approvalstatus', create_type=False, values_callable=lambda x: [e.value for e in x]), default=ApprovalStatus.PENDING, nullable=False, index=True)

    # Response
    approved_by_user_id = Column(String(255), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    response_time_seconds = Column(Float, nullable=True)  # Time to respond

    # Escalation
    escalation_level = Column(Integer, default=0)  # 0 = no escalation, 1+ = escalation levels
    escalated_to_user_id = Column(String(255), nullable=True, index=True)
    escalated_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    approvals = relationship("ApprovalResponse", back_populates="request", cascade="all, delete-orphan")
    notifications = relationship("ApprovalNotification", back_populates="request", cascade="all, delete-orphan")
    escalations = relationship("ApprovalEscalation", back_populates="request", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_approval_requests_status_priority", "status", "priority"),
        Index("ix_approval_requests_org_status", "organization_id", "status"),
    )


class ApprovalResponse(Base):
    """
    Individual approval/rejection response.

    Supports multiple approvers per request.
    """
    __tablename__ = "approval_responses"

    id = Column(Integer, primary_key=True, index=True)

    # Reference
    request_id = Column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)

    # Approver
    approver_user_id = Column(String(255), nullable=False, index=True)
    approver_email = Column(String(500), nullable=True)

    # Decision
    decision = Column(String(50), nullable=False)  # "approved" or "rejected"
    comment = Column(Text, nullable=True)

    # Metadata
    response_time_seconds = Column(Float, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    request = relationship("ApprovalRequest", back_populates="approvals")

    __table_args__ = (
        Index("ix_approval_responses_request_approver", "request_id", "approver_user_id"),
    )


class ApprovalNotification(Base):
    """
    Notifications sent to approvers.

    Tracks multi-channel notifications (email, Slack, SMS, etc.).
    """
    __tablename__ = "approval_notifications"

    id = Column(Integer, primary_key=True, index=True)

    # Reference
    request_id = Column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)

    # Recipient
    recipient_user_id = Column(String(255), nullable=False, index=True)
    recipient_email = Column(String(500), nullable=True)
    recipient_phone = Column(String(50), nullable=True)
    recipient_slack_id = Column(String(255), nullable=True)

    # Channel
    channel = Column(SQLEnum(NotificationChannel, name='notificationchannel', create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)

    # Status
    sent = Column(Boolean, default=False, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    delivery_status = Column(String(50), nullable=True)  # "delivered", "failed", "bounced"
    error_message = Column(Text, nullable=True)

    # Metadata
    external_id = Column(String(500), nullable=True)  # Provider message ID
    extra_data = Column("metadata", JSON, default=dict)  # Maps to 'metadata' column in DB

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    request = relationship("ApprovalRequest", back_populates="notifications")

    __table_args__ = (
        Index("ix_approval_notifications_request_channel", "request_id", "channel"),
        Index("ix_approval_notifications_status", "sent", "delivery_status"),
    )


class ApprovalEscalation(Base):
    """
    Escalation rules and history.

    Automatically escalates approval requests based on triggers.
    """
    __tablename__ = "approval_escalations"

    id = Column(Integer, primary_key=True, index=True)

    # Reference
    request_id = Column(Integer, ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False, index=True)

    # Escalation level
    level = Column(Integer, nullable=False)  # 1, 2, 3, etc.

    # Trigger
    trigger = Column(SQLEnum(EscalationTrigger, name='escalationtrigger', create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    trigger_time = Column(DateTime, nullable=False)

    # Escalated to
    escalated_to_user_id = Column(String(255), nullable=False, index=True)
    escalated_by_user_id = Column(String(255), nullable=True)  # For manual escalations

    # Status
    resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)

    # Metadata
    notes = Column(Text, nullable=True)
    extra_data = Column("metadata", JSON, default=dict)  # Maps to 'metadata' column in DB

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationships
    request = relationship("ApprovalRequest", back_populates="escalations")

    __table_args__ = (
        Index("ix_approval_escalations_request_level", "request_id", "level"),
        Index("ix_approval_escalations_trigger_created", "trigger", "created_at"),
    )


class ApprovalTemplate(Base):
    """
    Reusable approval templates.

    Pre-configured approval workflows for common scenarios.
    """
    __tablename__ = "approval_templates"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Organization
    organization_id = Column(Integer, nullable=True, index=True)
    created_by_user_id = Column(String(255), nullable=False)

    # Configuration
    default_approvers = Column(JSON, default=list)  # List of user IDs
    required_approval_count = Column(Integer, default=1)
    timeout_seconds = Column(Integer, nullable=True)
    timeout_action = Column(String(50), nullable=True)

    # Escalation rules
    escalation_enabled = Column(Boolean, default=False)
    escalation_chain = Column(JSON, default=list)  # List of user IDs for escalation
    escalation_timeout_seconds = Column(Integer, nullable=True)

    # Notification configuration
    notification_channels = Column(JSON, default=list)  # List of channels
    notification_template = Column(JSON, default=dict)  # Message templates per channel

    # Metadata
    category = Column(String(100), nullable=True, index=True)
    tags = Column(JSON, default=list)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Usage analytics
    usage_count = Column(Integer, default=0)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_approval_templates_org_active", "organization_id", "is_active"),
    )


# ============================================================================
# Pydantic Models (API Schemas)
# ============================================================================

class ApprovalRequestCreate(BaseModel):
    """Create new approval request."""
    workflow_execution_id: int
    task_id: Optional[int] = None
    node_id: str
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    required_approvers: List[str] = Field(default_factory=list)
    required_approval_count: int = 1
    priority: ApprovalPriority = ApprovalPriority.MEDIUM
    timeout_seconds: Optional[int] = None
    timeout_action: Optional[str] = None  # "approve" or "reject"
    notification_channels: List[NotificationChannel] = Field(default_factory=lambda: [NotificationChannel.EMAIL])

    @validator("timeout_action")
    def validate_timeout_action(cls, v):
        if v and v not in ["approve", "reject"]:
            raise ValueError("timeout_action must be 'approve' or 'reject'")
        return v


class ApprovalDecision(BaseModel):
    """Approve or reject decision."""
    decision: str = Field(..., pattern="^(approved|rejected)$")
    comment: Optional[str] = None


class ApprovalRequestResponse(BaseModel):
    """Approval request with status."""
    id: int
    workflow_execution_id: int
    task_id: Optional[int]
    node_id: str
    title: str
    description: Optional[str]
    context: Dict[str, Any]
    requested_by_user_id: str
    organization_id: Optional[int]
    required_approvers: List[str]
    required_approval_count: int
    priority: ApprovalPriority
    timeout_seconds: Optional[int]
    timeout_action: Optional[str]
    expires_at: Optional[datetime]
    status: ApprovalStatus
    approved_by_user_id: Optional[str]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    response_time_seconds: Optional[float]
    escalation_level: int
    escalated_to_user_id: Optional[str]
    escalated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApprovalResponseCreate(BaseModel):
    """Create approval response."""
    approver_user_id: str
    approver_email: Optional[str] = None
    decision: str = Field(..., pattern="^(approved|rejected)$")
    comment: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ApprovalNotificationCreate(BaseModel):
    """Create notification."""
    recipient_user_id: str
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    recipient_slack_id: Optional[str] = None
    channel: NotificationChannel


class ApprovalEscalationCreate(BaseModel):
    """Create escalation."""
    level: int
    trigger: EscalationTrigger
    escalated_to_user_id: str
    escalated_by_user_id: Optional[str] = None
    notes: Optional[str] = None


class ApprovalTemplateCreate(BaseModel):
    """Create approval template."""
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    default_approvers: List[str] = Field(default_factory=list)
    required_approval_count: int = 1
    timeout_seconds: Optional[int] = None
    timeout_action: Optional[str] = None
    escalation_enabled: bool = False
    escalation_chain: List[str] = Field(default_factory=list)
    escalation_timeout_seconds: Optional[int] = None
    notification_channels: List[NotificationChannel] = Field(default_factory=lambda: [NotificationChannel.EMAIL])
    notification_template: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ApprovalTemplateResponse(BaseModel):
    """Approval template response."""
    id: int
    name: str
    slug: str
    description: Optional[str]
    organization_id: Optional[int]
    created_by_user_id: str
    default_approvers: List[str]
    required_approval_count: int
    timeout_seconds: Optional[int]
    timeout_action: Optional[str]
    escalation_enabled: bool
    escalation_chain: List[str]
    escalation_timeout_seconds: Optional[int]
    notification_channels: List[str]
    notification_template: Dict[str, Dict[str, str]]
    category: Optional[str]
    tags: List[str]
    is_active: bool
    usage_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApprovalStats(BaseModel):
    """Approval statistics."""
    total_requests: int
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    timeout_approvals: int
    timeout_rejections: int
    avg_response_time_seconds: float
    escalation_rate: float  # % of requests escalated
    approval_rate: float  # % of requests approved
