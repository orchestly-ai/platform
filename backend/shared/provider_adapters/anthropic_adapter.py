"""
Anthropic Provider Adapter

Handles translation between UniversalRequest/Response and Anthropic's API format.
Supports Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku, and Claude 3.5 Haiku.
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


class AnthropicAdapter(ProviderAdapter):
    """Adapter for Anthropic Claude API format."""

    provider_name = "anthropic"

    # Pricing per 1M tokens (as of Dec 2024)
    PRICING = {
        # Claude 3.5 Sonnet
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
        "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
        # Claude 3.5 Haiku
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00, "cache_write": 1.00, "cache_read": 0.08},
        "claude-3-5-haiku-latest": {"input": 0.80, "output": 4.00, "cache_write": 1.00, "cache_read": 0.08},
        # Claude 3 Opus
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
        "claude-3-opus-latest": {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
        # Claude 3 Sonnet (older)
        "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
        # Claude 3 Haiku (older)
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25, "cache_write": 0.30, "cache_read": 0.03},
    }

    def to_provider_format(self, request: UniversalRequest) -> Dict[str, Any]:
        """Convert UniversalRequest to Anthropic API format."""
        # Extract system message separately (Anthropic requires separate system param)
        system_content = None
        messages = []

        for msg in request.messages:
            if msg.role == UniversalRole.SYSTEM:
                system_content = self._get_content(msg)
            else:
                messages.append(msg)

        # Validate and ensure alternating user/assistant pattern
        messages = self.validate_messages(messages)

        # Convert messages
        anthropic_messages = self._convert_messages(messages)

        # Build payload
        payload = {
            "model": request.model_config.model,
            "max_tokens": request.model_config.max_tokens,
            "messages": anthropic_messages,
        }

        if system_content:
            payload["system"] = system_content

        # Temperature (Anthropic uses 0-1 scale)
        if request.model_config.temperature is not None:
            payload["temperature"] = min(1.0, max(0.0, request.model_config.temperature))

        if request.model_config.top_p is not None:
            payload["top_p"] = request.model_config.top_p

        if request.model_config.stop_sequences:
            payload["stop_sequences"] = request.model_config.stop_sequences

        # Tools
        if request.tools:
            payload["tools"] = self._convert_tools(request.tools)

        if request.tool_choice:
            if request.tool_choice == "none":
                # Anthropic doesn't have explicit "none", just don't send tools
                payload.pop("tools", None)
            elif request.tool_choice == "required":
                payload["tool_choice"] = {"type": "any"}
            elif request.tool_choice == "auto":
                payload["tool_choice"] = {"type": "auto"}
            else:
                # Specific tool
                payload["tool_choice"] = {"type": "tool", "name": request.tool_choice}

        if request.stream:
            payload["stream"] = True

        return payload

    def _convert_messages(self, messages: List[UniversalMessage]) -> List[Dict[str, Any]]:
        """Convert UniversalMessages to Anthropic message format."""
        result = []

        for msg in messages:
            if msg.role == UniversalRole.USER:
                content = self._format_content(msg)
                result.append({"role": "user", "content": content})

            elif msg.role == UniversalRole.ASSISTANT:
                content = self._format_content(msg)
                result.append({"role": "assistant", "content": content})

            elif msg.role == UniversalRole.TOOL_CALL:
                # In Anthropic, tool calls are part of assistant content
                content = []
                if msg.content:
                    text_content = self._get_content(msg)
                    if text_content:
                        content.append({"type": "text", "text": text_content})

                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })

                result.append({"role": "assistant", "content": content})

            elif msg.role == UniversalRole.TOOL_RESULT:
                # Tool results in Anthropic are user messages with tool_result content
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": self._get_content(msg),
                    }]
                })

        return result

    def _format_content(self, msg: UniversalMessage) -> Any:
        """Format message content for Anthropic."""
        if isinstance(msg.content, str):
            return msg.content

        # Multi-modal content
        result = []
        for block in msg.content:
            if block.type == ContentType.TEXT:
                result.append({"type": "text", "text": block.content})
            elif block.type == ContentType.IMAGE_URL:
                # Anthropic requires base64 for images, but we'll pass URL in source
                result.append({
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": block.content,
                    }
                })
            elif block.type == ContentType.IMAGE_BASE64:
                media_type = block.metadata.get("media_type", "image/png")
                result.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": block.content,
                    }
                })
        return result if result else ""

    def _get_content(self, msg: UniversalMessage) -> str:
        """Extract string content from message."""
        if isinstance(msg.content, str):
            return msg.content
        return msg.get_text_content()

    def _convert_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Convert ToolDefinitions to Anthropic tool format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.to_json_schema(),
            }
            for tool in tools
        ]

    def from_provider_format(
        self,
        response: Dict[str, Any],
        latency_ms: float = 0,
    ) -> UniversalResponse:
        """Convert Anthropic response to UniversalResponse."""
        content_blocks = response.get("content", [])
        usage_data = response.get("usage", {})

        # Parse content and tool calls
        text_content = ""
        tool_calls = []

        for block in content_blocks:
            if block["type"] == "text":
                text_content += block.get("text", "")
            elif block["type"] == "tool_use":
                tool_calls.append(UniversalToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=block.get("input", {}),
                ))

        # Determine role
        role = UniversalRole.TOOL_CALL if tool_calls else UniversalRole.ASSISTANT

        message = UniversalMessage(
            role=role,
            content=text_content,
            tool_calls=tool_calls if tool_calls else None,
        )

        # Token usage
        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)
        cache_read = usage_data.get("cache_read_input_tokens", 0)
        cache_creation = usage_data.get("cache_creation_input_tokens", 0)

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )

        model = response.get("model", "unknown")
        cost = self.calculate_cost(
            model, input_tokens, output_tokens, cache_read, cache_creation
        )

        # Map stop reason
        stop_reason = response.get("stop_reason")
        finish_reason = self._map_stop_reason(stop_reason)

        return UniversalResponse(
            message=message,
            usage=usage,
            cost=cost,
            provider=self.provider_name,
            model=model,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            request_id=response.get("id"),
        )

    def _map_stop_reason(self, stop_reason: Optional[str]) -> Optional[str]:
        """Map Anthropic stop_reason to universal finish_reason."""
        mapping = {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
            "max_tokens": "length",
            "content_filter": "content_filter",
        }
        return mapping.get(stop_reason, stop_reason)

    def validate_messages(self, messages: List[UniversalMessage]) -> List[UniversalMessage]:
        """
        Validate and fix messages for Anthropic requirements.

        Anthropic requires:
        1. Messages must alternate between user and assistant
        2. First message must be from user
        3. Cannot have consecutive messages from same role
        """
        if not messages:
            return messages

        validated = []
        last_role = None

        for msg in messages:
            # Skip system messages (handled separately)
            if msg.role == UniversalRole.SYSTEM:
                continue

            # Map tool results to user role for alternation check
            effective_role = "user" if msg.role in (UniversalRole.USER, UniversalRole.TOOL_RESULT) else "assistant"

            if last_role == effective_role:
                # Merge with previous message or skip
                if effective_role == "user" and validated:
                    # For consecutive user messages, combine content
                    prev = validated[-1]
                    if isinstance(prev.content, str) and isinstance(msg.content, str):
                        validated[-1] = UniversalMessage(
                            role=prev.role,
                            content=prev.content + "\n" + msg.content,
                            metadata=prev.metadata,
                        )
                        continue
            else:
                # If first message is assistant, prepend empty user message
                if not validated and effective_role == "assistant":
                    validated.append(UniversalMessage(
                        role=UniversalRole.USER,
                        content="Continue from previous context.",
                    ))

            validated.append(msg)
            last_role = effective_role

        return validated

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Calculate cost for Anthropic API call with cache support."""
        pricing = self._get_pricing(model)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        cache_read_cost = (cache_read_tokens / 1_000_000) * pricing.get("cache_read", pricing["input"] * 0.1)
        cache_write_cost = (cache_creation_tokens / 1_000_000) * pricing.get("cache_write", pricing["input"] * 1.25)

        return input_cost + output_cost + cache_read_cost + cache_write_cost

    def _get_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for model, with fallback."""
        for model_key, prices in self.PRICING.items():
            if model.startswith(model_key) or model_key.startswith(model):
                return prices

        # Default to Claude 3.5 Sonnet pricing
        return self.PRICING["claude-3-5-sonnet-20241022"]

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for a specific model."""
        return self._get_pricing(model)
