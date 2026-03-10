"""
Task Queue - Redis-based task queue for distributing work to agents.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
from uuid import UUID

import redis.asyncio as redis

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)

# Capability name validation pattern — prevents Redis key injection
CAPABILITY_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]{1,100}$')

from backend.shared.models import Task, TaskStatus, TaskOutput, TaskInput
from backend.shared.config import get_settings
from backend.orchestrator.router import TaskRouter, get_router
from backend.orchestrator.registry import get_registry
from backend.observer.metrics_collector import get_collector


class TaskQueue:
    """
    Redis-based task queue for agent orchestration.

    Features:
    - Priority queues (separate queues per capability)
    - Task retry with exponential backoff
    - Dead letter queue for failed tasks
    - Task result storage
    """

    def __init__(
        self,
        router: Optional[TaskRouter] = None,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        Initialize task queue.

        Args:
            router: Task router (default: global router)
            redis_client: Redis client (default: create from settings)
        """
        self.settings = get_settings()
        self.router = router or get_router()
        self.registry = get_registry()
        self.collector = get_collector()

        # Redis client
        self.redis = redis_client or redis.from_url(
            self.settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )

        # Shutdown flag for graceful drain
        self._shutting_down = False

        # Queue name prefixes
        self.TASK_QUEUE_PREFIX = "task_queue:"
        self.TASK_PROCESSING_PREFIX = "task_processing:"
        self.TASK_DATA_PREFIX = "task_data:"
        self.TASK_RESULT_PREFIX = "task_result:"
        self.DEAD_LETTER_QUEUE = "task_dlq"

    @staticmethod
    def _validate_capability(capability: str) -> str:
        """Validate capability name to prevent Redis key injection."""
        if not CAPABILITY_PATTERN.match(capability):
            raise ValueError(f"Invalid capability name: {capability!r}. Must match [a-zA-Z0-9_\\-.]{{1,100}}")
        return capability

    def _task_queue_key(self, capability: str) -> str:
        """Get Redis key for capability-specific queue."""
        self._validate_capability(capability)
        return f"{self.TASK_QUEUE_PREFIX}{capability}"

    def _task_processing_key(self, capability: str) -> str:
        """Get Redis key for processing list (tasks being worked on)."""
        self._validate_capability(capability)
        return f"{self.TASK_PROCESSING_PREFIX}{capability}"

    def _task_data_key(self, task_id: UUID) -> str:
        """Get Redis key for task data."""
        return f"{self.TASK_DATA_PREFIX}{task_id}"

    def _task_result_key(self, task_id: UUID) -> str:
        """Get Redis key for task result."""
        return f"{self.TASK_RESULT_PREFIX}{task_id}"

    async def enqueue_task(self, task: Task) -> UUID:
        """
        Add task to queue.

        Args:
            task: Task to enqueue

        Returns:
            Task ID

        Raises:
            ValueError: If task is invalid
        """
        if self._shutting_down:
            raise RuntimeError("TaskQueue is shutting down, not accepting new tasks")

        if not task.capability:
            raise ValueError("Task must have a capability")

        task_id = task.task_id

        # Set status before writing — single write, no race window
        task.status = TaskStatus.QUEUED
        task_data = task.model_dump_json()

        # Atomic: store task data + add to queue in a single pipeline
        queue_key = self._task_queue_key(task.capability)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(self._task_data_key(task_id), task_data, ex=self.settings.QUEUE_TTL_SECONDS)
            pipe.rpush(queue_key, str(task_id))
            await pipe.execute()

        logger.info(f"Enqueued task {task_id}: capability={task.capability}, priority={task.priority.value}")

        return task_id

    async def get_next_task(self, capability: str) -> Optional[Task]:
        """
        Get next task for given capability using atomic dequeue.

        Uses Redis LMOVE to atomically move task from queue to processing list,
        preventing task loss on crash.

        Args:
            capability: Required capability

        Returns:
            Task or None if queue is empty
        """
        queue_key = self._task_queue_key(capability)
        processing_key = self._task_processing_key(capability)

        # Atomic move: queue -> processing list (prevents task loss on crash)
        task_id_str = await self.redis.lmove(
            queue_key, processing_key, "LEFT", "RIGHT"
        )

        if not task_id_str:
            return None

        task_id = UUID(task_id_str)

        # Get task data
        task_data_str = await self.redis.get(self._task_data_key(task_id))

        if not task_data_str:
            logger.warning(f"Task {task_id} data not found (expired?), removing from processing list")
            await self.redis.lrem(processing_key, 1, task_id_str)
            return None

        # Parse task
        task_data = json.loads(task_data_str)
        task = Task(**task_data)

        # Route task to agent
        agent_id = await self.router.route_task(task)

        if not agent_id:
            # No agents available — move back to queue atomically
            await self.redis.lmove(
                processing_key, queue_key, "RIGHT", "LEFT"
            )
            return None

        # Assign task to agent
        task.assigned_agent_id = agent_id
        task.status = TaskStatus.RUNNING
        task.started_at = _utcnow()

        # Extend TTL to cover task timeout + buffer, then update data and remove from processing
        extended_ttl = max(self.settings.QUEUE_TTL_SECONDS, task.timeout_seconds + 3600)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(self._task_data_key(task_id), task.model_dump_json(), ex=extended_ttl)
            pipe.lrem(processing_key, 1, task_id_str)
            await pipe.execute()

        # Update router state
        await self.router.assign_task(task_id, agent_id)

        logger.info(f"Dispatched task {task_id} to agent {agent_id}")

        return task

    async def complete_task(
        self,
        task_id: UUID,
        output: Dict,
        cost: Optional[float] = None
    ) -> None:
        """
        Mark task as completed.

        Args:
            task_id: Task ID
            output: Task output data
            cost: Execution cost (USD)
        """
        # Get task data
        task_data_str = await self.redis.get(self._task_data_key(task_id))

        if not task_data_str:
            logger.warning(f"Task {task_id} not found")
            return

        task_data = json.loads(task_data_str)
        task = Task(**task_data)

        # Update task
        task.status = TaskStatus.COMPLETED
        task.completed_at = _utcnow()
        task.output = TaskOutput(data=output)
        task.actual_cost = cost or 0.0

        # Atomic: store result + update task data in a single pipeline
        task_json = task.model_dump_json()
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(self._task_result_key(task_id), task_json, ex=86400)  # Keep results for 24 hours
            pipe.set(self._task_data_key(task_id), task_json, ex=self.settings.QUEUE_TTL_SECONDS)
            await pipe.execute()

        # Update router state
        if task.assigned_agent_id:
            await self.router.complete_task(task_id, task.assigned_agent_id, cost or 0.0)

        # Record metrics
        if task.started_at:
            latency = (task.completed_at - task.started_at).total_seconds()
            await self.collector.record_task_completion(
                task_id=task_id,
                capability=task.capability,
                latency_seconds=latency,
                cost=cost or 0.0,
                success=True
            )

        logger.info(f"Task {task_id} completed" + (f" (cost: ${cost:.4f})" if cost else ""))

    async def fail_task(
        self,
        task_id: UUID,
        error: str,
        retry: bool = True
    ) -> None:
        """
        Mark task as failed with optional retry.

        Args:
            task_id: Task ID
            error: Error message
            retry: Whether to retry the task
        """
        # Get task data
        task_data_str = await self.redis.get(self._task_data_key(task_id))

        if not task_data_str:
            logger.warning(f"Task {task_id} not found for failure marking")
            return

        task_data = json.loads(task_data_str)
        task = Task(**task_data)

        # Increment retry count
        task.retry_count += 1

        # Update router state
        if task.assigned_agent_id:
            await self.router.fail_task(task_id, task.assigned_agent_id)

        # Check if should retry
        if retry and task.retry_count < task.max_retries:
            # Re-queue task with exponential backoff via delayed re-queue
            task.status = TaskStatus.PENDING
            task.assigned_agent_id = None

            # Exponential backoff: 5s, 10s, 20s, 40s, ... capped at 300s
            backoff_seconds = min(5 * (2 ** (task.retry_count - 1)), 300)

            # Atomic: update task data + schedule retry in a single pipeline
            retry_at = time.time() + backoff_seconds
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.set(
                    self._task_data_key(task_id),
                    task.model_dump_json(),
                    ex=self.settings.QUEUE_TTL_SECONDS
                )
                pipe.zadd(
                    f"task_retry:{task.capability}",
                    {str(task_id): retry_at}
                )
                await pipe.execute()

            logger.info(f"Task {task_id} failed, scheduled retry {task.retry_count}/{task.max_retries} in {backoff_seconds}s: {error}")

        else:
            # Max retries exceeded or no retry - move to dead letter queue
            task.status = TaskStatus.FAILED
            task.completed_at = _utcnow()
            task.error_message = error

            await self.redis.set(
                self._task_data_key(task_id),
                task.model_dump_json(),
                ex=self.settings.QUEUE_TTL_SECONDS
            )

            # Add to dead letter queue
            await self.redis.rpush(self.DEAD_LETTER_QUEUE, str(task_id))

            # Record metrics for failed task
            if task.started_at:
                latency = (task.completed_at - task.started_at).total_seconds()
                await self.collector.record_task_completion(
                    task_id=task_id,
                    capability=task.capability,
                    latency_seconds=latency,
                    cost=0.0,
                    success=False
                )

            logger.error(f"Task {task_id} failed permanently after {task.retry_count}/{task.max_retries} retries: {error}")

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """
        Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None
        """
        task_data_str = await self.redis.get(self._task_data_key(task_id))

        if not task_data_str:
            return None

        task_data = json.loads(task_data_str)
        return Task(**task_data)

    async def get_task_result(self, task_id: UUID) -> Optional[Task]:
        """
        Get task result (for completed tasks).

        Args:
            task_id: Task ID

        Returns:
            Task with result or None
        """
        result_str = await self.redis.get(self._task_result_key(task_id))

        if not result_str:
            return None

        task_data = json.loads(result_str)
        return Task(**task_data)

    async def get_queue_depth(self, capability: str) -> int:
        """
        Get number of tasks in queue for capability.

        Args:
            capability: Capability name

        Returns:
            Queue depth
        """
        queue_key = self._task_queue_key(capability)
        return await self.redis.llen(queue_key)

    async def get_all_queue_depths(self) -> Dict[str, int]:
        """
        Get queue depths for all capabilities.

        Uses SCAN to find keys and a pipeline for bulk LLEN (avoids N round-trips).

        Returns:
            Dictionary mapping capability → queue depth
        """
        pattern = f"{self.TASK_QUEUE_PREFIX}*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if not keys:
            return {}

        # Pipeline: single round-trip for all LLEN calls
        async with self.redis.pipeline(transaction=False) as pipe:
            for key in keys:
                pipe.llen(key)
            results = await pipe.execute()

        depths = {}
        for key, depth in zip(keys, results):
            if depth > 0:
                capability = key.replace(self.TASK_QUEUE_PREFIX, "")
                depths[capability] = depth

        return depths

    async def get_dead_letter_queue_depth(self) -> int:
        """Get number of permanently failed tasks."""
        return await self.redis.llen(self.DEAD_LETTER_QUEUE)

    async def promote_retries(self) -> int:
        """
        Move eligible retry tasks from sorted sets back to their queues.

        Checks all task_retry:<capability> sorted sets for tasks whose
        retry timestamp has passed, and moves them back to the task queue.

        Returns:
            Number of tasks promoted
        """
        promoted = 0
        now = time.time()

        async for key in self.redis.scan_iter(match="task_retry:*"):
            capability = key.replace("task_retry:", "")

            # Get all tasks whose retry time has passed (score <= now)
            task_ids = await self.redis.zrangebyscore(key, "-inf", now)

            if not task_ids:
                continue

            queue_key = self._task_queue_key(capability)

            async with self.redis.pipeline(transaction=True) as pipe:
                for task_id_str in task_ids:
                    pipe.rpush(queue_key, task_id_str)
                pipe.zremrangebyscore(key, "-inf", now)
                await pipe.execute()

            promoted += len(task_ids)
            if task_ids:
                logger.info(f"Promoted {len(task_ids)} retry tasks for capability '{capability}'")

        return promoted

    async def reap_stuck_tasks(self, max_age_seconds: int = 3600) -> int:
        """
        Recover tasks stuck in processing lists (e.g., after worker crashes).

        Scans all processing lists and re-queues any tasks whose data shows
        they've been in RUNNING state longer than max_age_seconds.

        Args:
            max_age_seconds: Max time a task can be in processing before reaping

        Returns:
            Number of tasks reaped
        """
        reaped = 0
        cutoff = _utcnow().timestamp() - max_age_seconds

        async for proc_key in self.redis.scan_iter(match=f"{self.TASK_PROCESSING_PREFIX}*"):
            capability = proc_key.replace(self.TASK_PROCESSING_PREFIX, "")
            queue_key = self._task_queue_key(capability)

            # Get all task IDs in the processing list
            task_ids = await self.redis.lrange(proc_key, 0, -1)

            for task_id_str in task_ids:
                task_data_str = await self.redis.get(self._task_data_key(UUID(task_id_str)))

                if not task_data_str:
                    # Task data expired — remove from processing list
                    await self.redis.lrem(proc_key, 1, task_id_str)
                    reaped += 1
                    logger.warning(f"Reaped expired task {task_id_str} from processing list")
                    continue

                task_data = json.loads(task_data_str)
                started_at = task_data.get("started_at")

                if started_at:
                    from datetime import datetime
                    started_ts = datetime.fromisoformat(started_at).timestamp()
                    if started_ts < cutoff:
                        # Task has been stuck too long — move back to queue
                        # Reset task state
                        task = Task(**task_data)
                        task.status = TaskStatus.PENDING
                        task.assigned_agent_id = None
                        task.started_at = None

                        # Atomic: remove from processing + re-queue + update data
                        async with self.redis.pipeline(transaction=True) as pipe:
                            pipe.lrem(proc_key, 1, task_id_str)
                            pipe.rpush(queue_key, task_id_str)
                            pipe.set(
                                self._task_data_key(task.task_id),
                                task.model_dump_json(),
                                ex=self.settings.QUEUE_TTL_SECONDS
                            )
                            await pipe.execute()

                        reaped += 1
                        logger.warning(f"Reaped stuck task {task_id_str} for capability '{capability}'")

        return reaped

    async def close(self, drain_timeout: float = 30.0):
        """
        Gracefully shut down the task queue.

        1. Stop accepting new tasks (set shutdown flag)
        2. Wait up to drain_timeout for in-flight tasks (processing lists) to empty
        3. Re-queue any remaining processing items back to their queues
        4. Close Redis connection

        Args:
            drain_timeout: Max seconds to wait for in-flight tasks to drain
        """
        self._shutting_down = True
        logger.info("TaskQueue shutting down, draining in-flight tasks...")

        # Collect all processing keys
        processing_pattern = f"{self.TASK_PROCESSING_PREFIX}*"
        processing_keys = []
        async for key in self.redis.scan_iter(match=processing_pattern):
            processing_keys.append(key)

        if processing_keys:
            # Wait for processing lists to drain (tasks completing naturally)
            deadline = time.monotonic() + drain_timeout
            while time.monotonic() < deadline:
                total_processing = 0
                for key in processing_keys:
                    total_processing += await self.redis.llen(key)
                if total_processing == 0:
                    break
                await asyncio.sleep(0.5)
            else:
                # Timeout — re-queue any remaining processing items
                for proc_key in processing_keys:
                    capability = proc_key.replace(self.TASK_PROCESSING_PREFIX, "")
                    queue_key = f"{self.TASK_QUEUE_PREFIX}{capability}"
                    while True:
                        task_id = await self.redis.lmove(proc_key, queue_key, "LEFT", "LEFT")
                        if not task_id:
                            break
                        logger.warning(f"Re-queued undrained task {task_id} for capability '{capability}'")

        logger.info("TaskQueue drain complete, closing Redis connection")
        await self.redis.close()


# Global queue instance
_queue: Optional[TaskQueue] = None


def get_queue():
    """Get or create global task queue instance.

    Tries Redis-backed TaskQueue first. Falls back to InMemoryTaskQueue
    if Redis is unavailable. Use set_queue() to inject a pre-verified queue.
    """
    global _queue
    if _queue is None:
        try:
            _queue = TaskQueue()
            logger.info("Task queue: Redis-backed (connection not yet verified)")
        except (ConnectionError, redis.RedisError, OSError) as e:
            logger.warning(f"Redis unavailable ({e}), using in-memory task queue")
            from backend.orchestrator.memory_queue import InMemoryTaskQueue
            _queue = InMemoryTaskQueue()
    return _queue


def set_queue(queue_instance: Union["TaskQueue", "InMemoryTaskQueue"]) -> None:
    """Set the global queue instance (used by lifespan after async verification)."""
    global _queue
    _queue = queue_instance
