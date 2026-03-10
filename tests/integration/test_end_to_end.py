"""Integration tests for end-to-end workflows.

NOTE: These integration tests require async Redis and have infrastructure dependencies.
They are skipped by default. See backend/tests/ for working tests.
"""
import asyncio
import pytest
from uuid import uuid4
from datetime import datetime

# Skip all tests in this module - requires async Redis and infrastructure
pytestmark = pytest.mark.skip(reason="Integration tests require infrastructure - see backend/tests/ for working tests")

from backend.shared.models import (
    AgentConfig,
    AgentCapability,
    Task,
    TaskInput,
    TaskPriority,
    TaskStatus,
)
from backend.orchestrator.registry import AgentRegistry
from backend.orchestrator.queue import TaskQueue
from backend.orchestrator.router import TaskRouter


@pytest.mark.integration
@pytest.mark.asyncio
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    async def setup_system(self, async_redis_client):
        """Set up complete system for integration testing."""
        # Create instances
        registry = AgentRegistry()
        router = TaskRouter(registry=registry)
        queue = TaskQueue(router=router, redis_client=async_redis_client)

        yield {
            "registry": registry,
            "router": router,
            "queue": queue,
        }

        # Cleanup
        await queue.close()

    @pytest.fixture
    def sample_agent_config(self):
        """Create sample agent configuration."""
        return AgentConfig(
            agent_id=uuid4(),
            name="Test Agent",
            capabilities=[
                AgentCapability(
                    name="test_capability",
                    description="Test capability for integration testing",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=100.0,
            cost_limit_monthly=1000.0,
            max_concurrent_tasks=5,
        )

    async def test_complete_task_workflow(self, setup_system, sample_agent_config):
        """Test complete workflow: register agent → submit task → process → complete."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        # Step 1: Register agent
        agent_id = await registry.register_agent(sample_agent_config)
        assert agent_id == sample_agent_config.agent_id

        # Step 2: Submit task
        task = Task(
            task_id=uuid4(),
            capability="test_capability",
            input=TaskInput(data={"test": "data"}),
            priority=TaskPriority.NORMAL,
        )
        task_id = await queue.enqueue_task(task)
        assert task_id == task.task_id

        # Step 3: Agent polls for task
        fetched_task = await queue.get_next_task("test_capability")
        assert fetched_task is not None
        assert fetched_task.task_id == task_id
        assert fetched_task.status == TaskStatus.RUNNING
        assert fetched_task.assigned_agent_id == agent_id

        # Step 4: Agent completes task
        output = {"result": "success"}
        await queue.complete_task(task_id, output, cost=0.05)

        # Step 5: Verify task completed
        result = await queue.get_task_result(task_id)
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.output.data == output
        assert result.actual_cost == 0.05

        # Step 6: Verify agent metrics updated
        agent_state = await registry.get_agent_state(agent_id)
        assert agent_state.tasks_completed == 1
        assert agent_state.total_cost_today == 0.05

    async def test_task_failure_and_retry(self, setup_system, sample_agent_config):
        """Test task failure and retry mechanism."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        # Register agent
        agent_id = await registry.register_agent(sample_agent_config)

        # Submit task with max 3 retries
        task = Task(
            task_id=uuid4(),
            capability="test_capability",
            input=TaskInput(data={"test": "data"}),
            max_retries=3,
        )
        task_id = await queue.enqueue_task(task)

        # First attempt - fail
        fetched_task = await queue.get_next_task("test_capability")
        await queue.fail_task(fetched_task.task_id, "First failure", retry=True)

        # Verify retry count incremented
        retried_task_data = await queue.get_task(task_id)
        assert retried_task_data.retry_count == 1

        # Second attempt - fail again
        fetched_task = await queue.get_next_task("test_capability")
        await queue.fail_task(fetched_task.task_id, "Second failure", retry=True)

        retried_task_data = await queue.get_task(task_id)
        assert retried_task_data.retry_count == 2

        # Third attempt - succeed
        fetched_task = await queue.get_next_task("test_capability")
        await queue.complete_task(fetched_task.task_id, {"result": "success"}, 0.01)

        # Verify completion
        result = await queue.get_task_result(task_id)
        assert result.status == TaskStatus.COMPLETED

        # Verify agent stats
        agent_state = await registry.get_agent_state(agent_id)
        assert agent_state.tasks_completed == 1

    async def test_multiple_agents_load_balancing(self, setup_system):
        """Test load balancing across multiple agents."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        # Register multiple agents with same capability
        agent_configs = []
        for i in range(3):
            config = AgentConfig(
                agent_id=uuid4(),
                name=f"Agent {i}",
                capabilities=[
                    AgentCapability(
                        name="shared_capability",
                        description="Shared capability",
                        estimated_cost_per_call=0.01,
                    )
                ],
                cost_limit_daily=10.0,
                cost_limit_monthly=100.0,
            )
            await registry.register_agent(config)
            agent_configs.append(config)

        # Submit multiple tasks
        task_ids = []
        for i in range(5):
            task = Task(
                task_id=uuid4(),
                capability="shared_capability",
                input=TaskInput(data={"task_num": i}),
            )
            task_id = await queue.enqueue_task(task)
            task_ids.append(task_id)

        # Process tasks (should distribute across agents)
        processed_agents = []
        for _ in range(5):
            fetched_task = await queue.get_next_task("shared_capability")
            if fetched_task:
                processed_agents.append(fetched_task.assigned_agent_id)
                await queue.complete_task(fetched_task.task_id, {"result": "done"}, 0.01)

        # Verify tasks were distributed (not all to same agent)
        assert len(set(processed_agents)) >= 2, "Tasks should be distributed across multiple agents"

    async def test_queue_isolation_by_capability(self, setup_system):
        """Test that different capabilities have isolated queues."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        # Register agents with different capabilities
        agent_a = AgentConfig(
            agent_id=uuid4(),
            name="Agent A",
            capabilities=[
                AgentCapability(
                    name="capability_a",
                    description="Capability A",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )
        agent_b = AgentConfig(
            agent_id=uuid4(),
            name="Agent B",
            capabilities=[
                AgentCapability(
                    name="capability_b",
                    description="Capability B",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )

        await registry.register_agent(agent_a)
        await registry.register_agent(agent_b)

        # Submit tasks to different capabilities
        task_a = Task(
            task_id=uuid4(),
            capability="capability_a",
            input=TaskInput(data={"queue": "a"}),
        )
        task_b = Task(
            task_id=uuid4(),
            capability="capability_b",
            input=TaskInput(data={"queue": "b"}),
        )

        await queue.enqueue_task(task_a)
        await queue.enqueue_task(task_b)

        # Agent A should only get capability_a tasks
        fetched_a = await queue.get_next_task("capability_a")
        assert fetched_a.task_id == task_a.task_id
        assert fetched_a.assigned_agent_id == agent_a.agent_id

        # Agent B should only get capability_b tasks
        fetched_b = await queue.get_next_task("capability_b")
        assert fetched_b.task_id == task_b.task_id
        assert fetched_b.assigned_agent_id == agent_b.agent_id

    async def test_agent_heartbeat_and_recovery(self, setup_system, sample_agent_config):
        """Test agent heartbeat mechanism and error recovery."""
        registry = setup_system["registry"]

        # Register agent
        agent_id = await registry.register_agent(sample_agent_config)

        # Get initial state
        initial_state = await registry.get_agent_state(agent_id)
        assert initial_state.status.value == "active"

        # Mark agent as error
        await registry.update_agent_status(agent_id, "error", "Test error")

        error_state = await registry.get_agent_state(agent_id)
        assert error_state.status.value == "error"

        # Heartbeat should recover agent
        await registry.update_heartbeat(agent_id)

        recovered_state = await registry.get_agent_state(agent_id)
        assert recovered_state.status.value == "active"
        assert recovered_state.error_message is None

    async def test_cost_limit_enforcement(self, setup_system):
        """Test that cost limits are enforced."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        # Register agent with low cost limit
        agent_config = AgentConfig(
            agent_id=uuid4(),
            name="Limited Agent",
            capabilities=[
                AgentCapability(
                    name="expensive_capability",
                    description="Expensive task",
                    estimated_cost_per_call=1.0,
                )
            ],
            cost_limit_daily=5.0,  # Low limit
            cost_limit_monthly=100.0,
        )
        agent_id = await registry.register_agent(agent_config)

        # Process tasks until limit exceeded
        for i in range(3):
            task = Task(
                task_id=uuid4(),
                capability="expensive_capability",
                input=TaskInput(data={}),
            )
            await queue.enqueue_task(task)

            fetched_task = await queue.get_next_task("expensive_capability")
            await queue.complete_task(fetched_task.task_id, {"result": "done"}, cost=2.0)

        # Check cost exceeded
        within_limit = await registry.check_cost_limit(agent_id)
        assert within_limit is False

        agent_state = await registry.get_agent_state(agent_id)
        assert agent_state.total_cost_today >= 5.0

    async def test_dead_letter_queue_handling(self, setup_system, sample_agent_config):
        """Test that permanently failed tasks go to DLQ."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        await registry.register_agent(sample_agent_config)

        # Submit task with 0 retries
        task = Task(
            task_id=uuid4(),
            capability="test_capability",
            input=TaskInput(data={}),
            max_retries=0,
        )
        await queue.enqueue_task(task)

        # Fail task
        fetched_task = await queue.get_next_task("test_capability")
        await queue.fail_task(fetched_task.task_id, "Permanent failure", retry=False)

        # Verify in DLQ
        dlq_depth = await queue.get_dead_letter_queue_depth()
        assert dlq_depth == 1

        # Verify task marked as failed
        failed_task = await queue.get_task(fetched_task.task_id)
        assert failed_task.status == TaskStatus.FAILED


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentOperations:
    """Test concurrent operations and race conditions."""

    @pytest.fixture
    async def setup_system(self, async_redis_client):
        """Set up system for concurrent testing."""
        registry = AgentRegistry()
        router = TaskRouter(registry=registry)
        queue = TaskQueue(router=router, redis_client=async_redis_client)

        yield {
            "registry": registry,
            "router": router,
            "queue": queue,
        }

        await queue.close()

    async def test_concurrent_task_submissions(self, setup_system):
        """Test submitting multiple tasks concurrently."""
        queue = setup_system["queue"]

        # Submit 10 tasks concurrently
        async def submit_task(i):
            task = Task(
                task_id=uuid4(),
                capability="test_capability",
                input=TaskInput(data={"index": i}),
            )
            return await queue.enqueue_task(task)

        task_ids = await asyncio.gather(*[submit_task(i) for i in range(10)])

        assert len(task_ids) == 10
        assert len(set(task_ids)) == 10  # All unique

        # Verify all in queue
        queue_depth = await queue.get_queue_depth("test_capability")
        assert queue_depth == 10

    async def test_concurrent_agent_registrations(self, setup_system):
        """Test registering multiple agents concurrently."""
        registry = setup_system["registry"]

        # Register 5 agents concurrently
        async def register_agent(i):
            config = AgentConfig(
                agent_id=uuid4(),
                name=f"Agent {i}",
                capabilities=[
                    AgentCapability(
                        name="test_cap",
                        description="Test",
                        estimated_cost_per_call=0.01,
                    )
                ],
                cost_limit_daily=10.0,
                cost_limit_monthly=100.0,
            )
            return await registry.register_agent(config)

        agent_ids = await asyncio.gather(*[register_agent(i) for i in range(5)])

        assert len(agent_ids) == 5
        assert len(set(agent_ids)) == 5  # All unique

        # Verify all registered
        agents = await registry.list_agents()
        assert len(agents) == 5
