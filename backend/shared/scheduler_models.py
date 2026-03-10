"""
Scheduler Models - Cron-based Workflow Scheduling

Supports:
- Cron expression scheduling
- Interval-based scheduling
- Per-organization job management
- Execution history tracking
- Tiered limits (free vs paid)
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Text, Integer,
    Float, Index
)

from backend.database.session import Base
from backend.shared.workflow_models import UniversalUUID, UniversalJSON


class ScheduleStatus(Enum):
    """Schedule status"""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    ERROR = "error"


class ScheduleType(Enum):
    """Type of schedule"""
    CRON = "cron"          # Cron expression (e.g., "0 9 * * *")
    INTERVAL = "interval"  # Fixed interval (e.g., every 5 minutes)
    ONCE = "once"          # One-time scheduled execution


class ScheduledWorkflowModel(Base):
    """
    Scheduled workflow job.

    Stores schedule configuration and tracks execution history.
    Supports both platform-managed and BYOS (customer's own scheduler) modes.
    """
    __tablename__ = "scheduled_workflows"

    # Primary key
    schedule_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # Workflow to execute
    workflow_id = Column(UniversalUUID(), nullable=False, index=True)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Schedule name and description
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Schedule type and configuration
    schedule_type = Column(String(50), nullable=False, default=ScheduleType.CRON.value)

    # For CRON type: "0 9 * * *" (9 AM daily)
    cron_expression = Column(String(100), nullable=True)

    # For INTERVAL type: seconds between runs
    interval_seconds = Column(Integer, nullable=True)

    # For ONCE type: specific datetime
    run_at = Column(DateTime, nullable=True)

    # Timezone (default UTC)
    timezone = Column(String(50), nullable=False, default="UTC")

    # Status
    status = Column(String(50), nullable=False, default=ScheduleStatus.ACTIVE.value)

    # Input data to pass to workflow
    input_data = Column(JSON, nullable=True, default=dict)

    # Execution tracking
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(50), nullable=True)  # completed, failed
    last_run_execution_id = Column(UniversalUUID(), nullable=True)
    last_run_error = Column(Text, nullable=True)

    next_run_at = Column(DateTime, nullable=True, index=True)

    # Statistics
    total_runs = Column(Integer, nullable=False, default=0)
    successful_runs = Column(Integer, nullable=False, default=0)
    failed_runs = Column(Integer, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0.0)

    # Limits and controls
    max_retries = Column(Integer, nullable=False, default=3)
    retry_delay_seconds = Column(Integer, nullable=False, default=60)
    timeout_seconds = Column(Integer, nullable=False, default=3600)

    # Concurrency control
    allow_concurrent = Column(Boolean, nullable=False, default=False)
    is_running = Column(Boolean, nullable=False, default=False)

    # BYOS (Bring Your Own Scheduler) mode
    # If true, we don't run the scheduler - customer calls our trigger endpoint
    external_scheduler = Column(Boolean, nullable=False, default=False)
    external_trigger_token = Column(String(255), nullable=True)  # Secure token for external triggers

    # Metadata
    tags = Column(UniversalJSON(), nullable=True)
    extra_metadata = Column(JSON, nullable=True)

    # Audit
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_schedule_org', 'organization_id'),
        Index('idx_schedule_workflow', 'workflow_id'),
        Index('idx_schedule_status', 'status'),
        Index('idx_schedule_next_run', 'next_run_at'),
        Index('idx_schedule_external', 'external_scheduler'),
    )

    def __repr__(self):
        return f"<ScheduledWorkflow(id={self.schedule_id}, name={self.name}, cron={self.cron_expression})>"


class ScheduleExecutionHistoryModel(Base):
    """
    History of scheduled executions.

    Tracks each time a scheduled workflow runs for audit and debugging.
    """
    __tablename__ = "schedule_execution_history"

    # Primary key
    history_id = Column(UniversalUUID(), primary_key=True, default=uuid4)

    # References
    schedule_id = Column(UniversalUUID(), nullable=False, index=True)
    workflow_id = Column(UniversalUUID(), nullable=False)
    execution_id = Column(UniversalUUID(), nullable=True)  # Null if failed to start
    organization_id = Column(String(255), nullable=False, index=True)

    # Timing
    scheduled_for = Column(DateTime, nullable=False)  # When it was supposed to run
    started_at = Column(DateTime, nullable=True)       # When it actually started
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Status
    status = Column(String(50), nullable=False)  # started, completed, failed, skipped

    # Trigger source
    trigger_source = Column(String(50), nullable=False, default="scheduler")
    # scheduler, external, manual

    # Results
    error_message = Column(Text, nullable=True)
    output_summary = Column(JSON, nullable=True)

    # Cost
    cost = Column(Float, nullable=False, default=0.0)
    tokens_used = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_history_schedule', 'schedule_id'),
        Index('idx_history_org', 'organization_id'),
        Index('idx_history_scheduled_for', 'scheduled_for'),
        Index('idx_history_status', 'status'),
    )

    def __repr__(self):
        return f"<ScheduleExecutionHistory(id={self.history_id}, status={self.status})>"


class OrganizationScheduleLimits(Base):
    """
    Per-organization schedule limits based on tier.

    Implements tiered pricing model:
    - Free: Max 5 schedules, minimum 1 hour interval
    - Pro: Max 50 schedules, minimum 5 minute interval
    - Enterprise: Unlimited, minimum 1 minute interval
    """
    __tablename__ = "organization_schedule_limits"

    # Primary key is organization_id
    organization_id = Column(String(255), primary_key=True)

    # Tier
    tier = Column(String(50), nullable=False, default="free")
    # free, pro, enterprise

    # Limits
    max_schedules = Column(Integer, nullable=False, default=5)
    min_interval_seconds = Column(Integer, nullable=False, default=3600)  # 1 hour for free
    max_concurrent_executions = Column(Integer, nullable=False, default=2)

    # Usage
    current_schedule_count = Column(Integer, nullable=False, default=0)
    executions_this_month = Column(Integer, nullable=False, default=0)
    cost_this_month = Column(Float, nullable=False, default=0.0)

    # Billing
    per_execution_cost = Column(Float, nullable=False, default=0.0)  # 0 for free, $0.001 for paid

    # Reset date for monthly counters
    billing_cycle_start = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<OrganizationScheduleLimits(org={self.organization_id}, tier={self.tier})>"


# Tier configurations
SCHEDULE_TIER_CONFIGS = {
    "free": {
        "max_schedules": 5,
        "min_interval_seconds": 3600,  # 1 hour
        "max_concurrent_executions": 2,
        "per_execution_cost": 0.0,
    },
    "pro": {
        "max_schedules": 50,
        "min_interval_seconds": 300,  # 5 minutes
        "max_concurrent_executions": 10,
        "per_execution_cost": 0.001,
    },
    "enterprise": {
        "max_schedules": -1,  # Unlimited
        "min_interval_seconds": 60,  # 1 minute
        "max_concurrent_executions": 50,
        "per_execution_cost": 0.0005,  # Volume discount
    },
}


# Common cron expressions for UI helpers
COMMON_CRON_EXPRESSIONS = {
    "every_minute": "* * * * *",
    "every_5_minutes": "*/5 * * * *",
    "every_15_minutes": "*/15 * * * *",
    "every_30_minutes": "*/30 * * * *",
    "every_hour": "0 * * * *",
    "every_day_9am": "0 9 * * *",
    "every_day_midnight": "0 0 * * *",
    "every_monday_9am": "0 9 * * 1",
    "every_weekday_9am": "0 9 * * 1-5",
    "first_of_month": "0 0 1 * *",
}
