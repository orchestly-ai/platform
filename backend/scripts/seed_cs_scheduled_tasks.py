"""
Seed Script: Customer Support Scheduled Tasks

Creates workflows and schedules for:
1. Daily Analytics Summary - Runs at 9 AM daily
2. Hourly Proactive Issue Scan - Runs every hour

Run:
    cd platform/agent-orchestration
    source backend/venv/bin/activate
    python -m backend.scripts.seed_cs_scheduled_tasks

This creates:
- Two workflows with LLM nodes for analytics and issue detection
- Two schedules that trigger these workflows automatically
"""

import asyncio
import os
import sys
from uuid import uuid4
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select

from backend.database.session import AsyncSessionLocal
from backend.shared.workflow_models import WorkflowModel, WorkflowStatus
from backend.shared.scheduler_models import ScheduledWorkflowModel, ScheduleType, ScheduleStatus


# ==================== Workflow Definitions ====================

DAILY_ANALYTICS_WORKFLOW = {
    "name": "CS Daily Analytics Summary",
    "description": "Generates daily analytics summary for customer support team. Analyzes ticket volume, response times, satisfaction scores, and agent performance.",
    "tags": ["customer-support", "analytics", "scheduled"],
    "nodes": [
        {
            "id": "fetch-metrics",
            "type": "integration",
            "position": {"x": 100, "y": 200},
            "data": {
                "label": "Fetch CS Metrics",
                "type": "integration",
                "integrationConfig": {
                    "type": "http",
                    "endpoint": "http://localhost:8030/api/analytics/daily",
                    "method": "GET",
                    "headers": {"Content-Type": "application/json"},
                },
                "status": "idle",
            }
        },
        {
            "id": "analyze-trends",
            "type": "worker",
            "position": {"x": 350, "y": 200},
            "data": {
                "label": "Analyze Trends",
                "type": "worker",
                "prompt": """Analyze the following customer support metrics and generate insights:

{{metrics}}

Provide:
1. Key performance highlights (positive trends)
2. Areas of concern (negative trends)
3. Agent performance summary
4. Recommendations for improvement
5. Customer satisfaction trends

Format as a concise executive summary suitable for morning standup.""",
                "modelSelection": "auto",
                "status": "idle",
            }
        },
        {
            "id": "send-report",
            "type": "integration",
            "position": {"x": 600, "y": 200},
            "data": {
                "label": "Send Report",
                "type": "integration",
                "integrationConfig": {
                    "type": "slack",
                    "channel": "#cs-daily-reports",
                    "message_template": "Daily CS Analytics Summary\n\n{{analysis}}",
                },
                "status": "idle",
            }
        }
    ],
    "edges": [
        {
            "id": "e1",
            "source": "fetch-metrics",
            "target": "analyze-trends",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e2",
            "source": "analyze-trends",
            "target": "send-report",
            "sourceHandle": "out",
            "targetHandle": "in",
        }
    ],
}

HOURLY_ISSUE_SCAN_WORKFLOW = {
    "name": "CS Proactive Issue Scanner",
    "description": "Scans for potential customer issues before they escalate. Checks for delivery delays, payment failures, high-priority unresolved tickets.",
    "tags": ["customer-support", "proactive", "scheduled", "escalation"],
    "nodes": [
        {
            "id": "scan-issues",
            "type": "integration",
            "position": {"x": 100, "y": 200},
            "data": {
                "label": "Scan for Issues",
                "type": "integration",
                "integrationConfig": {
                    "type": "http",
                    "endpoint": "http://localhost:8030/api/issues/scan",
                    "method": "GET",
                    "headers": {"Content-Type": "application/json"},
                },
                "status": "idle",
            }
        },
        {
            "id": "analyze-urgency",
            "type": "worker",
            "position": {"x": 350, "y": 200},
            "data": {
                "label": "Analyze Urgency",
                "type": "worker",
                "prompt": """Analyze these potential customer issues and prioritize them:

{{issues}}

For each issue:
1. Assign urgency score (1-10)
2. Estimate customer impact
3. Recommend immediate action
4. Suggest proactive outreach message

Focus on:
- Delivery delays > 3 days
- Payment failures
- VIP customer complaints
- Tickets approaching SLA breach

Output as JSON with structure:
{
  "critical_issues": [...],
  "warnings": [...],
  "proactive_outreach": [...]
}""",
                "modelSelection": "auto",
                "status": "idle",
            }
        },
        {
            "id": "route-critical",
            "type": "condition",
            "position": {"x": 600, "y": 150},
            "data": {
                "label": "Has Critical?",
                "type": "condition",
                "conditionConfig": {
                    "expression": "len(critical_issues) > 0",
                    "true_branch": "alert-team",
                    "false_branch": "log-status",
                },
                "status": "idle",
            }
        },
        {
            "id": "alert-team",
            "type": "integration",
            "position": {"x": 850, "y": 100},
            "data": {
                "label": "Alert Team",
                "type": "integration",
                "integrationConfig": {
                    "type": "slack",
                    "channel": "#cs-alerts",
                    "message_template": "URGENT: {{critical_count}} critical customer issues detected!\n\n{{critical_summary}}",
                },
                "status": "idle",
            }
        },
        {
            "id": "log-status",
            "type": "integration",
            "position": {"x": 850, "y": 250},
            "data": {
                "label": "Log Status",
                "type": "integration",
                "integrationConfig": {
                    "type": "http",
                    "endpoint": "http://localhost:8030/api/issues/scan-log",
                    "method": "POST",
                    "body_template": {"scan_time": "{{timestamp}}", "issues_found": "{{issue_count}}"},
                },
                "status": "idle",
            }
        }
    ],
    "edges": [
        {
            "id": "e1",
            "source": "scan-issues",
            "target": "analyze-urgency",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e2",
            "source": "analyze-urgency",
            "target": "route-critical",
            "sourceHandle": "out",
            "targetHandle": "in",
        },
        {
            "id": "e3",
            "source": "route-critical",
            "target": "alert-team",
            "sourceHandle": "true",
            "targetHandle": "in",
        },
        {
            "id": "e4",
            "source": "route-critical",
            "target": "log-status",
            "sourceHandle": "false",
            "targetHandle": "in",
        }
    ],
}


async def seed_scheduled_tasks():
    """Create workflows and schedules for CS tasks"""

    async with AsyncSessionLocal() as session:
        workflows_created = []

        # ==================== Create Workflows ====================

        # 1. Daily Analytics Summary Workflow
        stmt = select(WorkflowModel).where(WorkflowModel.name == "CS Daily Analytics Summary")
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Workflow 'CS Daily Analytics Summary' already exists (ID: {existing.workflow_id})")
            daily_workflow_id = existing.workflow_id
        else:
            daily_workflow = WorkflowModel(
                workflow_id=uuid4(),
                organization_id="org-customer-support",
                name=DAILY_ANALYTICS_WORKFLOW["name"],
                description=DAILY_ANALYTICS_WORKFLOW["description"],
                status=WorkflowStatus.ACTIVE.value,
                version=1,
                nodes=DAILY_ANALYTICS_WORKFLOW["nodes"],
                edges=DAILY_ANALYTICS_WORKFLOW["edges"],
                tags=DAILY_ANALYTICS_WORKFLOW["tags"],
            )
            session.add(daily_workflow)
            await session.flush()
            daily_workflow_id = daily_workflow.workflow_id
            workflows_created.append(("CS Daily Analytics Summary", daily_workflow_id))
            print(f"Created workflow: CS Daily Analytics Summary (ID: {daily_workflow_id})")

        # 2. Hourly Issue Scanner Workflow
        stmt = select(WorkflowModel).where(WorkflowModel.name == "CS Proactive Issue Scanner")
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Workflow 'CS Proactive Issue Scanner' already exists (ID: {existing.workflow_id})")
            hourly_workflow_id = existing.workflow_id
        else:
            hourly_workflow = WorkflowModel(
                workflow_id=uuid4(),
                organization_id="org-customer-support",
                name=HOURLY_ISSUE_SCAN_WORKFLOW["name"],
                description=HOURLY_ISSUE_SCAN_WORKFLOW["description"],
                status=WorkflowStatus.ACTIVE.value,
                version=1,
                nodes=HOURLY_ISSUE_SCAN_WORKFLOW["nodes"],
                edges=HOURLY_ISSUE_SCAN_WORKFLOW["edges"],
                tags=HOURLY_ISSUE_SCAN_WORKFLOW["tags"],
            )
            session.add(hourly_workflow)
            await session.flush()
            hourly_workflow_id = hourly_workflow.workflow_id
            workflows_created.append(("CS Proactive Issue Scanner", hourly_workflow_id))
            print(f"Created workflow: CS Proactive Issue Scanner (ID: {hourly_workflow_id})")

        # ==================== Create Schedules ====================

        # 1. Daily Analytics Schedule - 9 AM every day
        stmt = select(ScheduledWorkflowModel).where(ScheduledWorkflowModel.name == "CS Daily Analytics Summary")
        result = await session.execute(stmt)
        existing_schedule = result.scalar_one_or_none()

        if existing_schedule:
            print(f"Schedule 'CS Daily Analytics Summary' already exists (ID: {existing_schedule.schedule_id})")
        else:
            # Calculate next 9 AM
            now = datetime.utcnow()
            next_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if next_9am <= now:
                next_9am += timedelta(days=1)

            daily_schedule = ScheduledWorkflowModel(
                schedule_id=uuid4(),
                workflow_id=daily_workflow_id,
                organization_id="org-customer-support",
                name="CS Daily Analytics Summary",
                description="Runs daily at 9 AM to generate analytics summary",
                schedule_type=ScheduleType.CRON.value,
                cron_expression="0 9 * * *",  # 9 AM every day
                timezone="America/New_York",
                status=ScheduleStatus.ACTIVE.value,
                input_data={
                    "date_range": "yesterday",
                    "include_agent_breakdown": True,
                    "include_satisfaction_scores": True,
                },
                next_run_at=next_9am,
                external_scheduler=False,
            )
            session.add(daily_schedule)
            print(f"Created schedule: CS Daily Analytics Summary (Cron: 0 9 * * *)")

        # 2. Hourly Issue Scan Schedule - Every hour
        stmt = select(ScheduledWorkflowModel).where(ScheduledWorkflowModel.name == "CS Hourly Issue Scanner")
        result = await session.execute(stmt)
        existing_schedule = result.scalar_one_or_none()

        if existing_schedule:
            print(f"Schedule 'CS Hourly Issue Scanner' already exists (ID: {existing_schedule.schedule_id})")
        else:
            # Calculate next hour
            now = datetime.utcnow()
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

            hourly_schedule = ScheduledWorkflowModel(
                schedule_id=uuid4(),
                workflow_id=hourly_workflow_id,
                organization_id="org-customer-support",
                name="CS Hourly Issue Scanner",
                description="Runs every hour to scan for potential customer issues",
                schedule_type=ScheduleType.CRON.value,
                cron_expression="0 * * * *",  # Every hour at :00
                timezone="UTC",
                status=ScheduleStatus.ACTIVE.value,
                input_data={
                    "scan_types": ["delivery_delays", "payment_failures", "sla_breach", "vip_complaints"],
                    "threshold_days": 3,
                },
                next_run_at=next_hour,
                external_scheduler=False,
            )
            session.add(hourly_schedule)
            print(f"Created schedule: CS Hourly Issue Scanner (Cron: 0 * * * *)")

        await session.commit()

        print()
        print("=" * 60)
        print("Scheduled Tasks Summary")
        print("=" * 60)
        print()
        print("Workflows Created:")
        for name, wf_id in workflows_created:
            print(f"  - {name}: {wf_id}")
        print()
        print("Schedules:")
        print("  - Daily Analytics Summary: 9 AM daily (America/New_York)")
        print("  - Hourly Issue Scanner: Every hour at :00 (UTC)")
        print()
        print("The SchedulerRunner will automatically execute these workflows.")
        print("View in dashboard: http://localhost:3000/schedules")
        print()


if __name__ == "__main__":
    asyncio.run(seed_scheduled_tasks())
