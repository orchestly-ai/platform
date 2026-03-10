"""
RBAC (Role-Based Access Control) Models

Enterprise-grade permission system with fine-grained access control.
"""

from enum import Enum
from typing import List, Set, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, ForeignKey,
    Index, Text, Table, Integer
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from backend.database.session import Base


class Permission(Enum):
    """
    Granular permissions for different resources and actions.

    Format: <RESOURCE>_<ACTION>
    """
    # Agent permissions
    AGENT_CREATE = "agent:create"
    AGENT_READ = "agent:read"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_EXECUTE = "agent:execute"
    AGENT_CONFIGURE = "agent:configure"
    AGENT_MANAGE = "agent:manage"  # Full agent management (registry operations)
    AGENT_VIEW = "agent:view"  # View agent details
    AGENT_APPROVE = "agent:approve"  # Approve/reject agent registrations

    # Policy permissions
    POLICY_CREATE = "policy:create"
    POLICY_READ = "policy:read"
    POLICY_UPDATE = "policy:update"
    POLICY_DELETE = "policy:delete"
    POLICY_VIEW = "policy:view"
    POLICY_MANAGE = "policy:manage"

    # Task permissions
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_ASSIGN = "task:assign"
    TASK_CANCEL = "task:cancel"

    # Workflow permissions
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_UPDATE = "workflow:update"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_EXECUTE = "workflow:execute"
    WORKFLOW_EXPORT = "workflow:export"
    WORKFLOW_IMPORT = "workflow:import"

    # User management permissions
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_INVITE = "user:invite"

    # Role management permissions
    ROLE_CREATE = "role:create"
    ROLE_READ = "role:read"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"
    ROLE_ASSIGN = "role:assign"

    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    AUDIT_DELETE = "audit:delete"
    AUDIT_VIEW = "audit:view"

    # Analytics permissions
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"
    ANALYTICS_VIEW = "analytics:view"

    # Cost management permissions
    COST_READ = "cost:read"
    COST_UPDATE = "cost:update"
    COST_LIMIT_SET = "cost:limit_set"

    # System configuration permissions
    CONFIG_READ = "config:read"
    CONFIG_UPDATE = "config:update"
    CONFIG_EXPORT = "config:export"
    CONFIG_IMPORT = "config:import"

    # API key permissions
    API_KEY_CREATE = "api_key:create"
    API_KEY_READ = "api_key:read"
    API_KEY_REVOKE = "api_key:revoke"

    # Organization permissions
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    ORG_DELETE = "org:delete"


class ResourceType(Enum):
    """Types of resources that can be controlled"""
    AGENT = "agent"
    TASK = "task"
    WORKFLOW = "workflow"
    USER = "user"
    ROLE = "role"
    AUDIT = "audit"
    ANALYTICS = "analytics"
    COST = "cost"
    CONFIG = "config"
    API_KEY = "api_key"
    ORGANIZATION = "organization"


# Many-to-many relationship tables

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', PG_UUID(as_uuid=True), ForeignKey('roles.role_id', ondelete='CASCADE'), primary_key=True),
    Column('permission', String(100), primary_key=True),
    Index('idx_role_permissions_role', 'role_id'),
    Index('idx_role_permissions_permission', 'permission')
)

user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', String(255), ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', PG_UUID(as_uuid=True), ForeignKey('roles.role_id', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('assigned_by', String(255), nullable=True),
    Index('idx_user_roles_user', 'user_id'),
    Index('idx_user_roles_role', 'role_id')
)


class RoleModel(Base):
    """
    Role definition with associated permissions.
    """
    __tablename__ = "roles"

    # Primary key
    role_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Role details
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Type
    is_system_role = Column(Boolean, nullable=False, default=False)  # Cannot be deleted
    is_default = Column(Boolean, nullable=False, default=False)  # Assigned to new users

    # Permissions (stored as JSON array for flexibility)
    permissions = Column(JSON, nullable=False, default=list)

    # Organization (for multi-tenancy)
    organization_id = Column(String(255), nullable=True, index=True)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)

    # Relationships
    users = relationship("UserModel", secondary=user_roles, back_populates="roles")

    # Indexes
    __table_args__ = (
        Index('idx_role_name', 'name'),
        Index('idx_role_org', 'organization_id'),
        Index('idx_role_system', 'is_system_role'),
    )

    def __repr__(self):
        return f"<Role(id={self.role_id}, name={self.name})>"


class UserModel(Base):
    """
    User account with role assignments.
    """
    __tablename__ = "users"

    # Primary key
    user_id = Column(String(255), primary_key=True)  # From auth provider (e.g., "auth0|12345")

    # User details
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)

    # Password (for local auth; nullable for SSO-only users)
    password_hash = Column(String(255), nullable=True)

    # Role (admin, user, viewer, etc.)
    role = Column(String(50), nullable=False, default="user")

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    is_email_verified = Column(Boolean, nullable=False, default=False)

    # Preferences
    preferences = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    roles = relationship("RoleModel", secondary=user_roles, back_populates="users")

    # Indexes
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_org', 'organization_id'),
        Index('idx_user_active', 'is_active'),
    )

    def __repr__(self):
        return f"<User(id={self.user_id}, email={self.email})>"


class OrganizationModel(Base):
    """
    Organization/tenant for multi-tenancy.
    """
    __tablename__ = "organizations"

    # Primary key
    organization_id = Column(String(255), primary_key=True)

    # Organization details
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)  # URL-friendly name

    # Plan
    plan = Column(String(50), nullable=False, default="community")  # community, starter, pro, enterprise
    max_users = Column(Integer, nullable=False, default=1)
    max_agents = Column(Integer, nullable=False, default=5)

    # Features (for plan-based access control)
    enabled_features = Column(JSON, nullable=False, default=list)

    # Contact
    billing_email = Column(String(255), nullable=True)
    admin_email = Column(String(255), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    trial_ends_at = Column(DateTime, nullable=True)

    # Metadata
    settings = Column(JSON, nullable=True)
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_org_slug', 'slug'),
        Index('idx_org_active', 'is_active'),
    )

    def __repr__(self):
        return f"<Organization(id={self.organization_id}, name={self.name})>"


# Dataclasses for application logic

@dataclass
class User:
    """User data structure"""
    user_id: str
    email: str
    full_name: Optional[str]
    organization_id: str
    roles: List[str]
    permissions: Set[str]
    is_active: bool
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Role:
    """Role data structure"""
    role_id: UUID
    name: str
    description: Optional[str]
    permissions: List[str]
    is_system_role: bool = False


@dataclass
class AccessRequest:
    """Access request for permission checking"""
    user_id: str
    permission: Permission
    resource_type: Optional[ResourceType] = None
    resource_id: Optional[str] = None
    organization_id: Optional[str] = None


@dataclass
class AccessResult:
    """Result of access check"""
    allowed: bool
    reason: Optional[str] = None
    required_permission: Optional[Permission] = None


# System Roles (created by migration)

SYSTEM_ROLES = {
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access to agents, tasks, and workflows",
        "permissions": [
            Permission.AGENT_READ.value,
            Permission.TASK_READ.value,
            Permission.WORKFLOW_READ.value,
            Permission.ANALYTICS_READ.value,
            Permission.COST_READ.value,
        ]
    },
    "developer": {
        "name": "Developer",
        "description": "Can create and manage agents, tasks, and workflows",
        "permissions": [
            Permission.AGENT_READ.value,
            Permission.AGENT_CREATE.value,
            Permission.AGENT_UPDATE.value,
            Permission.AGENT_EXECUTE.value,
            Permission.TASK_READ.value,
            Permission.TASK_CREATE.value,
            Permission.TASK_UPDATE.value,
            Permission.TASK_ASSIGN.value,
            Permission.TASK_CANCEL.value,
            Permission.WORKFLOW_READ.value,
            Permission.WORKFLOW_CREATE.value,
            Permission.WORKFLOW_UPDATE.value,
            Permission.WORKFLOW_EXECUTE.value,
            Permission.WORKFLOW_EXPORT.value,
            Permission.ANALYTICS_READ.value,
            Permission.COST_READ.value,
            Permission.AUDIT_READ.value,
        ]
    },
    "org_admin": {
        "name": "Organization Admin",
        "description": "Full access within organization, can manage users and roles",
        "permissions": [perm.value for perm in Permission]  # All permissions
    },
    "super_admin": {
        "name": "Super Admin",
        "description": "Full system access across all organizations",
        "permissions": ["*"]  # Wildcard for all permissions
    },
    "billing_admin": {
        "name": "Billing Admin",
        "description": "Can manage costs and view analytics",
        "permissions": [
            Permission.COST_READ.value,
            Permission.COST_UPDATE.value,
            Permission.COST_LIMIT_SET.value,
            Permission.ANALYTICS_READ.value,
            Permission.ANALYTICS_EXPORT.value,
            Permission.AUDIT_READ.value,
            Permission.AUDIT_EXPORT.value,
        ]
    },
    "auditor": {
        "name": "Auditor",
        "description": "Can view audit logs and analytics for compliance",
        "permissions": [
            Permission.AUDIT_READ.value,
            Permission.AUDIT_EXPORT.value,
            Permission.ANALYTICS_READ.value,
            Permission.ANALYTICS_EXPORT.value,
        ]
    }
}


# Plan-based limits
PLAN_LIMITS = {
    "community":  {"max_users": 1, "max_agents": 5, "max_workflows": 10},
    "starter":    {"max_users": 3, "max_agents": 20, "max_workflows": 50},
    "pro":        {"max_users": 10, "max_agents": 100, "max_workflows": 500},
    "enterprise": {"max_users": 9999, "max_agents": 9999, "max_workflows": 9999},
}

PAID_FEATURES = [
    "team_management",
    "custom_rbac",
    "sso_saml",
    "ab_testing",
    "audit_logs",
    "white_label",
    "multi_cloud",
    "hitl_approvals",
    "advanced_routing",
    "api_keys",
]
