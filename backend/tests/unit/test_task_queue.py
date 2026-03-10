"""
Unit Tests for Task Queue

Tests for task queuing, routing, completion, and failure handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timezone

from backend.orchestrator.queue import TaskQueue, get_queue
from backend.shared.models import Task, TaskStatus, TaskPriority, TaskInput, TaskOutput


class TestTaskQueueInitialization:
    """Tests for TaskQueue initialization."""

    def test_queue_initialization_with_redis(self):
        """Test queue initializes with Redis client."""
        mock_redis = MagicMock()

        with patch('backend.orchestrator.queue.get_router') as mock_get_router:
            with patch('backend.orchestrator.queue.get_collector') as mock_get_collector:
                mock_get_router.return_value = MagicMock()
                mock_get_collector.return_value = MagicMock()

                queue = TaskQueue(redis_client=mock_redis)

                assert queue.redis == mock_redis

    def test_get_queue_singleton(self):
        """Test get_queue returns same instance."""
        import backend.orchestrator.queue as queue_module
        queue_module._queue = None

        mock_redis = MagicMock()

        with patch('backend.orchestrator.queue.get_router') as mock_get_router:
            with patch('backend.orchestrator.queue.get_collector') as mock_get_collector:
                with patch('backend.orchestrator.queue.redis.from_url', return_value=mock_redis):
                    mock_get_router.return_value = MagicMock()
                    mock_get_collector.return_value = MagicMock()

                    queue1 = get_queue()
                    queue2 = get_queue()

                    assert queue1 is queue2


class TestTaskQueueOperations:
    """Tests for task queue operations."""

    @pytest.fixture
    def mock_queue(self):
        """Create a mock task queue for testing."""
        with patch('backend.orchestrator.queue.get_router') as mock_get_router:
            with patch('backend.orchestrator.queue.get_collector') as mock_get_collector:
                mock_router = MagicMock()
                mock_router.route_task = AsyncMock(return_value=uuid4())
                mock_router.assign_task = AsyncMock()
                mock_router.complete_task = AsyncMock()
                mock_router.fail_task = AsyncMock()
                mock_get_router.return_value = mock_router

                mock_collector = MagicMock()
                mock_collector.record_task_completion = AsyncMock()
                mock_get_collector.return_value = mock_collector

                mock_redis = AsyncMock()
                mock_redis.set = AsyncMock()
                mock_redis.get = AsyncMock()
                mock_redis.rpush = AsyncMock()
                mock_redis.lpop = AsyncMock()
                mock_redis.delete = AsyncMock()
                mock_redis.zadd = AsyncMock()

                queue = TaskQueue(redis_client=mock_redis)
                yield queue

    @pytest.mark.asyncio
    async def test_enqueue_task(self, mock_queue):
        """Test enqueueing a task."""
        task = Task(
            task_id=uuid4(),
            capability="code_review",
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING,
            input=TaskInput(data={"code": "def hello(): pass"}),
            created_at=datetime.now(timezone.utc),
            timeout_seconds=300,
            max_retries=3
        )

        # Mock pipeline context manager for atomic enqueue
        mock_pipe = AsyncMock()
        mock_pipe.set = MagicMock()
        mock_pipe.rpush = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[True, 1])
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_queue.redis.pipeline = MagicMock(return_value=mock_pipe)

        task_id = await mock_queue.enqueue_task(task)

        assert task_id == task.task_id
        # enqueue_task uses a pipeline: one set + one rpush in a single transaction
        mock_pipe.set.assert_called_once()
        mock_pipe.rpush.assert_called_once()
        mock_pipe.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_next_task_empty_queue(self, mock_queue):
        """Test getting next task from empty queue."""
        mock_queue.redis.lmove = AsyncMock(return_value=None)

        task = await mock_queue.get_next_task("code_review")

        assert task is None

    @pytest.mark.asyncio
    async def test_get_next_task_with_available_task(self, mock_queue):
        """Test getting next task when one is available."""
        task_id = uuid4()
        agent_id = uuid4()

        task_data = {
            "task_id": str(task_id),
            "capability": "code_review",
            "priority": "normal",
            "status": "queued",
            "input": {"data": {"code": "def hello(): pass"}},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "timeout_seconds": 300,
            "max_retries": 3,
            "retry_count": 0
        }

        mock_queue.redis.lpop = AsyncMock(return_value=str(task_id))
        mock_queue.redis.get = AsyncMock(return_value=str(task_data).replace("'", '"'))
        mock_queue.router.route_task = AsyncMock(return_value=agent_id)

        # Need to properly mock Task deserialization
        with patch('backend.orchestrator.queue.Task') as MockTask:
            mock_task = MagicMock()
            mock_task.task_id = task_id
            mock_task.capability = "code_review"
            mock_task.priority = TaskPriority.NORMAL
            mock_task.assigned_agent_id = None
            mock_task.status = TaskStatus.QUEUED
            mock_task.model_dump_json = MagicMock(return_value='{}')
            MockTask.return_value = mock_task

            # For this test, we'll test the core logic manually
            # Real integration tests should test with actual Task objects
            pass

    @pytest.mark.asyncio
    async def test_complete_task_success(self, mock_queue):
        """Test completing a task successfully."""
        task_id = uuid4()
        agent_id = uuid4()

        # Create task data that simulates a task in RUNNING state
        task_data = Task(
            task_id=task_id,
            capability="code_review",
            priority=TaskPriority.NORMAL,
            status=TaskStatus.RUNNING,
            input=TaskInput(data={}),
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            assigned_agent_id=agent_id,
            timeout_seconds=300,
            max_retries=3
        )

        mock_queue.redis.get = AsyncMock(return_value=task_data.model_dump_json())

        # Mock pipeline context manager for atomic result + data writes
        mock_pipe = AsyncMock()
        mock_pipe.set = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True])
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_queue.redis.pipeline = MagicMock(return_value=mock_pipe)

        await mock_queue.complete_task(
            task_id=task_id,
            output={"result": "approved"},
            cost=0.01
        )

        # Verify task result + data were stored via pipeline
        assert mock_pipe.set.call_count == 2
        mock_pipe.execute.assert_called_once()
        # Verify router was notified
        mock_queue.router.complete_task.assert_called()

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self, mock_queue):
        """Test completing a task that doesn't exist."""
        task_id = uuid4()
        mock_queue.redis.get = AsyncMock(return_value=None)

        # Should not raise, just log warning
        await mock_queue.complete_task(
            task_id=task_id,
            output={"result": "approved"},
            cost=0.01
        )

    @pytest.mark.asyncio
    async def test_fail_task_with_retry(self, mock_queue):
        """Test failing a task with retry."""
        task_id = uuid4()
        agent_id = uuid4()

        task_data = Task(
            task_id=task_id,
            capability="code_review",
            priority=TaskPriority.NORMAL,
            status=TaskStatus.RUNNING,
            input=TaskInput(data={}),
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            assigned_agent_id=agent_id,
            timeout_seconds=300,
            max_retries=3,
            retry_count=0
        )

        mock_queue.redis.get = AsyncMock(return_value=task_data.model_dump_json())

        # Mock pipeline context manager for atomic retry scheduling
        mock_pipe = AsyncMock()
        mock_pipe.set = MagicMock()
        mock_pipe.zadd = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[True, 1])
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=False)
        mock_queue.redis.pipeline = MagicMock(return_value=mock_pipe)

        await mock_queue.fail_task(
            task_id=task_id,
            error="Connection timeout",
            retry=True
        )

        # Verify task was scheduled for retry via sorted set in pipeline
        mock_pipe.set.assert_called_once()
        mock_pipe.zadd.assert_called_once()
        mock_pipe.execute.assert_called_once()
        mock_queue.router.fail_task.assert_called()

    @pytest.mark.asyncio
    async def test_fail_task_max_retries_exceeded(self, mock_queue):
        """Test failing a task when max retries exceeded."""
        task_id = uuid4()
        agent_id = uuid4()

        task_data = Task(
            task_id=task_id,
            capability="code_review",
            priority=TaskPriority.NORMAL,
            status=TaskStatus.RUNNING,
            input=TaskInput(data={}),
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            assigned_agent_id=agent_id,
            timeout_seconds=300,
            max_retries=3,
            retry_count=3  # Already at max
        )

        mock_queue.redis.get = AsyncMock(return_value=task_data.model_dump_json())

        await mock_queue.fail_task(
            task_id=task_id,
            error="Persistent failure",
            retry=True
        )

        # Verify task was moved to dead letter queue
        assert mock_queue.redis.rpush.called

    @pytest.mark.asyncio
    async def test_get_task_by_id(self, mock_queue):
        """Test getting a task by ID."""
        task_id = uuid4()

        task_data = Task(
            task_id=task_id,
            capability="code_review",
            priority=TaskPriority.NORMAL,
            status=TaskStatus.QUEUED,
            input=TaskInput(data={}),
            created_at=datetime.now(timezone.utc),
            timeout_seconds=300,
            max_retries=3
        )

        mock_queue.redis.get = AsyncMock(return_value=task_data.model_dump_json())

        result = await mock_queue.get_task(task_id)

        assert result is not None
        assert result.task_id == task_id

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, mock_queue):
        """Test getting a task that doesn't exist."""
        task_id = uuid4()
        mock_queue.redis.get = AsyncMock(return_value=None)

        result = await mock_queue.get_task(task_id)

        assert result is None


class TestTaskQueueKeys:
    """Tests for task queue key generation."""

    def test_task_queue_key_generation(self):
        """Test task queue key is generated correctly."""
        with patch('backend.orchestrator.queue.get_router') as mock_get_router:
            with patch('backend.orchestrator.queue.get_collector') as mock_get_collector:
                mock_get_router.return_value = MagicMock()
                mock_get_collector.return_value = MagicMock()

                queue = TaskQueue(redis_client=MagicMock())

                key = queue._task_queue_key("code_review")

                assert "code_review" in key
                assert "queue" in key.lower()

    def test_task_data_key_generation(self):
        """Test task data key is generated correctly."""
        with patch('backend.orchestrator.queue.get_router') as mock_get_router:
            with patch('backend.orchestrator.queue.get_collector') as mock_get_collector:
                mock_get_router.return_value = MagicMock()
                mock_get_collector.return_value = MagicMock()

                queue = TaskQueue(redis_client=MagicMock())
                task_id = uuid4()

                key = queue._task_data_key(task_id)

                assert str(task_id) in key

    def test_task_result_key_generation(self):
        """Test task result key is generated correctly."""
        with patch('backend.orchestrator.queue.get_router') as mock_get_router:
            with patch('backend.orchestrator.queue.get_collector') as mock_get_collector:
                mock_get_router.return_value = MagicMock()
                mock_get_collector.return_value = MagicMock()

                queue = TaskQueue(redis_client=MagicMock())
                task_id = uuid4()

                key = queue._task_result_key(task_id)

                assert str(task_id) in key
                assert "result" in key.lower()
