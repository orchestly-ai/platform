"""Comprehensive unit tests for the Orchestly Python SDK."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest

from orchestly.client import AgentConfig, OrchestlyClient, TaskResult
from orchestly.llm import LLMClient
from orchestly.decorators import register_agent, task


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_AGENT_ID = "12345678-1234-5678-1234-567812345678"
FAKE_TASK_ID = "abcdefab-abcd-abcd-abcd-abcdefabcdef"


def _make_response(status_code: int = 200, json_data=None):
    """Build a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp


@pytest.fixture
def agent_config():
    return AgentConfig(
        name="test-agent",
        description="A test agent",
        capabilities=["cap_a", "cap_b"],
        cost_limit_daily=50.0,
        cost_limit_monthly=1000.0,
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        framework="custom",
        version="0.1.0",
        tags=["test"],
        metadata={"env": "test"},
    )


# =========================================================================
# AgentConfig / TaskResult Pydantic models
# =========================================================================

class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig(name="minimal")
        assert cfg.name == "minimal"
        assert cfg.description is None
        assert cfg.capabilities == []
        assert cfg.cost_limit_daily == 100.0
        assert cfg.cost_limit_monthly == 3000.0
        assert cfg.llm_provider == "openai"
        assert cfg.llm_model == "gpt-4o-mini"
        assert cfg.framework == "custom"
        assert cfg.version == "1.0.0"
        assert cfg.tags == []
        assert cfg.metadata == {}

    def test_custom_values(self, agent_config):
        assert agent_config.name == "test-agent"
        assert agent_config.description == "A test agent"
        assert agent_config.capabilities == ["cap_a", "cap_b"]
        assert agent_config.cost_limit_daily == 50.0
        assert agent_config.tags == ["test"]
        assert agent_config.metadata == {"env": "test"}

    def test_model_dump(self, agent_config):
        d = agent_config.model_dump()
        assert isinstance(d, dict)
        assert d["name"] == "test-agent"
        assert "capabilities" in d


class TestTaskResult:
    def test_minimal(self):
        tid = uuid4()
        tr = TaskResult(task_id=tid, status="completed")
        assert tr.task_id == tid
        assert tr.status == "completed"
        assert tr.output is None
        assert tr.error is None
        assert tr.cost is None

    def test_full(self):
        tid = uuid4()
        tr = TaskResult(
            task_id=tid,
            status="failed",
            output={"key": "val"},
            error="boom",
            cost=0.05,
        )
        assert tr.error == "boom"
        assert tr.cost == 0.05
        assert tr.output == {"key": "val"}


# =========================================================================
# OrchestlyClient -- initialisation
# =========================================================================

class TestOrchestlyClientInit:
    def test_defaults_no_env(self):
        with patch.dict("os.environ", {}, clear=True):
            client = OrchestlyClient()
            assert client.api_url == "http://localhost:8000"
            assert client.api_key == ""
            assert client.agent_id is None
            assert client.agent_config is None

    def test_explicit_params(self):
        client = OrchestlyClient(
            api_url="https://custom.orchestly.ai",
            api_key="sk-test-123",
        )
        assert client.api_url == "https://custom.orchestly.ai"
        assert client.api_key == "sk-test-123"

    def test_env_vars(self):
        env = {
            "ORCHESTLY_API_URL": "https://env-url.orchestly.ai",
            "ORCHESTLY_API_KEY": "sk-env-key",
        }
        with patch.dict("os.environ", env, clear=True):
            client = OrchestlyClient()
            assert client.api_url == "https://env-url.orchestly.ai"
            assert client.api_key == "sk-env-key"

    def test_explicit_overrides_env(self):
        env = {
            "ORCHESTLY_API_URL": "https://env-url.orchestly.ai",
            "ORCHESTLY_API_KEY": "sk-env-key",
        }
        with patch.dict("os.environ", env, clear=True):
            client = OrchestlyClient(
                api_url="https://explicit.orchestly.ai",
                api_key="sk-explicit",
            )
            assert client.api_url == "https://explicit.orchestly.ai"
            assert client.api_key == "sk-explicit"

    def test_api_key_sets_header(self):
        client = OrchestlyClient(api_key="sk-header")
        assert client.client.headers.get("x-api-key") == "sk-header"

    def test_no_api_key_no_header(self):
        with patch.dict("os.environ", {}, clear=True):
            client = OrchestlyClient()
            assert "x-api-key" not in client.client.headers


# =========================================================================
# OrchestlyClient -- context manager
# =========================================================================

class TestOrchestlyClientContextManager:
    @pytest.mark.asyncio
    async def test_aenter_returns_self(self):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        result = await client.__aenter__()
        assert result is client
        await client.close()

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        await client.__aexit__(None, None, None)
        client.client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_with(self):
        async with OrchestlyClient(api_url="http://test", api_key="k") as client:
            assert isinstance(client, OrchestlyClient)
        # After exiting, the internal httpx client should be closed.
        assert client.client.is_closed


# =========================================================================
# OrchestlyClient -- register_agent
# =========================================================================

class TestRegisterAgent:
    @pytest.mark.asyncio
    async def test_success(self, agent_config):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        response = _make_response(200, {"agent_id": FAKE_AGENT_ID})

        client.client = AsyncMock()
        client.client.post = AsyncMock(return_value=response)

        agent_id = await client.register_agent(agent_config)

        assert agent_id == UUID(FAKE_AGENT_ID)
        assert client.agent_id == UUID(FAKE_AGENT_ID)
        assert client.agent_config is agent_config

        # Verify the correct endpoint was called
        client.client.post.assert_awaited_once()
        call_args = client.client.post.call_args
        assert call_args[0][0] == "/api/v1/agents"

    @pytest.mark.asyncio
    async def test_success_with_api_key_in_response(self, agent_config):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        response = _make_response(
            200,
            {"agent_id": FAKE_AGENT_ID, "api_key": "sk-new-key"},
        )
        client.client = AsyncMock()
        client.client.post = AsyncMock(return_value=response)
        client.client.headers = {}

        await client.register_agent(agent_config)

        assert client.api_key == "sk-new-key"
        assert client.client.headers["X-API-Key"] == "sk-new-key"

    @pytest.mark.asyncio
    async def test_http_error_raises_runtime_error(self, agent_config):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        response = _make_response(500)

        client.client = AsyncMock()
        client.client.post = AsyncMock(return_value=response)

        with pytest.raises(RuntimeError, match="Failed to register agent"):
            await client.register_agent(agent_config)

    @pytest.mark.asyncio
    async def test_network_error_raises_runtime_error(self, agent_config):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        client.client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(RuntimeError, match="Failed to register agent"):
            await client.register_agent(agent_config)


# =========================================================================
# OrchestlyClient -- get_next_task
# =========================================================================

class TestGetNextTask:
    @pytest.mark.asyncio
    async def test_returns_task_data(self):
        task_data = {"task_id": FAKE_TASK_ID, "capability": "cap_a", "input": {"x": 1}}
        response = _make_response(200, task_data)

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.agent_id = UUID(FAKE_AGENT_ID)
        client.client = AsyncMock()
        client.client.get = AsyncMock(return_value=response)

        result = await client.get_next_task(["cap_a", "cap_b"])

        assert result == task_data
        client.client.get.assert_awaited_once()
        call_args = client.client.get.call_args
        assert f"/api/v1/agents/{FAKE_AGENT_ID}/tasks/next" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_204_returns_none(self):
        response = _make_response(204)
        # 204 is not an error, so raise_for_status should not be called
        # (the code checks status_code == 204 before raise_for_status)
        response.raise_for_status = MagicMock()

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.agent_id = UUID(FAKE_AGENT_ID)
        client.client = AsyncMock()
        client.client.get = AsyncMock(return_value=response)

        result = await client.get_next_task(["cap_a"])
        assert result is None

    @pytest.mark.asyncio
    async def test_not_registered_raises_error(self):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        # agent_id is None by default

        with pytest.raises(RuntimeError, match="Agent not registered"):
            await client.get_next_task(["cap_a"])

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        """On HTTP errors, get_next_task logs and returns None instead of raising."""
        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.agent_id = UUID(FAKE_AGENT_ID)
        client.client = AsyncMock()
        client.client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await client.get_next_task(["cap_a"])
        assert result is None

    @pytest.mark.asyncio
    async def test_capabilities_sent_as_params(self):
        response = _make_response(204)
        response.raise_for_status = MagicMock()

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.agent_id = UUID(FAKE_AGENT_ID)
        client.client = AsyncMock()
        client.client.get = AsyncMock(return_value=response)

        await client.get_next_task(["alpha", "beta", "gamma"])

        call_kwargs = client.client.get.call_args[1]
        assert call_kwargs["params"] == {"capabilities": "alpha,beta,gamma"}


# =========================================================================
# OrchestlyClient -- submit_result
# =========================================================================

class TestSubmitResult:
    @pytest.mark.asyncio
    async def test_success(self):
        response = _make_response(200)

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        client.client.post = AsyncMock(return_value=response)

        task_id = UUID(FAKE_TASK_ID)
        await client.submit_result(task_id, output={"answer": 42}, cost=0.01)

        client.client.post.assert_awaited_once()
        call_args = client.client.post.call_args
        assert f"/api/v1/tasks/{FAKE_TASK_ID}/result" in call_args[0][0]

        json_body = call_args[1]["json"]
        assert json_body["output"] == {"answer": 42}
        assert json_body["cost"] == 0.01
        assert json_body["status"] == "completed"

    @pytest.mark.asyncio
    async def test_cost_is_optional(self):
        response = _make_response(200)

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        client.client.post = AsyncMock(return_value=response)

        task_id = UUID(FAKE_TASK_ID)
        await client.submit_result(task_id, output={"result": "ok"})

        json_body = client.client.post.call_args[1]["json"]
        assert json_body["cost"] is None

    @pytest.mark.asyncio
    async def test_http_error_raises_runtime_error(self):
        response = _make_response(500)

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        client.client.post = AsyncMock(return_value=response)

        with pytest.raises(RuntimeError, match="Failed to submit result"):
            await client.submit_result(UUID(FAKE_TASK_ID), output={"a": 1})

    @pytest.mark.asyncio
    async def test_network_error_raises_runtime_error(self):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        client.client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(RuntimeError, match="Failed to submit result"):
            await client.submit_result(UUID(FAKE_TASK_ID), output={"a": 1})


# =========================================================================
# OrchestlyClient -- submit_error
# =========================================================================

class TestSubmitError:
    @pytest.mark.asyncio
    async def test_success(self):
        response = _make_response(200)

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        client.client.post = AsyncMock(return_value=response)

        task_id = UUID(FAKE_TASK_ID)
        await client.submit_error(task_id, error="something went wrong")

        call_args = client.client.post.call_args
        json_body = call_args[1]["json"]
        assert json_body["status"] == "failed"
        assert json_body["error"] == "something went wrong"

    @pytest.mark.asyncio
    async def test_http_error_does_not_raise(self):
        """submit_error swallows HTTP errors (prints instead of raising)."""
        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        client.client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        # Should not raise
        await client.submit_error(UUID(FAKE_TASK_ID), error="boom")


# =========================================================================
# OrchestlyClient -- send_heartbeat
# =========================================================================

class TestSendHeartbeat:
    @pytest.mark.asyncio
    async def test_sends_heartbeat(self):
        response = _make_response(200)

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.agent_id = UUID(FAKE_AGENT_ID)
        client.client = AsyncMock()
        client.client.post = AsyncMock(return_value=response)

        await client.send_heartbeat()

        client.client.post.assert_awaited_once()
        call_args = client.client.post.call_args
        assert f"/api/v1/agents/{FAKE_AGENT_ID}/heartbeat" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_agent_id_returns_silently(self):
        """If agent_id is None, heartbeat does nothing."""
        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()
        client.client.post = AsyncMock()

        await client.send_heartbeat()

        client.client.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_http_error_does_not_raise(self):
        """Heartbeat errors are swallowed."""
        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.agent_id = UUID(FAKE_AGENT_ID)
        client.client = AsyncMock()
        client.client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        # Should not raise
        await client.send_heartbeat()


# =========================================================================
# OrchestlyClient -- get_agent_status
# =========================================================================

class TestGetAgentStatus:
    @pytest.mark.asyncio
    async def test_success(self):
        status_data = {"status": "active", "tasks_completed": 10}
        response = _make_response(200, status_data)

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.agent_id = UUID(FAKE_AGENT_ID)
        client.client = AsyncMock()
        client.client.get = AsyncMock(return_value=response)

        result = await client.get_agent_status()

        assert result == status_data
        client.client.get.assert_awaited_once()
        call_args = client.client.get.call_args
        assert f"/api/v1/agents/{FAKE_AGENT_ID}" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_not_registered_raises_error(self):
        client = OrchestlyClient(api_url="http://test", api_key="k")

        with pytest.raises(RuntimeError, match="Agent not registered"):
            await client.get_agent_status()

    @pytest.mark.asyncio
    async def test_http_error_propagates(self):
        response = _make_response(500)

        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.agent_id = UUID(FAKE_AGENT_ID)
        client.client = AsyncMock()
        client.client.get = AsyncMock(return_value=response)

        with pytest.raises(httpx.HTTPStatusError):
            await client.get_agent_status()


# =========================================================================
# OrchestlyClient -- close
# =========================================================================

class TestClientClose:
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        client = OrchestlyClient(api_url="http://test", api_key="k")
        client.client = AsyncMock()

        await client.close()
        client.client.aclose.assert_awaited_once()


# =========================================================================
# LLMClient -- initialisation
# =========================================================================

class TestLLMClientInit:
    def test_defaults_no_env(self):
        with patch.dict("os.environ", {}, clear=True):
            llm = LLMClient()
            assert llm.agent_id is None
            assert llm.api_url == "http://localhost:8000"
            assert llm.api_key == ""
            assert llm.provider == "openai"
            assert llm.model == "gpt-4o-mini"
            assert llm.temperature == 0.7

    def test_custom_params(self):
        aid = uuid4()
        llm = LLMClient(
            agent_id=aid,
            api_url="https://custom.ai",
            api_key="sk-llm-key",
            provider="anthropic",
            model="claude-3-haiku",
            temperature=0.3,
        )
        assert llm.agent_id == aid
        assert llm.api_url == "https://custom.ai"
        assert llm.api_key == "sk-llm-key"
        assert llm.provider == "anthropic"
        assert llm.model == "claude-3-haiku"
        assert llm.temperature == 0.3

    def test_env_vars(self):
        env = {
            "ORCHESTLY_API_URL": "https://env-llm.ai",
            "ORCHESTLY_API_KEY": "sk-env-llm",
        }
        with patch.dict("os.environ", env, clear=True):
            llm = LLMClient()
            assert llm.api_url == "https://env-llm.ai"
            assert llm.api_key == "sk-env-llm"

    def test_api_key_sets_header(self):
        llm = LLMClient(api_key="sk-header-llm")
        assert llm.client.headers.get("x-api-key") == "sk-header-llm"

    def test_no_api_key_no_header(self):
        with patch.dict("os.environ", {}, clear=True):
            llm = LLMClient()
            assert "x-api-key" not in llm.client.headers


# =========================================================================
# LLMClient -- context manager
# =========================================================================

class TestLLMClientContextManager:
    @pytest.mark.asyncio
    async def test_aenter_returns_self(self):
        llm = LLMClient(api_url="http://test", api_key="k")
        result = await llm.__aenter__()
        assert result is llm
        await llm.close()

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        await llm.__aexit__(None, None, None)
        llm.client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_with(self):
        async with LLMClient(api_url="http://test", api_key="k") as llm:
            assert isinstance(llm, LLMClient)
        assert llm.client.is_closed


# =========================================================================
# LLMClient -- chat
# =========================================================================

class TestLLMClientChat:
    @pytest.mark.asyncio
    async def test_success(self):
        response = _make_response(200, {"content": "Hello from LLM!"})

        llm = LLMClient(api_url="http://test", api_key="k", provider="openai", model="gpt-4o")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        messages = [{"role": "user", "content": "Hi"}]
        result = await llm.chat(messages)

        assert result == "Hello from LLM!"

        call_args = llm.client.post.call_args
        assert call_args[0][0] == "/api/v1/llm/completions"
        json_body = call_args[1]["json"]
        assert json_body["provider"] == "openai"
        assert json_body["model"] == "gpt-4o"
        assert json_body["messages"] == messages
        assert json_body["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_with_overrides(self):
        response = _make_response(200, {"content": "overridden"})

        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        messages = [{"role": "user", "content": "test"}]
        result = await llm.chat(
            messages, max_tokens=100, temperature=0.2, model="gpt-3.5-turbo"
        )

        assert result == "overridden"
        json_body = llm.client.post.call_args[1]["json"]
        assert json_body["model"] == "gpt-3.5-turbo"
        assert json_body["temperature"] == 0.2
        assert json_body["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_agent_id_included(self):
        aid = uuid4()
        response = _make_response(200, {"content": "ok"})

        llm = LLMClient(agent_id=aid, api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        await llm.chat([{"role": "user", "content": "test"}])

        json_body = llm.client.post.call_args[1]["json"]
        assert json_body["agent_id"] == str(aid)

    @pytest.mark.asyncio
    async def test_no_agent_id_sends_none(self):
        response = _make_response(200, {"content": "ok"})

        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        await llm.chat([{"role": "user", "content": "test"}])

        json_body = llm.client.post.call_args[1]["json"]
        assert json_body["agent_id"] is None

    @pytest.mark.asyncio
    async def test_http_error_raises_runtime_error(self):
        response = _make_response(500)

        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        with pytest.raises(RuntimeError, match="LLM generation failed"):
            await llm.chat([{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_network_error_raises_runtime_error(self):
        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(RuntimeError, match="LLM generation failed"):
            await llm.chat([{"role": "user", "content": "test"}])


# =========================================================================
# LLMClient -- generate
# =========================================================================

class TestLLMClientGenerate:
    @pytest.mark.asyncio
    async def test_simple_prompt(self):
        response = _make_response(200, {"content": "Generated text"})

        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        result = await llm.generate("Tell me a joke")

        assert result == "Generated text"

        json_body = llm.client.post.call_args[1]["json"]
        messages = json_body["messages"]
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Tell me a joke"}

    @pytest.mark.asyncio
    async def test_with_system_message(self):
        response = _make_response(200, {"content": "sys+user"})

        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        result = await llm.generate("Hello", system="You are a poet")

        assert result == "sys+user"
        json_body = llm.client.post.call_args[1]["json"]
        messages = json_body["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are a poet"}
        assert messages[1] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_with_overrides(self):
        response = _make_response(200, {"content": "overridden"})

        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        await llm.generate(
            "prompt", max_tokens=50, temperature=0.1, model="gpt-3.5-turbo"
        )

        json_body = llm.client.post.call_args[1]["json"]
        assert json_body["max_tokens"] == 50
        assert json_body["temperature"] == 0.1
        assert json_body["model"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_generate_error_propagates(self):
        response = _make_response(500)

        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()
        llm.client.post = AsyncMock(return_value=response)

        with pytest.raises(RuntimeError, match="LLM generation failed"):
            await llm.generate("prompt")


# =========================================================================
# LLMClient -- close
# =========================================================================

class TestLLMClientClose:
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        llm = LLMClient(api_url="http://test", api_key="k")
        llm.client = AsyncMock()

        await llm.close()
        llm.client.aclose.assert_awaited_once()


# =========================================================================
# @register_agent decorator
# =========================================================================

class TestRegisterAgentDecorator:
    def test_attaches_config_to_class(self):
        @register_agent(
            name="test_agent",
            capabilities=["cap_a"],
            description="Test desc",
            cost_limit_daily=50.0,
            cost_limit_monthly=1500.0,
            llm_provider="anthropic",
            llm_model="claude-3-haiku",
            framework="langchain",
            version="2.0.0",
            tags=["test"],
            metadata={"k": "v"},
        )
        class MyAgent:
            pass

        assert hasattr(MyAgent, "_agent_config")
        assert isinstance(MyAgent._agent_config, AgentConfig)
        assert MyAgent._agent_config.name == "test_agent"
        assert MyAgent._agent_config.capabilities == ["cap_a"]
        assert MyAgent._agent_config.description == "Test desc"
        assert MyAgent._agent_config.cost_limit_daily == 50.0
        assert MyAgent._agent_config.llm_provider == "anthropic"
        assert MyAgent._agent_config.tags == ["test"]

    def test_uses_docstring_as_description(self):
        @register_agent(name="doc_agent", capabilities=["cap"])
        class DocAgent:
            """This is a documented agent."""
            pass

        assert DocAgent._agent_config.description == "This is a documented agent."

    def test_initial_state(self):
        @register_agent(name="state_agent", capabilities=["cap"])
        class StateAgent:
            pass

        assert StateAgent._agent_client is None
        assert StateAgent._registered is False

    def test_attaches_register_method(self):
        @register_agent(name="reg_method_agent", capabilities=["cap"])
        class RegMethodAgent:
            pass

        instance = RegMethodAgent()
        assert hasattr(instance, "_register")
        assert asyncio.iscoroutinefunction(instance._register)

    def test_attaches_run_forever_method(self):
        @register_agent(name="run_agent", capabilities=["cap"])
        class RunAgent:
            pass

        instance = RunAgent()
        assert hasattr(instance, "run_forever")
        assert asyncio.iscoroutinefunction(instance.run_forever)

    def test_default_tags_and_metadata(self):
        @register_agent(name="default_agent", capabilities=["cap"])
        class DefaultAgent:
            pass

        assert DefaultAgent._agent_config.tags == []
        assert DefaultAgent._agent_config.metadata == {}

    @pytest.mark.asyncio
    async def test_register_creates_client_and_registers(self):
        @register_agent(name="auto_reg", capabilities=["cap"])
        class AutoRegAgent:
            pass

        instance = AutoRegAgent()

        # Mock the OrchestlyClient
        mock_client = AsyncMock(spec=OrchestlyClient)
        mock_client.register_agent = AsyncMock(return_value=UUID(FAKE_AGENT_ID))

        with patch(
            "orchestly.decorators.OrchestlyClient", return_value=mock_client
        ):
            # Reset class-level state for clean test
            AutoRegAgent._agent_client = None
            AutoRegAgent._registered = False

            agent_id = await instance._register()

            assert agent_id == UUID(FAKE_AGENT_ID)
            assert AutoRegAgent._registered is True

    @pytest.mark.asyncio
    async def test_register_idempotent(self):
        @register_agent(name="idem_agent", capabilities=["cap"])
        class IdemAgent:
            pass

        instance = IdemAgent()

        mock_client = AsyncMock(spec=OrchestlyClient)
        mock_client.register_agent = AsyncMock(return_value=UUID(FAKE_AGENT_ID))

        with patch(
            "orchestly.decorators.OrchestlyClient", return_value=mock_client
        ):
            IdemAgent._agent_client = None
            IdemAgent._registered = False

            await instance._register()
            await instance._register()  # second call should be a no-op

            # register_agent should only be called once
            mock_client.register_agent.assert_awaited_once()


# =========================================================================
# @task decorator
# =========================================================================

class TestTaskDecorator:
    def test_attaches_metadata_defaults(self):
        @task()
        async def my_task(data):
            return data

        assert my_task._is_task is True
        assert my_task._task_timeout == 300
        assert my_task._task_max_retries == 3
        assert my_task._task_input_schema is None
        assert my_task._task_output_schema is None

    def test_attaches_metadata_custom(self):
        schemas_in = {"type": "object"}
        schemas_out = {"type": "string"}

        @task(timeout=60, max_retries=5, input_schema=schemas_in, output_schema=schemas_out)
        async def custom_task(data):
            return data

        assert custom_task._is_task is True
        assert custom_task._task_timeout == 60
        assert custom_task._task_max_retries == 5
        assert custom_task._task_input_schema == schemas_in
        assert custom_task._task_output_schema == schemas_out

    @pytest.mark.asyncio
    async def test_async_function_executes(self):
        @task(timeout=5)
        async def adder(a, b):
            return a + b

        result = await adder(2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_async_function_timeout(self):
        @task(timeout=1)
        async def slow_task():
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(TimeoutError, match="Task exceeded timeout of 1s"):
            await slow_task()

    @pytest.mark.asyncio
    async def test_sync_function_in_executor(self):
        @task(timeout=5)
        def sync_task(x):
            return x * 2

        result = await sync_task(7)
        assert result == 14

    def test_preserves_function_name(self):
        @task()
        async def named_function():
            pass

        assert named_function.__name__ == "named_function"

    def test_preserves_docstring(self):
        @task()
        async def documented():
            """This is documented."""
            pass

        assert documented.__doc__ == "This is documented."

    @pytest.mark.asyncio
    async def test_passes_kwargs(self):
        @task(timeout=5)
        async def kwarg_task(a, b=10):
            return a + b

        result = await kwarg_task(5, b=20)
        assert result == 25

    @pytest.mark.asyncio
    async def test_propagates_exceptions(self):
        @task(timeout=5)
        async def failing_task():
            raise ValueError("task failed")

        with pytest.raises(ValueError, match="task failed"):
            await failing_task()
