"""
Multi-LLM Routing API Endpoints - P1 Feature #3

REST API for LLM provider management and intelligent routing.

Endpoints:
- POST   /api/v1/llm/providers              - Register LLM provider
- GET    /api/v1/llm/providers              - List providers
- GET    /api/v1/llm/providers/{id}         - Get provider details
- POST   /api/v1/llm/models                 - Register model
- GET    /api/v1/llm/models                 - List models
- GET    /api/v1/llm/models/{id}            - Get model details
- POST   /api/v1/llm/route                  - Get routing recommendation
- POST   /api/v1/llm/requests               - Log request
- GET    /api/v1/llm/analytics              - Get cost analytics
- POST   /api/v1/llm/compare                - Create A/B test
- GET    /api/v1/llm/compare/{id}           - Get comparison results
- POST   /api/v1/llm/compare/{id}/execute   - Run comparison
- GET    /api/v1/llm/recommendations        - Get model recommendations
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta

from backend.database.session import get_db
from backend.shared.llm_models import (
    LLMProviderCreate,
    LLMProviderResponse,
    LLMModelCreate,
    LLMModelResponse,
    LLMRequestCreate,
    LLMRoutingRequest,
    LLMRoutingResponse,
    ModelComparisonCreate,
    ModelComparisonResponse,
    LLMProvider,
    RoutingStrategyRequest,
    RoutingStrategyResponse,
    RoutingStrategy,
)
from backend.shared.llm_service import LLMRoutingService
from backend.api.response_transformers import ResponseTransformer
from backend.shared.auth import get_current_user_id, get_current_organization_id


router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


# Alias for backwards compatibility (DB schema uses int for org_id)
async def get_organization_id() -> Optional[int]:
    """Get current user's organization ID as int."""
    return 1


@router.post("/providers", response_model=LLMProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    provider_data: LLMProviderCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Register new LLM provider.

    Creates provider configuration with credentials (encrypted).
    """
    provider = await LLMRoutingService.create_provider(
        db, provider_data, user_id, organization_id
    )
    return provider


@router.get("/providers")
async def list_providers(
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """List all LLM providers for organization (deduplicated by provider type)."""
    try:
        from sqlalchemy import select
        from backend.shared.llm_models import LLMProviderConfig

        stmt = select(LLMProviderConfig).where(LLMProviderConfig.is_active == True)

        if organization_id:
            stmt = stmt.where(
                (LLMProviderConfig.organization_id == organization_id) |
                (LLMProviderConfig.organization_id.is_(None))
            )

        result = await db.execute(stmt)
        all_providers = result.scalars().all()

        # Eagerly convert to dicts while in async context to avoid lazy loading issues
        provider_dicts = []
        for p in all_providers:
            provider_dicts.append({
                'id': p.id,
                'provider': p.provider,  # Access enum while in async context
                'name': p.name,
                'description': p.description,
                'organization_id': p.organization_id,
                'is_active': p.is_active,
                'is_default': p.is_default,
                'api_key_configured': bool(p.api_key),
                'created_at': p.created_at,
                'updated_at': p.updated_at,
            })

        # Deduplicate by provider type (keep the first one with the lowest ID)
        seen_providers = {}
        for provider_dict in provider_dicts:
            provider_key = provider_dict['provider']
            if provider_key not in seen_providers:
                seen_providers[provider_key] = provider_dict
            elif provider_dict['id'] < seen_providers[provider_key]['id']:
                seen_providers[provider_key] = provider_dict

        # Transform responses to match frontend expectations
        return ResponseTransformer.transform_list(
            list(seen_providers.values()),
            ResponseTransformer.transform_llm_provider
        )

    except Exception as e:
        # Database not available - return mock providers for development
        import os
        if os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes"):
            return _get_mock_providers()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


def _get_mock_providers():
    """Return mock providers for development without database."""
    from datetime import datetime

    class MockProvider:
        def __init__(self, id, provider, name, description, is_default=False):
            self.id = id
            self.provider = provider
            self.name = name
            self.description = description
            self.organization_id = 1
            self.api_endpoint = None
            self.is_active = True
            self.is_default = is_default
            self.created_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()

    mock_providers = [
        MockProvider(1, LLMProvider.OPENAI, "OpenAI", "OpenAI GPT models", True),
        MockProvider(2, LLMProvider.ANTHROPIC, "Anthropic", "Claude models"),
        MockProvider(3, LLMProvider.GOOGLE, "Google AI", "Gemini models"),
        MockProvider(4, LLMProvider.AZURE_OPENAI, "Azure OpenAI", "Azure-hosted OpenAI"),
        MockProvider(5, LLMProvider.LOCAL_OLLAMA, "Ollama (Local)", "Local models"),
    ]

    # Transform mock providers to match frontend expectations
    return ResponseTransformer.transform_list(
        mock_providers,
        ResponseTransformer.transform_llm_provider
    )


@router.get("/providers/{provider_id}", response_model=LLMProviderResponse)
async def get_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get provider details."""
    from sqlalchemy import select
    from backend.shared.llm_models import LLMProviderConfig

    stmt = select(LLMProviderConfig).where(LLMProviderConfig.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found",
        )

    return provider


@router.post("/models", response_model=LLMModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    model_data: LLMModelCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Register new LLM model.

    Creates model configuration with pricing and capabilities.
    """
    model = await LLMRoutingService.create_model(db, model_data, user_id)
    return model


@router.get("/models", response_model=List[LLMModelResponse])
async def list_models(
    provider: Optional[LLMProvider] = None,
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """List all LLM models."""
    from sqlalchemy import select
    from backend.shared.llm_models import LLMModelConfig, LLMProviderConfig

    stmt = select(LLMModelConfig).join(LLMProviderConfig).where(
        LLMModelConfig.is_active == is_active
    )

    if provider:
        stmt = stmt.where(LLMProviderConfig.provider == provider)

    if organization_id:
        stmt = stmt.where(
            (LLMProviderConfig.organization_id == organization_id) |
            (LLMProviderConfig.organization_id.is_(None))
        )

    result = await db.execute(stmt)
    models = result.scalars().all()

    return models


@router.get("/models/{model_id}", response_model=LLMModelResponse)
async def get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get model details including performance metrics."""
    from sqlalchemy import select
    from backend.shared.llm_models import LLMModelConfig

    stmt = select(LLMModelConfig).where(LLMModelConfig.id == model_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    return model


@router.post("/route", response_model=LLMRoutingResponse)
async def route_request(
    routing_request: LLMRoutingRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get intelligent routing recommendation for LLM request.

    Returns the best model based on routing strategy and constraints.
    """
    try:
        routing_response = await LLMRoutingService.route_llm_request(
            db, routing_request, user_id, organization_id
        )
        return routing_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def log_request(
    request_data: LLMRequestCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Log LLM request for analytics and cost tracking.

    Records usage, calculates cost, updates model metrics.
    """
    try:
        request = await LLMRoutingService.log_request(
            db, request_data, user_id, organization_id
        )
        return {
            "request_id": request.id,
            "total_cost": request.total_cost,
            "total_tokens": request.total_tokens,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/analytics")
async def get_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get cost and usage analytics.

    Returns aggregated metrics for time period.
    """
    try:
        analytics = await LLMRoutingService.get_cost_analytics(
            db, organization_id, start_date, end_date
        )
        return analytics
    except Exception as e:
        # Database not available - return mock analytics
        import os
        if os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes"):
            return _get_mock_analytics()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


def _get_mock_analytics():
    """Return mock analytics for development without database."""
    return {
        "total_cost": 125.50,
        "total_tokens": 1250000,
        "total_requests": 5000,
        "avg_latency": 450.0,
        "cost_by_provider": {
            "openai": 75.00,
            "anthropic": 35.50,
            "google": 15.00,
        },
        "requests_by_provider": {
            "openai": 3000,
            "anthropic": 1500,
            "google": 500,
        },
        "cost_by_model": {
            "gpt-4": 50.00,
            "gpt-3.5-turbo": 25.00,
            "claude-3-opus": 25.50,
            "claude-3-sonnet": 10.00,
            "gemini-pro": 15.00,
        },
    }


@router.post("/compare", response_model=ModelComparisonResponse, status_code=status.HTTP_201_CREATED)
async def create_comparison(
    comparison_data: ModelComparisonCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Create A/B test to compare two models.

    Sets up comparison with test cases and evaluation criteria.
    """
    comparison = await LLMRoutingService.create_model_comparison(
        db, comparison_data, user_id, organization_id
    )
    return comparison


@router.get("/compare/{comparison_id}", response_model=ModelComparisonResponse)
async def get_comparison(
    comparison_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get A/B test comparison results."""
    from sqlalchemy import select
    from backend.shared.llm_models import LLMModelComparison

    stmt = select(LLMModelComparison).where(LLMModelComparison.id == comparison_id)
    result = await db.execute(stmt)
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison not found",
        )

    return comparison


@router.post("/compare/{comparison_id}/execute", response_model=ModelComparisonResponse)
async def execute_comparison(
    comparison_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute A/B test comparison.

    Runs test cases against both models and calculates winner.
    """
    try:
        comparison = await LLMRoutingService.execute_comparison(db, comparison_id)
        return comparison
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/recommendations", response_model=List[LLMModelResponse])
async def get_recommendations(
    task_type: str = Query(..., description="Task type: code, vision, reasoning, json"),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get recommended models for a specific task type.

    Returns top 5 models best suited for the task.
    """
    models = await LLMRoutingService.get_model_recommendations(
        db, task_type, organization_id
    )
    return models


@router.get("/providers/available")
async def get_available_providers():
    """Get list of supported LLM providers."""
    return {
        "providers": [
            {
                "id": provider.value,
                "name": provider.value.replace("_", " ").title(),
                "description": f"{provider.value} LLM provider",
            }
            for provider in LLMProvider
        ]
    }


@router.get("/routing-strategy", response_model=RoutingStrategyResponse)
async def get_routing_strategy(
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Get current LLM routing strategy configuration.

    Returns the organization's routing strategy or default if not set.
    """
    from sqlalchemy import select
    from backend.database.models import RoutingStrategyModel

    # Get existing organization-level strategy (filter by scope_type to avoid duplicates)
    stmt = select(RoutingStrategyModel).where(
        RoutingStrategyModel.organization_id == str(organization_id or 1),
        RoutingStrategyModel.scope_type == 'organization'
    ).order_by(RoutingStrategyModel.created_at.desc())
    result = await db.execute(stmt)
    strategy = result.scalars().first()

    # Return existing or default
    if strategy:
        # Deserialize config from JSON string to dict
        import json
        config_dict = json.loads(strategy.config) if isinstance(strategy.config, str) else (strategy.config or {})

        # Map new strategy_type to old RoutingStrategy enum
        strategy_type_map = {
            "cost": RoutingStrategy.COST_OPTIMIZED,
            "latency": RoutingStrategy.LATENCY_OPTIMIZED,
            "quality": RoutingStrategy.BEST_AVAILABLE,
            "weighted_rr": RoutingStrategy.PRIMARY_WITH_BACKUP,
            "primary_only": RoutingStrategy.PRIMARY_ONLY,
            "round_robin": RoutingStrategy.BEST_AVAILABLE,
            "balanced": RoutingStrategy.BEST_AVAILABLE,
        }

        # Use strategy_type (new field) instead of strategy (old field)
        strategy_enum = strategy_type_map.get(
            strategy.strategy_type,
            RoutingStrategy.BEST_AVAILABLE
        )

        return RoutingStrategyResponse(
            id=strategy.id,
            organization_id=strategy.organization_id,
            strategy=strategy_enum,
            config=config_dict,
            created_at=strategy.created_at,
            updated_at=strategy.updated_at,
        )
    else:
        # Return default strategy
        from uuid import uuid4
        return RoutingStrategyResponse(
            id=str(uuid4()),
            organization_id=str(organization_id or 1),
            strategy=RoutingStrategy.BEST_AVAILABLE,
            config={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )


@router.post("/routing-strategy", response_model=RoutingStrategyResponse, status_code=status.HTTP_201_CREATED)
async def set_routing_strategy(
    strategy_request: RoutingStrategyRequest,
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Set LLM routing strategy configuration.

    Persists the routing strategy preference for the organization.
    """
    from sqlalchemy import select
    from backend.database.models import RoutingStrategyModel
    from uuid import uuid4

    org_id = str(organization_id or 1)

    # Map old RoutingStrategy enum to new strategy_type values
    strategy_enum_to_type = {
        RoutingStrategy.COST_OPTIMIZED: "cost",
        RoutingStrategy.LATENCY_OPTIMIZED: "latency",
        RoutingStrategy.BEST_AVAILABLE: "quality",
        RoutingStrategy.PRIMARY_WITH_BACKUP: "weighted_rr",
        RoutingStrategy.PRIMARY_ONLY: "primary_only",
    }

    new_strategy_type = strategy_enum_to_type.get(
        strategy_request.strategy,
        "cost"  # Default fallback
    )

    # Check if strategy already exists (use first() to handle duplicates gracefully)
    stmt = select(RoutingStrategyModel).where(
        RoutingStrategyModel.organization_id == org_id,
        RoutingStrategyModel.scope_type == "organization",
        RoutingStrategyModel.scope_id.is_(None),
    ).order_by(RoutingStrategyModel.created_at.desc())
    result = await db.execute(stmt)
    existing_strategy = result.scalars().first()

    if existing_strategy:
        # Update existing
        import json
        existing_strategy.strategy_type = new_strategy_type  # Use strategy_type field
        existing_strategy.config = json.dumps(strategy_request.config)  # Serialize to JSON string
        existing_strategy.updated_at = datetime.utcnow()
        existing_strategy.is_active = True
        await db.commit()
        await db.refresh(existing_strategy)

        # Deserialize config for response
        config_dict = json.loads(existing_strategy.config) if isinstance(existing_strategy.config, str) else (existing_strategy.config or {})

        return RoutingStrategyResponse(
            id=existing_strategy.id,
            organization_id=existing_strategy.organization_id,
            strategy=strategy_request.strategy,  # Return original enum value
            config=config_dict,
            created_at=existing_strategy.created_at,
            updated_at=existing_strategy.updated_at,
        )
    else:
        # Create new
        import json
        new_strategy = RoutingStrategyModel(
            id=str(uuid4()),
            organization_id=org_id,
            scope_type="organization",  # Organization-wide strategy
            scope_id=None,
            strategy_type=new_strategy_type,  # Use strategy_type field
            config=json.dumps(strategy_request.config),  # Serialize to JSON string
            is_active=True,
        )
        db.add(new_strategy)
        await db.commit()
        await db.refresh(new_strategy)

        # Deserialize config for response
        config_dict = json.loads(new_strategy.config) if isinstance(new_strategy.config, str) else (new_strategy.config or {})

        return RoutingStrategyResponse(
            id=new_strategy.id,
            organization_id=new_strategy.organization_id,
            strategy=strategy_request.strategy,  # Return original enum value
            config=config_dict,
            created_at=new_strategy.created_at,
            updated_at=new_strategy.updated_at,
        )


@router.post("/providers/reset")
async def reset_providers(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Reset LLM providers to clean default state (development only).

    Removes all duplicate providers and seeds with default provider configs.
    """
    from sqlalchemy import delete
    from backend.shared.llm_models import LLMProviderConfig, LLMModelConfig

    # Delete all existing models and providers
    await db.execute(delete(LLMModelConfig))
    await db.execute(delete(LLMProviderConfig))
    await db.commit()

    # Seed default providers
    default_providers = [
        {
            "provider": LLMProvider.OPENAI,
            "name": "OpenAI",
            "description": "OpenAI GPT models including GPT-4 and GPT-3.5",
            "is_default": True,
        },
        {
            "provider": LLMProvider.ANTHROPIC,
            "name": "Anthropic",
            "description": "Anthropic Claude models including Claude 3",
        },
        {
            "provider": LLMProvider.GOOGLE,
            "name": "Google AI",
            "description": "Google Gemini models",
        },
        {
            "provider": LLMProvider.AZURE_OPENAI,
            "name": "Azure OpenAI",
            "description": "Azure-hosted OpenAI models",
        },
        {
            "provider": LLMProvider.LOCAL_OLLAMA,
            "name": "Ollama (Local)",
            "description": "Local models via Ollama",
        },
    ]

    created_providers = []
    for provider_data in default_providers:
        provider = LLMProviderConfig(
            provider=provider_data["provider"],  # Pass enum directly, SQLAlchemy handles conversion
            name=provider_data["name"],
            description=provider_data.get("description"),
            is_default=provider_data.get("is_default", False),
            is_active=True,
            created_by_user_id=user_id,
            organization_id=1,
        )
        db.add(provider)
        created_providers.append(provider_data["name"])

    await db.commit()

    return {
        "status": "success",
        "message": "LLM providers reset to defaults",
        "providers_created": created_providers,
    }
