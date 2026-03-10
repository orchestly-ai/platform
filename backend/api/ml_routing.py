"""
ML-Based Routing API - P2 Feature #6

REST API for intelligent LLM routing optimization.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from backend.database.session import get_db
from backend.shared.ml_routing_models import *
from backend.shared.ml_routing_service import MLRoutingService
from backend.shared.auth import get_current_user_id

router = APIRouter(prefix="/api/v1/ml-routing", tags=["ml-routing"])

# LLM Models
@router.post("/models", response_model=LLMModelResponse, status_code=status.HTTP_201_CREATED)
async def register_model(
    model_data: LLMModelCreate,
    db: AsyncSession = Depends(get_db),
):
    model = await MLRoutingService.register_model(db, model_data)
    return model

@router.get("/models", response_model=List[LLMModelResponse])
async def list_models(
    provider: Optional[ModelProvider] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    models = await MLRoutingService.get_models(db, provider)
    return models

# Routing Policies
@router.post("/policies", response_model=RoutingPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: RoutingPolicyCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    policy = await MLRoutingService.create_routing_policy(db, policy_data, user_id)
    return policy

@router.get("/policies", response_model=List[RoutingPolicyResponse])
async def list_policies(
    db: AsyncSession = Depends(get_db),
):
    policies = await MLRoutingService.get_routing_policies(db)
    return policies

# Routing
@router.post("/route", response_model=RouteResponse)
async def route_request(
    route_request: RouteRequest,
    db: AsyncSession = Depends(get_db),
):
    response = await MLRoutingService.route_request(db, route_request)
    return response

@router.post("/decisions/{decision_id}/record")
async def record_execution(
    decision_id: int,
    actual_latency_ms: float,
    actual_input_tokens: int,
    actual_output_tokens: int,
    success: bool,
    error_message: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    decision = await MLRoutingService.record_execution(
        db, decision_id, actual_latency_ms, actual_input_tokens,
        actual_output_tokens, success, error_message
    )
    return {"id": decision.id, "cost_saved_usd": decision.cost_saved_usd}

# Analytics
@router.get("/stats", response_model=OptimizationStatsResponse)
async def get_stats(
    hours: int = Query(24, le=168),
    db: AsyncSession = Depends(get_db),
):
    stats = await MLRoutingService.get_optimization_stats(db, hours)
    return stats
