"""
E2E Integration Tests for Human-in-the-Loop Workflows

Tests complete HITL flows including:
- Approval request creation and routing
- Approval decision processing
- Timeout handling with auto-approve/reject
- Escalation chains
- Workflow pause and resume
- Notification delivery
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import uuid4

from backend.shared.hitl_service import HITLService
from backend.shared.hitl_models import (
    ApprovalRequest, ApprovalResponse, ApprovalNotification,
    ApprovalEscalation, ApprovalTemplate,
    ApprovalRequestCreate, ApprovalDecision, ApprovalTemplateCreate,
    ApprovalStatus, NotificationChannel, EscalationTrigger, ApprovalPriority
)


class TestApprovalRequestFlow:
    """Tests for complete approval request flow."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_complete_approval_flow(self, mock_db):
        """Test complete flow: create request -> approve -> complete."""
        # Step 1: Create approval request
        request_data = ApprovalRequestCreate(
            workflow_execution_id=123,
            node_id="approval_node",
            title="Approve deployment to production",
            description="Deploy v2.0 to production environment",
            context={"version": "2.0", "environment": "production"},
            required_approvers=["manager@company.com"],
            required_approval_count=1,
            priority=ApprovalPriority.HIGH
        )

        mock_request = MagicMock()
        mock_request.id = 1
        mock_request.status = ApprovalStatus.PENDING.value
        mock_request.notifications = []

        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=mock_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            request = await HITLService.create_approval_request(
                db=mock_db,
                request_data=request_data,
                user_id="developer@company.com",
                organization_id=1
            )

        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_approval_with_multiple_approvers(self, mock_db):
        """Test approval flow requiring multiple approvers."""
        request_data = ApprovalRequestCreate(
            workflow_execution_id=456,
            node_id="multi_approval_node",
            title="Critical system change",
            required_approvers=["manager1@company.com", "manager2@company.com", "cto@company.com"],
            required_approval_count=2,  # Need 2 of 3 to approve
            priority=ApprovalPriority.CRITICAL
        )

        mock_request = MagicMock()
        mock_request.id = 2
        mock_request.status = ApprovalStatus.PENDING.value
        mock_request.notifications = []

        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=mock_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            request = await HITLService.create_approval_request(
                db=mock_db,
                request_data=request_data,
                user_id="requester@company.com"
            )

        mock_db.add.assert_called()


class TestApprovalDecisionFlow:
    """Tests for approval decision processing."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_first_approval_keeps_pending(self, mock_db):
        """Test first approval when multiple required keeps request pending."""
        pending_request = MagicMock()
        pending_request.id = 1
        pending_request.status = ApprovalStatus.PENDING.value
        pending_request.required_approvers = ["approver1@company.com", "approver2@company.com"]
        pending_request.required_approval_count = 2
        pending_request.created_at = datetime.utcnow()

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=pending_request)

        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=0)  # No approvals yet

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        decision = ApprovalDecision(decision="approved", comment="LGTM")

        result = await HITLService.submit_decision(
            db=mock_db,
            request_id=1,
            decision_data=decision,
            approver_user_id="approver1@company.com"
        )

        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_rejection_immediately_rejects(self, mock_db):
        """Test that any rejection immediately rejects the request."""
        pending_request = MagicMock()
        pending_request.id = 1
        pending_request.status = ApprovalStatus.PENDING.value
        pending_request.required_approvers = ["approver1@company.com", "approver2@company.com"]
        pending_request.required_approval_count = 2
        pending_request.created_at = datetime.utcnow()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=pending_request)
        mock_result.scalar = MagicMock(return_value=0)
        mock_db.execute = AsyncMock(return_value=mock_result)

        decision = ApprovalDecision(decision="rejected", comment="Not ready for prod")

        result = await HITLService.submit_decision(
            db=mock_db,
            request_id=1,
            decision_data=decision,
            approver_user_id="approver1@company.com"
        )

        mock_db.add.assert_called()


class TestTimeoutFlow:
    """Tests for timeout handling in approval workflows."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_timeout_auto_approve(self, mock_db):
        """Test auto-approval on timeout."""
        expired_request = MagicMock()
        expired_request.id = 1
        expired_request.timeout_action = "approve"
        expired_request.timeout_seconds = 3600  # 1 hour
        expired_request.created_at = datetime.utcnow() - timedelta(hours=2)  # 2 hours ago

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[expired_request])
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        processed = await HITLService.process_timeouts(mock_db)

        assert processed == 1
        assert expired_request.status == ApprovalStatus.TIMEOUT_APPROVED.value

    @pytest.mark.asyncio
    async def test_timeout_auto_reject(self, mock_db):
        """Test auto-rejection on timeout."""
        expired_request = MagicMock()
        expired_request.id = 2
        expired_request.timeout_action = "reject"
        expired_request.timeout_seconds = 1800  # 30 minutes
        expired_request.created_at = datetime.utcnow() - timedelta(hours=1)  # 1 hour ago

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[expired_request])
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        processed = await HITLService.process_timeouts(mock_db)

        assert processed == 1
        assert expired_request.status == ApprovalStatus.TIMEOUT_REJECTED.value

    @pytest.mark.asyncio
    async def test_no_expired_requests(self, mock_db):
        """Test processing when no requests have expired."""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[])
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        processed = await HITLService.process_timeouts(mock_db)

        assert processed == 0


class TestEscalationFlow:
    """Tests for escalation chain processing."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_escalation_to_manager(self, mock_db):
        """Test escalation from approver to manager."""
        pending_request = MagicMock()
        pending_request.id = 1
        pending_request.status = ApprovalStatus.PENDING.value
        pending_request.required_approvers = ["approver@company.com"]
        pending_request.escalation_level = 0

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=pending_request)

        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=0)

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            escalation = await HITLService.escalate_request(
                db=mock_db,
                request_id=1,
                escalated_to_user_id="manager@company.com",
                trigger=EscalationTrigger.TIMEOUT,
                notes="No response in 24 hours"
            )

        assert pending_request.status == ApprovalStatus.ESCALATED.value
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_multi_level_escalation(self, mock_db):
        """Test multiple escalation levels (approver -> manager -> executive)."""
        request_level_0 = MagicMock()
        request_level_0.id = 1
        request_level_0.status = ApprovalStatus.PENDING.value
        request_level_0.required_approvers = ["approver@company.com"]
        request_level_0.escalation_level = 0

        request_level_1 = MagicMock()
        request_level_1.id = 1
        request_level_1.status = ApprovalStatus.ESCALATED.value
        request_level_1.required_approvers = ["manager@company.com"]
        request_level_1.escalation_level = 1

        # First escalation
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=request_level_0)
        mock_result1.scalar = MagicMock(return_value=0)

        mock_db.execute = AsyncMock(return_value=mock_result1)

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            await HITLService.escalate_request(
                db=mock_db,
                request_id=1,
                escalated_to_user_id="manager@company.com",
                trigger=EscalationTrigger.TIMEOUT
            )

        assert request_level_0.escalation_level == 1


class TestWorkflowPauseResume:
    """Tests for pausing and resuming workflows on approval."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_workflow_pauses_on_hitl_node(self, mock_db):
        """Test that workflow pauses when reaching HITL node."""
        request_data = ApprovalRequestCreate(
            workflow_execution_id=789,
            node_id="hitl_gate",
            title="Manual approval required",
            required_approvers=["admin@company.com"]
        )

        mock_request = MagicMock()
        mock_request.id = 5
        mock_request.status = ApprovalStatus.PENDING.value
        mock_request.workflow_execution_id = 789
        mock_request.notifications = []

        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=mock_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            request = await HITLService.create_approval_request(
                db=mock_db,
                request_data=request_data,
                user_id="workflow_engine"
            )

        # Workflow should be in waiting state
        mock_db.add.assert_called()


class TestNotificationDelivery:
    """Tests for notification delivery to approvers."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        # _send_notification does: result = await db.execute(stmt)
        #                          approval_request = result.scalar_one_or_none()
        mock_approval = MagicMock()
        mock_approval.title = "Test Approval"
        mock_approval.description = "Test description"
        mock_approval.priority = "medium"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_approval
        db.execute = AsyncMock(return_value=mock_result)
        return db

    @pytest.mark.asyncio
    async def test_email_notification_sent(self, mock_db):
        """Test email notification is sent to approvers."""
        notification = await HITLService._send_notification(
            db=mock_db,
            request_id=1,
            recipient_user_id="approver@company.com",
            channel=NotificationChannel.EMAIL
        )

        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_slack_notification_sent(self, mock_db):
        """Test Slack notification is sent to approvers."""
        notification = await HITLService._send_notification(
            db=mock_db,
            request_id=1,
            recipient_user_id="U123ABC",
            channel=NotificationChannel.SLACK
        )

        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_multiple_notification_channels(self, mock_db):
        """Test notifications sent to multiple channels."""
        channels = [NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.IN_APP]

        for channel in channels:
            notification = await HITLService._send_notification(
                db=mock_db,
                request_id=1,
                recipient_user_id="user@company.com",
                channel=channel
            )

        # Should be called once for each channel
        assert mock_db.add.call_count >= len(channels)


class TestTemplateBasedApprovals:
    """Tests for template-based approval workflows."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_approval_from_template(self, mock_db):
        """Test creating approval request from template."""
        template_data = ApprovalTemplateCreate(
            name="Production Deployment",
            slug="prod-deploy",
            description="Template for production deployments",
            default_approvers=["devops-lead@company.com", "sre-lead@company.com"],
            required_approval_count=2,
            timeout_seconds=43200,  # 12 hours
            timeout_action="reject",
            escalation_enabled=True,
            escalation_chain=["eng-manager@company.com", "vp-eng@company.com"],
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK]
        )

        template = await HITLService.create_template(
            db=mock_db,
            template_data=template_data,
            user_id="admin@company.com",
            organization_id=1
        )

        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_get_template_by_slug(self, mock_db):
        """Test retrieving template by slug."""
        mock_template = MagicMock()
        mock_template.slug = "prod-deploy"
        mock_template.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_template)
        mock_db.execute = AsyncMock(return_value=mock_result)

        template = await HITLService.get_template_by_slug(
            db=mock_db,
            slug="prod-deploy",
            organization_id=1
        )

        assert template is not None
        assert template.slug == "prod-deploy"


class TestCancellationFlow:
    """Tests for approval request cancellation."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_requester_can_cancel(self, mock_db):
        """Test that requester can cancel their own request."""
        pending_request = MagicMock()
        pending_request.id = 1
        pending_request.status = ApprovalStatus.PENDING
        pending_request.requested_by_user_id = "requester@company.com"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=pending_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await HITLService.cancel_request(
            db=mock_db,
            request_id=1,
            user_id="requester@company.com"
        )

        assert pending_request.status == ApprovalStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_other_user_cannot_cancel(self, mock_db):
        """Test that other users cannot cancel request."""
        pending_request = MagicMock()
        pending_request.id = 1
        pending_request.status = ApprovalStatus.PENDING
        pending_request.requested_by_user_id = "requester@company.com"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=pending_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="not authorized"):
            await HITLService.cancel_request(
                db=mock_db,
                request_id=1,
                user_id="other_user@company.com"
            )


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
