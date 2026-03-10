"""
Routing Configuration API Endpoints

Provides endpoints for managing routing strategies at different scopes:
- Organization level (default for all workflows)
- Workflow level (override for specific workflow)
- Agent level (override for specific agent)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from backend.database.session import get_db
from backend.shared.ml_routing_models import RoutingPolicy, RoutingStrategy as MLRoutingStrategy, OptimizationGoal
from backend.shared.smart_router_service import RoutingStrategy

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])


# Pydantic models for API
class RouterConfigRequest(BaseModel):
    """Request to save routing configuration"""
    scope: str = Field(..., description="Scope: organization, workflow, or agent")
    scope_id: Optional[str] = Field(None, alias="scopeId", description="ID for workflow or agent scope")
    strategy_type: str = Field(..., alias="strategyType", description="Strategy: cost_optimized, latency_optimized, quality_first, etc.")
    min_quality_score: Optional[float] = Field(None, alias="minQualityScore", ge=0, le=1)
    max_latency: Optional[int] = Field(None, alias="maxLatency", gt=0)
    max_cost_per_request: Optional[float] = Field(None, alias="maxCostPerRequest", gt=0)
    fallback_strategy: Optional[str] = Field(None, alias="fallbackStrategy")
    model_preferences: Optional[List[Dict[str, Any]]] = Field(default_factory=list, alias="modelPreferences")
    enabled_models: Optional[List[str]] = Field(default_factory=list, alias="enabledModels")

    class Config:
        populate_by_name = True  # Accept both camelCase and snake_case


class RouterConfigResponse(BaseModel):
    """Response with routing configuration"""
    scope: str
    scope_id: Optional[str]
    strategy_type: str
    min_quality_score: Optional[float]
    max_latency: Optional[int]
    max_cost_per_request: Optional[float]
    fallback_strategy: Optional[str]
    model_preferences: List[Dict[str, Any]]
    enabled_models: List[str]
    created_at: Optional[str]


class TestRoutingRequest(BaseModel):
    """Request to test routing decision"""
    scope: str
    scope_id: Optional[str] = Field(None, alias="scopeId")
    strategy_type: str = Field(..., alias="strategyType")
    min_quality_score: Optional[float] = Field(None, alias="minQualityScore")
    max_latency: Optional[int] = Field(None, alias="maxLatency")
    model_preferences: List[Dict[str, Any]] = Field(default_factory=list, alias="modelPreferences")

    class Config:
        populate_by_name = True


class TestRoutingResponse(BaseModel):
    """Response from routing test"""
    selected_model: str = Field(..., alias="selectedModel")
    provider: str
    estimated_cost: float = Field(..., alias="estimatedCost")
    estimated_latency: int = Field(..., alias="estimatedLatency")
    reason: str
    strategy_used: str

    class Config:
        populate_by_name = True


@router.get("/config", response_model=RouterConfigResponse)
async def get_routing_config(
    scope: str = Query(..., description="Scope: organization, workflow, or agent"),
    scope_id: Optional[str] = Query(None, description="Workflow ID or Agent ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get routing configuration for a specific scope.

    Hierarchy:
    1. Agent-level config (if scope='agent' and scope_id provided)
    2. Workflow-level config (if scope='workflow' and scope_id provided)
    3. Organization-level default (if scope='organization')
    """
    from sqlalchemy import or_

    # Build query
    stmt = select(RoutingPolicy).where(RoutingPolicy.is_active == True)

    if scope == "organization":
        # Get organization default (no scope_id)
        stmt = stmt.where(
            or_(
                RoutingPolicy.name.like("%organization%"),
                RoutingPolicy.name.like("%default%")
            )
        )
    elif scope == "workflow" and scope_id:
        # Get workflow-specific config
        stmt = stmt.where(RoutingPolicy.name.like(f"%{scope_id}%"))
    elif scope == "agent" and scope_id:
        # Get agent-specific config
        stmt = stmt.where(RoutingPolicy.name.like(f"%{scope_id}%"))

    result = await db.execute(stmt)
    policy = result.scalars().first()

    if not policy:
        # Return default configuration
        return RouterConfigResponse(
            scope=scope,
            scope_id=scope_id,
            strategy_type="cost_optimized",
            min_quality_score=0.7,
            max_latency=5000,
            max_cost_per_request=1.0,
            fallback_strategy="latency_optimized",
            model_preferences=[],
            enabled_models=["gpt-4o-mini", "claude-3-haiku", "claude-3-sonnet"],
            created_at=None
        )

    # Convert database model to response
    return RouterConfigResponse(
        scope=scope,
        scope_id=scope_id,
        strategy_type=policy.strategy,
        min_quality_score=policy.min_quality_score,
        max_latency=int(policy.max_latency_ms) if policy.max_latency_ms else None,
        max_cost_per_request=policy.max_cost_per_request_usd,
        fallback_strategy=policy.fallback_strategy,
        model_preferences=[],
        enabled_models=policy.allowed_models or [],
        created_at=policy.created_at.isoformat() if policy.created_at else None
    )


@router.post("/config")
async def save_routing_config(
    config: RouterConfigRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Save routing configuration for a specific scope.

    Creates or updates the routing policy in the database.
    """
    # Build policy name
    if config.scope == "organization":
        policy_name = "organization_default"
    elif config.scope == "workflow":
        policy_name = f"workflow_{config.scope_id}"
    elif config.scope == "agent":
        policy_name = f"agent_{config.scope_id}"
    else:
        raise HTTPException(status_code=400, detail=f"Invalid scope: {config.scope}")

    # Check if policy already exists
    stmt = select(RoutingPolicy).where(
        RoutingPolicy.is_active == True,
        RoutingPolicy.name == policy_name
    )
    result = await db.execute(stmt)
    existing_policy = result.scalars().first()

    if existing_policy:
        # Update existing
        existing_policy.strategy = config.strategy_type
        existing_policy.min_quality_score = config.min_quality_score or 0.0
        existing_policy.max_latency_ms = float(config.max_latency) if config.max_latency else None
        existing_policy.max_cost_per_request_usd = config.max_cost_per_request
        existing_policy.fallback_strategy = config.fallback_strategy
        existing_policy.allowed_models = config.enabled_models
    else:
        # Create new
        new_policy = RoutingPolicy(
            name=policy_name,
            description=f"Routing policy for {config.scope}",
            strategy=config.strategy_type,
            optimization_goal=OptimizationGoal.MINIMIZE_COST.value if config.strategy_type == "cost_optimized" else OptimizationGoal.MINIMIZE_LATENCY.value,
            min_quality_score=config.min_quality_score or 0.0,
            max_latency_ms=float(config.max_latency) if config.max_latency else None,
            max_cost_per_request_usd=config.max_cost_per_request,
            fallback_strategy=config.fallback_strategy,
            allowed_models=config.enabled_models,
            use_ml_prediction=False,  # Start with rule-based
            is_active=True
        )
        db.add(new_policy)

    await db.commit()

    return {"success": True, "message": f"Routing configuration saved for {config.scope}"}


@router.post("/test", response_model=TestRoutingResponse)
async def test_routing(
    request: TestRoutingRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Test routing decision without actually executing.

    Simulates which model would be selected based on the configuration.
    """
    from backend.shared.smart_router_service import get_smart_router, UniversalRequest, OrgRoutingConfig

    # Map strategy type to RoutingStrategy enum
    strategy_map = {
        "cost_optimized": RoutingStrategy.COST_OPTIMIZED,
        "latency_optimized": RoutingStrategy.LATENCY_OPTIMIZED,
        "quality_first": RoutingStrategy.BEST_AVAILABLE,  # Use best_available for quality
        "weighted_roundrobin": RoutingStrategy.PRIMARY_WITH_BACKUP,
        "auto": RoutingStrategy.COST_OPTIMIZED,  # Default to cost optimized
    }

    strategy = strategy_map.get(request.strategy_type, RoutingStrategy.COST_OPTIMIZED)

    # Get SmartRouter instance
    router_instance = get_smart_router(db=db)

    # Create org config
    org_config = OrgRoutingConfig(
        org_id="test_org",
        routing_strategy=strategy,
        primary_provider="openai",
        primary_model="gpt-4o-mini",
        backup_provider="anthropic",
        backup_model="claude-3-haiku"
    )

    # Create test request
    test_request = UniversalRequest(
        messages=[{"role": "user", "content": "Test message"}],
        tools=[],
        model="gpt-4",
        temperature=0.7,
        max_tokens=1000
    )

    # Get routing decision
    decision = await router_instance.route_request(test_request, org_config)

    # Get provider health for latency estimate
    health = router_instance.get_provider_health(decision.provider)
    estimated_latency = int(health.avg_latency_ms) if health and health.avg_latency_ms > 0 else 800

    # Estimate cost based on model
    cost_estimates = {
        "gpt-4o-mini": 0.15,
        "claude-3-haiku": 0.25,
        "gpt-4o": 2.50,
        "claude-3-sonnet": 3.00,
        "claude-3-opus": 15.00,
    }
    estimated_cost = cost_estimates.get(decision.model, 1.0)

    return TestRoutingResponse(
        selectedModel=decision.model,
        provider=decision.provider,
        estimatedCost=estimated_cost,
        estimatedLatency=estimated_latency,
        reason=decision.reason or "strategy_based_selection",
        strategy_used=strategy.value
    )


@router.get("/strategies")
async def list_strategies():
    """List all available routing strategies"""
    return {
        "strategies": [
            {
                "id": "cost_optimized",
                "name": "Cost Optimized",
                "description": "Minimize costs while meeting quality/latency thresholds"
            },
            {
                "id": "latency_optimized",
                "name": "Latency Optimized",
                "description": "Minimize response time"
            },
            {
                "id": "quality_first",
                "name": "Quality First",
                "description": "Maximize quality within cost limits"
            },
            {
                "id": "weighted_roundrobin",
                "name": "Weighted Round-Robin",
                "description": "Distribute load based on weights"
            },
            {
                "id": "auto",
                "name": "Auto (Use Routing Strategy)",
                "description": "Automatically select best strategy"
            }
        ]
    }


@router.get("/task-types")
async def list_task_types():
    """
    List all available task types and their model mappings.

    Task types allow intelligent model selection based on the nature of the task:
    - Classification tasks (cheap models): ticket_classification, sentiment_analysis
    - Generation tasks (quality models): response_generation, email_generation
    - Latency-critical tasks (fast models): autocomplete, quick_response

    Usage:
    - Set `task_type` in workflow node's data field
    - The routing resolver will automatically select the appropriate model
    """
    from backend.services.routing_integration import TASK_TYPE_MODEL_MAPPINGS

    task_types = []
    for task_type, config in TASK_TYPE_MODEL_MAPPINGS.items():
        task_types.append({
            "id": task_type,
            "description": config.description,
            "optimization": config.optimization,
            "primary_model": f"{config.primary_provider}/{config.primary_model}",
            "fallback_model": f"{config.fallback_provider}/{config.fallback_model}",
        })

    # Group by optimization type
    grouped = {
        "cost": [t for t in task_types if t["optimization"] == "cost"],
        "quality": [t for t in task_types if t["optimization"] == "quality"],
        "latency": [t for t in task_types if t["optimization"] == "latency"],
    }

    return {
        "task_types": task_types,
        "by_optimization": grouped,
        "usage": {
            "workflow_node": "Set `task_type` in node.data object",
            "api_call": "Pass `task_type` parameter to resolve_model_selection()",
            "example": {
                "node_data": {
                    "type": "worker",
                    "data": {
                        "label": "Classify Ticket",
                        "task_type": "ticket_classification",
                        "prompt": "Classify this ticket: {{input.message}}"
                    }
                }
            }
        }
    }


@router.post("/task-type/test")
async def test_task_type_routing(
    task_type: str = Query(..., description="Task type to test (e.g., 'ticket_classification')"),
    db: AsyncSession = Depends(get_db)
):
    """
    Test routing decision for a specific task type.

    Returns the model that would be selected for the given task type.
    """
    from backend.services.routing_integration import get_task_type_config, TASK_TYPE_MODEL_MAPPINGS

    config = get_task_type_config(task_type)
    if not config:
        available = list(TASK_TYPE_MODEL_MAPPINGS.keys())
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Unknown task type: {task_type}",
                "available_task_types": available
            }
        )

    # Estimate costs based on model
    cost_per_1k_tokens = {
        "gpt-4o-mini": 0.00015,
        "claude-3-haiku-20240307": 0.00025,
        "gpt-4o": 0.0025,
        "claude-3-5-sonnet-20241022": 0.003,
        "llama-3.3-70b-versatile": 0.00059,
    }

    primary_cost = cost_per_1k_tokens.get(config.primary_model, 0.001)
    fallback_cost = cost_per_1k_tokens.get(config.fallback_model, 0.001)

    return {
        "task_type": task_type,
        "description": config.description,
        "optimization": config.optimization,
        "routing_decision": {
            "provider": config.primary_provider,
            "model": config.primary_model,
            "reason": f"task_type_routing:{task_type}",
            "fallback_provider": config.fallback_provider,
            "fallback_model": config.fallback_model,
        },
        "estimated_cost_per_1k_tokens": {
            "primary": primary_cost,
            "fallback": fallback_cost,
        },
        "typical_use_cases": {
            "ticket_classification": "Categorize incoming support tickets",
            "sentiment_analysis": "Analyze customer sentiment",
            "response_generation": "Generate customer-facing responses",
            "code_generation": "Generate code snippets",
            "autocomplete": "Real-time text completion",
        }.get(task_type, config.description)
    }
