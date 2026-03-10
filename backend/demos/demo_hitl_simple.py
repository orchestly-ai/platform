"""
Simple HITL API Demo

Tests the Human-in-the-Loop approval API directly (without workflow execution).
This is a minimal demo that shows the approval create/list/decide flow.

Run:
    cd agent-orchestration
    USE_SQLITE=true python backend/demos/demo_hitl_simple.py
"""

import asyncio
import httpx

API_BASE = "http://localhost:8000/api/v1/hitl"


async def main():
    print("=" * 60)
    print("SIMPLE HITL API DEMO")
    print("=" * 60)
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Create approval request
        print("1. Creating approval request...")
        create_resp = await client.post(f"{API_BASE}/approvals", json={
            "workflow_execution_id": 0,  # Required field (0 for standalone)
            "node_id": "hitl-demo-1",  # Required field
            "title": "Deploy to Production",
            "description": "Review and approve deployment of v2.0",
            "required_approvers": ["admin@company.com"],  # Must match mock user from auth
            "priority": "high",
            "timeout_minutes": 60,
            "context": {"version": "2.0", "environment": "production"}
        })

        if create_resp.status_code != 201:
            print(f"   FAILED: {create_resp.text}")
            return

        approval = create_resp.json()
        approval_id = approval["id"]
        print(f"   Created approval #{approval_id}")
        print(f"   Title: {approval['title']}")
        print(f"   Status: {approval['status']}")
        print()

        # 2. List pending approvals
        print("2. Listing pending approvals...")
        list_resp = await client.get(f"{API_BASE}/approvals")

        if list_resp.status_code == 200:
            approvals = list_resp.json()
            pending = [a for a in approvals if a.get('status') == 'pending']
            print(f"   Found {len(pending)} pending approval(s)")
        else:
            print(f"   FAILED: {list_resp.text}")
        print()

        # 3. Approve the request
        print("3. Approving request...")
        decide_resp = await client.post(f"{API_BASE}/approvals/{approval_id}/decide", json={
            "decision": "approved",
            "comment": "Looks good, approved for production!"
        })

        if decide_resp.status_code == 200:
            result = decide_resp.json()
            print(f"   Decision submitted!")
            print(f"   New status: {result['status']}")
            print(f"   Approved by: {result.get('approved_by_user_id', 'N/A')}")
        else:
            print(f"   FAILED: {decide_resp.text}")
        print()

        # 4. Verify final state
        print("4. Verifying final state...")
        get_resp = await client.get(f"{API_BASE}/approvals/{approval_id}")

        if get_resp.status_code == 200:
            final = get_resp.json()
            print(f"   Status: {final['status']}")
            print(f"   Approved by: {final.get('approved_by_user_id', 'N/A')}")
        else:
            print(f"   FAILED: {get_resp.text}")

    print()
    print("=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
