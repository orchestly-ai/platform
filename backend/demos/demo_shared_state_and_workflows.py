"""
Demo: Shared State Manager + Webhook + HITL Workflow

This demo showcases:
1. Shared State Manager for cross-node data passing
2. Variable substitution ({{node_id.field}})
3. Webhook nodes with authentication
4. HITL (Human-in-the-Loop) approval nodes
5. Complete workflow with state management

Run with: python backend/demos/demo_shared_state_and_workflows.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.shared.shared_state_manager import (
    SharedStateManager,
    StateScope,
    reset_shared_state_manager
)


async def demo_basic_state_operations():
    """Demo 1: Basic state operations."""
    print("\n" + "="*80)
    print("DEMO 1: Basic State Operations")
    print("="*80)

    # Create state manager
    state = SharedStateManager()
    workflow_id = "workflow_demo_001"

    # Set workflow state
    print("\n1. Setting workflow state...")
    await state.set(
        key="user_input",
        value={"message": "Hello World", "user_id": "user_123"},
        scope=StateScope.WORKFLOW,
        scope_id=workflow_id
    )
    print("   ✓ Stored user_input")

    await state.set(
        key="processing_status",
        value="in_progress",
        scope=StateScope.WORKFLOW,
        scope_id=workflow_id
    )
    print("   ✓ Stored processing_status")

    # Retrieve values
    print("\n2. Retrieving values...")
    user_input = await state.get("user_input", StateScope.WORKFLOW, workflow_id)
    print(f"   user_input = {json.dumps(user_input, indent=2)}")

    status = await state.get("processing_status", StateScope.WORKFLOW, workflow_id)
    print(f"   processing_status = {status}")

    # Get all workflow state
    print("\n3. Getting all workflow state...")
    all_state = await state.get_all(StateScope.WORKFLOW, workflow_id)
    print(f"   Found {len(all_state)} entries:")
    for key, value in all_state.items():
        print(f"     - {key}: {value}")

    # Clear workflow state
    print("\n4. Clearing workflow state...")
    cleared = await state.clear(StateScope.WORKFLOW, workflow_id)
    print(f"   ✓ Cleared {cleared} entries")


async def demo_scope_isolation():
    """Demo 2: Scope isolation."""
    print("\n" + "="*80)
    print("DEMO 2: Scope Isolation")
    print("="*80)

    state = SharedStateManager()

    # Set same key in different scopes
    print("\n1. Setting same key in different scopes...")
    await state.set("status", "workflow_status", StateScope.WORKFLOW, "wf_001")
    await state.set("status", "agent_status", StateScope.AGENT, "agent_001")
    await state.set("status", "global_status", StateScope.GLOBAL, "global")

    # Retrieve from each scope
    print("\n2. Retrieving from each scope...")
    wf_status = await state.get("status", StateScope.WORKFLOW, "wf_001")
    agent_status = await state.get("status", StateScope.AGENT, "agent_001")
    global_status = await state.get("status", StateScope.GLOBAL, "global")

    print(f"   Workflow scope: {wf_status}")
    print(f"   Agent scope:    {agent_status}")
    print(f"   Global scope:   {global_status}")

    # Cleanup
    await state.clear(StateScope.WORKFLOW, "wf_001")
    await state.clear(StateScope.AGENT, "agent_001")
    await state.clear(StateScope.GLOBAL, "global")


async def demo_workflow_node_outputs():
    """Demo 3: Storing node outputs (as workflow executor does)."""
    print("\n" + "="*80)
    print("DEMO 3: Workflow Node Outputs")
    print("="*80)

    state = SharedStateManager()
    workflow_id = "workflow_demo_003"

    print("\n1. Simulating workflow execution...")

    # Node 1: User Input
    print("\n   Node 1: User Input")
    await state.set(
        key="node_output:user_input_1",
        value={
            "message": "Book a flight to New York",
            "user_id": "user_456",
            "timestamp": "2024-01-15T10:00:00Z"
        },
        scope=StateScope.WORKFLOW,
        scope_id=workflow_id,
        metadata={"node_type": "input", "cost": 0}
    )
    print("   ✓ Stored output")

    # Node 2: LLM Processor
    print("\n   Node 2: LLM Intent Classifier")
    await state.set(
        key="node_output:intent_classifier_2",
        value={
            "content": "Intent: book_flight",
            "entities": {
                "destination": "New York",
                "action": "book"
            },
            "model": "gpt-4o-mini",
            "tokens": 150,
            "cost": 0.0015
        },
        scope=StateScope.WORKFLOW,
        scope_id=workflow_id,
        metadata={"node_type": "llm", "execution_time": 1500}
    )
    print("   ✓ Stored output")

    # Node 3: API Call (using previous outputs)
    print("\n   Node 3: Flight Search API")
    # In real workflow, this would use {{intent_classifier_2.entities.destination}}
    intent_data = await state.get("node_output:intent_classifier_2", StateScope.WORKFLOW, workflow_id)
    destination = intent_data["entities"]["destination"]

    await state.set(
        key="node_output:flight_api_3",
        value={
            "flights": [
                {"airline": "AA", "price": 350, "destination": destination},
                {"airline": "UA", "price": 320, "destination": destination}
            ],
            "status_code": 200
        },
        scope=StateScope.WORKFLOW,
        scope_id=workflow_id,
        metadata={"node_type": "tool", "execution_time": 800}
    )
    print(f"   ✓ Searched flights to {destination}")

    # View all workflow state
    print("\n2. Complete workflow state:")
    all_state = await state.get_all(StateScope.WORKFLOW, workflow_id)
    for key, value in all_state.items():
        print(f"\n   {key}:")
        print(f"   {json.dumps(value, indent=4)}")

    # Cleanup
    await state.clear(StateScope.WORKFLOW, workflow_id)


async def demo_variable_substitution():
    """Demo 4: Variable substitution simulation."""
    print("\n" + "="*80)
    print("DEMO 4: Variable Substitution ({{node_id.field}})")
    print("="*80)

    state = SharedStateManager()
    workflow_id = "workflow_demo_004"

    # Setup workflow state
    print("\n1. Setting up workflow state...")
    await state.set(
        "node_output:user_input",
        {"user_id": "user_789", "message": "Send notification"},
        StateScope.WORKFLOW,
        workflow_id
    )
    await state.set(
        "node_output:user_lookup",
        {"name": "Alice", "email": "alice@example.com"},
        StateScope.WORKFLOW,
        workflow_id
    )

    # Simulate variable substitution
    print("\n2. Simulating variable substitution...")

    template_url = "https://api.example.com/notify/{{user_input.user_id}}"
    template_body = {
        "recipient": "{{user_lookup.email}}",
        "message": "{{user_input.message}}",
        "name": "{{user_lookup.name}}"
    }

    print(f"\n   Template URL: {template_url}")
    print(f"   Template Body: {json.dumps(template_body, indent=4)}")

    # Manual substitution (in real workflow, _substitute_variables does this)
    import re

    async def substitute(text, workflow_id):
        pattern = r'\{\{([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_.-]+)\}\}'
        matches = re.finditer(pattern, text)

        result = text
        for match in matches:
            node_id = match.group(1)
            field = match.group(2)

            node_output = await state.get(
                f"node_output:{node_id}",
                StateScope.WORKFLOW,
                workflow_id
            )

            if node_output and field in node_output:
                result = result.replace(match.group(0), str(node_output[field]))

        return result

    # Substitute URL
    final_url = await substitute(template_url, workflow_id)
    print(f"\n   Substituted URL: {final_url}")

    # Substitute body
    body_str = json.dumps(template_body)
    final_body_str = await substitute(body_str, workflow_id)
    final_body = json.loads(final_body_str)
    print(f"   Substituted Body: {json.dumps(final_body, indent=4)}")

    # Cleanup
    await state.clear(StateScope.WORKFLOW, workflow_id)


async def demo_state_snapshots():
    """Demo 5: State snapshots for time-travel debugging."""
    print("\n" + "="*80)
    print("DEMO 5: State Snapshots (Time-Travel Debugging)")
    print("="*80)

    state = SharedStateManager()
    workflow_id = "workflow_demo_005"

    # Initial state
    print("\n1. Creating initial workflow state...")
    await state.set("step", "1", StateScope.WORKFLOW, workflow_id)
    await state.set("status", "processing", StateScope.WORKFLOW, workflow_id)
    await state.set("data", {"count": 0}, StateScope.WORKFLOW, workflow_id)

    # Create snapshot
    print("\n2. Creating snapshot...")
    snapshot = await state.snapshot(StateScope.WORKFLOW, workflow_id)
    print(f"   ✓ Snapshot created at {snapshot.captured_at}")
    print(f"   ✓ Contains {len(snapshot.entries)} entries")

    # Modify state
    print("\n3. Modifying state...")
    await state.set("step", "2", StateScope.WORKFLOW, workflow_id)
    await state.set("status", "completed", StateScope.WORKFLOW, workflow_id)
    await state.set("data", {"count": 100}, StateScope.WORKFLOW, workflow_id)

    current = await state.get_all(StateScope.WORKFLOW, workflow_id)
    print(f"   Current state: {json.dumps(current, indent=4)}")

    # Restore snapshot
    print("\n4. Restoring snapshot (time-travel)...")
    restored = await state.restore_snapshot(snapshot)
    print(f"   ✓ Restored {restored} entries")

    restored_state = await state.get_all(StateScope.WORKFLOW, workflow_id)
    print(f"   Restored state: {json.dumps(restored_state, indent=4)}")

    # Cleanup
    await state.clear(StateScope.WORKFLOW, workflow_id)


async def demo_webhook_and_hitl_config():
    """Demo 6: Webhook and HITL node configuration."""
    print("\n" + "="*80)
    print("DEMO 6: Webhook and HITL Node Configuration")
    print("="*80)

    print("\n1. Webhook Node Configuration:")
    webhook_config = {
        "method": "POST",
        "authentication": {
            "type": "bearer",
            "token": "secret_token_123"
        },
        "responseStatus": 200,
        "path": "/webhook/workflow_123"
    }
    print(json.dumps(webhook_config, indent=2))

    print("\n2. HITL Node Configuration:")
    hitl_config = {
        "approvalType": "any",
        "timeout": 60,
        "timeoutAction": "reject",
        "notifyVia": ["email", "slack"],
        "approvers": [
            "manager@company.com",
            "supervisor@company.com"
        ]
    }
    print(json.dumps(hitl_config, indent=2))

    print("\n3. Complete Workflow Definition:")
    workflow = {
        "id": "workflow_webhook_hitl_demo",
        "name": "Payment Approval Workflow",
        "nodes": [
            {
                "id": "1",
                "type": "webhook",
                "data": {
                    "label": "Payment Request Webhook",
                    "webhookConfig": webhook_config
                }
            },
            {
                "id": "2",
                "type": "hitl",
                "data": {
                    "label": "Manager Approval",
                    "hitlConfig": hitl_config
                }
            },
            {
                "id": "3",
                "type": "tool",
                "data": {
                    "label": "Process Payment",
                    "toolConfig": {
                        "url": "https://api.payment.com/charge",
                        "method": "POST",
                        "body": json.dumps({
                            "amount": "{{webhook.amount}}",
                            "user_id": "{{webhook.user_id}}"
                        })
                    }
                }
            }
        ],
        "edges": [
            {"source": "1", "target": "2"},
            {"source": "2", "target": "3"}
        ]
    }
    print(json.dumps(workflow, indent=2))


async def main():
    """Run all demos."""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " " * 15 + "SHARED STATE MANAGER & WORKFLOW DEMO" + " " * 27 + "║")
    print("╚" + "="*78 + "╝")

    try:
        # Reset state manager
        reset_shared_state_manager()

        # Run demos
        await demo_basic_state_operations()
        await demo_scope_isolation()
        await demo_workflow_node_outputs()
        await demo_variable_substitution()
        await demo_state_snapshots()
        await demo_webhook_and_hitl_config()

        print("\n" + "="*80)
        print("✓ All demos completed successfully!")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
