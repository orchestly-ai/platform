#!/usr/bin/env python3
"""
Simple test to understand httpx connection issue
"""

import asyncio
import httpx
import json

async def test_simple():
    url = "http://localhost:8001/mcp/calculator"

    print(f"Testing URL: {url}")

    try:
        # Test with AsyncClient
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            print(f"Success! Status: {response.status_code}")
            print(f"Content: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
        print(f"Error type: {type(e)}")

    # Also test synchronous
    try:
        print("\nTesting with sync client...")
        response = httpx.get(url)
        print(f"Sync success! Status: {response.status_code}")
    except Exception as e:
        print(f"Sync error: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple())