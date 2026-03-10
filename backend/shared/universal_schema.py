#!/usr/bin/env python3
"""
Universal Schema for Provider Normalization

Implements ROADMAP.md Section: Provider Normalization Layer

Features:
- UniversalRequest/Response that works with any provider
- Provider adapters for OpenAI, Anthropic, DeepSeek, Google
- No raw provider JSON in persistent state
- Tool call normalization across providers
- Streaming support abstraction

Key Design Decisions:
- All messages use UniversalRole enum for consistency
- Tool calls use a unified format regardless of provider
- Provider-specific quirks handled in adapters
- Metadata preserved for debugging without polluting core schema
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from enum import Enum
from datetime import datetime
import json
import hashlib


class UniversalRole(str, Enum):
    """Universal role types for messages."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class ContentType(str, Enum):
    """Content types for multi-modal support."""
    TEXT = "text"
    IMAGE_URL = "image_url"
    IMAGE_BASE64 = "image_base64"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class ContentBlock:
    """A block of content (text, image, etc.)."""
    type: ContentType
    content: str  # Text or URL or base64
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentBlock":
        return cls(
            type=ContentType(data["type"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class UniversalToolCall:
    """A tool/function call in universal format."""
    id: str
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UniversalToolCall":
        return cls(
            id=data["id"],
            name=data["name"],
            arguments=data["arguments"],
        )

    def arguments_hash(self) -> str:
        """Hash of arguments for duplicate detection."""
        return hashlib.md5(json.dumps(self.arguments, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class UniversalMessage:
    """A message in universal format."""
    role: UniversalRole
    content: Union[str, List[ContentBlock]]
    tool_calls: Optional[List[UniversalToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # For tool results
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "role": self.role.value,
        }

        if isinstance(self.content, str):
            result["content"] = self.content
        else:
            result["content"] = [block.to_dict() for block in self.content]

        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.name:
            result["name"] = self.name
        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UniversalMessage":
        content = data["content"]
        if isinstance(content, list):
            content = [ContentBlock.from_dict(block) for block in content]

        tool_calls = None
        if "tool_calls" in data:
            tool_calls = [UniversalToolCall.from_dict(tc) for tc in data["tool_calls"]]

        return cls(
            role=UniversalRole(data["role"]),
            content=content,
            tool_calls=tool_calls,
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
            metadata=data.get("metadata", {}),
        )

    def get_text_content(self) -> str:
        """Extract text content from message."""
        if isinstance(self.content, str):
            return self.content
        return " ".join(
            block.content for block in self.content
            if block.type == ContentType.TEXT
        )


@dataclass
class ToolParameter:
    """A parameter for a tool definition."""
    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = False
    enum: Optional[List[str]] = None
    default: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            result["enum"] = self.enum
        if self.default is not None:
            result["default"] = self.default
        return result


@dataclass
class ToolDefinition:
    """A tool/function definition in universal format."""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    returns: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters],
            "returns": self.returns,
        }

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format (for OpenAI compatibility)."""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolDefinition":
        params = [
            ToolParameter(
                name=p["name"],
                type=p["type"],
                description=p["description"],
                required=p.get("required", False),
                enum=p.get("enum"),
                default=p.get("default"),
            )
            for p in data.get("parameters", [])
        ]
        return cls(
            name=data["name"],
            description=data["description"],
            parameters=params,
            returns=data.get("returns"),
        )


@dataclass
class ModelConfig:
    """Configuration for model inference."""
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: Optional[List[str]] = None
    seed: Optional[int] = None
    response_format: Optional[str] = None  # "text" or "json_object"

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
        }
        if self.stop_sequences:
            result["stop_sequences"] = self.stop_sequences
        if self.seed is not None:
            result["seed"] = self.seed
        if self.response_format:
            result["response_format"] = self.response_format
        return result


@dataclass
class TokenUsage:
    """Token usage statistics."""
    input_tokens: int
    output_tokens: int
    total_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_creation_tokens: Optional[int] = None

    def __post_init__(self):
        if self.total_tokens is None:
            self.total_tokens = self.input_tokens + self.output_tokens

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }
        if self.cache_read_tokens is not None:
            result["cache_read_tokens"] = self.cache_read_tokens
        if self.cache_creation_tokens is not None:
            result["cache_creation_tokens"] = self.cache_creation_tokens
        return result


@dataclass
class UniversalRequest:
    """A request in universal format."""
    messages: List[UniversalMessage]
    model_config: ModelConfig
    tools: List[ToolDefinition] = field(default_factory=list)
    tool_choice: Optional[str] = None  # "auto", "none", "required", or tool name
    stream: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages": [m.to_dict() for m in self.messages],
            "model_config": self.model_config.to_dict(),
            "tools": [t.to_dict() for t in self.tools],
            "tool_choice": self.tool_choice,
            "stream": self.stream,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UniversalRequest":
        messages = [UniversalMessage.from_dict(m) for m in data["messages"]]
        tools = [ToolDefinition.from_dict(t) for t in data.get("tools", [])]

        model_config = ModelConfig(
            model=data["model_config"]["model"],
            temperature=data["model_config"].get("temperature", 0.7),
            max_tokens=data["model_config"].get("max_tokens", 4096),
            top_p=data["model_config"].get("top_p", 1.0),
            frequency_penalty=data["model_config"].get("frequency_penalty", 0.0),
            presence_penalty=data["model_config"].get("presence_penalty", 0.0),
            stop_sequences=data["model_config"].get("stop_sequences"),
            seed=data["model_config"].get("seed"),
            response_format=data["model_config"].get("response_format"),
        )

        return cls(
            messages=messages,
            model_config=model_config,
            tools=tools,
            tool_choice=data.get("tool_choice"),
            stream=data.get("stream", False),
            metadata=data.get("metadata", {}),
        )

    def get_system_message(self) -> Optional[str]:
        """Extract system message content."""
        for msg in self.messages:
            if msg.role == UniversalRole.SYSTEM:
                return msg.get_text_content()
        return None

    def get_conversation_history(self) -> List[UniversalMessage]:
        """Get all non-system messages."""
        return [m for m in self.messages if m.role != UniversalRole.SYSTEM]


@dataclass
class UniversalResponse:
    """A response in universal format."""
    message: UniversalMessage
    usage: TokenUsage
    cost: float
    provider: str
    model: str
    finish_reason: Optional[str] = None  # "stop", "tool_calls", "length", "content_filter"
    latency_ms: Optional[float] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message.to_dict(),
            "usage": self.usage.to_dict(),
            "cost": self.cost,
            "provider": self.provider,
            "model": self.model,
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UniversalResponse":
        message = UniversalMessage.from_dict(data["message"])
        usage = TokenUsage(
            input_tokens=data["usage"]["input_tokens"],
            output_tokens=data["usage"]["output_tokens"],
            total_tokens=data["usage"].get("total_tokens"),
            cache_read_tokens=data["usage"].get("cache_read_tokens"),
            cache_creation_tokens=data["usage"].get("cache_creation_tokens"),
        )

        return cls(
            message=message,
            usage=usage,
            cost=data["cost"],
            provider=data["provider"],
            model=data["model"],
            finish_reason=data.get("finish_reason"),
            latency_ms=data.get("latency_ms"),
            request_id=data.get("request_id"),
            metadata=data.get("metadata", {}),
        )

    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.message.tool_calls)

    def get_tool_calls(self) -> List[UniversalToolCall]:
        """Get tool calls from response."""
        return self.message.tool_calls or []


@dataclass
class StreamChunk:
    """A streaming response chunk."""
    content: str
    is_final: bool = False
    tool_call_delta: Optional[Dict[str, Any]] = None
    usage: Optional[TokenUsage] = None
    finish_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "content": self.content,
            "is_final": self.is_final,
        }
        if self.tool_call_delta:
            result["tool_call_delta"] = self.tool_call_delta
        if self.usage:
            result["usage"] = self.usage.to_dict()
        if self.finish_reason:
            result["finish_reason"] = self.finish_reason
        return result


class ProviderAdapter:
    """
    Base class for provider-specific adapters.

    Adapters handle the translation between UniversalRequest/Response
    and provider-specific formats.
    """

    provider_name: str = "base"

    def to_provider_format(self, request: UniversalRequest) -> Dict[str, Any]:
        """Convert UniversalRequest to provider-specific format."""
        raise NotImplementedError

    def from_provider_format(self, response: Dict[str, Any], latency_ms: float = 0) -> UniversalResponse:
        """Convert provider response to UniversalResponse."""
        raise NotImplementedError

    def validate_messages(self, messages: List[UniversalMessage]) -> List[UniversalMessage]:
        """
        Validate and transform messages for this provider.

        Some providers have specific requirements (e.g., Anthropic requires
        alternating user/assistant messages).
        """
        return messages

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Calculate cost based on token usage."""
        raise NotImplementedError

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing info for a model (per 1M tokens)."""
        raise NotImplementedError


# Helper functions

def create_text_message(role: UniversalRole, content: str, **kwargs) -> UniversalMessage:
    """Create a simple text message."""
    return UniversalMessage(role=role, content=content, **kwargs)


def create_tool_result_message(
    tool_call_id: str,
    content: str,
    name: Optional[str] = None,
) -> UniversalMessage:
    """Create a tool result message."""
    return UniversalMessage(
        role=UniversalRole.TOOL_RESULT,
        content=content,
        tool_call_id=tool_call_id,
        name=name,
    )


def create_tool_call_message(
    tool_calls: List[UniversalToolCall],
    content: str = "",
) -> UniversalMessage:
    """Create a tool call message."""
    return UniversalMessage(
        role=UniversalRole.TOOL_CALL,
        content=content,
        tool_calls=tool_calls,
    )


def messages_to_json(messages: List[UniversalMessage]) -> str:
    """Serialize messages to JSON for storage."""
    return json.dumps([m.to_dict() for m in messages])


def messages_from_json(json_str: str) -> List[UniversalMessage]:
    """Deserialize messages from JSON."""
    data = json.loads(json_str)
    return [UniversalMessage.from_dict(m) for m in data]
