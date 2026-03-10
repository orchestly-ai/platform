"""
Webhook API Endpoints

Receives webhooks from external services and routes them for processing.

Endpoints:
- POST /api/webhooks/handlers          - Register a webhook handler
- GET  /api/webhooks/handlers          - List all handlers
- DELETE /api/webhooks/handlers/{type} - Remove a handler
- GET  /api/webhooks/events            - List webhook events
- GET  /api/webhooks/events/{event_id} - Get event details
- POST /api/webhooks/events/{id}/retry - Retry failed event
- GET  /api/webhooks/config            - List webhook configurations
- POST /api/webhooks/config/{provider} - Configure webhook for provider
- POST /api/webhooks/{provider}        - Receive webhook from provider (catch-all, must be last)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Query, Header
from pydantic import BaseModel, Field

from backend.webhooks.schema import WebhookStatus, WebhookHandler
from backend.webhooks.registry import get_webhook_registry, get_event_store
from backend.webhooks.processor import get_webhook_processor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ============================================================================
# Response Models
# ============================================================================

class WebhookReceivedResponse(BaseModel):
    """Response after receiving a webhook."""
    success: bool
    event_id: str
    status: str
    message: str


class WebhookEventResponse(BaseModel):
    """Webhook event details."""
    event_id: str
    provider: str
    event_type: str
    payload: Dict[str, Any]
    status: str
    received_at: str
    processed_at: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class WebhookEventsListResponse(BaseModel):
    """List of webhook events."""
    events: List[WebhookEventResponse]
    total: int


class WebhookConfigRequest(BaseModel):
    """Request to configure a webhook."""
    secret_key: Optional[str] = Field(None, description="Webhook secret for signature verification")
    enabled: bool = Field(True, description="Enable/disable webhook processing")
    event_types: List[str] = Field(default_factory=list, description="Event types to process (empty = all)")


class WebhookConfigResponse(BaseModel):
    """Webhook configuration."""
    provider: str
    enabled: bool
    has_secret: bool
    signature_header: str
    event_types: List[str]


class WebhookHandlerRequest(BaseModel):
    """Request to register a webhook handler."""
    event_type: str = Field(..., description="Event type pattern (e.g., 'stripe.payment.succeeded' or 'stripe.*')")
    handler_type: str = Field(..., description="Handler type: 'workflow', 'function', 'http', 'log'")
    handler_config: Dict[str, Any] = Field(default_factory=dict, description="Handler-specific configuration")
    enabled: bool = Field(True, description="Enable/disable handler")


# ============================================================================
# Handler Registration Endpoints (MUST come before /{provider} catch-all)
# ============================================================================

@router.get("/handlers")
async def list_handlers():
    """
    List all registered webhook handlers.
    """
    registry = get_webhook_registry()
    handlers = registry.list_all_handlers()

    return {
        "handlers": [
            {
                "event_type": h.event_type,
                "handler_type": h.handler_type,
                "handler_config": h.handler_config,
                "enabled": h.enabled,
            }
            for h in handlers
        ],
        "total": len(handlers),
    }


@router.post("/handlers")
async def register_handler(request: WebhookHandlerRequest):
    """
    Register a handler for webhook events.

    Example:
        POST /api/webhooks/handlers
        {
            "event_type": "stripe.payment.succeeded",
            "handler_type": "workflow",
            "handler_config": {"workflow_id": "wf-123"}
        }
    """
    registry = get_webhook_registry()

    handler = WebhookHandler(
        event_type=request.event_type,
        handler_type=request.handler_type,
        handler_config=request.handler_config,
        enabled=request.enabled,
    )

    registry.register_handler(handler)

    return {
        "success": True,
        "message": f"Handler registered for {request.event_type}",
        "event_type": request.event_type,
        "handler_type": request.handler_type,
    }


@router.delete("/handlers/{event_type}")
async def unregister_handler(
    event_type: str,
    handler_type: Optional[str] = Query(None, description="Specific handler type to remove"),
):
    """
    Unregister handlers for an event type.
    """
    registry = get_webhook_registry()

    if handler_type:
        registry.unregister_handler(event_type, handler_type)
        message = f"Removed {handler_type} handlers for {event_type}"
    else:
        # Remove all handlers for this event type
        for ht in ["workflow", "function", "http", "log"]:
            registry.unregister_handler(event_type, ht)
        message = f"Removed all handlers for {event_type}"

    return {"success": True, "message": message}


# ============================================================================
# Event Management Endpoints
# ============================================================================

@router.get("/events", response_model=WebhookEventsListResponse)
async def list_webhook_events(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, le=1000, description="Max events to return"),
):
    """
    List webhook events.

    Useful for debugging and monitoring webhook processing.
    """
    event_store = get_event_store()

    status_filter = None
    if status:
        try:
            status_filter = WebhookStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    events = await event_store.list_events(
        provider=provider,
        status=status_filter,
        limit=limit,
    )

    return WebhookEventsListResponse(
        events=[
            WebhookEventResponse(
                event_id=e.event_id,
                provider=e.provider,
                event_type=e.event_type,
                payload=e.payload,
                status=e.status.value,
                received_at=e.received_at.isoformat(),
                processed_at=e.processed_at.isoformat() if e.processed_at else None,
                error_message=e.error_message,
                retry_count=e.retry_count,
            )
            for e in events
        ],
        total=len(events),
    )


@router.get("/events/{event_id}", response_model=WebhookEventResponse)
async def get_webhook_event(event_id: str):
    """
    Get details of a specific webhook event.
    """
    event_store = get_event_store()
    event = await event_store.get(event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return WebhookEventResponse(
        event_id=event.event_id,
        provider=event.provider,
        event_type=event.event_type,
        payload=event.payload,
        status=event.status.value,
        received_at=event.received_at.isoformat(),
        processed_at=event.processed_at.isoformat() if event.processed_at else None,
        error_message=event.error_message,
        retry_count=event.retry_count,
    )


@router.post("/events/{event_id}/retry")
async def retry_webhook_event(event_id: str):
    """
    Retry processing a failed webhook event.
    """
    event_store = get_event_store()
    event = await event_store.get(event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status == WebhookStatus.COMPLETED:
        return {"message": "Event already completed", "event_id": event_id}

    # Update status and retry
    await event_store.update_status(event_id, WebhookStatus.RETRYING)

    processor = get_webhook_processor()
    success = await processor.process_event(event)

    return {
        "success": success,
        "event_id": event_id,
        "status": event.status.value,
    }


# ============================================================================
# Configuration Endpoints
# ============================================================================

@router.get("/config", response_model=List[WebhookConfigResponse])
async def list_webhook_configs():
    """
    List all webhook configurations.
    """
    registry = get_webhook_registry()

    configs = []
    for provider in registry.list_providers():
        config = registry.get_config(provider)
        if config:
            configs.append(WebhookConfigResponse(
                provider=config.provider,
                enabled=config.enabled,
                has_secret=bool(config.secret_key),
                signature_header=config.signature_header,
                event_types=config.event_types,
            ))

    return configs


@router.get("/config/{provider}", response_model=WebhookConfigResponse)
async def get_webhook_config(provider: str):
    """
    Get webhook configuration for a provider.
    """
    registry = get_webhook_registry()
    config = registry.get_config(provider)

    if not config:
        raise HTTPException(status_code=404, detail=f"No config for provider: {provider}")

    return WebhookConfigResponse(
        provider=config.provider,
        enabled=config.enabled,
        has_secret=bool(config.secret_key),
        signature_header=config.signature_header,
        event_types=config.event_types,
    )


@router.post("/config/{provider}", response_model=WebhookConfigResponse)
async def configure_webhook(
    provider: str,
    config_request: WebhookConfigRequest,
):
    """
    Configure webhook settings for a provider.

    Set the webhook secret and other options.
    """
    registry = get_webhook_registry()

    # Get existing config or create new
    config = registry.get_config(provider)
    if not config:
        from backend.webhooks.schema import WebhookConfig
        config = WebhookConfig(provider=provider)

    # Update config
    if config_request.secret_key is not None:
        config.secret_key = config_request.secret_key
    config.enabled = config_request.enabled
    if config_request.event_types:
        config.event_types = config_request.event_types

    registry.set_config(config)

    return WebhookConfigResponse(
        provider=config.provider,
        enabled=config.enabled,
        has_secret=bool(config.secret_key),
        signature_header=config.signature_header,
        event_types=config.event_types,
    )


# ============================================================================
# Webhook Receiver Endpoint (MUST be LAST - catch-all route)
# ============================================================================

@router.post("/{provider}", response_model=WebhookReceivedResponse)
async def receive_webhook(
    provider: str,
    request: Request,
):
    """
    Receive a webhook from an external provider.

    This is the main entry point for all incoming webhooks.
    The endpoint automatically handles:
    - Signature verification
    - Payload parsing
    - Event routing

    Example webhook URLs:
    - Stripe: POST /api/webhooks/stripe
    - GitHub: POST /api/webhooks/github
    - Slack:  POST /api/webhooks/slack

    NOTE: This route MUST be defined LAST in this file because it's a catch-all
    that matches any provider name. Specific routes like /handlers must come first.

    NOTE: Organization ID is derived from the webhook handler config, not from
    user-supplied headers, to prevent org ID spoofing.
    """
    # Get raw body for signature verification
    raw_body = await request.body()

    # Get headers
    headers = dict(request.headers)

    # Process webhook — org_id is derived from handler config internally
    processor = get_webhook_processor()

    try:
        event = await processor.receive_webhook(
            provider=provider,
            raw_body=raw_body,
            headers=headers,
        )

        # Determine response message
        if event.status == WebhookStatus.FAILED:
            message = event.error_message or "Webhook processing failed"
        elif event.status == WebhookStatus.COMPLETED:
            message = "Webhook processed successfully"
        else:
            message = f"Webhook received, status: {event.status.value}"

        return WebhookReceivedResponse(
            success=event.status != WebhookStatus.FAILED,
            event_id=event.event_id,
            status=event.status.value,
            message=message,
        )

    except Exception as e:
        logger.exception(f"Error processing webhook from {provider}")
        raise HTTPException(status_code=500, detail=str(e))
