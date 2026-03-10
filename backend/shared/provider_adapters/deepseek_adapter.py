"""
DeepSeek Provider Adapter

Handles translation between UniversalRequest/Response and DeepSeek's API format.
DeepSeek uses an OpenAI-compatible API, so this adapter extends OpenAI patterns.
"""

import json
from typing import Dict, Any, List, Optional

from backend.shared.universal_schema import (
    ProviderAdapter,
    UniversalRequest,
    UniversalResponse,
    UniversalMessage,
    UniversalRole,
    UniversalToolCall,
    ToolDefinition,
    TokenUsage,
    ContentBlock,
    ContentType,
)


class DeepSeekAdapter(ProviderAdapter):
    """
    Adapter for DeepSeek API format.

    DeepSeek uses an OpenAI-compatible API with some differences:
    - Different model names
    - Different pricing
    - Some parameter differences
    """

    provider_name = "deepseek"

    # Pricing per 1M tokens (as of Dec 2024)
    # DeepSeek is significantly cheaper than OpenAI
    PRICING = {
        # DeepSeek Chat
        "deepseek-chat": {"input": 0.14, "output": 0.28},
        # DeepSeek Coder
        "deepseek-coder": {"input": 0.14, "output": 0.28},
        # DeepSeek V3 (latest)
        "deepseek-v3": {"input": 0.27, "output": 1.10},
        # DeepSeek Reasoner (R1)
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    }

    # Cache pricing (DeepSeek offers cache discounts)
    CACHE_PRICING = {
        "deepseek-chat": {"cache_hit": 0.014},  # 90% discount
        "deepseek-coder": {"cache_hit": 0.014},
        "deepseek-v3": {"cache_hit": 0.027},
        "deepseek-reasoner": {"cache_hit": 0.055},
    }

    def to_provider_format(self, request: UniversalRequest) -> Dict[str, Any]:
        """Convert UniversalRequest to DeepSeek API format (OpenAI-compatible)."""
        messages = self._convert_messages(request.messages)
        tools = self._convert_tools(request.tools) if request.tools else None

        payload = {
            "model": request.model_config.model,
            "messages": messages,
            "temperature": request.model_config.temperature,
            "max_tokens": request.model_config.max_tokens,
            "top_p": request.model_config.top_p,
            "frequency_penalty": request.model_config.frequency_penalty,
            "presence_penalty": request.model_config.presence_penalty,
        }

        if tools:
            payload["tools"] = tools

        if request.tool_choice:
            if request.tool_choice in ("auto", "none", "required"):
                payload["tool_choice"] = request.tool_choice
            else:
                payload["tool_choice"] = {
                    "type": "function",
                    "function": {"name": request.tool_choice}
                }

        if request.stream:
            payload["stream"] = True

        if request.model_config.stop_sequences:
            payload["stop"] = request.model_config.stop_sequences

        if request.model_config.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        return payload

    def _convert_messages(self, messages: List[UniversalMessage]) -> List[Dict[str, Any]]:
        """Convert UniversalMessages to DeepSeek message format."""
        result = []

        for msg in messages:
            if msg.role == UniversalRole.SYSTEM:
                result.append({
                    "role": "system",
                    "content": self._get_content(msg),
                })

            elif msg.role == UniversalRole.USER:
                content = self._get_content(msg)
                # DeepSeek has limited multi-modal support
                if isinstance(msg.content, list):
                    # Extract text only for now
                    content = msg.get_text_content()
                result.append({"role": "user", "content": content})

            elif msg.role == UniversalRole.ASSISTANT:
                result.append({
                    "role": "assistant",
                    "content": self._get_content(msg),
                })

            elif msg.role == UniversalRole.TOOL_CALL:
                openai_msg = {"role": "assistant"}
                if msg.content:
                    openai_msg["content"] = self._get_content(msg)

                if msg.tool_calls:
                    openai_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                result.append(openai_msg)

            elif msg.role == UniversalRole.TOOL_RESULT:
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": self._get_content(msg),
                })

        return result

    def _get_content(self, msg: UniversalMessage) -> str:
        """Extract string content from message."""
        if isinstance(msg.content, str):
            return msg.content
        return msg.get_text_content()

    def _convert_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Convert ToolDefinitions to OpenAI-compatible function format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.to_json_schema(),
                }
            }
            for tool in tools
        ]

    def from_provider_format(
        self,
        response: Dict[str, Any],
        latency_ms: float = 0,
    ) -> UniversalResponse:
        """Convert DeepSeek response to UniversalResponse."""
        choice = response["choices"][0]
        message_data = choice["message"]
        usage_data = response.get("usage", {})

        # Parse tool calls if present
        tool_calls = None
        if "tool_calls" in message_data and message_data["tool_calls"]:
            tool_calls = [
                UniversalToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                )
                for tc in message_data["tool_calls"]
            ]

        # Determine role
        role = UniversalRole.TOOL_CALL if tool_calls else UniversalRole.ASSISTANT

        message = UniversalMessage(
            role=role,
            content=message_data.get("content", ""),
            tool_calls=tool_calls,
        )

        # DeepSeek includes cache info in usage
        input_tokens = usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("completion_tokens", 0)
        cache_hit_tokens = usage_data.get("prompt_cache_hit_tokens", 0)
        cache_miss_tokens = usage_data.get("prompt_cache_miss_tokens", 0)

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_hit_tokens,
        )

        model = response.get("model", "deepseek-chat")
        cost = self.calculate_cost(
            model, input_tokens, output_tokens, cache_hit_tokens
        )

        return UniversalResponse(
            message=message,
            usage=usage,
            cost=cost,
            provider=self.provider_name,
            model=model,
            finish_reason=choice.get("finish_reason"),
            latency_ms=latency_ms,
            request_id=response.get("id"),
            metadata={
                "cache_hit_tokens": cache_hit_tokens,
                "cache_miss_tokens": cache_miss_tokens,
            },
        )

    def validate_messages(self, messages: List[UniversalMessage]) -> List[UniversalMessage]:
        """Validate messages for DeepSeek (minimal requirements)."""
        # DeepSeek is quite flexible like OpenAI
        return messages

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Calculate cost for DeepSeek API call with cache support."""
        pricing = self._get_pricing(model)
        cache_pricing = self._get_cache_pricing(model)

        # Non-cached input tokens
        non_cached_input = max(0, input_tokens - cache_read_tokens)

        input_cost = (non_cached_input / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        cache_cost = (cache_read_tokens / 1_000_000) * cache_pricing.get("cache_hit", pricing["input"] * 0.1)

        return input_cost + output_cost + cache_cost

    def _get_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for model."""
        for model_key, prices in self.PRICING.items():
            if model.startswith(model_key) or model_key in model:
                return prices
        # Default to deepseek-chat
        return self.PRICING["deepseek-chat"]

    def _get_cache_pricing(self, model: str) -> Dict[str, float]:
        """Get cache pricing for model."""
        for model_key, prices in self.CACHE_PRICING.items():
            if model.startswith(model_key) or model_key in model:
                return prices
        return self.CACHE_PRICING["deepseek-chat"]

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for a specific model."""
        return self._get_pricing(model)
