#!/usr/bin/env python3
"""
Test script for AB Testing and HITL Approvals API endpoints.

This script tests the complete workflow:
1. Create AB Experiment
2. Create HITL Approval
3. Submit Approval Decision
"""

import requests
import json
import sys
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}


def print_response(title: str, response: requests.Response):
    """Pretty print API response."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response Text: {response.text}")
    print(f"{'='*80}\n")


def test_ab_experiment():
    """Test AB Testing - Create Experiment"""
    print("\n🧪 TEST 1: Create AB Testing Experiment")

    payload = {
        "name": "GPT-4 vs Claude-3 Test",
        "slug": "gpt4-claude3-2026-test",
        "description": "Testing which model performs better for code generation",
        "variants": [
            {
                "name": "Control - GPT-4",
                "variant_key": "control_gpt4",
                "variant_type": "control",
                "traffic_percentage": 50.0,
                "config": {
                    "model": "gpt-4",
                    "temperature": 0.7
                }
            },
            {
                "name": "Treatment - Claude-3",
                "variant_key": "treatment_claude3",
                "variant_type": "treatment",
                "traffic_percentage": 50.0,
                "config": {
                    "model": "claude-3-opus",
                    "temperature": 0.7
                }
            }
        ]
    }

    response = requests.post(
        f"{API_BASE_URL}/api/v1/experiments",
        headers=HEADERS,
        json=payload
    )

    print_response("CREATE AB EXPERIMENT", response)

    if response.status_code == 201:
        print("✅ AB Experiment created successfully!")
        return response.json()
    else:
        print("❌ Failed to create AB Experiment")
        return None


def test_hitl_approval():
    """Test HITL - Create Approval Request"""
    print("\n🔐 TEST 2: Create HITL Approval Request")

    payload = {
        "workflow_execution_id": 1,
        "node_id": "approval_node_test",
        "title": "Approve Database Migration",
        "description": "This migration will alter the users table schema",
        "context": {
            "migration_file": "20260105_add_columns.sql",
            "affected_tables": ["users"],
            "estimated_downtime_minutes": 5
        },
        "priority": "high",
        "required_approvers": ["user_12345"],  # Changed to match default user ID
        "timeout_seconds": 3600
    }

    response = requests.post(
        f"{API_BASE_URL}/api/v1/hitl/approvals",
        headers=HEADERS,
        json=payload
    )

    print_response("CREATE HITL APPROVAL", response)

    if response.status_code == 201:
        print("✅ HITL Approval created successfully!")
        return response.json()
    else:
        print("❌ Failed to create HITL Approval")
        return None


def test_approval_decision(approval_id: int, decision: str = "approved"):
    """Test HITL - Submit Approval Decision"""
    print(f"\n✍️  TEST 3: Submit Approval Decision ({decision})")

    payload = {
        "decision": decision,
        "comment": f"Test {decision} comment"
    }

    response = requests.post(
        f"{API_BASE_URL}/api/v1/hitl/approvals/{approval_id}/decide",
        headers=HEADERS,
        json=payload
    )

    print_response(f"SUBMIT DECISION ({decision.upper()})", response)

    if response.status_code == 200:
        print(f"✅ Approval decision '{decision}' submitted successfully!")
        return response.json()
    else:
        print(f"❌ Failed to submit approval decision")
        return None


def test_get_pending_approvals():
    """Test HITL - Get Pending Approvals"""
    print("\n📋 TEST 4: Get Pending Approvals")

    response = requests.get(
        f"{API_BASE_URL}/api/v1/hitl/approvals/pending/me",
        headers=HEADERS
    )

    print_response("GET PENDING APPROVALS", response)

    if response.status_code == 200:
        print("✅ Retrieved pending approvals successfully!")
        return response.json()
    else:
        print("❌ Failed to get pending approvals")
        return None


def main():
    """Run all tests."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║   API ENDPOINT TESTS: AB Testing & HITL Approvals            ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Test 1: Create AB Experiment
    experiment = test_ab_experiment()
    if not experiment:
        print("\n⚠️  AB Experiment test failed, but continuing with HITL tests...")

    # Test 2: Create HITL Approval
    approval = test_hitl_approval()
    if not approval:
        print("\n❌ HITL Approval test failed. Stopping tests.")
        sys.exit(1)

    approval_id = approval.get("id")

    # Test 3: Get Pending Approvals
    test_get_pending_approvals()

    # Test 4: Submit Approval Decision
    if approval_id:
        test_approval_decision(approval_id, "approved")

    print("""
╔═══════════════════════════════════════════════════════════════╗
║                      TESTS COMPLETED                          ║
╚═══════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
