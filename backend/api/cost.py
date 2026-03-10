"""
Cost Management API

AI-powered cost tracking, forecasting, and budget management.
Addresses #2 production pain point: cost runaway ($10K+ surprise bills).
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field

from backend.database.session import get_db
from backend.shared.cost_service import get_cost_service
from backend.shared.cost_models import (
    CostCategory, CostEvent, CostSummary, CostForecast,
    CostAnomaly, Budget, BudgetStatus, BudgetAlert, BudgetPeriod,
    BudgetModel
)
from backend.shared.rbac_service import requires_permission, Permission, get_current_user, User
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEventType
from backend.shared.auth import verify_jwt_token
# ResponseTransformer import removed - frontend handles snake_case to camelCase conversion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cost", tags=["Cost Management"])


# Environment check for auth bypass in development
import os
_DEVELOPMENT_MODE = os.environ.get("ENVIRONMENT", "").lower() == "development"

async def get_authenticated_user(
    token_payload: dict = Depends(verify_jwt_token),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get authenticated user from JWT token.

    In development mode (ENVIRONMENT=development), falls back to mock user.
    In production, requires valid JWT token.
    """
    from backend.shared.rbac_models import User as RBACUser

    # Extract user info from JWT token
    user_id = token_payload.get("sub", "anonymous")
    email = token_payload.get("email", "")
    org_id = token_payload.get("org_id", token_payload.get("organization_id", "default"))
    roles = token_payload.get("roles", ["viewer"])

    return RBACUser(
        user_id=user_id,
        email=email,
        full_name=token_payload.get("name", email),
        organization_id=org_id,
        roles=roles if isinstance(roles, list) else [roles],
        permissions=set(),
        is_active=True,
        metadata=None
    )


# Request/Response Models

class CostEventRequest(BaseModel):
    """Cost event creation request"""
    organization_id: str
    category: str = Field(..., description="llm_inference, storage, compute, etc.")
    amount: float = Field(..., gt=0)
    currency: str = "USD"

    # Attribution
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    workflow_id: Optional[str] = None

    # Provider details (for LLM costs)
    provider: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    # Metadata
    metadata: dict = Field(default_factory=dict)


class CostEventResponse(BaseModel):
    """Cost event response"""
    event_id: str
    timestamp: datetime
    organization_id: str
    category: str
    amount: float
    currency: str

    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    workflow_id: Optional[str] = None

    provider: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class CostSummaryResponse(BaseModel):
    """Cost summary response"""
    organization_id: str
    start_time: datetime
    end_time: datetime

    total_cost: float
    event_count: int
    avg_cost_per_event: float

    category_breakdown: dict[str, float]
    provider_breakdown: dict[str, float]
    model_breakdown: dict[str, float]

    top_agents: List[tuple[str, float]]
    top_workflows: List[tuple[str, float]]
    top_users: List[tuple[str, float]]

    vs_previous_period_percent: Optional[float] = None


class ForecastResponse(BaseModel):
    """Cost forecast response"""
    forecast_id: str
    organization_id: str
    forecast_date: datetime

    forecast_period_start: datetime
    forecast_period_end: datetime

    predicted_cost: float
    confidence_lower: float
    confidence_upper: float
    confidence_interval: float

    trend: str
    anomalies_detected: List[dict]


class BudgetRequest(BaseModel):
    """Budget creation/update request"""
    organization_id: str
    name: str
    period: str = Field(..., description="daily, weekly, monthly, quarterly, yearly")
    amount: float = Field(..., gt=0)
    currency: str = "USD"

    # Scope
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None

    # Alert thresholds (percentages)
    alert_threshold_info: float = 50.0
    alert_threshold_warning: float = 75.0
    alert_threshold_critical: float = 90.0

    # Actions
    auto_disable_on_exceeded: bool = False


class BudgetUpdateRequest(BaseModel):
    """Budget update request - all fields optional for partial updates"""
    name: Optional[str] = None
    period: Optional[str] = Field(None, description="daily, weekly, monthly, quarterly, yearly")
    amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = None

    # Scope
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None

    # Alert thresholds (percentages)
    alert_threshold_info: Optional[float] = None
    alert_threshold_warning: Optional[float] = None
    alert_threshold_critical: Optional[float] = None

    # Actions
    auto_disable_on_exceeded: Optional[bool] = None

    # Status
    is_active: Optional[bool] = None


class BudgetResponse(BaseModel):
    """Budget response"""
    budget_id: str
    organization_id: str
    name: str
    period: str
    amount: float
    currency: str

    scope_type: Optional[str] = None
    scope_id: Optional[str] = None

    alert_threshold_info: float
    alert_threshold_warning: float
    alert_threshold_critical: float
    auto_disable_on_exceeded: bool

    is_active: bool
    created_at: datetime
    updated_at: datetime


class BudgetStatusResponse(BaseModel):
    """Budget status response"""
    budget_id: str
    name: str
    amount: float

    current_period_start: datetime
    current_period_end: datetime

    spent: float
    remaining: float
    percent_used: float

    status: str
    alerts: List[dict]


class AnomalyResponse(BaseModel):
    """Cost anomaly response"""
    timestamp: datetime
    expected_cost: float
    actual_cost: float
    deviation_percent: float
    severity: str
    potential_causes: List[str]


# Cost Event Tracking

@router.post("/events", response_model=CostEventResponse, status_code=status.HTTP_201_CREATED)
@requires_permission(Permission.COST_UPDATE)
async def log_cost_event(
    request: CostEventRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Log a cost event.

    Automatically tracks costs for billing, forecasting, and anomaly detection.
    """
    cost_service = get_cost_service()

    # Create cost event
    event = CostEvent(
        organization_id=request.organization_id,
        category=CostCategory(request.category),
        amount=request.amount,
        currency=request.currency,
        user_id=request.user_id,
        agent_id=UUID(request.agent_id) if request.agent_id else None,
        task_id=UUID(request.task_id) if request.task_id else None,
        workflow_id=UUID(request.workflow_id) if request.workflow_id else None,
        provider=request.provider,
        model=request.model,
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens,
        metadata=request.metadata
    )

    event_id = await cost_service.log_cost_event(event, db)

    return CostEventResponse(
        event_id=str(event_id),
        timestamp=datetime.utcnow(),
        organization_id=event.organization_id,
        category=event.category.value,
        amount=event.amount,
        currency=event.currency,
        user_id=event.user_id,
        agent_id=str(event.agent_id) if event.agent_id else None,
        task_id=str(event.task_id) if event.task_id else None,
        workflow_id=str(event.workflow_id) if event.workflow_id else None,
        provider=event.provider,
        model=event.model,
        input_tokens=event.input_tokens,
        output_tokens=event.output_tokens
    )


@router.get("/events", response_model=List[CostEventResponse])
@requires_permission(Permission.COST_READ)
async def query_cost_events(
    organization_id: str = Query(...),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    category: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """Query cost events with filters"""
    # Implementation would query cost_events table
    # For now, return empty list
    return []


# Cost Summary and Analytics

@router.get("/summary", response_model=CostSummaryResponse)
@requires_permission(Permission.COST_READ)
async def get_cost_summary(
    organization_id: str = Query(...),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cost summary with breakdowns.

    Provides:
    - Total cost and event count
    - Category/provider/model breakdown
    - Top agents/workflows/users by cost
    - Trend vs previous period
    """
    cost_service = get_cost_service()

    if not start_time:
        start_time = datetime.utcnow() - timedelta(days=30)
    if not end_time:
        end_time = datetime.utcnow()

    summary = await cost_service.get_cost_summary(
        organization_id=organization_id,
        start_time=start_time,
        end_time=end_time,
        db=db
    )

    backend_response = CostSummaryResponse(
        organization_id=organization_id,
        start_time=start_time,
        end_time=end_time,
        total_cost=summary.total_cost,
        event_count=summary.event_count,
        avg_cost_per_event=summary.avg_cost_per_event,
        category_breakdown=summary.category_breakdown,
        provider_breakdown=summary.provider_breakdown,
        model_breakdown=summary.model_breakdown,
        top_agents=summary.top_agents,
        top_workflows=summary.top_workflows,
        top_users=summary.top_users,
        vs_previous_period_percent=summary.vs_previous_period_percent
    )

    # Return the Pydantic response model directly
    # Frontend api.ts will handle transformation from snake_case to camelCase
    return backend_response


# Cost Forecasting

@router.get("/forecast", response_model=ForecastResponse)
@requires_permission(Permission.COST_READ)
async def forecast_cost(
    organization_id: str = Query(...),
    forecast_days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    AI-powered cost forecasting.

    Uses linear regression (upgradable to Prophet/ARIMA) to predict:
    - Future costs with 95% confidence intervals
    - Cost trend (increasing/decreasing/stable)
    - Anomalies in historical data
    """
    cost_service = get_cost_service()

    forecast = await cost_service.forecast_cost(
        organization_id=organization_id,
        forecast_days=forecast_days,
        db=db
    )

    return ForecastResponse(
        forecast_id=str(uuid4()),  # Generate ID for this forecast response
        organization_id=organization_id,
        forecast_date=datetime.utcnow(),
        forecast_period_start=datetime.combine(forecast.forecast_period_start, datetime.min.time()),
        forecast_period_end=datetime.combine(forecast.forecast_period_end, datetime.min.time()),
        predicted_cost=forecast.predicted_cost,
        confidence_lower=forecast.confidence_lower,
        confidence_upper=forecast.confidence_upper,
        confidence_interval=forecast.confidence_interval,
        trend=forecast.trend,
        anomalies_detected=[
            {
                "timestamp": anomaly.timestamp.isoformat(),
                "expected_cost": anomaly.expected_cost,
                "actual_cost": anomaly.actual_cost,
                "deviation_percent": anomaly.deviation_percent,
                "severity": anomaly.severity
            }
            for anomaly in forecast.anomalies_detected
        ]
    )


@router.get("/anomalies", response_model=List[AnomalyResponse])
@requires_permission(Permission.COST_READ)
async def detect_cost_anomalies(
    organization_id: str = Query(...),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Detect cost anomalies using 2σ threshold.

    Identifies:
    - Sudden cost spikes (>2 std deviations)
    - Potential causes (agent activity, batch jobs, etc.)
    - Severity levels (low, medium, high)
    """
    cost_service = get_cost_service()

    if not start_time:
        start_time = datetime.utcnow() - timedelta(days=7)
    if not end_time:
        end_time = datetime.utcnow()

    anomalies = await cost_service.detect_anomalies(
        organization_id=organization_id,
        start_time=start_time,
        end_time=end_time,
        db=db
    )

    return [
        AnomalyResponse(
            timestamp=anomaly.timestamp,
            expected_cost=anomaly.expected_cost,
            actual_cost=anomaly.actual_cost,
            deviation_percent=anomaly.deviation_percent,
            severity=anomaly.severity,
            potential_causes=anomaly.potential_causes
        )
        for anomaly in anomalies
    ]


# Budget Management

@router.post("/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
@requires_permission(Permission.COST_LIMIT_SET)
async def create_budget(
    request: BudgetRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create budget with 4-tier alerting.

    Alert levels:
    - INFO (50%): Heads up, half budget used
    - WARNING (75%): Budget alert, 3/4 spent
    - CRITICAL (90%): Only 10% left
    - EXCEEDED (100%): Take action, budget exceeded
    """
    cost_service = get_cost_service()

    # Convert period string to enum
    try:
        budget_period = BudgetPeriod(request.period)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period: {request.period}. Must be one of: {[p.value for p in BudgetPeriod]}"
        )

    budget = Budget(
        organization_id=request.organization_id,
        name=request.name,
        period=budget_period,
        amount=request.amount,
        currency=request.currency,
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        alert_threshold_info=request.alert_threshold_info,
        alert_threshold_warning=request.alert_threshold_warning,
        alert_threshold_critical=request.alert_threshold_critical,
        auto_disable_on_exceeded=request.auto_disable_on_exceeded
    )

    budget_id = await cost_service.create_budget(budget, db)

    # Audit log
    audit_logger = get_audit_logger()
    await audit_logger.log_resource_event(
        event_type=AuditEventType.CONFIG_UPDATED,
        action="create",
        resource_type="budget",
        resource_id=str(budget_id),
        description=f"Budget created: {request.name} (${request.amount}/{request.period})",
        db=db
    )

    return BudgetResponse(
        budget_id=str(budget_id),
        organization_id=budget.organization_id,
        name=budget.name,
        period=budget.period.value if hasattr(budget.period, 'value') else budget.period,
        amount=budget.amount,
        currency=budget.currency,
        scope_type=budget.scope_type,
        scope_id=budget.scope_id,
        alert_threshold_info=budget.alert_threshold_info,
        alert_threshold_warning=budget.alert_threshold_warning,
        alert_threshold_critical=budget.alert_threshold_critical,
        auto_disable_on_exceeded=budget.auto_disable_on_exceeded,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@router.get("/budgets", response_model=List[BudgetResponse])
@requires_permission(Permission.COST_READ)
async def list_budgets(
    organization_id: str = Query(...),
    is_active: Optional[bool] = Query(None),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """List budgets for organization"""
    # Build query filters
    filters = [BudgetModel.organization_id == organization_id]
    if is_active is not None:
        filters.append(BudgetModel.is_active == is_active)

    # Query database
    stmt = select(BudgetModel).where(and_(*filters)).order_by(BudgetModel.created_at.desc())
    result = await db.execute(stmt)
    budgets = result.scalars().all()

    # Convert to response model
    return [
        BudgetResponse(
            budget_id=str(budget.budget_id),
            organization_id=budget.organization_id,
            name=budget.name,
            period=budget.period,
            amount=budget.amount,
            currency=budget.currency,
            scope_type=budget.scope_type,
            scope_id=budget.scope_id,
            alert_threshold_info=budget.alert_threshold_info,
            alert_threshold_warning=budget.alert_threshold_warning,
            alert_threshold_critical=budget.alert_threshold_critical,
            auto_disable_on_exceeded=budget.auto_disable_on_exceeded,
            is_active=budget.is_active,
            created_at=budget.created_at,
            updated_at=budget.updated_at
        )
        for budget in budgets
    ]


@router.get("/budgets/{budget_id}/status", response_model=BudgetStatusResponse)
@requires_permission(Permission.COST_READ)
async def get_budget_status(
    budget_id: str,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get budget status with current spending.

    Shows:
    - Spent vs budget
    - Remaining amount
    - Percent used
    - Active alerts
    """
    cost_service = get_cost_service()

    try:
        budget_uuid = UUID(budget_id)
        status = await cost_service.get_budget_status(budget_uuid, db)

        return BudgetStatusResponse(
            budget_id=budget_id,
            name=status.budget_name,
            amount=status.budget_amount,
            current_period_start=status.period_start,
            current_period_end=status.period_end,
            spent=status.spent,
            remaining=status.remaining,
            percent_used=status.percent_used,
            status=status.status.value,
            alerts=[
                {
                    "level": alert.level.value,
                    "threshold": alert.threshold,
                    "message": alert.message,
                    "created_at": alert.created_at.isoformat()
                }
                for alert in status.alerts
            ]
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget not found: {budget_id}"
        )


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
@requires_permission(Permission.COST_LIMIT_SET)
async def delete_budget(
    budget_id: str,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a budget.

    Permanently removes the budget configuration.
    """
    try:
        budget_uuid = UUID(budget_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid budget ID format: {budget_id}"
        )

    # Check if budget exists
    stmt = select(BudgetModel).where(BudgetModel.budget_id == budget_uuid)
    result = await db.execute(stmt)
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget not found: {budget_id}"
        )

    # Delete the budget
    await db.delete(budget)
    await db.commit()

    # Audit log
    audit_logger = get_audit_logger()
    await audit_logger.log_resource_event(
        event_type=AuditEventType.CONFIG_UPDATED,
        action="delete",
        resource_type="budget",
        resource_id=str(budget_id),
        description=f"Budget deleted: {budget.name}",
        db=db
    )

    return None


@router.patch("/budgets/{budget_id}", response_model=BudgetResponse)
@requires_permission(Permission.COST_LIMIT_SET)
async def update_budget(
    budget_id: str,
    request: BudgetUpdateRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a budget.

    Supports partial updates - only provided fields will be updated.
    """
    try:
        budget_uuid = UUID(budget_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid budget ID format: {budget_id}"
        )

    # Find the budget
    stmt = select(BudgetModel).where(BudgetModel.budget_id == budget_uuid)
    result = await db.execute(stmt)
    budget = result.scalar_one_or_none()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget not found: {budget_id}"
        )

    # Track changes for audit log
    changes = []

    # Update fields if provided
    if request.name is not None and request.name != budget.name:
        changes.append(f"name: {budget.name} -> {request.name}")
        budget.name = request.name

    if request.period is not None:
        try:
            new_period = BudgetPeriod(request.period.lower())
            # Handle both string and enum comparison
            current_period_value = budget.period.value if isinstance(budget.period, BudgetPeriod) else budget.period
            if new_period.value != current_period_value:
                changes.append(f"period: {current_period_value} -> {new_period.value}")
                # Assign string value, not enum - asyncpg expects string for VARCHAR column
                budget.period = new_period.value
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid period: {request.period}. Must be one of: daily, weekly, monthly, quarterly, yearly"
            )

    if request.amount is not None and request.amount != budget.amount:
        changes.append(f"amount: {budget.amount} -> {request.amount}")
        budget.amount = request.amount

    if request.currency is not None and request.currency != budget.currency:
        changes.append(f"currency: {budget.currency} -> {request.currency}")
        budget.currency = request.currency

    if request.scope_type is not None and request.scope_type != budget.scope_type:
        changes.append(f"scope_type: {budget.scope_type} -> {request.scope_type}")
        budget.scope_type = request.scope_type

    if request.scope_id is not None and request.scope_id != budget.scope_id:
        changes.append(f"scope_id: {budget.scope_id} -> {request.scope_id}")
        budget.scope_id = request.scope_id

    if request.alert_threshold_info is not None and request.alert_threshold_info != budget.alert_threshold_info:
        changes.append(f"alert_threshold_info: {budget.alert_threshold_info} -> {request.alert_threshold_info}")
        budget.alert_threshold_info = request.alert_threshold_info

    if request.alert_threshold_warning is not None and request.alert_threshold_warning != budget.alert_threshold_warning:
        changes.append(f"alert_threshold_warning: {budget.alert_threshold_warning} -> {request.alert_threshold_warning}")
        budget.alert_threshold_warning = request.alert_threshold_warning

    if request.alert_threshold_critical is not None and request.alert_threshold_critical != budget.alert_threshold_critical:
        changes.append(f"alert_threshold_critical: {budget.alert_threshold_critical} -> {request.alert_threshold_critical}")
        budget.alert_threshold_critical = request.alert_threshold_critical

    if request.auto_disable_on_exceeded is not None and request.auto_disable_on_exceeded != budget.auto_disable_on_exceeded:
        changes.append(f"auto_disable_on_exceeded: {budget.auto_disable_on_exceeded} -> {request.auto_disable_on_exceeded}")
        budget.auto_disable_on_exceeded = request.auto_disable_on_exceeded

    if request.is_active is not None and request.is_active != budget.is_active:
        changes.append(f"is_active: {budget.is_active} -> {request.is_active}")
        budget.is_active = request.is_active

    # Update timestamp
    budget.updated_at = datetime.utcnow()

    # Commit changes
    await db.commit()
    await db.refresh(budget)

    # Audit log if there were changes
    if changes:
        audit_logger = get_audit_logger()
        await audit_logger.log_resource_event(
            event_type=AuditEventType.CONFIG_UPDATED,
            action="update",
            resource_type="budget",
            resource_id=str(budget_id),
            description=f"Budget updated: {budget.name}. Changes: {', '.join(changes)}",
            db=db
        )

    return BudgetResponse(
        budget_id=str(budget.budget_id),
        organization_id=budget.organization_id,
        name=budget.name,
        period=budget.period.value if isinstance(budget.period, BudgetPeriod) else budget.period,
        amount=budget.amount,
        currency=budget.currency,
        scope_type=budget.scope_type,
        scope_id=budget.scope_id,
        alert_threshold_info=budget.alert_threshold_info,
        alert_threshold_warning=budget.alert_threshold_warning,
        alert_threshold_critical=budget.alert_threshold_critical,
        auto_disable_on_exceeded=budget.auto_disable_on_exceeded,
        is_active=budget.is_active,
        created_at=budget.created_at,
        updated_at=budget.updated_at
    )


# Provider and Category Information

@router.get("/categories")
async def list_cost_categories():
    """List available cost categories"""
    return {
        "categories": [
            {
                "id": "llm_inference",
                "name": "LLM Inference",
                "description": "Language model API calls"
            },
            {
                "id": "llm_embedding",
                "name": "LLM Embeddings",
                "description": "Text embedding generation"
            },
            {
                "id": "storage",
                "name": "Storage",
                "description": "Data storage costs"
            },
            {
                "id": "compute",
                "name": "Compute",
                "description": "Compute resources"
            },
            {
                "id": "data_transfer",
                "name": "Data Transfer",
                "description": "Network bandwidth"
            },
            {
                "id": "external_api",
                "name": "External APIs",
                "description": "Third-party API calls"
            }
        ]
    }


@router.get("/providers")
async def list_providers():
    """List supported LLM providers and models"""
    return {
        "providers": [
            {
                "id": "openai",
                "name": "OpenAI",
                "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
            },
            {
                "id": "anthropic",
                "name": "Anthropic",
                "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
            },
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "models": ["deepseek-v3", "deepseek-r1"]
            }
        ]
    }
