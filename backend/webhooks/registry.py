"""
Webhook Registry

Manages webhook configurations and handlers.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from .schema import (
    WebhookConfig,
    WebhookEvent,
    WebhookHandler,
    WebhookStatus,
    WebhookVerificationMethod,
)

# Singleton instances
_webhook_registry: Optional["WebhookRegistry"] = None
_event_store: Optional["WebhookEventStore"] = None

# Get persistent data directory (relative to this file's location)
_BACKEND_DIR = Path(__file__).parent.parent
_DATA_DIR = _BACKEND_DIR / "data"


# Default webhook configurations for common providers
DEFAULT_WEBHOOK_CONFIGS: Dict[str, Dict[str, Any]] = {
    "stripe": {
        "enabled": True,
        "verification_method": "hmac_sha256",
        "signature_header": "Stripe-Signature",
        "event_type_path": "type",
        "event_type_mapping": {
            "payment_intent.succeeded": "payment.succeeded",
            "payment_intent.failed": "payment.failed",
            "customer.created": "customer.created",
            "customer.updated": "customer.updated",
            "invoice.paid": "invoice.paid",
            "invoice.payment_failed": "invoice.payment_failed",
        },
    },
    "github": {
        "enabled": True,
        "verification_method": "hmac_sha256",
        "signature_header": "X-Hub-Signature-256",
        "event_type_path": "__header__X-GitHub-Event",  # Event type in header
        "event_type_mapping": {
            "push": "code.push",
            "pull_request": "pr.activity",
            "issues": "issue.activity",
            "issue_comment": "issue.comment",
            "release": "release.activity",
        },
    },
    "slack": {
        "enabled": True,
        "verification_method": "hmac_sha256",
        "signature_header": "X-Slack-Signature",
        "event_type_path": "event.type",
        "event_type_mapping": {
            "message": "message.received",
            "app_mention": "mention.received",
            "reaction_added": "reaction.added",
        },
    },
    "discord": {
        "enabled": True,
        "verification_method": "none",  # Discord uses different verification
        "event_type_path": "t",
        "event_type_mapping": {
            "MESSAGE_CREATE": "message.received",
            "INTERACTION_CREATE": "interaction.received",
        },
    },
    "hubspot": {
        "enabled": True,
        "verification_method": "hmac_sha256",
        "signature_header": "X-HubSpot-Signature-v3",
        "event_type_path": "subscriptionType",
        "event_type_mapping": {
            "contact.creation": "contact.created",
            "contact.propertyChange": "contact.updated",
            "deal.creation": "deal.created",
        },
    },
}


class WebhookRegistry:
    """
    Registry of webhook configurations and handlers.

    Manages which providers are enabled and how to process their events.
    """

    def __init__(self, handlers_storage_path: Optional[str] = None):
        self._configs: Dict[str, WebhookConfig] = {}
        self._handlers: Dict[str, List[WebhookHandler]] = {}  # event_type -> handlers

        # Use persistent data directory instead of /tmp
        default_path = str(_DATA_DIR / "webhook_handlers.json")
        self._handlers_storage_path = handlers_storage_path or os.environ.get(
            "WEBHOOK_HANDLERS_STORAGE_PATH",
            default_path
        )

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self._handlers_storage_path), exist_ok=True)

        self._load_default_configs()
        self._load_handlers_from_file()

    def _load_handlers_from_file(self):
        """Load handlers from file if exists."""
        logger.info(f"Loading handlers from: {self._handlers_storage_path}")
        if not os.path.exists(self._handlers_storage_path):
            logger.info("Handlers file does not exist yet")
            return
        try:
            with open(self._handlers_storage_path, 'r') as f:
                data = json.load(f)
                for event_type, handlers_list in data.items():
                    self._handlers[event_type] = [
                        WebhookHandler(
                            event_type=h.get("event_type", event_type),
                            handler_type=h.get("handler_type", "log"),
                            handler_config=h.get("handler_config", {}),
                            enabled=h.get("enabled", True),
                        )
                        for h in handlers_list
                    ]
                logger.info(f"Loaded {len(self._handlers)} event types with handlers")
        except Exception as e:
            logger.exception(f"Error loading handlers from file: {e}")

    def _save_handlers_to_file(self):
        """Save handlers to file."""
        logger.info(f"Saving handlers to: {self._handlers_storage_path}")
        try:
            data = {}
            for event_type, handlers_list in self._handlers.items():
                data[event_type] = [
                    {
                        "event_type": h.event_type,
                        "handler_type": h.handler_type,
                        "handler_config": h.handler_config,
                        "enabled": h.enabled,
                    }
                    for h in handlers_list
                ]
            with open(self._handlers_storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(data)} event types with handlers to file")
        except Exception as e:
            logger.exception(f"Error saving handlers to file: {e}")

    def _load_default_configs(self):
        """Load default webhook configurations."""
        for provider, config_dict in DEFAULT_WEBHOOK_CONFIGS.items():
            self._configs[provider] = WebhookConfig(
                provider=provider,
                enabled=config_dict.get("enabled", True),
                verification_method=WebhookVerificationMethod(
                    config_dict.get("verification_method", "none")
                ),
                signature_header=config_dict.get("signature_header", ""),
                event_type_path=config_dict.get("event_type_path", "type"),
                event_type_mapping=config_dict.get("event_type_mapping", {}),
            )

    def get_config(self, provider: str) -> Optional[WebhookConfig]:
        """Get webhook config for a provider."""
        return self._configs.get(provider)

    def set_config(self, config: WebhookConfig):
        """Set or update webhook config."""
        self._configs[config.provider] = config

    def set_secret(self, provider: str, secret: str):
        """Set the webhook secret for a provider."""
        if provider in self._configs:
            self._configs[provider].secret_key = secret
        else:
            # Create new config with secret
            self._configs[provider] = WebhookConfig(
                provider=provider,
                secret_key=secret,
            )

    def list_providers(self) -> List[str]:
        """List all configured providers."""
        return list(self._configs.keys())

    def register_handler(self, handler: WebhookHandler):
        """Register a handler for an event type."""
        logger.info(f"Registering handler: event_type={handler.event_type}, handler_type={handler.handler_type}")
        if handler.event_type not in self._handlers:
            self._handlers[handler.event_type] = []
        self._handlers[handler.event_type].append(handler)
        logger.info(f"Total handlers now: {sum(len(h) for h in self._handlers.values())}")
        self._save_handlers_to_file()

    def get_handlers(self, event_type: str) -> List[WebhookHandler]:
        """Get all handlers for an event type."""
        handlers = []

        # Exact match
        handlers.extend(self._handlers.get(event_type, []))

        # Wildcard match (e.g., "stripe.*" matches "stripe.payment.succeeded")
        for pattern, pattern_handlers in self._handlers.items():
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if event_type.startswith(prefix):
                    handlers.extend(pattern_handlers)

        return [h for h in handlers if h.enabled]

    def unregister_handler(self, event_type: str, handler_type: str):
        """Unregister handlers of a specific type for an event."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type]
                if h.handler_type != handler_type
            ]
            # Clean up empty entries
            if not self._handlers[event_type]:
                del self._handlers[event_type]
            self._save_handlers_to_file()

    def list_all_handlers(self) -> List[WebhookHandler]:
        """List all registered handlers."""
        handlers = []
        for event_handlers in self._handlers.values():
            handlers.extend(event_handlers)
        logger.info(f"list_all_handlers called, returning {len(handlers)} handlers")
        return handlers


class WebhookEventStore:
    """
    Storage for webhook events.

    In production, this would use a database.
    For development, uses in-memory with optional file persistence.
    """

    def __init__(self, storage_path: Optional[str] = None):
        # Use persistent data directory instead of /tmp
        default_path = str(_DATA_DIR / "webhook_events.json")
        self._storage_path = storage_path or os.environ.get(
            "WEBHOOK_EVENT_STORAGE_PATH",
            default_path
        )

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)

        self._events: Dict[str, WebhookEvent] = {}
        self._load_from_file()

    def _load_from_file(self):
        """Load events from file if exists."""
        if not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path, 'r') as f:
                data = json.load(f)
                for event_id, event_data in data.items():
                    # Reconstruct WebhookEvent
                    self._events[event_id] = WebhookEvent(
                        event_id=event_data["event_id"],
                        provider=event_data["provider"],
                        event_type=event_data["event_type"],
                        payload=event_data["payload"],
                        received_at=datetime.fromisoformat(event_data["received_at"]),
                        status=WebhookStatus(event_data["status"]),
                        organization_id=event_data.get("organization_id"),
                        error_message=event_data.get("error_message"),
                        retry_count=event_data.get("retry_count", 0),
                    )
        except Exception as e:
            print(f"Error loading webhook events: {e}")

    def _save_to_file(self):
        """Save events to file."""
        if not self._storage_path:
            return
        try:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            # Only keep last 1000 events
            events_to_save = dict(list(self._events.items())[-1000:])
            with open(self._storage_path, 'w') as f:
                json.dump(
                    {eid: e.to_dict() for eid, e in events_to_save.items()},
                    f
                )
        except Exception as e:
            print(f"Error saving webhook events: {e}")

    async def store(self, event: WebhookEvent) -> str:
        """Store a webhook event."""
        self._events[event.event_id] = event
        self._save_to_file()
        return event.event_id

    async def get(self, event_id: str) -> Optional[WebhookEvent]:
        """Get a webhook event by ID."""
        return self._events.get(event_id)

    async def update_status(
        self,
        event_id: str,
        status: WebhookStatus,
        error_message: Optional[str] = None
    ):
        """Update event status."""
        if event_id in self._events:
            self._events[event_id].status = status
            if error_message:
                self._events[event_id].error_message = error_message
            if status == WebhookStatus.COMPLETED:
                self._events[event_id].processed_at = datetime.utcnow()
            elif status == WebhookStatus.RETRYING:
                self._events[event_id].retry_count += 1
            self._save_to_file()

    async def list_events(
        self,
        provider: Optional[str] = None,
        status: Optional[WebhookStatus] = None,
        limit: int = 100
    ) -> List[WebhookEvent]:
        """List events with optional filters."""
        events = list(self._events.values())

        if provider:
            events = [e for e in events if e.provider == provider]
        if status:
            events = [e for e in events if e.status == status]

        # Sort by received_at descending
        events.sort(key=lambda e: e.received_at, reverse=True)

        return events[:limit]

    async def get_pending_events(self, limit: int = 100) -> List[WebhookEvent]:
        """Get events that need processing."""
        return await self.list_events(status=WebhookStatus.PENDING, limit=limit)


def get_webhook_registry() -> WebhookRegistry:
    """Get singleton webhook registry."""
    global _webhook_registry
    if _webhook_registry is None:
        _webhook_registry = WebhookRegistry()
    return _webhook_registry


def get_event_store() -> WebhookEventStore:
    """Get singleton event store."""
    global _event_store
    if _event_store is None:
        _event_store = WebhookEventStore()
    return _event_store
