"""
In-Memory Task Queue — fallback when Redis is unavailable.

Provides the same interface as TaskQueue but uses in-memory data structures.
Data is NOT persistent across restarts.
"""

import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from backend.shared.models import Task, TaskStatus, TaskOutput

logger = logging.getLogger(__name__)


class InMemoryTaskQueue:
    """
    In-memory task queue for local development without Redis.

    Same interface as TaskQueue so it can be used as a drop-in replacement.
    """

    def __init__(self):
        logger.warning(
            "Using in-memory task queue — tasks will NOT persist across restarts. "
            "Set REDIS_URL to use Redis for production."
        )
        # capability -> deque of task_ids
        self._queues: Dict[str, deque] = defaultdict(deque)
        # task_id -> Task
        self._tasks: Dict[str, Task] = {}
        # task_id -> Task (completed results)
        self._results: Dict[str, Task] = {}
        # dead letter queue
        self._dlq: List[str] = []

    async def enqueue_task(self, task: Task) -> UUID:
        """Add task to queue."""
        if not task.capability:
            raise ValueError("Task must have a capability")

        task_id = task.task_id
        task.status = TaskStatus.QUEUED
        self._tasks[str(task_id)] = task
        self._queues[task.capability].append(str(task_id))

        logger.info(f"Enqueued task {task_id}: capability={task.capability}")
        return task_id

    async def get_next_task(self, capability: str) -> Optional[Task]:
        """Get next task for given capability."""
        queue = self._queues.get(capability)
        if not queue:
            return None

        task_id_str = queue.popleft() if queue else None
        if not task_id_str:
            return None

        task = self._tasks.get(task_id_str)
        if not task:
            logger.warning(f"Task {task_id_str} data not found")
            return None

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        return task

    async def complete_task(
        self,
        task_id: UUID,
        output: Dict,
        cost: Optional[float] = None,
    ) -> None:
        """Mark task as completed."""
        key = str(task_id)
        task = self._tasks.get(key)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.output = TaskOutput(data=output)
        task.actual_cost = cost or 0.0

        self._results[key] = task
        logger.info(f"Task {task_id} completed")

    async def fail_task(
        self,
        task_id: UUID,
        error: str,
        retry: bool = True,
    ) -> None:
        """Mark task as failed with optional retry."""
        key = str(task_id)
        task = self._tasks.get(key)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return

        task.retry_count += 1

        if retry and task.retry_count < task.max_retries:
            task.status = TaskStatus.PENDING
            task.assigned_agent_id = None
            self._queues[task.capability].append(key)
            logger.info(f"Task {task_id} failed, retrying ({task.retry_count}/{task.max_retries})")
        else:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error_message = error
            self._dlq.append(key)
            logger.error(f"Task {task_id} failed permanently: {error}")

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """Get task by ID."""
        return self._tasks.get(str(task_id))

    async def get_task_result(self, task_id: UUID) -> Optional[Task]:
        """Get task result (for completed tasks)."""
        return self._results.get(str(task_id))

    async def get_queue_depth(self, capability: str) -> int:
        """Get number of tasks in queue for capability."""
        return len(self._queues.get(capability, deque()))

    async def get_all_queue_depths(self) -> Dict[str, int]:
        """Get queue depths for all capabilities."""
        return {
            cap: len(q)
            for cap, q in self._queues.items()
            if len(q) > 0
        }

    async def get_dead_letter_queue_depth(self) -> int:
        """Get number of permanently failed tasks."""
        return len(self._dlq)

    async def close(self):
        """No-op for in-memory queue."""
        pass
