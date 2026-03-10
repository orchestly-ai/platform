"""
Router API Endpoints

API endpoints for model router configuration and routing decisions.
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.router import (
    get_routing_engine,
    get_model_registry,
    get_health_monitor,
)
from backend.router.strategies import RoutingRequest


# ============================================================================
# Request/Response Models
# ============================================================================

class ModelCreate(BaseModel):
    """Request to create a new model."""
    provider: str = Field(..., description="Provider name (openai, anthropic, google)")
    model_name: str = Field(..., description="Model identifier")
    display_name: Optional[str] = Field(None, description="Human-readable name")
    cost_per_1k_input_tokens: Optional[float] = Field(None, description="Cost per 1K input tokens")
    cost_per_1k_output_tokens: Optional[float] = Field(None, description="Cost per 1K output tokens")
    max_tokens: Optional[int] = Field(None, description="Maximum context window")
    supports_vision: bool = Field(False, description="Supports vision inputs")
    supports_tools: bool = Field(False, description="Supports function calling")
    quality_score: float = Field(0.8, description="Quality score (0-1)")


class ModelUpdate(BaseModel):
    """Request to update a model."""
    display_name: Optional[str] = None
    cost_per_1k_input_tokens: Optional[float] = None
    cost_per_1k_output_tokens: Optional[float] = None
    max_tokens: Optional[int] = None
    supports_vision: Optional[bool] = None
    supports_tools: Optional[bool] = None
    quality_score: Optional[float] = None
    is_enabled: Optional[bool] = None


class StrategyCreate(BaseModel):
    """Request to create a routing strategy."""
    strategy_type: str = Field(..., description="Strategy type (cost, latency, quality, weighted_rr, round_robin, balanced)")
    scope_type: str = Field("organization", description="Scope type (organization, workflow, agent)")
    scope_id: Optional[str] = Field(None, description="Scope ID (for workflow or agent)")
    config: Optional[Dict] = Field(None, description="Strategy configuration")
    fallback_strategy_id: Optional[str] = Field(None, description="Fallback strategy ID")


class StrategyUpdate(BaseModel):
    """Request to update a routing strategy."""
    strategy_type: Optional[str] = None
    config: Optional[Dict] = None
    fallback_strategy_id: Optional[str] = None
    is_active: Optional[bool] = None


class RouteRequest(BaseModel):
    """Request to route a model selection (dry-run)."""
    min_quality: Optional[float] = Field(None, description="Minimum quality score")
    max_cost: Optional[float] = Field(None, description="Maximum cost per 1K tokens")
    require_vision: bool = Field(False, description="Require vision support")
    require_tools: bool = Field(False, description="Require function calling support")
    max_latency_ms: Optional[int] = Field(None, description="Maximum acceptable latency")
    scope_type: str = Field("organization", description="Scope type")
    scope_id: Optional[str] = Field(None, description="Scope ID")


class ModelWeightCreate(BaseModel):
    """Request to add model weight to strategy."""
    model_id: str = Field(..., description="Model ID")
    weight: float = Field(1.0, description="Weight for weighted routing")
    priority: int = Field(0, description="Priority for priority-based routing")


# ============================================================================
# Router
# ============================================================================

router = APIRouter(prefix="/api/router", tags=["Model Router"])


# ============================================================================
# Model Management Endpoints
# ============================================================================

@router.get("/models")
async def list_models(
    organization_id: str,
    provider: Optional[str] = None,
    enabled_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    List available models.

    Returns all models registered for the organization with their current health status.
    """
    registry = get_model_registry(db)
    monitor = get_health_monitor(db)

    models = await registry.list_models(organization_id, provider, enabled_only)

    # Enrich with health data
    model_ids = [m.id for m in models]
    health_data = monitor.get_all_health(model_ids)

    result = []
    for model in models:
        model_dict = model.to_dict()
        if model.id in health_data:
            model_dict["health"] = health_data[model.id].to_dict()
        else:
            model_dict["health"] = None
        result.append(model_dict)

    return {"models": result, "total": len(result)}


@router.post("/models")
async def create_model(
    organization_id: str,
    model: ModelCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new model.

    Add a custom model or override default model pricing.
    """
    registry = get_model_registry(db)

    created = await registry.register_model(
        organization_id=organization_id,
        **model.dict(),
    )

    return {"model": created.to_dict(), "message": "Model registered successfully"}


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific model by ID."""
    registry = get_model_registry(db)
    monitor = get_health_monitor(db)

    model = await registry.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model_dict = model.to_dict()
    health = monitor.get_health(model_id)
    model_dict["health"] = health.to_dict()

    return {"model": model_dict}


@router.put("/models/{model_id}")
async def update_model(
    model_id: str,
    updates: ModelUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a model's configuration."""
    registry = get_model_registry(db)

    # Filter out None values
    update_dict = {k: v for k, v in updates.dict().items() if v is not None}

    updated = await registry.update_model(model_id, **update_dict)
    if not updated:
        raise HTTPException(status_code=404, detail="Model not found")

    return {"model": updated.to_dict(), "message": "Model updated successfully"}


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a model."""
    registry = get_model_registry(db)

    success = await registry.delete_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")

    return {"message": "Model deleted successfully"}


@router.post("/models/seed")
async def seed_models(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Seed default popular models.

    Adds commonly used models with current pricing.
    """
    registry = get_model_registry(db)
    await registry.seed_default_models(organization_id)

    return {"message": "Default models seeded successfully"}


# ============================================================================
# Strategy Management Endpoints
# ============================================================================

@router.get("/strategies")
async def list_strategies(
    organization_id: str,
    scope_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List routing strategies for an organization."""
    engine = get_routing_engine(db)

    strategies = await engine.list_strategies(organization_id, scope_type)

    return {"strategies": strategies, "total": len(strategies)}


@router.post("/strategies")
async def create_strategy(
    organization_id: str,
    strategy: StrategyCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new routing strategy.

    This will deactivate any existing strategy for the same scope.
    """
    engine = get_routing_engine(db)

    strategy_id = await engine.create_strategy(
        organization_id=organization_id,
        strategy_type=strategy.strategy_type,
        scope_type=strategy.scope_type,
        scope_id=strategy.scope_id,
        config=strategy.config,
        fallback_strategy_id=strategy.fallback_strategy_id,
    )

    return {
        "strategy_id": strategy_id,
        "message": "Strategy created successfully"
    }


@router.put("/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    updates: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a routing strategy."""
    engine = get_routing_engine(db)

    # Filter out None values
    update_dict = {k: v for k, v in updates.dict().items() if v is not None}

    success = await engine.update_strategy(strategy_id, **update_dict)
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")

    return {"message": "Strategy updated successfully"}


@router.post("/strategies/{strategy_id}/weights")
async def add_model_weight(
    strategy_id: str,
    weight: ModelWeightCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add model weight to a strategy.

    Used for weighted round-robin or priority-based routing.
    """
    engine = get_routing_engine(db)

    weight_id = await engine.add_model_weight(
        strategy_id=strategy_id,
        model_id=weight.model_id,
        weight=weight.weight,
        priority=weight.priority,
    )

    return {
        "weight_id": weight_id,
        "message": "Model weight added successfully"
    }


# ============================================================================
# Routing Endpoints
# ============================================================================

@router.post("/route")
async def test_route(
    organization_id: str,
    request: RouteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Test routing decision (dry-run).

    Returns the model that would be selected for the given constraints.
    """
    engine = get_routing_engine(db)

    routing_request = RoutingRequest(
        min_quality=request.min_quality,
        max_cost=request.max_cost,
        require_vision=request.require_vision,
        require_tools=request.require_tools,
        max_latency_ms=request.max_latency_ms,
    )

    decision = await engine.route(
        organization_id=organization_id,
        request=routing_request,
        scope_type=request.scope_type,
        scope_id=request.scope_id,
    )

    if not decision:
        raise HTTPException(
            status_code=404,
            detail="No suitable model found for the given constraints"
        )

    return {"decision": decision.to_dict()}


# ============================================================================
# Health Monitoring Endpoints
# ============================================================================

@router.get("/health")
async def get_health_dashboard(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get health dashboard data.

    Returns overview of all models with health metrics.
    """
    monitor = get_health_monitor(db)

    dashboard = await monitor.get_dashboard_data(organization_id)

    return dashboard


@router.get("/health/{model_id}")
async def get_model_health(
    model_id: str,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """
    Get health history for a specific model.

    Returns time-series health metrics.
    """
    monitor = get_health_monitor(db)

    # Get current health
    current = monitor.get_health(model_id)

    # Get historical metrics
    history = await monitor.get_historical_metrics(model_id, hours)

    return {
        "model_id": model_id,
        "current": current.to_dict(),
        "history": [h.to_dict() for h in history],
    }


# Export router
__all__ = ["router"]
