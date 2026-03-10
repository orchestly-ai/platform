"""
LLM Billing API Routes

Endpoints for managing customer LLM configuration, billing, and usage.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field

from backend.services.llm_billing_service import (
    LLMBillingService,
    get_llm_billing_service,
    BillingModel,
    LLMProvider,
    CustomerLLMConfig,
    LLM_PRICING,
)


router = APIRouter(prefix="/api/v1/llm-billing", tags=["LLM Billing"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateCustomerConfigRequest(BaseModel):
    """Request to create customer LLM configuration."""
    customer_id: str = Field(..., description="Unique customer identifier")
    billing_model: str = Field(..., description="byok, managed, prepaid, or enterprise")
    markup_percentage: float = Field(default=15.0, description="Markup for managed model")
    daily_limit_usd: Optional[float] = Field(None, description="Daily spending limit")
    monthly_limit_usd: Optional[float] = Field(None, description="Monthly spending limit")
    allowed_models: List[str] = Field(default=[], description="Allowed LLM models")
    blocked_models: List[str] = Field(default=[], description="Blocked LLM models")


class SetBYOKKeyRequest(BaseModel):
    """Request to set a BYOK API key."""
    provider: str = Field(..., description="openai, anthropic, google, etc.")
    api_key: str = Field(..., description="The customer's API key")
    key_name: Optional[str] = Field(None, description="Friendly name for the key")
    expires_at: Optional[str] = Field(None, description="Expiration date (ISO format)")
    reminder_days_before: int = Field(default=7, description="Days before expiration to send reminder")


class UpdateBYOKKeyMetadataRequest(BaseModel):
    """Request to update BYOK key metadata (without changing the key)."""
    key_name: Optional[str] = Field(None, description="Friendly name for the key")
    expires_at: Optional[str] = Field(None, description="Expiration date (ISO format)")
    reminder_days_before: Optional[int] = Field(None, description="Days before expiration to send reminder")


class AddCreditsRequest(BaseModel):
    """Request to add prepaid credits."""
    amount_usd: float = Field(..., gt=0, description="Amount to add in USD")
    payment_reference: Optional[str] = Field(None, description="Payment reference/ID")


class RecordUsageRequest(BaseModel):
    """Request to record LLM usage."""
    provider: str = Field(..., description="LLM provider")
    model: str = Field(..., description="Model name")
    input_tokens: int = Field(..., ge=0, description="Input tokens used")
    output_tokens: int = Field(..., ge=0, description="Output tokens used")
    agent_name: Optional[str] = Field(None, description="Agent that made the call")
    session_id: Optional[str] = Field(None, description="Session ID")
    ticket_id: Optional[str] = Field(None, description="Ticket ID")
    latency_ms: Optional[int] = Field(None, description="Request latency in ms")


class BYOKKeyMetadataResponse(BaseModel):
    """Metadata for a BYOK API key."""
    provider: str
    is_valid: Optional[bool] = None
    last_validated_at: Optional[str] = None
    validation_error: Optional[str] = None
    expires_at: Optional[str] = None
    reminder_days_before: int = 7
    created_at: str
    updated_at: str
    key_name: Optional[str] = None
    key_prefix: Optional[str] = None
    needs_renewal: bool = False
    days_until_expiry: Optional[int] = None


class CustomerConfigResponse(BaseModel):
    """Response with customer configuration."""
    customer_id: str
    billing_model: str
    managed_providers: List[str]
    markup_percentage: float
    prepaid_balance_usd: Optional[float]
    daily_limit_usd: Optional[float]
    monthly_limit_usd: Optional[float]
    allowed_models: List[str]
    blocked_models: List[str]
    has_byok_keys: Dict[str, bool]
    byok_key_metadata: Dict[str, BYOKKeyMetadataResponse] = {}  # Full metadata for each key
    created_at: str
    updated_at: str


class UsageSummaryResponse(BaseModel):
    """Response with usage summary."""
    customer_id: str
    period_start: str
    period_end: str
    total_requests: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    raw_cost_usd: float
    markup_usd: float
    total_cost_usd: float
    by_provider: Dict[str, Any]
    by_model: Dict[str, Any]
    by_agent: Dict[str, Any]


class CostEstimateRequest(BaseModel):
    """Request for cost estimation."""
    provider: str = Field(..., description="LLM provider")
    model: str = Field(..., description="Model name")
    daily_requests: int = Field(..., gt=0, description="Expected daily requests")
    avg_input_tokens: int = Field(default=500, description="Average input tokens per request")
    avg_output_tokens: int = Field(default=200, description="Average output tokens per request")


class CostEstimateResponse(BaseModel):
    """Response with cost estimation."""
    provider: str
    model: str
    per_request_usd: float
    daily_estimate_usd: float
    monthly_estimate_usd: float
    raw_cost_monthly_usd: float
    markup_monthly_usd: float
    billing_model: str


# =============================================================================
# Dependency
# =============================================================================

def get_billing_service() -> LLMBillingService:
    """Dependency to get billing service."""
    return get_llm_billing_service()


# =============================================================================
# Configuration Endpoints
# =============================================================================

@router.post("/customers", response_model=CustomerConfigResponse)
async def create_customer_config(
    request: CreateCustomerConfigRequest,
    service: LLMBillingService = Depends(get_billing_service)
):
    """
    Create a new customer LLM configuration.

    Billing models:
    - **byok**: Customer brings their own API keys (zero LLM cost to us)
    - **managed**: We manage keys, charge usage + markup
    - **prepaid**: Customer buys credits upfront
    - **enterprise**: Custom agreement
    """
    try:
        billing_model = BillingModel(request.billing_model)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid billing model: {request.billing_model}. "
                   f"Valid options: {[m.value for m in BillingModel]}"
        )

    config = await service.create_customer_config(
        customer_id=request.customer_id,
        billing_model=billing_model,
        markup_percentage=request.markup_percentage,
        daily_limit_usd=Decimal(str(request.daily_limit_usd)) if request.daily_limit_usd else None,
        monthly_limit_usd=Decimal(str(request.monthly_limit_usd)) if request.monthly_limit_usd else None,
        allowed_models=request.allowed_models,
        blocked_models=request.blocked_models,
    )

    return _config_to_response(config, service)


@router.get("/customers/{customer_id}", response_model=CustomerConfigResponse)
async def get_customer_config(
    customer_id: str,
    service: LLMBillingService = Depends(get_billing_service)
):
    """Get customer's LLM configuration."""
    config = await service.get_customer_config(customer_id)
    if not config:
        raise HTTPException(status_code=404, detail="Customer not found")

    return _config_to_response(config, service)


@router.patch("/customers/{customer_id}", response_model=CustomerConfigResponse)
async def update_customer_config(
    customer_id: str,
    updates: Dict[str, Any] = Body(...),
    service: LLMBillingService = Depends(get_billing_service)
):
    """Update customer's LLM configuration."""
    # Convert decimal fields
    if "daily_limit_usd" in updates and updates["daily_limit_usd"]:
        updates["daily_limit_usd"] = Decimal(str(updates["daily_limit_usd"]))
    if "monthly_limit_usd" in updates and updates["monthly_limit_usd"]:
        updates["monthly_limit_usd"] = Decimal(str(updates["monthly_limit_usd"]))

    config = await service.update_customer_config(customer_id, **updates)
    if not config:
        raise HTTPException(status_code=404, detail="Customer not found")

    return _config_to_response(config, service)


def _config_to_response(config: CustomerLLMConfig, service: LLMBillingService) -> CustomerConfigResponse:
    """Convert config to response model."""
    # Check which BYOK keys exist
    has_byok_keys = {}
    for provider in LLMProvider:
        has_byok_keys[provider.value] = provider in config.byok_keys

    # Get full metadata for each key
    byok_key_metadata = {}
    for provider, metadata in config.byok_key_metadata.items():
        byok_key_metadata[provider.value] = BYOKKeyMetadataResponse(
            provider=metadata.provider.value,
            is_valid=metadata.is_valid,
            last_validated_at=metadata.last_validated_at.isoformat() if metadata.last_validated_at else None,
            validation_error=metadata.validation_error,
            expires_at=metadata.expires_at.isoformat() if metadata.expires_at else None,
            reminder_days_before=metadata.reminder_days_before,
            created_at=metadata.created_at.isoformat(),
            updated_at=metadata.updated_at.isoformat(),
            key_name=metadata.key_name,
            key_prefix=metadata.key_prefix,
            needs_renewal=metadata.needs_renewal_reminder(),
            days_until_expiry=(metadata.expires_at - datetime.utcnow()).days if metadata.expires_at else None,
        )

    return CustomerConfigResponse(
        customer_id=config.customer_id,
        billing_model=config.billing_model.value,
        managed_providers=[p.value for p in config.managed_providers],
        markup_percentage=config.markup_percentage,
        prepaid_balance_usd=float(config.prepaid_balance_usd) if config.billing_model == BillingModel.PREPAID else None,
        daily_limit_usd=float(config.daily_limit_usd) if config.daily_limit_usd else None,
        monthly_limit_usd=float(config.monthly_limit_usd) if config.monthly_limit_usd else None,
        allowed_models=config.allowed_models,
        blocked_models=config.blocked_models,
        has_byok_keys=has_byok_keys,
        byok_key_metadata=byok_key_metadata,
        created_at=config.created_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


# =============================================================================
# BYOK Key Management Endpoints
# =============================================================================

@router.post("/customers/{customer_id}/byok-keys")
async def set_byok_key(
    customer_id: str,
    request: SetBYOKKeyRequest,
    service: LLMBillingService = Depends(get_billing_service)
):
    """
    Set a BYOK (Bring Your Own Key) API key for a customer.

    The key is encrypted before storage. Optionally set expiration date
    for renewal reminders.
    """
    try:
        provider = LLMProvider(request.provider)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {request.provider}. "
                   f"Valid options: {[p.value for p in LLMProvider]}"
        )

    # Parse expiration date if provided
    expires_at = None
    if request.expires_at:
        try:
            expires_at = datetime.fromisoformat(request.expires_at.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid expires_at format. Use ISO format.")

    success = await service.set_byok_key(
        customer_id,
        provider,
        request.api_key,
        key_name=request.key_name,
        expires_at=expires_at,
        reminder_days_before=request.reminder_days_before,
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to set BYOK key. Ensure customer exists and is on BYOK plan."
        )

    return {
        "status": "success",
        "message": f"BYOK key set for provider {request.provider}",
        "provider": request.provider,
    }


@router.patch("/customers/{customer_id}/byok-keys/{provider}/metadata")
async def update_byok_key_metadata(
    customer_id: str,
    provider: str,
    request: UpdateBYOKKeyMetadataRequest,
    service: LLMBillingService = Depends(get_billing_service)
):
    """
    Update BYOK key metadata (expiration, name) without changing the key itself.
    """
    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    metadata = service.get_byok_key_metadata(customer_id, llm_provider)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"No BYOK key found for {provider}")

    # Update metadata fields
    if request.key_name is not None:
        metadata.key_name = request.key_name
    if request.reminder_days_before is not None:
        metadata.reminder_days_before = request.reminder_days_before
    if request.expires_at is not None:
        try:
            metadata.expires_at = datetime.fromisoformat(request.expires_at.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid expires_at format. Use ISO format.")
    metadata.updated_at = datetime.utcnow()

    return {
        "status": "success",
        "message": f"Metadata updated for {provider}",
        "metadata": metadata.to_dict(),
    }


@router.post("/customers/{customer_id}/byok-keys/{provider}/validate")
async def validate_byok_key(
    customer_id: str,
    provider: str,
    service: LLMBillingService = Depends(get_billing_service)
):
    """
    Validate that a BYOK key is working.

    The validation result is persisted and returned with the customer config.
    """
    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    is_valid, error = await service.validate_byok_key(customer_id, llm_provider)

    # Get updated metadata to return
    metadata = service.get_byok_key_metadata(customer_id, llm_provider)

    return {
        "provider": provider,
        "is_valid": is_valid,
        "error": error,
        "last_validated_at": metadata.last_validated_at.isoformat() if metadata and metadata.last_validated_at else None,
    }


@router.delete("/customers/{customer_id}/byok-keys/{provider}")
async def delete_byok_key(
    customer_id: str,
    provider: str,
    service: LLMBillingService = Depends(get_billing_service)
):
    """Delete a BYOK API key."""
    config = await service.get_customer_config(customer_id)
    if not config:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    if llm_provider in config.byok_keys:
        del config.byok_keys[llm_provider]
        return {"status": "deleted", "provider": provider}

    raise HTTPException(status_code=404, detail=f"No BYOK key found for {provider}")


# =============================================================================
# Prepaid Credits Endpoints
# =============================================================================

@router.post("/customers/{customer_id}/credits")
async def add_prepaid_credits(
    customer_id: str,
    request: AddCreditsRequest,
    service: LLMBillingService = Depends(get_billing_service)
):
    """Add prepaid credits to a customer's account."""
    try:
        new_balance = await service.add_prepaid_credits(
            customer_id,
            Decimal(str(request.amount_usd)),
            request.payment_reference
        )
        return {
            "status": "success",
            "amount_added_usd": request.amount_usd,
            "new_balance_usd": float(new_balance),
            "payment_reference": request.payment_reference,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/customers/{customer_id}/credits")
async def get_prepaid_balance(
    customer_id: str,
    service: LLMBillingService = Depends(get_billing_service)
):
    """Get prepaid credit balance."""
    config = await service.get_customer_config(customer_id)
    if not config:
        raise HTTPException(status_code=404, detail="Customer not found")

    if config.billing_model != BillingModel.PREPAID:
        raise HTTPException(
            status_code=400,
            detail="Customer is not on prepaid billing model"
        )

    return {
        "customer_id": customer_id,
        "balance_usd": float(config.prepaid_balance_usd),
        "auto_recharge_threshold": float(config.auto_recharge_threshold) if config.auto_recharge_threshold else None,
        "auto_recharge_amount": float(config.auto_recharge_amount) if config.auto_recharge_amount else None,
    }


# =============================================================================
# Usage Tracking Endpoints
# =============================================================================

@router.post("/customers/{customer_id}/usage")
async def record_usage(
    customer_id: str,
    request: RecordUsageRequest,
    service: LLMBillingService = Depends(get_billing_service)
):
    """Record LLM usage for billing."""
    try:
        provider = LLMProvider(request.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")

    try:
        record = await service.record_request_usage(
            customer_id=customer_id,
            provider=provider,
            model=request.model,
            input_tokens=request.input_tokens,
            output_tokens=request.output_tokens,
            agent_name=request.agent_name,
            session_id=request.session_id,
            ticket_id=request.ticket_id,
            latency_ms=request.latency_ms,
        )

        return {
            "usage_id": record.id,
            "raw_cost_usd": float(record.raw_cost_usd),
            "markup_usd": float(record.markup_usd),
            "total_cost_usd": float(record.total_cost_usd),
            "billing_model": record.billing_model.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customers/{customer_id}/usage/summary")
async def get_usage_summary(
    customer_id: str,
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    service: LLMBillingService = Depends(get_billing_service)
):
    """Get usage summary for billing period."""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    summary = await service.get_billing_summary(customer_id, start, end)

    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])

    return summary


@router.get("/customers/{customer_id}/usage/daily")
async def get_daily_spend(
    customer_id: str,
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD)"),
    service: LLMBillingService = Depends(get_billing_service)
):
    """Get daily spending for a specific date."""
    target_date = datetime.fromisoformat(date) if date else datetime.utcnow()

    daily_total = await service.usage_tracker.get_daily_spend(customer_id, target_date)

    config = await service.get_customer_config(customer_id)
    daily_limit = float(config.daily_limit_usd) if config and config.daily_limit_usd else None

    return {
        "customer_id": customer_id,
        "date": target_date.strftime("%Y-%m-%d"),
        "spend_usd": float(daily_total),
        "daily_limit_usd": daily_limit,
        "remaining_usd": daily_limit - float(daily_total) if daily_limit else None,
        "limit_percentage": (float(daily_total) / daily_limit * 100) if daily_limit else None,
    }


# =============================================================================
# Cost Estimation Endpoints
# =============================================================================

@router.post("/estimate-cost", response_model=CostEstimateResponse)
async def estimate_cost(
    request: CostEstimateRequest,
    customer_id: Optional[str] = Query(None, description="Customer ID for custom markup"),
    service: LLMBillingService = Depends(get_billing_service)
):
    """
    Estimate LLM costs based on expected usage.

    Useful for customers to plan their budget.
    """
    try:
        provider = LLMProvider(request.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")

    # Get markup from customer config or use default
    markup = 0.0
    billing_model = "byok"

    if customer_id:
        config = await service.get_customer_config(customer_id)
        if config:
            billing_model = config.billing_model.value
            if config.billing_model == BillingModel.MANAGED:
                markup = config.markup_percentage

    estimate = service.cost_calculator.estimate_monthly_cost(
        daily_requests=request.daily_requests,
        avg_input_tokens=request.avg_input_tokens,
        avg_output_tokens=request.avg_output_tokens,
        provider=provider,
        model=request.model,
        markup_percentage=markup,
    )

    return CostEstimateResponse(
        provider=request.provider,
        model=request.model,
        per_request_usd=float(estimate["per_request"]),
        daily_estimate_usd=float(estimate["daily_estimate"]),
        monthly_estimate_usd=float(estimate["monthly_estimate"]),
        raw_cost_monthly_usd=float(estimate["raw_cost_monthly"]),
        markup_monthly_usd=float(estimate["markup_monthly"]),
        billing_model=billing_model,
    )


@router.get("/pricing")
async def get_pricing():
    """
    Get current LLM pricing for all supported providers and models.

    Pricing is per 1 million tokens.
    """
    pricing_response = {}
    for provider, models in LLM_PRICING.items():
        pricing_response[provider.value] = {
            model: {
                "input_per_1m_tokens": prices["input"],
                "output_per_1m_tokens": prices["output"],
            }
            for model, prices in models.items()
        }

    return {
        "pricing": pricing_response,
        "currency": "USD",
        "unit": "per_1_million_tokens",
        "last_updated": "2026-01-01",
    }


# =============================================================================
# Invoice Endpoints
# =============================================================================

@router.get("/customers/{customer_id}/invoice")
async def generate_invoice(
    customer_id: str,
    start_date: str = Query(..., description="Billing period start (ISO format)"),
    end_date: str = Query(..., description="Billing period end (ISO format)"),
    service: LLMBillingService = Depends(get_billing_service)
):
    """Generate invoice data for a billing period."""
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    invoice = await service.generate_invoice_data(customer_id, start, end)

    return invoice


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "llm-billing",
        "timestamp": datetime.utcnow().isoformat(),
    }
