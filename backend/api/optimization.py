"""
API Endpoints for Auto-Optimization Engine

Provides endpoints to:
- Get optimization recommendations
- Approve/reject recommendations
- Apply approved optimizations
- Get optimization summary
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime

from backend.database.session import get_db
from backend.shared.auto_optimization_engine import (
    get_optimization_engine,
    OptimizationRecommendation,
    OptimizationStatus
)
from backend.api.cost import get_authenticated_user


router = APIRouter(prefix="/optimization", tags=["optimization"])


class RecommendationResponse(BaseModel):
    """Response model for a single recommendation."""
    recommendation_id: str
    organization_id: str
    type: str
    title: str
    description: str
    confidence: str
    estimated_savings: Optional[float]
    estimated_latency_improvement_ms: Optional[float]
    affected_workflows: List[str]
    current_config: dict
    recommended_config: dict
    evidence: dict
    auto_apply_eligible: bool
    status: str
    created_at: str
    applied_at: Optional[str]


class OptimizationSummaryResponse(BaseModel):
    """Response model for optimization summary."""
    organization_id: str
    total_recommendations: int
    total_estimated_monthly_savings: float
    total_latency_improvement_ms: float
    by_type: dict
    high_confidence_count: int
    auto_apply_eligible_count: int
    recommendations: List[dict]


class ApproveRequest(BaseModel):
    """Request to approve a recommendation."""
    recommendation_id: str


class ApplyRequest(BaseModel):
    """Request to apply an approved recommendation."""
    recommendation_id: str


@router.get("/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations(
    db=Depends(get_db),
    current_user=Depends(get_authenticated_user)
):
    """
    Get optimization recommendations for the user's organization.

    Analyzes execution patterns and returns actionable recommendations
    for cost reduction, latency improvement, and A/B test graduation.
    """
    engine = get_optimization_engine(db)

    recommendations = await engine.analyze_organization(current_user.organization_id)

    return [
        RecommendationResponse(**r.to_dict())
        for r in recommendations
    ]


@router.get("/summary", response_model=OptimizationSummaryResponse)
async def get_optimization_summary(
    db=Depends(get_db),
    current_user=Depends(get_authenticated_user)
):
    """
    Get summary of optimization opportunities.

    Returns aggregate metrics including total potential savings,
    latency improvements, and breakdown by optimization type.
    """
    engine = get_optimization_engine(db)

    summary = await engine.get_optimization_summary(current_user.organization_id)

    return OptimizationSummaryResponse(**summary)


@router.post("/recommendations/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: str,
    db=Depends(get_db),
    current_user=Depends(get_authenticated_user)
):
    """
    Approve a recommendation for application.

    Requires admin role. Once approved, the recommendation can be
    applied automatically or manually.
    """
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to approve optimizations"
        )

    engine = get_optimization_engine(db)
    recommendations = engine.get_cached_recommendations(current_user.organization_id)

    rec = None
    for r in recommendations:
        if str(r.recommendation_id) == recommendation_id:
            rec = r
            break

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found"
        )

    if rec.status != OptimizationStatus.SUGGESTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recommendation is already {rec.status.value}"
        )

    rec.status = OptimizationStatus.APPROVED

    return {
        "status": "approved",
        "recommendation_id": recommendation_id,
        "approved_by": current_user.user_id,
        "approved_at": datetime.utcnow().isoformat()
    }


@router.post("/recommendations/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: str,
    db=Depends(get_db),
    current_user=Depends(get_authenticated_user)
):
    """
    Reject a recommendation.

    The recommendation will be marked as rejected and won't be shown again.
    """
    engine = get_optimization_engine(db)
    recommendations = engine.get_cached_recommendations(current_user.organization_id)

    rec = None
    for r in recommendations:
        if str(r.recommendation_id) == recommendation_id:
            rec = r
            break

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found"
        )

    rec.status = OptimizationStatus.REJECTED

    return {
        "status": "rejected",
        "recommendation_id": recommendation_id,
        "rejected_by": current_user.user_id,
        "rejected_at": datetime.utcnow().isoformat()
    }


@router.post("/recommendations/{recommendation_id}/apply")
async def apply_recommendation(
    recommendation_id: str,
    db=Depends(get_db),
    current_user=Depends(get_authenticated_user)
):
    """
    Apply an approved recommendation.

    This will make the actual configuration changes recommended.
    Requires admin role and recommendation must be in APPROVED status.
    """
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to apply optimizations"
        )

    engine = get_optimization_engine(db)

    # Find and validate recommendation
    recommendations = engine.get_cached_recommendations(current_user.organization_id)
    rec = None
    for r in recommendations:
        if str(r.recommendation_id) == recommendation_id:
            rec = r
            break

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found"
        )

    if rec.status != OptimizationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recommendation must be approved before applying (current: {rec.status.value})"
        )

    # Apply the optimization
    success = await engine.apply_recommendation(
        UUID(recommendation_id),
        approved_by=current_user.user_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to apply optimization"
        )

    return {
        "status": "applied",
        "recommendation_id": recommendation_id,
        "applied_by": current_user.user_id,
        "applied_at": datetime.utcnow().isoformat(),
        "changes": rec.recommended_config
    }


@router.get("/auto-apply-candidates")
async def get_auto_apply_candidates(
    db=Depends(get_db),
    current_user=Depends(get_authenticated_user)
):
    """
    Get recommendations eligible for automatic application.

    These are high-confidence recommendations that can be safely
    applied without manual review. Still requires admin approval
    to enable auto-apply for the organization.
    """
    engine = get_optimization_engine(db)
    recommendations = await engine.analyze_organization(current_user.organization_id)

    auto_apply_candidates = [
        r.to_dict() for r in recommendations
        if r.auto_apply_eligible
    ]

    return {
        "organization_id": current_user.organization_id,
        "auto_apply_candidates": auto_apply_candidates,
        "count": len(auto_apply_candidates),
        "total_estimated_savings": sum(
            r.get("estimated_savings", 0) or 0
            for r in auto_apply_candidates
        )
    }
