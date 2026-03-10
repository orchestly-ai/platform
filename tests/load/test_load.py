"""Load tests for system scalability.

NOTE: These load tests require async Redis and have infrastructure dependencies.
They are skipped by default. See backend/tests/ for working tests.
"""
import asyncio
import pytest
import time
from uuid import uuid4
from statistics import mean, median, stdev

# Skip all tests in this module - requires async Redis and infrastructure
pytestmark = pytest.mark.skip(reason="Load tests require infrastructure - see backend/tests/ for working tests")

from backend.shared.models import (
    AgentConfig,
    AgentCapability,
    Task,
    TaskInput,
    TaskPriority,
)
from backend.orchestrator.registry import AgentRegistry
from backend.orchestrator.queue import TaskQueue
from backend.orchestrator.router import TaskRouter


@pytest.mark.slow
@pytest.mark.asyncio
class TestLoadScalability:
    """Load tests for system scalability."""

    @pytest.fixture
    async def setup_system(self, async_redis_client):
        """Set up system for load testing."""
        registry = AgentRegistry()
        router = TaskRouter(registry=registry)
        queue = TaskQueue(router=router, redis_client=async_redis_client)

        yield {
            "registry": registry,
            "router": router,
            "queue": queue,
        }

        await queue.close()

    async def test_1000_concurrent_tasks(self, setup_system):
        """Test processing 1000 concurrent tasks."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        # Register 10 agents
        agent_ids = []
        for i in range(10):
            config = AgentConfig(
                agent_id=uuid4(),
                name=f"Load Agent {i}",
                capabilities=[
                    AgentCapability(
                        name="load_test_capability",
                        description="Load testing",
                        estimated_cost_per_call=0.001,
                    )
                ],
                cost_limit_daily=1000.0,
                cost_limit_monthly=10000.0,
                max_concurrent_tasks=100,
            )
            agent_id = await registry.register_agent(config)
            agent_ids.append(agent_id)

        print(f"\n✓ Registered {len(agent_ids)} agents")

        # Submit 1000 tasks
        start_time = time.time()
        task_ids = []

        async def submit_task(i):
            task = Task(
                task_id=uuid4(),
                capability="load_test_capability",
                input=TaskInput(data={"task_num": i}),
                priority=TaskPriority.NORMAL,
            )
            return await queue.enqueue_task(task)

        # Submit in batches of 100 to avoid overwhelming
        for batch_start in range(0, 1000, 100):
            batch_ids = await asyncio.gather(*[
                submit_task(i) for i in range(batch_start, batch_start + 100)
            ])
            task_ids.extend(batch_ids)

        submission_time = time.time() - start_time
        print(f"✓ Submitted 1000 tasks in {submission_time:.2f}s ({1000/submission_time:.1f} tasks/s)")

        # Process tasks
        start_time = time.time()
        latencies = []

        async def process_task():
            task_start = time.time()
            fetched_task = await queue.get_next_task("load_test_capability")
            if fetched_task:
                await queue.complete_task(
                    fetched_task.task_id,
                    {"result": "completed"},
                    cost=0.001
                )
                latency = time.time() - task_start
                latencies.append(latency)
                return True
            return False

        # Process in waves
        processed_count = 0
        while processed_count < 1000:
            results = await asyncio.gather(*[process_task() for _ in range(50)])
            processed_count += sum(results)
            if not any(results):
                break  # No more tasks

        processing_time = time.time() - start_time
        print(f"✓ Processed {processed_count} tasks in {processing_time:.2f}s ({processed_count/processing_time:.1f} tasks/s)")

        # Performance assertions
        assert processed_count == 1000, f"Expected 1000 tasks, processed {processed_count}"

        # Calculate statistics
        if latencies:
            avg_latency = mean(latencies)
            median_latency = median(latencies)
            max_latency = max(latencies)
            latency_stdev = stdev(latencies) if len(latencies) > 1 else 0

            print(f"\nLatency Statistics:")
            print(f"  Average: {avg_latency*1000:.2f}ms")
            print(f"  Median:  {median_latency*1000:.2f}ms")
            print(f"  Max:     {max_latency*1000:.2f}ms")
            print(f"  StdDev:  {latency_stdev*1000:.2f}ms")

            # Performance targets
            assert avg_latency < 0.5, f"Average latency too high: {avg_latency:.3f}s"
            assert median_latency < 0.3, f"Median latency too high: {median_latency:.3f}s"

        # Verify agent stats
        for agent_id in agent_ids:
            state = await registry.get_agent_state(agent_id)
            print(f"  Agent {state.agent_id}: {state.tasks_completed} tasks")

    async def test_100_agents_concurrent_registration(self, setup_system):
        """Test registering 100 agents concurrently."""
        registry = setup_system["registry"]

        start_time = time.time()

        async def register_agent(i):
            config = AgentConfig(
                agent_id=uuid4(),
                name=f"Agent {i}",
                capabilities=[
                    AgentCapability(
                        name=f"capability_{i % 10}",  # 10 different capabilities
                        description=f"Capability {i % 10}",
                        estimated_cost_per_call=0.01,
                    )
                ],
                cost_limit_daily=10.0,
                cost_limit_monthly=100.0,
            )
            return await registry.register_agent(config)

        # Register in batches
        agent_ids = []
        for batch_start in range(0, 100, 20):
            batch_ids = await asyncio.gather(*[
                register_agent(i) for i in range(batch_start, batch_start + 20)
            ])
            agent_ids.extend(batch_ids)

        registration_time = time.time() - start_time

        print(f"\n✓ Registered 100 agents in {registration_time:.2f}s ({100/registration_time:.1f} agents/s)")

        # Verify all registered
        all_agents = await registry.list_agents()
        assert len(all_agents) == 100

        # Verify capability index
        for i in range(10):
            agents_with_cap = await registry.find_agents_by_capability(f"capability_{i}")
            assert len(agents_with_cap) == 10  # 10 agents per capability

    async def test_queue_depth_monitoring(self, setup_system):
        """Test monitoring queue depths under load."""
        queue = setup_system["queue"]

        # Submit tasks to multiple capabilities
        capabilities = [f"capability_{i}" for i in range(5)]

        for cap_idx, capability in enumerate(capabilities):
            # Submit different numbers to each capability
            task_count = (cap_idx + 1) * 20  # 20, 40, 60, 80, 100

            for i in range(task_count):
                task = Task(
                    task_id=uuid4(),
                    capability=capability,
                    input=TaskInput(data={}),
                )
                await queue.enqueue_task(task)

        # Get all queue depths
        depths = await queue.get_all_queue_depths()

        print(f"\nQueue Depths:")
        for cap, depth in depths.items():
            print(f"  {cap}: {depth}")

        # Verify depths
        assert depths["capability_0"] == 20
        assert depths["capability_1"] == 40
        assert depths["capability_2"] == 60
        assert depths["capability_3"] == 80
        assert depths["capability_4"] == 100

    async def test_high_throughput_submission(self, setup_system):
        """Test high-throughput task submission."""
        queue = setup_system["queue"]

        num_tasks = 5000
        start_time = time.time()

        # Submit tasks as fast as possible
        async def rapid_submit(i):
            task = Task(
                task_id=uuid4(),
                capability="throughput_test",
                input=TaskInput(data={"index": i}),
            )
            return await queue.enqueue_task(task)

        # Submit in large batches
        batch_size = 500
        for batch_start in range(0, num_tasks, batch_size):
            await asyncio.gather(*[
                rapid_submit(i) for i in range(batch_start, min(batch_start + batch_size, num_tasks))
            ])

        elapsed_time = time.time() - start_time
        throughput = num_tasks / elapsed_time

        print(f"\n✓ Submitted {num_tasks} tasks in {elapsed_time:.2f}s")
        print(f"  Throughput: {throughput:.1f} tasks/s")

        # Performance target: >1000 tasks/second submission rate
        assert throughput > 1000, f"Throughput too low: {throughput:.1f} tasks/s"

        # Verify queue depth
        depth = await queue.get_queue_depth("throughput_test")
        assert depth == num_tasks

    async def test_memory_usage_stability(self, setup_system):
        """Test memory stability under sustained load."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        # Register agent
        config = AgentConfig(
            agent_id=uuid4(),
            name="Memory Test Agent",
            capabilities=[
                AgentCapability(
                    name="memory_test",
                    description="Memory testing",
                    estimated_cost_per_call=0.001,
                )
            ],
            cost_limit_daily=1000.0,
            cost_limit_monthly=10000.0,
        )
        agent_id = await registry.register_agent(config)

        # Submit and process 1000 tasks in cycles
        for cycle in range(10):
            # Submit 100 tasks
            for i in range(100):
                task = Task(
                    task_id=uuid4(),
                    capability="memory_test",
                    input=TaskInput(data={"cycle": cycle, "task": i}),
                )
                await queue.enqueue_task(task)

            # Process all tasks
            for _ in range(100):
                fetched_task = await queue.get_next_task("memory_test")
                if fetched_task:
                    await queue.complete_task(
                        fetched_task.task_id,
                        {"result": "done"},
                        cost=0.001
                    )

        # Verify agent processed all tasks
        state = await registry.get_agent_state(agent_id)
        assert state.tasks_completed == 1000

        print(f"\n✓ Processed 1000 tasks in 10 cycles")
        print(f"  Agent cost: ${state.total_cost_today:.4f}")


@pytest.mark.slow
@pytest.mark.asyncio
class TestStressScenarios:
    """Stress tests for edge cases."""

    @pytest.fixture
    async def setup_system(self, async_redis_client):
        """Set up system for stress testing."""
        registry = AgentRegistry()
        router = TaskRouter(registry=registry)
        queue = TaskQueue(router=router, redis_client=async_redis_client)

        yield {
            "registry": registry,
            "router": router,
            "queue": queue,
        }

        await queue.close()

    async def test_rapid_agent_churn(self, setup_system):
        """Test rapid agent registration/deregistration."""
        registry = setup_system["registry"]

        for iteration in range(50):
            # Register 10 agents
            agent_ids = []
            for i in range(10):
                config = AgentConfig(
                    agent_id=uuid4(),
                    name=f"Churn Agent {iteration}-{i}",
                    capabilities=[
                        AgentCapability(
                            name="churn_test",
                            description="Churn test",
                            estimated_cost_per_call=0.01,
                        )
                    ],
                    cost_limit_daily=10.0,
                    cost_limit_monthly=100.0,
                )
                agent_id = await registry.register_agent(config)
                agent_ids.append(agent_id)

            # Deregister all
            for agent_id in agent_ids:
                await registry.deregister_agent(agent_id)

        # Verify clean state
        agents = await registry.list_agents()
        assert len(agents) == 0

        print(f"\n✓ Completed 50 churn cycles (500 registrations/deregistrations)")

    async def test_task_failure_cascade(self, setup_system):
        """Test handling of cascading task failures."""
        registry = setup_system["registry"]
        queue = setup_system["queue"]

        # Register agent
        config = AgentConfig(
            agent_id=uuid4(),
            name="Failure Test Agent",
            capabilities=[
                AgentCapability(
                    name="failure_test",
                    description="Failure testing",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=100.0,
            cost_limit_monthly=1000.0,
        )
        await registry.register_agent(config)

        # Submit 100 tasks
        for i in range(100):
            task = Task(
                task_id=uuid4(),
                capability="failure_test",
                input=TaskInput(data={}),
                max_retries=0,  # No retries
            )
            await queue.enqueue_task(task)

        # Fail all tasks
        for _ in range(100):
            fetched_task = await queue.get_next_task("failure_test")
            if fetched_task:
                await queue.fail_task(fetched_task.task_id, "Simulated failure", retry=False)

        # Verify DLQ has all failed tasks
        dlq_depth = await queue.get_dead_letter_queue_depth()
        assert dlq_depth == 100

        print(f"\n✓ Handled 100 cascading failures")
        print(f"  DLQ depth: {dlq_depth}")


if __name__ == "__main__":
    """Run load tests standalone."""
    pytest.main([__file__, "-v", "-s", "-m", "slow"])
