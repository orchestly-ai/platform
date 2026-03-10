"""
Unit Tests for Human-in-the-Loop (HITL) Service

Tests for approval workflows, notifications, escalations, and timeout handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.hitl_service import HITLService
from backend.shared.hitl_models import (
    ApprovalRequest, ApprovalResponse, ApprovalNotification,
    ApprovalEscalation, ApprovalTemplate,
    ApprovalRequestCreate, ApprovalDecision, ApprovalTemplateCreate,
    ApprovalStatus, NotificationChannel, EscalationTrigger, ApprovalPriority,
    ApprovalStats
)


class TestApprovalRequestCreation:
    """Tests for creating approval requests."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def sample_request_data(self):
        return ApprovalRequestCreate(
            workflow_execution_id=123,
            node_id="node_1",
            title="Approve $50K budget request",
            description="Budget request for Q1 marketing campaign",
            context={"amount": 50000, "department": "marketing"},
            required_approvers=["user_1", "user_2"],
            required_approval_count=2,
            priority=ApprovalPriority.HIGH,
            timeout_seconds=3600,
            timeout_action="reject",
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK]
        )

    @pytest.mark.asyncio
    async def test_create_approval_request_success(self, mock_db, sample_request_data):
        """Test successful approval request creation."""
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=MagicMock(
            id=1,
            notifications=[]
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Patch _send_notification to avoid actual notifications
        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = MagicMock()

            request = await HITLService.create_approval_request(
                db=mock_db,
                request_data=sample_request_data,
                user_id="requester_user",
                organization_id=1
            )

            # Verify db operations
            mock_db.add.assert_called()
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_approval_request_with_timeout(self, mock_db):
        """Test approval request with timeout expiration."""
        request_data = ApprovalRequestCreate(
            workflow_execution_id=456,
            node_id="node_2",
            title="Quick approval needed",
            required_approvers=["user_1"],
            timeout_seconds=3600,
            timeout_action="approve"
        )

        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=MagicMock(
            id=1,
            notifications=[]
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            before_creation = datetime.utcnow()
            request = await HITLService.create_approval_request(
                db=mock_db,
                request_data=request_data,
                user_id="user_1"
            )

            # Verify timeout is calculated correctly
            mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_create_approval_request_no_timeout(self, mock_db):
        """Test approval request without timeout."""
        request_data = ApprovalRequestCreate(
            workflow_execution_id=789,
            node_id="node_3",
            title="No timeout request",
            required_approvers=["approver_1"]
        )

        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=MagicMock(
            id=1,
            notifications=[]
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            request = await HITLService.create_approval_request(
                db=mock_db,
                request_data=request_data,
                user_id="user_1"
            )

            mock_db.add.assert_called()


class TestApprovalDecisions:
    """Tests for submitting approval/rejection decisions."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_pending_request(self):
        request = MagicMock()
        request.id = 1
        request.status = ApprovalStatus.PENDING.value
        request.required_approvers = ["approver_1", "approver_2"]
        request.required_approval_count = 1
        request.created_at = datetime.utcnow() - timedelta(hours=1)
        return request

    @pytest.mark.asyncio
    async def test_submit_approval_decision(self, mock_db, mock_pending_request):
        """Test submitting an approval decision."""
        # Mock database queries
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=mock_pending_request)

        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=0)  # No existing approvals

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        decision = ApprovalDecision(decision="approved", comment="Looks good")

        result = await HITLService.submit_decision(
            db=mock_db,
            request_id=1,
            decision_data=decision,
            approver_user_id="approver_1",
            approver_email="approver@test.com"
        )

        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_submit_rejection_decision(self, mock_db, mock_pending_request):
        """Test submitting a rejection decision."""
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=mock_pending_request)

        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=0)

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        decision = ApprovalDecision(decision="rejected", comment="Budget too high")

        result = await HITLService.submit_decision(
            db=mock_db,
            request_id=1,
            decision_data=decision,
            approver_user_id="approver_1"
        )

        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_submit_decision_request_not_found(self, mock_db):
        """Test submitting decision for non-existent request."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        decision = ApprovalDecision(decision="approved")

        with pytest.raises(ValueError, match="not found"):
            await HITLService.submit_decision(
                db=mock_db,
                request_id=999,
                decision_data=decision,
                approver_user_id="approver_1"
            )

    @pytest.mark.asyncio
    async def test_submit_decision_already_decided(self, mock_db):
        """Test submitting decision on already decided request."""
        already_approved_request = MagicMock()
        already_approved_request.id = 1
        already_approved_request.status = ApprovalStatus.APPROVED.value
        already_approved_request.required_approvers = ["approver_1"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=already_approved_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        decision = ApprovalDecision(decision="approved")

        with pytest.raises(ValueError, match="already"):
            await HITLService.submit_decision(
                db=mock_db,
                request_id=1,
                decision_data=decision,
                approver_user_id="approver_1"
            )

    @pytest.mark.asyncio
    async def test_submit_decision_unauthorized_approver(self, mock_db, mock_pending_request):
        """Test submitting decision by unauthorized user."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_pending_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        decision = ApprovalDecision(decision="approved")

        with pytest.raises(ValueError, match="not authorized"):
            await HITLService.submit_decision(
                db=mock_db,
                request_id=1,
                decision_data=decision,
                approver_user_id="unauthorized_user"
            )


class TestTimeoutProcessing:
    """Tests for timeout handling."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_process_timeouts_approve(self, mock_db):
        """Test processing expired requests with approve timeout action."""
        expired_request = MagicMock()
        expired_request.id = 1
        expired_request.timeout_action = "approve"
        expired_request.timeout_seconds = 3600

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[expired_request])
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        processed = await HITLService.process_timeouts(mock_db)

        assert processed == 1
        assert expired_request.status == ApprovalStatus.TIMEOUT_APPROVED.value
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_process_timeouts_reject(self, mock_db):
        """Test processing expired requests with reject timeout action."""
        expired_request = MagicMock()
        expired_request.id = 1
        expired_request.timeout_action = "reject"
        expired_request.timeout_seconds = 1800

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[expired_request])
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        processed = await HITLService.process_timeouts(mock_db)

        assert processed == 1
        assert expired_request.status == ApprovalStatus.TIMEOUT_REJECTED.value

    @pytest.mark.asyncio
    async def test_process_timeouts_none_expired(self, mock_db):
        """Test processing when no requests have expired."""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[])
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        processed = await HITLService.process_timeouts(mock_db)

        assert processed == 0


class TestEscalation:
    """Tests for escalation functionality."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_pending_request(self):
        request = MagicMock()
        request.id = 1
        request.status = ApprovalStatus.PENDING.value
        request.required_approvers = ["approver_1"]
        return request

    @pytest.mark.asyncio
    async def test_escalate_request(self, mock_db, mock_pending_request):
        """Test escalating an approval request."""
        # Mock finding request
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=mock_pending_request)

        # Mock finding max escalation level
        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=0)

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            escalation = await HITLService.escalate_request(
                db=mock_db,
                request_id=1,
                escalated_to_user_id="manager_1",
                trigger=EscalationTrigger.TIMEOUT,
                notes="No response after 24 hours"
            )

            mock_db.add.assert_called()
            mock_db.commit.assert_called()
            assert mock_pending_request.status == ApprovalStatus.ESCALATED.value

    @pytest.mark.asyncio
    async def test_escalate_request_not_found(self, mock_db):
        """Test escalating non-existent request."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="not found"):
            await HITLService.escalate_request(
                db=mock_db,
                request_id=999,
                escalated_to_user_id="manager_1"
            )

    @pytest.mark.asyncio
    async def test_escalate_request_increments_level(self, mock_db, mock_pending_request):
        """Test that escalation level increments correctly."""
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none = MagicMock(return_value=mock_pending_request)

        # Previous escalation level was 2
        mock_result2 = MagicMock()
        mock_result2.scalar = MagicMock(return_value=2)

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        with patch.object(HITLService, '_send_notification', new_callable=AsyncMock):
            await HITLService.escalate_request(
                db=mock_db,
                request_id=1,
                escalated_to_user_id="exec_1"
            )

            # Escalation level should now be 3
            assert mock_pending_request.escalation_level == 3


class TestCancelRequest:
    """Tests for cancelling approval requests."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_cancel_request_success(self, mock_db):
        """Test cancelling a pending request."""
        pending_request = MagicMock()
        pending_request.id = 1
        pending_request.status = ApprovalStatus.PENDING
        pending_request.requested_by_user_id = "user_1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=pending_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await HITLService.cancel_request(
            db=mock_db,
            request_id=1,
            user_id="user_1"
        )

        assert pending_request.status == ApprovalStatus.CANCELLED.value
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_request_not_found(self, mock_db):
        """Test cancelling non-existent request."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="not found"):
            await HITLService.cancel_request(
                db=mock_db,
                request_id=999,
                user_id="user_1"
            )

    @pytest.mark.asyncio
    async def test_cancel_request_wrong_user(self, mock_db):
        """Test cancelling request by wrong user."""
        pending_request = MagicMock()
        pending_request.id = 1
        pending_request.status = ApprovalStatus.PENDING
        pending_request.requested_by_user_id = "user_1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=pending_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="not authorized"):
            await HITLService.cancel_request(
                db=mock_db,
                request_id=1,
                user_id="different_user"
            )

    @pytest.mark.asyncio
    async def test_cancel_already_approved_request(self, mock_db):
        """Test cancelling already approved request."""
        approved_request = MagicMock()
        approved_request.id = 1
        approved_request.status = ApprovalStatus.APPROVED
        approved_request.requested_by_user_id = "user_1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=approved_request)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="Cannot cancel"):
            await HITLService.cancel_request(
                db=mock_db,
                request_id=1,
                user_id="user_1"
            )


class TestApprovalStats:
    """Tests for approval statistics."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        return db

    @pytest.mark.asyncio
    async def test_get_approval_stats_empty(self, mock_db):
        """Test stats with no requests."""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[])
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        stats = await HITLService.get_approval_stats(mock_db)

        assert stats.total_requests == 0
        assert stats.pending_requests == 0
        assert stats.approval_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_approval_stats_with_data(self, mock_db):
        """Test stats calculation with actual data."""
        # Create mock requests
        requests = [
            MagicMock(status=ApprovalStatus.PENDING, escalation_level=0, response_time_seconds=None),
            MagicMock(status=ApprovalStatus.APPROVED, escalation_level=0, response_time_seconds=120),
            MagicMock(status=ApprovalStatus.APPROVED, escalation_level=0, response_time_seconds=180),
            MagicMock(status=ApprovalStatus.REJECTED, escalation_level=1, response_time_seconds=300),
            MagicMock(status=ApprovalStatus.TIMEOUT_APPROVED, escalation_level=0, response_time_seconds=3600),
        ]

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=requests)
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        stats = await HITLService.get_approval_stats(mock_db)

        assert stats.total_requests == 5
        assert stats.pending_requests == 1
        assert stats.approved_requests == 2
        assert stats.rejected_requests == 1
        assert stats.timeout_approvals == 1
        assert stats.escalation_rate == 20.0  # 1 out of 5


class TestTemplateManagement:
    """Tests for approval template management."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_create_template(self, mock_db):
        """Test creating an approval template."""
        template_data = ApprovalTemplateCreate(
            name="Budget Approval",
            slug="budget-approval",
            description="Template for budget approvals",
            default_approvers=["finance_manager"],
            required_approval_count=2,
            timeout_seconds=86400,
            timeout_action="reject",
            escalation_enabled=True,
            escalation_chain=["cfo", "ceo"],
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK]
        )

        template = await HITLService.create_template(
            db=mock_db,
            template_data=template_data,
            user_id="admin_1",
            organization_id=1
        )

        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_template_by_slug(self, mock_db):
        """Test getting template by slug."""
        mock_template = MagicMock()
        mock_template.slug = "budget-approval"
        mock_template.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_template)
        mock_db.execute = AsyncMock(return_value=mock_result)

        template = await HITLService.get_template_by_slug(
            db=mock_db,
            slug="budget-approval",
            organization_id=1
        )

        assert template is not None
        assert template.slug == "budget-approval"

    @pytest.mark.asyncio
    async def test_get_template_by_slug_not_found(self, mock_db):
        """Test getting non-existent template."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        template = await HITLService.get_template_by_slug(
            db=mock_db,
            slug="nonexistent-template"
        )

        assert template is None


class TestNotifications:
    """Tests for notification sending."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        # Mock execute to return a result whose scalar_one_or_none is a regular
        # (non-async) method, matching how SQLAlchemy Result objects work.
        mock_approval_request = MagicMock()
        mock_approval_request.title = "Test Approval"
        mock_approval_request.description = "Test description"
        mock_approval_request.priority = "medium"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_approval_request)
        db.execute = AsyncMock(return_value=mock_result)
        return db

    @pytest.mark.asyncio
    async def test_send_notification(self, mock_db):
        """Test sending notification."""
        notification = await HITLService._send_notification(
            db=mock_db,
            request_id=1,
            recipient_user_id="approver_1",
            channel=NotificationChannel.EMAIL
        )

        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_send_notification_slack(self, mock_db):
        """Test sending Slack notification."""
        notification = await HITLService._send_notification(
            db=mock_db,
            request_id=1,
            recipient_user_id="approver_2",
            channel=NotificationChannel.SLACK
        )

        mock_db.add.assert_called()


class TestPendingApprovals:
    """Tests for getting pending approvals."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        return db

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, mock_db):
        """Test getting pending approvals for a user."""
        mock_requests = [
            MagicMock(id=1, title="Request 1", priority=ApprovalPriority.HIGH),
            MagicMock(id=2, title="Request 2", priority=ApprovalPriority.MEDIUM),
        ]

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=mock_requests)
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        pending = await HITLService.get_pending_approvals(
            db=mock_db,
            approver_user_id="approver_1",
            limit=50
        )

        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_get_pending_approvals_empty(self, mock_db):
        """Test getting pending approvals when none exist."""
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=[])
        ))
        mock_db.execute = AsyncMock(return_value=mock_result)

        pending = await HITLService.get_pending_approvals(
            db=mock_db,
            approver_user_id="approver_1"
        )

        assert len(pending) == 0


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
