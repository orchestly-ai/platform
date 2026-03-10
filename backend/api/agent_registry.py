"""
Agent Registry & Governance API

REST API endpoints for agent management, approvals, policies, and analytics.
Enterprise-grade agent governance for organizations with 50+ AI agents.
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.shared.agent_registry_service import get_agent_registry_service
from backend.shared.agent_approval_service import get_agent_approval_service, ApprovalWorkflowResponse
from backend.shared.agent_policy_service import get_agent_policy_service, PolicyViolation
from backend.shared.agent_analytics_service import (
    get_agent_analytics_service,
    CostBreakdown,
    AgentCostAnalytics,
    UsageLogEntry
)
from backend.shared.agent_registry_models import (
    AgentRegistryCreate, AgentRegistryUpdate, AgentRegistryResponse,
    ApprovalRequest, ApprovalDecision,
    PolicyCreate, PolicyResponse,
    AgentSearchFilters, AgentStats
)
from backend.shared.rbac_service import get_rbac_service, requires_permission, Permission
from backend.shared.plan_enforcement import enforce_agent_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent-registry", tags=["Agent Registry & Governance"])


# ============================================================================
# Agent Registry Endpoints
# ============================================================================

@router.post("/agents", response_model=AgentRegistryResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    agent_data: AgentRegistryCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_MANAGE))
):
    """
    Register a new agent in the registry.

    Requires: AGENT_MANAGE permission

    Returns:
        Created agent registry entry
    """
    try:
        # Enforce agent limit for the organization
        org_id = agent_data.organization_id if hasattr(agent_data, 'organization_id') and agent_data.organization_id else "default"
        await enforce_agent_limit(org_id, db)

        service = get_agent_registry_service()
        agent = await service.register_agent(agent_data, db, user_id)
        return agent
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to register agent: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to register agent")


@router.get("/agents/{agent_id}", response_model=AgentRegistryResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_VIEW))
):
    """
    Get agent by ID.

    Requires: AGENT_VIEW permission
    """
    service = get_agent_registry_service()
    agent = await service.get_agent(agent_id, db)

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_id}' not found")

    return agent


@router.put("/agents/{agent_id}", response_model=AgentRegistryResponse)
async def update_agent(
    agent_id: str,
    update_data: AgentRegistryUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_MANAGE))
):
    """
    Update agent metadata.

    Requires: AGENT_MANAGE permission
    """
    try:
        service = get_agent_registry_service()
        agent = await service.update_agent(agent_id, update_data, db, user_id)
        return agent
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update agent: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update agent")


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_MANAGE))
):
    """
    Delete agent from registry.

    Requires: AGENT_MANAGE permission
    """
    try:
        service = get_agent_registry_service()
        await service.delete_agent(agent_id, db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete agent: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete agent")


@router.post("/agents/search", response_model=List[AgentRegistryResponse])
async def search_agents(
    filters: AgentSearchFilters,
    organization_id: str = Query(..., description="Organization ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_VIEW))
):
    """
    Search agents with filters.

    Supports filtering by:
    - Text query (name/description)
    - Owner (user/team)
    - Category
    - Tags (capabilities)
    - Status
    - Sensitivity level
    - Cost range

    Requires: AGENT_VIEW permission
    """
    service = get_agent_registry_service()
    agents = await service.search_agents(filters, organization_id, db, limit, offset)
    return agents


@router.get("/agents/duplicates", response_model=dict)
async def find_duplicate_capabilities(
    organization_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_VIEW))
):
    """
    Find agents with duplicate capabilities.

    Identifies agents with overlapping tags/capabilities to avoid duplication.

    Requires: AGENT_VIEW permission

    Returns:
        Dictionary mapping capability tag to list of agents with that capability
    """
    service = get_agent_registry_service()
    duplicates = await service.find_duplicate_capabilities(organization_id, db)
    return duplicates


@router.get("/stats", response_model=AgentStats)
async def get_registry_stats(
    organization_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_VIEW))
):
    """
    Get registry statistics.

    Returns:
        Total agents, active agents, pending approvals, cost, etc.

    Requires: AGENT_VIEW permission
    """
    service = get_agent_registry_service()
    stats = await service.get_registry_stats(organization_id, db)
    return stats


# ============================================================================
# Approval Workflow Endpoints
# ============================================================================

@router.post("/approvals", response_model=ApprovalWorkflowResponse, status_code=status.HTTP_201_CREATED)
async def request_approval(
    approval_request: ApprovalRequest,
    approver_user_id: str = Query(..., description="User who will approve"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_MANAGE))
):
    """
    Create approval request for an agent.

    Requires: AGENT_MANAGE permission
    """
    try:
        service = get_agent_approval_service()
        approval = await service.request_approval(
            request=approval_request,
            approver_user_id=approver_user_id,
            requested_by=user_id,
            db=db
        )
        return approval
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create approval request: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create approval request")


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalWorkflowResponse)
async def decide_approval(
    approval_id: str,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_APPROVE))
):
    """
    Approve or reject an approval request.

    Requires: AGENT_APPROVE permission
    """
    try:
        service = get_agent_approval_service()
        approval = await service.approve_or_reject(approval_id, decision, user_id, db)
        return approval
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process approval decision: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process approval")


@router.get("/approvals/pending", response_model=List[ApprovalWorkflowResponse])
async def get_pending_approvals(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_APPROVE))
):
    """
    Get pending approvals for current user.

    Requires: AGENT_APPROVE permission
    """
    service = get_agent_approval_service()
    approvals = await service.get_pending_approvals(user_id, db, limit)
    return approvals


@router.get("/agents/{agent_id}/approvals", response_model=List[ApprovalWorkflowResponse])
async def get_agent_approvals(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_VIEW))
):
    """
    Get all approval requests for an agent.

    Requires: AGENT_VIEW permission
    """
    service = get_agent_approval_service()
    approvals = await service.get_agent_approvals(agent_id, db)
    return approvals


@router.post("/agents/{agent_id}/multi-stage-approval", response_model=List[ApprovalWorkflowResponse])
async def create_multi_stage_workflow(
    agent_id: str,
    stages: List[dict],
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_MANAGE))
):
    """
    Create multi-stage approval workflow.

    Example stages:
    [
        {"stage": "manager", "approver_user_id": "user_003", "reason": "Manager approval"},
        {"stage": "security", "approver_user_id": "user_004", "reason": "Security review"},
        {"stage": "compliance", "approver_user_id": "user_005", "reason": "Compliance review"}
    ]

    Requires: AGENT_MANAGE permission
    """
    try:
        service = get_agent_approval_service()
        approvals = await service.create_multi_stage_workflow(agent_id, stages, user_id, db)
        return approvals
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create multi-stage workflow: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create workflow")


# ============================================================================
# Policy Management Endpoints
# ============================================================================

@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: PolicyCreate,
    organization_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.POLICY_MANAGE))
):
    """
    Create a new governance policy.

    Policy types:
    - cost_cap: Enforce maximum cost per month
    - data_access: Restrict data source access
    - approval_required: Require approvals for certain actions
    - retention: Data retention rules
    - compliance: HIPAA, SOC 2, etc.

    Requires: POLICY_MANAGE permission
    """
    try:
        service = get_agent_policy_service()
        policy = await service.create_policy(policy_data, organization_id, user_id, db)
        return policy
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create policy: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create policy")


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.POLICY_VIEW))
):
    """
    Get policy by ID.

    Requires: POLICY_VIEW permission
    """
    service = get_agent_policy_service()
    policy = await service.get_policy(policy_id, db)

    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy '{policy_id}' not found")

    return policy


@router.get("/policies", response_model=List[PolicyResponse])
async def get_organization_policies(
    organization_id: str = Query(..., description="Organization ID"),
    active_only: bool = Query(True, description="Only return active policies"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.POLICY_VIEW))
):
    """
    Get all policies for organization.

    Requires: POLICY_VIEW permission
    """
    service = get_agent_policy_service()
    policies = await service.get_organization_policies(organization_id, db, active_only)
    return policies


@router.put("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    rules: dict,
    enforcement_level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.POLICY_MANAGE))
):
    """
    Update policy rules or enforcement level.

    Requires: POLICY_MANAGE permission
    """
    try:
        service = get_agent_policy_service()
        policy = await service.update_policy(policy_id, rules, enforcement_level, db, user_id)
        return policy
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update policy: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update policy")


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.POLICY_MANAGE))
):
    """
    Deactivate a policy.

    Requires: POLICY_MANAGE permission
    """
    try:
        service = get_agent_policy_service()
        await service.deactivate_policy(policy_id, db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to deactivate policy: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deactivate policy")


@router.post("/agents/{agent_id}/check-compliance", response_model=List[PolicyResponse])
async def check_agent_compliance(
    agent_id: str,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AGENT_VIEW))
):
    """
    Check if agent complies with all applicable policies.

    Returns list of violated policies.
    If enforcement is blocking, raises PolicyViolation exception.

    Requires: AGENT_VIEW permission
    """
    try:
        service = get_agent_policy_service()
        violations = await service.check_agent_compliance(agent_id, db, action)
        return violations
    except PolicyViolation as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Policy violation",
                "policy_name": e.policy_name,
                "message": e.message,
                "details": e.details
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to check compliance: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to check compliance")


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get("/analytics/cost-by-team", response_model=List[CostBreakdown])
async def get_cost_by_team(
    organization_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.ANALYTICS_VIEW))
):
    """
    Get cost breakdown by team.

    Requires: ANALYTICS_VIEW permission
    """
    service = get_agent_analytics_service()
    breakdown = await service.get_cost_by_team(organization_id, db)
    return breakdown


@router.get("/analytics/cost-by-category", response_model=List[CostBreakdown])
async def get_cost_by_category(
    organization_id: str = Query(..., description="Organization ID"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.ANALYTICS_VIEW))
):
    """
    Get cost breakdown by agent category.

    Requires: ANALYTICS_VIEW permission
    """
    service = get_agent_analytics_service()
    breakdown = await service.get_cost_by_category(organization_id, db)
    return breakdown


@router.get("/analytics/top-expensive", response_model=List[AgentCostAnalytics])
async def get_top_expensive_agents(
    organization_id: str = Query(..., description="Organization ID"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.ANALYTICS_VIEW))
):
    """
    Get top N most expensive agents.

    Includes cost trends (increasing, decreasing, stable).

    Requires: ANALYTICS_VIEW permission
    """
    service = get_agent_analytics_service()
    agents = await service.get_top_expensive_agents(organization_id, db, limit)
    return agents


@router.get("/analytics/agents/{agent_id}/usage", response_model=List[UsageLogEntry])
async def get_agent_usage_logs(
    agent_id: str,
    limit: int = Query(100, ge=1, le=500),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.ANALYTICS_VIEW))
):
    """
    Get usage logs for specific agent.

    Requires: ANALYTICS_VIEW permission
    """
    service = get_agent_analytics_service()
    logs = await service.get_agent_usage_logs(agent_id, db, limit, start_date, end_date)
    return logs


@router.get("/analytics/pii-access-audit", response_model=List[UsageLogEntry])
async def get_pii_access_audit(
    organization_id: str = Query(..., description="Organization ID"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(requires_permission(Permission.AUDIT_VIEW))
):
    """
    Get audit trail of PII access.

    Critical for SOC 2, HIPAA compliance.

    Requires: AUDIT_VIEW permission
    """
    service = get_agent_analytics_service()
    logs = await service.get_pii_access_audit(organization_id, db, start_date, end_date, limit)
    return logs
