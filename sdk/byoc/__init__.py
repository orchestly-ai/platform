"""
BYOC Worker SDK - Bring Your Own Compute

A lightweight Python package for customers to deploy workflow workers
on their own infrastructure.

Usage:
    from agent_orchestration.byoc import Worker

    worker = Worker(
        api_url="https://api.agent-orchestration.com",
        api_key="your-api-key",
        organization_id="your-org",
    )

    # Start processing workflows
    worker.start()
"""

from .worker import Worker, WorkerConfig
from .executor import WorkflowExecutor
from .models import Job, JobResult, JobStatus

__version__ = "0.1.0"
__all__ = [
    "Worker",
    "WorkerConfig",
    "WorkflowExecutor",
    "Job",
    "JobResult",
    "JobStatus",
]
