#!/usr/bin/env python3
"""
Test script to verify routing strategy persistence.

This script demonstrates that the routing strategy persistence implementation
works correctly by making API calls to the backend.

Usage:
    python test_routing_persistence.py

Requirements:
    - Backend server running on http://localhost:8000
    - Database initialized with routing_strategies table
"""

import requests
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def print_response(label: str, response: requests.Response):
    """Print formatted API response."""
    print(f"\n{label}:")
    print(f"  Status: {response.status_code}")
    if response.status_code < 400:
        try:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
        except:
            print(f"  Response: {response.text}")
    else:
        print(f"  Error: {response.text}")


def test_get_default_strategy():
    """Test getting routing strategy when none is set (should return default)."""
    print_section("Test 1: Get Default Strategy")

    response = requests.get(f"{BASE_URL}/api/v1/llm/routing-strategy")
    print_response("GET /api/v1/llm/routing-strategy", response)

    if response.status_code == 200:
        data = response.json()
        assert data['strategy'] == 'BEST_AVAILABLE', "Default strategy should be BEST_AVAILABLE"
        print("\n  ✅ Test PASSED: Returns default strategy")
    else:
        print("\n  ❌ Test FAILED: Could not get default strategy")

    return response.status_code == 200


def test_set_cost_optimized():
    """Test setting routing strategy to COST_OPTIMIZED."""
    print_section("Test 2: Set Strategy to COST_OPTIMIZED")

    payload = {
        "strategy": "COST_OPTIMIZED",
        "config": {}
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/llm/routing-strategy",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    print_response("POST /api/v1/llm/routing-strategy", response)

    if response.status_code in [200, 201]:
        data = response.json()
        assert data['strategy'] == 'COST_OPTIMIZED', "Strategy should be COST_OPTIMIZED"
        assert 'id' in data, "Response should include ID"
        assert 'created_at' in data, "Response should include created_at"
        print("\n  ✅ Test PASSED: Strategy set successfully")
        return True, data
    else:
        print("\n  ❌ Test FAILED: Could not set strategy")
        return False, None


def test_verify_persistence():
    """Test that the strategy persists by fetching it again."""
    print_section("Test 3: Verify Persistence (GET after POST)")

    response = requests.get(f"{BASE_URL}/api/v1/llm/routing-strategy")
    print_response("GET /api/v1/llm/routing-strategy", response)

    if response.status_code == 200:
        data = response.json()
        assert data['strategy'] == 'COST_OPTIMIZED', "Strategy should still be COST_OPTIMIZED"
        print("\n  ✅ Test PASSED: Strategy persisted correctly")
        return True
    else:
        print("\n  ❌ Test FAILED: Could not verify persistence")
        return False


def test_update_strategy():
    """Test updating the strategy to LATENCY_OPTIMIZED."""
    print_section("Test 4: Update Strategy to LATENCY_OPTIMIZED")

    payload = {
        "strategy": "LATENCY_OPTIMIZED",
        "config": {"max_latency_ms": 1000}
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/llm/routing-strategy",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    print_response("POST /api/v1/llm/routing-strategy (update)", response)

    if response.status_code in [200, 201]:
        data = response.json()
        assert data['strategy'] == 'LATENCY_OPTIMIZED', "Strategy should be LATENCY_OPTIMIZED"
        assert data['config'].get('max_latency_ms') == 1000, "Config should be persisted"
        print("\n  ✅ Test PASSED: Strategy updated successfully")
        return True
    else:
        print("\n  ❌ Test FAILED: Could not update strategy")
        return False


def test_verify_update():
    """Test that the update persists."""
    print_section("Test 5: Verify Update Persisted")

    response = requests.get(f"{BASE_URL}/api/v1/llm/routing-strategy")
    print_response("GET /api/v1/llm/routing-strategy", response)

    if response.status_code == 200:
        data = response.json()
        assert data['strategy'] == 'LATENCY_OPTIMIZED', "Strategy should be LATENCY_OPTIMIZED"
        assert data['config'].get('max_latency_ms') == 1000, "Config should be persisted"
        print("\n  ✅ Test PASSED: Update persisted correctly")
        return True
    else:
        print("\n  ❌ Test FAILED: Could not verify update")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  ROUTING STRATEGY PERSISTENCE TEST SUITE")
    print("=" * 70)
    print(f"\nTesting backend at: {BASE_URL}")

    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        print(f"✅ Backend is running (status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend is not running: {e}")
        print(f"\nPlease start the backend server:")
        print(f"  cd .")
        print(f"  python -m uvicorn backend.api.main:app --reload")
        return

    # Run tests
    tests_passed = 0
    tests_failed = 0

    try:
        # Test 1: Get default strategy
        if test_get_default_strategy():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 2: Set strategy
        success, data = test_set_cost_optimized()
        if success:
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 3: Verify persistence
        if test_verify_persistence():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 4: Update strategy
        if test_update_strategy():
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 5: Verify update
        if test_verify_update():
            tests_passed += 1
        else:
            tests_failed += 1

    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        tests_failed += 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        tests_failed += 1

    # Print summary
    print_section("TEST SUMMARY")
    print(f"\n  Total Tests: {tests_passed + tests_failed}")
    print(f"  ✅ Passed: {tests_passed}")
    print(f"  ❌ Failed: {tests_failed}")

    if tests_failed == 0:
        print(f"\n  🎉 ALL TESTS PASSED!")
        print(f"\n  Routing strategy persistence is working correctly.")
    else:
        print(f"\n  ⚠️  Some tests failed. Please review the output above.")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
