#!/usr/bin/env python3
"""
Demo: How Agents Discover and Use Tools from Multiple Services

This demonstrates how a single agent can:
1. Discover tools from multiple MCP servers (calculator, property, legal)
2. Combine tools from different services to complete complex tasks
3. Orchestrate cross-service workflows
"""

import asyncio
import httpx
from typing import Dict, Any, List

class MultiServiceAgent:
    """Agent that can discover and use tools from multiple MCP servers"""

    def __init__(self, orchestrator_url: str = "http://localhost:8000"):
        self.orchestrator_url = orchestrator_url
        self.org_id = "00000000-0000-0000-0000-000000000001"
        self.discovered_tools = {}

    async def register_mcp_server(self, name: str, url: str, description: str) -> str:
        """Register a new MCP server with the orchestrator"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.orchestrator_url}/mcp/servers",
                json={
                    "name": name,
                    "description": description,
                    "transport_type": "http",
                    "endpoint_url": url
                },
                headers={"X-Organization-ID": self.org_id}
            )
            if response.status_code == 200:
                server_data = response.json()
                server_id = server_data["server_id"]
                print(f"✅ Registered {name}: {server_id}")
                return server_id
            else:
                print(f"❌ Failed to register {name}: {response.text}")
                return None

    async def connect_to_server(self, server_id: str) -> bool:
        """Connect to an MCP server and discover its tools"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.orchestrator_url}/mcp/servers/{server_id}/connect",
                headers={"X-Organization-ID": self.org_id}
            )
            if response.status_code == 200:
                print(f"✅ Connected to server {server_id}")
                return True
            else:
                print(f"❌ Failed to connect: {response.text}")
                return False

    async def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """Discover tools from a connected MCP server"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.orchestrator_url}/mcp/servers/{server_id}/tools",
                headers={"X-Organization-ID": self.org_id}
            )
            if response.status_code == 200:
                tools = response.json()
                for tool in tools:
                    self.discovered_tools[tool["tool_name"]] = {
                        "server_id": server_id,
                        "description": tool.get("description"),
                        "schema": tool.get("input_schema")
                    }
                return tools
            else:
                return []

    async def invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a tool through the orchestrator"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.orchestrator_url}/mcp/tools/invoke",
                json={
                    "tool_name": tool_name,
                    "arguments": arguments
                },
                headers={"X-Organization-ID": self.org_id}
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.text}

    async def demo_cross_service_workflow(self):
        """
        Demo: Property Investment Analysis

        This workflow uses tools from multiple services:
        1. Legal: Check compliance for property rental
        2. Property: List available properties
        3. Property: Get property details
        4. Calculator: Calculate ROI
        5. Legal: Draft a lease agreement
        """
        print("\n" + "="*60)
        print("DEMO: Property Investment Analysis Workflow")
        print("="*60)

        # Step 1: Check legal compliance for property rental business
        print("\n📋 Step 1: Checking legal compliance for rental business...")
        compliance = await self.invoke_tool(
            "check_compliance",
            {
                "regulation": "ada",
                "business_type": "property_rental",
                "operations": ["tenant_screening", "rent_collection", "maintenance"]
            }
        )
        if not compliance.get("error"):
            print(f"Compliance Result: {compliance.get('result', {}).get('content', [{}])[0].get('text', 'No result')[:200]}...")

        # Step 2: List available properties
        print("\n🏠 Step 2: Finding available properties...")
        properties = await self.invoke_tool(
            "list_properties",
            {
                "status": "available",
                "min_price": 3000,
                "max_price": 5000,
                "bedrooms": 2
            }
        )
        if not properties.get("error"):
            print(f"Properties Found: {properties.get('result', {}).get('content', [{}])[0].get('text', 'No result')[:200]}...")

        # Step 3: Calculate potential ROI
        print("\n🧮 Step 3: Calculating ROI for property investment...")
        monthly_rent = 3500
        annual_rent = await self.invoke_tool("multiply", {"a": monthly_rent, "b": 12})
        if not annual_rent.get("error"):
            annual_income = float(annual_rent.get('result', {}).get('content', [{}])[0].get('text', '0'))
            print(f"Annual Rental Income: ${annual_income}")

            # Calculate ROI assuming $500k property value
            property_value = 500000
            roi_calc = await self.invoke_tool("divide", {"a": annual_income, "b": property_value})
            if not roi_calc.get("error"):
                roi = float(roi_calc.get('result', {}).get('content', [{}])[0].get('text', '0'))
                roi_percentage = await self.invoke_tool("multiply", {"a": roi, "b": 100})
                print(f"ROI: {roi_percentage.get('result', {}).get('content', [{}])[0].get('text', '0')}%")

        # Step 4: Calculate total lease value
        print("\n💰 Step 4: Calculating total lease value...")
        lease_total = await self.invoke_tool(
            "calculate_rent",
            {
                "property_id": "prop-001",
                "lease_duration": 12,
                "include_utilities": True
            }
        )
        if not lease_total.get("error"):
            print(f"Lease Calculation: {lease_total.get('result', {}).get('content', [{}])[0].get('text', 'No result')[:200]}...")

        # Step 5: Draft lease agreement
        print("\n📄 Step 5: Drafting lease agreement...")
        lease = await self.invoke_tool(
            "draft_contract",
            {
                "contract_type": "lease",
                "party1_name": "Property Management LLC",
                "party2_name": "John Tenant",
                "key_terms": ["12 month term", "$3,500/month", "Pet-friendly"]
            }
        )
        if not lease.get("error"):
            print(f"Lease Draft: {lease.get('result', {}).get('content', [{}])[0].get('text', 'No result')[:300]}...")

        print("\n" + "="*60)
        print("✅ Workflow Complete: Cross-Service Integration Successful!")
        print("="*60)

async def main():
    """Main demo function"""

    agent = MultiServiceAgent()

    print("\n🚀 Multi-Service Agent Orchestration Demo")
    print("-" * 40)

    # Register all MCP servers
    print("\n📡 Registering MCP Servers...")

    servers = [
        {
            "name": "Calculator Service",
            "url": "http://localhost:8001/mcp/calculator",
            "description": "Basic mathematical operations"
        },
        {
            "name": "Property Management Service",
            "url": "http://localhost:8002/mcp/property",
            "description": "Property listing and management tools"
        },
        {
            "name": "Legal Service",
            "url": "http://localhost:8003/mcp/legal",
            "description": "Legal document and compliance tools"
        }
    ]

    server_ids = []
    for server in servers:
        server_id = await agent.register_mcp_server(
            server["name"],
            server["url"],
            server["description"]
        )
        if server_id:
            server_ids.append(server_id)

    # Connect to all servers
    print("\n🔌 Connecting to MCP Servers...")
    for server_id in server_ids:
        await agent.connect_to_server(server_id)

    # Discover tools from all servers
    print("\n🔍 Discovering Available Tools...")
    total_tools = 0
    for i, server_id in enumerate(server_ids):
        tools = await agent.discover_tools(server_id)
        print(f"   Server {i+1}: {len(tools)} tools discovered")
        for tool in tools[:3]:  # Show first 3 tools
            print(f"      - {tool['tool_name']}: {tool.get('description', 'No description')}")
        if len(tools) > 3:
            print(f"      ... and {len(tools)-3} more")
        total_tools += len(tools)

    print(f"\n📊 Total Tools Available: {total_tools}")
    print(f"   From {len(server_ids)} different services")

    # Run the cross-service workflow demo
    await agent.demo_cross_service_workflow()

    print("\n🎯 Key Benefits Demonstrated:")
    print("   1. Single agent accesses tools from multiple services")
    print("   2. Services remain independent and loosely coupled")
    print("   3. New services can be added without changing agent code")
    print("   4. Tools are discovered dynamically at runtime")
    print("   5. Complex workflows span multiple domains seamlessly")

if __name__ == "__main__":
    print("\n⚠️  NOTE: Make sure all MCP servers are running:")
    print("   1. Calculator MCP: python3 mcp_calculator_server.py")
    print("   2. Property MCP:  python3 mcp_property_server.py")
    print("   3. Legal MCP:     python3 mcp_legal_server.py")
    print("\nPress Enter to continue...")
    input()

    asyncio.run(main())