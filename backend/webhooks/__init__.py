"""
Webhook Processing Module

Receives and processes webhooks from external services.

Usage:
    from backend.webhooks import get_webhook_processor, get_webhook_registry

    # Receive a webhook
    processor = get_webhook_processor()
    event = await processor.receive_webhook(
        provider="stripe",
        raw_body=request_body,
        headers=request_headers,
    )

    # Register a handler
    registry = get_webhook_registry()
    registry.register_handler(WebhookHandler(
        event_type="stripe.payment.succeeded",
        handler_type="workflow",
        handler_config={"workflow_id": "wf-123"},
    ))
"""

from .schema import (
    WebhookEvent,
    WebhookConfig,
    WebhookHandler,
    WebhookStatus,
    WebhookVerificationMethod,
    WebhookSignatureVerifier,
)
from .registry import (
    WebhookRegistry,
    WebhookEventStore,
    get_webhook_registry,
    get_event_store,
)
from .processor import (
    WebhookProcessor,
    get_webhook_processor,
)

__all__ = [
    # Schema
    "WebhookEvent",
    "WebhookConfig",
    "WebhookHandler",
    "WebhookStatus",
    "WebhookVerificationMethod",
    "WebhookSignatureVerifier",
    # Registry
    "WebhookRegistry",
    "WebhookEventStore",
    "get_webhook_registry",
    "get_event_store",
    # Processor
    "WebhookProcessor",
    "get_webhook_processor",
]
