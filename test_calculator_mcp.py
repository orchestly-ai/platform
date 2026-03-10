#!/usr/bin/env python3
"""
Test script for the Calculator MCP Server
"""

import requests
import json

# MCP server endpoint
BASE_URL = "http://localhost:8001/mcp/calculator"

def test_operation(name, arguments, expected=None):
    """Test a calculator operation"""
    url = f"{BASE_URL}/tools/call"
    payload = {"name": name, "arguments": arguments}

    response = requests.post(url, json=payload)
    result = response.json()

    if result.get("content"):
        value = result["content"][0]["text"]
        status = "✅" if expected is None or str(expected) == value else "❌"
        print(f"{status} {name}({arguments}) = {value}")
        if expected and str(expected) != value:
            print(f"   Expected: {expected}")
    else:
        print(f"❌ {name}({arguments}) - Error: {result}")

def main():
    print("🧮 Testing Calculator MCP Server...")
    print("-" * 40)

    # Test addition
    test_operation("add", {"a": 10, "b": 20}, 30)
    test_operation("add", {"a": -5, "b": 15}, 10)

    # Test subtraction
    test_operation("subtract", {"a": 100, "b": 30}, 70)
    test_operation("subtract", {"a": 10, "b": 25}, -15)

    # Test multiplication
    test_operation("multiply", {"a": 7, "b": 8}, 56)
    test_operation("multiply", {"a": -3, "b": 4}, -12)

    # Test division
    test_operation("divide", {"a": 100, "b": 4}, 25)
    test_operation("divide", {"a": 10, "b": 3}, 3.3333333333333335)

    # Test square root
    test_operation("sqrt", {"n": 25}, 5.0)
    test_operation("sqrt", {"n": 144}, 12.0)

    # Test power
    test_operation("power", {"base": 2, "exponent": 10}, 1024)
    test_operation("power", {"base": 3, "exponent": 3}, 27)

    # Test error cases
    print("\n🔴 Testing error cases...")
    test_operation("divide", {"a": 10, "b": 0})  # Division by zero
    test_operation("sqrt", {"n": -16})  # Square root of negative

    print("-" * 40)
    print("✅ Tests complete!")

if __name__ == "__main__":
    main()