"""
Real-Time Collaboration Models - P1 Feature #5

Data models for WebSocket connections, presence, and real-time updates.

Enables:
- WebSocket connection management
- User presence tracking
- Real-time notifications
- Live workflow execution updates
- Collaborative editing
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, JSON,
    ForeignKey, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


from backend.database.base import Base


# ============================================================================
# Enums
# ============================================================================

class ConnectionStatus(str, Enum):
    """WebSocket connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    IDLE = "idle"  # Connected but inactive


class PresenceStatus(str, Enum):
    """User presence status."""
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"


class EventType(str, Enum):
    """Real-time event types."""
    # Workflow events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_PAUSED = "workflow_paused"

    # Task events
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Agent events
    AGENT_STATUS_CHANGED = "agent_status_changed"

    # Collaboration events
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    CURSOR_MOVED = "cursor_moved"
    SELECTION_CHANGED = "selection_changed"
    DOCUMENT_EDITED = "document_edited"

    # Notification events
    APPROVAL_REQUEST = "approval_request"
    ALERT = "alert"
    MESSAGE = "message"

    # System events
    SYSTEM_NOTIFICATION = "system_notification"


class ChannelType(str, Enum):
    """Channel types for pub/sub."""
    WORKFLOW = "workflow"  # Workflow-specific updates
    ORGANIZATION = "organization"  # Organization-wide
    USER = "user"  # User-specific
    AGENT = "agent"  # Agent-specific
    GLOBAL = "global"  # System-wide


# ============================================================================
# Database Models
# ============================================================================

class WebSocketConnection(Base):
    """
    Active WebSocket connection.

    Tracks all active WebSocket connections for presence and routing.
    """
    __tablename__ = "websocket_connections"

    id = Column(Integer, primary_key=True, index=True)

    # Connection details
    connection_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=True, index=True)

    # Client info
    client_ip = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Status
    status = Column(String(50), default="connected", nullable=False, index=True)

    # Channels subscribed to
    subscribed_channels = Column(JSON, default=list)

    # Activity tracking
    last_activity_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Audit
    connected_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    disconnected_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_ws_conn_user_status", "user_id", "status"),
        Index("ix_ws_conn_activity", "last_activity_at"),
    )


class UserPresence(Base):
    """
    User presence information.

    Tracks online/away/busy status for users.
    """
    __tablename__ = "user_presence"

    id = Column(Integer, primary_key=True, index=True)

    # User
    user_id = Column(String(255), unique=True, nullable=False, index=True)

    # Status
    status = Column(String(50), default='offline', nullable=False, index=True)
    status_message = Column(String(500), nullable=True)  # Custom status text

    # Location (what they're viewing)
    current_workflow_id = Column(Integer, nullable=True, index=True)
    current_page = Column(String(255), nullable=True)

    # Activity
    last_seen_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Metadata
    extra_metadata = Column(JSON, default=dict)

    # Audit
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_user_presence_status", "status"),
        Index("ix_user_presence_workflow", "current_workflow_id"),
    )


class RealtimeEvent(Base):
    """
    Real-time event log.

    Stores events for replay and analytics.
    """
    __tablename__ = "realtime_events"

    id = Column(Integer, primary_key=True, index=True)

    # Event details
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSON, default=dict)

    # Source
    user_id = Column(String(255), nullable=True, index=True)
    workflow_id = Column(Integer, nullable=True, index=True)
    task_id = Column(Integer, nullable=True, index=True)
    agent_id = Column(Integer, nullable=True, index=True)

    # Target channel
    channel_type = Column(String(50), nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True)

    # Delivery
    delivered_to_count = Column(Integer, default=0)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_rt_event_type_channel", "event_type", "channel_type"),
        Index("ix_rt_event_workflow", "workflow_id", "created_at"),
        Index("ix_rt_event_created", "created_at"),
    )


class Notification(Base):
    """
    User notifications.

    Persistent notifications shown in UI.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    # Recipient
    user_id = Column(String(255), nullable=False, index=True)

    # Notification details
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=True)
    notification_type = Column(String(50), nullable=False, index=True)  # info, success, warning, error

    # Link/action
    action_url = Column(String(500), nullable=True)
    action_label = Column(String(100), nullable=True)

    # Related entities
    workflow_id = Column(Integer, nullable=True, index=True)
    task_id = Column(Integer, nullable=True)
    approval_id = Column(Integer, nullable=True)

    # Status
    read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    dismissed = Column(Boolean, default=False, nullable=False)
    dismissed_at = Column(DateTime, nullable=True)

    # Priority
    priority = Column(String(20), default="normal", nullable=False, index=True)  # low, normal, high, urgent

    # Expiry
    expires_at = Column(DateTime, nullable=True, index=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_notif_user_read", "user_id", "read"),
        Index("ix_notif_user_priority", "user_id", "priority"),
        Index("ix_notif_created", "created_at"),
    )


# ============================================================================
# Pydantic Models (API Schemas)
# ============================================================================

class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: str  # Message type
    channel: str  # Target channel
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PresenceUpdate(BaseModel):
    """User presence update."""
    user_id: str
    status: PresenceStatus
    status_message: Optional[str] = None
    current_workflow_id: Optional[int] = None
    current_page: Optional[str] = None


class PresenceResponse(BaseModel):
    """User presence response."""
    user_id: str
    status: PresenceStatus
    status_message: Optional[str]
    current_workflow_id: Optional[int]
    current_page: Optional[str]
    last_seen_at: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    """Create notification."""
    user_id: str
    title: str = Field(..., max_length=500)
    message: Optional[str] = None
    notification_type: str = Field(default="info")  # info, success, warning, error
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    workflow_id: Optional[int] = None
    task_id: Optional[int] = None
    approval_id: Optional[int] = None
    priority: str = Field(default="normal")  # low, normal, high, urgent
    expires_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    """Notification response."""
    id: int
    user_id: str
    title: str
    message: Optional[str]
    notification_type: str
    action_url: Optional[str]
    action_label: Optional[str]
    workflow_id: Optional[int]
    task_id: Optional[int]
    approval_id: Optional[int]
    read: bool
    read_at: Optional[datetime]
    dismissed: bool
    dismissed_at: Optional[datetime]
    priority: str
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class SubscribeRequest(BaseModel):
    """Subscribe to channel."""
    channel_type: ChannelType
    channel_id: str


class EventPublish(BaseModel):
    """Publish event to channel."""
    event_type: EventType
    event_data: Dict[str, Any] = Field(default_factory=dict)
    channel_type: ChannelType
    channel_id: str
    user_id: Optional[str] = None
    workflow_id: Optional[int] = None
    task_id: Optional[int] = None


class ConnectionStats(BaseModel):
    """WebSocket connection statistics."""
    total_connections: int
    active_users: int
    connections_by_status: Dict[str, int]
    users_online: List[str]


class WorkflowLiveUpdate(BaseModel):
    """Live workflow execution update."""
    workflow_id: int
    execution_id: int
    status: str
    current_task: Optional[str] = None
    progress_percentage: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)
