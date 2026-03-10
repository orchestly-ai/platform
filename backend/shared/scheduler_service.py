"""
Scheduler Service - Cron-based Workflow Scheduling

Features:
- Cron expression parsing and scheduling
- Interval-based scheduling
- Per-organization limits and quotas
- BYOS (Bring Your Own Scheduler) support via trigger tokens
- Execution history tracking
- Automatic retry on failure

Platform Economics:
- Free tier: Limited schedules, 1-hour minimum interval
- Paid tiers: More schedules, finer granularity
- Enterprise: BYOS mode (customer brings their own scheduler)
"""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from croniter import croniter
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.scheduler_models import (
    ScheduledWorkflowModel,
    ScheduleExecutionHistoryModel,
    OrganizationScheduleLimits,
    ScheduleStatus,
    ScheduleType,
    SCHEDULE_TIER_CONFIGS,
)
from backend.shared.workflow_models import WorkflowModel, WorkflowExecutionModel

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Base exception for scheduler errors"""
    pass


class ScheduleLimitExceeded(SchedulerError):
    """Raised when organization exceeds schedule limits"""
    pass


class InvalidCronExpression(SchedulerError):
    """Raised when cron expression is invalid"""
    pass


class ScheduleNotFound(SchedulerError):
    """Raised when schedule is not found"""
    pass


class SchedulerService:
    """
    Manages scheduled workflow executions.

    Responsibilities:
    - Create, update, delete schedules
    - Calculate next run times
    - Enforce organization limits
    - Track execution history
    - Generate secure trigger tokens for BYOS
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Schedule CRUD ====================

    async def create_schedule(
        self,
        organization_id: str,
        workflow_id: UUID,
        name: str,
        schedule_type: ScheduleType,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        run_at: Optional[datetime] = None,
        timezone: str = "UTC",
        input_data: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        external_scheduler: bool = False,
        created_by: Optional[str] = None,
    ) -> ScheduledWorkflowModel:
        """
        Create a new scheduled workflow.

        Args:
            organization_id: Organization creating the schedule
            workflow_id: Workflow to execute
            name: Human-readable schedule name
            schedule_type: CRON, INTERVAL, or ONCE
            cron_expression: Cron expression (for CRON type)
            interval_seconds: Interval in seconds (for INTERVAL type)
            run_at: Specific datetime (for ONCE type)
            timezone: Timezone for cron interpretation
            input_data: Data to pass to workflow on each run
            description: Optional description
            external_scheduler: If True, use BYOS mode
            created_by: User who created the schedule

        Returns:
            Created ScheduledWorkflowModel

        Raises:
            ScheduleLimitExceeded: If organization exceeds limits
            InvalidCronExpression: If cron expression is invalid
        """
        # Check organization limits
        limits = await self._get_or_create_limits(organization_id)
        await self._check_limits(limits, schedule_type, cron_expression, interval_seconds)

        # Validate schedule configuration
        if schedule_type == ScheduleType.CRON:
            if not cron_expression:
                raise InvalidCronExpression("Cron expression required for CRON schedule type")
            if not self._validate_cron(cron_expression):
                raise InvalidCronExpression(f"Invalid cron expression: {cron_expression}")

        elif schedule_type == ScheduleType.INTERVAL:
            if not interval_seconds or interval_seconds < limits.min_interval_seconds:
                raise ScheduleLimitExceeded(
                    f"Interval must be at least {limits.min_interval_seconds} seconds for your tier"
                )

        elif schedule_type == ScheduleType.ONCE:
            if not run_at:
                raise SchedulerError("run_at required for ONCE schedule type")
            if run_at <= datetime.utcnow():
                raise SchedulerError("run_at must be in the future")

        # Calculate next run time
        next_run = self._calculate_next_run(
            schedule_type, cron_expression, interval_seconds, run_at, timezone
        )

        # Generate external trigger token if BYOS
        external_token = secrets.token_urlsafe(32) if external_scheduler else None

        # Create schedule
        schedule = ScheduledWorkflowModel(
            schedule_id=uuid4(),
            workflow_id=workflow_id,
            organization_id=organization_id,
            name=name,
            description=description,
            schedule_type=schedule_type.value,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            run_at=run_at,
            timezone=timezone,
            input_data=input_data or {},
            next_run_at=next_run,
            external_scheduler=external_scheduler,
            external_trigger_token=external_token,
            created_by=created_by,
        )

        self.db.add(schedule)

        # Update organization schedule count
        limits.current_schedule_count += 1
        await self.db.commit()
        await self.db.refresh(schedule)

        logger.info(f"Created schedule {schedule.schedule_id} for workflow {workflow_id}")
        return schedule

    async def get_schedule(self, schedule_id: UUID) -> Optional[ScheduledWorkflowModel]:
        """Get a schedule by ID"""
        result = await self.db.execute(
            select(ScheduledWorkflowModel).where(
                ScheduledWorkflowModel.schedule_id == schedule_id
            )
        )
        return result.scalar_one_or_none()

    async def get_schedules_for_organization(
        self,
        organization_id: str,
        status: Optional[ScheduleStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ScheduledWorkflowModel]:
        """Get all schedules for an organization"""
        query = select(ScheduledWorkflowModel).where(
            ScheduledWorkflowModel.organization_id == organization_id
        )

        if status:
            query = query.where(ScheduledWorkflowModel.status == status.value)

        query = query.order_by(ScheduledWorkflowModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_schedules_for_workflow(
        self,
        workflow_id: UUID,
    ) -> List[ScheduledWorkflowModel]:
        """Get all schedules for a workflow"""
        result = await self.db.execute(
            select(ScheduledWorkflowModel).where(
                ScheduledWorkflowModel.workflow_id == workflow_id
            )
        )
        return list(result.scalars().all())

    async def update_schedule(
        self,
        schedule_id: UUID,
        **updates,
    ) -> ScheduledWorkflowModel:
        """Update a schedule"""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            raise ScheduleNotFound(f"Schedule {schedule_id} not found")

        # Handle special updates
        if "cron_expression" in updates:
            if not self._validate_cron(updates["cron_expression"]):
                raise InvalidCronExpression(f"Invalid cron expression: {updates['cron_expression']}")

        # Apply updates
        for key, value in updates.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)

        # Recalculate next run if schedule changed
        if any(k in updates for k in ["cron_expression", "interval_seconds", "run_at", "timezone"]):
            schedule.next_run_at = self._calculate_next_run(
                ScheduleType(schedule.schedule_type),
                schedule.cron_expression,
                schedule.interval_seconds,
                schedule.run_at,
                schedule.timezone,
            )

        schedule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(schedule)

        return schedule

    async def delete_schedule(self, schedule_id: UUID) -> bool:
        """Delete a schedule"""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            return False

        # Update organization count
        limits = await self._get_or_create_limits(schedule.organization_id)
        limits.current_schedule_count = max(0, limits.current_schedule_count - 1)

        await self.db.delete(schedule)
        await self.db.commit()

        logger.info(f"Deleted schedule {schedule_id}")
        return True

    async def pause_schedule(self, schedule_id: UUID) -> ScheduledWorkflowModel:
        """Pause a schedule"""
        return await self.update_schedule(schedule_id, status=ScheduleStatus.PAUSED.value)

    async def resume_schedule(self, schedule_id: UUID) -> ScheduledWorkflowModel:
        """Resume a paused schedule"""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            raise ScheduleNotFound(f"Schedule {schedule_id} not found")

        # Recalculate next run from now
        schedule.next_run_at = self._calculate_next_run(
            ScheduleType(schedule.schedule_type),
            schedule.cron_expression,
            schedule.interval_seconds,
            schedule.run_at,
            schedule.timezone,
        )
        schedule.status = ScheduleStatus.ACTIVE.value
        schedule.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    # ==================== Execution ====================

    async def get_due_schedules(self, batch_size: int = 100) -> List[ScheduledWorkflowModel]:
        """
        Get schedules that are due to run.

        Only returns platform-managed schedules (not external_scheduler).
        """
        now = datetime.utcnow()

        result = await self.db.execute(
            select(ScheduledWorkflowModel).where(
                and_(
                    ScheduledWorkflowModel.status == ScheduleStatus.ACTIVE.value,
                    ScheduledWorkflowModel.external_scheduler == False,
                    ScheduledWorkflowModel.next_run_at <= now,
                    or_(
                        ScheduledWorkflowModel.is_running == False,
                        ScheduledWorkflowModel.allow_concurrent == True,
                    ),
                )
            ).limit(batch_size)
        )
        return list(result.scalars().all())

    async def mark_execution_started(
        self,
        schedule: ScheduledWorkflowModel,
        execution_id: UUID,
    ) -> ScheduleExecutionHistoryModel:
        """Mark a schedule execution as started"""
        # Update schedule
        schedule.is_running = True
        schedule.last_run_at = datetime.utcnow()
        schedule.last_run_execution_id = execution_id
        schedule.total_runs += 1

        # Create history entry
        history = ScheduleExecutionHistoryModel(
            history_id=uuid4(),
            schedule_id=schedule.schedule_id,
            workflow_id=schedule.workflow_id,
            execution_id=execution_id,
            organization_id=schedule.organization_id,
            scheduled_for=schedule.next_run_at,
            started_at=datetime.utcnow(),
            status="started",
            trigger_source="scheduler",
        )
        self.db.add(history)

        # Calculate next run
        schedule.next_run_at = self._calculate_next_run(
            ScheduleType(schedule.schedule_type),
            schedule.cron_expression,
            schedule.interval_seconds,
            None,  # run_at only for ONCE
            schedule.timezone,
        )

        # If ONCE type, disable after running
        if schedule.schedule_type == ScheduleType.ONCE.value:
            schedule.status = ScheduleStatus.DISABLED.value

        await self.db.commit()
        await self.db.refresh(history)
        return history

    async def mark_execution_completed(
        self,
        history_id: UUID,
        success: bool,
        error_message: Optional[str] = None,
        cost: float = 0.0,
        tokens_used: Optional[int] = None,
        output_summary: Optional[Dict[str, Any]] = None,
    ):
        """Mark a schedule execution as completed"""
        # Update history
        result = await self.db.execute(
            select(ScheduleExecutionHistoryModel).where(
                ScheduleExecutionHistoryModel.history_id == history_id
            )
        )
        history = result.scalar_one_or_none()
        if not history:
            return

        history.completed_at = datetime.utcnow()
        history.status = "completed" if success else "failed"
        history.error_message = error_message
        history.cost = cost
        history.tokens_used = tokens_used
        history.output_summary = output_summary

        if history.started_at:
            history.duration_seconds = (history.completed_at - history.started_at).total_seconds()

        # Update schedule
        schedule = await self.get_schedule(history.schedule_id)
        if schedule:
            schedule.is_running = False
            schedule.last_run_status = "completed" if success else "failed"
            schedule.last_run_error = error_message
            schedule.total_cost += cost

            if success:
                schedule.successful_runs += 1
            else:
                schedule.failed_runs += 1

        # Update organization usage
        limits = await self._get_or_create_limits(history.organization_id)
        limits.executions_this_month += 1
        limits.cost_this_month += cost

        await self.db.commit()

    # ==================== BYOS (External Scheduler) ====================

    async def trigger_by_token(
        self,
        trigger_token: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[ScheduledWorkflowModel]:
        """
        Trigger a schedule by its external trigger token.

        Used for BYOS mode where customer's scheduler (EventBridge, Cloud Scheduler, etc.)
        calls our API with the token.
        """
        result = await self.db.execute(
            select(ScheduledWorkflowModel).where(
                and_(
                    ScheduledWorkflowModel.external_trigger_token == trigger_token,
                    ScheduledWorkflowModel.external_scheduler == True,
                    ScheduledWorkflowModel.status == ScheduleStatus.ACTIVE.value,
                )
            )
        )
        schedule = result.scalar_one_or_none()

        if not schedule:
            return None

        # Merge input data
        merged_input = {**(schedule.input_data or {}), **(input_data or {})}
        schedule.input_data = merged_input

        return schedule

    async def regenerate_trigger_token(self, schedule_id: UUID) -> str:
        """Regenerate the external trigger token for a schedule"""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            raise ScheduleNotFound(f"Schedule {schedule_id} not found")

        new_token = secrets.token_urlsafe(32)
        schedule.external_trigger_token = new_token
        schedule.updated_at = datetime.utcnow()

        await self.db.commit()
        return new_token

    # ==================== History ====================

    async def get_execution_history(
        self,
        schedule_id: Optional[UUID] = None,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ScheduleExecutionHistoryModel]:
        """Get execution history for a schedule or organization"""
        query = select(ScheduleExecutionHistoryModel)

        if schedule_id:
            query = query.where(ScheduleExecutionHistoryModel.schedule_id == schedule_id)
        if organization_id:
            query = query.where(ScheduleExecutionHistoryModel.organization_id == organization_id)

        query = query.order_by(ScheduleExecutionHistoryModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ==================== Limits ====================

    async def _get_or_create_limits(self, organization_id: str) -> OrganizationScheduleLimits:
        """Get or create organization schedule limits"""
        result = await self.db.execute(
            select(OrganizationScheduleLimits).where(
                OrganizationScheduleLimits.organization_id == organization_id
            )
        )
        limits = result.scalar_one_or_none()

        if not limits:
            # Create default (free tier) limits
            limits = OrganizationScheduleLimits(
                organization_id=organization_id,
                tier="free",
                **SCHEDULE_TIER_CONFIGS["free"],
                billing_cycle_start=datetime.utcnow(),
            )
            self.db.add(limits)
            await self.db.commit()
            await self.db.refresh(limits)

        return limits

    async def _check_limits(
        self,
        limits: OrganizationScheduleLimits,
        schedule_type: ScheduleType,
        cron_expression: Optional[str],
        interval_seconds: Optional[int],
    ):
        """Check if organization can create a new schedule"""
        # Check schedule count limit
        if limits.max_schedules != -1 and limits.current_schedule_count >= limits.max_schedules:
            raise ScheduleLimitExceeded(
                f"Maximum schedules ({limits.max_schedules}) reached for {limits.tier} tier. "
                "Upgrade to create more schedules."
            )

        # Check minimum interval for cron
        if schedule_type == ScheduleType.CRON and cron_expression:
            # Calculate approximate interval from cron
            try:
                cron = croniter(cron_expression, datetime.utcnow())
                next1 = cron.get_next(datetime)
                next2 = cron.get_next(datetime)
                interval = (next2 - next1).total_seconds()

                if interval < limits.min_interval_seconds:
                    raise ScheduleLimitExceeded(
                        f"Minimum interval for {limits.tier} tier is {limits.min_interval_seconds} seconds. "
                        f"Your cron expression has ~{int(interval)} second intervals."
                    )
            except Exception:
                pass  # If we can't calculate, let it through

        # Check interval for interval type
        if schedule_type == ScheduleType.INTERVAL and interval_seconds:
            if interval_seconds < limits.min_interval_seconds:
                raise ScheduleLimitExceeded(
                    f"Minimum interval for {limits.tier} tier is {limits.min_interval_seconds} seconds."
                )

    async def upgrade_tier(self, organization_id: str, new_tier: str) -> OrganizationScheduleLimits:
        """Upgrade organization to a new tier"""
        if new_tier not in SCHEDULE_TIER_CONFIGS:
            raise SchedulerError(f"Unknown tier: {new_tier}")

        limits = await self._get_or_create_limits(organization_id)
        config = SCHEDULE_TIER_CONFIGS[new_tier]

        limits.tier = new_tier
        limits.max_schedules = config["max_schedules"]
        limits.min_interval_seconds = config["min_interval_seconds"]
        limits.max_concurrent_executions = config["max_concurrent_executions"]
        limits.per_execution_cost = config["per_execution_cost"]
        limits.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(limits)
        return limits

    # ==================== Helpers ====================

    def _validate_cron(self, expression: str) -> bool:
        """Validate a cron expression"""
        try:
            croniter(expression, datetime.utcnow())
            return True
        except (ValueError, KeyError):
            return False

    def _calculate_next_run(
        self,
        schedule_type: ScheduleType,
        cron_expression: Optional[str],
        interval_seconds: Optional[int],
        run_at: Optional[datetime],
        timezone: str,
    ) -> Optional[datetime]:
        """Calculate the next run time for a schedule"""
        now = datetime.utcnow()

        if schedule_type == ScheduleType.CRON and cron_expression:
            try:
                cron = croniter(cron_expression, now)
                return cron.get_next(datetime)
            except Exception:
                return None

        elif schedule_type == ScheduleType.INTERVAL and interval_seconds:
            return now + timedelta(seconds=interval_seconds)

        elif schedule_type == ScheduleType.ONCE and run_at:
            return run_at if run_at > now else None

        return None


class SchedulerRunner:
    """
    Background runner that executes due schedules.

    This runs as a background task and polls for due schedules.
    In production, this would be deployed as a separate worker process.
    """

    def __init__(self, db_session_factory, workflow_executor):
        self.db_session_factory = db_session_factory
        self.workflow_executor = workflow_executor
        self.running = False
        self.poll_interval = 10  # seconds

    async def start(self):
        """Start the scheduler runner"""
        self.running = True
        logger.info("Scheduler runner started")

        while self.running:
            try:
                await self._process_due_schedules()
            except Exception as e:
                logger.error(f"Error processing schedules: {e}")

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the scheduler runner"""
        self.running = False
        logger.info("Scheduler runner stopped")

    async def _process_due_schedules(self):
        """Process all due schedules"""
        async with self.db_session_factory() as db:
            service = SchedulerService(db)
            due_schedules = await service.get_due_schedules()

            for schedule in due_schedules:
                try:
                    await self._execute_schedule(db, service, schedule)
                except Exception as e:
                    logger.error(f"Error executing schedule {schedule.schedule_id}: {e}")

    async def _execute_schedule(
        self,
        db: AsyncSession,
        service: SchedulerService,
        schedule: ScheduledWorkflowModel,
    ):
        """Execute a single schedule"""
        execution_id = uuid4()

        # Mark as started
        history = await service.mark_execution_started(schedule, execution_id)

        try:
            # Execute workflow
            result = await self.workflow_executor.execute(
                workflow_id=schedule.workflow_id,
                input_data=schedule.input_data,
                execution_id=execution_id,
                trigger_source="schedule",
                triggered_by=f"schedule:{schedule.schedule_id}",
            )

            # Mark as completed
            await service.mark_execution_completed(
                history_id=history.history_id,
                success=True,
                cost=result.get("cost", 0),
                tokens_used=result.get("tokens_used"),
                output_summary={"status": "completed"},
            )

        except Exception as e:
            # Mark as failed
            await service.mark_execution_completed(
                history_id=history.history_id,
                success=False,
                error_message=str(e),
            )
            raise
