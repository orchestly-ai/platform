"""
Human-in-the-Loop (HITL) Workflows Demo Script - P1 Feature #4

Demonstrates approval workflows and human review:
- Creating approval requests
- Multi-channel notifications
- Approval/rejection decisions
- Automatic timeout handling
- Escalation workflows
- Approval templates
- Analytics and reporting

Run: python backend/demo_hitl_workflows.py
"""

import sys
from pathlib import Path

# Add parent directory to path so backend.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text

from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.hitl_models import (
    ApprovalRequestCreate,
    ApprovalDecision,
    ApprovalTemplateCreate,
    ApprovalPriority,
    NotificationChannel,
    EscalationTrigger,
)
from backend.shared.hitl_service import HITLService


async def demo_hitl_workflows():
    """Run complete demonstration of HITL workflows."""

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("HUMAN-IN-THE-LOOP (HITL) WORKFLOWS DEMO")
        print("=" * 80)
        print()

        # Drop and recreate HITL tables to fix ENUM type mismatches
        print("Setting up demo environment...")
        try:
            await db.execute(text("DROP TABLE IF EXISTS approval_escalations CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS approval_notifications CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS approval_responses CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS approval_templates CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS approval_requests CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS approvalstatus CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS notificationchannel CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS escalationtrigger CASCADE"))
            await db.execute(text("DROP TYPE IF EXISTS approvalpriority CASCADE"))
            await db.commit()
            print("✓ Cleaned up old tables and types")
        except Exception as e:
            print(f"⚠ Cleanup warning: {str(e)[:100]}")
            await db.rollback()

    # Initialize database tables
    await init_db()

    async with AsyncSessionLocal() as db:
        # Tables are fresh after drop/recreate, no cleanup needed
        print("✓ Database ready\n")

        # Demo 1: Simple Approval Request
        print("📋 DEMO 1: Simple Approval Request")
        print("-" * 80)

        print("\n1. Creating budget approval request...")
        approval_data = ApprovalRequestCreate(
            workflow_execution_id=1001,
            task_id=501,
            node_id="approval_budget",
            title="Approve $50,000 Marketing Campaign Budget",
            description="Q1 2025 digital marketing campaign targeting enterprise customers",
            context={
                "campaign_name": "Enterprise Growth Q1 2025",
                "budget": 50000,
                "duration": "90 days",
                "expected_roi": "3x",
                "requested_by": "marketing_director",
            },
            required_approvers=["cfo_user_id", "ceo_user_id"],
            required_approval_count=2,  # Need both CFO and CEO
            priority=ApprovalPriority.HIGH,
            timeout_seconds=86400,  # 24 hours
            timeout_action="reject",  # Auto-reject if no response
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
        )

        approval = await HITLService.create_approval_request(
            db, approval_data, user_id="marketing_director", organization_id=1
        )

        print(f"   ✓ Approval request created: ID {approval.id}")
        print(f"   ✓ Title: {approval.title}")
        print(f"   ✓ Priority: {approval.priority}")
        print(f"   ✓ Required approvers: {len(approval.required_approvers)}")
        print(f"   ✓ Expires at: {approval.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   ✓ Status: {approval.status}")

        print("\n2. Notifications sent:")
        print(f"   ✓ Email notifications: {len([n for n in approval.notifications if n.channel == NotificationChannel.EMAIL])}")
        print(f"   ✓ Slack notifications: {len([n for n in approval.notifications if n.channel == NotificationChannel.SLACK])}")

        print()

        # Demo 2: Approval Decision (Single Approver)
        print("✅ DEMO 2: Approval Decision")
        print("-" * 80)

        print("\n1. Creating expense approval request (single approver)...")
        expense_data = ApprovalRequestCreate(
            workflow_execution_id=1002,
            task_id=502,
            node_id="approval_expense",
            title="Approve $500 Software License",
            description="Annual Figma subscription for design team",
            context={
                "vendor": "Figma",
                "amount": 500,
                "category": "Software",
                "team": "Design",
            },
            required_approvers=["manager_user_id"],
            required_approval_count=1,
            priority=ApprovalPriority.MEDIUM,
            timeout_seconds=3600,  # 1 hour
            timeout_action="approve",  # Auto-approve small expenses
        )

        expense_approval = await HITLService.create_approval_request(
            db, expense_data, user_id="designer_user_id", organization_id=1
        )

        print(f"   ✓ Expense approval created: ID {expense_approval.id}")
        print(f"   ✓ Amount: $500")

        print("\n2. Manager approves...")
        decision = ApprovalDecision(
            decision="approved",
            comment="Approved. Design team needs this for client work."
        )

        updated_approval = await HITLService.submit_decision(
            db,
            expense_approval.id,
            decision,
            approver_user_id="manager_user_id",
            approver_email="manager@company.com",
            ip_address="192.168.1.100",
        )

        print(f"   ✓ Status: {updated_approval.status}")
        print(f"   ✓ Approved by: {updated_approval.approved_by_user_id}")
        print(f"   ✓ Response time: {updated_approval.response_time_seconds:.1f}s")
        print(f"   ✓ Comment: {decision.comment}")

        print()

        # Demo 3: Rejection with Reason
        print("❌ DEMO 3: Rejection with Reason")
        print("-" * 80)

        print("\n1. Creating large capital expense request...")
        capex_data = ApprovalRequestCreate(
            workflow_execution_id=1003,
            task_id=503,
            node_id="approval_capex",
            title="Approve $100,000 Server Infrastructure",
            description="New on-premise server cluster for data processing",
            context={
                "type": "Infrastructure",
                "amount": 100000,
                "vendor": "Dell",
                "justification": "Replace aging 5-year-old servers",
            },
            required_approvers=["cto_user_id"],
            required_approval_count=1,
            priority=ApprovalPriority.HIGH,
        )

        capex_approval = await HITLService.create_approval_request(
            db, capex_data, user_id="it_manager", organization_id=1
        )

        print(f"   ✓ Capital expense request created: ID {capex_approval.id}")

        print("\n2. CTO rejects (prefers cloud solution)...")
        rejection = ApprovalDecision(
            decision="rejected",
            comment="Let's move to cloud infrastructure instead. More cost-effective and scalable. Please propose AWS/Azure solution."
        )

        rejected_approval = await HITLService.submit_decision(
            db,
            capex_approval.id,
            rejection,
            approver_user_id="cto_user_id",
        )

        print(f"   ✓ Status: {rejected_approval.status}")
        print(f"   ✓ Reason: {rejected_approval.rejection_reason}")

        print()

        # Demo 4: Multi-Approver Workflow
        print("👥 DEMO 4: Multi-Approver Workflow")
        print("-" * 80)

        print("\n1. Creating major hiring request (needs 3 approvals)...")
        hiring_data = ApprovalRequestCreate(
            workflow_execution_id=1004,
            task_id=504,
            node_id="approval_hiring",
            title="Approve 5 New Engineering Hires",
            description="Expand engineering team to meet product roadmap",
            context={
                "positions": ["Senior Backend Engineer", "Frontend Engineer", "DevOps Engineer", "QA Engineer", "Product Manager"],
                "estimated_cost": 750000,
                "duration": "Annual",
                "team": "Engineering",
            },
            required_approvers=["vp_eng", "cfo", "ceo"],
            required_approval_count=3,  # All 3 must approve
            priority=ApprovalPriority.CRITICAL,
            timeout_seconds=172800,  # 48 hours
        )

        hiring_approval = await HITLService.create_approval_request(
            db, hiring_data, user_id="hiring_manager", organization_id=1
        )

        print(f"   ✓ Hiring request created: ID {hiring_approval.id}")
        print(f"   ✓ Positions: 5")
        print(f"   ✓ Required approvals: 3")

        print("\n2. First approval (VP Engineering)...")
        await HITLService.submit_decision(
            db,
            hiring_approval.id,
            ApprovalDecision(decision="approved", comment="Critical for Q1 roadmap"),
            approver_user_id="vp_eng",
        )
        print("   ✓ VP Engineering approved")

        print("\n3. Second approval (CFO)...")
        await HITLService.submit_decision(
            db,
            hiring_approval.id,
            ApprovalDecision(decision="approved", comment="Budget approved"),
            approver_user_id="cfo",
        )
        print("   ✓ CFO approved")

        print("\n4. Third approval (CEO)...")
        final_approval = await HITLService.submit_decision(
            db,
            hiring_approval.id,
            ApprovalDecision(decision="approved", comment="Approved. Let's grow the team!"),
            approver_user_id="ceo",
        )

        print(f"   ✓ CEO approved")
        print(f"   ✓ Final status: {final_approval.status}")
        print(f"   ✓ All {final_approval.required_approval_count} approvals received!")

        print()

        # Demo 5: Escalation Workflow
        print("⬆️  DEMO 5: Escalation Workflow")
        print("-" * 80)

        print("\n1. Creating approval that will be escalated...")
        contract_data = ApprovalRequestCreate(
            workflow_execution_id=1005,
            task_id=505,
            node_id="approval_contract",
            title="Approve Enterprise Contract ($250K ARR)",
            description="3-year SaaS contract with Fortune 500 customer",
            context={
                "customer": "Fortune 500 Corp",
                "arr": 250000,
                "term": "3 years",
                "discount": "15%",
            },
            required_approvers=["sales_director"],
            required_approval_count=1,
            priority=ApprovalPriority.CRITICAL,
            timeout_seconds=7200,  # 2 hours
        )

        contract_approval = await HITLService.create_approval_request(
            db, contract_data, user_id="account_exec", organization_id=1
        )

        print(f"   ✓ Contract approval created: ID {contract_approval.id}")
        print(f"   ✓ Value: $250K ARR")

        print("\n2. Sales Director doesn't respond, escalating to VP Sales...")
        escalation = await HITLService.escalate_request(
            db,
            contract_approval.id,
            escalated_to_user_id="vp_sales",
            trigger=EscalationTrigger.NO_RESPONSE,
            escalated_by_user_id="account_exec",
            notes="Contract is time-sensitive, customer wants to close this week",
        )

        print(f"   ✓ Escalated to: {escalation.escalated_to_user_id}")
        print(f"   ✓ Escalation level: {escalation.level}")
        print(f"   ✓ Trigger: {escalation.trigger}")
        print(f"   ✓ Notes: {escalation.notes}")

        print("\n3. VP Sales approves...")
        escalated_approval = await HITLService.submit_decision(
            db,
            contract_approval.id,
            ApprovalDecision(decision="approved", comment="Great deal! Approve immediately."),
            approver_user_id="vp_sales",
        )

        print(f"   ✓ Status: {escalated_approval.status}")
        print(f"   ✓ Escalation resolved!")

        print()

        # Demo 6: Timeout Handling
        print("⏱️  DEMO 6: Timeout Handling")
        print("-" * 80)

        print("\n1. Creating approvals with timeout...")
        # Auto-approve timeout
        auto_approve_data = ApprovalRequestCreate(
            workflow_execution_id=1006,
            task_id=506,
            node_id="approval_auto",
            title="Approve Routine System Maintenance",
            description="Weekly database backup and optimization",
            required_approvers=["ops_manager"],
            required_approval_count=1,
            priority=ApprovalPriority.LOW,
            timeout_seconds=1,  # 1 second (for demo)
            timeout_action="approve",  # Auto-approve routine tasks
        )

        auto_approve = await HITLService.create_approval_request(
            db, auto_approve_data, user_id="sre_engineer", organization_id=1
        )

        print(f"   ✓ Auto-approve request created: ID {auto_approve.id}")
        print(f"   ✓ Timeout: 1 second")
        print(f"   ✓ Action: auto-approve")

        # Auto-reject timeout
        auto_reject_data = ApprovalRequestCreate(
            workflow_execution_id=1007,
            task_id=507,
            node_id="approval_reject",
            title="Approve Production Deployment (Off-Hours)",
            description="Deploy to production at 2 AM",
            required_approvers=["ops_manager"],
            required_approval_count=1,
            priority=ApprovalPriority.HIGH,
            timeout_seconds=1,  # 1 second (for demo)
            timeout_action="reject",  # Auto-reject risky off-hours deploys
        )

        auto_reject = await HITLService.create_approval_request(
            db, auto_reject_data, user_id="developer", organization_id=1
        )

        print(f"   ✓ Auto-reject request created: ID {auto_reject.id}")
        print(f"   ✓ Timeout: 1 second")
        print(f"   ✓ Action: auto-reject")

        print("\n2. Waiting for timeouts...")
        await asyncio.sleep(2)

        print("\n3. Processing timeouts...")
        processed = await HITLService.process_timeouts(db)
        print(f"   ✓ Processed {processed} timed-out requests")

        # Refresh to get updated status
        await db.refresh(auto_approve)
        await db.refresh(auto_reject)

        print(f"\n4. Results:")
        print(f"   - Auto-approve request: {auto_approve.status}")
        print(f"   - Auto-reject request: {auto_reject.status}")

        print()

        # Demo 7: Approval Templates
        print("📄 DEMO 7: Approval Templates")
        print("-" * 80)

        print("\n1. Creating reusable approval template...")

        # Check if template exists
        from sqlalchemy import select
        from backend.shared.hitl_models import ApprovalTemplate
        stmt = select(ApprovalTemplate).where(ApprovalTemplate.slug == "budget-approval-standard")
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            template = existing
            print(f"   ✓ Using existing template: {template.name}")
        else:
            template_data = ApprovalTemplateCreate(
                name="Standard Budget Approval",
                slug="budget-approval-standard",
            description="Standard process for budget approvals up to $10K",
            default_approvers=["department_manager", "finance_director"],
            required_approval_count=2,
            timeout_seconds=86400,  # 24 hours
            timeout_action="reject",
            escalation_enabled=True,
            escalation_chain=["vp", "cfo", "ceo"],
            escalation_timeout_seconds=43200,  # 12 hours per level
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            notification_template={
                "email": {
                    "subject": "Budget Approval Required: {title}",
                    "body": "Please review and approve budget request: {description}"
                },
                "slack": {
                    "text": "🔔 New approval required: {title}"
                }
            },
            category="Finance",
            tags=["budget", "finance", "standard"],
            )

            template = await HITLService.create_template(
                db, template_data, user_id="finance_director", organization_id=1
            )

            print(f"   ✓ Template created: {template.name}")
        print(f"   ✓ Slug: {template.slug}")
        print(f"   ✓ Default approvers: {len(template.default_approvers)}")
        print(f"   ✓ Escalation enabled: {template.escalation_enabled}")
        print(f"   ✓ Escalation chain: {len(template.escalation_chain)} levels")

        print("\n2. Using template for new approval...")
        template_approval = await HITLService.create_approval_request(
            db,
            ApprovalRequestCreate(
                workflow_execution_id=1008,
                task_id=508,
                node_id="approval_budget_template",
                title="Approve $8,500 Conference Budget",
                description="Q1 industry conference attendance",
                context={"event": "AI Summit 2025", "amount": 8500},
                required_approvers=template.default_approvers,
                required_approval_count=template.required_approval_count,
                priority=ApprovalPriority.MEDIUM,
                timeout_seconds=template.timeout_seconds,
                timeout_action=template.timeout_action,
            ),
            user_id="team_lead",
            organization_id=1,
        )

        print(f"   ✓ Approval created from template: ID {template_approval.id}")
        print(f"   ✓ Uses template defaults for approvers and timeout")

        print()

        # Demo 8: Pending Approvals (User View)
        print("📬 DEMO 8: Get My Pending Approvals")
        print("-" * 80)

        print("\n1. Getting pending approvals for CFO...")
        cfo_approvals = await HITLService.get_pending_approvals(
            db,
            approver_user_id="cfo",
            organization_id=1,
        )

        print(f"   ✓ Found {len(cfo_approvals)} pending approvals")
        for i, approval in enumerate(cfo_approvals[:3], 1):
            print(f"\n   {i}. {approval.title}")
            print(f"      Priority: {approval.priority}")
            print(f"      Requested: {approval.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if approval.expires_at:
                time_left = (approval.expires_at - datetime.utcnow()).total_seconds() / 3600
                print(f"      Time left: {time_left:.1f} hours")

        print()

        # Demo 9: Approval Analytics
        print("📊 DEMO 9: Approval Analytics")
        print("-" * 80)

        print("\n1. Getting approval statistics...")
        stats = await HITLService.get_approval_stats(
            db,
            organization_id=1,
        )

        print(f"\n2. Overall metrics:")
        print(f"   Total requests: {stats.total_requests}")
        print(f"   Pending: {stats.pending_requests}")
        print(f"   Approved: {stats.approved_requests}")
        print(f"   Rejected: {stats.rejected_requests}")
        print(f"   Timeout approvals: {stats.timeout_approvals}")
        print(f"   Timeout rejections: {stats.timeout_rejections}")

        print(f"\n3. Performance metrics:")
        print(f"   Avg response time: {stats.avg_response_time_seconds:.1f} seconds")
        print(f"   Approval rate: {stats.approval_rate:.1f}%")
        print(f"   Escalation rate: {stats.escalation_rate:.1f}%")

        print()

        # Demo 10: Cancel Approval
        print("🚫 DEMO 10: Cancel Approval Request")
        print("-" * 80)

        print("\n1. Creating approval to be cancelled...")
        cancel_data = ApprovalRequestCreate(
            workflow_execution_id=1009,
            task_id=509,
            node_id="approval_cancel",
            title="Approve Q2 Marketing Campaign",
            description="Campaign budget request",
            required_approvers=["marketing_vp"],
            required_approval_count=1,
            priority=ApprovalPriority.MEDIUM,
        )

        cancel_approval = await HITLService.create_approval_request(
            db, cancel_data, user_id="marketing_manager", organization_id=1
        )

        print(f"   ✓ Approval created: ID {cancel_approval.id}")
        print(f"   ✓ Status: {cancel_approval.status}")

        print("\n2. Requester cancels (plans changed)...")
        cancelled = await HITLService.cancel_request(
            db,
            cancel_approval.id,
            user_id="marketing_manager",
        )

        print(f"   ✓ Status: {cancelled.status}")
        print(f"   ✓ Workflow can now proceed without approval")

        print()

        # Summary
        print("=" * 80)
        print("DEMO SUMMARY")
        print("=" * 80)
        print()
        print("✅ Approval Workflows:")
        print("   - Simple approval (single approver)")
        print("   - Multi-approver workflow (3 required)")
        print("   - Approval with rejection")
        print("   - Escalation (no response → escalate to manager)")
        print()
        print("✅ Automation:")
        print("   - Auto-approve timeouts (routine tasks)")
        print("   - Auto-reject timeouts (risky tasks)")
        print("   - Timeout processing (background worker)")
        print()
        print("✅ Templates:")
        print("   - Reusable approval templates")
        print("   - Standard workflows for common scenarios")
        print("   - Escalation chains built-in")
        print()
        print("✅ Notifications:")
        print("   - Multi-channel (email, Slack, SMS)")
        print("   - Custom templates per channel")
        print("   - Delivery tracking")
        print()
        print("✅ Analytics:")
        print("   - Approval rate")
        print("   - Response time")
        print("   - Escalation rate")
        print("   - Pending approvals dashboard")
        print()
        print("✅ Flexibility:")
        print("   - Priority levels (low, medium, high, critical)")
        print("   - Custom timeouts")
        print("   - Context data for approvers")
        print("   - Cancellation support")
        print()
        print("🎉 HITL enables safe, controlled automation with human oversight!")
        print()


if __name__ == "__main__":
    asyncio.run(demo_hitl_workflows())
