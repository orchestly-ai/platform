"""
OpenAI Provider Adapter

Handles translation between UniversalRequest/Response and OpenAI's API format.
Supports GPT-4, GPT-4 Turbo, GPT-4o, and GPT-3.5 models.
"""

import json
from typing import Dict, Any, List, Optional
from uuid import uuid4

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


class OpenAIAdapter(ProviderAdapter):
    """Adapter for OpenAI API format."""

    provider_name = "openai"

    # Pricing per 1M tokens (as of Dec 2024)
    PRICING = {
        # GPT-4o
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
        # GPT-4 Turbo
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4-turbo-2024-04-09": {"input": 10.00, "output": 30.00},
        "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
        # GPT-4
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-4-0613": {"input": 30.00, "output": 60.00},
        # GPT-3.5
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50},
        # o1 models
        "o1-preview": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 3.00, "output": 12.00},
    }

    def to_provider_format(self, request: UniversalRequest) -> Dict[str, Any]:
        """Convert UniversalRequest to OpenAI API format."""
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
                # Specific tool name
                payload["tool_choice"] = {
                    "type": "function",
                    "function": {"name": request.tool_choice}
                }

        if request.stream:
            payload["stream"] = True

        if request.model_config.stop_sequences:
            payload["stop"] = request.model_config.stop_sequences

        if request.model_config.seed is not None:
            payload["seed"] = request.model_config.seed

        if request.model_config.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        return payload

    def _convert_messages(self, messages: List[UniversalMessage]) -> List[Dict[str, Any]]:
        """Convert UniversalMessages to OpenAI message format."""
        result = []

        for msg in messages:
            if msg.role == UniversalRole.SYSTEM:
                result.append({
                    "role": "system",
                    "content": self._get_content(msg),
                })

            elif msg.role == UniversalRole.USER:
                content = self._get_content(msg)
                if isinstance(msg.content, list):
                    # Multi-modal content
                    content = self._convert_multi_modal(msg.content)
                result.append({"role": "user", "content": content})

            elif msg.role == UniversalRole.ASSISTANT:
                result.append({
                    "role": "assistant",
                    "content": self._get_content(msg),
                })

            elif msg.role == UniversalRole.TOOL_CALL:
                # Assistant message with tool calls
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

    def _convert_multi_modal(self, content: List[ContentBlock]) -> List[Dict[str, Any]]:
        """Convert multi-modal content to OpenAI format."""
        result = []
        for block in content:
            if block.type == ContentType.TEXT:
                result.append({"type": "text", "text": block.content})
            elif block.type == ContentType.IMAGE_URL:
                result.append({
                    "type": "image_url",
                    "image_url": {"url": block.content}
                })
            elif block.type == ContentType.IMAGE_BASE64:
                media_type = block.metadata.get("media_type", "image/png")
                result.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{block.content}"}
                })
        return result

    def _convert_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Convert ToolDefinitions to OpenAI function format."""
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
        """Convert OpenAI response to UniversalResponse."""
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
        role = UniversalRole.ASSISTANT
        if tool_calls:
            role = UniversalRole.TOOL_CALL

        message = UniversalMessage(
            role=role,
            content=message_data.get("content", ""),
            tool_calls=tool_calls,
        )

        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )

        model = response.get("model", "unknown")
        cost = self.calculate_cost(model, usage.input_tokens, usage.output_tokens)

        return UniversalResponse(
            message=message,
            usage=usage,
            cost=cost,
            provider=self.provider_name,
            model=model,
            finish_reason=choice.get("finish_reason"),
            latency_ms=latency_ms,
            request_id=response.get("id"),
        )

    def validate_messages(self, messages: List[UniversalMessage]) -> List[UniversalMessage]:
        """Validate messages for OpenAI (no specific requirements)."""
        return messages

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Calculate cost for OpenAI API call."""
        # Find matching pricing (handle model variants)
        # First try exact match, then prefix match (longest first)
        pricing = self.PRICING.get(model)

        if not pricing:
            # Try prefix matching, preferring longer model keys
            sorted_keys = sorted(self.PRICING.keys(), key=len, reverse=True)
            for model_key in sorted_keys:
                if model.startswith(model_key) or model_key.startswith(model):
                    pricing = self.PRICING[model_key]
                    break

        if not pricing:
            # Default to gpt-4o pricing if unknown
            pricing = self.PRICING["gpt-4o"]

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for a specific model."""
        for model_key, prices in self.PRICING.items():
            if model.startswith(model_key) or model_key.startswith(model):
                return prices
        return self.PRICING["gpt-4o"]
