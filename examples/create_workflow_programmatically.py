#!/usr/bin/env python3
"""
Example: Create and Execute Workflows Programmatically

This script demonstrates how to use the Agent Orchestration API to:
1. Create a workflow with nodes and edges
2. Execute the workflow with input data
3. Monitor execution via WebSocket for real-time updates

API Endpoints:
- POST /api/workflows - Create a workflow
- GET /api/workflows - List workflows
- GET /api/workflows/{id} - Get workflow details
- PUT /api/workflows/{id} - Update workflow
- DELETE /api/workflows/{id} - Delete workflow
- POST /api/workflows/{id}/execute - Execute workflow (REST, async)
- WS /api/workflows/{id}/execute - Execute with real-time updates
"""

import asyncio
import json
import httpx
import websockets
from uuid import uuid4
from typing import Optional, Dict, Any, List


# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


def create_ticket_classifier_workflow() -> Dict[str, Any]:
    """
    Create a ticket classifier workflow definition.

    This workflow:
    1. Receives ticket data via trigger
    2. Classifies the ticket using an LLM
    3. Sends the classification to Discord

    Returns:
        Workflow definition dict
    """
    return {
        "name": "Ticket Classifier Workflow",
        "description": "Classifies support tickets and sends results to Discord",
        "tags": ["support", "classification", "discord"],
        "nodes": [
            # Trigger node - entry point for the workflow
            {
                "id": "trigger-1",
                "type": "trigger",
                "position": {"x": 100, "y": 200},
                "data": {
                    "label": "Manual Trigger",
                    "type": "trigger",
                    "triggerConfig": {
                        "triggerType": "manual",
                        "inputSchema": {
                            "ticket_id": "string",
                            "title": "string",
                            "description": "string"
                        }
                    }
                }
            },
            # Worker node - LLM that classifies the ticket
            {
                "id": "worker-classifier",
                "type": "worker",
                "position": {"x": 400, "y": 200},
                "data": {
                    "label": "Ticket Classifier",
                    "type": "worker",
                    "llmModel": "llama",  # Will be routed via SmartRouter
                    "capabilities": ["classification", "analysis"],
                    "config": {
                        "prompt": """You are a support ticket classifier. Analyze the following ticket and classify its priority.

Classification rules:
- HIGH: System down, security issues, data loss, blocking multiple users
- MEDIUM: Feature broken, workaround exists, affects some users
- LOW: Questions, minor bugs, cosmetic issues, feature requests

Respond in this exact JSON format:
{
  "priority": "HIGH|MEDIUM|LOW",
  "category": "bug|feature|question|security|performance",
  "reason": "brief explanation"
}

Ticket:
Title: {{input.title}}
Description: {{input.description}}""",
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                }
            },
            # Integration node - sends result to Discord
            {
                "id": "integration-discord",
                "type": "integration",
                "position": {"x": 700, "y": 200},
                "data": {
                    "label": "Discord",
                    "type": "integration",
                    "integrationConfig": {
                        "integrationType": "discord",
                        "action": "send_message",
                        "parameters": {
                            "channel_id": "YOUR_CHANNEL_ID",  # Replace with actual channel ID
                            "content": "**Ticket Classification Result**\n\nTicket: {{input.title}}\n\n{{Ticket Classifier.content}}"
                        }
                    }
                }
            }
        ],
        "edges": [
            # Connect trigger -> classifier
            {
                "id": "edge-1",
                "source": "trigger-1",
                "target": "worker-classifier",
                "type": "default"
            },
            # Connect classifier -> discord
            {
                "id": "edge-2",
                "source": "worker-classifier",
                "target": "integration-discord",
                "type": "default"
            }
        ]
    }


def create_multi_agent_workflow() -> Dict[str, Any]:
    """
    Create a multi-agent workflow with supervisor and workers.

    This demonstrates:
    - Supervisor agent delegating to worker agents
    - Parallel execution
    - Variable passing between nodes

    Returns:
        Workflow definition dict
    """
    return {
        "name": "Multi-Agent Research Workflow",
        "description": "Research workflow with supervisor and specialized workers",
        "tags": ["research", "multi-agent"],
        "nodes": [
            {
                "id": "trigger-1",
                "type": "trigger",
                "position": {"x": 100, "y": 300},
                "data": {
                    "label": "Research Trigger",
                    "type": "trigger",
                    "triggerConfig": {
                        "triggerType": "manual",
                        "inputSchema": {
                            "research_topic": "string",
                            "depth": "string"
                        }
                    }
                }
            },
            {
                "id": "supervisor-1",
                "type": "supervisor",
                "position": {"x": 400, "y": 300},
                "data": {
                    "label": "Research Coordinator",
                    "type": "supervisor",
                    "llmModel": "gpt-4",
                    "capabilities": ["planning", "coordination", "synthesis"],
                    "config": {
                        "prompt": """You are a research coordinator. Given the topic: {{input.research_topic}}

Create a research plan with 3 key areas to investigate.
Format your response as a numbered list.""",
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                }
            },
            {
                "id": "worker-analyst",
                "type": "worker",
                "position": {"x": 700, "y": 150},
                "data": {
                    "label": "Data Analyst",
                    "type": "worker",
                    "llmModel": "llama",
                    "capabilities": ["analysis", "statistics"],
                    "config": {
                        "prompt": """Based on the research plan from the coordinator:
{{Research Coordinator.content}}

Provide data analysis insights for the topic: {{input.research_topic}}""",
                        "temperature": 0.5,
                        "max_tokens": 800
                    }
                }
            },
            {
                "id": "worker-writer",
                "type": "worker",
                "position": {"x": 700, "y": 450},
                "data": {
                    "label": "Content Writer",
                    "type": "worker",
                    "llmModel": "claude",
                    "capabilities": ["writing", "summarization"],
                    "config": {
                        "prompt": """Based on the research plan from the coordinator:
{{Research Coordinator.content}}

Write a summary paragraph about: {{input.research_topic}}""",
                        "temperature": 0.7,
                        "max_tokens": 600
                    }
                }
            },
            {
                "id": "worker-synthesizer",
                "type": "worker",
                "position": {"x": 1000, "y": 300},
                "data": {
                    "label": "Report Synthesizer",
                    "type": "worker",
                    "llmModel": "gpt-4",
                    "capabilities": ["synthesis", "reporting"],
                    "config": {
                        "prompt": """Combine the following into a final research report:

Research Plan:
{{Research Coordinator.content}}

Data Analysis:
{{Data Analyst.content}}

Written Summary:
{{Content Writer.content}}

Create a cohesive final report.""",
                        "temperature": 0.5,
                        "max_tokens": 1500
                    }
                }
            }
        ],
        "edges": [
            {"id": "e1", "source": "trigger-1", "target": "supervisor-1"},
            {"id": "e2", "source": "supervisor-1", "target": "worker-analyst"},
            {"id": "e3", "source": "supervisor-1", "target": "worker-writer"},
            {"id": "e4", "source": "worker-analyst", "target": "worker-synthesizer"},
            {"id": "e5", "source": "worker-writer", "target": "worker-synthesizer"}
        ]
    }


async def create_workflow(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a workflow via the REST API.

    Args:
        workflow_data: Workflow definition

    Returns:
        Created workflow with ID
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/workflows",
            json=workflow_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()


async def get_workflow(workflow_id: str) -> Dict[str, Any]:
    """Get workflow by ID."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/workflows/{workflow_id}")
        response.raise_for_status()
        return response.json()


async def list_workflows() -> List[Dict[str, Any]]:
    """List all workflows."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/workflows")
        response.raise_for_status()
        return response.json()["workflows"]


async def update_workflow(workflow_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update a workflow."""
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/api/workflows/{workflow_id}",
            json=updates,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()


async def delete_workflow(workflow_id: str) -> bool:
    """Delete a workflow."""
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BASE_URL}/api/workflows/{workflow_id}")
        return response.status_code == 204


async def execute_workflow_rest(
    workflow_id: str,
    input_data: Optional[Dict[str, Any]] = None,
    jwt_token: str = "test-token"
) -> Dict[str, Any]:
    """
    Execute workflow via REST API (non-blocking, returns execution ID).

    For real-time updates, use execute_workflow_websocket instead.

    Args:
        workflow_id: Workflow UUID
        input_data: Input data for the workflow
        jwt_token: JWT token for authentication

    Returns:
        Execution info with execution_id
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/workflows/{workflow_id}/execute",
            json={"input": input_data or {}},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {jwt_token}"
            }
        )
        response.raise_for_status()
        return response.json()


async def execute_workflow_websocket(
    workflow_id: str,
    workflow_data: Dict[str, Any],
    input_data: Optional[Dict[str, Any]] = None,
    on_event: Optional[callable] = None
) -> List[Dict[str, Any]]:
    """
    Execute workflow via WebSocket with real-time event streaming.

    Args:
        workflow_id: Workflow UUID
        workflow_data: Full workflow definition (nodes, edges)
        input_data: Input data for the workflow
        on_event: Callback function for each event

    Returns:
        List of all execution events
    """
    events = []
    uri = f"{WS_URL}/api/workflows/{workflow_id}/execute"

    async with websockets.connect(uri) as websocket:
        # Send start command with workflow data
        start_message = {
            "action": "start",
            "workflow": workflow_data,
            "inputData": input_data or {}
        }
        await websocket.send(json.dumps(start_message))

        # Receive events until completion or error
        while True:
            try:
                message = await websocket.recv()
                event = json.loads(message)
                events.append(event)

                if on_event:
                    on_event(event)

                # Check for terminal events
                if event.get("event_type") in ["execution_completed", "execution_failed", "error"]:
                    break

            except websockets.exceptions.ConnectionClosed:
                break

    return events


def print_event(event: Dict[str, Any]):
    """Pretty print a workflow execution event."""
    event_type = event.get("event_type", "unknown")
    node_id = event.get("node_id", "")
    status = event.get("status", "")
    message = event.get("message", "")

    # Color codes for terminal
    colors = {
        "execution_started": "\033[94m",  # Blue
        "node_status_changed": "\033[93m",  # Yellow
        "execution_completed": "\033[92m",  # Green
        "execution_failed": "\033[91m",     # Red
        "error": "\033[91m",                # Red
    }
    reset = "\033[0m"
    color = colors.get(event_type, "")

    print(f"{color}[{event_type}]{reset} {node_id} - {status}: {message}")

    if event.get("data"):
        print(f"  Data: {json.dumps(event['data'], indent=2)[:200]}...")
    if event.get("cost"):
        print(f"  Cost: ${event['cost']:.6f}")
    if event.get("actual_model"):
        print(f"  Model: {event['actual_provider']}/{event['actual_model']}")


async def main():
    """Main example demonstrating workflow creation and execution."""

    print("=" * 60)
    print("Agent Orchestration - Programmatic Workflow Example")
    print("=" * 60)

    # Example 1: Create a ticket classifier workflow
    print("\n📝 Creating Ticket Classifier Workflow...")
    workflow_def = create_ticket_classifier_workflow()

    try:
        created = await create_workflow(workflow_def)
        workflow_id = created["id"]
        print(f"✅ Created workflow: {workflow_id}")
        print(f"   Name: {created['name']}")
        print(f"   Nodes: {len(created['nodes'])}")
        print(f"   Edges: {len(created['edges'])}")
    except httpx.HTTPError as e:
        print(f"❌ Failed to create workflow: {e}")
        return

    # Example 2: Execute the workflow with input data
    print("\n🚀 Executing workflow with sample ticket...")

    input_data = {
        "ticket_id": "TICKET-12345",
        "title": "Production database connection timeout",
        "description": "Users are experiencing intermittent connection timeouts when accessing the production database. This started around 2pm today and is affecting approximately 30% of requests. No recent deployments or configuration changes were made."
    }

    print(f"   Input: {json.dumps(input_data, indent=2)}")

    try:
        # Execute via WebSocket for real-time updates
        events = await execute_workflow_websocket(
            workflow_id=workflow_id,
            workflow_data={
                "nodes": created["nodes"],
                "edges": created["edges"]
            },
            input_data=input_data,
            on_event=print_event
        )

        print(f"\n📊 Execution completed with {len(events)} events")

        # Find the classifier output
        for event in events:
            if event.get("node_id") and "classifier" in event.get("node_id", "").lower():
                if event.get("data", {}).get("content"):
                    print(f"\n🎯 Classification Result:")
                    print(event["data"]["content"])

    except Exception as e:
        print(f"❌ Execution failed: {e}")

    # Example 3: List all workflows
    print("\n📋 Listing all workflows...")
    try:
        workflows = await list_workflows()
        print(f"   Found {len(workflows)} workflows:")
        for wf in workflows[:5]:  # Show first 5
            print(f"   - {wf['id']}: {wf['name']}")
    except httpx.HTTPError as e:
        print(f"❌ Failed to list workflows: {e}")

    # Cleanup (optional)
    # print("\n🧹 Cleaning up...")
    # await delete_workflow(workflow_id)
    # print(f"   Deleted workflow: {workflow_id}")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
