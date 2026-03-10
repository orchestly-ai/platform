"""Add MCP (Model Context Protocol) Support

Revision ID: 010
Revises: 009
Create Date: 2025-12-17 18:00:00.000000

This migration adds complete Model Context Protocol (MCP) infrastructure:
- MCP server registry (stdio, HTTP, SSE, WebSocket transports)
- Tool discovery and invocation
- Resource management with caching
- Prompt templates
- Request logging and analytics

Competitive Advantage:
- Universal tool ecosystem via Anthropic's MCP standard
- Multi-transport support for maximum compatibility
- Intelligent caching and resource management
- Compatible with all MCP-compliant servers (GitHub, Slack, Postgres, etc.)
- Exceeds LangChain with standardized protocol

This is P0 Feature #8 - completes 100% of P0 roadmap!
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create MCP tables.

    This enables:
    - MCP server registration and connection management
    - Tool discovery, registration, and invocation
    - Resource discovery, caching, and reading
    - Prompt template discovery and retrieval
    - Request/response logging for debugging
    """

    # =========================================================================
    # MCP_SERVERS TABLE
    # =========================================================================

    op.create_table(
        'mcp_servers',
        sa.Column('server_id', postgresql.UUID(as_uuid=True), primary_key=True),

        # Organization
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Server info
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Connection
        sa.Column('transport_type', sa.String(50), nullable=False),  # stdio, http, sse, websocket
        sa.Column('endpoint_url', sa.String(500), nullable=True),
        sa.Column('command', sa.String(500), nullable=True),
        sa.Column('args', postgresql.JSONB(), nullable=True),
        sa.Column('env', postgresql.JSONB(), nullable=True),

        # Capabilities (discovered during initialization)
        sa.Column('server_info', postgresql.JSONB(), nullable=True),
        sa.Column('capabilities', postgresql.JSONB(), nullable=True),
        sa.Column('protocol_version', sa.String(50), nullable=True),

        # Status
        sa.Column('status', sa.String(50), nullable=False, server_default='disconnected'),
        sa.Column('last_connected_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),

        # Statistics
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_errors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_latency_ms', sa.Float(), nullable=True),

        # Configuration
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('retry_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),

        # Metadata
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )

    # Create indexes for mcp_servers
    op.create_index('idx_mcp_server_org', 'mcp_servers', ['organization_id'])
    op.create_index('idx_mcp_server_status', 'mcp_servers', ['status'])
    op.create_index('idx_mcp_server_transport', 'mcp_servers', ['transport_type'])


    # =========================================================================
    # MCP_TOOLS TABLE
    # =========================================================================

    op.create_table(
        'mcp_tools',
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Tool definition (from server)
        sa.Column('tool_name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),

        # Input schema (JSON Schema format)
        sa.Column('input_schema', postgresql.JSONB(), nullable=False),

        # Metadata
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),

        # Statistics
        sa.Column('total_invocations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_errors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_duration_ms', sa.Float(), nullable=True),

        # Configuration
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),

        # Discovery
        sa.Column('discovered_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_used_at', sa.DateTime(), nullable=True)
    )

    # Create indexes for mcp_tools
    op.create_index('idx_mcp_tool_server', 'mcp_tools', ['server_id'])
    op.create_index('idx_mcp_tool_org', 'mcp_tools', ['organization_id'])
    op.create_index('idx_mcp_tool_name', 'mcp_tools', ['tool_name'])
    op.create_index('idx_mcp_tool_category', 'mcp_tools', ['category'])
    # op.create_index('idx_mcp_tool_tags', 'mcp_tools', ['tags'], postgresql_using='gin'  # GIN index disabled - requires JSONB type)


    # =========================================================================
    # MCP_RESOURCES TABLE
    # =========================================================================

    op.create_table(
        'mcp_resources',
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Resource definition
        sa.Column('resource_uri', sa.String(500), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),

        # Resource metadata
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('annotations', postgresql.JSONB(), nullable=True),

        # Caching
        sa.Column('cached_content', sa.Text(), nullable=True),
        sa.Column('cache_expires_at', sa.DateTime(), nullable=True),

        # Statistics
        sa.Column('total_reads', sa.Integer(), nullable=False, server_default='0'),

        # Configuration
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),

        # Discovery
        sa.Column('discovered_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_read_at', sa.DateTime(), nullable=True)
    )

    # Create indexes for mcp_resources
    op.create_index('idx_mcp_resource_server', 'mcp_resources', ['server_id'])
    op.create_index('idx_mcp_resource_org', 'mcp_resources', ['organization_id'])
    op.create_index('idx_mcp_resource_uri', 'mcp_resources', ['resource_uri'])
    op.create_index('idx_mcp_resource_mime', 'mcp_resources', ['mime_type'])


    # =========================================================================
    # MCP_PROMPTS TABLE
    # =========================================================================

    op.create_table(
        'mcp_prompts',
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Prompt definition
        sa.Column('prompt_name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),

        # Prompt structure
        sa.Column('arguments', postgresql.JSONB(), nullable=True),

        # Statistics
        sa.Column('total_uses', sa.Integer(), nullable=False, server_default='0'),

        # Configuration
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),

        # Discovery
        sa.Column('discovered_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_used_at', sa.DateTime(), nullable=True)
    )

    # Create indexes for mcp_prompts
    op.create_index('idx_mcp_prompt_server', 'mcp_prompts', ['server_id'])
    op.create_index('idx_mcp_prompt_org', 'mcp_prompts', ['organization_id'])
    op.create_index('idx_mcp_prompt_name', 'mcp_prompts', ['prompt_name'])


    # =========================================================================
    # MCP_REQUEST_LOGS TABLE
    # =========================================================================

    op.create_table(
        'mcp_request_logs',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('server_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Request details
        sa.Column('method', sa.String(100), nullable=False, index=True),
        sa.Column('request_id', sa.String(255), nullable=True),

        # Payload
        sa.Column('request_payload', postgresql.JSONB(), nullable=False),
        sa.Column('response_payload', postgresql.JSONB(), nullable=True),

        # Timing
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),

        # Status
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('error_code', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Context
        sa.Column('workflow_execution_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),

        # Metadata
        sa.Column('request_metadata', postgresql.JSONB(), nullable=True)
    )

    # Create indexes for mcp_request_logs
    op.create_index('idx_mcp_log_server', 'mcp_request_logs', ['server_id'])
    op.create_index('idx_mcp_log_org', 'mcp_request_logs', ['organization_id'])
    op.create_index('idx_mcp_log_method', 'mcp_request_logs', ['method'])
    op.create_index('idx_mcp_log_started', 'mcp_request_logs', ['started_at'])
    op.create_index('idx_mcp_log_status', 'mcp_request_logs', ['status'])
    op.create_index('idx_mcp_log_workflow', 'mcp_request_logs', ['workflow_execution_id'])


def downgrade() -> None:
    """
    Rollback MCP tables.

    Warning: This will delete all MCP servers, tools, resources, prompts, and request logs.
    """

    # Drop mcp_request_logs
    op.drop_index('idx_mcp_log_workflow', table_name='mcp_request_logs')
    op.drop_index('idx_mcp_log_status', table_name='mcp_request_logs')
    op.drop_index('idx_mcp_log_started', table_name='mcp_request_logs')
    op.drop_index('idx_mcp_log_method', table_name='mcp_request_logs')
    op.drop_index('idx_mcp_log_org', table_name='mcp_request_logs')
    op.drop_index('idx_mcp_log_server', table_name='mcp_request_logs')
    op.drop_table('mcp_request_logs')

    # Drop mcp_prompts
    op.drop_index('idx_mcp_prompt_name', table_name='mcp_prompts')
    op.drop_index('idx_mcp_prompt_org', table_name='mcp_prompts')
    op.drop_index('idx_mcp_prompt_server', table_name='mcp_prompts')
    op.drop_table('mcp_prompts')

    # Drop mcp_resources
    op.drop_index('idx_mcp_resource_mime', table_name='mcp_resources')
    op.drop_index('idx_mcp_resource_uri', table_name='mcp_resources')
    op.drop_index('idx_mcp_resource_org', table_name='mcp_resources')
    op.drop_index('idx_mcp_resource_server', table_name='mcp_resources')
    op.drop_table('mcp_resources')

    # Drop mcp_tools
    op.drop_index('idx_mcp_tool_tags', table_name='mcp_tools')
    op.drop_index('idx_mcp_tool_category', table_name='mcp_tools')
    op.drop_index('idx_mcp_tool_name', table_name='mcp_tools')
    op.drop_index('idx_mcp_tool_org', table_name='mcp_tools')
    op.drop_index('idx_mcp_tool_server', table_name='mcp_tools')
    op.drop_table('mcp_tools')

    # Drop mcp_servers
    op.drop_index('idx_mcp_server_transport', table_name='mcp_servers')
    op.drop_index('idx_mcp_server_status', table_name='mcp_servers')
    op.drop_index('idx_mcp_server_org', table_name='mcp_servers')
    op.drop_table('mcp_servers')
