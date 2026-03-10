"""
Orchestrator Service

Manages agent registration, task routing, and multi-agent coordination.
"""

__version__ = "0.1.0"

from .registry import AgentRegistry, get_registry
from .router import TaskRouter, get_router
from .queue import TaskQueue, get_queue

__all__ = [
    "AgentRegistry",
    "get_registry",
    "TaskRouter",
    "get_router",
    "TaskQueue",
    "get_queue",
]
