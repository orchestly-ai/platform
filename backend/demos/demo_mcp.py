#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Interactive Demo

This demo seeds real MCP data into the database and provides an interactive
way to test MCP functionality through the API.

Key Features Demonstrated:
1. Server Registration - Register MCP servers with different transports
2. Tool Discovery - Discover and register tools from MCP servers
3. Resource Management - Register resources with caching
4. Prompt Templates - Register reusable prompts
5. Tool Invocation - Invoke tools with simulated responses
6. Analytics - View usage statistics

Usage:
    python demo_mcp.py                    # Run full demo with seeding
    python demo_mcp.py --seed-only        # Only seed data, no interactive demo
    python demo_mcp.py --api-test         # Test API endpoints after seeding

How to Test in the Dashboard:
1. Start the backend: cd backend && python -m uvicorn api.main:app --reload
2. Run this demo: python demos/demo_mcp.py
3. Open http://localhost:3000/mcp
4. You should see registered servers, tools, resources, and prompts

Multi-Tenancy:
- All data is scoped to organization_id for proper isolation
- Each customer/org can only see their own MCP servers
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta
import random
import json

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.mcp_models import (
    MCPServerModel, MCPToolModel, MCPResourceModel, MCPPromptModel,
    MCPTransportType, MCPServerStatus
)

# Demo organization ID (matches default from auth)
DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"


# ============================================================================
# Demo MCP Servers
# ============================================================================

DEMO_SERVERS = [
    {
        "name": "GitHub MCP Server",
        "description": "Access GitHub repositories, issues, and pull requests via MCP",
        "transport_type": MCPTransportType.HTTP,
        "endpoint_url": "https://mcp.github.example.com",
        "status": MCPServerStatus.CONNECTED,
        "protocol_version": "2024-11-05",
        "server_info": {
            "name": "github-mcp-server",
            "version": "1.0.0",
            "vendor": "GitHub"
        },
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": True,
            "roots": False,
            "sampling": False
        },
        "total_requests": 1247,
        "total_errors": 3,
        "average_latency_ms": 156.5,
    },
    {
        "name": "Slack MCP Server",
        "description": "Send messages, manage channels, and interact with Slack workspaces",
        "transport_type": MCPTransportType.SSE,
        "endpoint_url": "https://mcp.slack.example.com/events",
        "status": MCPServerStatus.CONNECTED,
        "protocol_version": "2024-11-05",
        "server_info": {
            "name": "slack-mcp-server",
            "version": "1.2.0",
            "vendor": "Slack"
        },
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": True,
            "roots": False,
            "sampling": False
        },
        "total_requests": 892,
        "total_errors": 1,
        "average_latency_ms": 89.2,
    },
    {
        "name": "Filesystem MCP Server",
        "description": "Read and write files from the local filesystem",
        "transport_type": MCPTransportType.STDIO,
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "status": MCPServerStatus.CONNECTED,
        "protocol_version": "2024-11-05",
        "server_info": {
            "name": "filesystem-mcp-server",
            "version": "0.5.0",
            "vendor": "Anthropic"
        },
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": False,
            "roots": True,
            "sampling": False
        },
        "total_requests": 543,
        "total_errors": 0,
        "average_latency_ms": 12.4,
    },
    {
        "name": "PostgreSQL MCP Server",
        "description": "Query and manage PostgreSQL databases",
        "transport_type": MCPTransportType.HTTP,
        "endpoint_url": "https://mcp.postgres.example.com",
        "status": MCPServerStatus.DISCONNECTED,
        "protocol_version": "2024-11-05",
        "server_info": None,
        "capabilities": None,
        "total_requests": 0,
        "total_errors": 0,
        "average_latency_ms": None,
    },
]


# ============================================================================
# Demo Tools
# ============================================================================

DEMO_TOOLS = {
    "GitHub MCP Server": [
        {
            "tool_name": "get_repository",
            "description": "Get information about a GitHub repository",
            "category": "github",
            "tags": ["repository", "info", "github"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"}
                },
                "required": ["owner", "repo"]
            },
            "total_invocations": 234,
            "total_errors": 1,
            "average_duration_ms": 145.2
        },
        {
            "tool_name": "list_issues",
            "description": "List issues for a GitHub repository",
            "category": "github",
            "tags": ["issues", "list", "github"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["owner", "repo"]
            },
            "total_invocations": 189,
            "total_errors": 0,
            "average_duration_ms": 234.5
        },
        {
            "tool_name": "create_pull_request",
            "description": "Create a new pull request",
            "category": "github",
            "tags": ["pr", "create", "github"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "title": {"type": "string"},
                    "head": {"type": "string", "description": "Branch containing changes"},
                    "base": {"type": "string", "description": "Branch to merge into"},
                    "body": {"type": "string"}
                },
                "required": ["owner", "repo", "title", "head", "base"]
            },
            "total_invocations": 56,
            "total_errors": 2,
            "average_duration_ms": 312.8
        },
        {
            "tool_name": "search_code",
            "description": "Search code across GitHub repositories",
            "category": "github",
            "tags": ["search", "code", "github"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "language": {"type": "string", "description": "Filter by programming language"},
                    "repo": {"type": "string", "description": "Filter by specific repository"}
                },
                "required": ["query"]
            },
            "total_invocations": 412,
            "total_errors": 0,
            "average_duration_ms": 567.3
        },
    ],
    "Slack MCP Server": [
        {
            "tool_name": "send_message",
            "description": "Send a message to a Slack channel",
            "category": "communication",
            "tags": ["slack", "message", "chat"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel ID or name"},
                    "text": {"type": "string", "description": "Message text"},
                    "thread_ts": {"type": "string", "description": "Thread timestamp for replies"}
                },
                "required": ["channel", "text"]
            },
            "total_invocations": 523,
            "total_errors": 1,
            "average_duration_ms": 78.4
        },
        {
            "tool_name": "list_channels",
            "description": "List available Slack channels",
            "category": "communication",
            "tags": ["slack", "channels", "list"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "types": {"type": "string", "default": "public_channel"},
                    "limit": {"type": "integer", "default": 100}
                }
            },
            "total_invocations": 145,
            "total_errors": 0,
            "average_duration_ms": 156.7
        },
        {
            "tool_name": "get_user_info",
            "description": "Get information about a Slack user",
            "category": "communication",
            "tags": ["slack", "user", "info"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Slack user ID"}
                },
                "required": ["user_id"]
            },
            "total_invocations": 224,
            "total_errors": 0,
            "average_duration_ms": 89.2
        },
    ],
    "Filesystem MCP Server": [
        {
            "tool_name": "read_file",
            "description": "Read contents of a file",
            "category": "filesystem",
            "tags": ["file", "read", "filesystem"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            },
            "total_invocations": 312,
            "total_errors": 0,
            "average_duration_ms": 8.5
        },
        {
            "tool_name": "write_file",
            "description": "Write contents to a file",
            "category": "filesystem",
            "tags": ["file", "write", "filesystem"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            },
            "total_invocations": 89,
            "total_errors": 0,
            "average_duration_ms": 12.3
        },
        {
            "tool_name": "list_directory",
            "description": "List contents of a directory",
            "category": "filesystem",
            "tags": ["directory", "list", "filesystem"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            },
            "total_invocations": 142,
            "total_errors": 0,
            "average_duration_ms": 5.6
        },
    ],
}


# ============================================================================
# Demo Resources
# ============================================================================

DEMO_RESOURCES = {
    "GitHub MCP Server": [
        {
            "resource_uri": "github://anthropics/claude-code/README.md",
            "name": "Claude Code README",
            "description": "README file for the Claude Code repository",
            "mime_type": "text/markdown",
            "size_bytes": 4820,
            "total_reads": 156
        },
        {
            "resource_uri": "github://anthropics/claude-code/LICENSE",
            "name": "Claude Code License",
            "description": "MIT License file",
            "mime_type": "text/plain",
            "size_bytes": 1074,
            "total_reads": 23
        },
    ],
    "Filesystem MCP Server": [
        {
            "resource_uri": "file:///workspace/README.md",
            "name": "Workspace README",
            "description": "Project README",
            "mime_type": "text/markdown",
            "size_bytes": 2340,
            "total_reads": 89
        },
        {
            "resource_uri": "file:///workspace/package.json",
            "name": "Package Configuration",
            "description": "NPM package.json",
            "mime_type": "application/json",
            "size_bytes": 1250,
            "total_reads": 67
        },
        {
            "resource_uri": "file:///workspace/tsconfig.json",
            "name": "TypeScript Config",
            "description": "TypeScript configuration",
            "mime_type": "application/json",
            "size_bytes": 890,
            "total_reads": 34
        },
    ],
}


# ============================================================================
# Demo Prompts
# ============================================================================

DEMO_PROMPTS = {
    "GitHub MCP Server": [
        {
            "prompt_name": "code_review",
            "description": "Perform a thorough code review with specific focus areas",
            "arguments": [
                {"name": "code", "description": "Code to review", "required": True},
                {"name": "language", "description": "Programming language", "required": True},
                {"name": "focus_areas", "description": "Areas to focus on", "required": False}
            ],
            "total_uses": 89
        },
        {
            "prompt_name": "generate_tests",
            "description": "Generate unit tests for the given code",
            "arguments": [
                {"name": "code", "description": "Code to test", "required": True},
                {"name": "framework", "description": "Testing framework", "required": False}
            ],
            "total_uses": 56
        },
    ],
    "Slack MCP Server": [
        {
            "prompt_name": "daily_standup",
            "description": "Generate a daily standup message",
            "arguments": [
                {"name": "yesterday", "description": "What was done yesterday", "required": True},
                {"name": "today", "description": "What's planned for today", "required": True},
                {"name": "blockers", "description": "Any blockers", "required": False}
            ],
            "total_uses": 234
        },
        {
            "prompt_name": "incident_report",
            "description": "Generate an incident report message",
            "arguments": [
                {"name": "severity", "description": "Incident severity", "required": True},
                {"name": "description", "description": "What happened", "required": True},
                {"name": "impact", "description": "Impact assessment", "required": True},
                {"name": "resolution", "description": "How it was resolved", "required": False}
            ],
            "total_uses": 12
        },
    ],
}


# ============================================================================
# Seed Functions
# ============================================================================

async def cleanup_mcp_data(db: AsyncSession):
    """Clean up previous MCP demo data."""
    print("\n🧹 Cleaning up previous MCP demo data...")
    try:
        await db.execute(text(f"DELETE FROM mcp_prompts WHERE organization_id = '{DEMO_ORG_ID}'"))
        await db.execute(text(f"DELETE FROM mcp_resources WHERE organization_id = '{DEMO_ORG_ID}'"))
        await db.execute(text(f"DELETE FROM mcp_tools WHERE organization_id = '{DEMO_ORG_ID}'"))
        await db.execute(text(f"DELETE FROM mcp_servers WHERE organization_id = '{DEMO_ORG_ID}'"))
        await db.commit()
        print("   ✓ Cleaned up existing demo data")
    except Exception as e:
        print(f"   ⚠ Cleanup warning (tables may not exist yet): {str(e)[:80]}")
        await db.rollback()


async def ensure_tables_exist(db: AsyncSession):
    """Ensure MCP tables exist."""
    try:
        # Check if mcp_servers table exists
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'mcp_servers'
            )
        """))
        exists = result.scalar()
        if not exists:
            print("   ⚠ MCP tables don't exist. Run migrations first:")
            print("      alembic upgrade head")
            return False
        return True
    except Exception as e:
        print(f"   ⚠ Cannot check tables: {e}")
        return False


async def seed_mcp_data():
    """Seed MCP demo data into the database."""
    print("\n" + "=" * 80)
    print("MCP DATA SEEDING")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        # Check tables exist
        if not await ensure_tables_exist(db):
            return {}

        # Cleanup first
        await cleanup_mcp_data(db)

        server_map = {}  # Map server name to server_id

        # Seed servers
        print("\n1. Seeding MCP Servers...")
        for server_data in DEMO_SERVERS:
            server = MCPServerModel(
                server_id=uuid4(),
                organization_id=DEMO_ORG_ID,
                name=server_data["name"],
                description=server_data.get("description"),
                transport_type=server_data["transport_type"].value,
                endpoint_url=server_data.get("endpoint_url"),
                command=server_data.get("command"),
                args=server_data.get("args"),
                env=server_data.get("env"),
                status=server_data["status"].value,
                protocol_version=server_data.get("protocol_version"),
                server_info=server_data.get("server_info"),
                capabilities=server_data.get("capabilities"),
                total_requests=server_data.get("total_requests", 0),
                total_errors=server_data.get("total_errors", 0),
                average_latency_ms=server_data.get("average_latency_ms"),
                last_connected_at=datetime.utcnow() if server_data["status"] == MCPServerStatus.CONNECTED else None,
                is_active=True,
            )
            db.add(server)
            server_map[server_data["name"]] = server.server_id
            status_icon = "✅" if server_data["status"] == MCPServerStatus.CONNECTED else "⭕"
            print(f"   {status_icon} {server_data['name']} ({server_data['transport_type'].value})")

        await db.commit()
        print(f"   ✓ {len(DEMO_SERVERS)} servers seeded")

        # Seed tools
        print("\n2. Seeding MCP Tools...")
        total_tools = 0
        for server_name, tools in DEMO_TOOLS.items():
            if server_name not in server_map:
                continue
            server_id = server_map[server_name]
            for tool_data in tools:
                tool = MCPToolModel(
                    tool_id=uuid4(),
                    server_id=server_id,
                    organization_id=DEMO_ORG_ID,
                    tool_name=tool_data["tool_name"],
                    description=tool_data.get("description"),
                    input_schema=tool_data.get("input_schema", {}),
                    category=tool_data.get("category"),
                    tags=tool_data.get("tags"),
                    total_invocations=tool_data.get("total_invocations", 0),
                    total_errors=tool_data.get("total_errors", 0),
                    average_duration_ms=tool_data.get("average_duration_ms"),
                    is_enabled=True,
                )
                db.add(tool)
                total_tools += 1
            print(f"   ✓ {len(tools)} tools from {server_name}")

        await db.commit()
        print(f"   ✓ {total_tools} total tools seeded")

        # Seed resources
        print("\n3. Seeding MCP Resources...")
        total_resources = 0
        for server_name, resources in DEMO_RESOURCES.items():
            if server_name not in server_map:
                continue
            server_id = server_map[server_name]
            for resource_data in resources:
                resource = MCPResourceModel(
                    resource_id=uuid4(),
                    server_id=server_id,
                    organization_id=DEMO_ORG_ID,
                    resource_uri=resource_data["resource_uri"],
                    name=resource_data["name"],
                    description=resource_data.get("description"),
                    mime_type=resource_data.get("mime_type"),
                    size_bytes=resource_data.get("size_bytes"),
                    total_reads=resource_data.get("total_reads", 0),
                    is_enabled=True,
                )
                db.add(resource)
                total_resources += 1
            print(f"   ✓ {len(resources)} resources from {server_name}")

        await db.commit()
        print(f"   ✓ {total_resources} total resources seeded")

        # Seed prompts
        print("\n4. Seeding MCP Prompts...")
        total_prompts = 0
        for server_name, prompts in DEMO_PROMPTS.items():
            if server_name not in server_map:
                continue
            server_id = server_map[server_name]
            for prompt_data in prompts:
                prompt = MCPPromptModel(
                    prompt_id=uuid4(),
                    server_id=server_id,
                    organization_id=DEMO_ORG_ID,
                    prompt_name=prompt_data["prompt_name"],
                    description=prompt_data.get("description"),
                    arguments=prompt_data.get("arguments"),
                    total_uses=prompt_data.get("total_uses", 0),
                    is_enabled=True,
                )
                db.add(prompt)
                total_prompts += 1
            print(f"   ✓ {len(prompts)} prompts from {server_name}")

        await db.commit()
        print(f"   ✓ {total_prompts} total prompts seeded")

        return server_map


async def print_mcp_summary():
    """Print summary of seeded MCP data."""
    print("\n" + "=" * 80)
    print("MCP DEMO SUMMARY")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, func

        # Server stats
        result = await db.execute(
            select(func.count(MCPServerModel.server_id)).where(
                MCPServerModel.organization_id == DEMO_ORG_ID
            )
        )
        server_count = result.scalar() or 0

        result = await db.execute(
            select(func.count(MCPServerModel.server_id)).where(
                MCPServerModel.organization_id == DEMO_ORG_ID,
                MCPServerModel.status == MCPServerStatus.CONNECTED.value
            )
        )
        connected_count = result.scalar() or 0

        # Tool stats
        result = await db.execute(
            select(func.count(MCPToolModel.tool_id)).where(
                MCPToolModel.organization_id == DEMO_ORG_ID
            )
        )
        tool_count = result.scalar() or 0

        result = await db.execute(
            select(func.sum(MCPToolModel.total_invocations)).where(
                MCPToolModel.organization_id == DEMO_ORG_ID
            )
        )
        total_invocations = result.scalar() or 0

        # Resource stats
        result = await db.execute(
            select(func.count(MCPResourceModel.resource_id)).where(
                MCPResourceModel.organization_id == DEMO_ORG_ID
            )
        )
        resource_count = result.scalar() or 0

        # Prompt stats
        result = await db.execute(
            select(func.count(MCPPromptModel.prompt_id)).where(
                MCPPromptModel.organization_id == DEMO_ORG_ID
            )
        )
        prompt_count = result.scalar() or 0

    print(f"""
📊 MCP Analytics Summary:

   Servers:
   ├── Total: {server_count}
   ├── Connected: {connected_count}
   └── Disconnected: {server_count - connected_count}

   Tools:
   ├── Total: {tool_count}
   └── Total Invocations: {total_invocations:,}

   Resources: {resource_count}
   Prompts: {prompt_count}
""")

    print("""
🔗 How to Test:

   1. Start the backend (if not running):
      cd platform/agent-orchestration/backend
      python -m uvicorn api.main:app --reload --port 8000

   2. Start the dashboard (if not running):
      cd platform/agent-orchestration/dashboard
      npm run dev

   3. Open http://localhost:3000/mcp in your browser

   4. You should see:
      • 4 registered MCP servers (3 connected, 1 disconnected)
      • 10+ tools available for invocation
      • Resources from GitHub and filesystem
      • Prompt templates for code review and Slack

   5. Try:
      • Connect/disconnect servers
      • Invoke a tool (click "Invoke" button)
      • View analytics in the dashboard

📚 What is MCP (Model Context Protocol)?

   MCP is Anthropic's standard for connecting LLMs to external tools.
   It provides a unified protocol that works across:

   • Transport mechanisms: stdio, HTTP, SSE, WebSocket
   • Tool types: APIs, databases, file systems, services
   • Vendors: GitHub, Slack, Postgres, custom servers

   This means you can connect to ANY MCP-compliant server and
   immediately access its tools, resources, and prompts.

🔧 Multi-Tenancy Note:

   All MCP data is scoped to organization_id ({DEMO_ORG_ID}).
   Each customer can only see their own:
   • Servers and connections
   • Discovered tools
   • Resources and caches
   • Usage analytics
""")


async def test_api_endpoints():
    """Test MCP API endpoints."""
    import aiohttp

    print("\n" + "=" * 80)
    print("TESTING MCP API ENDPOINTS")
    print("=" * 80)

    base_url = "http://localhost:8000"

    async with aiohttp.ClientSession() as session:
        endpoints = [
            ("GET", "/mcp/servers", "List servers"),
            ("GET", "/mcp/tools", "List tools"),
            ("GET", "/mcp/resources", "List resources"),
            ("GET", "/mcp/prompts", "List prompts"),
            ("GET", "/mcp/analytics/servers/summary", "Get analytics"),
        ]

        for method, path, description in endpoints:
            try:
                async with session.request(method, f"{base_url}{path}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            print(f"   ✅ {description}: {len(data)} items")
                        elif isinstance(data, dict):
                            print(f"   ✅ {description}: OK")
                    else:
                        print(f"   ❌ {description}: HTTP {resp.status}")
            except aiohttp.ClientError as e:
                print(f"   ❌ {description}: Connection error - {e}")
            except Exception as e:
                print(f"   ❌ {description}: {e}")


async def main():
    """Run the MCP demo."""
    print("\n" + "=" * 80)
    print("MCP (MODEL CONTEXT PROTOCOL) DEMO")
    print("Universal Tool Ecosystem for AI Agents")
    print("=" * 80)

    # Check for command line args
    import sys
    args = sys.argv[1:]

    seed_only = "--seed-only" in args
    api_test = "--api-test" in args

    # Initialize database
    print("\n🔧 Initializing database...")
    await init_db()

    # Seed data
    await seed_mcp_data()

    if not seed_only:
        # Print summary
        await print_mcp_summary()

    if api_test:
        # Test API
        await test_api_endpoints()

    print("\n✅ MCP Demo Complete!")
    print("   Visit http://localhost:3000/mcp to see the dashboard")


if __name__ == "__main__":
    asyncio.run(main())
