"""
MCP (Model Context Protocol) REST API

Endpoints for managing MCP servers, tools, resources, and prompts.

API Groups:
1. Server Management - Register, connect, disconnect MCP servers
2. Tool Operations - Discovery, search, invocation
3. Resource Operations - Discovery, reading, caching
4. Prompt Operations - Discovery, retrieval
5. Analytics - Usage statistics and monitoring

Competitive Advantage:
- Universal tool ecosystem via MCP standard
- Multi-transport support (stdio, HTTP, SSE, WebSocket)
- Intelligent caching and resource management
- Real-time tool discovery across all providers
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from backend.database.session import AsyncSessionLocal, get_db
from backend.shared.auth import get_current_user_id, get_current_organization_id
from backend.shared.mcp_service import (
    MCPClient, ToolDiscoveryService, ResourceManager
)
from backend.shared.mcp_models import (
    MCPServerModel, MCPToolModel, MCPResourceModel, MCPPromptModel,
    MCPTransportType, MCPServerStatus,
    MCPToolDefinition, MCPResourceDefinition, MCPPromptDefinition
)

router = APIRouter(prefix="/mcp", tags=["MCP"])


# ============================================================================
# Request/Response Models
# ============================================================================

class RegisterServerRequest(BaseModel):
    """Request to register a new MCP server."""
    name: str = Field(..., description="Server name")
    description: Optional[str] = Field(None, description="Server description")
    transport_type: MCPTransportType = Field(..., description="Transport mechanism")

    # Connection details
    endpoint_url: Optional[str] = Field(None, description="URL for HTTP/SSE/WebSocket")
    command: Optional[str] = Field(None, description="Command for stdio transport")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")

    # Configuration
    timeout_seconds: int = Field(30, description="Request timeout in seconds")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    is_active: bool = Field(True, description="Whether server is active")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "GitHub MCP Server",
                "description": "Access GitHub repositories and issues",
                "transport_type": "http",
                "endpoint_url": "https://mcp.github.com",
                "timeout_seconds": 30,
                "retry_attempts": 3,
                "is_active": True
            }
        }


class ServerResponse(BaseModel):
    """MCP server details."""
    server_id: UUID
    organization_id: str
    name: str
    description: Optional[str]
    transport_type: str
    status: str

    # Capabilities
    server_info: Optional[Dict[str, Any]]
    capabilities: Optional[Dict[str, Any]]
    protocol_version: Optional[str]

    # Statistics
    total_requests: int
    total_errors: int
    average_latency_ms: Optional[float]
    last_connected_at: Optional[datetime]

    class Config:
        from_attributes = True


class ToolResponse(BaseModel):
    """MCP tool details."""
    tool_id: UUID
    server_id: UUID
    tool_name: str
    description: Optional[str]
    input_schema: Dict[str, Any]
    category: Optional[str]
    tags: Optional[List[str]]

    # Statistics
    total_invocations: int
    total_errors: int
    average_duration_ms: Optional[float]

    class Config:
        from_attributes = True


class InvokeToolRequest(BaseModel):
    """Request to invoke an MCP tool."""
    tool_name: str = Field(..., description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(..., description="Tool arguments")
    server_id: Optional[UUID] = Field(None, description="Specific server to use")

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "get_weather",
                "arguments": {
                    "location": "San Francisco",
                    "units": "celsius"
                }
            }
        }


class ToolInvocationResponse(BaseModel):
    """Result of tool invocation."""
    tool_name: str
    server_id: UUID
    request_id: str
    success: bool
    result: Optional[Any]
    error_message: Optional[str]
    duration_ms: Optional[float]


class ResourceResponse(BaseModel):
    """MCP resource details."""
    resource_id: UUID
    server_id: UUID
    resource_uri: str
    name: str
    description: Optional[str]
    mime_type: Optional[str]
    size_bytes: Optional[int]
    total_reads: int

    class Config:
        from_attributes = True


class ReadResourceRequest(BaseModel):
    """Request to read resource content."""
    resource_uri: str = Field(..., description="URI of the resource")
    server_id: Optional[UUID] = Field(None, description="Specific server to use")
    use_cache: bool = Field(True, description="Whether to use cached content")


class ResourceContentResponse(BaseModel):
    """Resource content."""
    uri: str
    server_id: UUID
    content: str
    mime_type: Optional[str]
    cached: bool


class PromptResponse(BaseModel):
    """MCP prompt details."""
    prompt_id: UUID
    server_id: UUID
    prompt_name: str
    description: Optional[str]
    arguments: Optional[List[Dict[str, Any]]]
    total_uses: int

    class Config:
        from_attributes = True


class GetPromptRequest(BaseModel):
    """Request to get a prompt."""
    prompt_name: str = Field(..., description="Name of the prompt")
    arguments: Optional[Dict[str, Any]] = Field(None, description="Prompt arguments")
    server_id: Optional[UUID] = Field(None, description="Specific server to use")


class PromptResultResponse(BaseModel):
    """Prompt result."""
    prompt_name: str
    server_id: UUID
    description: Optional[str]
    messages: List[Dict[str, Any]]


# ============================================================================
# Server Management Endpoints
# ============================================================================

@router.post("/servers", response_model=ServerResponse, status_code=201)
async def register_server(
    request: RegisterServerRequest,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    Register a new MCP server.

    This adds the server to the registry but does not connect to it yet.
    Use the connect endpoint to establish connection.
    """
    client = MCPClient(db)

    server = await client.register_server(
        name=request.name,
        organization_id=organization_id,
        transport_type=request.transport_type,
        endpoint_url=request.endpoint_url,
        command=request.command,
        args=request.args,
        env=request.env
    )

    return ServerResponse.model_validate(server)


@router.get("/servers", response_model=List[ServerResponse])
async def list_servers(
    status: Optional[MCPServerStatus] = Query(None, description="Filter by status"),
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    List all registered MCP servers.

    Returns servers for the current organization, optionally filtered by status.
    """
    from sqlalchemy import select

    query = select(MCPServerModel).where(
        MCPServerModel.organization_id == organization_id
    )

    if status:
        query = query.where(MCPServerModel.status == status.value)

    result = await db.execute(query)
    servers = result.scalars().all()

    return [ServerResponse.model_validate(s) for s in servers]


@router.get("/servers/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: UUID,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """Get details of a specific MCP server."""
    from sqlalchemy import select

    result = await db.execute(
        select(MCPServerModel).where(
            MCPServerModel.server_id == server_id,
            MCPServerModel.organization_id == organization_id
        )
    )
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    return ServerResponse.model_validate(server)


@router.post("/servers/{server_id}/connect", response_model=ServerResponse)
async def connect_server(
    server_id: UUID,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    Connect to an MCP server.

    This establishes connection, performs handshake, and discovers capabilities.
    After successful connection, tools, resources, and prompts are automatically discovered.
    """
    client = MCPClient(db)

    success = await client.connect_server(server_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to connect to server")

    # Reload server to get updated status
    from sqlalchemy import select
    result = await db.execute(
        select(MCPServerModel).where(MCPServerModel.server_id == server_id)
    )
    server = result.scalar_one()

    return ServerResponse.model_validate(server)


@router.post("/servers/{server_id}/disconnect")
async def disconnect_server(
    server_id: UUID,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """Disconnect from an MCP server."""
    client = MCPClient(db)
    await client.disconnect_server(server_id)

    return {"message": "Server disconnected successfully"}


@router.get("/servers/{server_id}/tools", response_model=List[ToolResponse])
async def list_server_tools(
    server_id: UUID,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    List all tools available from a specific MCP server.

    Returns tools that have been discovered from the specified server.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(MCPToolModel).where(
            MCPToolModel.server_id == server_id,
            MCPToolModel.organization_id == organization_id
        )
    )
    tools = result.scalars().all()

    return [ToolResponse.model_validate(t) for t in tools]


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: UUID,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    Delete an MCP server.

    This also deletes all associated tools, resources, and prompts.
    """
    from sqlalchemy import select, delete

    # Check server exists
    result = await db.execute(
        select(MCPServerModel).where(
            MCPServerModel.server_id == server_id,
            MCPServerModel.organization_id == organization_id
        )
    )
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Disconnect if connected
    client = MCPClient(db)
    await client.disconnect_server(server_id)

    # Delete server and all related data
    await db.execute(delete(MCPToolModel).where(MCPToolModel.server_id == server_id))
    await db.execute(delete(MCPResourceModel).where(MCPResourceModel.server_id == server_id))
    await db.execute(delete(MCPPromptModel).where(MCPPromptModel.server_id == server_id))
    await db.execute(delete(MCPServerModel).where(MCPServerModel.server_id == server_id))
    await db.commit()

    return {"message": "Server deleted successfully"}


# ============================================================================
# Tool Operations Endpoints
# ============================================================================

@router.get("/tools", response_model=List[ToolResponse])
async def list_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    search: Optional[str] = Query(None, description="Search query"),
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    List all available MCP tools.

    Returns tools discovered from all connected servers, with optional filtering.
    """
    client = MCPClient(db)
    discovery_service = ToolDiscoveryService(db, client)

    if search:
        tools = await discovery_service.search_tools(organization_id, search)
    else:
        tools = await discovery_service.list_all_tools(organization_id, category, tags)

    return [ToolResponse.model_validate(t) for t in tools]


@router.get("/tools/{tool_name}", response_model=ToolResponse)
async def get_tool(
    tool_name: str,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """Get details of a specific tool."""
    client = MCPClient(db)
    discovery_service = ToolDiscoveryService(db, client)

    tool = await discovery_service.get_tool_by_name(tool_name, organization_id)

    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    return ToolResponse.model_validate(tool)


@router.post("/tools/invoke", response_model=ToolInvocationResponse)
async def invoke_tool(
    request: InvokeToolRequest,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    Invoke an MCP tool.

    Calls the specified tool with the provided arguments and returns the result.
    """
    client = MCPClient(db)

    result = await client.invoke_tool(
        tool_name=request.tool_name,
        arguments=request.arguments,
        server_id=request.server_id,
        organization_id=organization_id
    )

    return ToolInvocationResponse(
        tool_name=result.tool_name,
        server_id=result.server_id,
        request_id=result.request_id,
        success=result.success,
        result=result.result,
        error_message=result.error_message,
        duration_ms=result.duration_ms
    )


# ============================================================================
# Resource Operations Endpoints
# ============================================================================

@router.get("/resources", response_model=List[ResourceResponse])
async def list_resources(
    mime_type: Optional[str] = Query(None, description="Filter by MIME type"),
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    List all available MCP resources.

    Returns resources discovered from all connected servers.
    """
    client = MCPClient(db)
    resource_manager = ResourceManager(db, client)

    resources = await resource_manager.list_all_resources(organization_id, mime_type)

    return [ResourceResponse.model_validate(r) for r in resources]


@router.post("/resources/read", response_model=ResourceContentResponse)
async def read_resource(
    request: ReadResourceRequest,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    Read content from an MCP resource.

    Returns the resource content, potentially from cache if available.
    """
    client = MCPClient(db)
    resource_manager = ResourceManager(db, client)

    content = await resource_manager.get_resource_content(
        resource_uri=request.resource_uri,
        organization_id=organization_id,
        use_cache=request.use_cache
    )

    return ResourceContentResponse(
        uri=content.uri,
        server_id=content.server_id,
        content=content.content,
        mime_type=content.mime_type,
        cached=content.cached
    )


@router.post("/resources/{resource_uri}/invalidate-cache")
async def invalidate_resource_cache(
    resource_uri: str,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """Invalidate cached content for a resource."""
    client = MCPClient(db)
    resource_manager = ResourceManager(db, client)

    await resource_manager.invalidate_cache(resource_uri, organization_id)

    return {"message": "Cache invalidated successfully"}


# ============================================================================
# Prompt Operations Endpoints
# ============================================================================

@router.get("/prompts", response_model=List[PromptResponse])
async def list_prompts(
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    List all available MCP prompts.

    Returns prompt templates discovered from all connected servers.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(MCPPromptModel).where(
            MCPPromptModel.organization_id == organization_id,
            MCPPromptModel.is_enabled == True
        )
    )
    prompts = result.scalars().all()

    return [PromptResponse.model_validate(p) for p in prompts]


@router.post("/prompts/get", response_model=PromptResultResponse)
async def get_prompt(
    request: GetPromptRequest,
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    Get a prompt template from MCP server.

    Returns the filled prompt with the provided arguments.
    """
    client = MCPClient(db)

    result = await client.get_prompt(
        prompt_name=request.prompt_name,
        arguments=request.arguments,
        server_id=request.server_id
    )

    return PromptResultResponse(
        prompt_name=result.prompt_name,
        server_id=result.server_id,
        description=result.description,
        messages=result.messages
    )


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get("/analytics/servers/summary")
async def get_server_analytics(
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    Get analytics summary for all MCP servers.

    Returns connection statistics, request counts, error rates, etc.
    """
    from sqlalchemy import select, func

    # Get server statistics
    result = await db.execute(
        select(
            func.count(MCPServerModel.server_id).label("total_servers"),
            func.count(MCPServerModel.server_id).filter(
                MCPServerModel.status == MCPServerStatus.CONNECTED.value
            ).label("connected_servers"),
            func.sum(MCPServerModel.total_requests).label("total_requests"),
            func.sum(MCPServerModel.total_errors).label("total_errors"),
            func.avg(MCPServerModel.average_latency_ms).label("avg_latency_ms")
        ).where(
            MCPServerModel.organization_id == organization_id
        )
    )

    stats = result.one()

    # Get tool statistics
    tool_result = await db.execute(
        select(
            func.count(MCPToolModel.tool_id).label("total_tools"),
            func.sum(MCPToolModel.total_invocations).label("total_invocations"),
            func.sum(MCPToolModel.total_errors).label("tool_errors")
        ).where(
            MCPToolModel.organization_id == organization_id
        )
    )

    tool_stats = tool_result.one()

    return {
        "servers": {
            "total": stats.total_servers or 0,
            "connected": stats.connected_servers or 0,
            "total_requests": stats.total_requests or 0,
            "total_errors": stats.total_errors or 0,
            "average_latency_ms": stats.avg_latency_ms or 0
        },
        "tools": {
            "total": tool_stats.total_tools or 0,
            "total_invocations": tool_stats.total_invocations or 0,
            "total_errors": tool_stats.tool_errors or 0
        }
    }


@router.get("/analytics/tools/popular")
async def get_popular_tools(
    limit: int = Query(10, description="Number of tools to return"),
    organization_id: str = Depends(get_current_organization_id),
    db: AsyncSessionLocal = Depends(get_db)
):
    """
    Get most popular tools by invocation count.

    Returns top N tools ordered by usage.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(MCPToolModel)
        .where(MCPToolModel.organization_id == organization_id)
        .order_by(MCPToolModel.total_invocations.desc())
        .limit(limit)
    )

    tools = result.scalars().all()

    return [ToolResponse.model_validate(t) for t in tools]
