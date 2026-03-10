#!/usr/bin/env python3 -u
"""
Scheduler Demo - Test the cron-based workflow scheduling system

This demo shows:
1. Creating scheduled workflows with different schedule types
2. BYOS (Bring Your Own Scheduler) mode with external triggers
3. Execution history tracking
4. Tier-based limits

Run with: python -m backend.demo_scheduler
"""
# Force unbuffered output
import sys
sys.stdout.reconfigure(line_buffering=True)
print("demo_scheduler: starting...", file=sys.stderr, flush=True)

import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from uuid import uuid4

print("demo_scheduler: stdlib imports done", file=sys.stderr, flush=True)

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("USE_SQLITE", "true")

print("demo_scheduler: loading sqlalchemy...", file=sys.stderr, flush=True)
from sqlalchemy import text

print("demo_scheduler: loading backend modules...", file=sys.stderr, flush=True)
from backend.database.session import AsyncSessionLocal, init_db
from backend.shared.scheduler_service import (
    SchedulerService,
    ScheduleLimitExceeded,
    InvalidCronExpression,
)
from backend.shared.scheduler_models import ScheduleType, ScheduleStatus

print("demo_scheduler: imports complete", file=sys.stderr, flush=True)


async def demo_scheduler():
    """Demonstrate scheduler functionality"""

    print("\n" + "=" * 70, flush=True)
    print("🕐 SCHEDULER DEMO - Cron-based Workflow Scheduling", flush=True)
    print("=" * 70, flush=True)

    # Drop and recreate scheduler tables to fix ENUM type mismatches
    use_sqlite = os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes")
    print(f"\nConnecting to database (SQLite: {use_sqlite})...", flush=True)
    async with AsyncSessionLocal() as db:
        print("Setting up demo environment...", flush=True)
        try:
            await db.execute(text("DROP TABLE IF EXISTS schedule_execution_history CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS organization_schedule_limits CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS scheduled_workflows CASCADE"))
            # DROP TYPE only works on PostgreSQL, not SQLite
            if not use_sqlite:
                await db.execute(text("DROP TYPE IF EXISTS schedulestatus CASCADE"))
                await db.execute(text("DROP TYPE IF EXISTS scheduletype CASCADE"))
            await db.commit()
            print("✓ Cleaned up old tables and types", flush=True)
        except Exception as e:
            print(f"⚠ Cleanup warning: {str(e)[:100]}", flush=True)
            await db.rollback()

    # Initialize database
    print("Initializing database tables...", flush=True)
    await init_db()
    print("✓ Database initialized", flush=True)

    async with AsyncSessionLocal() as db:
        # Tables are fresh after drop/recreate, no cleanup needed
        print("✓ Database ready\n")

        service = SchedulerService(db)

        # Demo organization and workflow
        org_id = "demo-org-scheduler"
        workflow_id = uuid4()

        print("\n📋 Setup:")
        print(f"   Organization: {org_id}")
        print(f"   Workflow ID: {workflow_id}")

        # ==================== 1. Cron Schedule ====================
        print("\n" + "-" * 50)
        print("1️⃣ Creating CRON Schedule (9 AM daily)")
        print("-" * 50)

        try:
            cron_schedule = await service.create_schedule(
                organization_id=org_id,
                workflow_id=workflow_id,
                name="Daily Report Generator",
                description="Generates daily summary report every morning",
                schedule_type=ScheduleType.CRON,
                cron_expression="0 9 * * *",  # 9 AM daily
                timezone="America/New_York",
                input_data={"report_type": "daily_summary", "format": "pdf"},
                created_by="demo@example.com",
            )
            print(f"   ✅ Created schedule: {cron_schedule.schedule_id}")
            print(f"   📅 Next run: {cron_schedule.next_run_at}")
            print(f"   ⏰ Cron: {cron_schedule.cron_expression}")
            print(f"   🌍 Timezone: {cron_schedule.timezone}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # ==================== 2. Interval Schedule ====================
        print("\n" + "-" * 50)
        print("2️⃣ Creating INTERVAL Schedule (every 2 hours)")
        print("-" * 50)

        try:
            interval_schedule = await service.create_schedule(
                organization_id=org_id,
                workflow_id=workflow_id,
                name="Health Check Monitor",
                description="Runs health checks on all services",
                schedule_type=ScheduleType.INTERVAL,
                interval_seconds=7200,  # 2 hours
                input_data={"check_type": "full", "notify_on_failure": True},
                created_by="demo@example.com",
            )
            print(f"   ✅ Created schedule: {interval_schedule.schedule_id}")
            print(f"   📅 Next run: {interval_schedule.next_run_at}")
            print(f"   ⏱️ Interval: {interval_schedule.interval_seconds} seconds")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # ==================== 3. One-Time Schedule ====================
        print("\n" + "-" * 50)
        print("3️⃣ Creating ONE-TIME Schedule (30 minutes from now)")
        print("-" * 50)

        try:
            run_at = datetime.utcnow() + timedelta(minutes=30)
            once_schedule = await service.create_schedule(
                organization_id=org_id,
                workflow_id=workflow_id,
                name="Database Migration",
                description="One-time database schema migration",
                schedule_type=ScheduleType.ONCE,
                run_at=run_at,
                input_data={"migration_version": "v2.5.0"},
                created_by="demo@example.com",
            )
            print(f"   ✅ Created schedule: {once_schedule.schedule_id}")
            print(f"   📅 Scheduled for: {once_schedule.next_run_at}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # ==================== 4. BYOS Mode ====================
        print("\n" + "-" * 50)
        print("4️⃣ Creating BYOS Schedule (External Scheduler)")
        print("-" * 50)

        try:
            byos_schedule = await service.create_schedule(
                organization_id=org_id,
                workflow_id=workflow_id,
                name="AWS EventBridge Triggered",
                description="Triggered by customer's AWS EventBridge",
                schedule_type=ScheduleType.CRON,
                cron_expression="*/15 * * * *",  # Every 15 minutes
                external_scheduler=True,  # BYOS mode
                input_data={"source": "aws_eventbridge"},
                created_by="demo@example.com",
            )
            print(f"   ✅ Created BYOS schedule: {byos_schedule.schedule_id}")
            print(f"   🔗 Trigger URL: /api/schedules/trigger/{byos_schedule.external_trigger_token}")
            print(f"   📝 Note: Customer calls this URL from their scheduler")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # ==================== 5. List Schedules ====================
        print("\n" + "-" * 50)
        print("5️⃣ Listing All Schedules")
        print("-" * 50)

        schedules = await service.get_schedules_for_organization(org_id)
        print(f"   Found {len(schedules)} schedules:")
        for s in schedules:
            mode = "BYOS" if s.external_scheduler else "Platform"
            print(f"   • {s.name} ({s.schedule_type}) - {mode}")

        # ==================== 6. Test Limits ====================
        print("\n" + "-" * 50)
        print("6️⃣ Testing Tier Limits (Free Tier: Max 5 schedules)")
        print("-" * 50)

        # Get current limits
        limits = await service._get_or_create_limits(org_id)
        print(f"   Tier: {limits.tier}")
        print(f"   Max schedules: {limits.max_schedules}")
        print(f"   Current count: {limits.current_schedule_count}")
        print(f"   Min interval: {limits.min_interval_seconds}s")

        # Try to create more than allowed
        print("\n   Attempting to exceed limit...")
        try:
            for i in range(3):  # Should exceed the 5 schedule limit
                await service.create_schedule(
                    organization_id=org_id,
                    workflow_id=workflow_id,
                    name=f"Extra Schedule {i+1}",
                    schedule_type=ScheduleType.CRON,
                    cron_expression="0 0 * * *",
                )
        except ScheduleLimitExceeded as e:
            print(f"   ✅ Limit enforced: {e}")

        # ==================== 7. Test Invalid Cron ====================
        print("\n" + "-" * 50)
        print("7️⃣ Testing Invalid Cron Expression")
        print("-" * 50)

        try:
            await service.create_schedule(
                organization_id=org_id,
                workflow_id=workflow_id,
                name="Invalid Schedule",
                schedule_type=ScheduleType.CRON,
                cron_expression="invalid cron here",
            )
        except InvalidCronExpression as e:
            print(f"   ✅ Validation caught: {e}")

        # ==================== 8. Pause/Resume ====================
        print("\n" + "-" * 50)
        print("8️⃣ Testing Pause/Resume")
        print("-" * 50)

        if cron_schedule:
            print(f"   Current status: {cron_schedule.status}")

            # Pause
            paused = await service.pause_schedule(cron_schedule.schedule_id)
            print(f"   After pause: {paused.status}")

            # Resume
            resumed = await service.resume_schedule(cron_schedule.schedule_id)
            print(f"   After resume: {resumed.status}")
            print(f"   New next_run: {resumed.next_run_at}")

        # ==================== 9. BYOS External Trigger ====================
        print("\n" + "-" * 50)
        print("9️⃣ Simulating External Trigger (BYOS)")
        print("-" * 50)

        if byos_schedule:
            token = byos_schedule.external_trigger_token
            triggered = await service.trigger_by_token(
                trigger_token=token,
                input_data={"extra_param": "from_external_scheduler"},
            )
            if triggered:
                print(f"   ✅ Trigger successful!")
                print(f"   Schedule: {triggered.name}")
                print(f"   Input data: {triggered.input_data}")
            else:
                print("   ❌ Invalid token")

        # ==================== Summary ====================
        print("\n" + "=" * 70)
        print("📊 SCHEDULER DEMO COMPLETE")
        print("=" * 70)

        final_schedules = await service.get_schedules_for_organization(org_id)
        print(f"\n   Total schedules created: {len(final_schedules)}")
        print(f"   Platform-managed: {sum(1 for s in final_schedules if not s.external_scheduler)}")
        print(f"   BYOS (external): {sum(1 for s in final_schedules if s.external_scheduler)}")

        print("\n🧪 HOW TO TEST WITH THE API:")
        print("-" * 50)
        print("""
   1. Start the backend:
      cd backend && uvicorn api.main:app --reload --port 8000

   2. Create a schedule:
      curl -X POST http://localhost:8000/api/schedules \\
        -H "Content-Type: application/json" \\
        -H "X-Organization-Id: my-org" \\
        -d '{
          "workflow_id": "123e4567-e89b-12d3-a456-426614174000",
          "name": "My Daily Job",
          "schedule_type": "cron",
          "cron_expression": "0 9 * * *"
        }'

   3. List schedules:
      curl http://localhost:8000/api/schedules -H "X-Organization-Id: my-org"

   4. Get cron helpers:
      curl http://localhost:8000/api/schedules/helpers

   5. External trigger (BYOS):
      curl -X POST http://localhost:8000/api/schedules/trigger/{token}
        """)


if __name__ == "__main__":
    asyncio.run(demo_scheduler())
