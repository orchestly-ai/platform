"""
Minimal workflow test to isolate recursion issue
"""
import asyncio
from uuid import uuid4
from backend.database.session import AsyncSessionLocal
from backend.shared.workflow_models import WorkflowModel, WorkflowStatus

async def test():
    async with AsyncSessionLocal() as db:
        try:
            # Create minimal workflow
            workflow = WorkflowModel(
                workflow_id=uuid4(),
                organization_id="test_org",
                name="Minimal Test",
                description="Testing",
                status=WorkflowStatus.ACTIVE.value,
                nodes=[],
                edges=[]
            )

            db.add(workflow)
            await db.commit()
            print("✅ Workflow created successfully!")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
