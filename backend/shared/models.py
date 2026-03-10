"""Core data models for Agent Orchestration Platform."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class AgentStatus(str, Enum):
    """Agent lifecycle status."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


# ============================================================================
# Agent Models
# ============================================================================

class AgentCapability(BaseModel):
    """Capability that an agent can perform."""
    name: str = Field(..., description="Capability name (e.g., 'email_classification')")
    description: str = Field(..., description="What this capability does")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for inputs")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for outputs")
    estimated_cost: Optional[float] = Field(None, description="Estimated cost per execution (USD)")
    avg_duration_seconds: Optional[float] = Field(None, description="Average execution time")


class AgentConfig(BaseModel):
    """Agent configuration."""
    agent_id: UUID = Field(default_factory=uuid4)
    organization_id: str = Field(..., description="Organization ID for multi-tenancy")
    name: str = Field(..., description="Unique agent name")
    description: Optional[str] = Field(None, description="Agent description")

    # Capabilities
    capabilities: List[AgentCapability] = Field(default_factory=list)

    # Resource limits
    cost_limit_daily: float = Field(100.0, description="Max daily cost in USD")
    cost_limit_monthly: float = Field(3000.0, description="Max monthly cost in USD")
    max_concurrent_tasks: int = Field(5, description="Max concurrent task executions")

    # LLM configuration
    llm_provider: LLMProvider = Field(LLMProvider.OPENAI)
    llm_model: str = Field("gpt-4", description="Model name")
    llm_temperature: float = Field(0.7, description="LLM temperature")
    llm_max_tokens: Optional[int] = Field(None, description="Max tokens per request")

    # Metadata
    framework: str = Field("custom", description="Agent framework (langchain, crewai, etc)")
    version: str = Field("1.0.0", description="Agent version")
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentState(BaseModel):
    """Current agent runtime state."""
    agent_id: UUID
    status: AgentStatus = Field(AgentStatus.INITIALIZING)

    # Metrics
    tasks_completed: int = Field(0)
    tasks_failed: int = Field(0)
    total_cost_today: float = Field(0.0, description="USD")
    total_cost_month: float = Field(0.0, description="USD")

    # Resource usage
    active_tasks: int = Field(0)
    avg_task_duration_seconds: Optional[float] = None

    # Health
    last_heartbeat: Optional[datetime] = None
    error_message: Optional[str] = None

    # Timestamps
    started_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Task Models
# ============================================================================

class TaskInput(BaseModel):
    """Task input data."""
    data: Dict[str, Any] = Field(..., description="Task input data")
    schema_version: str = Field("1.0", description="Input schema version")


class TaskOutput(BaseModel):
    """Task output data."""
    data: Dict[str, Any] = Field(..., description="Task output data")
    schema_version: str = Field("1.0", description="Output schema version")
    confidence: Optional[float] = Field(None, description="Confidence score 0-1")


class Task(BaseModel):
    """Agent task definition."""
    task_id: UUID = Field(default_factory=uuid4)
    organization_id: Optional[str] = Field(None, description="Organization ID for multi-tenancy")

    # Task definition
    capability: str = Field(..., description="Required capability")
    input: TaskInput
    priority: TaskPriority = Field(TaskPriority.NORMAL)

    # Assignment
    assigned_agent_id: Optional[UUID] = None
    assigned_agent_name: Optional[str] = None

    # Execution
    status: TaskStatus = Field(TaskStatus.PENDING)
    output: Optional[TaskOutput] = None
    error_message: Optional[str] = None

    # Timing
    timeout_seconds: int = Field(300, description="Max execution time")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Cost tracking
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None

    # Retry configuration
    max_retries: int = Field(3)
    retry_count: int = Field(0)

    # Metadata
    parent_task_id: Optional[UUID] = None  # For multi-step workflows
    workflow_id: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# LLM Request/Response Models
# ============================================================================

class LLMRequest(BaseModel):
    """LLM API request."""
    request_id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    task_id: Optional[UUID] = None

    # LLM parameters
    provider: LLMProvider
    model: str
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    temperature: float = Field(0.7)
    max_tokens: Optional[int] = None

    # Tracking
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LLMResponse(BaseModel):
    """LLM API response."""
    request_id: UUID

    # Response data
    content: str = Field(..., description="LLM generated content")
    finish_reason: str = Field(..., description="Completion reason")

    # Usage tracking
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    # Cost
    estimated_cost: float = Field(..., description="USD")

    # Timing
    latency_ms: float = Field(..., description="Response latency in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Metrics Models
# ============================================================================

class AgentMetrics(BaseModel):
    """Agent performance metrics."""
    agent_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Task metrics
    tasks_completed_1h: int = Field(0)
    tasks_failed_1h: int = Field(0)
    avg_task_duration_1h: Optional[float] = None

    # Cost metrics
    cost_1h: float = Field(0.0)
    cost_24h: float = Field(0.0)
    cost_30d: float = Field(0.0)

    # LLM metrics
    llm_requests_1h: int = Field(0)
    llm_tokens_1h: int = Field(0)
    avg_llm_latency_1h: Optional[float] = None

    # Success rate
    success_rate_1h: Optional[float] = None
    success_rate_24h: Optional[float] = None


class SystemMetrics(BaseModel):
    """Overall system metrics."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Agent stats
    total_agents: int = Field(0)
    active_agents: int = Field(0)
    idle_agents: int = Field(0)
    error_agents: int = Field(0)

    # Task stats
    pending_tasks: int = Field(0)
    running_tasks: int = Field(0)
    completed_tasks_1h: int = Field(0)
    failed_tasks_1h: int = Field(0)

    # Cost stats
    total_cost_1h: float = Field(0.0)
    total_cost_24h: float = Field(0.0)
    total_cost_30d: float = Field(0.0)

    # Performance
    avg_task_duration_1h: Optional[float] = None
    avg_queue_wait_time_1h: Optional[float] = None
    p95_task_duration_1h: Optional[float] = None
