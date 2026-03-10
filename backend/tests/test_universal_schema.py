#!/usr/bin/env python3
"""
Tests for Universal Schema and Provider Adapters

Tests provider normalization for OpenAI, Anthropic, and DeepSeek.
Reference: ROADMAP.md Section "Provider Normalization Layer"
"""

import pytest
import json
from uuid import uuid4

from backend.shared.universal_schema import (
    UniversalRole,
    UniversalMessage,
    UniversalToolCall,
    UniversalRequest,
    UniversalResponse,
    ToolDefinition,
    ToolParameter,
    ModelConfig,
    TokenUsage,
    ContentBlock,
    ContentType,
    create_text_message,
    create_tool_result_message,
    create_tool_call_message,
    messages_to_json,
    messages_from_json,
)
from backend.shared.provider_adapters import (
    OpenAIAdapter,
    AnthropicAdapter,
    DeepSeekAdapter,
    get_adapter,
)


# ============================================================================
# Universal Schema Tests
# ============================================================================


class TestUniversalMessage:
    """Tests for UniversalMessage class."""

    def test_create_text_message(self):
        """Should create a simple text message."""
        msg = UniversalMessage(
            role=UniversalRole.USER,
            content="Hello, world!",
        )
        assert msg.role == UniversalRole.USER
        assert msg.content == "Hello, world!"
        assert msg.tool_calls is None

    def test_message_to_dict(self):
        """Should serialize message to dict."""
        msg = UniversalMessage(
            role=UniversalRole.ASSISTANT,
            content="Response text",
        )
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["content"] == "Response text"

    def test_message_from_dict(self):
        """Should deserialize message from dict."""
        d = {"role": "user", "content": "Test message"}
        msg = UniversalMessage.from_dict(d)
        assert msg.role == UniversalRole.USER
        assert msg.content == "Test message"

    def test_message_with_tool_calls(self):
        """Should handle messages with tool calls."""
        tool_call = UniversalToolCall(
            id="call_123",
            name="get_weather",
            arguments={"location": "NYC"},
        )
        msg = UniversalMessage(
            role=UniversalRole.TOOL_CALL,
            content="",
            tool_calls=[tool_call],
        )
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "get_weather"

    def test_multi_modal_content(self):
        """Should handle multi-modal content blocks."""
        blocks = [
            ContentBlock(type=ContentType.TEXT, content="Look at this:"),
            ContentBlock(type=ContentType.IMAGE_URL, content="https://example.com/img.png"),
        ]
        msg = UniversalMessage(
            role=UniversalRole.USER,
            content=blocks,
        )
        assert len(msg.content) == 2
        assert msg.get_text_content() == "Look at this:"


class TestUniversalToolCall:
    """Tests for UniversalToolCall class."""

    def test_create_tool_call(self):
        """Should create a tool call."""
        tc = UniversalToolCall(
            id="call_abc",
            name="search",
            arguments={"query": "python"},
        )
        assert tc.id == "call_abc"
        assert tc.name == "search"
        assert tc.arguments["query"] == "python"

    def test_tool_call_to_dict(self):
        """Should serialize tool call to dict."""
        tc = UniversalToolCall(id="1", name="test", arguments={"a": 1})
        d = tc.to_dict()
        assert d["id"] == "1"
        assert d["name"] == "test"
        assert d["arguments"] == {"a": 1}

    def test_arguments_hash(self):
        """Should generate consistent hash for arguments."""
        tc1 = UniversalToolCall(id="1", name="test", arguments={"a": 1, "b": 2})
        tc2 = UniversalToolCall(id="2", name="test", arguments={"b": 2, "a": 1})
        # Same arguments, different order should produce same hash
        assert tc1.arguments_hash() == tc2.arguments_hash()


class TestToolDefinition:
    """Tests for ToolDefinition class."""

    def test_create_tool_definition(self):
        """Should create a tool definition."""
        tool = ToolDefinition(
            name="get_weather",
            description="Get current weather",
            parameters=[
                ToolParameter(
                    name="location",
                    type="string",
                    description="City name",
                    required=True,
                ),
            ],
        )
        assert tool.name == "get_weather"
        assert len(tool.parameters) == 1

    def test_to_json_schema(self):
        """Should convert to JSON schema format."""
        tool = ToolDefinition(
            name="search",
            description="Search for items",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query", required=True),
                ToolParameter(name="limit", type="number", description="Max results", required=False),
            ],
        )
        schema = tool.to_json_schema()
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "query" in schema["required"]
        assert "limit" not in schema["required"]


class TestUniversalRequest:
    """Tests for UniversalRequest class."""

    def test_create_simple_request(self):
        """Should create a simple request."""
        request = UniversalRequest(
            messages=[
                UniversalMessage(role=UniversalRole.USER, content="Hello"),
            ],
            model_config=ModelConfig(model="gpt-4"),
        )
        assert len(request.messages) == 1
        assert request.model_config.model == "gpt-4"

    def test_request_to_dict(self):
        """Should serialize request to dict."""
        request = UniversalRequest(
            messages=[UniversalMessage(role=UniversalRole.USER, content="Hi")],
            model_config=ModelConfig(model="claude-3-sonnet"),
        )
        d = request.to_dict()
        assert len(d["messages"]) == 1
        assert d["model_config"]["model"] == "claude-3-sonnet"

    def test_get_system_message(self):
        """Should extract system message."""
        request = UniversalRequest(
            messages=[
                UniversalMessage(role=UniversalRole.SYSTEM, content="You are helpful"),
                UniversalMessage(role=UniversalRole.USER, content="Hi"),
            ],
            model_config=ModelConfig(model="test"),
        )
        assert request.get_system_message() == "You are helpful"

    def test_get_conversation_history(self):
        """Should get non-system messages."""
        request = UniversalRequest(
            messages=[
                UniversalMessage(role=UniversalRole.SYSTEM, content="System"),
                UniversalMessage(role=UniversalRole.USER, content="User 1"),
                UniversalMessage(role=UniversalRole.ASSISTANT, content="Asst 1"),
            ],
            model_config=ModelConfig(model="test"),
        )
        history = request.get_conversation_history()
        assert len(history) == 2
        assert history[0].role == UniversalRole.USER


class TestUniversalResponse:
    """Tests for UniversalResponse class."""

    def test_create_response(self):
        """Should create a response."""
        response = UniversalResponse(
            message=UniversalMessage(role=UniversalRole.ASSISTANT, content="Hello!"),
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            cost=0.001,
            provider="openai",
            model="gpt-4",
        )
        assert response.provider == "openai"
        assert response.cost == 0.001

    def test_response_with_tool_calls(self):
        """Should detect tool calls in response."""
        tc = UniversalToolCall(id="1", name="test", arguments={})
        response = UniversalResponse(
            message=UniversalMessage(role=UniversalRole.TOOL_CALL, content="", tool_calls=[tc]),
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            cost=0.001,
            provider="openai",
            model="gpt-4",
        )
        assert response.has_tool_calls()
        assert len(response.get_tool_calls()) == 1


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_create_text_message_helper(self):
        """Should create text message with helper."""
        msg = create_text_message(UniversalRole.USER, "Hello")
        assert msg.role == UniversalRole.USER
        assert msg.content == "Hello"

    def test_create_tool_result_message_helper(self):
        """Should create tool result message."""
        msg = create_tool_result_message("call_123", "Result data")
        assert msg.role == UniversalRole.TOOL_RESULT
        assert msg.tool_call_id == "call_123"

    def test_messages_json_roundtrip(self):
        """Should serialize and deserialize messages."""
        messages = [
            UniversalMessage(role=UniversalRole.USER, content="Hi"),
            UniversalMessage(role=UniversalRole.ASSISTANT, content="Hello"),
        ]
        json_str = messages_to_json(messages)
        restored = messages_from_json(json_str)
        assert len(restored) == 2
        assert restored[0].content == "Hi"


# ============================================================================
# OpenAI Adapter Tests
# ============================================================================


class TestOpenAIAdapter:
    """Tests for OpenAI adapter."""

    @pytest.fixture
    def adapter(self):
        return OpenAIAdapter()

    def test_to_provider_format_simple(self, adapter):
        """Should convert simple request to OpenAI format."""
        request = UniversalRequest(
            messages=[UniversalMessage(role=UniversalRole.USER, content="Hello")],
            model_config=ModelConfig(model="gpt-4", temperature=0.7),
        )
        result = adapter.to_provider_format(request)

        assert result["model"] == "gpt-4"
        assert result["temperature"] == 0.7
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

    def test_to_provider_format_with_tools(self, adapter):
        """Should include tools in OpenAI format."""
        tool = ToolDefinition(
            name="get_weather",
            description="Get weather",
            parameters=[ToolParameter(name="city", type="string", description="City", required=True)],
        )
        request = UniversalRequest(
            messages=[UniversalMessage(role=UniversalRole.USER, content="Weather?")],
            model_config=ModelConfig(model="gpt-4"),
            tools=[tool],
        )
        result = adapter.to_provider_format(request)

        assert "tools" in result
        assert result["tools"][0]["function"]["name"] == "get_weather"

    def test_to_provider_format_tool_call_message(self, adapter):
        """Should convert tool call messages."""
        tc = UniversalToolCall(id="call_1", name="search", arguments={"q": "test"})
        messages = [
            UniversalMessage(role=UniversalRole.USER, content="Search"),
            UniversalMessage(role=UniversalRole.TOOL_CALL, content="", tool_calls=[tc]),
            UniversalMessage(role=UniversalRole.TOOL_RESULT, content="Results", tool_call_id="call_1"),
        ]
        request = UniversalRequest(messages=messages, model_config=ModelConfig(model="gpt-4"))
        result = adapter.to_provider_format(request)

        assert result["messages"][1]["role"] == "assistant"
        assert "tool_calls" in result["messages"][1]
        assert result["messages"][2]["role"] == "tool"

    def test_from_provider_format(self, adapter):
        """Should parse OpenAI response."""
        openai_response = {
            "id": "chatcmpl-123",
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "gpt-4-0613",
        }
        result = adapter.from_provider_format(openai_response)

        assert result.message.content == "Hello!"
        assert result.usage.input_tokens == 10
        assert result.provider == "openai"

    def test_from_provider_format_with_tool_calls(self, adapter):
        """Should parse tool calls from OpenAI response."""
        openai_response = {
            "id": "chatcmpl-123",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_abc",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city": "NYC"}'},
                    }]
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": "gpt-4",
        }
        result = adapter.from_provider_format(openai_response)

        assert result.has_tool_calls()
        assert result.get_tool_calls()[0].name == "get_weather"
        assert result.finish_reason == "tool_calls"

    def test_calculate_cost_gpt4(self, adapter):
        """Should calculate GPT-4 cost correctly."""
        cost = adapter.calculate_cost("gpt-4", input_tokens=1000, output_tokens=500)
        # GPT-4: $30/1M input, $60/1M output
        expected = (1000 / 1_000_000) * 30 + (500 / 1_000_000) * 60
        assert abs(cost - expected) < 0.0001

    def test_calculate_cost_gpt4o(self, adapter):
        """Should calculate GPT-4o cost correctly."""
        cost = adapter.calculate_cost("gpt-4o", input_tokens=1000, output_tokens=500)
        # GPT-4o: $2.50/1M input, $10/1M output
        expected = (1000 / 1_000_000) * 2.5 + (500 / 1_000_000) * 10
        assert abs(cost - expected) < 0.0001


# ============================================================================
# Anthropic Adapter Tests
# ============================================================================


class TestAnthropicAdapter:
    """Tests for Anthropic adapter."""

    @pytest.fixture
    def adapter(self):
        return AnthropicAdapter()

    def test_to_provider_format_with_system(self, adapter):
        """Should extract system message for Anthropic format."""
        request = UniversalRequest(
            messages=[
                UniversalMessage(role=UniversalRole.SYSTEM, content="You are helpful"),
                UniversalMessage(role=UniversalRole.USER, content="Hi"),
            ],
            model_config=ModelConfig(model="claude-3-sonnet", max_tokens=1000),
        )
        result = adapter.to_provider_format(request)

        assert result["system"] == "You are helpful"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

    def test_to_provider_format_tool_calls(self, adapter):
        """Should convert tool calls to Anthropic format."""
        tc = UniversalToolCall(id="tool_1", name="search", arguments={"q": "test"})
        messages = [
            UniversalMessage(role=UniversalRole.USER, content="Search"),
            UniversalMessage(role=UniversalRole.TOOL_CALL, content="", tool_calls=[tc]),
            UniversalMessage(role=UniversalRole.TOOL_RESULT, content="Results", tool_call_id="tool_1"),
        ]
        request = UniversalRequest(messages=messages, model_config=ModelConfig(model="claude-3", max_tokens=100))
        result = adapter.to_provider_format(request)

        # Tool calls should be in assistant content with tool_use type
        assert result["messages"][1]["role"] == "assistant"
        assert result["messages"][1]["content"][0]["type"] == "tool_use"

        # Tool results should be user messages with tool_result type
        assert result["messages"][2]["role"] == "user"
        assert result["messages"][2]["content"][0]["type"] == "tool_result"

    def test_from_provider_format(self, adapter):
        """Should parse Anthropic response."""
        anthropic_response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello!"}],
            "model": "claude-3-sonnet-20240229",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        result = adapter.from_provider_format(anthropic_response)

        assert result.message.content == "Hello!"
        assert result.finish_reason == "stop"  # Mapped from end_turn
        assert result.provider == "anthropic"

    def test_from_provider_format_with_tool_use(self, adapter):
        """Should parse tool use from Anthropic response."""
        anthropic_response = {
            "id": "msg_123",
            "content": [
                {"type": "text", "text": "Let me check that."},
                {"type": "tool_use", "id": "tool_1", "name": "get_weather", "input": {"city": "NYC"}},
            ],
            "model": "claude-3-sonnet-20240229",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 30},
        }
        result = adapter.from_provider_format(anthropic_response)

        assert result.has_tool_calls()
        assert result.get_tool_calls()[0].name == "get_weather"
        assert "Let me check that." in result.message.content

    def test_validate_messages_alternation(self, adapter):
        """Should ensure proper message alternation."""
        # Two consecutive user messages
        messages = [
            UniversalMessage(role=UniversalRole.USER, content="First"),
            UniversalMessage(role=UniversalRole.USER, content="Second"),
        ]
        validated = adapter.validate_messages(messages)

        # Should be merged
        assert len(validated) == 1
        assert "First" in validated[0].content
        assert "Second" in validated[0].content

    def test_calculate_cost_with_cache(self, adapter):
        """Should calculate cost with cache pricing."""
        cost = adapter.calculate_cost(
            "claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=200,
            cache_creation_tokens=100,
        )
        # Should include cache costs
        assert cost > 0


# ============================================================================
# DeepSeek Adapter Tests
# ============================================================================


class TestDeepSeekAdapter:
    """Tests for DeepSeek adapter."""

    @pytest.fixture
    def adapter(self):
        return DeepSeekAdapter()

    def test_to_provider_format(self, adapter):
        """Should convert to DeepSeek (OpenAI-compatible) format."""
        request = UniversalRequest(
            messages=[UniversalMessage(role=UniversalRole.USER, content="Hello")],
            model_config=ModelConfig(model="deepseek-chat"),
        )
        result = adapter.to_provider_format(request)

        assert result["model"] == "deepseek-chat"
        assert result["messages"][0]["role"] == "user"

    def test_from_provider_format(self, adapter):
        """Should parse DeepSeek response."""
        response = {
            "id": "cmpl-123",
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "prompt_cache_hit_tokens": 3,
            },
            "model": "deepseek-chat",
        }
        result = adapter.from_provider_format(response)

        assert result.message.content == "Hello!"
        assert result.usage.cache_read_tokens == 3
        assert result.provider == "deepseek"

    def test_calculate_cost_with_cache(self, adapter):
        """Should calculate cost with cache discount."""
        cost_no_cache = adapter.calculate_cost("deepseek-chat", 1000, 500, cache_read_tokens=0)
        cost_with_cache = adapter.calculate_cost("deepseek-chat", 1000, 500, cache_read_tokens=500)

        # Cache should reduce cost
        assert cost_with_cache < cost_no_cache


# ============================================================================
# Adapter Factory Tests
# ============================================================================


class TestAdapterFactory:
    """Tests for adapter factory function."""

    def test_get_openai_adapter(self):
        """Should return OpenAI adapter."""
        adapter = get_adapter("openai")
        assert isinstance(adapter, OpenAIAdapter)

    def test_get_anthropic_adapter(self):
        """Should return Anthropic adapter."""
        adapter = get_adapter("anthropic")
        assert isinstance(adapter, AnthropicAdapter)

    def test_get_deepseek_adapter(self):
        """Should return DeepSeek adapter."""
        adapter = get_adapter("deepseek")
        assert isinstance(adapter, DeepSeekAdapter)

    def test_get_unknown_adapter(self):
        """Should raise for unknown provider."""
        with pytest.raises(ValueError) as exc:
            get_adapter("unknown_provider")
        assert "Unknown provider" in str(exc.value)


# ============================================================================
# Cross-Provider Roundtrip Tests
# ============================================================================


class TestCrossProviderRoundtrip:
    """Tests for converting between providers."""

    def test_openai_to_anthropic_message(self):
        """Should convert OpenAI response to Anthropic request format."""
        openai_adapter = OpenAIAdapter()
        anthropic_adapter = AnthropicAdapter()

        # Parse OpenAI response
        openai_response = {
            "id": "cmpl-123",
            "choices": [{"message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "gpt-4",
        }
        universal = openai_adapter.from_provider_format(openai_response)

        # Create new request with the message
        new_request = UniversalRequest(
            messages=[
                UniversalMessage(role=UniversalRole.USER, content="Hi"),
                universal.message,
                UniversalMessage(role=UniversalRole.USER, content="Continue"),
            ],
            model_config=ModelConfig(model="claude-3-sonnet", max_tokens=100),
        )

        # Convert to Anthropic format
        anthropic_format = anthropic_adapter.to_provider_format(new_request)

        assert len(anthropic_format["messages"]) == 3
        assert anthropic_format["messages"][1]["role"] == "assistant"

    def test_tool_call_flow_across_providers(self):
        """Should handle tool calls when switching providers."""
        openai_adapter = OpenAIAdapter()
        anthropic_adapter = AnthropicAdapter()

        # Tool call from OpenAI
        openai_tool_response = {
            "id": "cmpl-123",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "get_data", "arguments": '{"id": 123}'},
                    }]
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": "gpt-4",
        }

        universal = openai_adapter.from_provider_format(openai_tool_response)
        assert universal.has_tool_calls()

        # Create request with tool result for Anthropic
        new_request = UniversalRequest(
            messages=[
                UniversalMessage(role=UniversalRole.USER, content="Get data 123"),
                universal.message,
                create_tool_result_message("call_1", '{"data": "result"}'),
            ],
            model_config=ModelConfig(model="claude-3-sonnet", max_tokens=100),
        )

        anthropic_format = anthropic_adapter.to_provider_format(new_request)

        # Verify tool result is properly formatted for Anthropic
        assert anthropic_format["messages"][-1]["role"] == "user"
        assert anthropic_format["messages"][-1]["content"][0]["type"] == "tool_result"
