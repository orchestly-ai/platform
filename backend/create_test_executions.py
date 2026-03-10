"""
Create test workflow executions for the Time-Travel Debugger
"""
import asyncio
import sys
import os
import random
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file in project root
from dotenv import load_dotenv
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}")

from backend.database.session import AsyncSessionLocal
from backend.shared.workflow_models import WorkflowModel, WorkflowExecutionModel, WorkflowStatus, ExecutionStatus


def generate_customer_support_steps(started: datetime, failed: bool = False, ticket_number: int = 0):
    """Generate detailed execution steps for Customer Support Email Analyzer workflow"""
    steps = []
    current_time = started
    step_id = 1

    # Step 1: Start
    steps.append({
        "id": step_id,
        "name": "Start",
        "timestamp": current_time.isoformat(),
        "duration": "0ms",
        "status": "completed",
        "state": {
            "input": f'Ticket #{4521 + ticket_number}: "My order hasn\'t arrived after 2 weeks. This is unacceptable! I want a full refund immediately."'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=10)

    # Step 2: Parse Email Input
    duration_ms = random.randint(5, 15)
    steps.append({
        "id": step_id,
        "name": "Parse Email Input",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": "Extract structured data from email...",
            "output": '{"customer_id": "12847", "email": "customer@example.com", "subject": "Order not received", "body": "..."}'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 3: Classify Ticket
    duration_ms = random.randint(1100, 1400)
    tokens = random.randint(800, 900)
    cost = round(tokens * 0.00000375, 6)
    steps.append({
        "id": step_id,
        "name": "Classify Ticket",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms/1000:.1f}s",
        "status": "failed" if failed else "completed",
        "state": {
            "input": "Classify this support ticket...",
            "output": '{"category": "shipping", "priority": "high", "urgency": "immediate"}' if not failed else None,
            "model": "gpt-4-turbo",
            "tokens": tokens,
            "cost": cost,
            "error": "LLM API rate limit exceeded" if failed else None
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    if failed:
        # If failed at classification, skip remaining steps
        steps.append({
            "id": step_id,
            "name": "Complete",
            "timestamp": current_time.isoformat(),
            "duration": "0ms",
            "status": "failed",
            "state": {
                "error": "Workflow failed at Classify Ticket step"
            }
        })
        return steps

    # Step 4: Extract Sentiment
    duration_ms = random.randint(700, 900)
    tokens = random.randint(380, 460)
    cost = round(tokens * 0.000002, 6)
    confidence = round(random.uniform(0.91, 0.97), 2)
    steps.append({
        "id": step_id,
        "name": "Extract Sentiment",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms/1000:.1f}s",
        "status": "completed",
        "state": {
            "input": "Analyze the sentiment of this customer message...",
            "output": "negative",
            "model": "claude-3-haiku",
            "tokens": tokens,
            "cost": cost,
            "confidence": confidence
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 5: Check Priority
    duration_ms = random.randint(8, 18)
    steps.append({
        "id": step_id,
        "name": "Check Priority",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": 'priority == "high" && sentiment == "negative"',
            "output": "true - escalating to manager"
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 6: Fetch Order History
    duration_ms = random.randint(200, 280)
    steps.append({
        "id": step_id,
        "name": "Fetch Order History",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": "GET /api/orders?customer_id=12847",
            "output": '{"orders": [{"id": "ORD-9821", "status": "shipped", "carrier": "FedEx", "tracking": "7892341234"}]}'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 7: Generate Response
    duration_ms = random.randint(1900, 2300)
    tokens = random.randint(1150, 1350)
    cost = round(tokens * 0.0000075, 6)
    steps.append({
        "id": step_id,
        "name": "Generate Response",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms/1000:.1f}s",
        "status": "completed",
        "state": {
            "input": "Generate empathetic response with order tracking info...",
            "output": "Dear valued customer, I sincerely apologize for the delay...",
            "model": "gpt-4",
            "tokens": tokens,
            "cost": cost
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 8: Send to Slack
    duration_ms = random.randint(140, 180)
    steps.append({
        "id": step_id,
        "name": "Send to Slack",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": 'POST /api/slack/send {"channel": "#escalations", "message": "..."}',
            "output": '{"ok": true, "ts": "1703644804.000200"}'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 9: Complete
    steps.append({
        "id": step_id,
        "name": "Complete",
        "timestamp": current_time.isoformat(),
        "duration": "0ms",
        "status": "completed",
        "state": {
            "output": "Workflow completed successfully"
        }
    })

    return steps


def generate_lead_scoring_steps(started: datetime, lead_number: int = 0):
    """Generate detailed execution steps for Lead Scoring Pipeline workflow"""
    steps = []
    current_time = started
    step_id = 1

    # Step 1: Start
    steps.append({
        "id": step_id,
        "name": "Start",
        "timestamp": current_time.isoformat(),
        "duration": "0ms",
        "status": "completed",
        "state": {
            "input": f'Webhook received: New lead from "Company {lead_number}"'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=8)

    # Step 2: Parse Webhook Data
    duration_ms = random.randint(10, 25)
    steps.append({
        "id": step_id,
        "name": "Parse Webhook Data",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": "Extract lead information from webhook payload...",
            "output": f'{{"email": "lead_{lead_number}@company.com", "company": "Company {lead_number}", "title": "VP of Engineering"}}'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 3: Enrich Lead Data
    duration_ms = random.randint(450, 650)
    steps.append({
        "id": step_id,
        "name": "Enrich Lead Data",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": "GET /api/clearbit/enrich?email=lead@company.com",
            "output": '{"company_size": "50-200", "industry": "SaaS", "revenue": "$10M-50M", "tech_stack": ["React", "AWS", "PostgreSQL"]}'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 4: Score Lead Quality
    duration_ms = random.randint(1400, 1800)
    tokens = random.randint(950, 1150)
    cost = round(tokens * 0.00000375, 6)
    score = random.randint(75, 95)
    steps.append({
        "id": step_id,
        "name": "Score Lead Quality",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms/1000:.1f}s",
        "status": "completed",
        "state": {
            "input": "Analyze lead quality based on company data and engagement...",
            "output": f'{{"score": {score}, "reasoning": "Strong company profile, relevant tech stack, senior title"}}',
            "model": "gpt-4-turbo",
            "tokens": tokens,
            "cost": cost
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 5: Classify Lead Tier
    duration_ms = random.randint(5, 12)
    tier = "hot" if score >= 85 else "warm" if score >= 70 else "cold"
    steps.append({
        "id": step_id,
        "name": "Classify Lead Tier",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": f"score >= 85 ? 'hot' : score >= 70 ? 'warm' : 'cold'",
            "output": tier
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 6: Update CRM
    duration_ms = random.randint(320, 480)
    steps.append({
        "id": step_id,
        "name": "Update CRM",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": f'POST /api/hubspot/contacts {{"email": "lead@company.com", "score": {score}, "tier": "{tier}"}}',
            "output": '{"id": "12345", "updated": true}'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 7: Complete
    steps.append({
        "id": step_id,
        "name": "Complete",
        "timestamp": current_time.isoformat(),
        "duration": "0ms",
        "status": "completed",
        "state": {
            "output": "Lead scoring completed successfully"
        }
    })

    return steps


def generate_running_lead_scoring_steps(started: datetime):
    """Generate partially completed steps for a running execution"""
    steps = []
    current_time = started
    step_id = 1

    # Step 1: Start
    steps.append({
        "id": step_id,
        "name": "Start",
        "timestamp": current_time.isoformat(),
        "duration": "0ms",
        "status": "completed",
        "state": {
            "input": 'Webhook received: New lead from "Acme Corp"'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=8)

    # Step 2: Parse Webhook Data
    duration_ms = 18
    steps.append({
        "id": step_id,
        "name": "Parse Webhook Data",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": "Extract lead information from webhook payload...",
            "output": '{"email": "processing@company.com", "company": "Acme Corp", "title": "CTO"}'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 3: Enrich Lead Data
    duration_ms = 520
    steps.append({
        "id": step_id,
        "name": "Enrich Lead Data",
        "timestamp": current_time.isoformat(),
        "duration": f"{duration_ms}ms",
        "status": "completed",
        "state": {
            "input": "GET /api/clearbit/enrich?email=processing@company.com",
            "output": '{"company_size": "200-500", "industry": "Enterprise Software", "revenue": "$50M+"}'
        }
    })
    step_id += 1
    current_time += timedelta(milliseconds=duration_ms)

    # Step 4: Score Lead Quality - Currently running
    steps.append({
        "id": step_id,
        "name": "Score Lead Quality",
        "timestamp": current_time.isoformat(),
        "duration": "Running...",
        "status": "running",
        "state": {
            "input": "Analyzing lead quality...",
            "model": "gpt-4-turbo"
        }
    })
    step_id += 1

    # Remaining steps are pending
    steps.append({
        "id": step_id,
        "name": "Classify Lead Tier",
        "timestamp": "Pending...",
        "duration": "0ms",
        "status": "pending",
        "state": {}
    })
    step_id += 1

    steps.append({
        "id": step_id,
        "name": "Update CRM",
        "timestamp": "Pending...",
        "duration": "0ms",
        "status": "pending",
        "state": {}
    })
    step_id += 1

    steps.append({
        "id": step_id,
        "name": "Complete",
        "timestamp": "Pending...",
        "duration": "0ms",
        "status": "pending",
        "state": {}
    })

    return steps


async def create_test_data():
    """Create test workflows and executions"""
    async with AsyncSessionLocal() as db:
        print("Creating test workflows and executions...")

        # Create a test workflow with detailed nodes matching execution steps
        workflow_id = uuid4()
        workflow = WorkflowModel(
            workflow_id=workflow_id,
            organization_id="default-org",
            name="Customer Support Email Analyzer",
            description="Analyzes customer support emails and categorizes them",
            tags=["customer-support", "email", "nlp"],
            status=WorkflowStatus.ACTIVE.value,
            version=1,
            nodes=[
                {"id": "start", "type": "trigger", "label": "Start"},
                {"id": "parse-email-input", "type": "tool", "label": "Parse Email Input"},
                {"id": "classify-ticket", "type": "llm", "label": "Classify Ticket"},
                {"id": "extract-sentiment", "type": "llm", "label": "Extract Sentiment"},
                {"id": "check-priority", "type": "condition", "label": "Check Priority"},
                {"id": "fetch-order-history", "type": "http", "label": "Fetch Order History"},
                {"id": "generate-response", "type": "llm", "label": "Generate Response"},
                {"id": "send-to-slack", "type": "integration", "label": "Send to Slack"},
                {"id": "complete", "type": "tool", "label": "Complete"}
            ],
            edges=[
                {"source": "start", "target": "parse-email-input"},
                {"source": "parse-email-input", "target": "classify-ticket"},
                {"source": "classify-ticket", "target": "extract-sentiment"},
                {"source": "extract-sentiment", "target": "check-priority"},
                {"source": "check-priority", "target": "fetch-order-history"},
                {"source": "fetch-order-history", "target": "generate-response"},
                {"source": "generate-response", "target": "send-to-slack"},
                {"source": "send-to-slack", "target": "complete"}
            ],
            environment="production",
            created_by="demo_user"
        )
        db.add(workflow)

        # Create another workflow with detailed nodes matching execution steps
        workflow_id_2 = uuid4()
        workflow_2 = WorkflowModel(
            workflow_id=workflow_id_2,
            organization_id="default-org",
            name="Lead Scoring Pipeline",
            description="Scores incoming leads based on engagement data",
            tags=["sales", "lead-scoring", "automation"],
            status=WorkflowStatus.ACTIVE.value,
            version=1,
            nodes=[
                {"id": "start", "type": "webhook", "label": "Start"},
                {"id": "parse-webhook-data", "type": "tool", "label": "Parse Webhook Data"},
                {"id": "enrich-lead-data", "type": "http", "label": "Enrich Lead Data"},
                {"id": "score-lead-quality", "type": "llm", "label": "Score Lead Quality"},
                {"id": "classify-lead-tier", "type": "condition", "label": "Classify Lead Tier"},
                {"id": "update-crm", "type": "http", "label": "Update CRM"},
                {"id": "complete", "type": "tool", "label": "Complete"}
            ],
            edges=[
                {"source": "start", "target": "parse-webhook-data"},
                {"source": "parse-webhook-data", "target": "enrich-lead-data"},
                {"source": "enrich-lead-data", "target": "score-lead-quality"},
                {"source": "score-lead-quality", "target": "classify-lead-tier"},
                {"source": "classify-lead-tier", "target": "update-crm"},
                {"source": "update-crm", "target": "complete"}
            ],
            environment="production",
            created_by="demo_user"
        )
        db.add(workflow_2)

        await db.commit()
        print(f"✅ Created workflows: {workflow.name}, {workflow_2.name}")

        # Create successful executions for first workflow
        base_time = datetime.utcnow()
        executions_created = 0

        for i in range(5):
            started = base_time - timedelta(hours=i*2)

            # Generate detailed execution steps
            steps = generate_customer_support_steps(started, failed=False, ticket_number=i)

            # Calculate total duration and cost from steps
            total_duration = 0
            total_cost = 0.0
            for step in steps:
                if step['duration'] != '0ms' and step['duration'] != 'Running...':
                    duration_str = step['duration']
                    # Check for 'ms' BEFORE 's' to avoid matching 'ms' as 's'
                    if 'ms' in duration_str:
                        total_duration += float(duration_str.replace('ms', '')) / 1000
                    elif 's' in duration_str:
                        total_duration += float(duration_str.replace('s', ''))
                if 'cost' in step.get('state', {}):
                    total_cost += step['state']['cost']

            completed = started + timedelta(seconds=total_duration)

            execution = WorkflowExecutionModel(
                execution_id=uuid4(),
                workflow_id=workflow_id,
                workflow_version=1,
                organization_id="default-org",
                triggered_by="demo_user",
                trigger_source="manual",
                status=ExecutionStatus.COMPLETED.value,
                started_at=started,
                completed_at=completed,
                duration_seconds=total_duration,
                input_data={"email": f"test_email_{i}@example.com", "subject": f"Support Request #{i}"},
                output_data={"category": "technical_support", "priority": "medium"},
                total_cost=total_cost,
                node_states={
                    "1": {"status": "completed"},
                    "2": {"status": "completed"},
                    "3": {"status": "completed"}
                },
                node_executions=steps
            )
            db.add(execution)
            executions_created += 1

        # Create a failed execution for first workflow
        started_failed = base_time - timedelta(hours=1)

        # Generate failed execution steps
        failed_steps = generate_customer_support_steps(started_failed, failed=True, ticket_number=99)

        # Calculate total duration and cost from steps
        total_duration_failed = 0
        total_cost_failed = 0.0
        for step in failed_steps:
            if step['duration'] != '0ms':
                duration_str = step['duration']
                # Check for 'ms' BEFORE 's' to avoid matching 'ms' as 's'
                if 'ms' in duration_str:
                    total_duration_failed += float(duration_str.replace('ms', '')) / 1000
                elif 's' in duration_str:
                    total_duration_failed += float(duration_str.replace('s', ''))
            if 'cost' in step.get('state', {}):
                total_cost_failed += step['state']['cost']

        execution_failed = WorkflowExecutionModel(
            execution_id=uuid4(),
            workflow_id=workflow_id,
            workflow_version=1,
            organization_id="default-org",
            triggered_by="demo_user",
            trigger_source="manual",
            status=ExecutionStatus.FAILED.value,
            started_at=started_failed,
            completed_at=started_failed + timedelta(seconds=total_duration_failed),
            duration_seconds=total_duration_failed,
            input_data={"email": "invalid@example.com", "subject": "Test"},
            error_message="LLM API rate limit exceeded",
            total_cost=total_cost_failed,
            node_states={
                "1": {"status": "completed"},
                "2": {"status": "failed"},
                "3": {"status": "pending"}
            },
            node_executions=failed_steps
        )
        db.add(execution_failed)
        executions_created += 1

        # Create executions for second workflow
        for i in range(3):
            started = base_time - timedelta(hours=i*3, minutes=30)

            # Generate detailed execution steps
            lead_steps = generate_lead_scoring_steps(started, lead_number=i)

            # Calculate total duration and cost from steps
            total_duration_lead = 0
            total_cost_lead = 0.0
            for step in lead_steps:
                if step['duration'] != '0ms':
                    duration_str = step['duration']
                    # Check for 'ms' BEFORE 's' to avoid matching 'ms' as 's'
                    if 'ms' in duration_str:
                        total_duration_lead += float(duration_str.replace('ms', '')) / 1000
                    elif 's' in duration_str:
                        total_duration_lead += float(duration_str.replace('s', ''))
                if 'cost' in step.get('state', {}):
                    total_cost_lead += step['state']['cost']

            completed = started + timedelta(seconds=total_duration_lead)

            # Extract score from the steps for output data
            score = 85
            tier = "qualified"
            for step in lead_steps:
                if step['name'] == 'Score Lead Quality':
                    import json
                    output = json.loads(step['state']['output'])
                    score = output['score']
                elif step['name'] == 'Classify Lead Tier':
                    tier = step['state']['output']

            execution = WorkflowExecutionModel(
                execution_id=uuid4(),
                workflow_id=workflow_id_2,
                workflow_version=1,
                organization_id="default-org",
                triggered_by="system",
                trigger_source="webhook",
                status=ExecutionStatus.COMPLETED.value,
                started_at=started,
                completed_at=completed,
                duration_seconds=total_duration_lead,
                input_data={"lead_email": f"lead_{i}@company.com", "company": f"Company {i}"},
                output_data={"score": score, "tier": tier},
                total_cost=total_cost_lead,
                node_states={
                    "1": {"status": "completed"},
                    "2": {"status": "completed"},
                    "3": {"status": "completed"}
                },
                node_executions=lead_steps
            )
            db.add(execution)
            executions_created += 1

        # Create a running execution
        started_running = base_time - timedelta(seconds=30)

        # Generate partially completed steps for running execution
        running_steps = generate_running_lead_scoring_steps(started_running)

        # Calculate cost from completed steps
        total_cost_running = 0.0
        for step in running_steps:
            if 'cost' in step.get('state', {}):
                total_cost_running += step['state']['cost']

        execution_running = WorkflowExecutionModel(
            execution_id=uuid4(),
            workflow_id=workflow_id_2,
            workflow_version=1,
            organization_id="default-org",
            triggered_by="system",
            trigger_source="webhook",
            status=ExecutionStatus.RUNNING.value,
            started_at=started_running,
            input_data={"lead_email": "processing@company.com", "company": "Acme Corp"},
            total_cost=total_cost_running,
            node_states={
                "1": {"status": "completed"},
                "2": {"status": "running"},
                "3": {"status": "pending"}
            },
            node_executions=running_steps
        )
        db.add(execution_running)
        executions_created += 1

        await db.commit()

        print(f"✅ Created {executions_created} workflow executions")
        print(f"   - 5 completed executions for '{workflow.name}'")
        print(f"   - 1 failed execution for '{workflow.name}'")
        print(f"   - 3 completed executions for '{workflow_2.name}'")
        print(f"   - 1 running execution for '{workflow_2.name}'")
        print("\n🎉 Test data created successfully!")
        print("\nYou can now visit http://localhost:3000/debugger to see the executions")


if __name__ == "__main__":
    asyncio.run(create_test_data())
