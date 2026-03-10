#!/usr/bin/env python3
"""
Demo: Human-in-the-Loop Approval Workflows

Demonstrates approval workflows that pause for human review.

Features demonstrated:
1. Creating approval requests
2. Multi-stage approvals
3. Timeout handling
4. Escalation chains
5. Approval templates

Usage:
    python demo_hitl_approval.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import random


class ApprovalStatus(Enum):
    """Approval request status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class Priority(Enum):
    """Approval priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalRequest:
    """An approval request"""
    id: str
    title: str
    description: str
    priority: Priority
    requested_by: str
    approvers: List[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    timeout_at: Optional[datetime] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    comments: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    escalation_level: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "requested_by": self.requested_by,
            "approvers": self.approvers,
            "decided_by": self.decided_by,
            "comments": self.comments
        }


@dataclass
class ApprovalTemplate:
    """Reusable approval template"""
    name: str
    slug: str
    default_approvers: List[str]
    timeout_hours: int = 24
    escalation_chain: List[str] = field(default_factory=list)
    auto_approve_on_timeout: bool = False
    required_fields: List[str] = field(default_factory=list)


class ApprovalWorkflow:
    """Manages approval workflows"""

    def __init__(self):
        self.requests: Dict[str, ApprovalRequest] = {}
        self.templates: Dict[str, ApprovalTemplate] = {}
        self.next_id = 1
        self.notification_handlers: List[Callable] = []

    def register_template(self, template: ApprovalTemplate):
        """Register an approval template"""
        self.templates[template.slug] = template

    def add_notification_handler(self, handler: Callable):
        """Add notification handler"""
        self.notification_handlers.append(handler)

    async def _notify(self, event: str, request: ApprovalRequest):
        """Send notifications"""
        for handler in self.notification_handlers:
            await handler(event, request)

    async def create_request(
        self,
        title: str,
        description: str,
        priority: Priority,
        requested_by: str,
        approvers: List[str],
        timeout_hours: int = 24,
        context: Dict[str, Any] = None
    ) -> ApprovalRequest:
        """Create a new approval request"""
        request_id = f"apr_{self.next_id:04d}"
        self.next_id += 1

        request = ApprovalRequest(
            id=request_id,
            title=title,
            description=description,
            priority=priority,
            requested_by=requested_by,
            approvers=approvers,
            timeout_at=datetime.utcnow() + timedelta(hours=timeout_hours),
            context=context or {}
        )

        self.requests[request_id] = request

        print(f"  📋 Created approval request: {request_id}")
        print(f"     Title: {title}")
        print(f"     Priority: {priority.value}")
        print(f"     Approvers: {', '.join(approvers)}")

        await self._notify("created", request)

        return request

    async def create_from_template(
        self,
        template_slug: str,
        title: str,
        description: str,
        requested_by: str,
        context: Dict[str, Any] = None,
        override_approvers: List[str] = None
    ) -> ApprovalRequest:
        """Create request from template"""
        template = self.templates.get(template_slug)
        if not template:
            raise ValueError(f"Template not found: {template_slug}")

        approvers = override_approvers or template.default_approvers

        return await self.create_request(
            title=title,
            description=description,
            priority=Priority.NORMAL,
            requested_by=requested_by,
            approvers=approvers,
            timeout_hours=template.timeout_hours,
            context=context
        )

    async def approve(
        self,
        request_id: str,
        approver: str,
        comments: str = None
    ) -> ApprovalRequest:
        """Approve a request"""
        request = self.requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending: {request.status.value}")

        if approver not in request.approvers:
            raise ValueError(f"{approver} is not authorized to approve")

        request.status = ApprovalStatus.APPROVED
        request.decided_by = approver
        request.decided_at = datetime.utcnow()
        request.comments = comments

        print(f"  ✅ Approved by {approver}: {request_id}")
        if comments:
            print(f"     Comments: {comments}")

        await self._notify("approved", request)

        return request

    async def reject(
        self,
        request_id: str,
        approver: str,
        reason: str
    ) -> ApprovalRequest:
        """Reject a request"""
        request = self.requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        request.status = ApprovalStatus.REJECTED
        request.decided_by = approver
        request.decided_at = datetime.utcnow()
        request.comments = reason

        print(f"  ❌ Rejected by {approver}: {request_id}")
        print(f"     Reason: {reason}")

        await self._notify("rejected", request)

        return request

    async def escalate(
        self,
        request_id: str,
        escalate_to: List[str],
        reason: str = None
    ) -> ApprovalRequest:
        """Escalate to higher level"""
        request = self.requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        request.approvers = escalate_to
        request.escalation_level += 1
        request.status = ApprovalStatus.ESCALATED

        print(f"  ⬆️  Escalated: {request_id}")
        print(f"     New approvers: {', '.join(escalate_to)}")
        print(f"     Level: {request.escalation_level}")

        # Reset status to pending for new approvers
        request.status = ApprovalStatus.PENDING

        await self._notify("escalated", request)

        return request

    async def process_timeouts(self):
        """Process timed out requests"""
        now = datetime.utcnow()
        processed = 0

        for request in self.requests.values():
            if request.status == ApprovalStatus.PENDING:
                if request.timeout_at and now >= request.timeout_at:
                    request.status = ApprovalStatus.TIMED_OUT
                    print(f"  ⏰ Timed out: {request.id}")
                    await self._notify("timed_out", request)
                    processed += 1

        return processed


class WorkflowEngine:
    """Simulates workflow execution with HITL"""

    def __init__(self, approval_workflow: ApprovalWorkflow):
        self.approval_workflow = approval_workflow
        self.paused_workflows: Dict[str, Dict] = {}

    async def execute_workflow(
        self,
        workflow_id: str,
        steps: List[Dict[str, Any]]
    ):
        """Execute workflow with potential HITL pauses"""
        print(f"\n🔄 Starting workflow: {workflow_id}")

        for i, step in enumerate(steps):
            step_type = step.get("type")
            step_name = step.get("name", f"Step {i+1}")

            print(f"\n  Step {i+1}: {step_name}")

            if step_type == "llm_call":
                # Simulate LLM call
                await asyncio.sleep(0.3)
                print(f"    🤖 LLM response generated")

            elif step_type == "human_approval":
                # Create approval request and pause
                request = await self.approval_workflow.create_request(
                    title=step.get("title", "Workflow Approval"),
                    description=step.get("description", "Please review"),
                    priority=Priority[step.get("priority", "NORMAL").upper()],
                    requested_by="workflow_engine",
                    approvers=step.get("approvers", ["default_approver"]),
                    context={"workflow_id": workflow_id, "step": i}
                )

                # Pause workflow
                self.paused_workflows[workflow_id] = {
                    "request_id": request.id,
                    "step": i,
                    "remaining_steps": steps[i+1:]
                }

                print(f"    ⏸️  Workflow paused, waiting for approval...")

                # Simulate approval decision (in real system, this would be async)
                await asyncio.sleep(0.5)

                # Simulate 80% approval rate
                if random.random() < 0.8:
                    await self.approval_workflow.approve(
                        request.id,
                        step.get("approvers", ["default_approver"])[0],
                        "Looks good!"
                    )
                    print(f"    ▶️  Workflow resumed")
                else:
                    await self.approval_workflow.reject(
                        request.id,
                        step.get("approvers", ["default_approver"])[0],
                        "Needs revision"
                    )
                    print(f"    ⛔ Workflow stopped due to rejection")
                    return False

            elif step_type == "code":
                # Simulate code execution
                await asyncio.sleep(0.2)
                print(f"    💻 Code executed")

            else:
                await asyncio.sleep(0.1)
                print(f"    ✓ Completed")

        print(f"\n✅ Workflow {workflow_id} completed!")
        return True


async def demo_basic_approval():
    """Demo: Basic approval workflow"""
    print("\n" + "="*60)
    print("Demo 1: Basic Approval Workflow")
    print("="*60)

    workflow = ApprovalWorkflow()

    # Create a simple approval
    request = await workflow.create_request(
        title="Refund Request - $500",
        description="Customer #12345 requests refund for damaged item",
        priority=Priority.NORMAL,
        requested_by="support_agent",
        approvers=["finance_manager"],
        timeout_hours=8,
        context={
            "customer_id": "12345",
            "order_id": "ORD-67890",
            "amount": 500.00
        }
    )

    print("\n📬 Manager reviews request...")
    await asyncio.sleep(0.5)

    # Approve the request
    await workflow.approve(
        request.id,
        "finance_manager",
        "Verified damage claim. Approved."
    )


async def demo_multi_stage_approval():
    """Demo: Multi-stage approval chain"""
    print("\n" + "="*60)
    print("Demo 2: Multi-Stage Approval")
    print("="*60)

    workflow = ApprovalWorkflow()

    # Register escalation template
    workflow.register_template(ApprovalTemplate(
        name="Large Purchase",
        slug="large-purchase",
        default_approvers=["manager"],
        timeout_hours=4,
        escalation_chain=["director", "vp", "cfo"]
    ))

    # Stage 1: Manager
    print("\n📋 Stage 1: Manager Approval")
    request = await workflow.create_from_template(
        template_slug="large-purchase",
        title="Equipment Purchase - $25,000",
        description="New servers for production environment",
        requested_by="it_lead",
        context={"amount": 25000}
    )

    await asyncio.sleep(0.3)
    await workflow.approve(request.id, "manager", "Within budget")

    # Stage 2: Director
    print("\n📋 Stage 2: Director Approval")
    await workflow.escalate(request.id, ["director"])
    await asyncio.sleep(0.3)
    await workflow.approve(request.id, "director", "Critical infrastructure")

    # Stage 3: VP (for amounts > $10k)
    print("\n📋 Stage 3: VP Approval")
    await workflow.escalate(request.id, ["vp"])
    await asyncio.sleep(0.3)
    await workflow.approve(request.id, "vp", "Final approval granted")


async def demo_workflow_with_hitl():
    """Demo: Workflow execution with HITL pauses"""
    print("\n" + "="*60)
    print("Demo 3: Workflow with HITL Pauses")
    print("="*60)

    approval_workflow = ApprovalWorkflow()
    engine = WorkflowEngine(approval_workflow)

    # Define workflow with approval steps
    workflow_steps = [
        {
            "type": "llm_call",
            "name": "Generate Code"
        },
        {
            "type": "human_approval",
            "name": "Code Review",
            "title": "Code Review Required",
            "description": "Please review the generated code before deployment",
            "priority": "HIGH",
            "approvers": ["senior_developer"]
        },
        {
            "type": "code",
            "name": "Run Tests"
        },
        {
            "type": "human_approval",
            "name": "Deploy Approval",
            "title": "Production Deployment",
            "description": "Approve deployment to production",
            "priority": "CRITICAL",
            "approvers": ["devops_lead", "tech_lead"]
        },
        {
            "type": "code",
            "name": "Deploy to Production"
        }
    ]

    await engine.execute_workflow("WF-001", workflow_steps)


async def demo_timeout_handling():
    """Demo: Timeout and auto-escalation"""
    print("\n" + "="*60)
    print("Demo 4: Timeout and Escalation")
    print("="*60)

    workflow = ApprovalWorkflow()

    # Create request with short timeout
    request = await workflow.create_request(
        title="Urgent Security Patch",
        description="Critical vulnerability fix needs deployment",
        priority=Priority.CRITICAL,
        requested_by="security_team",
        approvers=["on_call_engineer"],
        timeout_hours=1,  # Short timeout
        context={"cve": "CVE-2025-12345"}
    )

    print("\n⏰ Simulating timeout (on-call not responding)...")
    # Simulate timeout by setting it to past
    request.timeout_at = datetime.utcnow() - timedelta(minutes=1)

    await workflow.process_timeouts()

    print("\n⬆️  Auto-escalating to backup approvers...")
    # Escalate to backup
    request.status = ApprovalStatus.PENDING
    await workflow.escalate(
        request.id,
        ["backup_engineer", "manager"],
        "Primary approver timed out"
    )

    await asyncio.sleep(0.3)
    await workflow.approve(request.id, "manager", "Emergency approval")


async def demo_parallel_approvals():
    """Demo: Parallel approval requirements"""
    print("\n" + "="*60)
    print("Demo 5: Parallel Approvals (All Must Approve)")
    print("="*60)

    workflow = ApprovalWorkflow()

    # Create request requiring multiple approvals
    print("\n📋 Creating request requiring 3 approvals...")

    request = await workflow.create_request(
        title="Production Database Migration",
        description="Migrate customer data to new schema",
        priority=Priority.HIGH,
        requested_by="dba_team",
        approvers=["dba_lead", "security_officer", "product_owner"],
        timeout_hours=24,
        context={
            "affected_tables": 15,
            "estimated_downtime": "30 minutes"
        }
    )

    # Simulate parallel approvals
    print("\n📬 Collecting approvals...")

    approvers = [
        ("dba_lead", "Schema validated, migration plan approved"),
        ("security_officer", "Data handling compliant with policies"),
        ("product_owner", "Customer communication prepared")
    ]

    for approver, comment in approvers:
        await asyncio.sleep(0.4)
        print(f"\n  👤 {approver} reviewing...")
        # In a real system, we'd track individual approvals
        # For demo, we'll show sequential approval

    # Final approval
    await workflow.approve(request.id, "dba_lead", "All stakeholders aligned")


async def main():
    """Run all demos"""
    print("="*60)
    print("👥 Human-in-the-Loop Approval Workflows Demo")
    print("="*60)
    print("\nThis demo shows approval workflows that pause for human review.")

    await demo_basic_approval()
    await demo_multi_stage_approval()
    await demo_workflow_with_hitl()
    await demo_timeout_handling()
    await demo_parallel_approvals()

    print("\n" + "="*60)
    print("✅ All demos completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
