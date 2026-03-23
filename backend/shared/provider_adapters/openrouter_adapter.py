"""
OpenRouter Provider Adapter

Handles translation between UniversalRequest/Response and OpenRouter's API format.
OpenRouter uses an OpenAI-compatible API, providing access to 200+ models through
a single API key (https://openrouter.ai/api/v1).
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


class OpenRouterAdapter(ProviderAdapter):
    """
    Adapter for OpenRouter API format.

    OpenRouter uses an OpenAI-compatible API that routes to 200+ models
    from various providers. Model names use provider/model convention
    (e.g., "openai/gpt-4o", "anthropic/claude-3.5-sonnet").
    """

    provider_name = "openrouter"

    # Pricing per 1M tokens (as of early 2025)
    # Uses provider/model naming convention
    PRICING = {
        # OpenAI models
        "openai/gpt-4o": {"input": 2.50, "output": 10.00},
        "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "openai/gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "openai/o1": {"input": 15.00, "output": 60.00},
        "openai/o1-mini": {"input": 3.00, "output": 12.00},
        # Anthropic models
        "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
        "anthropic/claude-3-opus": {"input": 15.00, "output": 75.00},
        "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
        # Meta Llama models
        "meta-llama/llama-3.1-405b-instruct": {"input": 2.70, "output": 2.70},
        "meta-llama/llama-3.1-70b-instruct": {"input": 0.52, "output": 0.75},
        "meta-llama/llama-3.1-8b-instruct": {"input": 0.055, "output": 0.055},
        # Google models
        "google/gemini-pro-1.5": {"input": 2.50, "output": 10.00},
        "google/gemini-flash-1.5": {"input": 0.075, "output": 0.30},
        # Mistral models
        "mistralai/mistral-large": {"input": 2.00, "output": 6.00},
        "mistralai/mixtral-8x7b-instruct": {"input": 0.24, "output": 0.24},
    }

    def to_provider_format(self, request: UniversalRequest) -> Dict[str, Any]:
        """Convert UniversalRequest to OpenRouter API format (OpenAI-compatible)."""
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
        """Convert UniversalMessages to OpenRouter message format."""
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
        """Convert OpenRouter response to UniversalResponse."""
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

        input_tokens = usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("completion_tokens", 0)

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        model = response.get("model", "")

        # OpenRouter may include cost in usage data
        response_cost = usage_data.get("cost")
        if response_cost is not None:
            cost = float(response_cost)
        else:
            cost = self.calculate_cost(model, input_tokens, output_tokens)

        return UniversalResponse(
            message=message,
            usage=usage,
            cost=cost,
            provider=self.provider_name,
            model=model,
            finish_reason=choice.get("finish_reason"),
            latency_ms=latency_ms,
            request_id=response.get("id"),
            metadata={},
        )

    def validate_messages(self, messages: List[UniversalMessage]) -> List[UniversalMessage]:
        """Validate messages for OpenRouter (minimal requirements)."""
        return messages

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Calculate cost for OpenRouter API call."""
        pricing = self._get_pricing(model)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def _get_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for model."""
        # Direct match
        if model in self.PRICING:
            return self.PRICING[model]

        # Partial match (model name may include version suffixes)
        for model_key, prices in self.PRICING.items():
            if model.startswith(model_key) or model_key in model:
                return prices

        # Default to a reasonable mid-range pricing
        return {"input": 1.00, "output": 2.00}

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for a specific model."""
        return self._get_pricing(model)
