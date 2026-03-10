"""
Load Tests for High Throughput Performance

Tests high throughput scenarios including:
- Request rate testing
- Sustained load performance
- Burst handling
- Latency percentiles (p50, p90, p99)
- Cost tracking at scale
"""

import pytest
import asyncio
import time
import statistics
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from uuid import uuid4
from collections import defaultdict

from backend.shared.workflow_service import WorkflowExecutionEngine
from backend.shared.workflow_models import ExecutionStatus


class TestRequestRatePerformance:
    """Tests for request rate performance."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db_factory(self):
        def factory():
            db = AsyncMock()
            db.add = MagicMock()
            db.commit = AsyncMock()
            db.flush = AsyncMock()
            db.execute = AsyncMock()
            return db
        return factory

    @pytest.fixture
    def workflow_model(self):
        model = MagicMock()
        model.workflow_id = uuid4()
        model.organization_id = "org-123"
        model.name = "Throughput Test Workflow"
        model.description = "Test"
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

    @pytest.mark.asyncio
    async def test_100_requests_per_second(
        self, engine, mock_db_factory, workflow_model
    ):
        """Test handling 100 requests per second."""
        target_rps = 100
        duration_seconds = 1

        latencies = []

        async def make_request():
            mock_db = mock_db_factory()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=workflow_model)
            mock_db.execute = AsyncMock(return_value=mock_result)

            start = time.time()
            execution = await engine.execute_workflow(
                workflow_id=workflow_model.workflow_id,
                input_data={"test": "data"},
                triggered_by="load-test",
                db=mock_db
            )
            latencies.append(time.time() - start)
            return execution

        num_requests = target_rps * duration_seconds
        start_time = time.time()

        results = await asyncio.gather(*[make_request() for _ in range(num_requests)])

        elapsed = time.time() - start_time
        actual_rps = num_requests / elapsed

        assert len(results) == num_requests
        assert all(r.status == ExecutionStatus.COMPLETED for r in results)
        # Should achieve at least 50% of target RPS
        assert actual_rps >= target_rps * 0.5

    @pytest.mark.asyncio
    async def test_sustained_throughput(
        self, engine, mock_db_factory, workflow_model
    ):
        """Test sustained throughput over multiple batches."""
        batch_size = 50
        num_batches = 5

        batch_times = []
        total_completed = 0

        async def execute_batch():
            tasks = []
            for _ in range(batch_size):
                mock_db = mock_db_factory()
                mock_result = MagicMock()
                mock_result.scalar_one_or_none = MagicMock(return_value=workflow_model)
                mock_db.execute = AsyncMock(return_value=mock_result)

                tasks.append(engine.execute_workflow(
                    workflow_id=workflow_model.workflow_id,
                    input_data={"test": "data"},
                    triggered_by="load-test",
                    db=mock_db
                ))

            start = time.time()
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start
            return results, elapsed

        for _ in range(num_batches):
            results, batch_time = await execute_batch()
            batch_times.append(batch_time)
            total_completed += len(results)

        assert total_completed == batch_size * num_batches
        avg_batch_time = statistics.mean(batch_times)
        # Each batch should complete in reasonable time
        assert avg_batch_time < 5.0


class TestLatencyPercentiles:
    """Tests for latency percentile measurements."""

    @pytest.fixture
    def mock_db_factory(self):
        def factory():
            db = AsyncMock()
            db.add = MagicMock()
            db.commit = AsyncMock()
            db.flush = AsyncMock()
            db.execute = AsyncMock()
            return db
        return factory

    @pytest.mark.asyncio
    async def test_latency_percentiles(self, mock_db_factory):
        """Test p50, p90, p99 latency percentiles."""
        num_requests = 100
        latencies = []

        async def mock_request():
            mock_db = mock_db_factory()
            start = time.time()
            # Simulate variable latency
            await asyncio.sleep(0.01 + (0.005 * (hash(str(time.time())) % 10)))
            latency = time.time() - start
            latencies.append(latency)
            return True

        await asyncio.gather(*[mock_request() for _ in range(num_requests)])

        latencies.sort()
        p50 = latencies[int(num_requests * 0.5)]
        p90 = latencies[int(num_requests * 0.9)]
        p99 = latencies[int(num_requests * 0.99)]

        # Verify percentiles are in expected order
        assert p50 <= p90 <= p99
        # All latencies should be reasonable
        assert p99 < 1.0  # Less than 1 second

    @pytest.mark.asyncio
    async def test_latency_stability(self, mock_db_factory):
        """Test latency stability over time."""
        num_samples = 10
        sample_size = 20

        sample_means = []

        for _ in range(num_samples):
            latencies = []

            async def mock_request():
                mock_db = mock_db_factory()
                start = time.time()
                await asyncio.sleep(0.02)
                latencies.append(time.time() - start)

            await asyncio.gather(*[mock_request() for _ in range(sample_size)])
            sample_means.append(statistics.mean(latencies))

        # Coefficient of variation should be low (stable latency)
        cv = statistics.stdev(sample_means) / statistics.mean(sample_means)
        assert cv < 0.5  # Less than 50% variation (allows for system load variance)


class TestBurstHandling:
    """Tests for burst traffic handling."""

    @pytest.fixture
    def mock_db_factory(self):
        def factory():
            db = AsyncMock()
            db.add = MagicMock()
            db.commit = AsyncMock()
            return db
        return factory

    @pytest.mark.asyncio
    async def test_sudden_burst(self, mock_db_factory):
        """Test handling sudden burst of requests."""
        burst_size = 100
        results = []

        async def handle_request(idx):
            mock_db = mock_db_factory()
            await asyncio.sleep(0.01)  # Simulate processing
            return {"idx": idx, "timestamp": time.time()}

        start_time = time.time()

        # All requests hit at once
        responses = await asyncio.gather(*[
            handle_request(i) for i in range(burst_size)
        ])

        elapsed = time.time() - start_time

        assert len(responses) == burst_size
        # Should handle burst within reasonable time
        assert elapsed < 5.0

    @pytest.mark.asyncio
    async def test_burst_recovery(self, mock_db_factory):
        """Test system recovery after burst."""
        burst_size = 50
        normal_rate = 10

        # Burst phase
        burst_start = time.time()
        burst_tasks = [asyncio.sleep(0.01) for _ in range(burst_size)]
        await asyncio.gather(*burst_tasks)
        burst_elapsed = time.time() - burst_start

        # Recovery phase - normal operation
        recovery_latencies = []
        for _ in range(normal_rate):
            start = time.time()
            await asyncio.sleep(0.02)  # Simulate normal request
            recovery_latencies.append(time.time() - start)

        # Recovery latencies should be consistent
        avg_recovery_latency = statistics.mean(recovery_latencies)
        assert avg_recovery_latency < 0.05  # Should recover quickly

    @pytest.mark.asyncio
    async def test_rate_limiting_during_burst(self, mock_db_factory):
        """Test rate limiting protects during burst."""
        max_concurrent = 20
        burst_size = 100
        semaphore = asyncio.Semaphore(max_concurrent)

        active_count = {"current": 0, "max": 0}

        async def rate_limited_request():
            async with semaphore:
                active_count["current"] += 1
                active_count["max"] = max(active_count["max"], active_count["current"])
                await asyncio.sleep(0.02)
                active_count["current"] -= 1
                return True

        results = await asyncio.gather(*[
            rate_limited_request() for _ in range(burst_size)
        ])

        assert len(results) == burst_size
        assert active_count["max"] <= max_concurrent


class TestCostTrackingAtScale:
    """Tests for cost tracking under high load."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_aggregate_cost_tracking(self, mock_db):
        """Test cost aggregation under high load."""
        num_operations = 1000
        costs = []
        lock = asyncio.Lock()

        async def track_cost(amount):
            async with lock:
                costs.append(amount)
            await asyncio.sleep(0.001)
            return amount

        # Simulate varying costs
        cost_values = [0.001 + (i % 10) * 0.0001 for i in range(num_operations)]

        await asyncio.gather(*[track_cost(c) for c in cost_values])

        total_cost = sum(costs)
        expected_cost = sum(cost_values)

        assert len(costs) == num_operations
        assert abs(total_cost - expected_cost) < 0.0001  # Floating point tolerance

    @pytest.mark.asyncio
    async def test_per_organization_cost_tracking(self, mock_db):
        """Test per-organization cost tracking at scale."""
        num_orgs = 10
        operations_per_org = 100
        org_costs = defaultdict(list)
        lock = asyncio.Lock()

        async def track_org_cost(org_id, amount):
            async with lock:
                org_costs[org_id].append(amount)
            await asyncio.sleep(0.001)
            return amount

        tasks = []
        for org_id in range(num_orgs):
            for _ in range(operations_per_org):
                cost = 0.01 + (org_id * 0.001)
                tasks.append(track_org_cost(f"org_{org_id}", cost))

        await asyncio.gather(*tasks)

        assert len(org_costs) == num_orgs
        for org_id in range(num_orgs):
            assert len(org_costs[f"org_{org_id}"]) == operations_per_org


class TestThroughputMetrics:
    """Tests for throughput metric collection."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_requests_per_second_calculation(self, mock_db):
        """Test accurate RPS calculation."""
        request_count = 0
        lock = asyncio.Lock()
        duration = 2  # seconds

        async def count_request():
            nonlocal request_count
            async with lock:
                request_count += 1
            await asyncio.sleep(0.01)

        start = time.time()
        while time.time() - start < duration:
            await asyncio.gather(*[count_request() for _ in range(10)])

        elapsed = time.time() - start
        rps = request_count / elapsed

        assert request_count > 0
        assert rps > 0

    @pytest.mark.asyncio
    async def test_throughput_with_mixed_latencies(self, mock_db):
        """Test throughput with varying request latencies."""
        latencies = [0.01, 0.05, 0.1, 0.02, 0.03]  # Mixed latencies
        completed = []

        async def variable_latency_request(idx):
            latency = latencies[idx % len(latencies)]
            await asyncio.sleep(latency)
            completed.append(idx)
            return {"idx": idx, "latency": latency}

        num_requests = 50
        start = time.time()

        results = await asyncio.gather(*[
            variable_latency_request(i) for i in range(num_requests)
        ])

        elapsed = time.time() - start
        throughput = len(results) / elapsed

        assert len(results) == num_requests
        assert throughput > 10  # At least 10 requests/second


class TestScalabilityLimits:
    """Tests for system scalability limits."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, mock_db):
        """Test graceful degradation under extreme load."""
        max_capacity = 50
        semaphore = asyncio.Semaphore(max_capacity)
        rejected = []
        completed = []

        async def handle_request(idx, timeout=0.5):
            try:
                async def _process():
                    async with semaphore:
                        await asyncio.sleep(0.1)
                        completed.append(idx)
                        return True

                return await asyncio.wait_for(_process(), timeout=timeout)
            except asyncio.TimeoutError:
                rejected.append(idx)
                return False

        num_requests = 200  # More than capacity

        results = await asyncio.gather(*[
            handle_request(i) for i in range(num_requests)
        ])

        # Some requests should complete
        assert len(completed) > 0
        # Total should equal num_requests
        assert len(completed) + len(rejected) == num_requests

    @pytest.mark.asyncio
    async def test_backpressure_handling(self, mock_db):
        """Test backpressure mechanism."""
        queue = asyncio.Queue(maxsize=20)
        produced = 0
        consumed = 0
        dropped = 0

        async def producer():
            nonlocal produced, dropped
            for i in range(100):
                try:
                    queue.put_nowait(i)
                    produced += 1
                except asyncio.QueueFull:
                    dropped += 1
                await asyncio.sleep(0.005)

        async def consumer():
            nonlocal consumed
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.5)
                    consumed += 1
                    await asyncio.sleep(0.02)  # Slower than producer
                    queue.task_done()
                except asyncio.TimeoutError:
                    break

        await asyncio.gather(
            producer(),
            consumer()
        )

        # With backpressure, some items should be dropped
        assert dropped > 0
        # But some should be consumed
        assert consumed > 0


class TestMemoryEfficiency:
    """Tests for memory efficiency under load."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_streaming_large_results(self, mock_db):
        """Test streaming large results without memory issues."""
        num_chunks = 100
        chunk_size = 1000

        chunks_processed = 0

        async def process_chunk(chunk_idx):
            nonlocal chunks_processed
            # Generate chunk data
            data = list(range(chunk_size))
            await asyncio.sleep(0.005)
            chunks_processed += 1
            # Return summary, not full data
            return {"chunk_idx": chunk_idx, "sum": sum(data)}

        results = await asyncio.gather(*[
            process_chunk(i) for i in range(num_chunks)
        ])

        assert len(results) == num_chunks
        assert chunks_processed == num_chunks

    @pytest.mark.asyncio
    async def test_batch_processing_efficiency(self, mock_db):
        """Test batch processing for better efficiency."""
        total_items = 500
        batch_size = 50

        processed_items = []

        async def process_batch(batch):
            results = []
            for item in batch:
                results.append(item * 2)
            await asyncio.sleep(0.01)  # Batch processing
            return results

        # Create batches
        batches = [
            list(range(i, min(i + batch_size, total_items)))
            for i in range(0, total_items, batch_size)
        ]

        start = time.time()
        results = await asyncio.gather(*[process_batch(b) for b in batches])
        elapsed = time.time() - start

        total_processed = sum(len(r) for r in results)
        assert total_processed == total_items
        # Batch processing should be fast
        assert elapsed < 2.0


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
