"""Unit tests for Task Queue.

NOTE: These tests require an async Redis client (fakeredis.aioredis.FakeRedis)
but the current conftest.py provides sync FakeRedis. These tests are skipped
until the fixtures are updated. See backend/tests/ for working tests.
"""
import json
import pytest
import pytest_asyncio
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

# Skip all tests in this module - requires async Redis client
pytestmark = pytest.mark.skip(reason="Tests require async Redis client - see backend/tests/ for working tests")

from backend.shared.models import Task, TaskStatus, TaskPriority, TaskInput
from backend.orchestrator.queue import TaskQueue


@pytest.mark.unit
@pytest.mark.asyncio
class TestTaskQueue:
    """Test suite for TaskQueue."""

    @pytest_asyncio.fixture
    async def queue(self, async_redis_client):
        """Create TaskQueue with fake Redis."""
        # Mock router and collector
        mock_router = MagicMock()
        mock_router.route_task = AsyncMock(return_value=uuid4())
        mock_router.assign_task = AsyncMock()
        mock_router.complete_task = AsyncMock()
        mock_router.fail_task = AsyncMock()

        with patch("backend.orchestrator.queue.get_collector") as mock_get_collector:
            mock_collector = MagicMock()
            mock_collector.record_task_completion = AsyncMock()
            mock_get_collector.return_value = mock_collector

            queue = TaskQueue(
                router=mock_router,
                redis_client=async_redis_client
            )
            yield queue
            await queue.close()

    @pytest.fixture
    def sample_task(self):
        """Sample task for testing."""
        return Task(
            task_id=uuid4(),
            capability="test_capability",
            input=TaskInput(data={"test": "data"}),
            priority=TaskPriority.NORMAL,
            max_retries=3,
        )

    async def test_enqueue_task_success(self, queue, sample_task):
        """Test successful task enqueue."""
        task_id = await queue.enqueue_task(sample_task)

        assert task_id == sample_task.task_id

        # Verify task stored in Redis
        task_data_key = queue._task_data_key(task_id)
        task_data_str = await queue.redis.get(task_data_key)
        assert task_data_str is not None

        # Verify task added to capability queue
        queue_key = queue._task_queue_key("test_capability")
        queue_length = await queue.redis.llen(queue_key)
        assert queue_length == 1

        # Verify task ID in queue
        task_id_in_queue = await queue.redis.lindex(queue_key, 0)
        assert task_id_in_queue == str(task_id)

    async def test_enqueue_task_without_capability(self, queue):
        """Test enqueueing task without capability fails."""
        task = Task(
            task_id=uuid4(),
            capability="",  # Empty capability
            input=TaskInput(data={}),
        )

        with pytest.raises(ValueError, match="must have a capability"):
            await queue.enqueue_task(task)

    async def test_enqueue_task_updates_status(self, queue, sample_task):
        """Test enqueue updates task status to QUEUED."""
        await queue.enqueue_task(sample_task)

        task_data_str = await queue.redis.get(queue._task_data_key(sample_task.task_id))
        task_data = json.loads(task_data_str)
        assert task_data["status"] == TaskStatus.QUEUED.value

    async def test_get_next_task_success(self, queue, sample_task):
        """Test getting next task from queue."""
        await queue.enqueue_task(sample_task)

        task = await queue.get_next_task("test_capability")

        assert task is not None
        assert task.task_id == sample_task.task_id
        assert task.status == TaskStatus.RUNNING
        assert task.assigned_agent_id is not None
        assert task.started_at is not None

    async def test_get_next_task_empty_queue(self, queue):
        """Test getting task from empty queue returns None."""
        task = await queue.get_next_task("nonexistent_capability")
        assert task is None

    async def test_get_next_task_calls_router(self, queue, sample_task):
        """Test get_next_task calls router to assign agent."""
        await queue.enqueue_task(sample_task)

        await queue.get_next_task("test_capability")

        queue.router.route_task.assert_called_once()
        queue.router.assign_task.assert_called_once()

    async def test_get_next_task_no_agents_available(self, queue, sample_task):
        """Test get_next_task when no agents available."""
        # Mock router to return None (no agents)
        queue.router.route_task = AsyncMock(return_value=None)

        await queue.enqueue_task(sample_task)

        task = await queue.get_next_task("test_capability")

        assert task is None

        # Task should be put back in queue
        queue_depth = await queue.get_queue_depth("test_capability")
        assert queue_depth == 1

    async def test_get_next_task_expired_task_data(self, queue, sample_task):
        """Test handling of expired task data."""
        await queue.enqueue_task(sample_task)

        # Delete task data (simulate expiration)
        await queue.redis.delete(queue._task_data_key(sample_task.task_id))

        task = await queue.get_next_task("test_capability")

        assert task is None

    async def test_complete_task_success(self, queue, sample_task):
        """Test completing a task."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")

        output = {"result": "success"}
        cost = 0.25

        await queue.complete_task(task.task_id, output, cost)

        # Verify task result stored
        result_key = queue._task_result_key(task.task_id)
        result_str = await queue.redis.get(result_key)
        assert result_str is not None

        result_data = json.loads(result_str)
        assert result_data["status"] == TaskStatus.COMPLETED.value
        assert result_data["output"]["data"] == output
        assert result_data["actual_cost"] == cost

    async def test_complete_task_calls_collector(self, queue, sample_task):
        """Test complete_task records metrics."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")

        await queue.complete_task(task.task_id, {"result": "success"}, 0.1)

        queue.collector.record_task_completion.assert_called_once()
        call_args = queue.collector.record_task_completion.call_args[1]
        assert call_args["task_id"] == task.task_id
        assert call_args["success"] is True

    async def test_complete_task_calls_router(self, queue, sample_task):
        """Test complete_task updates router state."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")

        await queue.complete_task(task.task_id, {"result": "success"}, 0.1)

        queue.router.complete_task.assert_called_once()

    async def test_complete_nonexistent_task(self, queue):
        """Test completing non-existent task doesn't error."""
        fake_id = uuid4()
        await queue.complete_task(fake_id, {"result": "success"})
        # Should not raise

    async def test_fail_task_with_retry(self, queue, sample_task):
        """Test failing task with retry."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")

        await queue.fail_task(task.task_id, "Test error", retry=True)

        # Task should be back in queue
        queue_depth = await queue.get_queue_depth("test_capability")
        assert queue_depth == 1

        # Retry count should be incremented
        requeued_task = await queue.get_task(task.task_id)
        assert requeued_task.retry_count == 1
        assert requeued_task.status == TaskStatus.PENDING

    async def test_fail_task_max_retries_exceeded(self, queue):
        """Test failing task when max retries exceeded."""
        task = Task(
            task_id=uuid4(),
            capability="test_capability",
            input=TaskInput(data={}),
            max_retries=2,
            retry_count=2,  # Already at max
        )

        await queue.enqueue_task(task)
        fetched_task = await queue.get_next_task("test_capability")

        await queue.fail_task(fetched_task.task_id, "Test error", retry=True)

        # Task should be in DLQ
        dlq_depth = await queue.get_dead_letter_queue_depth()
        assert dlq_depth == 1

        # Task should be marked failed
        failed_task = await queue.get_task(fetched_task.task_id)
        assert failed_task.status == TaskStatus.FAILED
        assert failed_task.error_message == "Test error"

    async def test_fail_task_no_retry(self, queue, sample_task):
        """Test failing task without retry."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")

        await queue.fail_task(task.task_id, "Test error", retry=False)

        # Task should be in DLQ
        dlq_depth = await queue.get_dead_letter_queue_depth()
        assert dlq_depth == 1

        # Task should be marked failed
        failed_task = await queue.get_task(task.task_id)
        assert failed_task.status == TaskStatus.FAILED

    async def test_fail_task_records_metrics(self, queue, sample_task):
        """Test fail_task records metrics for permanent failures."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")

        await queue.fail_task(task.task_id, "Test error", retry=False)

        queue.collector.record_task_completion.assert_called_once()
        call_args = queue.collector.record_task_completion.call_args[1]
        assert call_args["success"] is False

    async def test_fail_task_calls_router(self, queue, sample_task):
        """Test fail_task updates router state."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")

        await queue.fail_task(task.task_id, "Test error")

        queue.router.fail_task.assert_called_once()

    async def test_get_task(self, queue, sample_task):
        """Test getting task by ID."""
        await queue.enqueue_task(sample_task)

        retrieved_task = await queue.get_task(sample_task.task_id)

        assert retrieved_task is not None
        assert retrieved_task.task_id == sample_task.task_id
        assert retrieved_task.capability == "test_capability"

    async def test_get_nonexistent_task(self, queue):
        """Test getting non-existent task returns None."""
        fake_id = uuid4()
        task = await queue.get_task(fake_id)
        assert task is None

    async def test_get_task_result(self, queue, sample_task):
        """Test getting task result."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")

        output = {"result": "completed"}
        await queue.complete_task(task.task_id, output, 0.1)

        result = await queue.get_task_result(task.task_id)

        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.output.data == output

    async def test_get_task_result_nonexistent(self, queue):
        """Test getting result for non-existent task."""
        fake_id = uuid4()
        result = await queue.get_task_result(fake_id)
        assert result is None

    async def test_get_queue_depth(self, queue):
        """Test getting queue depth for capability."""
        # Enqueue multiple tasks
        for i in range(5):
            task = Task(
                task_id=uuid4(),
                capability="test_capability",
                input=TaskInput(data={"index": i}),
            )
            await queue.enqueue_task(task)

        depth = await queue.get_queue_depth("test_capability")
        assert depth == 5

    async def test_get_queue_depth_empty(self, queue):
        """Test getting depth of empty queue."""
        depth = await queue.get_queue_depth("nonexistent_capability")
        assert depth == 0

    async def test_get_all_queue_depths(self, queue):
        """Test getting depths for all capabilities."""
        # Enqueue tasks for multiple capabilities
        capabilities = ["cap_a", "cap_b", "cap_c"]
        counts = [3, 1, 2]

        for cap, count in zip(capabilities, counts):
            for _ in range(count):
                task = Task(
                    task_id=uuid4(),
                    capability=cap,
                    input=TaskInput(data={}),
                )
                await queue.enqueue_task(task)

        depths = await queue.get_all_queue_depths()

        assert depths["cap_a"] == 3
        assert depths["cap_b"] == 1
        assert depths["cap_c"] == 2

    async def test_get_all_queue_depths_empty(self, queue):
        """Test getting all depths when no queues exist."""
        depths = await queue.get_all_queue_depths()
        assert depths == {}

    async def test_get_dead_letter_queue_depth(self, queue):
        """Test getting DLQ depth."""
        # Create tasks that will fail permanently
        for i in range(3):
            task = Task(
                task_id=uuid4(),
                capability="test_capability",
                input=TaskInput(data={}),
                max_retries=0,  # Fail immediately
            )
            await queue.enqueue_task(task)
            fetched_task = await queue.get_next_task("test_capability")
            await queue.fail_task(fetched_task.task_id, "Error", retry=False)

        dlq_depth = await queue.get_dead_letter_queue_depth()
        assert dlq_depth == 3

    async def test_task_ttl_set_correctly(self, queue, sample_task):
        """Test that task data has TTL set."""
        await queue.enqueue_task(sample_task)

        task_data_key = queue._task_data_key(sample_task.task_id)
        ttl = await queue.redis.ttl(task_data_key)

        # TTL should be positive (not expired)
        assert ttl > 0

    async def test_result_ttl_24_hours(self, queue, sample_task):
        """Test that task results have 24-hour TTL."""
        await queue.enqueue_task(sample_task)
        task = await queue.get_next_task("test_capability")
        await queue.complete_task(task.task_id, {"result": "done"}, 0.1)

        result_key = queue._task_result_key(task.task_id)
        ttl = await queue.redis.ttl(result_key)

        # Should be close to 86400 seconds (24 hours)
        assert 86390 <= ttl <= 86400

    async def test_multiple_tasks_fifo_order(self, queue):
        """Test tasks are processed in FIFO order."""
        task_ids = []

        for i in range(3):
            task = Task(
                task_id=uuid4(),
                capability="test_capability",
                input=TaskInput(data={"order": i}),
            )
            await queue.enqueue_task(task)
            task_ids.append(task.task_id)

        # Dequeue tasks
        for expected_id in task_ids:
            task = await queue.get_next_task("test_capability")
            assert task.task_id == expected_id

    async def test_queue_isolation_by_capability(self, queue):
        """Test tasks are isolated by capability."""
        task_a = Task(
            task_id=uuid4(),
            capability="capability_a",
            input=TaskInput(data={}),
        )
        task_b = Task(
            task_id=uuid4(),
            capability="capability_b",
            input=TaskInput(data={}),
        )

        await queue.enqueue_task(task_a)
        await queue.enqueue_task(task_b)

        # Getting from capability_a should only return task_a
        fetched_a = await queue.get_next_task("capability_a")
        assert fetched_a.task_id == task_a.task_id

        # capability_a queue should now be empty
        depth_a = await queue.get_queue_depth("capability_a")
        assert depth_a == 0

        # capability_b queue should still have task_b
        depth_b = await queue.get_queue_depth("capability_b")
        assert depth_b == 1


@pytest.mark.unit
class TestTaskQueueGlobalInstance:
    """Test global queue instance management."""

    def test_get_queue_singleton(self):
        """Test that get_queue returns singleton instance."""
        from backend.orchestrator.queue import get_queue

        queue1 = get_queue()
        queue2 = get_queue()

        assert queue1 is queue2
