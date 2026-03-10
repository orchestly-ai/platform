"""Unit tests for AgentClient SDK.

NOTE: These tests are for the SDK client and are skipped as they're
part of the legacy test suite. See backend/tests/ for working tests.
"""
import os
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
import respx

# Skip all tests in this module - legacy test suite
pytestmark = pytest.mark.skip(reason="Legacy tests - see backend/tests/ for working tests")

from sdk.python.agent_orchestrator.client import AgentClient, AgentConfig, TaskResult


@pytest.mark.unit
@pytest.mark.asyncio
class TestAgentClient:
    """Test suite for AgentClient."""

    @pytest.fixture
    def agent_config(self):
        """Create test agent configuration."""
        return AgentConfig(
            name="Test Agent",
            description="Test agent for unit tests",
            capabilities=["test_capability", "another_capability"],
            cost_limit_daily=50.0,
            cost_limit_monthly=1500.0,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            framework="langchain",
            version="1.0.0",
            tags=["test", "unit"],
            metadata={"team": "qa"},
        )

    @pytest_asyncio.fixture
    async def client(self):
        """Create agent client instance."""
        client = AgentClient(
            api_url="http://test-api.com",
            api_key="test-key-123",
        )
        yield client
        await client.close()

    async def test_client_initialization_with_params(self):
        """Test client initializes with provided parameters."""
        client = AgentClient(
            api_url="http://custom-api.com",
            api_key="custom-key",
        )

        assert client.api_url == "http://custom-api.com"
        assert client.api_key == "custom-key"
        assert client.agent_id is None
        assert client.agent_config is None

        await client.close()

    async def test_client_initialization_from_env(self):
        """Test client initializes from environment variables."""
        with patch.dict(os.environ, {
            "ORCHESTRATOR_API_URL": "http://env-api.com",
            "ORCHESTRATOR_API_KEY": "env-key",
        }):
            client = AgentClient()

            assert client.api_url == "http://env-api.com"
            assert client.api_key == "env-key"

            await client.close()

    async def test_client_initialization_defaults(self):
        """Test client uses default values when not provided."""
        with patch.dict(os.environ, {}, clear=True):
            client = AgentClient()

            assert client.api_url == "http://localhost:8000"
            assert client.api_key == ""

            await client.close()

    @respx.mock
    async def test_register_agent_success(self, client, agent_config):
        """Test successful agent registration."""
        agent_id = uuid4()

        # Mock the registration endpoint
        route = respx.post("http://test-api.com/api/v1/agents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agent_id": str(agent_id),
                    "status": "registered",
                    "api_key": "new-api-key-123",
                },
            )
        )

        result_agent_id = await client.register_agent(agent_config)

        assert result_agent_id == agent_id
        assert client.agent_id == agent_id
        assert client.agent_config == agent_config
        assert client.api_key == "new-api-key-123"
        assert route.called

    @respx.mock
    async def test_register_agent_http_error(self, client, agent_config):
        """Test agent registration handles HTTP errors."""
        respx.post("http://test-api.com/api/v1/agents").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )

        with pytest.raises(RuntimeError, match="Failed to register agent"):
            await client.register_agent(agent_config)

    @respx.mock
    async def test_get_next_task_success(self, client, agent_config):
        """Test successful task polling."""
        agent_id = uuid4()
        client.agent_id = agent_id
        client.agent_config = agent_config

        task_id = uuid4()
        task_data = {
            "task_id": str(task_id),
            "capability": "test_capability",
            "input": {"message": "Test task"},
            "priority": 1,
        }

        respx.get(
            f"http://test-api.com/api/v1/agents/{agent_id}/tasks/next"
        ).mock(return_value=httpx.Response(200, json=task_data))

        result = await client.get_next_task(["test_capability"])

        assert result == task_data
        assert result["task_id"] == str(task_id)

    @respx.mock
    async def test_get_next_task_no_tasks_available(self, client):
        """Test task polling when no tasks available."""
        agent_id = uuid4()
        client.agent_id = agent_id

        respx.get(
            f"http://test-api.com/api/v1/agents/{agent_id}/tasks/next"
        ).mock(return_value=httpx.Response(204))

        result = await client.get_next_task(["test_capability"])

        assert result is None

    async def test_get_next_task_not_registered(self, client):
        """Test task polling fails when agent not registered."""
        with pytest.raises(RuntimeError, match="Agent not registered"):
            await client.get_next_task(["test_capability"])

    @respx.mock
    async def test_get_next_task_http_error(self, client):
        """Test task polling handles HTTP errors gracefully."""
        agent_id = uuid4()
        client.agent_id = agent_id

        respx.get(
            f"http://test-api.com/api/v1/agents/{agent_id}/tasks/next"
        ).mock(return_value=httpx.Response(500))

        result = await client.get_next_task(["test_capability"])

        # Should return None instead of raising error
        assert result is None

    @respx.mock
    async def test_submit_result_success(self, client):
        """Test successful result submission."""
        task_id = uuid4()

        route = respx.post(
            f"http://test-api.com/api/v1/tasks/{task_id}/result"
        ).mock(return_value=httpx.Response(200, json={"status": "ok"}))

        output = {"result": "Task completed", "confidence": 0.95}
        await client.submit_result(task_id, output, cost=0.0023)

        assert route.called
        request = route.calls.last.request
        request_json = request.content.decode()
        assert "completed" in request_json
        assert "0.0023" in request_json

    @respx.mock
    async def test_submit_result_http_error(self, client):
        """Test result submission handles HTTP errors."""
        task_id = uuid4()

        respx.post(
            f"http://test-api.com/api/v1/tasks/{task_id}/result"
        ).mock(return_value=httpx.Response(500))

        with pytest.raises(RuntimeError, match="Failed to submit result"):
            await client.submit_result(task_id, {"result": "test"})

    @respx.mock
    async def test_submit_error_success(self, client):
        """Test successful error submission."""
        task_id = uuid4()

        route = respx.post(
            f"http://test-api.com/api/v1/tasks/{task_id}/result"
        ).mock(return_value=httpx.Response(200, json={"status": "ok"}))

        await client.submit_error(task_id, "Test error occurred")

        assert route.called
        request = route.calls.last.request
        request_json = request.content.decode()
        assert "failed" in request_json
        assert "Test error occurred" in request_json

    @respx.mock
    async def test_submit_error_http_error(self, client, capsys):
        """Test error submission handles HTTP errors gracefully."""
        task_id = uuid4()

        respx.post(
            f"http://test-api.com/api/v1/tasks/{task_id}/result"
        ).mock(return_value=httpx.Response(500))

        # Should not raise, just print error
        await client.submit_error(task_id, "Test error")

        captured = capsys.readouterr()
        assert "Failed to submit error" in captured.out

    @respx.mock
    async def test_send_heartbeat_success(self, client):
        """Test successful heartbeat."""
        agent_id = uuid4()
        client.agent_id = agent_id

        route = respx.post(
            f"http://test-api.com/api/v1/agents/{agent_id}/heartbeat"
        ).mock(return_value=httpx.Response(200, json={"status": "ok"}))

        await client.send_heartbeat()

        assert route.called

    @respx.mock
    async def test_send_heartbeat_not_registered(self, client):
        """Test heartbeat when not registered (should be no-op)."""
        await client.send_heartbeat()
        # Should complete without error

    @respx.mock
    async def test_send_heartbeat_http_error(self, client, capsys):
        """Test heartbeat handles HTTP errors gracefully."""
        agent_id = uuid4()
        client.agent_id = agent_id

        respx.post(
            f"http://test-api.com/api/v1/agents/{agent_id}/heartbeat"
        ).mock(return_value=httpx.Response(500))

        await client.send_heartbeat()

        captured = capsys.readouterr()
        assert "Heartbeat failed" in captured.out

    @respx.mock
    async def test_get_agent_status_success(self, client):
        """Test getting agent status."""
        agent_id = uuid4()
        client.agent_id = agent_id

        status_data = {
            "agent_id": str(agent_id),
            "status": "active",
            "tasks_completed": 42,
            "cost_today": 1.25,
        }

        respx.get(
            f"http://test-api.com/api/v1/agents/{agent_id}"
        ).mock(return_value=httpx.Response(200, json=status_data))

        result = await client.get_agent_status()

        assert result == status_data
        assert result["tasks_completed"] == 42

    async def test_get_agent_status_not_registered(self, client):
        """Test getting status when not registered."""
        with pytest.raises(RuntimeError, match="Agent not registered"):
            await client.get_agent_status()

    async def test_context_manager(self):
        """Test using client as async context manager."""
        async with AgentClient(api_url="http://test.com") as client:
            assert client is not None
            assert isinstance(client, AgentClient)

        # Client should be closed after exiting context

    async def test_close(self, client):
        """Test closing client."""
        await client.close()
        # Verify client can't be used after close
        # (httpx client should be closed)


@pytest.mark.unit
class TestAgentConfig:
    """Test suite for AgentConfig model."""

    def test_agent_config_defaults(self):
        """Test AgentConfig with default values."""
        config = AgentConfig(name="Test Agent")

        assert config.name == "Test Agent"
        assert config.description is None
        assert config.capabilities == []
        assert config.cost_limit_daily == 100.0
        assert config.cost_limit_monthly == 3000.0
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4o-mini"
        assert config.framework == "custom"
        assert config.version == "1.0.0"
        assert config.tags == []
        assert config.metadata == {}

    def test_agent_config_custom_values(self):
        """Test AgentConfig with custom values."""
        config = AgentConfig(
            name="Custom Agent",
            description="Custom description",
            capabilities=["cap1", "cap2"],
            cost_limit_daily=200.0,
            cost_limit_monthly=6000.0,
            llm_provider="anthropic",
            llm_model="claude-3-opus",
            framework="crewai",
            version="2.0.0",
            tags=["prod", "critical"],
            metadata={"env": "production"},
        )

        assert config.name == "Custom Agent"
        assert config.description == "Custom description"
        assert config.capabilities == ["cap1", "cap2"]
        assert config.cost_limit_daily == 200.0
        assert config.llm_provider == "anthropic"
        assert config.framework == "crewai"
        assert config.metadata == {"env": "production"}

    def test_agent_config_serialization(self):
        """Test AgentConfig can be serialized."""
        config = AgentConfig(
            name="Test",
            capabilities=["test"],
        )

        data = config.model_dump()

        assert isinstance(data, dict)
        assert data["name"] == "Test"
        assert data["capabilities"] == ["test"]


@pytest.mark.unit
class TestTaskResult:
    """Test suite for TaskResult model."""

    def test_task_result_minimal(self):
        """Test TaskResult with minimal fields."""
        task_id = uuid4()
        result = TaskResult(task_id=task_id, status="completed")

        assert result.task_id == task_id
        assert result.status == "completed"
        assert result.output is None
        assert result.error is None
        assert result.cost is None

    def test_task_result_with_output(self):
        """Test TaskResult with output."""
        task_id = uuid4()
        output = {"result": "Success", "data": [1, 2, 3]}

        result = TaskResult(
            task_id=task_id,
            status="completed",
            output=output,
            cost=0.0025,
        )

        assert result.output == output
        assert result.cost == 0.0025

    def test_task_result_with_error(self):
        """Test TaskResult with error."""
        task_id = uuid4()

        result = TaskResult(
            task_id=task_id,
            status="failed",
            error="Something went wrong",
        )

        assert result.status == "failed"
        assert result.error == "Something went wrong"
