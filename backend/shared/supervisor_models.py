"""
Supervisor Orchestration Mode - Data Models

Enables multi-agent coordination patterns:
- Supervisor agents (manager pattern)
- Task decomposition and routing
- Group chat mode (AutoGen-style)
- Sequential and concurrent execution
- Dynamic agent handoffs

Competitive advantage: Matches AWS Agent Squad + Microsoft AutoGen patterns.
This solves complex multi-agent orchestration needs.
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


# ============================================================================
# Enums
# ============================================================================

class SupervisorMode(Enum):
    """Supervisor orchestration modes"""
    SEQUENTIAL = "sequential"  # Execute agents one after another
    CONCURRENT = "concurrent"  # Execute agents in parallel
    GROUP_CHAT = "group_chat"  # Multi-agent conversation (AutoGen pattern)
    HANDOFF = "handoff"  # Dynamic agent handoffs based on context
    MAGENTIC = "magentic"  # Magnetic routing (AWS pattern)
    HIERARCHICAL = "hierarchical"  # Multi-level supervisor hierarchy


class RoutingStrategy(Enum):
    """How supervisor routes tasks to agents"""
    ROUND_ROBIN = "round_robin"  # Distribute evenly
    CAPABILITY_MATCH = "capability_match"  # Match task to agent capabilities
    LOAD_BALANCED = "load_balanced"  # Route to least busy agent
    PRIORITY_BASED = "priority_based"  # Route by task priority
    LLM_DECISION = "llm_decision"  # Let LLM decide routing
    CUSTOM_RULES = "custom_rules"  # Custom routing rules


class AgentRole(Enum):
    """Agent roles in supervisor orchestration"""
    SUPERVISOR = "supervisor"  # Coordinates other agents
    WORKER = "worker"  # Executes specific tasks
    SPECIALIST = "specialist"  # Domain expert for specific task type
    REVIEWER = "reviewer"  # Reviews and validates outputs
    TOOL = "tool"  # Tool/function agent


class TaskStatus(Enum):
    """Status of tasks assigned by supervisor"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ConversationTurn(Enum):
    """Who's turn in group chat mode"""
    SUPERVISOR = "supervisor"
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


# ============================================================================
# Database Models
# ============================================================================

class SupervisorConfigModel(Base):
    """
    Supervisor configuration - defines supervisor agent behavior.

    Stores supervisor settings, routing strategies, and agent pool.
    """
    __tablename__ = "supervisor_configs"

    # Primary key
    config_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Orchestration mode
    mode = Column(String(50), nullable=False)  # SupervisorMode enum
    routing_strategy = Column(String(50), nullable=False, default="capability_match")

    # Agent pool (list of agent IDs this supervisor can use)
    agent_pool = Column(ARRAY(String), nullable=False, default=list)

    # Agent capabilities map (agent_id -> capabilities)
    agent_capabilities = Column(JSONB, nullable=True)
    # {
    #   "agent_1": {"skills": ["python", "data_analysis"], "max_concurrent": 5},
    #   "agent_2": {"skills": ["writing", "research"], "max_concurrent": 3}
    # }

    # Supervisor behavior
    max_agents_concurrent = Column(Integer, nullable=False, default=3)
    max_conversation_turns = Column(Integer, nullable=True)  # For group chat mode
    timeout_seconds = Column(Integer, nullable=False, default=300)

    # LLM configuration for supervisor decisions
    llm_model = Column(String(100), nullable=True)  # e.g., "gpt-4"
    llm_temperature = Column(Float, nullable=True, default=0.7)
    llm_system_prompt = Column(Text, nullable=True)

    # Routing rules (for custom routing strategy)
    routing_rules = Column(JSONB, nullable=True)
    # [
    #   {"if": "task contains 'python'", "route_to": "agent_1"},
    #   {"if": "task contains 'writing'", "route_to": "agent_2"}
    # ]

    # Task decomposition settings
    auto_decompose_tasks = Column(Boolean, nullable=False, default=True)
    decomposition_prompt = Column(Text, nullable=True)

    # Metadata
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_supervisor_config_org', 'organization_id'),
        Index('idx_supervisor_config_active', 'is_active'),
    )

    def __repr__(self):
        return f"<SupervisorConfig(id={self.config_id}, name={self.name}, mode={self.mode})>"


class SupervisorExecutionModel(Base):
    """
    Supervisor execution - tracks supervisor orchestration session.

    Records entire supervisor execution including task decomposition,
    agent assignments, and conversation history.
    """
    __tablename__ = "supervisor_executions"

    # Primary key
    execution_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # References
    config_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    workflow_execution_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    organization_id = Column(String(255), nullable=False, index=True)

    # Execution metadata
    status = Column(String(50), nullable=False, default="pending")
    mode = Column(String(50), nullable=False)  # SupervisorMode enum

    # Input/Output
    input_task = Column(Text, nullable=False)  # Original task given to supervisor
    output_result = Column(JSONB, nullable=True)  # Final aggregated result

    # Task decomposition
    subtasks = Column(JSONB, nullable=True)
    # [
    #   {"id": "task_1", "description": "...", "assigned_to": "agent_1", "status": "completed"},
    #   {"id": "task_2", "description": "...", "assigned_to": "agent_2", "status": "in_progress"}
    # ]

    # Agent assignments
    agent_assignments = Column(JSONB, nullable=True)
    # {
    #   "agent_1": {"tasks": ["task_1", "task_3"], "status": "active"},
    #   "agent_2": {"tasks": ["task_2"], "status": "active"}
    # }

    # Conversation history (for group chat mode)
    conversation_history = Column(JSONB, nullable=True)
    # [
    #   {"turn": 1, "speaker": "supervisor", "message": "...", "timestamp": "..."},
    #   {"turn": 2, "speaker": "agent_1", "message": "...", "timestamp": "..."}
    # ]

    # Routing decisions
    routing_decisions = Column(JSONB, nullable=True)
    # [
    #   {"task_id": "task_1", "agent": "agent_1", "reason": "best capability match", "confidence": 0.95}
    # ]

    # Performance metrics
    total_agents_used = Column(Integer, nullable=True)
    total_turns = Column(Integer, nullable=True)  # For group chat
    duration_ms = Column(Float, nullable=True)

    # Cost tracking
    total_cost = Column(Float, nullable=False, default=0.0)
    cost_by_agent = Column(JSONB, nullable=True)
    # {"agent_1": 0.05, "agent_2": 0.03, "supervisor": 0.02}

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Error handling
    error_message = Column(Text, nullable=True)
    failed_tasks = Column(JSONB, nullable=True)

    # Metadata
    extra_metadata = Column(JSONB, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_supervisor_exec_config', 'config_id'),
        Index('idx_supervisor_exec_workflow', 'workflow_execution_id'),
        Index('idx_supervisor_exec_org', 'organization_id'),
        Index('idx_supervisor_exec_status', 'status'),
        Index('idx_supervisor_exec_created', 'created_at'),
    )

    def __repr__(self):
        return f"<SupervisorExecution(id={self.execution_id}, status={self.status})>"


class AgentRegistryModel(Base):
    """
    Agent registry - catalog of available agents for supervisor.

    Stores agent metadata, capabilities, and availability.
    """
    __tablename__ = "agent_registry"

    # Primary key
    agent_id = Column(String(255), primary_key=True)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    role = Column(String(50), nullable=False)  # AgentRole enum

    # Capabilities
    capabilities = Column(ARRAY(String), nullable=True)
    # ["python", "data_analysis", "api_integration"]

    specialization = Column(String(255), nullable=True)
    # "financial_analysis", "content_writing", "customer_support"

    # Configuration
    agent_type = Column(String(50), nullable=True)  # "llm", "function", "tool"
    llm_model = Column(String(100), nullable=True)  # If LLM agent
    system_prompt = Column(Text, nullable=True)
    tools = Column(ARRAY(String), nullable=True)  # Available tools

    # Performance constraints
    max_concurrent_tasks = Column(Integer, nullable=False, default=5)
    average_duration_ms = Column(Float, nullable=True)
    average_cost_per_task = Column(Float, nullable=True)

    # Availability
    is_active = Column(Boolean, nullable=False, default=True)
    current_load = Column(Integer, nullable=False, default=0)  # Current active tasks

    # Statistics
    total_tasks_completed = Column(Integer, nullable=False, default=0)
    total_tasks_failed = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=True)
    average_rating = Column(Float, nullable=True)

    # Metadata
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_agent_registry_org', 'organization_id'),
        Index('idx_agent_registry_role', 'role'),
        Index('idx_agent_registry_active', 'is_active'),
        Index('idx_agent_registry_capabilities', 'capabilities', postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<Agent(id={self.agent_id}, name={self.name}, role={self.role})>"


class TaskAssignmentModel(Base):
    """
    Task assignment - tracks individual task assigned to agent by supervisor.

    Stores task details, assignment history, and execution results.
    """
    __tablename__ = "task_assignments"

    # Primary key
    assignment_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # References
    execution_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(String(255), nullable=False, index=True)
    organization_id = Column(String(255), nullable=False, index=True)

    # Task details
    task_id = Column(String(255), nullable=False)
    task_description = Column(Text, nullable=False)
    task_type = Column(String(100), nullable=True)
    priority = Column(Integer, nullable=False, default=0)

    # Status
    status = Column(String(50), nullable=False, default="pending")  # TaskStatus enum

    # Input/Output
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)

    # Dependencies
    depends_on = Column(ARRAY(String), nullable=True)  # Task IDs this task depends on
    blocks = Column(ARRAY(String), nullable=True)  # Task IDs this task blocks

    # Assignment metadata
    assigned_at = Column(DateTime, nullable=True)
    assigned_by = Column(String(50), nullable=True)  # "supervisor" or "auto"
    routing_reason = Column(Text, nullable=True)  # Why this agent was chosen

    # Execution
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Float, nullable=True)

    # Cost
    cost = Column(Float, nullable=False, default=0.0)
    tokens_used = Column(Integer, nullable=True)

    # Error handling
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)

    # Quality metrics
    confidence_score = Column(Float, nullable=True)
    validation_status = Column(String(50), nullable=True)  # "passed", "failed", "pending"

    # Metadata
    extra_metadata = Column(JSONB, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_task_assignment_exec', 'execution_id'),
        Index('idx_task_assignment_agent', 'agent_id'),
        Index('idx_task_assignment_org', 'organization_id'),
        Index('idx_task_assignment_status', 'status'),
        Index('idx_task_assignment_task_id', 'task_id'),
    )

    def __repr__(self):
        return f"<TaskAssignment(id={self.assignment_id}, task={self.task_id}, agent={self.agent_id})>"


# ============================================================================
# Dataclasses for Application Logic
# ============================================================================

@dataclass
class SupervisorConfig:
    """Supervisor configuration data structure"""
    config_id: UUID
    organization_id: str
    name: str
    mode: SupervisorMode
    routing_strategy: RoutingStrategy
    agent_pool: List[str]

    description: Optional[str] = None
    agent_capabilities: Optional[Dict[str, Any]] = None
    max_agents_concurrent: int = 3
    max_conversation_turns: Optional[int] = None
    timeout_seconds: int = 300

    llm_model: Optional[str] = None
    llm_temperature: float = 0.7
    llm_system_prompt: Optional[str] = None

    routing_rules: Optional[List[Dict[str, Any]]] = None
    auto_decompose_tasks: bool = True
    decomposition_prompt: Optional[str] = None

    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class SupervisorExecution:
    """Supervisor execution data structure"""
    execution_id: UUID
    config_id: UUID
    organization_id: str
    status: str
    mode: SupervisorMode
    input_task: str

    workflow_execution_id: Optional[UUID] = None
    output_result: Optional[Dict[str, Any]] = None
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    agent_assignments: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    routing_decisions: List[Dict[str, Any]] = field(default_factory=list)

    total_agents_used: Optional[int] = None
    total_turns: Optional[int] = None
    duration_ms: Optional[float] = None
    total_cost: float = 0.0
    cost_by_agent: Optional[Dict[str, float]] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class Agent:
    """Agent data structure"""
    agent_id: str
    organization_id: str
    name: str
    role: AgentRole

    description: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    specialization: Optional[str] = None

    agent_type: Optional[str] = None
    llm_model: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: List[str] = field(default_factory=list)

    max_concurrent_tasks: int = 5
    average_duration_ms: Optional[float] = None
    average_cost_per_task: Optional[float] = None

    is_active: bool = True
    current_load: int = 0

    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    success_rate: Optional[float] = None


@dataclass
class TaskAssignment:
    """Task assignment data structure"""
    assignment_id: UUID
    execution_id: UUID
    agent_id: str
    task_id: str
    task_description: str
    status: TaskStatus

    task_type: Optional[str] = None
    priority: int = 0

    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None

    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)

    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    cost: float = 0.0
    tokens_used: Optional[int] = None

    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None


@dataclass
class DecomposedTask:
    """Decomposed task from supervisor task decomposition"""
    task_id: str
    description: str
    task_type: str
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0
    estimated_duration_ms: Optional[float] = None
    required_capabilities: List[str] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RoutingDecision:
    """Routing decision made by supervisor"""
    task_id: str
    agent_id: str
    reason: str
    confidence: float
    strategy: str = "capability_match"
    alternatives: List[str] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# Supervisor Mode Configurations
# ============================================================================

SUPERVISOR_MODE_CONFIGS = {
    "sequential": {
        "name": "Sequential Execution",
        "description": "Execute agents one after another in order",
        "icon": "➡️",
        "use_cases": ["Pipeline processing", "Step-by-step workflows"],
        "supports_parallel": False
    },
    "concurrent": {
        "name": "Concurrent Execution",
        "description": "Execute multiple agents in parallel",
        "icon": "⚡",
        "use_cases": ["Parallel data processing", "Fan-out tasks"],
        "supports_parallel": True
    },
    "group_chat": {
        "name": "Group Chat Mode",
        "description": "Multi-agent conversation (AutoGen pattern)",
        "icon": "💬",
        "use_cases": ["Collaborative problem solving", "Multi-perspective analysis"],
        "supports_parallel": False
    },
    "handoff": {
        "name": "Dynamic Handoff",
        "description": "Agents hand off tasks dynamically based on context",
        "icon": "🔄",
        "use_cases": ["Customer support escalation", "Expertise routing"],
        "supports_parallel": False
    },
    "magentic": {
        "name": "Magentic Routing",
        "description": "AWS-style magnetic routing to best agent",
        "icon": "🧲",
        "use_cases": ["Smart task distribution", "Capability matching"],
        "supports_parallel": True
    },
    "hierarchical": {
        "name": "Hierarchical Supervisors",
        "description": "Multi-level supervisor hierarchy",
        "icon": "🏢",
        "use_cases": ["Complex org structures", "Nested workflows"],
        "supports_parallel": True
    }
}

ROUTING_STRATEGY_CONFIGS = {
    "round_robin": {
        "name": "Round Robin",
        "description": "Distribute tasks evenly across agents",
        "complexity": "simple"
    },
    "capability_match": {
        "name": "Capability Matching",
        "description": "Match tasks to agent capabilities",
        "complexity": "medium"
    },
    "load_balanced": {
        "name": "Load Balanced",
        "description": "Route to least busy agent",
        "complexity": "medium"
    },
    "priority_based": {
        "name": "Priority Based",
        "description": "Route high priority tasks first",
        "complexity": "simple"
    },
    "llm_decision": {
        "name": "LLM Decision",
        "description": "Let LLM decide best routing",
        "complexity": "complex"
    },
    "custom_rules": {
        "name": "Custom Rules",
        "description": "User-defined routing rules",
        "complexity": "medium"
    }
}
