"""
Human-in-the-Loop (HITL) Service - P1 Feature #4

Business logic for approval workflows, notifications, and escalations.

Key Features:
- Create and manage approval requests
- Send multi-channel notifications
- Handle approvals/rejections
- Automatic timeout handling
- Escalation management
- Approval analytics
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging
import os

# Check if using SQLite
USE_SQLITE = os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes")

logger = logging.getLogger(__name__)

from backend.shared.hitl_models import (
    ApprovalRequest,
    ApprovalResponse,
    ApprovalNotification,
    ApprovalEscalation,
    ApprovalTemplate,
    ApprovalRequestCreate,
    ApprovalDecision,
    ApprovalResponseCreate,
    ApprovalNotificationCreate,
    ApprovalEscalationCreate,
    ApprovalTemplateCreate,
    ApprovalStats,
    ApprovalStatus,
    NotificationChannel,
    EscalationTrigger,
    ApprovalPriority,
)


class HITLService:
    """Service for Human-in-the-Loop workflows."""

    @staticmethod
    async def create_approval_request(
        db: AsyncSession,
        request_data: ApprovalRequestCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> ApprovalRequest:
        """
        Create new approval request.

        Args:
            db: Database session
            request_data: Approval request data
            user_id: User creating the request
            organization_id: Organization ID

        Returns:
            Created approval request

        Raises:
            ValueError: If validation fails
        """
        # Calculate expiration time
        expires_at = None
        if request_data.timeout_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=request_data.timeout_seconds)

        # Create request (set timestamps explicitly for SQLite compatibility)
        now = datetime.utcnow()
        approval_request = ApprovalRequest(
            workflow_execution_id=request_data.workflow_execution_id,
            task_id=request_data.task_id,
            node_id=request_data.node_id,
            title=request_data.title,
            description=request_data.description,
            context=request_data.context,
            requested_by_user_id=user_id,
            organization_id=organization_id,
            required_approvers=request_data.required_approvers,
            required_approval_count=request_data.required_approval_count,
            priority=request_data.priority,
            timeout_seconds=request_data.timeout_seconds,
            timeout_action=request_data.timeout_action,
            expires_at=expires_at,
            status=ApprovalStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )

        db.add(approval_request)
        await db.commit()
        await db.refresh(approval_request)

        # Send notifications
        for approver_id in request_data.required_approvers:
            for channel in request_data.notification_channels:
                await HITLService._send_notification(
                    db,
                    approval_request.id,
                    approver_id,
                    channel,
                )

        # Eager load notifications before returning
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_request.id
        ).options(selectinload(ApprovalRequest.notifications))
        result = await db.execute(stmt)
        approval_request = result.scalar_one()

        return approval_request

    @staticmethod
    async def submit_decision(
        db: AsyncSession,
        request_id: int,
        decision_data: ApprovalDecision,
        approver_user_id: str,
        approver_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Submit approval or rejection decision.

        Args:
            db: Database session
            request_id: Approval request ID
            decision_data: Decision (approved/rejected)
            approver_user_id: User making decision
            approver_email: Approver email
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Updated approval request

        Raises:
            ValueError: If request not found, already decided, or user not authorized
        """
        # Get request
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        result = await db.execute(stmt)
        request = result.scalar_one_or_none()

        if not request:
            raise ValueError(f"Approval request {request_id} not found")

        # Allow decisions on pending or escalated requests
        if request.status not in (ApprovalStatus.PENDING, ApprovalStatus.ESCALATED, ApprovalStatus.PENDING.value, ApprovalStatus.ESCALATED.value):
            status_val = request.status if isinstance(request.status, str) else request.status.value
            raise ValueError(f"Approval request already {status_val}")

        # Check authorization
        if approver_user_id not in request.required_approvers:
            raise ValueError(f"User {approver_user_id} not authorized to approve this request")

        # Calculate response time
        response_time = (datetime.utcnow() - request.created_at).total_seconds()

        # Count existing approvals BEFORE adding new response
        stmt = select(func.count(ApprovalResponse.id)).where(
            and_(
                ApprovalResponse.request_id == request_id,
                ApprovalResponse.decision == "approved"
            )
        )
        result = await db.execute(stmt)
        approval_count = result.scalar()

        # Create response record
        response = ApprovalResponse(
            request_id=request_id,
            approver_user_id=approver_user_id,
            approver_email=approver_email,
            decision=decision_data.decision,
            comment=decision_data.comment,
            response_time_seconds=response_time,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(response)

        # Update request status if threshold met
        if decision_data.decision == "approved":
            if approval_count + 1 >= request.required_approval_count:
                request.status = ApprovalStatus.APPROVED.value
                request.approved_by_user_id = approver_user_id
                request.approved_at = datetime.utcnow()
                request.response_time_seconds = response_time
        else:
            # Rejection immediately fails the request
            request.status = ApprovalStatus.REJECTED.value
            request.approved_by_user_id = approver_user_id
            request.approved_at = datetime.utcnow()
            request.rejection_reason = decision_data.comment
            request.response_time_seconds = response_time

        await db.commit()
        await db.refresh(request)

        return request

    @staticmethod
    async def process_timeouts(db: AsyncSession) -> int:
        """
        Process approval requests that have timed out.

        This should be called periodically (e.g., every minute) by a background worker.

        Args:
            db: Database session

        Returns:
            Number of requests processed
        """
        # Find expired pending requests
        stmt = select(ApprovalRequest).where(
            and_(
                ApprovalRequest.status == ApprovalStatus.PENDING,
                ApprovalRequest.expires_at.isnot(None),
                ApprovalRequest.expires_at <= datetime.utcnow()
            )
        )
        result = await db.execute(stmt)
        expired_requests = result.scalars().all()

        processed = 0
        for request in expired_requests:
            if request.timeout_action == "approve":
                request.status = ApprovalStatus.TIMEOUT_APPROVED.value
                request.approved_at = datetime.utcnow()
                request.response_time_seconds = request.timeout_seconds
            else:  # Default to reject
                request.status = ApprovalStatus.TIMEOUT_REJECTED.value
                request.approved_at = datetime.utcnow()
                request.rejection_reason = "Timed out waiting for approval"
                request.response_time_seconds = request.timeout_seconds

            processed += 1

        if processed > 0:
            await db.commit()

        return processed

    @staticmethod
    async def escalate_request(
        db: AsyncSession,
        request_id: int,
        escalated_to_user_id: str,
        trigger: EscalationTrigger = EscalationTrigger.MANUAL,
        escalated_by_user_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ApprovalEscalation:
        """
        Escalate approval request to another approver.

        Args:
            db: Database session
            request_id: Approval request ID
            escalated_to_user_id: User to escalate to
            trigger: Escalation trigger
            escalated_by_user_id: User initiating escalation (for manual)
            notes: Escalation notes

        Returns:
            Created escalation record
        """
        # Get request
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        result = await db.execute(stmt)
        request = result.scalar_one_or_none()

        if not request:
            raise ValueError(f"Approval request {request_id} not found")

        # Get current escalation level
        stmt = select(func.max(ApprovalEscalation.level)).where(
            ApprovalEscalation.request_id == request_id
        )
        result = await db.execute(stmt)
        max_level = result.scalar() or 0
        new_level = max_level + 1

        # Create escalation
        escalation = ApprovalEscalation(
            request_id=request_id,
            level=new_level,
            trigger=trigger,
            trigger_time=datetime.utcnow(),
            escalated_to_user_id=escalated_to_user_id,
            escalated_by_user_id=escalated_by_user_id,
            notes=notes,
        )

        db.add(escalation)

        # Update request
        request.status = ApprovalStatus.ESCALATED.value
        request.escalation_level = new_level
        request.escalated_to_user_id = escalated_to_user_id
        request.escalated_at = datetime.utcnow()

        # Add escalated user to required approvers
        if escalated_to_user_id not in request.required_approvers:
            request.required_approvers.append(escalated_to_user_id)

        await db.commit()
        await db.refresh(escalation)

        # Send notification to escalated user
        await HITLService._send_notification(
            db,
            request_id,
            escalated_to_user_id,
            NotificationChannel.EMAIL,
        )

        return escalation

    @staticmethod
    async def cancel_request(
        db: AsyncSession,
        request_id: int,
        user_id: str,
    ) -> ApprovalRequest:
        """
        Cancel pending approval request.

        Args:
            db: Database session
            request_id: Approval request ID
            user_id: User cancelling the request

        Returns:
            Cancelled approval request
        """
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        result = await db.execute(stmt)
        request = result.scalar_one_or_none()

        if not request:
            raise ValueError(f"Approval request {request_id} not found")

        if request.status != ApprovalStatus.PENDING:
            status_val = request.status if isinstance(request.status, str) else request.status.value
            raise ValueError(f"Cannot cancel request with status {status_val}")

        if request.requested_by_user_id != user_id:
            raise ValueError(f"User {user_id} not authorized to cancel this request")

        request.status = ApprovalStatus.CANCELLED.value
        request.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(request)

        return request

    @staticmethod
    async def get_pending_approvals(
        db: AsyncSession,
        approver_user_id: str,
        organization_id: Optional[int] = None,
        priority: Optional[ApprovalPriority] = None,
        limit: int = 50,
    ) -> List[ApprovalRequest]:
        """
        Get pending approvals for a user.

        Args:
            db: Database session
            approver_user_id: User ID to get approvals for
            organization_id: Filter by organization
            priority: Filter by priority
            limit: Maximum results

        Returns:
            List of pending approval requests
        """
        # Build query - use different approach for SQLite vs PostgreSQL
        if USE_SQLITE:
            # For SQLite, use LIKE to search in JSON text
            stmt = select(ApprovalRequest).where(
                and_(
                    ApprovalRequest.status == ApprovalStatus.PENDING.value,
                    or_(
                        ApprovalRequest.required_approvers.like(f'%"{approver_user_id}"%'),
                        ApprovalRequest.required_approvers.is_(None)  # Also include if no specific approvers required
                    )
                )
            )
        else:
            # For PostgreSQL, use JSON contains (cast both to JSONB for @> operator)
            from sqlalchemy.dialects.postgresql import JSONB
            from sqlalchemy import cast as sql_cast
            stmt = select(ApprovalRequest).where(
                and_(
                    ApprovalRequest.status == ApprovalStatus.PENDING.value,
                    sql_cast(ApprovalRequest.required_approvers, JSONB).contains([approver_user_id])
                )
            )

        if organization_id:
            stmt = stmt.where(ApprovalRequest.organization_id == organization_id)

        if priority:
            stmt = stmt.where(ApprovalRequest.priority == priority)

        stmt = stmt.order_by(
            ApprovalRequest.priority.desc(),
            ApprovalRequest.created_at.asc()
        ).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_approval_stats(
        db: AsyncSession,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ApprovalStats:
        """
        Get approval statistics.

        Args:
            db: Database session
            organization_id: Filter by organization
            start_date: Start date for stats
            end_date: End date for stats

        Returns:
            Approval statistics
        """
        stmt = select(ApprovalRequest)

        if organization_id:
            stmt = stmt.where(ApprovalRequest.organization_id == organization_id)

        if start_date:
            stmt = stmt.where(ApprovalRequest.created_at >= start_date)

        if end_date:
            stmt = stmt.where(ApprovalRequest.created_at <= end_date)

        result = await db.execute(stmt)
        requests = result.scalars().all()

        total_requests = len(requests)
        if total_requests == 0:
            return ApprovalStats(
                total_requests=0,
                pending_requests=0,
                approved_requests=0,
                rejected_requests=0,
                timeout_approvals=0,
                timeout_rejections=0,
                avg_response_time_seconds=0.0,
                escalation_rate=0.0,
                approval_rate=0.0,
            )

        pending = sum(1 for r in requests if r.status == ApprovalStatus.PENDING)
        approved = sum(1 for r in requests if r.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for r in requests if r.status == ApprovalStatus.REJECTED)
        timeout_approved = sum(1 for r in requests if r.status == ApprovalStatus.TIMEOUT_APPROVED)
        timeout_rejected = sum(1 for r in requests if r.status == ApprovalStatus.TIMEOUT_REJECTED)
        escalated = sum(1 for r in requests if r.escalation_level > 0)

        # Calculate average response time (exclude pending)
        response_times = [r.response_time_seconds for r in requests if r.response_time_seconds]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0

        # Rates
        escalation_rate = (escalated / total_requests) * 100 if total_requests > 0 else 0.0
        completed = approved + rejected + timeout_approved + timeout_rejected
        approval_rate = ((approved + timeout_approved) / completed) * 100 if completed > 0 else 0.0

        return ApprovalStats(
            total_requests=total_requests,
            pending_requests=pending,
            approved_requests=approved,
            rejected_requests=rejected,
            timeout_approvals=timeout_approved,
            timeout_rejections=timeout_rejected,
            avg_response_time_seconds=avg_response_time,
            escalation_rate=escalation_rate,
            approval_rate=approval_rate,
        )

    # =========================================================================
    # Template Management
    # =========================================================================

    @staticmethod
    async def create_template(
        db: AsyncSession,
        template_data: ApprovalTemplateCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> ApprovalTemplate:
        """Create approval template."""
        template = ApprovalTemplate(
            name=template_data.name,
            slug=template_data.slug,
            description=template_data.description,
            organization_id=organization_id,
            created_by_user_id=user_id,
            default_approvers=template_data.default_approvers,
            required_approval_count=template_data.required_approval_count,
            timeout_seconds=template_data.timeout_seconds,
            timeout_action=template_data.timeout_action,
            escalation_enabled=template_data.escalation_enabled,
            escalation_chain=template_data.escalation_chain,
            escalation_timeout_seconds=template_data.escalation_timeout_seconds,
            notification_channels=template_data.notification_channels,
            notification_template=template_data.notification_template,
            category=template_data.category,
            tags=template_data.tags,
        )

        db.add(template)
        await db.commit()
        await db.refresh(template)

        return template

    @staticmethod
    async def get_template_by_slug(
        db: AsyncSession,
        slug: str,
        organization_id: Optional[int] = None,
    ) -> Optional[ApprovalTemplate]:
        """Get template by slug."""
        stmt = select(ApprovalTemplate).where(
            and_(
                ApprovalTemplate.slug == slug,
                ApprovalTemplate.is_active == True
            )
        )

        if organization_id:
            stmt = stmt.where(
                or_(
                    ApprovalTemplate.organization_id == organization_id,
                    ApprovalTemplate.organization_id.is_(None)
                )
            )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================================
    # Private Methods
    # =========================================================================

    @staticmethod
    async def _send_notification(
        db: AsyncSession,
        request_id: int,
        recipient_user_id: str,
        channel: NotificationChannel,
    ) -> ApprovalNotification:
        """
        Send approval notification via the appropriate channel.

        Dispatches to real integration services (Slack, SendGrid) when
        credentials are configured. Falls back to recording the notification
        without delivery when credentials are unavailable.

        Args:
            db: Database session
            request_id: Approval request ID
            recipient_user_id: Recipient user ID
            channel: Notification channel

        Returns:
            Created notification record
        """
        # Fetch the approval request for context in the notification message
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        result = await db.execute(stmt)
        approval_request = result.scalar_one_or_none()

        title = approval_request.title if approval_request else f"Approval #{request_id}"
        description = approval_request.description if approval_request else ""
        priority = approval_request.priority if approval_request else "medium"

        sent = False
        delivery_status = "pending"
        error_message = None

        # Dispatch based on channel
        channel_value = channel.value if hasattr(channel, 'value') else str(channel)

        if channel_value == NotificationChannel.SLACK.value:
            sent, delivery_status, error_message = await HITLService._dispatch_slack(
                recipient_user_id=recipient_user_id,
                title=title,
                description=description,
                priority=priority,
                request_id=request_id,
            )
        elif channel_value == NotificationChannel.DISCORD.value:
            sent, delivery_status, error_message = await HITLService._dispatch_discord(
                recipient_user_id=recipient_user_id,
                title=title,
                description=description,
                priority=priority,
                request_id=request_id,
            )
        elif channel_value == NotificationChannel.EMAIL.value:
            sent, delivery_status, error_message = await HITLService._dispatch_email(
                recipient_user_id=recipient_user_id,
                title=title,
                description=description,
                priority=priority,
                request_id=request_id,
            )
        elif channel_value == NotificationChannel.IN_APP.value:
            # In-app notifications are always "delivered" — they're stored in DB
            # and the dashboard polls for them
            sent = True
            delivery_status = "delivered"
            logger.info(f"In-app notification recorded for user {recipient_user_id}, request {request_id}")
        else:
            # SMS, webhook — not yet wired, record as pending
            logger.warning(
                f"Notification channel '{channel_value}' not yet implemented. "
                f"Recording notification for user {recipient_user_id}, request {request_id}"
            )
            delivery_status = "unsupported_channel"

        notification = ApprovalNotification(
            request_id=request_id,
            recipient_user_id=recipient_user_id,
            channel=channel,
            sent=sent,
            sent_at=datetime.utcnow() if sent else None,
            delivery_status=delivery_status,
        )

        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        return notification

    @staticmethod
    async def _dispatch_slack(
        recipient_user_id: str,
        title: str,
        description: str,
        priority: str,
        request_id: int,
    ) -> tuple:
        """
        Send notification via Slack integration.

        Returns:
            (sent: bool, delivery_status: str, error_message: Optional[str])
        """
        slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
        slack_channel = os.environ.get("SLACK_NOTIFICATION_CHANNEL", "#approvals")

        if not slack_bot_token:
            logger.warning(
                "SLACK_BOT_TOKEN not configured — Slack notification recorded but not sent. "
                f"Request {request_id} for user {recipient_user_id}"
            )
            return False, "no_credentials", "SLACK_BOT_TOKEN not configured"

        try:
            from backend.integrations.slack import SlackIntegration

            slack = SlackIntegration(
                auth_credentials={"bot_token": slack_bot_token}
            )

            priority_emoji = {"low": "", "medium": "", "high": "", "critical": ""}.get(
                priority, ""
            )

            message = (
                f"{priority_emoji} *Approval Required*: {title}\n"
                f"> {description[:200]}{'...' if len(description) > 200 else ''}\n"
                f"Assigned to: `{recipient_user_id}` | Priority: *{priority}*\n"
                f"Review in the <http://localhost:3000/hitl|Orchestration Dashboard>"
            )

            result = await slack.execute_action("send_message", {
                "channel": slack_channel,
                "text": message,
            })

            if result.success:
                logger.info(f"Slack notification sent for request {request_id} to {slack_channel}")
                return True, "delivered", None
            else:
                logger.error(f"Slack notification failed: {result.error_message}")
                return False, "failed", result.error_message

        except Exception as e:
            logger.error(f"Slack notification error: {e}", exc_info=True)
            return False, "error", str(e)

    @staticmethod
    async def _dispatch_discord(
        recipient_user_id: str,
        title: str,
        description: str,
        priority: str,
        request_id: int,
    ) -> tuple:
        """
        Send notification via Discord integration.

        Requires env vars:
            DISCORD_BOT_TOKEN: Discord bot token
            DISCORD_NOTIFICATION_CHANNEL_ID: Channel ID to post to

        Returns:
            (sent: bool, delivery_status: str, error_message: Optional[str])
        """
        discord_bot_token = os.environ.get("DISCORD_BOT_TOKEN")
        discord_channel_id = os.environ.get("DISCORD_NOTIFICATION_CHANNEL_ID")

        if not discord_bot_token:
            logger.warning(
                "DISCORD_BOT_TOKEN not configured — Discord notification recorded but not sent. "
                f"Request {request_id} for user {recipient_user_id}"
            )
            return False, "no_credentials", "DISCORD_BOT_TOKEN not configured"

        if not discord_channel_id:
            logger.warning(
                "DISCORD_NOTIFICATION_CHANNEL_ID not configured — Discord notification recorded but not sent. "
                f"Request {request_id} for user {recipient_user_id}"
            )
            return False, "no_channel", "DISCORD_NOTIFICATION_CHANNEL_ID not configured"

        try:
            from backend.integrations.discord import DiscordIntegration

            discord = DiscordIntegration(
                auth_credentials={"bot_token": discord_bot_token}
            )

            priority_emoji = {"low": "\u2139\ufe0f", "medium": "\u26a0\ufe0f", "high": "\ud83d\udea8", "critical": "\ud83d\udd34"}.get(
                str(priority), "\u26a0\ufe0f"
            )

            desc_truncated = (description[:200] + '...') if len(description) > 200 else description

            message = (
                f"{priority_emoji} **Approval Required**: {title}\n"
                f"> {desc_truncated}\n"
                f"Assigned to: `{recipient_user_id}` | Priority: **{priority}**\n"
                f"Review in the dashboard: <http://localhost:3000/hitl>"
            )

            result = await discord.execute_action("send_message", {
                "channel_id": discord_channel_id,
                "content": message,
            })

            if result.success:
                logger.info(f"Discord notification sent for request {request_id} to channel {discord_channel_id}")
                return True, "delivered", None
            else:
                logger.error(f"Discord notification failed: {result.error_message}")
                return False, "failed", result.error_message

        except Exception as e:
            logger.error(f"Discord notification error: {e}", exc_info=True)
            return False, "error", str(e)

    @staticmethod
    async def _dispatch_email(
        recipient_user_id: str,
        title: str,
        description: str,
        priority: str,
        request_id: int,
    ) -> tuple:
        """
        Send notification via SendGrid integration.

        Returns:
            (sent: bool, delivery_status: str, error_message: Optional[str])
        """
        sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
        from_email = os.environ.get("NOTIFICATION_FROM_EMAIL", "noreply@agentorch.dev")

        if not sendgrid_api_key:
            logger.warning(
                "SENDGRID_API_KEY not configured — email notification recorded but not sent. "
                f"Request {request_id} for user {recipient_user_id}"
            )
            return False, "no_credentials", "SENDGRID_API_KEY not configured"

        # In a real system, recipient_user_id would be resolved to an email
        # via a user profile lookup. For now, check if it looks like an email.
        recipient_email = recipient_user_id if "@" in recipient_user_id else None
        if not recipient_email:
            logger.warning(
                f"Cannot send email: recipient '{recipient_user_id}' is not an email address. "
                "User profile lookup not yet implemented."
            )
            return False, "no_recipient_email", f"Cannot resolve user '{recipient_user_id}' to email"

        try:
            from backend.integrations.sendgrid import SendGridIntegration

            sendgrid = SendGridIntegration(
                auth_credentials={"api_key": sendgrid_api_key}
            )

            priority_label = priority.upper() if priority else "MEDIUM"
            content = (
                f"<h2>[{priority_label}] Approval Required</h2>"
                f"<p><strong>{title}</strong></p>"
                f"<p>{description}</p>"
                f"<p>Assigned to: {recipient_user_id}</p>"
                f"<p><a href='http://localhost:3000/hitl'>Review in Dashboard</a></p>"
            )

            result = await sendgrid.execute_action("send_email", {
                "to_email": recipient_email,
                "from_email": from_email,
                "subject": f"[{priority_label}] Approval Required: {title}",
                "content": content,
                "html": True,
            })

            if result.success:
                logger.info(f"Email notification sent for request {request_id} to {recipient_email}")
                return True, "delivered", None
            else:
                logger.error(f"Email notification failed: {result.error_message}")
                return False, "failed", result.error_message

        except Exception as e:
            logger.error(f"Email notification error: {e}", exc_info=True)
            return False, "error", str(e)
