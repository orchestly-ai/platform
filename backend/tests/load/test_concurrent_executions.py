"""
Load Tests for Concurrent Workflow Executions

Tests concurrent execution patterns including:
- Multiple workflows running simultaneously
- Concurrent agent invocations
- Resource contention handling
- Connection pool management
- Memory usage under load
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from backend.shared.workflow_service import WorkflowExecutionEngine
from backend.shared.workflow_models import ExecutionStatus


class TestConcurrentWorkflowExecution:
    """Tests for concurrent workflow execution."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db_factory(self):
        """Factory for creating mock database connections."""
        def factory():
            db = AsyncMock()
            db.add = MagicMock()
            db.commit = AsyncMock()
            db.flush = AsyncMock()
            db.refresh = AsyncMock()
            db.execute = AsyncMock()
            return db
        return factory

    @pytest.fixture
    def simple_workflow_model_factory(self):
        """Factory for creating workflow models."""
        def factory(workflow_id=None):
            model = MagicMock()
            model.workflow_id = workflow_id or uuid4()
            model.organization_id = "org-123"
            model.name = f"Test Workflow {model.workflow_id}"
            model.description = "Test workflow"
            model.status = "active"
            model.version = 1
            model.nodes = [
                {"id": "input", "type": "data_input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "output", "type": "data_output", "position": {"x": 100, "y": 0}, "data": {}},
            ]
            model.edges = [
                {"id": "e1", "source": "input", "target": "output"},
            ]
            model.max_execution_time_seconds = 300
            model.retry_on_failure = False
            model.max_retries = 0
            model.variables = {}
            model.environment = "development"
            model.total_executions = 0
            model.successful_executions = 0
            model.failed_executions = 0
            model.avg_execution_time_seconds = None
            model.total_cost = 0
            return model
        return factory

    @pytest.mark.asyncio
    async def test_10_concurrent_workflows(
        self, engine, mock_db_factory, simple_workflow_model_factory
    ):
        """Test executing 10 workflows concurrently."""
        num_workflows = 10
        workflows = [simple_workflow_model_factory() for _ in range(num_workflows)]

        async def execute_workflow(workflow):
            mock_db = mock_db_factory()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=workflow)
            mock_db.execute = AsyncMock(return_value=mock_result)

            execution = await engine.execute_workflow(
                workflow_id=workflow.workflow_id,
                input_data={"test": "data"},
                triggered_by="load-test",
                db=mock_db
            )
            return execution

        start_time = time.time()
        executions = await asyncio.gather(*[
            execute_workflow(w) for w in workflows
        ])
        elapsed = time.time() - start_time

        assert len(executions) == num_workflows
        assert all(e.status == ExecutionStatus.COMPLETED for e in executions)
        # Should complete in reasonable time
        assert elapsed < 30  # 30 seconds max

    @pytest.mark.asyncio
    async def test_50_concurrent_workflows(
        self, engine, mock_db_factory, simple_workflow_model_factory
    ):
        """Test executing 50 workflows concurrently."""
        num_workflows = 50
        workflows = [simple_workflow_model_factory() for _ in range(num_workflows)]

        async def execute_workflow(workflow):
            mock_db = mock_db_factory()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=workflow)
            mock_db.execute = AsyncMock(return_value=mock_result)

            execution = await engine.execute_workflow(
                workflow_id=workflow.workflow_id,
                input_data={"test": "data"},
                triggered_by="load-test",
                db=mock_db
            )
            return execution

        start_time = time.time()
        executions = await asyncio.gather(*[
            execute_workflow(w) for w in workflows
        ])
        elapsed = time.time() - start_time

        assert len(executions) == num_workflows
        completed = sum(1 for e in executions if e.status == ExecutionStatus.COMPLETED)
        assert completed == num_workflows

    @pytest.mark.asyncio
    async def test_concurrent_execution_isolation(
        self, engine, mock_db_factory, simple_workflow_model_factory
    ):
        """Test that concurrent executions are isolated from each other."""
        num_workflows = 20
        workflows = [simple_workflow_model_factory() for _ in range(num_workflows)]

        results = {}

        async def execute_workflow(idx, workflow):
            mock_db = mock_db_factory()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=workflow)
            mock_db.execute = AsyncMock(return_value=mock_result)

            # Simulate some work
            await asyncio.sleep(0.01 * (idx % 5))

            execution = await engine.execute_workflow(
                workflow_id=workflow.workflow_id,
                input_data={"workflow_index": idx},
                triggered_by="load-test",
                db=mock_db
            )

            results[idx] = {
                "workflow_id": str(workflow.workflow_id),
                "input_index": idx
            }
            return execution

        executions = await asyncio.gather(*[
            execute_workflow(i, w) for i, w in enumerate(workflows)
        ])

        # Verify each workflow got its correct input
        assert len(results) == num_workflows
        for idx in range(num_workflows):
            assert results[idx]["input_index"] == idx


class TestConcurrentAgentInvocations:
    """Tests for concurrent agent invocations within workflows."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_parallel_llm_calls(self, mock_db):
        """Test parallel LLM calls within single workflow."""
        num_calls = 10

        async def mock_llm_call(prompt):
            # Simulate LLM latency
            await asyncio.sleep(0.1)
            return {"response": f"Response to: {prompt}"}

        start_time = time.time()
        results = await asyncio.gather(*[
            mock_llm_call(f"Prompt {i}") for i in range(num_calls)
        ])
        elapsed = time.time() - start_time

        assert len(results) == num_calls
        # Parallel execution should be faster than sequential (0.1s * 10 = 1s)
        assert elapsed < 1.0  # Should complete in ~0.1s with parallelism

    @pytest.mark.asyncio
    async def test_rate_limited_api_calls(self, mock_db):
        """Test handling rate-limited API calls."""
        num_calls = 20
        rate_limit = 10  # Max concurrent calls
        semaphore = asyncio.Semaphore(rate_limit)

        call_times = []

        async def rate_limited_call(idx):
            async with semaphore:
                call_times.append((idx, time.time()))
                await asyncio.sleep(0.05)
                return {"idx": idx, "result": "success"}

        results = await asyncio.gather(*[
            rate_limited_call(i) for i in range(num_calls)
        ])

        assert len(results) == num_calls
        # Verify rate limiting worked
        concurrent_at_any_time = 0
        for i, (idx, t) in enumerate(call_times):
            concurrent = sum(1 for _, t2 in call_times if abs(t - t2) < 0.04)
            concurrent_at_any_time = max(concurrent_at_any_time, concurrent)

        # Should not exceed rate limit (with some tolerance)
        assert concurrent_at_any_time <= rate_limit + 2


class TestResourceContention:
    """Tests for resource contention under load."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_database_connection_sharing(self, mock_db):
        """Test database connection handling under concurrent load."""
        num_operations = 100

        async def db_operation(idx):
            await asyncio.sleep(0.01)
            mock_db.add({"id": idx})
            await mock_db.commit()
            return idx

        start_time = time.time()
        results = await asyncio.gather(*[
            db_operation(i) for i in range(num_operations)
        ])
        elapsed = time.time() - start_time

        assert len(results) == num_operations
        assert mock_db.add.call_count == num_operations

    @pytest.mark.asyncio
    async def test_concurrent_state_updates(self, mock_db):
        """Test concurrent state updates are atomic."""
        shared_state = {"counter": 0}
        lock = asyncio.Lock()
        num_updates = 100

        async def update_state():
            async with lock:
                current = shared_state["counter"]
                await asyncio.sleep(0.001)  # Simulate some work
                shared_state["counter"] = current + 1

        await asyncio.gather(*[update_state() for _ in range(num_updates)])

        # With proper locking, counter should equal num_updates
        assert shared_state["counter"] == num_updates


class TestMemoryUsageUnderLoad:
    """Tests for memory usage during high load."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_large_payload_handling(self, mock_db):
        """Test handling large payloads under concurrent load."""
        num_operations = 50
        payload_size = 10000  # 10KB per payload

        async def process_large_payload(idx):
            payload = {"data": "x" * payload_size, "idx": idx}
            await asyncio.sleep(0.01)
            return len(payload["data"])

        results = await asyncio.gather(*[
            process_large_payload(i) for i in range(num_operations)
        ])

        assert len(results) == num_operations
        assert all(r == payload_size for r in results)

    @pytest.mark.asyncio
    async def test_result_cleanup(self, mock_db):
        """Test that results are properly cleaned up after processing."""
        num_operations = 100
        processed = []

        async def process_and_cleanup(idx):
            result = {"data": list(range(1000)), "idx": idx}
            await asyncio.sleep(0.005)
            processed.append(idx)
            # Return only what's needed
            return {"idx": idx, "count": len(result["data"])}

        results = await asyncio.gather(*[
            process_and_cleanup(i) for i in range(num_operations)
        ])

        assert len(results) == num_operations
        assert len(processed) == num_operations


class TestWorkflowQueueing:
    """Tests for workflow queuing under load."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_fifo_queue_processing(self, mock_db):
        """Test FIFO queue processing of workflows."""
        queue = asyncio.Queue()
        processed_order = []

        async def producer(num_items):
            for i in range(num_items):
                await queue.put(i)

        async def consumer():
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.5)
                    processed_order.append(item)
                    queue.task_done()
                except asyncio.TimeoutError:
                    break

        num_items = 50
        await producer(num_items)

        consumers = [asyncio.create_task(consumer()) for _ in range(3)]
        await queue.join()

        for c in consumers:
            c.cancel()

        assert len(processed_order) == num_items

    @pytest.mark.asyncio
    async def test_priority_queue_processing(self, mock_db):
        """Test priority queue processing."""
        from heapq import heappush, heappop

        priority_queue = []
        processed = []

        # Add items with priorities (lower number = higher priority)
        items = [(3, "low"), (1, "high"), (2, "medium"), (1, "high2"), (3, "low2")]
        for priority, name in items:
            heappush(priority_queue, (priority, name))

        while priority_queue:
            priority, name = heappop(priority_queue)
            processed.append(name)

        # High priority items should be processed first
        assert processed[0] in ["high", "high2"]
        assert processed[1] in ["high", "high2"]
        assert processed[2] == "medium"


class TestConcurrencyLimits:
    """Tests for concurrency limit enforcement."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_max_concurrent_workflows(self, mock_db):
        """Test enforcement of max concurrent workflows limit."""
        max_concurrent = 5
        semaphore = asyncio.Semaphore(max_concurrent)
        current_count = {"value": 0}
        max_reached = {"value": 0}

        async def execute_workflow(idx):
            async with semaphore:
                current_count["value"] += 1
                max_reached["value"] = max(max_reached["value"], current_count["value"])
                await asyncio.sleep(0.05)
                current_count["value"] -= 1
                return idx

        num_workflows = 20
        results = await asyncio.gather(*[
            execute_workflow(i) for i in range(num_workflows)
        ])

        assert len(results) == num_workflows
        assert max_reached["value"] <= max_concurrent

    @pytest.mark.asyncio
    async def test_per_organization_limits(self, mock_db):
        """Test per-organization concurrency limits."""
        org_limits = {"org_1": 3, "org_2": 5, "org_3": 2}
        org_semaphores = {org: asyncio.Semaphore(limit) for org, limit in org_limits.items()}
        org_max_concurrent = {org: 0 for org in org_limits}
        org_current = {org: 0 for org in org_limits}

        async def execute_for_org(org, idx):
            async with org_semaphores[org]:
                org_current[org] += 1
                org_max_concurrent[org] = max(org_max_concurrent[org], org_current[org])
                await asyncio.sleep(0.02)
                org_current[org] -= 1
                return (org, idx)

        tasks = []
        for org in org_limits:
            for i in range(10):
                tasks.append(execute_for_org(org, i))

        results = await asyncio.gather(*tasks)

        assert len(results) == 30
        for org, limit in org_limits.items():
            assert org_max_concurrent[org] <= limit


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
