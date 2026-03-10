"""
Unit Tests for InMemoryTaskQueue

Tests for the in-memory task queue fallback used when Redis is unavailable.
Verifies enqueue/dequeue cycles, capability routing, task completion,
failure with retry, dead-letter queue behaviour, and queue depth tracking.
"""

import os
os.environ["USE_SQLITE"] = "true"

import pytest
import pytest_asyncio
from uuid import uuid4

from backend.orchestrator.memory_queue import InMemoryTaskQueue
from backend.shared.models import Task, TaskInput, TaskStatus, TaskPriority


def _make_task(capability: str = "code_review", **overrides) -> Task:
    """Helper to create a Task with sensible defaults."""
    defaults = dict(
        capability=capability,
        input=TaskInput(data={"payload": "test"}),
        priority=TaskPriority.NORMAL,
        timeout_seconds=300,
        max_retries=3,
    )
    defaults.update(overrides)
    return Task(**defaults)


@pytest_asyncio.fixture
async def queue():
    """Create a fresh InMemoryTaskQueue for each test."""
    q = InMemoryTaskQueue()
    yield q
    await q.close()


# --------------------------------------------------------------------------- #
# 1. Enqueue / dequeue cycle
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_enqueue_dequeue_cycle(queue):
    """Enqueuing a task and then calling get_next_task returns the same task."""
    task = _make_task("summarization")
    returned_id = await queue.enqueue_task(task)

    assert returned_id == task.task_id

    fetched = await queue.get_next_task("summarization")

    assert fetched is not None
    assert fetched.task_id == task.task_id
    assert fetched.capability == "summarization"
    assert fetched.status == TaskStatus.RUNNING
    assert fetched.started_at is not None


# --------------------------------------------------------------------------- #
# 2. Empty queue returns None
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_next_task_empty_queue(queue):
    """get_next_task returns None when no tasks are queued for the capability."""
    result = await queue.get_next_task("nonexistent_capability")
    assert result is None


@pytest.mark.asyncio
async def test_get_next_task_after_drain(queue):
    """After all tasks are dequeued, get_next_task returns None."""
    task = _make_task("code_review")
    await queue.enqueue_task(task)

    # Drain the queue
    fetched = await queue.get_next_task("code_review")
    assert fetched is not None

    # Now the queue should be empty
    result = await queue.get_next_task("code_review")
    assert result is None


# --------------------------------------------------------------------------- #
# 3. Multiple capabilities with independent queues
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_independent_capability_queues(queue):
    """Tasks enqueued for different capabilities are routed independently."""
    task_a = _make_task("email_classification")
    task_b = _make_task("code_review")
    task_c = _make_task("email_classification")

    await queue.enqueue_task(task_a)
    await queue.enqueue_task(task_b)
    await queue.enqueue_task(task_c)

    # Dequeue from email_classification -- should get task_a first (FIFO)
    fetched_email = await queue.get_next_task("email_classification")
    assert fetched_email is not None
    assert fetched_email.task_id == task_a.task_id

    # Dequeue from code_review -- should get task_b
    fetched_code = await queue.get_next_task("code_review")
    assert fetched_code is not None
    assert fetched_code.task_id == task_b.task_id

    # Second email_classification dequeue -- should get task_c
    fetched_email_2 = await queue.get_next_task("email_classification")
    assert fetched_email_2 is not None
    assert fetched_email_2.task_id == task_c.task_id

    # Both queues now empty
    assert await queue.get_next_task("email_classification") is None
    assert await queue.get_next_task("code_review") is None


# --------------------------------------------------------------------------- #
# 4. Complete task updates status
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_complete_task_updates_status(queue):
    """Completing a task sets status to COMPLETED with output and cost."""
    task = _make_task("summarization")
    await queue.enqueue_task(task)

    # Move task to RUNNING
    fetched = await queue.get_next_task("summarization")
    assert fetched is not None

    output_data = {"summary": "All tests pass."}
    await queue.complete_task(fetched.task_id, output=output_data, cost=0.05)

    completed = await queue.get_task(fetched.task_id)
    assert completed is not None
    assert completed.status == TaskStatus.COMPLETED
    assert completed.output is not None
    assert completed.output.data == output_data
    assert completed.actual_cost == 0.05
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_complete_task_default_cost(queue):
    """Completing a task without specifying cost defaults to 0.0."""
    task = _make_task("code_review")
    await queue.enqueue_task(task)
    fetched = await queue.get_next_task("code_review")

    await queue.complete_task(fetched.task_id, output={"result": "ok"})

    completed = await queue.get_task(fetched.task_id)
    assert completed.actual_cost == 0.0


@pytest.mark.asyncio
async def test_complete_nonexistent_task(queue):
    """Completing a task that does not exist should not raise."""
    fake_id = uuid4()
    # Should silently return (logs a warning internally)
    await queue.complete_task(fake_id, output={"x": 1})


# --------------------------------------------------------------------------- #
# 5. Fail task with retry re-queues
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_fail_task_with_retry_requeues(queue):
    """Failing a task with retry=True re-enqueues it when retries remain."""
    task = _make_task("code_review", max_retries=3)
    await queue.enqueue_task(task)
    fetched = await queue.get_next_task("code_review")

    await queue.fail_task(fetched.task_id, error="Transient error", retry=True)

    # Task should have been re-queued
    requeued = await queue.get_next_task("code_review")
    assert requeued is not None
    assert requeued.task_id == task.task_id
    assert requeued.retry_count == 1
    assert requeued.status == TaskStatus.RUNNING  # get_next_task sets RUNNING


@pytest.mark.asyncio
async def test_fail_task_retry_increments_count(queue):
    """Each retry increments the retry_count until max_retries is reached."""
    task = _make_task("code_review", max_retries=2)
    await queue.enqueue_task(task)

    # First failure -- retry_count goes to 1 (< max_retries=2), re-queued
    fetched = await queue.get_next_task("code_review")
    await queue.fail_task(fetched.task_id, error="fail 1", retry=True)

    t = await queue.get_task(task.task_id)
    assert t.retry_count == 1
    assert t.status == TaskStatus.PENDING  # re-queued as PENDING

    # Second failure -- retry_count goes to 2 (== max_retries), goes to DLQ
    fetched2 = await queue.get_next_task("code_review")
    await queue.fail_task(fetched2.task_id, error="fail 2", retry=True)

    t2 = await queue.get_task(task.task_id)
    assert t2.retry_count == 2
    assert t2.status == TaskStatus.FAILED


# --------------------------------------------------------------------------- #
# 6. Fail task without retry moves to DLQ
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_fail_task_no_retry_goes_to_dlq(queue):
    """Failing a task with retry=False moves it directly to the DLQ."""
    task = _make_task("code_review", max_retries=5)
    await queue.enqueue_task(task)
    fetched = await queue.get_next_task("code_review")

    await queue.fail_task(fetched.task_id, error="Fatal error", retry=False)

    failed = await queue.get_task(fetched.task_id)
    assert failed.status == TaskStatus.FAILED
    assert failed.error_message == "Fatal error"
    assert failed.completed_at is not None

    # Should NOT be re-queued
    assert await queue.get_next_task("code_review") is None

    # DLQ should contain the task
    dlq_depth = await queue.get_dead_letter_queue_depth()
    assert dlq_depth == 1


@pytest.mark.asyncio
async def test_fail_task_max_retries_exhausted_goes_to_dlq(queue):
    """When retry_count reaches max_retries the task lands in the DLQ."""
    task = _make_task("code_review", max_retries=1)
    await queue.enqueue_task(task)

    fetched = await queue.get_next_task("code_review")
    # retry_count will become 1, which equals max_retries -- should go to DLQ
    await queue.fail_task(fetched.task_id, error="Too many failures", retry=True)

    t = await queue.get_task(task.task_id)
    assert t.status == TaskStatus.FAILED
    assert t.error_message == "Too many failures"

    dlq_depth = await queue.get_dead_letter_queue_depth()
    assert dlq_depth == 1


# --------------------------------------------------------------------------- #
# 7. Queue depth tracking
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_all_queue_depths_empty(queue):
    """Empty queue reports no depths."""
    depths = await queue.get_all_queue_depths()
    assert depths == {}


@pytest.mark.asyncio
async def test_get_all_queue_depths(queue):
    """Queue depths accurately reflect the number of pending tasks per capability."""
    # Enqueue several tasks across two capabilities
    for _ in range(3):
        await queue.enqueue_task(_make_task("email_classification"))
    for _ in range(2):
        await queue.enqueue_task(_make_task("code_review"))

    depths = await queue.get_all_queue_depths()

    assert depths["email_classification"] == 3
    assert depths["code_review"] == 2
    assert len(depths) == 2


@pytest.mark.asyncio
async def test_queue_depth_decreases_on_dequeue(queue):
    """Dequeuing a task decreases the reported queue depth."""
    await queue.enqueue_task(_make_task("code_review"))
    await queue.enqueue_task(_make_task("code_review"))

    assert (await queue.get_all_queue_depths())["code_review"] == 2

    await queue.get_next_task("code_review")

    assert (await queue.get_all_queue_depths())["code_review"] == 1


@pytest.mark.asyncio
async def test_queue_depth_excludes_empty_capabilities(queue):
    """Capabilities whose queues have been fully drained are excluded from depths."""
    await queue.enqueue_task(_make_task("code_review"))
    await queue.get_next_task("code_review")  # drain it

    depths = await queue.get_all_queue_depths()
    assert "code_review" not in depths


@pytest.mark.asyncio
async def test_get_queue_depth_single_capability(queue):
    """get_queue_depth returns the count for a single capability."""
    await queue.enqueue_task(_make_task("code_review"))
    await queue.enqueue_task(_make_task("code_review"))

    depth = await queue.get_queue_depth("code_review")
    assert depth == 2

    depth_empty = await queue.get_queue_depth("nonexistent")
    assert depth_empty == 0
