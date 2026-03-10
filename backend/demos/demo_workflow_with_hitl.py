"""
Demo: Workflow with Human-in-the-Loop (HITL) Approval Gate

This script demonstrates how to create and run a workflow that pauses
for human approval before continuing.

Workflow: Marketing Campaign Launcher
    1. Prepare campaign data (AI node)
    2. ⏸️ HITL: Manager approval required (workflow pauses here)
    3. Send campaign (Integration node - Discord/Slack/Email)

Prerequisites:
    - PostgreSQL running with agent_orchestration database
    - Server running: ./run_api_postgres.sh

Run:
    python backend/demos/demo_workflow_with_hitl.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
import httpx
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000/api"


async def main():
    """Run the HITL workflow demonstration."""

    print("=" * 80)
    print("WORKFLOW WITH HUMAN-IN-THE-LOOP (HITL) DEMO")
    print("=" * 80)
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:

        # =================================================================
        # STEP 1: Create a workflow with HITL approval node
        # =================================================================
        print("📋 STEP 1: Creating workflow with HITL approval gate")
        print("-" * 60)

        workflow_data = {
            "name": "Marketing Campaign Launcher with Approval",
            "description": "Launches marketing campaign after manager approval",
            "tags": ["marketing", "hitl", "approval"],
            "environment": "production",
            "max_execution_time_seconds": 3600,
            "nodes": [
                # Node 1: Start trigger
                {
                    "id": "trigger-1",
                    "type": "trigger",
                    "position": {"x": 100, "y": 200},
                    "data": {
                        "type": "trigger",
                        "label": "Campaign Request",
                        "triggerType": "manual"
                    }
                },
                # Node 2: AI prepares campaign data
                {
                    "id": "ai-prepare-1",
                    "type": "ai",
                    "position": {"x": 300, "y": 200},
                    "data": {
                        "type": "ai",
                        "label": "Prepare Campaign",
                        "prompt": "Prepare a marketing campaign summary for: {{input.campaign_name}}. Include target audience, key messages, and expected reach.",
                        "model": "gpt-4"
                    }
                },
                # Node 3: HITL - Manager Approval Required
                {
                    "id": "hitl-approval-1",
                    "type": "hitl",
                    "position": {"x": 500, "y": 200},
                    "data": {
                        "type": "hitl",
                        "label": "Manager Approval",
                        "hitlConfig": {
                            "title": "Approve Marketing Campaign Launch",
                            "description": "Please review and approve the marketing campaign before launch.",
                            "context": {
                                "campaign_type": "Digital Marketing",
                                "budget": 50000,
                                "target_channels": ["LinkedIn", "Google Ads", "Email"]
                            },
                            "approvers": ["manager@company.com", "director@company.com"],
                            "approvalType": "any",  # any = first approval wins, all = need all approvers
                            "priority": "high",
                            "timeout": 60,  # minutes
                            "timeoutAction": "reject",  # auto-reject if no response
                            "notifyVia": ["email", "slack"]
                        }
                    }
                },
                # Node 4: Send to Discord (after approval)
                {
                    "id": "discord-send-1",
                    "type": "integration",
                    "position": {"x": 700, "y": 200},
                    "data": {
                        "type": "integration",
                        "label": "Announce Campaign",
                        "integration": "discord",
                        "action": "send_message",
                        "parameters": {
                            "channel_id": "{{env.DISCORD_CHANNEL_ID}}",
                            "content": "🚀 Campaign Approved and Launching: {{nodes.ai-prepare-1.output.summary}}"
                        }
                    }
                },
                # Node 5: End
                {
                    "id": "end-1",
                    "type": "end",
                    "position": {"x": 900, "y": 200},
                    "data": {
                        "type": "end",
                        "label": "Campaign Launched"
                    }
                }
            ],
            "edges": [
                {"id": "e1", "source": "trigger-1", "target": "ai-prepare-1"},
                {"id": "e2", "source": "ai-prepare-1", "target": "hitl-approval-1"},
                {"id": "e3", "source": "hitl-approval-1", "target": "discord-send-1"},
                {"id": "e4", "source": "discord-send-1", "target": "end-1"}
            ],
            "variables": {
                "campaign_name": "Q1 Product Launch"
            }
        }

        response = await client.post(
            f"{API_BASE_URL}/workflows",  # /api/workflows
            json=workflow_data
        )

        if response.status_code != 201:
            print(f"❌ Failed to create workflow: {response.text}")
            return

        workflow = response.json()
        workflow_id = workflow.get("id") or workflow.get("workflow_id")
        print(f"✅ Workflow created: ID {workflow_id}")
        print(f"   Name: {workflow['name']}")
        print(f"   Nodes: {len(workflow_data['nodes'])}")
        print()

        # =================================================================
        # STEP 2: Execute the workflow
        # =================================================================
        print("🚀 STEP 2: Executing workflow (will pause at HITL node)")
        print("-" * 60)

        exec_response = await client.post(
            f"{API_BASE_URL}/workflows/{workflow_id}/execute",  # /api/workflows/{id}/execute
            json={
                "input": {
                    "campaign_name": "Q1 Enterprise Product Launch"
                }
            }
        )

        if exec_response.status_code not in [200, 201, 202]:
            print(f"❌ Failed to execute workflow: {exec_response.text}")
            return

        execution = exec_response.json()
        execution_id = execution.get("execution_id") or execution.get("id")
        print(f"✅ Workflow execution started: ID {execution_id}")
        print(f"   Status: {execution.get('status', 'running')}")
        print()

        # =================================================================
        # STEP 3: Wait for HITL approval request
        # =================================================================
        print("⏳ STEP 3: Waiting for HITL approval request to be created...")
        print("-" * 60)

        # Give the workflow time to reach the HITL node
        await asyncio.sleep(3)

        # Check for pending approvals
        approvals_response = await client.get(
            f"{API_BASE_URL}/v1/hitl/approvals"  # /api/v1/hitl/approvals
        )

        if approvals_response.status_code == 200:
            approvals = approvals_response.json()
            pending = [a for a in approvals if a.get('status') == 'pending']

            if pending:
                approval = pending[0]
                approval_id = approval['id']
                print(f"✅ HITL approval request found: ID {approval_id}")
                print(f"   Title: {approval['title']}")
                print(f"   Priority: {approval['priority']}")
                print(f"   Approvers: {approval['required_approvers']}")
                print(f"   Expires: {approval['expires_at']}")
                print()

                # =================================================================
                # STEP 4: Approve the request (simulating manager action)
                # =================================================================
                print("✅ STEP 4: Manager approves the request")
                print("-" * 60)

                decision_response = await client.post(
                    f"{API_BASE_URL}/v1/hitl/approvals/{approval_id}/decide",  # /api/v1/hitl/approvals/{id}/decide
                    json={
                        "decision": "approved",
                        "comment": "Approved. Campaign looks good, proceed with launch!"
                    }
                )

                if decision_response.status_code == 200:
                    result = decision_response.json()
                    print(f"✅ Approval submitted!")
                    print(f"   Status: {result['status']}")
                    print(f"   Approved by: {result['approved_by_user_id']}")
                    print(f"   Response time: {result.get('response_time_seconds', 0):.1f}s")
                    print()

                    # =================================================================
                    # STEP 5: Workflow resumes after approval
                    # =================================================================
                    print("🔄 STEP 5: Workflow resumes after approval")
                    print("-" * 60)
                    print("   The workflow will now continue to the Discord integration node")
                    print("   and complete the campaign launch.")
                    print()

                else:
                    print(f"❌ Failed to submit decision: {decision_response.text}")
            else:
                print("⏳ No pending approvals found yet.")
                print("   The workflow executor creates the approval when it reaches the HITL node.")
                print()
                print("   To test manually:")
                print(f"   1. Check pending approvals: GET {API_BASE_URL}/v1/hitl/approvals")
                print(f"   2. Approve: POST {API_BASE_URL}/v1/hitl/approvals/{{id}}/decide")
        else:
            print(f"❌ Failed to get approvals: {approvals_response.text}")

        # =================================================================
        # Summary
        # =================================================================
        print()
        print("=" * 80)
        print("SUMMARY: HITL Workflow Flow")
        print("=" * 80)
        print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW EXECUTION FLOW                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Trigger                                                                 │
│     └─► Campaign request received                                           │
│                                                                             │
│  2. AI Node (Prepare Campaign)                                              │
│     └─► AI prepares campaign summary                                        │
│                                                                             │
│  3. ⏸️  HITL Node (Manager Approval)                                         │
│     ├─► Creates approval request in database                                │
│     ├─► Sends notifications (email/Slack)                                   │
│     ├─► WORKFLOW PAUSES HERE                                                │
│     │                                                                       │
│     │   Manager reviews in dashboard or receives notification               │
│     │   Manager clicks Approve/Reject                                       │
│     │                                                                       │
│     └─► Approval decision saved, workflow notified                          │
│                                                                             │
│  4. Integration Node (Discord - only runs if approved)                      │
│     └─► Sends campaign announcement                                         │
│                                                                             │
│  5. End                                                                     │
│     └─► Campaign successfully launched!                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

API Endpoints Used:
  • POST /api/workflows                       - Create workflow
  • POST /api/workflows/{id}/execute          - Execute workflow
  • GET  /api/v1/hitl/approvals               - List pending approvals
  • POST /api/v1/hitl/approvals/{id}/decide   - Approve/reject
""")


if __name__ == "__main__":
    asyncio.run(main())
