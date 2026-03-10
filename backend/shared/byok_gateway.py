#!/usr/bin/env python3
"""
BYOK Gateway - Bring Your Own Key Support

Implements ROADMAP.md Section: Customer-Managed Key Gateway (BYOK)

Features:
- Encrypted customer API key storage (Key Vault)
- Usage tracking and rate limit prediction (Quota Guard)
- Cost transparency with customer pricing (Transparency Engine)
- Pre-emptive throttling to avoid rate limits
- Key validation and health monitoring

Key Design Decisions:
- Customer keys encrypted at rest with Fernet
- Usage tracked in hourly buckets for billing
- Rate limits enforced before hitting provider limits
- Cost calculated using customer's tier pricing
"""

import asyncio
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4
import logging
import json

logger = logging.getLogger(__name__)


class KeyProvider(str, Enum):
    """Supported API key providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GOOGLE = "google"


class KeyStatus(str, Enum):
    """Status of a customer API key."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    RATE_LIMITED = "rate_limited"
    INVALID = "invalid"


@dataclass
class CustomerTier:
    """Customer's API tier configuration."""
    tier_name: str
    rate_limit_rpm: int  # Requests per minute
    rate_limit_tpm: int  # Tokens per minute
    rate_limit_rpd: Optional[int] = None  # Requests per day
    pricing_per_1m_input: float = 0.0
    pricing_per_1m_output: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier_name": self.tier_name,
            "rate_limit_rpm": self.rate_limit_rpm,
            "rate_limit_tpm": self.rate_limit_tpm,
            "rate_limit_rpd": self.rate_limit_rpd,
            "pricing_per_1m_input": self.pricing_per_1m_input,
            "pricing_per_1m_output": self.pricing_per_1m_output,
        }


# Default tiers per provider
DEFAULT_TIERS = {
    KeyProvider.OPENAI: {
        "tier_1": CustomerTier("tier_1", rate_limit_rpm=500, rate_limit_tpm=40000),
        "tier_2": CustomerTier("tier_2", rate_limit_rpm=5000, rate_limit_tpm=80000),
        "tier_3": CustomerTier("tier_3", rate_limit_rpm=5000, rate_limit_tpm=160000),
        "tier_4": CustomerTier("tier_4", rate_limit_rpm=10000, rate_limit_tpm=1000000),
        "tier_5": CustomerTier("tier_5", rate_limit_rpm=10000, rate_limit_tpm=2000000),
    },
    KeyProvider.ANTHROPIC: {
        "tier_1": CustomerTier("tier_1", rate_limit_rpm=50, rate_limit_tpm=40000),
        "tier_2": CustomerTier("tier_2", rate_limit_rpm=1000, rate_limit_tpm=80000),
        "tier_3": CustomerTier("tier_3", rate_limit_rpm=2000, rate_limit_tpm=160000),
        "tier_4": CustomerTier("tier_4", rate_limit_rpm=4000, rate_limit_tpm=400000),
    },
    KeyProvider.DEEPSEEK: {
        "default": CustomerTier("default", rate_limit_rpm=60, rate_limit_tpm=100000),
    },
}


@dataclass
class CustomerAPIKey:
    """A customer's API key configuration."""
    key_id: UUID
    org_id: UUID
    provider: KeyProvider
    encrypted_key: str  # Base64-encoded encrypted key
    key_prefix: str  # First few chars for display (e.g., "sk-proj-abc...")
    tier: CustomerTier
    status: KeyStatus = KeyStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    last_validated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": str(self.key_id),
            "org_id": str(self.org_id),
            "provider": self.provider.value,
            "key_prefix": self.key_prefix,
            "tier": self.tier.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "last_validated_at": self.last_validated_at.isoformat() if self.last_validated_at else None,
        }


@dataclass
class UsageBucket:
    """Hourly usage tracking bucket."""
    bucket_id: UUID
    key_id: UUID
    org_id: UUID
    period_start: datetime
    period_end: datetime
    requests_count: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    estimated_cost: float = 0.0
    rate_limit_hits: int = 0
    errors_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bucket_id": str(self.bucket_id),
            "key_id": str(self.key_id),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "requests_count": self.requests_count,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "estimated_cost": self.estimated_cost,
            "rate_limit_hits": self.rate_limit_hits,
            "errors_count": self.errors_count,
        }


@dataclass
class QuotaCheckResult:
    """Result of a quota check."""
    allowed: bool
    reason: Optional[str] = None
    current_rpm: int = 0
    current_tpm: int = 0
    remaining_rpm: int = 0
    remaining_tpm: int = 0
    retry_after_seconds: Optional[int] = None
    throttle_recommended: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "current_rpm": self.current_rpm,
            "current_tpm": self.current_tpm,
            "remaining_rpm": self.remaining_rpm,
            "remaining_tpm": self.remaining_tpm,
            "retry_after_seconds": self.retry_after_seconds,
            "throttle_recommended": self.throttle_recommended,
        }


@dataclass
class SpendReport:
    """Cost transparency report."""
    org_id: UUID
    period_start: datetime
    period_end: datetime
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    cost_by_provider: Dict[str, float] = field(default_factory=dict)
    cost_by_day: List[Dict[str, Any]] = field(default_factory=list)
    burn_rate_per_hour: float = 0.0
    projected_monthly_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "org_id": str(self.org_id),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "cost_by_provider": self.cost_by_provider,
            "burn_rate_per_hour": self.burn_rate_per_hour,
            "projected_monthly_cost": self.projected_monthly_cost,
        }


class KeyVault:
    """
    Secure storage for customer API keys.

    Uses Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256).
    In production, this would use AWS KMS, HashiCorp Vault, or similar.
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize with encryption key.

        Args:
            encryption_key: A Fernet-compatible key (base64-encoded 32 bytes).
                If not provided, derives one from BYOK_ENCRYPTION_SECRET env var
                or auto-generates an ephemeral key (dev only).
        """
        import os
        import warnings

        # cryptography is a hard dependency — no fallback to base64
        from cryptography.fernet import Fernet

        if encryption_key:
            # If it's already a valid Fernet key, use directly
            try:
                self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            except Exception:
                # Treat as passphrase and derive a key
                self._fernet = self._derive_fernet_key(encryption_key)
        else:
            secret = os.environ.get("BYOK_ENCRYPTION_SECRET", "")
            if secret:
                self._fernet = self._derive_fernet_key(secret)
            else:
                # Auto-generate ephemeral key for development
                self._fernet = Fernet(Fernet.generate_key())
                warnings.warn(
                    "BYOK_ENCRYPTION_SECRET not set — using ephemeral encryption key. "
                    "Encrypted keys will be unrecoverable after restart.",
                    stacklevel=2,
                )

    @staticmethod
    def _derive_fernet_key(secret: str) -> "Fernet":
        """Derive a Fernet key from a passphrase using PBKDF2."""
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"orchestly-byok-vault-v1",
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        return Fernet(key)

    def encrypt_key(self, api_key: str) -> str:
        """Encrypt an API key for storage using Fernet."""
        return self._fernet.encrypt(api_key.encode()).decode()

    def decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt an API key for use."""
        return self._fernet.decrypt(encrypted_key.encode()).decode()

    def get_key_prefix(self, api_key: str) -> str:
        """Get display prefix for key (e.g., 'sk-proj-abc...')."""
        if len(api_key) <= 12:
            return api_key[:4] + "..."
        return api_key[:12] + "..."


class BYOKGateway:
    """
    BYOK Gateway for customer-managed API keys.

    Provides:
    - Encrypted key storage
    - Quota/rate limit management
    - Cost transparency
    - Pre-emptive throttling
    """

    # Buffer percentage before hitting actual rate limits
    RATE_LIMIT_BUFFER_PERCENT = 0.9  # Throttle at 90% of limit

    def __init__(
        self,
        db=None,
        encryption_key: Optional[str] = None,
        rate_limit_callback: Optional[Callable] = None,
    ):
        """Initialize the BYOK gateway."""
        self.db = db
        self.vault = KeyVault(encryption_key)
        self.rate_limit_callback = rate_limit_callback

        # In-memory storage for testing
        self._keys: Dict[UUID, CustomerAPIKey] = {}
        self._usage_buckets: Dict[str, UsageBucket] = {}  # key: "{key_id}:{hour}"
        self._minute_counters: Dict[str, Dict[str, int]] = {}  # For RPM tracking

    async def register_key(
        self,
        org_id: UUID,
        provider: KeyProvider,
        api_key: str,
        tier_name: str = "tier_1",
        custom_tier: Optional[CustomerTier] = None,
    ) -> CustomerAPIKey:
        """
        Register a customer's API key.

        Args:
            org_id: Organization ID
            provider: API provider (openai, anthropic, etc.)
            api_key: The actual API key
            tier_name: Customer's tier level
            custom_tier: Optional custom tier configuration

        Returns:
            CustomerAPIKey with encrypted key
        """
        # Encrypt the key
        encrypted = self.vault.encrypt_key(api_key)
        prefix = self.vault.get_key_prefix(api_key)

        # Get tier configuration
        if custom_tier:
            tier = custom_tier
        else:
            provider_tiers = DEFAULT_TIERS.get(provider, {})
            tier = provider_tiers.get(tier_name, CustomerTier(tier_name, 1000, 100000))

        key = CustomerAPIKey(
            key_id=uuid4(),
            org_id=org_id,
            provider=provider,
            encrypted_key=encrypted,
            key_prefix=prefix,
            tier=tier,
        )

        self._keys[key.key_id] = key
        return key

    async def get_key(self, key_id: UUID) -> Optional[CustomerAPIKey]:
        """Get a registered key by ID."""
        return self._keys.get(key_id)

    async def get_keys_by_org(self, org_id: UUID) -> List[CustomerAPIKey]:
        """Get all keys for an organization."""
        return [k for k in self._keys.values() if k.org_id == org_id]

    async def get_decrypted_key(self, key_id: UUID) -> Optional[str]:
        """Get the decrypted API key for making requests."""
        key = self._keys.get(key_id)
        if not key or key.status != KeyStatus.ACTIVE:
            return None

        # Update last used timestamp
        key.last_used_at = datetime.utcnow()

        return self.vault.decrypt_key(key.encrypted_key)

    async def update_key_status(
        self,
        key_id: UUID,
        status: KeyStatus,
    ) -> bool:
        """Update the status of a key."""
        key = self._keys.get(key_id)
        if not key:
            return False
        key.status = status
        return True

    async def check_quota(
        self,
        key_id: UUID,
        estimated_tokens: int = 0,
    ) -> QuotaCheckResult:
        """
        Check if a request is within quota limits.

        Args:
            key_id: The customer key ID
            estimated_tokens: Estimated tokens for this request

        Returns:
            QuotaCheckResult indicating if request is allowed
        """
        key = self._keys.get(key_id)
        if not key:
            return QuotaCheckResult(allowed=False, reason="Key not found")

        if key.status != KeyStatus.ACTIVE:
            return QuotaCheckResult(allowed=False, reason=f"Key status: {key.status.value}")

        # Get current minute counters
        now = datetime.utcnow()
        minute_key = f"{key_id}:{now.strftime('%Y%m%d%H%M')}"

        counters = self._minute_counters.get(minute_key, {"rpm": 0, "tpm": 0})

        current_rpm = counters["rpm"]
        current_tpm = counters["tpm"]

        # Calculate limits with buffer
        max_rpm = int(key.tier.rate_limit_rpm * self.RATE_LIMIT_BUFFER_PERCENT)
        max_tpm = int(key.tier.rate_limit_tpm * self.RATE_LIMIT_BUFFER_PERCENT)

        # Check RPM
        if current_rpm >= max_rpm:
            return QuotaCheckResult(
                allowed=False,
                reason="Rate limit: too many requests per minute",
                current_rpm=current_rpm,
                current_tpm=current_tpm,
                remaining_rpm=0,
                remaining_tpm=max(0, max_tpm - current_tpm),
                retry_after_seconds=60 - now.second,
            )

        # Check TPM
        if current_tpm + estimated_tokens > max_tpm:
            return QuotaCheckResult(
                allowed=False,
                reason="Rate limit: token limit would be exceeded",
                current_rpm=current_rpm,
                current_tpm=current_tpm,
                remaining_rpm=max(0, max_rpm - current_rpm),
                remaining_tpm=0,
                retry_after_seconds=60 - now.second,
            )

        # Check if we should recommend throttling (approaching limits)
        throttle_recommended = (
            current_rpm > max_rpm * 0.8 or
            current_tpm + estimated_tokens > max_tpm * 0.8
        )

        return QuotaCheckResult(
            allowed=True,
            current_rpm=current_rpm,
            current_tpm=current_tpm,
            remaining_rpm=max_rpm - current_rpm - 1,
            remaining_tpm=max_tpm - current_tpm - estimated_tokens,
            throttle_recommended=throttle_recommended,
        )

    async def record_usage(
        self,
        key_id: UUID,
        input_tokens: int,
        output_tokens: int,
        success: bool = True,
        rate_limited: bool = False,
    ) -> UsageBucket:
        """
        Record API usage for a key.

        Args:
            key_id: The customer key ID
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            success: Whether the request succeeded
            rate_limited: Whether request was rate limited

        Returns:
            Updated usage bucket
        """
        key = self._keys.get(key_id)
        if not key:
            raise ValueError(f"Key {key_id} not found")

        now = datetime.utcnow()

        # Get or create hourly bucket
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        bucket_key = f"{key_id}:{hour_start.strftime('%Y%m%d%H')}"

        if bucket_key not in self._usage_buckets:
            self._usage_buckets[bucket_key] = UsageBucket(
                bucket_id=uuid4(),
                key_id=key_id,
                org_id=key.org_id,
                period_start=hour_start,
                period_end=hour_end,
            )

        bucket = self._usage_buckets[bucket_key]

        # Update bucket
        bucket.requests_count += 1
        bucket.tokens_input += input_tokens
        bucket.tokens_output += output_tokens

        # Calculate cost using customer's pricing
        input_cost = (input_tokens / 1_000_000) * key.tier.pricing_per_1m_input
        output_cost = (output_tokens / 1_000_000) * key.tier.pricing_per_1m_output
        bucket.estimated_cost += input_cost + output_cost

        if rate_limited:
            bucket.rate_limit_hits += 1
        if not success:
            bucket.errors_count += 1

        # Update minute counters for rate limiting
        minute_key = f"{key_id}:{now.strftime('%Y%m%d%H%M')}"
        if minute_key not in self._minute_counters:
            self._minute_counters[minute_key] = {"rpm": 0, "tpm": 0}

        self._minute_counters[minute_key]["rpm"] += 1
        self._minute_counters[minute_key]["tpm"] += input_tokens + output_tokens

        # Cleanup old minute counters (keep last 5 minutes)
        self._cleanup_old_counters()

        return bucket

    def _cleanup_old_counters(self):
        """Remove minute counters older than 5 minutes."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=5)
        cutoff_str = cutoff.strftime('%Y%m%d%H%M')

        to_delete = [
            k for k in self._minute_counters.keys()
            if k.split(":")[1] < cutoff_str
        ]
        for k in to_delete:
            del self._minute_counters[k]

    async def get_spend_report(
        self,
        org_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> SpendReport:
        """
        Generate a spend report for an organization.

        Args:
            org_id: Organization ID
            start_date: Report start date (default: 30 days ago)
            end_date: Report end date (default: now)

        Returns:
            SpendReport with cost breakdown
        """
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Aggregate usage buckets
        total_requests = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0
        cost_by_provider: Dict[str, float] = {}

        org_keys = await self.get_keys_by_org(org_id)
        key_ids = {k.key_id for k in org_keys}
        key_providers = {k.key_id: k.provider.value for k in org_keys}

        for bucket_key, bucket in self._usage_buckets.items():
            if bucket.key_id not in key_ids:
                continue
            if bucket.period_start < start_date or bucket.period_end > end_date:
                continue

            total_requests += bucket.requests_count
            total_input_tokens += bucket.tokens_input
            total_output_tokens += bucket.tokens_output
            total_cost += bucket.estimated_cost

            provider = key_providers.get(bucket.key_id, "unknown")
            cost_by_provider[provider] = cost_by_provider.get(provider, 0) + bucket.estimated_cost

        # Calculate burn rate
        hours_elapsed = max(1, (end_date - start_date).total_seconds() / 3600)
        burn_rate_per_hour = total_cost / hours_elapsed

        # Project monthly cost
        projected_monthly_cost = burn_rate_per_hour * 24 * 30

        return SpendReport(
            org_id=org_id,
            period_start=start_date,
            period_end=end_date,
            total_requests=total_requests,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_cost=total_cost,
            cost_by_provider=cost_by_provider,
            burn_rate_per_hour=burn_rate_per_hour,
            projected_monthly_cost=projected_monthly_cost,
        )

    async def validate_key(self, key_id: UUID) -> bool:
        """
        Validate that a key is still working.

        In production, this would make a lightweight API call to the provider.
        Returns True if key is valid, False otherwise.
        """
        key = self._keys.get(key_id)
        if not key:
            return False

        # In production: make actual API call to validate
        # For now, just check status
        key.last_validated_at = datetime.utcnow()
        return key.status == KeyStatus.ACTIVE

    async def rotate_key(
        self,
        key_id: UUID,
        new_api_key: str,
    ) -> CustomerAPIKey:
        """
        Rotate a customer's API key.

        Args:
            key_id: Existing key ID
            new_api_key: New API key to use

        Returns:
            Updated CustomerAPIKey
        """
        key = self._keys.get(key_id)
        if not key:
            raise ValueError(f"Key {key_id} not found")

        # Encrypt new key
        key.encrypted_key = self.vault.encrypt_key(new_api_key)
        key.key_prefix = self.vault.get_key_prefix(new_api_key)
        key.last_validated_at = datetime.utcnow()
        key.status = KeyStatus.ACTIVE

        return key

    async def delete_key(self, key_id: UUID) -> bool:
        """Delete a customer's API key."""
        if key_id in self._keys:
            del self._keys[key_id]
            return True
        return False

    def get_all_keys(self) -> List[CustomerAPIKey]:
        """Get all registered keys."""
        return list(self._keys.values())

    async def get_usage_history(
        self,
        key_id: UUID,
        hours: int = 24,
    ) -> List[UsageBucket]:
        """Get usage history for a key."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        return [
            bucket for bucket in self._usage_buckets.values()
            if bucket.key_id == key_id and bucket.period_start >= cutoff
        ]


# Singleton instance
_gateway_instance: Optional[BYOKGateway] = None


def get_byok_gateway(
    db=None,
    encryption_key: Optional[str] = None,
) -> BYOKGateway:
    """Get or create the singleton BYOK gateway instance."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = BYOKGateway(db=db, encryption_key=encryption_key)
    return _gateway_instance


def reset_byok_gateway() -> None:
    """Reset the singleton instance (for testing)."""
    global _gateway_instance
    _gateway_instance = None
