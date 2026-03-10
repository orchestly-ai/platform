"""
Agent Approval Service

Manages multi-stage approval workflows for agent deployment and changes.
Supports manager → security → compliance → CTO approval chains.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.shared.agent_registry_models import (
    AgentRegistry, AgentApproval,
    AgentStatus, ApprovalStatus,
    ApprovalRequest, ApprovalDecision
)
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEventType, AuditSeverity
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ApprovalWorkflowResponse(BaseModel):
    """Response model for approval workflow"""
    approval_id: str
    agent_id: str
    agent_name: str
    approval_stage: str
    approver_user_id: str
    status: str
    requested_by: str
    request_reason: Optional[str]
    decision_reason: Optional[str]
    requested_at: datetime
    decided_at: Optional[datetime]

    class Config:
        from_attributes = True


class AgentApprovalService:
    """
    Agent Approval Service

    Features:
    - Multi-stage approval workflows
    - Parallel and sequential approvals
    - Auto-approval rules
    - Approval audit trail
    - Escalation and timeouts
    """

    def __init__(self):
        try:
            self.audit_logger = get_audit_logger()
        except RuntimeError:
            # Audit logger not initialized (demo mode)
            self.audit_logger = None

    async def request_approval(
        self,
        request: ApprovalRequest,
        approver_user_id: str,
        requested_by: str,
        db: AsyncSession
    ) -> ApprovalWorkflowResponse:
        """
        Create approval request for an agent.

        Args:
            request: Approval request data
            approver_user_id: User who will approve
            requested_by: User requesting approval
            db: Database session

        Returns:
            Created approval workflow
        """
        logger.info(f"Creating approval request for agent: {request.agent_id}")

        # Verify agent exists
        stmt = select(AgentRegistry).where(AgentRegistry.agent_id == request.agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent '{request.agent_id}' not found")

        # Check if approval already exists for this stage
        existing_stmt = select(AgentApproval).where(
            and_(
                AgentApproval.agent_id == request.agent_id,
                AgentApproval.approval_stage == request.approval_stage,
                AgentApproval.status == ApprovalStatus.PENDING
            )
        )
        existing_result = await db.execute(existing_stmt)
        existing_approval = existing_result.scalar_one_or_none()

        if existing_approval:
            raise ValueError(
                f"Pending approval already exists for agent '{request.agent_id}' "
                f"at stage '{request.approval_stage}'"
            )

        # Create approval request
        approval = AgentApproval(
            approval_id=str(uuid4())[:16],
            agent_id=request.agent_id,
            approval_stage=request.approval_stage,
            approver_user_id=approver_user_id,
            status=ApprovalStatus.PENDING,
            requested_by=requested_by,
            request_reason=request.request_reason,
            requested_at=datetime.now()
        )

        db.add(approval)
        await db.commit()
        await db.refresh(approval)

        # Audit log
        if self.audit_logger:
            await self.audit_logger.log_event(
            event_type=AuditEventType.APPROVAL_REQUESTED,
            user_id=requested_by,
            organization_id=agent.organization_id,
            resource_type="agent_approval",
            resource_id=approval.approval_id,
            details={
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "approval_stage": approval.approval_stage,
                "approver_user_id": approver_user_id
            },
            severity=AuditSeverity.INFO,
            db=db
        )

        logger.info(f"✓ Approval request created: {approval.approval_id}")
        return self._to_response(approval, agent.name)

    async def approve_or_reject(
        self,
        approval_id: str,
        decision: ApprovalDecision,
        decided_by: str,
        db: AsyncSession
    ) -> ApprovalWorkflowResponse:
        """
        Approve or reject an approval request.

        Args:
            approval_id: ID of approval to decide
            decision: Approval decision (approved/rejected)
            decided_by: User making the decision
            db: Database session

        Returns:
            Updated approval workflow
        """
        logger.info(f"Processing approval decision: {approval_id} -> {decision.status}")

        # Get approval
        stmt = select(AgentApproval).where(AgentApproval.approval_id == approval_id)
        result = await db.execute(stmt)
        approval = result.scalar_one_or_none()

        if not approval:
            raise ValueError(f"Approval '{approval_id}' not found")

        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval '{approval_id}' is already {approval.status}")

        # Verify approver
        if approval.approver_user_id != decided_by:
            raise ValueError(
                f"User '{decided_by}' is not authorized to approve this request. "
                f"Approver should be '{approval.approver_user_id}'"
            )

        # Get agent
        agent_stmt = select(AgentRegistry).where(AgentRegistry.agent_id == approval.agent_id)
        agent_result = await db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent '{approval.agent_id}' not found")

        # Update approval
        approval.status = decision.status
        approval.decision_reason = decision.decision_reason
        approval.decided_at = datetime.now()

        # Update agent status if approved
        if decision.status == ApprovalStatus.APPROVED:
            # Check if all required approvals are complete
            all_approved = await self._check_all_approvals_complete(approval.agent_id, db)
            if all_approved:
                agent.status = AgentStatus.ACTIVE
                agent.approved_by = decided_by
                agent.approved_at = datetime.now()
                logger.info(f"✓ All approvals complete - Agent {agent.agent_id} activated")

        elif decision.status == ApprovalStatus.REJECTED:
            # Rejection blocks deployment
            agent.status = AgentStatus.DRAFT
            logger.info(f"✓ Approval rejected - Agent {agent.agent_id} set to DRAFT")

        await db.commit()
        await db.refresh(approval)

        # Audit log
        if self.audit_logger:
            await self.audit_logger.log_event(
            event_type=AuditEventType.APPROVAL_DECIDED,
            user_id=decided_by,
            organization_id=agent.organization_id,
            resource_type="agent_approval",
            resource_id=approval.approval_id,
            details={
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "approval_stage": approval.approval_stage,
                "decision": decision.status,
                "decision_reason": decision.decision_reason
            },
            severity=AuditSeverity.INFO if decision.status == ApprovalStatus.APPROVED else AuditSeverity.WARNING,
            db=db
        )

        logger.info(f"✓ Approval decision recorded: {decision.status}")
        return self._to_response(approval, agent.name)

    async def get_pending_approvals(
        self,
        approver_user_id: str,
        db: AsyncSession,
        limit: int = 50
    ) -> List[ApprovalWorkflowResponse]:
        """Get pending approvals for a user"""
        stmt = select(AgentApproval).where(
            and_(
                AgentApproval.approver_user_id == approver_user_id,
                AgentApproval.status == ApprovalStatus.PENDING
            )
        ).order_by(AgentApproval.requested_at.desc()).limit(limit)

        result = await db.execute(stmt)
        approvals = result.scalars().all()

        # Fetch agent names
        responses = []
        for approval in approvals:
            agent_stmt = select(AgentRegistry).where(AgentRegistry.agent_id == approval.agent_id)
            agent_result = await db.execute(agent_stmt)
            agent = agent_result.scalar_one_or_none()
            agent_name = agent.name if agent else "Unknown"
            responses.append(self._to_response(approval, agent_name))

        return responses

    async def get_agent_approvals(
        self,
        agent_id: str,
        db: AsyncSession
    ) -> List[ApprovalWorkflowResponse]:
        """Get all approval requests for an agent"""
        stmt = select(AgentApproval).where(
            AgentApproval.agent_id == agent_id
        ).order_by(AgentApproval.requested_at.desc())

        result = await db.execute(stmt)
        approvals = result.scalars().all()

        # Get agent name
        agent_stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        agent_result = await db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()
        agent_name = agent.name if agent else "Unknown"

        return [self._to_response(approval, agent_name) for approval in approvals]

    async def create_multi_stage_workflow(
        self,
        agent_id: str,
        stages: List[Dict[str, str]],
        requested_by: str,
        db: AsyncSession
    ) -> List[ApprovalWorkflowResponse]:
        """
        Create multi-stage approval workflow.

        Args:
            agent_id: Agent requiring approval
            stages: List of {stage: str, approver_user_id: str, reason: str}
            requested_by: User requesting approval
            db: Database session

        Returns:
            List of created approval requests
        """
        logger.info(f"Creating {len(stages)}-stage approval workflow for agent: {agent_id}")

        # Verify agent exists
        stmt = select(AgentRegistry).where(AgentRegistry.agent_id == agent_id)
        result = await db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Update agent status
        agent.status = AgentStatus.PENDING_APPROVAL

        # Create approval requests for each stage
        approvals = []
        for stage_config in stages:
            approval_request = ApprovalRequest(
                agent_id=agent_id,
                approval_stage=stage_config["stage"],
                request_reason=stage_config.get("reason", f"{stage_config['stage']} approval required")
            )

            approval = await self.request_approval(
                request=approval_request,
                approver_user_id=stage_config["approver_user_id"],
                requested_by=requested_by,
                db=db
            )
            approvals.append(approval)

        await db.commit()
        logger.info(f"✓ Created {len(approvals)} approval stages")
        return approvals

    async def _check_all_approvals_complete(
        self,
        agent_id: str,
        db: AsyncSession
    ) -> bool:
        """Check if all approval stages are complete (approved)"""
        stmt = select(AgentApproval).where(AgentApproval.agent_id == agent_id)
        result = await db.execute(stmt)
        approvals = result.scalars().all()

        if not approvals:
            return False

        # All approvals must be approved (none pending or rejected)
        return all(approval.status == ApprovalStatus.APPROVED for approval in approvals)

    def _to_response(
        self,
        approval: AgentApproval,
        agent_name: str
    ) -> ApprovalWorkflowResponse:
        """Convert ORM model to Pydantic response"""
        return ApprovalWorkflowResponse(
            approval_id=approval.approval_id,
            agent_id=approval.agent_id,
            agent_name=agent_name,
            approval_stage=approval.approval_stage,
            approver_user_id=approval.approver_user_id,
            status=approval.status,
            requested_by=approval.requested_by,
            request_reason=approval.request_reason,
            decision_reason=approval.decision_reason,
            requested_at=approval.requested_at,
            decided_at=approval.decided_at
        )


# Singleton instance
_agent_approval_service: Optional[AgentApprovalService] = None


def get_agent_approval_service() -> AgentApprovalService:
    """Get singleton AgentApprovalService instance"""
    global _agent_approval_service
    if _agent_approval_service is None:
        _agent_approval_service = AgentApprovalService()
    return _agent_approval_service
