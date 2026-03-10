"""
Human-in-the-Loop (HITL) API Endpoints - P1 Feature #4

REST API for approval workflows and human review.

Endpoints:
- POST   /api/v1/hitl/approvals              - Create approval request
- GET    /api/v1/hitl/approvals              - List approval requests
- GET    /api/v1/hitl/approvals/{id}         - Get approval details
- POST   /api/v1/hitl/approvals/{id}/decide  - Submit approval decision
- POST   /api/v1/hitl/approvals/{id}/escalate - Escalate approval
- POST   /api/v1/hitl/approvals/{id}/cancel  - Cancel approval
- GET    /api/v1/hitl/approvals/pending      - Get pending approvals for user
- GET    /api/v1/hitl/approvals/stats        - Get approval statistics
- POST   /api/v1/hitl/templates              - Create approval template
- GET    /api/v1/hitl/templates              - List templates
- GET    /api/v1/hitl/templates/{slug}       - Get template by slug
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from backend.database.session import get_db
from backend.shared.hitl_models import (
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalDecision,
    ApprovalTemplateCreate,
    ApprovalTemplateResponse,
    ApprovalStats,
    ApprovalStatus,
    ApprovalPriority,
    EscalationTrigger,
)
from backend.shared.hitl_service import HITLService
from backend.api.response_transformers import ResponseTransformer
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEventType, AuditSeverity, AuditEvent
from backend.shared.auth import get_current_user_id, get_current_organization_id


router = APIRouter(prefix="/api/v1/hitl", tags=["hitl"])


# Alias for backwards compatibility (some routes use int, shared auth returns str)
async def get_organization_id(
    org_id: str = Depends(get_current_organization_id),
) -> Optional[int]:
    """Get current user's organization ID as int."""
    # Convert UUID string to int 1 for backwards compat with existing DB schema
    return 1


@router.post("/approvals", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_approval_request(
    request_data: ApprovalRequestCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Create new approval request.

    Pauses workflow execution until human decision is made.
    """
    approval_request = await HITLService.create_approval_request(
        db, request_data, user_id, organization_id
    )
    return approval_request


@router.get("/approvals", response_model=List[ApprovalRequestResponse])
async def list_approval_requests(
    status_filter: Optional[ApprovalStatus] = None,
    priority: Optional[ApprovalPriority] = None,
    workflow_execution_id: Optional[int] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """List approval requests with filters."""
    from sqlalchemy import select, and_
    from backend.shared.hitl_models import ApprovalRequest

    stmt = select(ApprovalRequest)

    filters = []
    if organization_id:
        filters.append(ApprovalRequest.organization_id == organization_id)
    if status_filter:
        filters.append(ApprovalRequest.status == status_filter)
    if priority:
        filters.append(ApprovalRequest.priority == priority)
    if workflow_execution_id:
        filters.append(ApprovalRequest.workflow_execution_id == workflow_execution_id)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(ApprovalRequest.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    approvals = result.scalars().all()

    # Return raw approvals (response_model handles serialization)
    return approvals


@router.get("/approvals/{approval_id}", response_model=ApprovalRequestResponse)
async def get_approval_request(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get approval request details."""
    from sqlalchemy import select
    from backend.shared.hitl_models import ApprovalRequest

    stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    result = await db.execute(stmt)
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found",
        )

    # Return raw approval (response_model handles serialization)
    return approval


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalRequestResponse)
async def submit_decision(
    approval_id: int,
    decision: ApprovalDecision,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Submit approval or rejection decision.

    Requires user to be in the required_approvers list.
    """
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        approval_request = await HITLService.submit_decision(
            db,
            approval_id,
            decision,
            user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Log audit event
        audit_logger = get_audit_logger()
        audit_event = AuditEvent(
            event_type=AuditEventType.APPROVAL_DECIDED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            user_email=user_id,  # Using user_id as email for now
            resource_type="approval_request",
            resource_id=str(approval_id),
            resource_name=approval_request.title,
            action=f"approval_{decision.decision}",
            description=f"User {user_id} {decision.decision} approval request '{approval_request.title}'",
            changes={
                "decision": decision.decision,
                "comment": decision.comment,
                "approval_id": approval_id,
            },
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )
        await audit_logger.log_event(audit_event, db=db)

        return approval_request
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/approvals/{approval_id}/escalate")
async def escalate_approval(
    approval_id: int,
    escalated_to_user_id: str,
    trigger: EscalationTrigger = EscalationTrigger.MANUAL,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Escalate approval to another user.

    Can be triggered manually or automatically (timeout, rejection, etc.).
    """
    try:
        escalation = await HITLService.escalate_request(
            db,
            approval_id,
            escalated_to_user_id,
            trigger,
            escalated_by_user_id=user_id,
            notes=notes,
        )
        return {
            "escalation_id": escalation.id,
            "level": escalation.level,
            "escalated_to": escalation.escalated_to_user_id,
            "trigger": escalation.trigger.value,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/approvals/{approval_id}/cancel", response_model=ApprovalRequestResponse)
async def cancel_approval(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Cancel pending approval request.

    Only the original requester can cancel.
    """
    try:
        approval_request = await HITLService.cancel_request(db, approval_id, user_id)
        return approval_request
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/approvals/pending/me", response_model=List[ApprovalRequestResponse])
async def get_my_pending_approvals(
    priority: Optional[ApprovalPriority] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get pending approvals for current user.

    Returns approvals where user is in required_approvers list.
    """
    approvals = await HITLService.get_pending_approvals(
        db, user_id, organization_id, priority, limit
    )

    # Return raw approvals (response_model handles serialization)
    return approvals


@router.get("/approvals/stats", response_model=ApprovalStats)
async def get_approval_stats(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get approval statistics for organization.

    Returns metrics like approval rate, avg response time, escalation rate, etc.
    """
    stats = await HITLService.get_approval_stats(
        db, organization_id, start_date, end_date
    )
    return stats


@router.post("/templates", response_model=ApprovalTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_approval_template(
    template_data: ApprovalTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Create reusable approval template.

    Templates define default approvers, timeouts, escalation rules, etc.
    """
    template = await HITLService.create_template(
        db, template_data, user_id, organization_id
    )
    return template


@router.get("/templates", response_model=List[ApprovalTemplateResponse])
async def list_approval_templates(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """List approval templates."""
    from sqlalchemy import select, and_, or_
    from backend.shared.hitl_models import ApprovalTemplate

    stmt = select(ApprovalTemplate).where(ApprovalTemplate.is_active == True)

    if organization_id:
        stmt = stmt.where(
            or_(
                ApprovalTemplate.organization_id == organization_id,
                ApprovalTemplate.organization_id.is_(None)
            )
        )

    if category:
        stmt = stmt.where(ApprovalTemplate.category == category)

    stmt = stmt.order_by(ApprovalTemplate.usage_count.desc())

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/templates/{slug}", response_model=ApprovalTemplateResponse)
async def get_approval_template(
    slug: str,
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """Get approval template by slug."""
    template = await HITLService.get_template_by_slug(db, slug, organization_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return template


@router.post("/process-timeouts")
async def process_timeouts(
    db: AsyncSession = Depends(get_db),
):
    """
    Process approval timeouts.

    This endpoint should be called by a background worker (cron job).
    Auto-approves or auto-rejects requests that have exceeded timeout.
    """
    processed_count = await HITLService.process_timeouts(db)

    return {
        "processed_count": processed_count,
        "message": f"Processed {processed_count} timed-out approval requests",
    }


@router.get("/approvals/{approval_id}/history")
async def get_approval_history(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full history of approval request.

    Includes responses, escalations, and notifications.
    """
    from sqlalchemy import select
    from backend.shared.hitl_models import (
        ApprovalRequest,
        ApprovalResponse,
        ApprovalEscalation,
        ApprovalNotification,
    )

    # Get request
    stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    result = await db.execute(stmt)
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found",
        )

    # Get responses
    stmt = select(ApprovalResponse).where(ApprovalResponse.request_id == approval_id)
    result = await db.execute(stmt)
    responses = result.scalars().all()

    # Get escalations
    stmt = select(ApprovalEscalation).where(ApprovalEscalation.request_id == approval_id)
    result = await db.execute(stmt)
    escalations = result.scalars().all()

    # Get notifications
    stmt = select(ApprovalNotification).where(ApprovalNotification.request_id == approval_id)
    result = await db.execute(stmt)
    notifications = result.scalars().all()

    return {
        "request": request,
        "responses": responses,
        "escalations": escalations,
        "notifications": notifications,
    }
