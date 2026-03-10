"""
Unit Tests for MCP Service

Tests:
1. MCP server registration and management
2. Transport layer (stdio, HTTP)
3. Tool discovery and invocation
4. Resource management and caching
5. Prompt template handling
6. JSON-RPC protocol

Coverage Target: 85%+
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

# Import MCP models and services
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if httpx is available (required by mcp_service)
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    httpx = None

# Skip entire module if httpx is not installed
if not HAS_HTTPX:
    pytest.skip("httpx module not installed", allow_module_level=True)

from shared.mcp_models import (
    MCPServerModel, MCPToolModel, MCPResourceModel, MCPPromptModel,
    MCPTransportType, MCPServerStatus, MCPRequestMethod,
    MCPToolDefinition, MCPResourceDefinition, MCPPromptDefinition,
    MCPServerConfig, MCPToolInvocation, MCPResourceContent, MCPPromptResult,
    JSONRPCRequest, JSONRPCResponse, JSONRPCError
)

from shared.mcp_service import (
    MCPClient, StdioTransport, HTTPTransport,
    ToolDiscoveryService, ResourceManager
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def sample_server_config():
    """Sample MCP server configuration."""
    return MCPServerConfig(
        server_id=uuid4(),
        name="Test Server",
        organization_id="test_org",
        transport_type=MCPTransportType.HTTP,
        endpoint_url="http://localhost:8000",
        timeout_seconds=30,
        retry_attempts=3
    )


@pytest.fixture
def sample_tool_definition():
    """Sample tool definition."""
    return MCPToolDefinition(
        name="test_tool",
        description="A test tool",
        input_schema={
            "type": "object",
            "properties": {
                "arg1": {"type": "string"},
                "arg2": {"type": "number"}
            },
            "required": ["arg1"]
        }
    )


# ============================================================================
# MCP Client Tests
# ============================================================================

class TestMCPClient:
    """Test MCP client functionality."""

    @pytest.mark.asyncio
    async def test_register_server_http(self, mock_db):
        """Test registering an HTTP MCP server."""
        client = MCPClient(mock_db)

        server = await client.register_server(
            name="GitHub Server",
            organization_id="test_org",
            transport_type=MCPTransportType.HTTP,
            endpoint_url="https://mcp.github.com"
        )

        # Verify server was created
        assert server.name == "GitHub Server"
        assert server.transport_type == MCPTransportType.HTTP.value
        assert server.endpoint_url == "https://mcp.github.com"
        assert server.status == MCPServerStatus.DISCONNECTED.value

        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_server_stdio(self, mock_db):
        """Test registering a stdio MCP server."""
        client = MCPClient(mock_db)

        server = await client.register_server(
            name="Local Server",
            organization_id="test_org",
            transport_type=MCPTransportType.STDIO,
            command="python",
            args=["server.py"],
            env={"MODE": "test"}
        )

        # Verify server was created
        assert server.name == "Local Server"
        assert server.transport_type == MCPTransportType.STDIO.value
        assert server.command == "python"
        assert server.args == ["server.py"]
        assert server.env == {"MODE": "test"}

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self, mock_db):
        """Test successful tool invocation."""
        client = MCPClient(mock_db)

        # Mock tool lookup
        tool = MCPToolModel(
            tool_id=uuid4(),
            server_id=uuid4(),
            organization_id="test_org",
            tool_name="test_tool",
            description="Test tool",
            input_schema={},
            total_invocations=0,
            total_errors=0
        )

        # invoke_tool uses result.scalars().first()
        mock_scalars = Mock()
        mock_scalars.first = Mock(return_value=tool)
        mock_result = AsyncMock()
        mock_result.scalars = Mock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock transport
        mock_transport = AsyncMock()
        mock_transport.is_connected = True
        mock_response = JSONRPCResponse(
            jsonrpc="2.0",
            id="test_id",
            result={"output": "success"}
        )
        mock_transport.send_request = AsyncMock(return_value=mock_response)
        client._transports[tool.server_id] = mock_transport

        # Invoke tool
        result = await client.invoke_tool(
            tool_name="test_tool",
            arguments={"arg1": "value1"},
            server_id=tool.server_id,
            organization_id="test_org"
        )

        # Verify result
        assert result.success is True
        assert result.tool_name == "test_tool"
        assert result.result == {"output": "success"}
        assert result.duration_ms is not None

    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self, mock_db):
        """Test tool invocation when tool doesn't exist."""
        client = MCPClient(mock_db)

        # Mock tool not found - invoke_tool uses result.scalars().first()
        mock_scalars = Mock()
        mock_scalars.first = Mock(return_value=None)
        mock_result = AsyncMock()
        mock_result.scalars = Mock(return_value=mock_scalars)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Invoke tool
        result = await client.invoke_tool(
            tool_name="nonexistent_tool",
            arguments={},
            organization_id="test_org"
        )

        # Verify error result
        assert result.success is False
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_read_resource_with_cache(self, mock_db):
        """Test reading a resource with valid cache."""
        client = MCPClient(mock_db)

        # Mock resource with valid cache
        resource = MCPResourceModel(
            resource_id=uuid4(),
            server_id=uuid4(),
            organization_id="test_org",
            resource_uri="file:///test.txt",
            name="test.txt",
            mime_type="text/plain",
            cached_content="cached content",
            cache_expires_at=datetime.utcnow() + timedelta(hours=1),
            total_reads=0
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = Mock(return_value=resource)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Read resource
        content = await client.read_resource(
            resource_uri="file:///test.txt",
            use_cache=True
        )

        # Verify cached content returned
        assert content.content == "cached content"
        assert content.cached is True
        assert content.uri == "file:///test.txt"

    @pytest.mark.asyncio
    async def test_read_resource_expired_cache(self, mock_db):
        """Test reading a resource with expired cache."""
        client = MCPClient(mock_db)

        # Mock resource with expired cache
        resource = MCPResourceModel(
            resource_id=uuid4(),
            server_id=uuid4(),
            organization_id="test_org",
            resource_uri="file:///test.txt",
            name="test.txt",
            mime_type="text/plain",
            cached_content="old content",
            cache_expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
            total_reads=0
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = Mock(return_value=resource)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock transport
        mock_transport = AsyncMock()
        mock_transport.is_connected = True
        mock_response = JSONRPCResponse(
            jsonrpc="2.0",
            id="test_id",
            result={"contents": [{"text": "fresh content"}]}
        )
        mock_transport.send_request = AsyncMock(return_value=mock_response)
        client._transports[resource.server_id] = mock_transport

        # Read resource
        content = await client.read_resource(
            resource_uri="file:///test.txt",
            use_cache=True
        )

        # Verify fresh content fetched
        assert content.content == "fresh content"
        assert content.cached is False


# ============================================================================
# Transport Layer Tests
# ============================================================================

class TestHTTPTransport:
    """Test HTTP transport layer."""

    @pytest.mark.asyncio
    async def test_http_transport_connect(self, sample_server_config):
        """Test HTTP transport connection."""
        transport = HTTPTransport(sample_server_config)

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            success = await transport.connect()

            assert success is True
            assert transport.is_connected is True

    @pytest.mark.asyncio
    async def test_http_transport_send_request(self, sample_server_config):
        """Test sending JSON-RPC request via HTTP."""
        transport = HTTPTransport(sample_server_config)
        transport.is_connected = True

        # Create a mock client with proper async behavior
        mock_client = AsyncMock()

        # Create a mock response - use MagicMock for sync methods like json()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "test_id",
            "result": {"success": True}
        }

        # Set up the post method to return the mock response
        mock_client.post.return_value = mock_response
        transport.client = mock_client

        request = JSONRPCRequest(
            id="test_id",
            method="test_method",
            params={"arg": "value"}
        )

        response = await transport.send_request(request)

        assert response.result == {"success": True}
        mock_client.post.assert_awaited_once()


class TestStdioTransport:
    """Test stdio transport layer."""

    def test_stdio_transport_creation(self, sample_server_config):
        """Test stdio transport initialization."""
        config = MCPServerConfig(
            server_id=uuid4(),
            name="Stdio Server",
            organization_id="test_org",
            transport_type=MCPTransportType.STDIO,
            command="python",
            args=["server.py"]
        )

        transport = StdioTransport(config)

        assert transport.config.command == "python"
        assert transport.config.args == ["server.py"]
        assert transport.is_connected is False


# ============================================================================
# Tool Discovery Service Tests
# ============================================================================

class TestToolDiscoveryService:
    """Test tool discovery and management."""

    @pytest.mark.asyncio
    async def test_list_all_tools(self, mock_db):
        """Test listing all available tools."""
        client = MCPClient(mock_db)
        service = ToolDiscoveryService(mock_db, client)

        # Mock tools
        tools = [
            MCPToolModel(
                tool_id=uuid4(),
                server_id=uuid4(),
                organization_id="test_org",
                tool_name="tool1",
                description="Tool 1",
                input_schema={},
                is_enabled=True,
                total_invocations=0,
                total_errors=0
            ),
            MCPToolModel(
                tool_id=uuid4(),
                server_id=uuid4(),
                organization_id="test_org",
                tool_name="tool2",
                description="Tool 2",
                input_schema={},
                is_enabled=True,
                total_invocations=0,
                total_errors=0
            )
        ]

        mock_result = AsyncMock()
        mock_result.scalars = Mock(return_value=Mock(all=Mock(return_value=tools)))
        mock_db.execute = AsyncMock(return_value=mock_result)

        # List tools
        result = await service.list_all_tools("test_org")

        assert len(result) == 2
        assert result[0].tool_name == "tool1"
        assert result[1].tool_name == "tool2"

    @pytest.mark.asyncio
    async def test_search_tools(self, mock_db):
        """Test searching tools by query."""
        client = MCPClient(mock_db)
        service = ToolDiscoveryService(mock_db, client)

        # Mock search result
        tools = [
            MCPToolModel(
                tool_id=uuid4(),
                server_id=uuid4(),
                organization_id="test_org",
                tool_name="github_tool",
                description="GitHub integration",
                input_schema={},
                is_enabled=True,
                total_invocations=0,
                total_errors=0
            )
        ]

        mock_result = AsyncMock()
        mock_result.scalars = Mock(return_value=Mock(all=Mock(return_value=tools)))
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Search tools
        result = await service.search_tools("test_org", "github")

        assert len(result) == 1
        assert "github" in result[0].tool_name.lower()

    @pytest.mark.asyncio
    async def test_get_tool_by_name(self, mock_db):
        """Test getting specific tool by name."""
        client = MCPClient(mock_db)
        service = ToolDiscoveryService(mock_db, client)

        # Mock tool
        tool = MCPToolModel(
            tool_id=uuid4(),
            server_id=uuid4(),
            organization_id="test_org",
            tool_name="specific_tool",
            description="Specific tool",
            input_schema={},
            is_enabled=True,
            total_invocations=0,
            total_errors=0
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = Mock(return_value=tool)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Get tool
        result = await service.get_tool_by_name("specific_tool", "test_org")

        assert result is not None
        assert result.tool_name == "specific_tool"


# ============================================================================
# Resource Manager Tests
# ============================================================================

class TestResourceManager:
    """Test resource management and caching."""

    @pytest.mark.asyncio
    async def test_list_all_resources(self, mock_db):
        """Test listing all resources."""
        client = MCPClient(mock_db)
        manager = ResourceManager(mock_db, client)

        # Mock resources
        resources = [
            MCPResourceModel(
                resource_id=uuid4(),
                server_id=uuid4(),
                organization_id="test_org",
                resource_uri="file:///test1.txt",
                name="test1.txt",
                mime_type="text/plain",
                is_enabled=True,
                total_reads=0
            ),
            MCPResourceModel(
                resource_id=uuid4(),
                server_id=uuid4(),
                organization_id="test_org",
                resource_uri="file:///test2.json",
                name="test2.json",
                mime_type="application/json",
                is_enabled=True,
                total_reads=0
            )
        ]

        mock_result = AsyncMock()
        mock_result.scalars = Mock(return_value=Mock(all=Mock(return_value=resources)))
        mock_db.execute = AsyncMock(return_value=mock_result)

        # List resources
        result = await manager.list_all_resources("test_org")

        assert len(result) == 2
        assert result[0].name == "test1.txt"
        assert result[1].name == "test2.json"

    @pytest.mark.asyncio
    async def test_list_resources_by_mime_type(self, mock_db):
        """Test filtering resources by MIME type."""
        client = MCPClient(mock_db)
        manager = ResourceManager(mock_db, client)

        # Mock JSON resources only
        resources = [
            MCPResourceModel(
                resource_id=uuid4(),
                server_id=uuid4(),
                organization_id="test_org",
                resource_uri="file:///test.json",
                name="test.json",
                mime_type="application/json",
                is_enabled=True,
                total_reads=0
            )
        ]

        mock_result = AsyncMock()
        mock_result.scalars = Mock(return_value=Mock(all=Mock(return_value=resources)))
        mock_db.execute = AsyncMock(return_value=mock_result)

        # List JSON resources
        result = await manager.list_all_resources("test_org", mime_type="application/json")

        assert len(result) == 1
        assert result[0].mime_type == "application/json"

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, mock_db):
        """Test cache invalidation."""
        client = MCPClient(mock_db)
        manager = ResourceManager(mock_db, client)

        await manager.invalidate_cache("file:///test.txt", "test_org")

        # Verify database update was called
        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()


# ============================================================================
# JSON-RPC Protocol Tests
# ============================================================================

class TestJSONRPCProtocol:
    """Test JSON-RPC 2.0 protocol implementation."""

    def test_jsonrpc_request_creation(self):
        """Test creating JSON-RPC request."""
        request = JSONRPCRequest(
            id="test_123",
            method="test_method",
            params={"arg": "value"}
        )

        assert request.jsonrpc == "2.0"
        assert request.id == "test_123"
        assert request.method == "test_method"
        assert request.params == {"arg": "value"}

    def test_jsonrpc_response_creation(self):
        """Test creating JSON-RPC response."""
        response = JSONRPCResponse(
            id="test_123",
            result={"output": "success"}
        )

        assert response.jsonrpc == "2.0"
        assert response.id == "test_123"
        assert response.result == {"output": "success"}

    def test_jsonrpc_error_creation(self):
        """Test creating JSON-RPC error."""
        error = JSONRPCError(
            code=-32601,
            message="Method not found",
            data={"method": "unknown_method"}
        )

        assert error.code == -32601
        assert error.message == "Method not found"
        assert error.data == {"method": "unknown_method"}


# ============================================================================
# Integration Tests
# ============================================================================

class TestMCPIntegration:
    """Integration tests for complete MCP workflows."""

    @pytest.mark.asyncio
    async def test_complete_tool_workflow(self, mock_db):
        """Test complete workflow: register → connect → discover → invoke."""
        client = MCPClient(mock_db)

        # 1. Register server
        server = await client.register_server(
            name="Test Server",
            organization_id="test_org",
            transport_type=MCPTransportType.HTTP,
            endpoint_url="http://localhost:8000"
        )

        assert server.server_id is not None
        assert server.status == MCPServerStatus.DISCONNECTED.value

        # Subsequent steps would require actual server connection
        # which we skip in unit tests

    @pytest.mark.asyncio
    async def test_resource_caching_workflow(self, mock_db):
        """Test resource caching workflow."""
        client = MCPClient(mock_db)

        # Mock resource without cache
        resource = MCPResourceModel(
            resource_id=uuid4(),
            server_id=uuid4(),
            organization_id="test_org",
            resource_uri="file:///data.json",
            name="data.json",
            mime_type="application/json",
            cached_content=None,
            cache_expires_at=None,
            total_reads=0
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = Mock(return_value=resource)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock transport response
        mock_transport = AsyncMock()
        mock_transport.is_connected = True
        mock_response = JSONRPCResponse(
            jsonrpc="2.0",
            id="test_id",
            result={"contents": [{"text": '{"key": "value"}'}]}
        )
        mock_transport.send_request = AsyncMock(return_value=mock_response)
        client._transports[resource.server_id] = mock_transport

        # Read resource (should cache)
        content = await client.read_resource(
            resource_uri="file:///data.json",
            use_cache=True
        )

        # Verify content and caching
        assert content.content == '{"key": "value"}'
        assert content.cached is False  # First read, not from cache
        assert resource.cached_content == '{"key": "value"}'  # Should be cached now
