#!/usr/bin/env python3
"""
Debug test for MCP connection
"""

import asyncio
import httpx
from uuid import UUID

async def test_direct_connection():
    """Test direct connection to MCP server."""

    endpoint_url = "http://localhost:8001/mcp/calculator"

    print(f"Testing connection to: {endpoint_url}")

    async with httpx.AsyncClient() as client:
        try:
            # Test health endpoint
            health_url = f"{endpoint_url}/health"
            print(f"Testing health: {health_url}")
            response = await client.get(health_url)
            print(f"Health response: {response.status_code}")
        except Exception as e:
            print(f"Health failed: {e}")

            # Test base endpoint
            try:
                print(f"Testing base: {endpoint_url}")
                response = await client.get(endpoint_url)
                print(f"Base response: {response.status_code}")
                print(f"Base content: {response.text}")
            except Exception as e2:
                print(f"Base also failed: {e2}")

async def test_through_api():
    """Test connection through the API."""

    server_id = "2760d9db-58b8-4dbe-ae7e-d64b29f44f10"
    api_url = f"http://localhost:8000/mcp/servers/{server_id}/connect"

    print(f"\nTesting through API: {api_url}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_url)
            print(f"API response: {response.status_code}")
            print(f"API content: {response.text}")
        except Exception as e:
            print(f"API failed: {e}")

async def main():
    await test_direct_connection()
    await test_through_api()

if __name__ == "__main__":
    asyncio.run(main())