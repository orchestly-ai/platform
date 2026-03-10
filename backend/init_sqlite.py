"""
Initialize SQLite database for local development.

This script creates all tables directly without going through Alembic migrations,
which may use PostgreSQL-specific types (JSONB, INET, UUID, etc.).

Usage:
    python -m backend.init_sqlite
"""

import os
import sys
from pathlib import Path

# Set environment for SQLite
os.environ["USE_SQLITE"] = "true"

# Add parent directory to path
agent_orch_root = Path(__file__).parent.parent
sys.path.insert(0, str(agent_orch_root))

from sqlalchemy import create_engine, Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text
from datetime import datetime

# Database setup
DB_PATH = agent_orch_root / "test_workflow.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"Initializing SQLite database at: {DB_PATH}")

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()


# ============================================================================
# CORE TABLES
# ============================================================================

class Agent(Base):
    __tablename__ = 'agents'
    id = Column(Integer, primary_key=True)
    agent_id = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    framework = Column(String(50))
    version = Column(String(20))
    capabilities = Column(Text)  # JSON as TEXT
    config = Column(Text)  # JSON
    status = Column(String(50), default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AgentState(Base):
    __tablename__ = 'agent_states'
    id = Column(Integer, primary_key=True)
    agent_id = Column(String(36), ForeignKey('agents.agent_id'))
    status = Column(String(50))
    last_heartbeat = Column(DateTime)
    current_task_id = Column(String(36))
    metrics = Column(Text)  # JSON


class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    task_id = Column(String(36), unique=True, nullable=False)
    capability = Column(String(255))
    status = Column(String(50))
    priority = Column(String(20))
    input_data = Column(Text)  # JSON
    output_data = Column(Text)  # JSON
    error_message = Column(Text)
    assigned_agent_id = Column(String(36))
    actual_cost = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    timeout_seconds = Column(Integer)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)


class TaskExecution(Base):
    __tablename__ = 'task_executions'
    id = Column(Integer, primary_key=True)
    task_id = Column(String(36), ForeignKey('tasks.task_id'))
    agent_id = Column(String(36))
    status = Column(String(50))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    tokens_used = Column(Integer)
    cost = Column(Float)
    result = Column(Text)  # JSON
    error = Column(Text)


class Metric(Base):
    __tablename__ = 'metrics'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    value = Column(Float)
    labels = Column(Text)  # JSON
    timestamp = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True)
    alert_id = Column(String(36), unique=True)
    type = Column(String(100))
    severity = Column(String(20))
    message = Column(Text)
    alert_metadata = Column(Text)  # JSON
    status = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)


# ============================================================================
# WORKFLOW TABLES
# ============================================================================

class Workflow(Base):
    __tablename__ = 'workflows'
    id = Column(Integer, primary_key=True)
    workflow_id = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    organization_id = Column(String(255), default='org_default')
    tags = Column(Text)  # JSON - was JSONB in PostgreSQL
    status = Column(String(50), default='draft')
    version = Column(Integer, default=1)
    nodes = Column(Text)  # JSON
    edges = Column(Text)  # JSON
    variables = Column(Text)  # JSON
    trigger_type = Column(String(50))
    trigger_config = Column(Text)  # JSON
    max_execution_time_seconds = Column(Integer, default=3600)
    retry_on_failure = Column(Boolean, default=True)
    max_retries = Column(Integer, default=3)
    environment = Column(String(50), default='development')
    total_executions = Column(Integer, default=0)
    successful_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)
    avg_execution_time_seconds = Column(Float)
    average_execution_time = Column(Float)
    execution_count = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    last_executed_at = Column(DateTime)
    is_template = Column(Boolean, default=False)
    extra_metadata = Column(Text)  # JSON
    created_by = Column(String(255))
    updated_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class WorkflowExecution(Base):
    __tablename__ = 'workflow_executions'
    id = Column(Integer, primary_key=True)
    execution_id = Column(String(36), unique=True, nullable=False)
    workflow_id = Column(String(36), ForeignKey('workflows.workflow_id'))
    workflow_version = Column(Integer, default=1)
    organization_id = Column(String(255), default='org_default')
    status = Column(String(50))
    triggered_by = Column(String(255))
    trigger_source = Column(String(50))
    input_data = Column(Text)  # JSON
    output_data = Column(Text)  # JSON
    error_message = Column(Text)
    error_node_id = Column(String(255))
    node_states = Column(Text)  # JSON
    node_executions = Column(Text)  # JSON
    total_cost = Column(Float, default=0.0)
    total_tokens = Column(Integer)
    duration_seconds = Column(Float)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    extra_metadata = Column(Text)  # JSON


class WorkflowTemplate(Base):
    __tablename__ = 'workflow_templates'
    id = Column(Integer, primary_key=True)
    template_id = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    tags = Column(Text)  # JSON array
    thumbnail_url = Column(String(512))
    nodes = Column(Text, nullable=False)  # JSON
    edges = Column(Text, nullable=False)  # JSON
    variables = Column(Text)  # JSON
    use_count = Column(Integer, default=0)
    rating = Column(Float)
    is_public = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    created_by = Column(String(255))
    organization_id = Column(String(255))
    extra_metadata = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# HITL / APPROVAL TABLES
# ============================================================================

class ApprovalRequest(Base):
    __tablename__ = 'approval_requests'
    id = Column(Integer, primary_key=True)
    workflow_execution_id = Column(Integer)
    task_id = Column(Integer)
    node_id = Column(String(255))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    context = Column(Text)  # JSON
    requested_by_user_id = Column(String(255), nullable=False)
    organization_id = Column(Integer)
    required_approvers = Column(Text)  # JSON
    required_approval_count = Column(Integer, default=1)
    priority = Column(String(50), default='medium')
    timeout_seconds = Column(Integer)
    timeout_action = Column(String(50))
    expires_at = Column(DateTime)
    status = Column(String(50), default='pending')
    approved_by_user_id = Column(String(255))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    response_time_seconds = Column(Float)
    escalation_level = Column(Integer, default=0)
    escalated_to_user_id = Column(String(255))
    escalated_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ApprovalResponse(Base):
    __tablename__ = 'approval_responses'
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('approval_requests.id', ondelete='CASCADE'))
    approver_user_id = Column(String(255), nullable=False)
    approver_email = Column(String(500))
    decision = Column(String(50), nullable=False)
    comment = Column(Text)
    response_time_seconds = Column(Float)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalNotification(Base):
    __tablename__ = 'approval_notifications'
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('approval_requests.id', ondelete='CASCADE'))
    recipient_user_id = Column(String(255), nullable=False)
    recipient_email = Column(String(500))
    recipient_phone = Column(String(50))
    recipient_slack_id = Column(String(255))
    channel = Column(String(50), nullable=False)  # email, slack, sms, webhook, in_app
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    delivery_status = Column(String(50))  # pending, delivered, failed
    error_message = Column(Text)
    external_id = Column(String(255))  # External notification ID
    # Note: Use "metadata" as column name but different Python attribute to avoid SQLAlchemy conflict
    extra_data = Column("metadata", Text)  # JSON - must match ORM model column name
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalEscalation(Base):
    __tablename__ = 'approval_escalations'
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('approval_requests.id', ondelete='CASCADE'))
    level = Column(Integer, nullable=False, default=1)
    escalated_to_user_id = Column(String(255), nullable=False)
    escalated_by_user_id = Column(String(255))
    trigger = Column(String(50), nullable=False)  # timeout, rejection, no_response, manual
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalTemplate(Base):
    __tablename__ = 'approval_templates'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    category = Column(String(100))  # financial, operational, security, etc.
    organization_id = Column(Integer)
    created_by = Column(String(255))
    default_approvers = Column(Text)  # JSON array of user IDs
    required_approval_count = Column(Integer, default=1)
    default_timeout_seconds = Column(Integer)
    default_timeout_action = Column(String(50))
    default_priority = Column(String(50), default='medium')
    notification_channels = Column(Text)  # JSON array
    escalation_rules = Column(Text)  # JSON
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# A/B TESTING TABLES
# ============================================================================

class ABExperiment(Base):
    __tablename__ = 'ab_experiments'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    # What's being tested
    agent_id = Column(Integer)
    workflow_id = Column(Integer)
    task_type = Column(String(100))
    # Organization
    organization_id = Column(Integer)
    created_by_user_id = Column(String(255), nullable=False, default='system')
    # Traffic configuration
    traffic_split_strategy = Column(String(50), default='random')
    total_traffic_percentage = Column(Float, default=100.0)
    # Experiment parameters
    hypothesis = Column(Text)
    success_criteria = Column(Text)  # JSON
    minimum_sample_size = Column(Integer, default=100)
    confidence_level = Column(Float, default=0.95)
    minimum_effect_size = Column(Float, default=0.05)
    # Winner selection
    winner_selection_criteria = Column(String(50), default='composite_score')
    winner_variant_id = Column(Integer)
    winner_confidence = Column(Float)
    # Status
    status = Column(String(50), default='draft')
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    scheduled_end_date = Column(DateTime)
    # Results
    total_samples = Column(Integer, default=0)
    is_statistically_significant = Column(Boolean, default=False)
    p_value = Column(Float)
    # Auto-promotion
    auto_promote_winner = Column(Boolean, default=False)
    promoted_at = Column(DateTime)
    # Metadata
    tags = Column(Text)  # JSON
    extra_metadata = Column(Text)  # JSON
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ABVariant(Base):
    __tablename__ = 'ab_variants'
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey('ab_experiments.id', ondelete='CASCADE'))
    name = Column(String(255), nullable=False)
    variant_key = Column(String(100), nullable=False, default='control')
    variant_type = Column(String(50), default='treatment')
    description = Column(Text)
    config = Column(Text)  # JSON
    traffic_percentage = Column(Float, default=50.0)
    # What's different
    agent_config_id = Column(Integer)
    workflow_definition = Column(Text)  # JSON
    prompt_template = Column(Text)
    model_name = Column(String(255))
    # Performance tracking
    sample_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    total_latency_ms = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    # Calculated metrics (REQUIRED by model)
    success_rate = Column(Float, default=0.0)
    avg_latency_ms = Column(Float, default=0.0)
    avg_cost = Column(Float, default=0.0)
    error_rate = Column(Float, default=0.0)
    # Status
    is_active = Column(Boolean, default=True)
    is_winner = Column(Boolean, default=False)
    # Legacy fields for compatibility
    is_control = Column(Boolean, default=False)
    traffic_weight = Column(Integer, default=50)
    workflow_id = Column(String(36))
    agent_id = Column(String(36))
    total_assignments = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    conversion_rate = Column(Float)
    avg_metric_value = Column(Float)
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ABAssignment(Base):
    __tablename__ = 'ab_assignments'
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey('ab_experiments.id', ondelete='CASCADE'))
    variant_id = Column(Integer, ForeignKey('ab_variants.id', ondelete='CASCADE'))
    user_id = Column(String(255))
    session_id = Column(String(255))
    execution_id = Column(Integer)
    assignment_hash = Column(String(64))
    assignment_reason = Column(String(100))
    # Outcome
    completed = Column(Boolean, default=False)
    success = Column(Boolean)
    latency_ms = Column(Float)
    cost = Column(Float)
    error_message = Column(Text)
    custom_metrics = Column(Text)  # JSON
    # Audit
    assigned_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    context = Column(Text)  # JSON - legacy


class ABMetric(Base):
    __tablename__ = 'ab_metrics'
    id = Column(Integer, primary_key=True)
    experiment_id = Column(Integer, ForeignKey('ab_experiments.id', ondelete='CASCADE'))
    variant_id = Column(Integer, ForeignKey('ab_variants.id', ondelete='CASCADE'))
    assignment_id = Column(Integer, ForeignKey('ab_assignments.id', ondelete='CASCADE'))
    metric_type = Column(String(50), nullable=False, default='custom')
    metric_name = Column(String(255), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50))
    context = Column(Text)  # JSON
    recorded_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# ORGANIZATION / TEAM TABLES
# ============================================================================

class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True)
    org_id = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True)
    plan = Column(String(50), default='free')
    settings = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TeamMember(Base):
    __tablename__ = 'team_members'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    role = Column(String(50), default='viewer')
    status = Column(String(50), default='active')
    invited_by = Column(String(36))
    joined_at = Column(DateTime)
    last_active = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class APIKey(Base):
    __tablename__ = 'api_keys'
    id = Column(Integer, primary_key=True)
    key_id = Column(String(36), unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(10))  # First 8 chars for identification
    key_hash = Column(String(255), nullable=False)  # Hashed full key
    permissions = Column(Text)  # JSON
    rate_limit = Column(Integer)
    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)
    created_by = Column(String(36))
    status = Column(String(50), default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime)


# ============================================================================
# COST TRACKING TABLES
# ============================================================================

class CostRecord(Base):
    __tablename__ = 'cost_records'
    id = Column(Integer, primary_key=True)
    record_id = Column(String(36), unique=True, nullable=False)
    organization_id = Column(Integer)
    agent_id = Column(String(36))
    workflow_id = Column(String(36))
    task_id = Column(String(36))
    provider = Column(String(50))
    model = Column(String(100))
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class Budget(Base):
    """Budget limits and alerts"""
    __tablename__ = 'budgets'
    id = Column(Integer, primary_key=True)
    budget_id = Column(String(36), unique=True, nullable=False)
    organization_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    period = Column(String(20), nullable=False)  # daily, weekly, monthly, quarterly, yearly
    amount = Column(Float, nullable=False)  # USD
    currency = Column(String(3), nullable=False, default='USD')
    scope_type = Column(String(50))  # agent, category, organization
    scope_id = Column(String(255))
    alert_threshold_info = Column(Float, nullable=False, default=50.0)
    alert_threshold_warning = Column(Float, nullable=False, default=75.0)
    alert_threshold_critical = Column(Float, nullable=False, default=90.0)
    auto_disable_on_exceeded = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    extra_metadata = Column(Text)  # JSON
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(255))


class CostEvent(Base):
    """Individual cost event for tracking"""
    __tablename__ = 'cost_events'
    id = Column(Integer, primary_key=True)
    event_id = Column(String(36), unique=True, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    organization_id = Column(String(255), nullable=False)
    user_id = Column(String(255))
    agent_id = Column(String(36))
    task_id = Column(String(36))
    workflow_id = Column(String(36))
    category = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)  # USD
    currency = Column(String(3), nullable=False, default='USD')
    provider = Column(String(50))
    model = Column(String(100))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    total_tokens = Column(Integer)
    extra_metadata = Column("metadata", Text)  # JSON
    recorded_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# AUDIT TABLES
# ============================================================================

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id = Column(Integer, primary_key=True)
    event_id = Column(String(36), unique=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    user_id = Column(String(255))
    user_email = Column(String(255))
    user_role = Column(String(100))
    session_id = Column(String(255))
    request_id = Column(String(255))
    ip_address = Column(String(50))
    user_agent = Column(String(512))
    resource_type = Column(String(100))
    resource_id = Column(String(255))
    resource_name = Column(String(255))
    action = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    changes = Column(Text)  # JSON
    request_data = Column(Text)  # JSON
    response_data = Column(Text)  # JSON
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    error_code = Column(String(100))
    cost_impact = Column(Float)
    tags = Column(Text)  # JSON
    extra_metadata = Column("metadata", Text)  # Maps Python attr to DB column 'metadata'
    pii_accessed = Column(Boolean, default=False)
    sensitive_action = Column(Boolean, default=False)
    retention_days = Column(Integer, default=2555)
    parent_event_id = Column(String(36))
    correlation_id = Column(String(255))


# ============================================================================
# RBAC TABLES
# ============================================================================

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    permissions = Column(Text)  # JSON array
    is_system_role = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class UserRole(Base):
    __tablename__ = 'user_roles'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'))
    organization_id = Column(Integer)
    granted_by = Column(String(36))
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)


# ============================================================================
# SSO / SAML TABLES
# ============================================================================

class SSOProvider(Base):
    __tablename__ = 'sso_providers'
    id = Column(Integer, primary_key=True)
    provider_id = Column(String(36), unique=True, nullable=False)
    organization_id = Column(Integer)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # saml, oidc, oauth2
    config = Column(Text)  # JSON - encrypted
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SSOSession(Base):
    __tablename__ = 'sso_sessions'
    id = Column(Integer, primary_key=True)
    session_id = Column(String(36), unique=True, nullable=False)
    user_id = Column(String(36), nullable=False)
    provider_id = Column(String(36))
    attributes = Column(Text)  # JSON
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# USER TABLE (for auth)
# ============================================================================

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255))
    name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    organization_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)


# ============================================================================
# LLM PROVIDER CONFIG TABLES
# ============================================================================

class LLMProviderConfig(Base):
    __tablename__ = 'llm_providers'
    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    organization_id = Column(Integer)
    created_by_user_id = Column(String(255), nullable=False, default='system')
    api_key = Column(Text)  # Should be encrypted
    api_endpoint = Column(String(500))
    additional_config = Column(Text)  # JSON
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LLMModelConfig(Base):
    __tablename__ = 'llm_models'
    id = Column(Integer, primary_key=True)
    provider_id = Column(Integer, ForeignKey('llm_providers.id'))
    model_name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text)
    capabilities = Column(Text)  # JSON array
    max_tokens = Column(Integer, default=4096)
    supports_streaming = Column(Boolean, default=True)
    supports_function_calling = Column(Boolean, default=False)
    input_cost_per_1m_tokens = Column(Float, nullable=False, default=0.0)
    output_cost_per_1m_tokens = Column(Float, nullable=False, default=0.0)
    currency = Column(String(3), default='USD')
    avg_latency_ms = Column(Float, default=0.0)
    avg_quality_score = Column(Float, default=0.0)
    success_rate = Column(Float, default=1.0)
    rate_limit_per_minute = Column(Integer)
    rate_limit_per_day = Column(Integer)
    max_concurrent_requests = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    is_experimental = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# INTEGRATION MARKETPLACE TABLES
# ============================================================================

class Integration(Base):
    __tablename__ = 'integrations'
    id = Column(Integer, primary_key=True)
    integration_id = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    long_description = Column(Text)
    category = Column(String(100), nullable=False)
    tags = Column(Text)  # JSON array as TEXT
    integration_type = Column(String(50), nullable=False)
    auth_type = Column(String(50), nullable=False)
    configuration_schema = Column(Text)  # JSON as TEXT
    auth_config_schema = Column(Text)  # JSON as TEXT
    supported_actions = Column(Text)  # JSON as TEXT
    supported_triggers = Column(Text)  # JSON as TEXT
    version = Column(String(50), default='1.0.0')
    homepage_url = Column(String(500))
    documentation_url = Column(String(500))
    icon_url = Column(String(500))
    provider_name = Column(String(255))
    provider_url = Column(String(500))
    is_verified = Column(Boolean, default=False)
    is_community = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    is_free = Column(Boolean, default=True)
    pricing_info = Column(Text)  # JSON as TEXT
    status = Column(String(50), default='approved')
    total_installations = Column(Integer, default=0)
    total_active_installations = Column(Integer, default=0)
    average_rating = Column(Float)
    total_ratings = Column(Integer, default=0)
    published_at = Column(DateTime)
    created_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class IntegrationInstallation(Base):
    __tablename__ = 'integration_installations'
    id = Column(Integer, primary_key=True)
    installation_id = Column(String(36), unique=True, nullable=False)
    integration_id = Column(String(36), ForeignKey('integrations.integration_id'), nullable=False)
    organization_id = Column(String(255), nullable=False)
    installed_version = Column(String(50), default='1.0.0')
    status = Column(String(50), default='not_installed')
    configuration = Column(Text)  # JSON as TEXT
    auth_credentials = Column(Text)  # JSON as TEXT - stores encrypted credentials
    total_executions = Column(Integer, default=0)
    successful_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)
    last_execution_at = Column(DateTime)
    is_healthy = Column(Boolean, default=True)
    last_health_check_at = Column(DateTime)
    health_check_message = Column(Text)
    installed_by = Column(String(255))
    installed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class IntegrationRating(Base):
    __tablename__ = 'integration_ratings'
    id = Column(Integer, primary_key=True)
    rating_id = Column(String(36), unique=True, nullable=False)
    integration_id = Column(String(36), ForeignKey('integrations.integration_id'), nullable=False)
    organization_id = Column(String(255), nullable=False)
    user_id = Column(String(255), nullable=False)
    rating = Column(Integer, nullable=False)
    review = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class IntegrationExecutionLog(Base):
    __tablename__ = 'integration_execution_logs'
    id = Column(Integer, primary_key=True)
    log_id = Column(String(36), unique=True, nullable=False)
    installation_id = Column(String(36), ForeignKey('integration_installations.installation_id'))
    action_id = Column(String(36))
    organization_id = Column(String(255))
    action_name = Column(String(255))
    input_parameters = Column(Text)  # JSON as TEXT
    output_result = Column(Text)  # JSON as TEXT
    status = Column(String(50))
    error_message = Column(Text)
    error_code = Column(String(100))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_ms = Column(Float)
    workflow_execution_id = Column(String(36))
    task_id = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# INITIALIZE DATABASE
# ============================================================================

def init_database():
    """Create all tables."""
    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("Tables created successfully!")

    # Create alembic version table and mark as upgraded
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
        """))
        # Mark as fully migrated to skip all PostgreSQL migrations
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260102_0001')"))
        conn.commit()
        print("Alembic version set to 20260102_0001 (SQLite compat)")

    print(f"\nDatabase initialized at: {DB_PATH}")
    print("You can now start the API server with: ./run_api.sh")


if __name__ == "__main__":
    init_database()
