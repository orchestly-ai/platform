"""
Model Context Protocol (MCP) Data Models

Implements Anthropic's MCP specification for agent-to-tool communication.

MCP Architecture:
- Client-Server model using JSON-RPC 2.0
- 5 core primitives: Prompts, Resources, Tools, Roots, Sampling
- Transport: stdio, HTTP, SSE
- Protocol: JSON-RPC 2.0 over transport layer

Competitive Advantage:
- Enables universal tool discovery and invocation
- Compatible with Anthropic Claude, OpenAI, and custom LLMs
- Matches LangChain's tool ecosystem with standardized protocol
- Exceeds proprietary solutions with open standard

References:
- Spec: https://spec.modelcontextprotocol.io
- GitHub: https://github.com/modelcontextprotocol
- Docs: https://www.anthropic.com/news/model-context-protocol
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, JSON as SQLJSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY
from pydantic import BaseModel, Field

from backend.database.session import Base


# ============================================================================
# Enums
# ============================================================================

class MCPTransportType(str, Enum):
    """MCP transport mechanisms."""
    STDIO = "stdio"  # Standard I/O (local processes)
    HTTP = "http"  # HTTP/HTTPS
    SSE = "sse"  # Server-Sent Events (streaming over HTTP)
    WEBSOCKET = "websocket"  # WebSocket (bidirectional)


class MCPPrimitiveType(str, Enum):
    """MCP primitive types (server-side and client-side)."""
    # Server primitives
    PROMPT = "prompt"  # Reusable prompt templates
    RESOURCE = "resource"  # Structured data for context
    TOOL = "tool"  # Executable functions

    # Client primitives
    ROOT = "root"  # File system roots
    SAMPLING = "sampling"  # LLM sampling control


class MCPServerStatus(str, Enum):
    """MCP server connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    TIMEOUT = "timeout"


class MCPToolParameterType(str, Enum):
    """JSON Schema types for tool parameters."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"


class MCPRequestMethod(str, Enum):
    """JSON-RPC 2.0 method names for MCP."""
    # Initialization
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"

    # Tool discovery and execution
    LIST_TOOLS = "tools/list"
    CALL_TOOL = "tools/call"

    # Resource discovery and reading
    LIST_RESOURCES = "resources/list"
    READ_RESOURCE = "resources/read"
    SUBSCRIBE_RESOURCE = "resources/subscribe"
    UNSUBSCRIBE_RESOURCE = "resources/unsubscribe"

    # Prompt discovery and execution
    LIST_PROMPTS = "prompts/list"
    GET_PROMPT = "prompts/get"

    # Sampling (client-side)
    CREATE_MESSAGE = "sampling/createMessage"

    # Roots (client-side)
    LIST_ROOTS = "roots/list"

    # Logging
    LOG_MESSAGE = "logging/setLevel"

    # Completion
    COMPLETE = "completion/complete"


# ============================================================================
# Database Models (SQLAlchemy)
# ============================================================================

class MCPServerModel(Base):
    """
    MCP Server Registry.

    Tracks available MCP servers (local or remote) and their capabilities.
    """
    __tablename__ = "mcp_servers"
    __table_args__ = {'extend_existing': True}

    # Identity
    server_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(String(255), nullable=False, index=True)

    # Server info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Connection
    transport_type = Column(String(50), nullable=False)  # stdio, http, sse, websocket
    endpoint_url = Column(String(500), nullable=True)  # For HTTP/SSE/WebSocket
    command = Column(String(500), nullable=True)  # For stdio (e.g., "python server.py")
    args = Column(JSONB, nullable=True)  # Command arguments
    env = Column(JSONB, nullable=True)  # Environment variables

    # Capabilities (discovered during initialization)
    server_info = Column(JSONB, nullable=True)  # From initialize response
    capabilities = Column(JSONB, nullable=True)  # Supported primitives
    protocol_version = Column(String(50), nullable=True)

    # Status
    status = Column(String(50), nullable=False, default="disconnected")
    last_connected_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    # Statistics
    total_requests = Column(Integer, nullable=False, default=0)
    total_errors = Column(Integer, nullable=False, default=0)
    average_latency_ms = Column(Float, nullable=True)

    # Configuration
    timeout_seconds = Column(Integer, nullable=False, default=30)
    retry_attempts = Column(Integer, nullable=False, default=3)
    is_active = Column(Boolean, nullable=False, default=True)

    # Metadata
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class MCPToolModel(Base):
    """
    MCP Tool Registry.

    Discovered tools from MCP servers. Tools are executable functions.
    """
    __tablename__ = "mcp_tools"
    __table_args__ = {'extend_existing': True}

    # Identity
    tool_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    server_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    organization_id = Column(String(255), nullable=False, index=True)

    # Tool definition (from server)
    tool_name = Column(String(255), nullable=False, index=True)  # Unique per server
    description = Column(Text, nullable=True)

    # Input schema (JSON Schema format)
    input_schema = Column(JSONB, nullable=False)  # JSON Schema for parameters

    # Metadata
    tags = Column(ARRAY(String), nullable=True)
    category = Column(String(100), nullable=True)

    # Statistics
    total_invocations = Column(Integer, nullable=False, default=0)
    total_errors = Column(Integer, nullable=False, default=0)
    average_duration_ms = Column(Float, nullable=True)

    # Configuration
    is_enabled = Column(Boolean, nullable=False, default=True)

    # Discovery
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class MCPResourceModel(Base):
    """
    MCP Resource Registry.

    Resources are structured data that can be included in LLM context.
    Examples: files, database records, API responses.
    """
    __tablename__ = "mcp_resources"
    __table_args__ = {'extend_existing': True}

    # Identity
    resource_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    server_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    organization_id = Column(String(255), nullable=False, index=True)

    # Resource definition
    resource_uri = Column(String(500), nullable=False, index=True)  # Unique identifier
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    mime_type = Column(String(100), nullable=True)  # e.g., "text/plain", "application/json"

    # Resource metadata
    size_bytes = Column(Integer, nullable=True)
    annotations = Column(JSONB, nullable=True)  # Additional metadata

    # Caching
    cached_content = Column(Text, nullable=True)  # Cached resource content
    cache_expires_at = Column(DateTime, nullable=True)

    # Statistics
    total_reads = Column(Integer, nullable=False, default=0)

    # Configuration
    is_enabled = Column(Boolean, nullable=False, default=True)

    # Discovery
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_read_at = Column(DateTime, nullable=True)


class MCPPromptModel(Base):
    """
    MCP Prompt Registry.

    Prompts are reusable templates with parameters.
    """
    __tablename__ = "mcp_prompts"
    __table_args__ = {'extend_existing': True}

    # Identity
    prompt_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    server_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    organization_id = Column(String(255), nullable=False, index=True)

    # Prompt definition
    prompt_name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Prompt structure
    arguments = Column(JSONB, nullable=True)  # Parameter definitions

    # Statistics
    total_uses = Column(Integer, nullable=False, default=0)

    # Configuration
    is_enabled = Column(Boolean, nullable=False, default=True)

    # Discovery
    discovered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class MCPRequestLogModel(Base):
    """
    MCP Request Log.

    Logs all JSON-RPC requests/responses for debugging and analytics.
    """
    __tablename__ = "mcp_request_logs"
    __table_args__ = {'extend_existing': True}

    # Identity
    log_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    server_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    organization_id = Column(String(255), nullable=False, index=True)

    # Request details
    method = Column(String(100), nullable=False, index=True)  # JSON-RPC method
    request_id = Column(String(255), nullable=True)  # JSON-RPC request ID

    # Payload
    request_payload = Column(JSONB, nullable=False)
    response_payload = Column(JSONB, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Float, nullable=True)

    # Status
    status = Column(String(50), nullable=False)  # success, error, timeout
    error_code = Column(Integer, nullable=True)  # JSON-RPC error code
    error_message = Column(Text, nullable=True)

    # Context
    workflow_execution_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    # Metadata
    request_extra_metadata = Column(JSONB, nullable=True)


# ============================================================================
# Pydantic Models (API/Business Logic)
# ============================================================================

class MCPToolParameter(BaseModel):
    """Tool parameter definition (JSON Schema)."""
    name: str
    type: MCPToolParameterType
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


class MCPToolDefinition(BaseModel):
    """MCP Tool definition from server."""
    name: str
    description: Optional[str] = None
    input_schema: Dict[str, Any]  # Full JSON Schema

    class Config:
        json_schema_extra = {
            "example": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name or zip code"
                        },
                        "units": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "default": "celsius"
                        }
                    },
                    "required": ["location"]
                }
            }
        }


class MCPResourceDefinition(BaseModel):
    """MCP Resource definition from server."""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None
    annotations: Optional[Dict[str, Any]] = None


class MCPPromptDefinition(BaseModel):
    """MCP Prompt definition from server."""
    name: str
    description: Optional[str] = None
    arguments: Optional[List[Dict[str, Any]]] = None


@dataclass
class MCPServerConfig:
    """Configuration for connecting to an MCP server."""
    server_id: UUID
    name: str
    organization_id: str
    transport_type: MCPTransportType

    # Connection details
    endpoint_url: Optional[str] = None  # For HTTP/SSE/WebSocket
    command: Optional[str] = None  # For stdio
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None

    # Configuration
    timeout_seconds: int = 30
    retry_attempts: int = 3
    is_active: bool = True


@dataclass
class MCPToolInvocation:
    """Result of a tool invocation."""
    tool_name: str
    server_id: UUID
    request_id: str

    # Input/Output
    arguments: Dict[str, Any]
    result: Optional[Any] = None

    # Status
    success: bool = True
    error_message: Optional[str] = None

    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    # Context
    workflow_execution_id: Optional[UUID] = None


@dataclass
class MCPResourceContent:
    """Content read from an MCP resource."""
    uri: str
    server_id: UUID
    content: str
    mime_type: Optional[str] = None

    # Metadata
    read_at: datetime = field(default_factory=datetime.utcnow)
    cached: bool = False


@dataclass
class MCPPromptResult:
    """Result of getting a prompt from MCP server."""
    prompt_name: str
    server_id: UUID

    # Prompt content
    description: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)

    # Context
    arguments_used: Optional[Dict[str, Any]] = None


# ============================================================================
# JSON-RPC 2.0 Message Models
# ============================================================================

class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None  # Can be string or number


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response (success)."""
    jsonrpc: str = "2.0"
    result: Any
    id: Optional[str] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error object."""
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCErrorResponse(BaseModel):
    """JSON-RPC 2.0 Response (error)."""
    jsonrpc: str = "2.0"
    error: JSONRPCError
    id: Optional[str] = None


# JSON-RPC Error Codes (standard + MCP-specific)
class MCPErrorCode(int, Enum):
    """Standard JSON-RPC and MCP-specific error codes."""
    # JSON-RPC standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific errors
    TOOL_NOT_FOUND = -32001
    TOOL_EXECUTION_ERROR = -32002
    RESOURCE_NOT_FOUND = -32003
    RESOURCE_READ_ERROR = -32004
    PROMPT_NOT_FOUND = -32005
    SERVER_TIMEOUT = -32006
    SERVER_UNAVAILABLE = -32007
