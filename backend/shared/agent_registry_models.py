"""
Agent Registry & Governance Database Models

Provides central registry, lifecycle management, and governance for AI agents.
Enables enterprises to track, discover, approve, and audit all agents.
"""

from sqlalchemy import Column, String, Text, Integer, BigInteger, Boolean, DECIMAL, TIMESTAMP, ForeignKey, ARRAY, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database.session import Base
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

# Import RBAC models to ensure they are registered in Base.metadata
# This is required for foreign key relationships to work
from backend.shared.rbac_models import UserModel, OrganizationModel


class AgentStatus(str, Enum):
    """Agent lifecycle status"""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class DeploymentStatus(str, Enum):
    """Agent deployment status"""
    NOT_DEPLOYED = "not_deployed"
    DEPLOYED = "deployed"
    FAILED = "failed"


class SensitivityLevel(str, Enum):
    """Data sensitivity classification"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ApprovalStatus(str, Enum):
    """Approval request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PolicyType(str, Enum):
    """Types of governance policies"""
    COST_CAP = "cost_cap"
    DATA_ACCESS = "data_access"
    APPROVAL_REQUIRED = "approval_required"
    RETENTION = "retention"
    COMPLIANCE = "compliance"


class EnforcementLevel(str, Enum):
    """Policy enforcement levels"""
    ADVISORY = "advisory"  # Warning only
    WARNING = "warning"     # Warning + log
    BLOCKING = "blocking"   # Prevent action


# ============================================================================
# Agent Registry Models
# ============================================================================

class AgentRegistry(Base):
    """
    Central registry of all AI agents in the enterprise.

    Provides:
    - Searchable catalog of agents
    - Ownership and team tracking
    - Capability tagging
    - Cost and usage metrics
    - Lifecycle management
    """
    __tablename__ = "agents_registry"

    # Primary Key
    agent_id = Column(String(255), primary_key=True)

    # Basic Info
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    version = Column(String(50))

    # Ownership
    owner_user_id = Column(String(255), ForeignKey("users.user_id"), nullable=False, index=True)
    owner_team_id = Column(String(255), index=True)
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # Classification
    category = Column(String(100), index=True)  # e.g., "customer_service", "data_processing"
    tags = Column(ARRAY(String))  # capabilities: ["email", "summarization", "nlp"]
    sensitivity = Column(String(50), default=SensitivityLevel.INTERNAL)

    # Lifecycle
    status = Column(String(50), default=AgentStatus.DRAFT, index=True)
    deployment_status = Column(String(50), default=DeploymentStatus.NOT_DEPLOYED)

    # Access Control
    data_sources_allowed = Column(ARRAY(String))  # ["salesforce", "zendesk", "internal_db"]
    permissions = Column(JSON)  # {salesforce: "read-only", zendesk: "read-write"}

    # Metrics - Token-Based (Universal) + Legacy cost tracking for backward compatibility
    total_executions = Column(Integer, default=0)
    total_cost_usd = Column(DECIMAL(10, 2), default=0.00)  # Legacy - kept for backward compatibility
    total_input_tokens = Column(BigInteger, default=0)  # Track tokens, not costs
    total_output_tokens = Column(BigInteger, default=0)  # Costs calculated on-demand
    primary_model = Column(String(100))  # e.g., "gpt-4-turbo", "claude-3-opus"
    primary_provider = Column(String(50))  # e.g., "openai", "anthropic", "google"
    avg_response_time_ms = Column(Integer)
    success_rate = Column(DECIMAL(5, 2))

    # Governance
    requires_approval = Column(Boolean, default=True)
    approved_by = Column(String(255))
    approved_at = Column(TIMESTAMP)
    sunset_date = Column(TIMESTAMP)  # For deprecated agents

    # Metadata
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    last_active_at = Column(TIMESTAMP)

    # Relationships
    approvals = relationship("AgentApproval", back_populates="agent", cascade="all, delete-orphan")
    usage_logs = relationship("AgentUsageLog", back_populates="agent", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AgentRegistry(agent_id={self.agent_id}, name={self.name}, status={self.status})>"


class AgentApproval(Base):
    """
    Approval workflow for agent deployment and changes.

    Supports multi-stage approvals:
    - Manager approval
    - Security review
    - Compliance review
    - CTO/VP Engineering approval
    """
    __tablename__ = "agent_approvals"

    # Primary Key
    approval_id = Column(String(255), primary_key=True)
    agent_id = Column(String(255), ForeignKey("agents_registry.agent_id"), nullable=False, index=True)

    # Approval Workflow
    approval_stage = Column(String(50), index=True)  # manager, security, compliance, cto
    approver_user_id = Column(String(255), ForeignKey("users.user_id"), index=True)
    status = Column(String(50), default=ApprovalStatus.PENDING, index=True)

    # Justification
    requested_by = Column(String(255), ForeignKey("users.user_id"), nullable=False)
    request_reason = Column(Text)
    decision_reason = Column(Text)

    # Audit
    requested_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    decided_at = Column(TIMESTAMP)

    # Relationships
    agent = relationship("AgentRegistry", back_populates="approvals")

    def __repr__(self):
        return f"<AgentApproval(approval_id={self.approval_id}, agent_id={self.agent_id}, status={self.status})>"


class AgentPolicy(Base):
    """
    Governance policies for agent management.

    Policies can be:
    - Organization-wide (apply to all agents)
    - Team-specific (apply to specific team's agents)
    - Category-specific (apply to agent categories)
    - Agent-specific (apply to individual agents)
    """
    __tablename__ = "agent_policies"

    # Primary Key
    policy_id = Column(String(255), primary_key=True)
    organization_id = Column(String(255), ForeignKey("organizations.organization_id"), nullable=False, index=True)

    # Policy Details
    policy_name = Column(String(255), nullable=False)
    description = Column(Text)
    policy_type = Column(String(50), index=True)

    # Scope
    applies_to = Column(String(50), index=True)  # all_agents, team, category, specific_agent
    scope_value = Column(String(255))  # e.g., "finance_team" or "customer_service"

    # Policy Rules (JSON)
    rules = Column(JSON, nullable=False)
    # Example:
    # {
    #   "max_cost_per_month_usd": 10000,
    #   "require_2fa": true,
    #   "allowed_data_sources": ["salesforce", "zendesk"],
    #   "require_approval_for": ["pii_access", "cost_over_1000"]
    # }

    # Enforcement
    enforcement_level = Column(String(50), default=EnforcementLevel.WARNING)
    violations_count = Column(Integer, default=0)

    # Metadata
    created_by = Column(String(255), ForeignKey("users.user_id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<AgentPolicy(policy_id={self.policy_id}, policy_name={self.policy_name}, type={self.policy_type})>"


class AgentUsageLog(Base):
    """
    Detailed usage log for agent executions.

    Tracks:
    - Execution metrics (time, cost, tokens)
    - Data access (for compliance auditing)
    - Success/failure rates
    - User and team attribution
    """
    __tablename__ = "agent_usage_log"

    # Primary Key
    log_id = Column(String(255), primary_key=True)
    agent_id = Column(String(255), ForeignKey("agents_registry.agent_id"), nullable=False, index=True)

    # Usage Details
    execution_id = Column(String(255), index=True)  # Links to workflow execution
    user_id = Column(String(255), ForeignKey("users.user_id"), index=True)
    team_id = Column(String(255), index=True)

    # Metrics - Token-Based + Legacy for backward compatibility
    execution_time_ms = Column(Integer)
    tokens_used = Column(Integer)  # Legacy - kept for backward compatibility
    cost_usd = Column(DECIMAL(10, 4))  # Legacy - kept for backward compatibility
    input_tokens = Column(Integer)  # Separate input/output for accurate pricing
    output_tokens = Column(Integer)
    model_used = Column(String(100))  # e.g., "gpt-4-turbo", "claude-3-opus"
    provider = Column(String(50))  # e.g., "openai", "anthropic", "google"
    success = Column(Boolean, index=True)

    # Data Access (for compliance auditing)
    data_sources_accessed = Column(ARRAY(String))
    pii_accessed = Column(Boolean, default=False, index=True)

    # Timestamp
    executed_at = Column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)

    # Relationships
    agent = relationship("AgentRegistry", back_populates="usage_logs")

    def __repr__(self):
        return f"<AgentUsageLog(log_id={self.log_id}, agent_id={self.agent_id}, success={self.success})>"


# ============================================================================
# Pydantic Models for API (Input/Output)
# ============================================================================

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AgentRegistryCreate(BaseModel):
    """Request model for creating new agent in registry"""
    agent_id: str
    name: str
    description: Optional[str] = None
    version: Optional[str] = "1.0.0"
    owner_user_id: str
    owner_team_id: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = []
    sensitivity: str = SensitivityLevel.INTERNAL
    data_sources_allowed: Optional[List[str]] = []
    permissions: Optional[Dict[str, str]] = {}
    requires_approval: bool = True


class AgentRegistryUpdate(BaseModel):
    """Request model for updating agent metadata"""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    sensitivity: Optional[str] = None
    data_sources_allowed: Optional[List[str]] = None
    permissions: Optional[Dict[str, str]] = None
    status: Optional[str] = None


class AgentRegistryResponse(BaseModel):
    """Response model for agent registry"""
    agent_id: str
    name: str
    description: Optional[str]
    version: Optional[str]
    owner_user_id: str
    owner_team_id: Optional[str]
    organization_id: str
    category: Optional[str]
    tags: Optional[List[str]]
    sensitivity: str
    status: str
    deployment_status: str
    data_sources_allowed: Optional[List[str]]
    permissions: Optional[Dict[str, str]]
    total_executions: int
    total_cost_usd: Optional[float] = 0.0  # Legacy - kept for backward compatibility
    total_input_tokens: Optional[int] = 0  # Token-based metrics
    total_output_tokens: Optional[int] = 0
    primary_model: Optional[str] = None  # e.g., "gpt-4-turbo"
    primary_provider: Optional[str] = None  # e.g., "openai"
    avg_response_time_ms: Optional[int]
    success_rate: Optional[float]
    requires_approval: bool
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    sunset_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    last_active_at: Optional[datetime]

    class Config:
        from_attributes = True


class ApprovalRequest(BaseModel):
    """Request model for agent approval"""
    agent_id: str
    approval_stage: str
    request_reason: Optional[str] = None


class ApprovalDecision(BaseModel):
    """Request model for approval decision"""
    status: str  # approved or rejected
    decision_reason: Optional[str] = None


class PolicyCreate(BaseModel):
    """Request model for creating policy"""
    policy_id: str
    policy_name: str
    description: Optional[str] = None
    policy_type: str
    applies_to: str
    scope_value: Optional[str] = None
    rules: Dict[str, Any]
    enforcement_level: str = EnforcementLevel.WARNING


class PolicyResponse(BaseModel):
    """Response model for policy"""
    policy_id: str
    organization_id: str
    policy_name: str
    description: Optional[str]
    policy_type: str
    applies_to: str
    scope_value: Optional[str]
    rules: Dict[str, Any]
    enforcement_level: str
    violations_count: int
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True


class AgentSearchFilters(BaseModel):
    """Search filters for agent registry"""
    query: Optional[str] = None  # Search in name/description
    owner_user_id: Optional[str] = None
    owner_team_id: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    sensitivity: Optional[str] = None
    min_cost: Optional[float] = None
    max_cost: Optional[float] = None


class AgentStats(BaseModel):
    """Registry statistics"""
    total_agents: int
    active_agents: int
    pending_approval: int
    deprecated_agents: int
    retired_agents: int
    total_teams: int
    total_monthly_cost_usd: float
    avg_success_rate: float
