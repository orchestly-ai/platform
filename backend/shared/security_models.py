"""
Advanced Security & Compliance Models - P2 Feature #5

Data models for security, compliance, and audit features.

Enables:
- Comprehensive audit logging
- Role-based access control (RBAC)
- Data encryption at rest and in transit
- Compliance framework tracking (SOC 2, HIPAA, GDPR)
- Security event monitoring
- Access control policies
- Data retention policies
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, JSON, Float,
    ForeignKey, Enum as SQLEnum, Index, UniqueConstraint
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

class AuditEventType(str, Enum):
    """Audit event types."""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"

    # Authorization
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"

    # Data access
    DATA_READ = "data_read"
    DATA_CREATED = "data_created"
    DATA_UPDATED = "data_updated"
    DATA_DELETED = "data_deleted"
    DATA_EXPORTED = "data_exported"

    # Configuration
    CONFIG_CHANGED = "config_changed"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"

    # Security
    ENCRYPTION_KEY_ROTATED = "encryption_key_rotated"
    SECURITY_SCAN = "security_scan"
    THREAT_DETECTED = "threat_detected"
    INCIDENT_CREATED = "incident_created"


class AuditSeverity(str, Enum):
    """Audit event severity."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComplianceFramework(str, Enum):
    """Compliance frameworks."""
    SOC2_TYPE1 = "soc2_type1"
    SOC2_TYPE2 = "soc2_type2"
    HIPAA = "hipaa"
    GDPR = "gdpr"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    CCPA = "ccpa"


class ControlStatus(str, Enum):
    """Compliance control status."""
    NOT_IMPLEMENTED = "not_implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    NON_COMPLIANT = "non_compliant"


class IncidentSeverity(str, Enum):
    """Security incident severity."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Security incident status."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    CLOSED = "closed"


class DataClassification(str, Enum):
    """Data sensitivity classification."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # PII, PHI, PCI data


# ============================================================================
# Database Models
# ============================================================================

class AuditLog(Base):
    """
    Comprehensive audit log.

    Immutable record of all security-relevant events.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(50), default='info', nullable=False, index=True)

    # Actor (who performed the action)
    user_id = Column(String(255), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    service_account = Column(String(255), nullable=True)  # For automated actions

    # Target (what was affected)
    resource_type = Column(String(100), nullable=True, index=True)  # workflow, agent, user, etc.
    resource_id = Column(String(255), nullable=True, index=True)

    # Action details
    action = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Request details
    ip_address = Column(String(50), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(255), nullable=True, index=True)

    # Context
    organization_id = Column(Integer, nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)

    # Data changes (before/after)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)

    # Additional metadata
    extra_metadata = Column(JSON, default=dict)
    tags = Column(JSON, default=list)

    # Compliance
    compliance_relevant = Column(Boolean, default=False, nullable=False, index=True)
    retention_until = Column(DateTime, nullable=True, index=True)

    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_user_time", "user_id", "created_at"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
        Index("ix_audit_severity_time", "severity", "created_at"),
        Index("ix_audit_compliance", "compliance_relevant", "created_at"),
        {'extend_existing': True}
    )


class Role(Base):
    """
    RBAC role definition.

    Groups permissions together.
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)

    # Role details
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Permissions
    permissions = Column(JSON, default=list)  # List of permission strings

    # Scope
    is_system_role = Column(Boolean, default=False, nullable=False)  # Built-in roles
    organization_id = Column(Integer, nullable=True, index=True)  # Org-specific roles

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)

    # Relationships
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_role_org_active", "organization_id", "is_active"),
        {'extend_existing': True}
    )


class UserRole(Base):
    """
    User-role assignment.

    Links users to their roles.
    """
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)

    # Assignment
    user_id = Column(String(255), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)

    # Scope
    organization_id = Column(Integer, nullable=True, index=True)

    # Conditions
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True, index=True)

    # Audit
    assigned_at = Column(DateTime, server_default=func.now(), nullable=False)
    assigned_by = Column(String(255), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(String(255), nullable=True)

    # Relationships
    role = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        Index("ix_user_role_assignment", "user_id", "role_id"),
        Index("ix_user_role_org", "user_id", "organization_id"),
    )


class AccessPolicy(Base):
    """
    Fine-grained access control policy.

    Defines who can do what to which resources.
    """
    __tablename__ = "access_policies"

    id = Column(Integer, primary_key=True, index=True)

    # Policy details
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Principal (who)
    principal_type = Column(String(50), nullable=False)  # user, role, organization
    principal_id = Column(String(255), nullable=False, index=True)

    # Resource (what)
    resource_type = Column(String(100), nullable=False, index=True)  # workflow, agent, data, etc.
    resource_pattern = Column(String(255), nullable=False)  # Glob pattern or specific ID

    # Actions (do)
    actions = Column(JSON, default=list)  # List of allowed actions

    # Effect
    effect = Column(String(10), default="allow", nullable=False)  # allow or deny

    # Conditions
    conditions = Column(JSON, default=dict)  # IP range, time of day, etc.

    # Priority (higher = evaluated first)
    priority = Column(Integer, default=100)

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_policy_principal", "principal_type", "principal_id"),
        Index("ix_policy_resource", "resource_type"),
    )


class ComplianceControl(Base):
    """
    Compliance framework control.

    Tracks implementation of compliance requirements.
    """
    __tablename__ = "compliance_controls"

    id = Column(Integer, primary_key=True, index=True)

    # Framework
    framework = Column(String(50), nullable=False, index=True)

    # Control details
    control_id = Column(String(100), nullable=False, index=True)  # e.g., "CC6.1" for SOC 2
    control_name = Column(String(255), nullable=False)
    control_description = Column(Text, nullable=False)

    # Category
    category = Column(String(100), nullable=True)  # Organization, Monitoring, etc.

    # Status
    status = Column(String(50), default=ControlStatus.NOT_IMPLEMENTED, nullable=False, index=True)

    # Implementation
    implementation_notes = Column(Text, nullable=True)
    evidence_urls = Column(JSON, default=list)  # Documentation/evidence links

    # Responsible party
    owner = Column(String(255), nullable=True)

    # Testing
    last_tested_at = Column(DateTime, nullable=True)
    last_tested_by = Column(String(255), nullable=True)
    test_results = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("framework", "control_id", name="uq_framework_control"),
        Index("ix_control_framework_status", "framework", "status"),
    )


class SecurityIncident(Base):
    """
    Security incident tracking.

    Records and tracks security incidents.
    """
    __tablename__ = "security_incidents"

    id = Column(Integer, primary_key=True, index=True)

    # Incident details
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    incident_type = Column(String(100), nullable=False, index=True)  # breach, unauthorized_access, etc.

    # Severity
    severity = Column(String(50), nullable=False, index=True)
    status = Column(String(50), default='open', nullable=False, index=True)

    # Detection
    detected_at = Column(DateTime, nullable=False, index=True)
    detected_by = Column(String(255), nullable=True)
    detection_method = Column(String(100), nullable=True)  # automated, manual, reported

    # Impact
    affected_users = Column(JSON, default=list)
    affected_resources = Column(JSON, default=list)
    data_classification = Column(String(50), nullable=True)

    # Response
    assigned_to = Column(String(255), nullable=True)
    containment_actions = Column(Text, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Timeline
    contained_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Compliance
    requires_notification = Column(Boolean, default=False, nullable=False)  # Breach notification laws
    notification_sent_at = Column(DateTime, nullable=True)

    # Related audit logs
    audit_log_ids = Column(JSON, default=list)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_incident_severity_status", "severity", "status"),
        Index("ix_incident_detected", "detected_at"),
    )


class DataRetentionPolicy(Base):
    """
    Data retention policy.

    Defines how long different types of data should be retained.
    """
    __tablename__ = "data_retention_policies"

    id = Column(Integer, primary_key=True, index=True)

    # Policy details
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Scope
    data_type = Column(String(100), nullable=False, index=True)  # audit_logs, workflows, etc.
    data_classification = Column(String(50), nullable=True, index=True)

    # Retention period
    retention_days = Column(Integer, nullable=False)  # 0 = keep forever

    # Deletion
    auto_delete = Column(Boolean, default=True, nullable=False)
    deletion_method = Column(String(50), default="soft_delete")  # soft_delete, hard_delete, anonymize

    # Compliance
    compliance_framework = Column(String(50), nullable=True)
    legal_hold_exempt = Column(Boolean, default=False, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_retention_data_type", "data_type", "is_active"),
    )


class EncryptionKey(Base):
    """
    Encryption key management.

    Tracks encryption keys for data encryption.
    """
    __tablename__ = "encryption_keys"

    id = Column(Integer, primary_key=True, index=True)

    # Key details
    key_id = Column(String(255), unique=True, nullable=False, index=True)
    key_type = Column(String(50), nullable=False)  # AES-256, RSA-2048, etc.
    key_purpose = Column(String(100), nullable=False)  # data_encryption, signing, etc.

    # Key material (encrypted with master key)
    encrypted_key_material = Column(Text, nullable=True)  # Store in KMS in production

    # Rotation
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    rotated_at = Column(DateTime, nullable=True)
    rotation_schedule_days = Column(Integer, default=90)

    # Audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("ix_key_active_purpose", "is_active", "key_purpose"),
    )


# ============================================================================
# Pydantic Models (API Schemas)
# ============================================================================

class AuditLogCreate(BaseModel):
    """Create audit log entry."""
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    user_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: str
    description: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    compliance_relevant: bool = False


class AuditLogResponse(BaseModel):
    """Audit log response."""
    id: int
    event_type: AuditEventType
    severity: AuditSeverity
    user_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: str
    description: Optional[str]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    """Create role."""
    name: str = Field(..., max_length=100)
    display_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class RoleResponse(BaseModel):
    """Role response."""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    permissions: List[str]
    is_system_role: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserRoleAssign(BaseModel):
    """Assign role to user."""
    user_id: str
    role_id: int
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class AccessPolicyCreate(BaseModel):
    """Create access policy."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    principal_type: str
    principal_id: str
    resource_type: str
    resource_pattern: str
    actions: List[str]
    effect: str = "allow"
    conditions: Dict[str, Any] = Field(default_factory=dict)


class AccessPolicyResponse(BaseModel):
    """Access policy response."""
    id: int
    name: str
    principal_type: str
    principal_id: str
    resource_type: str
    resource_pattern: str
    actions: List[str]
    effect: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ComplianceControlUpdate(BaseModel):
    """Update compliance control."""
    status: Optional[ControlStatus] = None
    implementation_notes: Optional[str] = None
    evidence_urls: Optional[List[str]] = None
    owner: Optional[str] = None


class ComplianceControlResponse(BaseModel):
    """Compliance control response."""
    id: int
    framework: ComplianceFramework
    control_id: str
    control_name: str
    control_description: str
    status: ControlStatus
    owner: Optional[str]
    last_tested_at: Optional[datetime]

    class Config:
        from_attributes = True


class IncidentCreate(BaseModel):
    """Create security incident."""
    title: str = Field(..., max_length=255)
    description: str
    incident_type: str
    severity: IncidentSeverity
    detected_at: datetime
    detected_by: Optional[str] = None


class IncidentUpdate(BaseModel):
    """Update security incident."""
    status: Optional[IncidentStatus] = None
    assigned_to: Optional[str] = None
    containment_actions: Optional[str] = None
    resolution_notes: Optional[str] = None


class IncidentResponse(BaseModel):
    """Security incident response."""
    id: int
    title: str
    description: str
    incident_type: str
    severity: IncidentSeverity
    status: IncidentStatus
    detected_at: datetime
    assigned_to: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ComplianceReport(BaseModel):
    """Compliance status report."""
    framework: ComplianceFramework
    total_controls: int
    implemented_controls: int
    verified_controls: int
    non_compliant_controls: int
    compliance_percentage: float
    last_updated: datetime
