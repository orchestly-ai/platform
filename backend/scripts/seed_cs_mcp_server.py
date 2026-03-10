"""
Seed Script: Register Customer Support AI Intelligence MCP Server

Registers the CS AI Intelligence MCP server with the Agent Orchestration Platform
so other services can discover and use CS AI capabilities.

Prerequisites:
    1. Start the CS Intelligence MCP server:
       cd services/customer-support/support-service/backend
       python mcp_cs_intelligence_server.py --port 8041

    2. Start the Agent Orchestration backend:
       cd platform/agent-orchestration
       ENABLE_EXTENDED_ROUTERS=true uvicorn backend.api.main:app --port 8000

Run:
    cd platform/agent-orchestration
    source backend/venv/bin/activate
    python -m backend.scripts.seed_cs_mcp_server

This creates:
- MCP Server registration for cs-intelligence
- Connects and discovers tools automatically
"""

import asyncio
import os
import sys
from uuid import uuid4
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select

from backend.database.session import AsyncSessionLocal
from backend.shared.mcp_models import MCPServerModel, MCPToolModel, MCPTransportType, MCPServerStatus


# CS Intelligence MCP Server Configuration
CS_INTELLIGENCE_SERVER = {
    "name": "Customer Support AI Intelligence",
    "description": "AI-powered customer support tools: triage, response generation, KB search, sentiment analysis",
    "transport_type": "http",
    "endpoint_url": os.getenv("CS_INTELLIGENCE_MCP_URL", "http://localhost:8041/mcp"),
    "organization_id": "org-customer-support",
    "timeout_seconds": 30,
    "retry_attempts": 3,
}


async def seed_mcp_server():
    """Register the CS AI Intelligence MCP server"""

    async with AsyncSessionLocal() as session:
        # Check if server already exists
        stmt = select(MCPServerModel).where(
            MCPServerModel.name == CS_INTELLIGENCE_SERVER["name"]
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"MCP Server '{CS_INTELLIGENCE_SERVER['name']}' already exists")
            print(f"  Server ID: {existing.server_id}")
            print(f"  Status: {existing.status}")
            print(f"  Endpoint: {existing.endpoint_url}")

            # Check for discovered tools
            stmt = select(MCPToolModel).where(MCPToolModel.server_id == existing.server_id)
            result = await session.execute(stmt)
            tools = result.scalars().all()

            if tools:
                print(f"\nDiscovered Tools ({len(tools)}):")
                for tool in tools:
                    print(f"  - {tool.tool_name}: {tool.description[:50]}..." if tool.description else f"  - {tool.tool_name}")
            else:
                print("\nNo tools discovered yet. Connect to discover tools.")

            return existing.server_id

        # Create new MCP server registration
        server = MCPServerModel(
            server_id=uuid4(),
            organization_id=CS_INTELLIGENCE_SERVER["organization_id"],
            name=CS_INTELLIGENCE_SERVER["name"],
            description=CS_INTELLIGENCE_SERVER["description"],
            transport_type=CS_INTELLIGENCE_SERVER["transport_type"],
            endpoint_url=CS_INTELLIGENCE_SERVER["endpoint_url"],
            timeout_seconds=CS_INTELLIGENCE_SERVER["timeout_seconds"],
            retry_attempts=CS_INTELLIGENCE_SERVER["retry_attempts"],
            status=MCPServerStatus.DISCONNECTED.value,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        session.add(server)
        await session.commit()
        await session.refresh(server)

        print("=" * 60)
        print("CS AI Intelligence MCP Server Registered")
        print("=" * 60)
        print()
        print(f"Server ID: {server.server_id}")
        print(f"Name: {server.name}")
        print(f"Endpoint: {server.endpoint_url}")
        print(f"Status: {server.status}")
        print()
        print("Next Steps:")
        print("1. Start the MCP server:")
        print("   cd services/customer-support/support-service/backend")
        print("   python mcp_cs_intelligence_server.py --port 8041")
        print()
        print("2. Connect and discover tools via API:")
        print(f"   POST http://localhost:8000/api/v1/mcp/servers/{server.server_id}/connect")
        print()
        print("3. View available tools:")
        print(f"   GET http://localhost:8000/api/v1/mcp/servers/{server.server_id}/tools")
        print()
        print("Available Tools (after connection):")
        print("  - triage_support_ticket: Classify & prioritize tickets")
        print("  - generate_support_response: AI response generation")
        print("  - search_support_knowledge_base: KB search")
        print("  - analyze_customer_sentiment: Sentiment analysis")
        print()

        return server.server_id


async def test_mcp_connection():
    """Test connecting to the MCP server (optional)"""
    import httpx

    endpoint_url = CS_INTELLIGENCE_SERVER["endpoint_url"]
    base_url = endpoint_url.replace("/mcp", "")

    print("\nTesting MCP Server Connection...")
    print(f"Endpoint: {base_url}/health")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test health endpoint
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print(f"Health check: OK - {response.json()}")
            else:
                print(f"Health check failed: {response.status_code}")
                return False

            # Test tools list
            response = await client.post(
                endpoint_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {}
                }
            )
            if response.status_code == 200:
                data = response.json()
                tools = data.get("result", {}).get("tools", [])
                print(f"\nDiscovered {len(tools)} tools:")
                for tool in tools:
                    print(f"  - {tool['name']}: {tool.get('description', '')[:50]}...")
                return True
            else:
                print(f"Tools list failed: {response.status_code}")
                return False

    except httpx.ConnectError:
        print("Cannot connect to MCP server. Make sure it's running:")
        print("  cd services/customer-support/support-service/backend")
        print("  python mcp_cs_intelligence_server.py --port 8041")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Register CS AI Intelligence MCP Server")
    parser.add_argument("--test", action="store_true", help="Test MCP server connection")
    args = parser.parse_args()

    async def main():
        server_id = await seed_mcp_server()

        if args.test:
            await test_mcp_connection()

    asyncio.run(main())
