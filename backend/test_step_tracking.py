#!/usr/bin/env python3
"""
Test script to verify real step tracking in workflow execution engine
"""

import asyncio
import sys
from datetime import datetime
from uuid import uuid4
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

from backend.database.session import AsyncSessionLocal
from backend.shared.workflow_models import (
    WorkflowModel, NodeType, WorkflowStatus
)
from backend.shared.workflow_service import get_workflow_service


async def test_step_tracking():
    """Test that workflow execution captures detailed steps"""

    print("=" * 80)
    print("Testing Real Step Tracking in Workflow Execution Engine")
    print("=" * 80)

    # Get database session
    async with AsyncSessionLocal() as db:
        try:
            # Create a simple test workflow with 3 LLM nodes
            workflow_id = uuid4()
            workflow = WorkflowModel(
                workflow_id=workflow_id,
                organization_id="test-org",
                name="Test Step Tracking Workflow",
                description="Test workflow to verify step tracking",
                status=WorkflowStatus.ACTIVE.value,
                version=1,
                nodes=[
                    {
                        "id": "input-1",
                        "type": "input",
                        "label": "Start",
                        "position": {"x": 100, "y": 100},
                        "data": {}
                    },
                    {
                        "id": "llm-1",
                        "type": "llm_openai",
                        "label": "Analyze Input",
                        "position": {"x": 300, "y": 100},
                        "data": {
                            "model": "gpt-4",
                            "prompt": "Analyze the following input: {input}"
                        }
                    },
                    {
                        "id": "llm-2",
                        "type": "llm_anthropic",
                        "label": "Generate Response",
                        "position": {"x": 500, "y": 100},
                        "data": {
                            "model": "claude-3-sonnet",
                            "prompt": "Generate a response based on: {llm-1}"
                        }
                    },
                    {
                        "id": "output-1",
                        "type": "output",
                        "label": "Complete",
                        "position": {"x": 700, "y": 100},
                        "data": {}
                    }
                ],
                edges=[
                    {"id": "e1", "source": "input-1", "target": "llm-1"},
                    {"id": "e2", "source": "llm-1", "target": "llm-2"},
                    {"id": "e3", "source": "llm-2", "target": "output-1"}
                ],
                max_execution_time_seconds=300,
                retry_on_failure=False
            )

            db.add(workflow)
            await db.commit()

            print(f"\n✓ Created test workflow: {workflow_id}")
            print(f"  - 4 nodes: input → llm_openai → llm_anthropic → output")

            # Execute the workflow
            print(f"\n→ Executing workflow...")
            service = get_workflow_service()

            input_data = {
                "message": "Test message for step tracking",
                "timestamp": datetime.utcnow().isoformat()
            }

            execution = await service.execute_workflow(
                workflow_id=workflow_id,
                input_data=input_data,
                triggered_by="test-user",
                db=db
            )

            print(f"\n✓ Workflow execution completed")
            print(f"  - Execution ID: {execution.execution_id}")
            print(f"  - Status: {execution.status.value}")
            print(f"  - Duration: {execution.duration_seconds:.2f}s")
            print(f"  - Total Cost: ${execution.total_cost:.6f}")

            # Verify execution steps were captured
            print(f"\n→ Verifying execution steps...")

            if not service.execution_steps:
                print("✗ ERROR: No execution steps captured!")
                return False

            print(f"\n✓ Captured {len(service.execution_steps)} execution steps:")
            print()

            for step in service.execution_steps:
                print(f"  Step {step['id']}: {step['name']}")
                print(f"    - Status: {step['status']}")
                print(f"    - Duration: {step['duration']}")

                state = step.get('state', {})
                if state.get('model'):
                    print(f"    - Model: {state['model']}")
                if state.get('tokens'):
                    print(f"    - Tokens: {state['tokens']}")
                if state.get('cost'):
                    print(f"    - Cost: ${state['cost']:.6f}")
                if state.get('error'):
                    print(f"    - Error: {state['error']}")
                print()

            # Check if steps were saved to database
            print(f"→ Checking database persistence...")

            await db.refresh(workflow)

            # Query the execution from database
            from sqlalchemy import select
            from backend.shared.workflow_models import WorkflowExecutionModel

            stmt = select(WorkflowExecutionModel).where(
                WorkflowExecutionModel.execution_id == execution.execution_id
            )
            result = await db.execute(stmt)
            execution_model = result.scalar_one_or_none()

            if not execution_model:
                print("✗ ERROR: Execution not found in database!")
                return False

            if not execution_model.node_executions:
                print("✗ ERROR: node_executions not saved to database!")
                return False

            print(f"\n✓ node_executions successfully saved to database")
            print(f"  - {len(execution_model.node_executions)} steps persisted")

            print("\n" + "=" * 80)
            print("✓ All tests passed! Step tracking is working correctly.")
            print("=" * 80)

            return True

        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(test_step_tracking())
    exit(0 if success else 1)
