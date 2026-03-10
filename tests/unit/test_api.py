"""Unit tests for FastAPI endpoints.

NOTE: These tests are outdated and need to be updated to match the current
API endpoints. The backend/tests/ directory contains the up-to-date tests.
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.skip(reason="Tests outdated - API has changed. See backend/tests/ for current tests")

from backend.api.main import app
from backend.shared.models import (
    AgentConfig,
    AgentCapability,
    AgentStatus,
    Task,
    TaskInput,
    TaskPriority,
    TaskStatus,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_registry():
    """Mock agent registry."""
    registry = MagicMock()
    registry.register_agent = AsyncMock(return_value=uuid4())
    registry.deregister_agent = AsyncMock()
    registry.get_agent = AsyncMock()
    registry.list_agents = AsyncMock(return_value=[])
    registry.update_heartbeat = AsyncMock()
    return registry


@pytest.fixture
def mock_queue():
    """Mock task queue."""
    queue = MagicMock()
    queue.enqueue_task = AsyncMock(return_value=uuid4())
    queue.get_next_task = AsyncMock(return_value=None)
    queue.complete_task = AsyncMock()
    queue.fail_task = AsyncMock()
    queue.get_task = AsyncMock(return_value=None)
    return queue


@pytest.mark.unit
class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_success(self, client):
        """Test health check returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.unit
class TestAgentEndpoints:
    """Tests for agent management endpoints."""

    @patch("backend.api.main.get_registry")
    def test_register_agent_success(self, mock_get_registry, client):
        """Test agent registration endpoint."""
        agent_id = uuid4()
        mock_registry = MagicMock()
        mock_registry.register_agent = AsyncMock(return_value=agent_id)
        mock_get_registry.return_value = mock_registry

        agent_config = {
            "agent_id": str(agent_id),
            "name": "Test Agent",
            "capabilities": [
                {
                    "name": "test_capability",
                    "description": "Test",
                    "estimated_cost_per_call": 0.01,
                }
            ],
            "cost_limit_daily": 10.0,
            "cost_limit_monthly": 100.0,
        }

        response = client.post("/api/v1/agents", json=agent_config)

        assert response.status_code == 201
        assert "agent_id" in response.json()

    @patch("backend.api.main.get_registry")
    def test_register_agent_missing_fields(self, mock_get_registry, client):
        """Test registration with missing required fields."""
        response = client.post("/api/v1/agents", json={"name": "Test"})

        assert response.status_code == 422  # Validation error

    @patch("backend.api.main.get_registry")
    def test_list_agents(self, mock_get_registry, client):
        """Test listing all agents."""
        mock_registry = MagicMock()
        agent1 = AgentConfig(
            agent_id=uuid4(),
            name="Agent 1",
            capabilities=[
                AgentCapability(
                    name="test",
                    description="Test",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )
        mock_registry.list_agents = AsyncMock(return_value=[agent1])
        mock_get_registry.return_value = mock_registry

        response = client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    @patch("backend.api.main.get_registry")
    def test_get_agent_by_id(self, mock_get_registry, client):
        """Test getting specific agent."""
        agent_id = uuid4()
        mock_registry = MagicMock()
        agent = AgentConfig(
            agent_id=agent_id,
            name="Test Agent",
            capabilities=[
                AgentCapability(
                    name="test",
                    description="Test",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )
        mock_registry.get_agent = AsyncMock(return_value=agent)
        mock_get_registry.return_value = mock_registry

        response = client.get(f"/api/v1/agents/{agent_id}")

        assert response.status_code == 200
        assert response.json()["name"] == "Test Agent"

    @patch("backend.api.main.get_registry")
    def test_get_nonexistent_agent(self, mock_get_registry, client):
        """Test getting non-existent agent returns 404."""
        mock_registry = MagicMock()
        mock_registry.get_agent = AsyncMock(return_value=None)
        mock_get_registry.return_value = mock_registry

        response = client.get(f"/api/v1/agents/{uuid4()}")

        assert response.status_code == 404

    @patch("backend.api.main.get_registry")
    def test_deregister_agent(self, mock_get_registry, client):
        """Test agent deregistration."""
        agent_id = uuid4()
        mock_registry = MagicMock()
        mock_registry.deregister_agent = AsyncMock()
        mock_get_registry.return_value = mock_registry

        response = client.delete(f"/api/v1/agents/{agent_id}")

        assert response.status_code == 200
        mock_registry.deregister_agent.assert_called_once()

    @patch("backend.api.main.get_registry")
    def test_agent_heartbeat(self, mock_get_registry, client):
        """Test agent heartbeat endpoint."""
        agent_id = uuid4()
        mock_registry = MagicMock()
        mock_registry.update_heartbeat = AsyncMock()
        mock_get_registry.return_value = mock_registry

        response = client.post(f"/api/v1/agents/{agent_id}/heartbeat")

        assert response.status_code == 200
        mock_registry.update_heartbeat.assert_called_once_with(agent_id)


@pytest.mark.unit
class TestTaskEndpoints:
    """Tests for task management endpoints."""

    @patch("backend.api.main.get_queue")
    def test_submit_task_success(self, mock_get_queue, client):
        """Test task submission."""
        task_id = uuid4()
        mock_queue = MagicMock()
        mock_queue.enqueue_task = AsyncMock(return_value=task_id)
        mock_get_queue.return_value = mock_queue

        task_data = {
            "task_id": str(task_id),
            "capability": "test_capability",
            "input": {"data": {"test": "value"}},
            "priority": "normal",
        }

        response = client.post("/api/v1/tasks", json=task_data)

        assert response.status_code == 201
        assert "task_id" in response.json()

    @patch("backend.api.main.get_queue")
    def test_submit_task_invalid_data(self, mock_get_queue, client):
        """Test task submission with invalid data."""
        response = client.post("/api/v1/tasks", json={"capability": ""})

        assert response.status_code == 422  # Validation error

    @patch("backend.api.main.get_queue")
    def test_get_task_status(self, mock_get_queue, client):
        """Test getting task status."""
        task_id = uuid4()
        mock_queue = MagicMock()
        task = Task(
            task_id=task_id,
            capability="test",
            input=TaskInput(data={}),
            status=TaskStatus.COMPLETED,
        )
        mock_queue.get_task = AsyncMock(return_value=task)
        mock_get_queue.return_value = mock_queue

        response = client.get(f"/api/v1/tasks/{task_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @patch("backend.api.main.get_queue")
    def test_get_task_result(self, mock_get_queue, client):
        """Test getting task result."""
        task_id = uuid4()
        mock_queue = MagicMock()
        task = Task(
            task_id=task_id,
            capability="test",
            input=TaskInput(data={}),
            status=TaskStatus.COMPLETED,
        )
        mock_queue.get_task_result = AsyncMock(return_value=task)
        mock_get_queue.return_value = mock_queue

        response = client.get(f"/api/v1/tasks/{task_id}/result")

        assert response.status_code == 200

    @patch("backend.api.main.get_queue")
    def test_get_next_task_for_agent(self, mock_get_queue, client):
        """Test polling for next task."""
        agent_id = uuid4()
        task_id = uuid4()
        mock_queue = MagicMock()
        task = Task(
            task_id=task_id,
            capability="test",
            input=TaskInput(data={}),
            assigned_agent_id=agent_id,
        )
        mock_queue.get_next_task = AsyncMock(return_value=task)
        mock_get_queue.return_value = mock_queue

        response = client.get(
            f"/api/v1/agents/{agent_id}/tasks/next",
            params={"capability": "test"}
        )

        assert response.status_code == 200
        assert "task_id" in response.json()

    @patch("backend.api.main.get_queue")
    def test_get_next_task_empty_queue(self, mock_get_queue, client):
        """Test polling when no tasks available."""
        mock_queue = MagicMock()
        mock_queue.get_next_task = AsyncMock(return_value=None)
        mock_get_queue.return_value = mock_queue

        response = client.get(
            f"/api/v1/agents/{uuid4()}/tasks/next",
            params={"capability": "test"}
        )

        assert response.status_code == 204  # No content

    @patch("backend.api.main.get_queue")
    def test_submit_task_result(self, mock_get_queue, client):
        """Test submitting task result."""
        task_id = uuid4()
        mock_queue = MagicMock()
        mock_queue.complete_task = AsyncMock()
        mock_get_queue.return_value = mock_queue

        result_data = {
            "output": {"result": "success"},
            "cost": 0.25,
        }

        response = client.post(f"/api/v1/tasks/{task_id}/result", json=result_data)

        assert response.status_code == 200
        mock_queue.complete_task.assert_called_once()

    @patch("backend.api.main.get_queue")
    def test_submit_task_failure(self, mock_get_queue, client):
        """Test submitting task failure."""
        task_id = uuid4()
        mock_queue = MagicMock()
        mock_queue.fail_task = AsyncMock()
        mock_get_queue.return_value = mock_queue

        failure_data = {
            "error": "Task failed",
            "retry": True,
        }

        response = client.post(f"/api/v1/tasks/{task_id}/fail", json=failure_data)

        assert response.status_code == 200
        mock_queue.fail_task.assert_called_once()


@pytest.mark.unit
class TestMetricsEndpoints:
    """Tests for metrics endpoints."""

    @patch("backend.api.main.get_collector")
    def test_get_metrics(self, mock_get_collector, client):
        """Test getting system metrics."""
        mock_collector = MagicMock()
        mock_collector.collect_metrics = AsyncMock(
            return_value={
                "agents": {"total": 5},
                "tasks": {"completed": 100},
            }
        )
        mock_get_collector.return_value = mock_collector

        response = client.get("/api/v1/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "tasks" in data

    @patch("backend.api.main.get_queue")
    def test_get_queue_depths(self, mock_get_queue, client):
        """Test getting queue depths."""
        mock_queue = MagicMock()
        mock_queue.get_all_queue_depths = AsyncMock(
            return_value={
                "capability_a": 10,
                "capability_b": 5,
            }
        )
        mock_get_queue.return_value = mock_queue

        response = client.get("/api/v1/metrics/queues")

        assert response.status_code == 200
        data = response.json()
        assert data["capability_a"] == 10
        assert data["capability_b"] == 5


@pytest.mark.unit
class TestCORSMiddleware:
    """Tests for CORS middleware."""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present in response."""
        response = client.options(
            "/api/v1/agents",
            headers={"Origin": "http://localhost:3000"}
        )

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers


@pytest.mark.unit
class TestAPIDocumentation:
    """Tests for API documentation."""

    def test_openapi_json_available(self, client):
        """Test OpenAPI JSON is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "openapi" in response.json()

    def test_docs_page_available(self, client):
        """Test Swagger UI docs are accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_page_available(self, client):
        """Test ReDoc docs are accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200
