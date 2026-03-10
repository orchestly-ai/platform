"""
BYOC Worker SDK - Data Models

Defines the data structures used for job management.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


class JobStatus(Enum):
    """Status of a job"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class Job:
    """
    A job to be executed by the worker.

    Jobs are created by the Agent Orchestration platform and polled
    by BYOC workers for execution.
    """
    job_id: str
    workflow_id: str
    execution_id: str
    organization_id: str

    # Workflow definition
    workflow_definition: Dict[str, Any]

    # Input data
    input_data: Optional[Dict[str, Any]] = None

    # Configuration
    timeout_seconds: int = 3600
    max_retries: int = 3
    retry_count: int = 0

    # Scheduling info
    scheduled_for: Optional[datetime] = None
    priority: int = 0

    # Context
    context: Optional[Dict[str, Any]] = None

    # Metadata
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create a Job from a dictionary."""
        return cls(
            job_id=data["job_id"],
            workflow_id=data["workflow_id"],
            execution_id=data["execution_id"],
            organization_id=data["organization_id"],
            workflow_definition=data["workflow_definition"],
            input_data=data.get("input_data"),
            timeout_seconds=data.get("timeout_seconds", 3600),
            max_retries=data.get("max_retries", 3),
            retry_count=data.get("retry_count", 0),
            scheduled_for=datetime.fromisoformat(data["scheduled_for"]) if data.get("scheduled_for") else None,
            priority=data.get("priority", 0),
            context=data.get("context"),
            metadata=data.get("metadata"),
        )


@dataclass
class JobResult:
    """
    Result of executing a job.

    Sent back to the Agent Orchestration platform after execution.
    """
    job_id: str
    status: JobStatus
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None

    # Performance metrics
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Resource usage
    tokens_used: Optional[int] = None
    cost: Optional[float] = None

    # Step-level results
    step_results: Optional[List[Dict[str, Any]]] = None

    # Logs
    logs: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API submission."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "error_traceback": self.error_traceback,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "tokens_used": self.tokens_used,
            "cost": self.cost,
            "step_results": self.step_results,
            "logs": self.logs,
        }


@dataclass
class WorkerStatus:
    """Status of a worker"""
    worker_id: str
    organization_id: str
    status: str  # idle, busy, offline
    current_job_id: Optional[str] = None
    jobs_completed: int = 0
    jobs_failed: int = 0
    total_duration_seconds: float = 0.0
    last_heartbeat: Optional[datetime] = None
    started_at: Optional[datetime] = None
    capabilities: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider (BYOK)"""
    provider: str  # openai, anthropic, google, etc.
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None


@dataclass
class WorkerConfig:
    """Configuration for a BYOC worker"""
    api_url: str
    api_key: str
    organization_id: str

    # Worker settings
    worker_id: Optional[str] = None
    max_concurrent_jobs: int = 1
    poll_interval_seconds: float = 5.0
    heartbeat_interval_seconds: float = 30.0
    job_timeout_seconds: int = 3600

    # LLM providers (BYOK)
    llm_providers: List[LLMProviderConfig] = field(default_factory=list)

    # Capabilities
    capabilities: Optional[List[str]] = None

    # Logging
    log_level: str = "INFO"

    # Metadata
    metadata: Optional[Dict[str, Any]] = None
