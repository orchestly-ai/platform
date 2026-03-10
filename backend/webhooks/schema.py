"""
Webhook Schema and Models

Defines the data structures for webhook events and configurations.
"""

import hashlib
import hmac
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class WebhookStatus(str, Enum):
    """Status of a webhook event."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookVerificationMethod(str, Enum):
    """Method used to verify webhook signatures."""
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA1 = "hmac_sha1"
    SIGNATURE_HEADER = "signature_header"
    NONE = "none"


@dataclass
class WebhookEvent:
    """
    Represents an incoming webhook event.

    Stores the raw payload and metadata for processing.
    """
    event_id: str = field(default_factory=lambda: str(uuid4()))
    provider: str = ""  # stripe, github, slack, etc.
    event_type: str = ""  # payment.succeeded, push, message, etc.
    payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    raw_body: bytes = b""
    received_at: datetime = field(default_factory=datetime.utcnow)
    status: WebhookStatus = WebhookStatus.PENDING
    organization_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    processed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "provider": self.provider,
            "event_type": self.event_type,
            "payload": self.payload,
            "received_at": self.received_at.isoformat(),
            "status": self.status.value,
            "organization_id": self.organization_id,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


@dataclass
class WebhookConfig:
    """
    Configuration for a webhook endpoint.

    Loaded from YAML or database.
    """
    provider: str
    enabled: bool = True
    secret_key: Optional[str] = None  # For signature verification
    verification_method: WebhookVerificationMethod = WebhookVerificationMethod.NONE
    signature_header: str = ""  # Header containing signature
    event_types: List[str] = field(default_factory=list)  # Events to process (empty = all)

    # Mapping of provider event types to our internal types
    event_type_mapping: Dict[str, str] = field(default_factory=dict)

    # Field paths in payload
    event_type_path: str = "type"  # Path to event type in payload
    payload_path: Optional[str] = None  # Path to actual payload (if nested)

    def get_internal_event_type(self, provider_event_type: str) -> str:
        """Map provider event type to internal type."""
        return self.event_type_mapping.get(provider_event_type, provider_event_type)


@dataclass
class WebhookHandler:
    """
    Handler for a specific event type.

    Defines what action to take when an event is received.
    """
    event_type: str  # e.g., "stripe.payment.succeeded"
    handler_type: str  # "workflow", "function", "http"
    handler_config: Dict[str, Any] = field(default_factory=dict)
    # For workflow: {"workflow_id": "xxx"}
    # For function: {"function_name": "xxx"}
    # For http: {"url": "xxx", "method": "POST"}

    enabled: bool = True
    filters: Dict[str, Any] = field(default_factory=dict)  # Optional filters


class WebhookSignatureVerifier:
    """
    Verifies webhook signatures for security.

    Supports multiple verification methods used by different providers.
    """

    @staticmethod
    def verify_hmac_sha256(
        payload: bytes,
        signature: str,
        secret: str,
        prefix: str = ""
    ) -> bool:
        """
        Verify HMAC SHA256 signature.

        Used by: Stripe, GitHub, Slack
        """
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Handle prefixed signatures (e.g., "sha256=xxx")
        if prefix and signature.startswith(prefix):
            signature = signature[len(prefix):]

        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_hmac_sha1(
        payload: bytes,
        signature: str,
        secret: str,
        prefix: str = ""
    ) -> bool:
        """
        Verify HMAC SHA1 signature.

        Used by: Some legacy integrations
        """
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha1
        ).hexdigest()

        if prefix and signature.startswith(prefix):
            signature = signature[len(prefix):]

        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_stripe_signature(
        payload: bytes,
        signature_header: str,
        secret: str,
        tolerance: int = 300
    ) -> bool:
        """
        Verify Stripe webhook signature.

        Stripe uses a special format: t=timestamp,v1=signature
        """
        try:
            # Parse signature header
            parts = dict(item.split("=", 1) for item in signature_header.split(","))
            timestamp = parts.get("t")
            signature = parts.get("v1")

            if not timestamp or not signature:
                return False

            # Check timestamp tolerance
            if abs(int(timestamp) - datetime.utcnow().timestamp()) > tolerance:
                return False

            # Compute expected signature
            signed_payload = f"{timestamp}.{payload.decode()}"
            expected = hmac.new(
                secret.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected, signature)

        except Exception:
            return False

    def verify(
        self,
        config: WebhookConfig,
        payload: bytes,
        headers: Dict[str, str]
    ) -> bool:
        """
        Verify webhook signature based on config.

        Returns True if signature is valid or verification is disabled.
        """
        if config.verification_method == WebhookVerificationMethod.NONE:
            return True

        if not config.secret_key:
            return True  # No secret configured, skip verification

        signature = headers.get(config.signature_header, "")
        if not signature:
            return False

        if config.verification_method == WebhookVerificationMethod.HMAC_SHA256:
            return self.verify_hmac_sha256(payload, signature, config.secret_key)

        elif config.verification_method == WebhookVerificationMethod.HMAC_SHA1:
            return self.verify_hmac_sha1(payload, signature, config.secret_key)

        # Special handling for Stripe
        if config.provider == "stripe":
            return self.verify_stripe_signature(payload, signature, config.secret_key)

        return False
