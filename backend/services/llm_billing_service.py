"""
LLM Billing and Key Management Service

Handles multiple billing models for LLM usage:
1. BYOK (Bring Your Own Key) - Customer provides their own API keys
2. Managed Keys - We provision and manage keys, charge usage + markup
3. Prepaid Credits - Customer buys credits upfront, we deduct usage

This ensures we never lose money on heavy LLM users while providing
flexibility for different customer segments.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from cryptography.fernet import Fernet
import aiohttp


# Use standard logging
logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class BillingModel(str, Enum):
    """How the customer pays for LLM usage."""
    BYOK = "byok"              # Bring Your Own Key - zero LLM cost to us
    MANAGED = "managed"        # We manage keys, charge usage + markup
    PREPAID = "prepaid"        # Prepaid credits, deduct as they use
    ENTERPRISE = "enterprise"  # Custom agreement


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    COHERE = "cohere"
    MISTRAL = "mistral"
    GROQ = "groq"  # Fast inference provider


class UsageType(str, Enum):
    """Type of LLM usage for billing."""
    CHAT_COMPLETION = "chat_completion"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    AUDIO_SYNTHESIS = "audio_synthesis"


# Current pricing per 1M tokens (as of 2026-01)
LLM_PRICING = {
    LLMProvider.OPENAI: {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
        "text-embedding-3-large": {"input": 0.13, "output": 0.0},
    },
    LLMProvider.ANTHROPIC: {
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    },
    LLMProvider.GOOGLE: {
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    },
    LLMProvider.GROQ: {
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
        "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
        "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
    },
}

# Default markup percentage for managed keys
DEFAULT_MARKUP_PERCENTAGE = 15.0


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BYOKKeyMetadata:
    """Metadata for a BYOK API key including validation and expiration tracking."""
    provider: LLMProvider
    encrypted_key: str

    # Validation tracking
    is_valid: Optional[bool] = None
    last_validated_at: Optional[datetime] = None
    validation_error: Optional[str] = None

    # Expiration tracking (optional - not all keys expire)
    expires_at: Optional[datetime] = None
    reminder_days_before: int = 7  # Days before expiration to send reminder
    last_reminder_sent: Optional[datetime] = None

    # Key lifecycle
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Optional metadata
    key_name: Optional[str] = None  # User-friendly name like "Production Key"
    key_prefix: Optional[str] = None  # First 8 chars for identification (e.g., "sk-proj-...")

    def needs_validation(self, max_age_hours: int = 24) -> bool:
        """Check if key needs revalidation based on age."""
        if self.last_validated_at is None:
            return True
        age = datetime.utcnow() - self.last_validated_at
        return age > timedelta(hours=max_age_hours)

    def needs_renewal_reminder(self) -> bool:
        """Check if we should send an expiration reminder."""
        if self.expires_at is None:
            return False
        days_until_expiry = (self.expires_at - datetime.utcnow()).days
        if days_until_expiry > self.reminder_days_before:
            return False
        # Don't spam - only remind once per day
        if self.last_reminder_sent:
            hours_since_reminder = (datetime.utcnow() - self.last_reminder_sent).total_seconds() / 3600
            if hours_since_reminder < 24:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.value,
            "is_valid": self.is_valid,
            "last_validated_at": self.last_validated_at.isoformat() if self.last_validated_at else None,
            "validation_error": self.validation_error,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "reminder_days_before": self.reminder_days_before,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "key_name": self.key_name,
            "key_prefix": self.key_prefix,
            "needs_renewal": self.needs_renewal_reminder(),
            "days_until_expiry": (self.expires_at - datetime.utcnow()).days if self.expires_at else None,
        }


@dataclass
class CustomerLLMConfig:
    """Configuration for a customer's LLM access."""
    customer_id: str
    billing_model: BillingModel

    # BYOK settings - now stores full metadata including validation status
    byok_keys: Dict[LLMProvider, str] = field(default_factory=dict)  # Legacy: encrypted keys only
    byok_key_metadata: Dict[LLMProvider, BYOKKeyMetadata] = field(default_factory=dict)  # New: full metadata

    # Managed settings
    managed_providers: List[LLMProvider] = field(default_factory=list)
    markup_percentage: float = DEFAULT_MARKUP_PERCENTAGE

    # Prepaid settings
    prepaid_balance_usd: Decimal = Decimal("0.00")
    auto_recharge_threshold: Optional[Decimal] = None
    auto_recharge_amount: Optional[Decimal] = None

    # Limits and controls
    daily_limit_usd: Optional[Decimal] = None
    monthly_limit_usd: Optional[Decimal] = None
    allowed_models: List[str] = field(default_factory=list)
    blocked_models: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "billing_model": self.billing_model.value,
            "managed_providers": [p.value for p in self.managed_providers],
            "markup_percentage": self.markup_percentage,
            "prepaid_balance_usd": str(self.prepaid_balance_usd),
            "daily_limit_usd": str(self.daily_limit_usd) if self.daily_limit_usd else None,
            "monthly_limit_usd": str(self.monthly_limit_usd) if self.monthly_limit_usd else None,
            "allowed_models": self.allowed_models,
            "blocked_models": self.blocked_models,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class LLMUsageRecord:
    """Record of a single LLM API call."""
    id: str
    customer_id: str
    timestamp: datetime

    # Request details
    provider: LLMProvider
    model: str
    usage_type: UsageType

    # Token counts
    input_tokens: int
    output_tokens: int
    total_tokens: int

    # Cost calculation
    raw_cost_usd: Decimal          # What the provider charges
    markup_usd: Decimal            # Our markup (if managed)
    total_cost_usd: Decimal        # What we charge customer

    # Billing
    billing_model: BillingModel
    billed: bool = False
    billed_at: Optional[datetime] = None

    # Context
    agent_name: Optional[str] = None
    session_id: Optional[str] = None
    ticket_id: Optional[str] = None

    # Metadata
    request_id: Optional[str] = None
    latency_ms: Optional[int] = None


@dataclass
class UsageSummary:
    """Aggregated usage summary for billing."""
    customer_id: str
    period_start: datetime
    period_end: datetime

    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    raw_cost_usd: Decimal = Decimal("0.00")
    markup_usd: Decimal = Decimal("0.00")
    total_cost_usd: Decimal = Decimal("0.00")

    by_provider: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_model: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_agent: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# =============================================================================
# Key Encryption Service
# =============================================================================

class KeyEncryptionService:
    """Securely encrypt and decrypt API keys."""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize with encryption key.

        Args:
            encryption_key: Base64-encoded Fernet key. If not provided,
                          reads from LLM_KEY_ENCRYPTION_KEY env var.
        """
        key = encryption_key or os.getenv("LLM_KEY_ENCRYPTION_KEY")
        if not key:
            # Generate a key for development (NOT for production!)
            logger.warning("No encryption key provided, generating ephemeral key")
            key = Fernet.generate_key().decode()

        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string (like an API key)."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string."""
        return self._fernet.decrypt(ciphertext.encode()).decode()

    @staticmethod
    def hash_key(api_key: str) -> str:
        """Create a hash of an API key for logging (never log the actual key)."""
        return hashlib.sha256(api_key.encode()).hexdigest()[:12]


# =============================================================================
# Cost Calculator
# =============================================================================

class LLMCostCalculator:
    """Calculate costs for LLM API calls."""

    def __init__(self, pricing: Dict = None):
        self.pricing = pricing or LLM_PRICING

    def calculate_cost(
        self,
        provider: LLMProvider,
        model: str,
        input_tokens: int,
        output_tokens: int,
        markup_percentage: float = 0.0
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate cost for an LLM call.

        Returns:
            Tuple of (raw_cost, markup, total_cost) in USD
        """
        # Get pricing for this provider/model
        provider_pricing = self.pricing.get(provider, {})
        model_pricing = provider_pricing.get(model)

        if not model_pricing:
            # Try to find a matching model (handle versions like gpt-4o-2024-05-13)
            for known_model, pricing in provider_pricing.items():
                if model.startswith(known_model):
                    model_pricing = pricing
                    break

        if not model_pricing:
            logger.warning(f"No pricing found for {provider.value}/{model}, using estimate")
            model_pricing = {"input": 1.0, "output": 3.0}  # Conservative estimate

        # Calculate raw cost (pricing is per 1M tokens)
        input_cost = Decimal(str(input_tokens)) * Decimal(str(model_pricing["input"])) / Decimal("1000000")
        output_cost = Decimal(str(output_tokens)) * Decimal(str(model_pricing["output"])) / Decimal("1000000")
        raw_cost = input_cost + output_cost

        # Calculate markup
        markup = raw_cost * Decimal(str(markup_percentage)) / Decimal("100")

        # Total cost
        total_cost = raw_cost + markup

        return raw_cost, markup, total_cost

    def estimate_monthly_cost(
        self,
        daily_requests: int,
        avg_input_tokens: int,
        avg_output_tokens: int,
        provider: LLMProvider,
        model: str,
        markup_percentage: float = 0.0
    ) -> Dict[str, Decimal]:
        """Estimate monthly cost for planning."""
        raw, markup, total = self.calculate_cost(
            provider, model,
            avg_input_tokens, avg_output_tokens,
            markup_percentage
        )

        daily_cost = total * daily_requests
        monthly_cost = daily_cost * 30

        return {
            "per_request": total,
            "daily_estimate": daily_cost,
            "monthly_estimate": monthly_cost,
            "raw_cost_monthly": raw * daily_requests * 30,
            "markup_monthly": markup * daily_requests * 30,
        }


# =============================================================================
# Usage Tracker
# =============================================================================

class LLMUsageTracker:
    """Track and store LLM usage for billing."""

    def __init__(self, storage_backend: str = "memory"):
        """
        Initialize tracker.

        Args:
            storage_backend: "memory", "redis", or "postgres"
        """
        self.storage_backend = storage_backend
        self._usage_records: List[LLMUsageRecord] = []
        self._daily_totals: Dict[str, Dict[str, Decimal]] = {}  # customer_id -> date -> total

        self.cost_calculator = LLMCostCalculator()

    async def record_usage(
        self,
        customer_id: str,
        provider: LLMProvider,
        model: str,
        input_tokens: int,
        output_tokens: int,
        usage_type: UsageType = UsageType.CHAT_COMPLETION,
        billing_model: BillingModel = BillingModel.MANAGED,
        markup_percentage: float = DEFAULT_MARKUP_PERCENTAGE,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        request_id: Optional[str] = None,
        latency_ms: Optional[int] = None,
    ) -> LLMUsageRecord:
        """Record an LLM API call for billing."""

        # Calculate costs
        if billing_model == BillingModel.BYOK:
            # BYOK: No cost to us, no charge to customer (they pay provider directly)
            raw_cost = Decimal("0.00")
            markup = Decimal("0.00")
            total_cost = Decimal("0.00")
        else:
            raw_cost, markup, total_cost = self.cost_calculator.calculate_cost(
                provider, model, input_tokens, output_tokens,
                markup_percentage if billing_model == BillingModel.MANAGED else 0.0
            )

        # Create record
        record = LLMUsageRecord(
            id=f"usage_{customer_id}_{int(time.time() * 1000)}_{os.urandom(4).hex()}",
            customer_id=customer_id,
            timestamp=datetime.utcnow(),
            provider=provider,
            model=model,
            usage_type=usage_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            raw_cost_usd=raw_cost,
            markup_usd=markup,
            total_cost_usd=total_cost,
            billing_model=billing_model,
            agent_name=agent_name,
            session_id=session_id,
            ticket_id=ticket_id,
            request_id=request_id,
            latency_ms=latency_ms,
        )

        # Store record
        self._usage_records.append(record)

        # Update daily totals
        date_key = record.timestamp.strftime("%Y-%m-%d")
        if customer_id not in self._daily_totals:
            self._daily_totals[customer_id] = {}
        if date_key not in self._daily_totals[customer_id]:
            self._daily_totals[customer_id][date_key] = Decimal("0.00")
        self._daily_totals[customer_id][date_key] += total_cost

        logger.info(
            f"LLM usage recorded: customer={customer_id} provider={provider.value} "
            f"model={model} tokens={input_tokens}+{output_tokens} cost=${total_cost:.4f}"
        )

        return record

    async def get_usage_summary(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> UsageSummary:
        """Get aggregated usage summary for a period."""

        summary = UsageSummary(
            customer_id=customer_id,
            period_start=start_date,
            period_end=end_date,
        )

        for record in self._usage_records:
            if record.customer_id != customer_id:
                continue
            if record.timestamp < start_date or record.timestamp > end_date:
                continue

            summary.total_requests += 1
            summary.total_input_tokens += record.input_tokens
            summary.total_output_tokens += record.output_tokens
            summary.raw_cost_usd += record.raw_cost_usd
            summary.markup_usd += record.markup_usd
            summary.total_cost_usd += record.total_cost_usd

            # By provider
            provider_key = record.provider.value
            if provider_key not in summary.by_provider:
                summary.by_provider[provider_key] = {
                    "requests": 0, "tokens": 0, "cost": Decimal("0.00")
                }
            summary.by_provider[provider_key]["requests"] += 1
            summary.by_provider[provider_key]["tokens"] += record.total_tokens
            summary.by_provider[provider_key]["cost"] += record.total_cost_usd

            # By model
            if record.model not in summary.by_model:
                summary.by_model[record.model] = {
                    "requests": 0, "tokens": 0, "cost": Decimal("0.00")
                }
            summary.by_model[record.model]["requests"] += 1
            summary.by_model[record.model]["tokens"] += record.total_tokens
            summary.by_model[record.model]["cost"] += record.total_cost_usd

            # By agent
            if record.agent_name:
                if record.agent_name not in summary.by_agent:
                    summary.by_agent[record.agent_name] = {
                        "requests": 0, "tokens": 0, "cost": Decimal("0.00")
                    }
                summary.by_agent[record.agent_name]["requests"] += 1
                summary.by_agent[record.agent_name]["tokens"] += record.total_tokens
                summary.by_agent[record.agent_name]["cost"] += record.total_cost_usd

        return summary

    async def get_daily_spend(self, customer_id: str, date: Optional[datetime] = None) -> Decimal:
        """Get total spend for a specific day."""
        date_key = (date or datetime.utcnow()).strftime("%Y-%m-%d")
        return self._daily_totals.get(customer_id, {}).get(date_key, Decimal("0.00"))

    async def check_limit(
        self,
        customer_id: str,
        config: CustomerLLMConfig,
        additional_cost: Decimal = Decimal("0.00")
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a customer is within their spending limits.

        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        # Check daily limit
        if config.daily_limit_usd:
            daily_spend = await self.get_daily_spend(customer_id)
            if daily_spend + additional_cost > config.daily_limit_usd:
                return False, f"Daily limit of ${config.daily_limit_usd} exceeded"

        # Check monthly limit
        if config.monthly_limit_usd:
            start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
            summary = await self.get_usage_summary(
                customer_id, start_of_month, datetime.utcnow()
            )
            if summary.total_cost_usd + additional_cost > config.monthly_limit_usd:
                return False, f"Monthly limit of ${config.monthly_limit_usd} exceeded"

        # Check prepaid balance
        if config.billing_model == BillingModel.PREPAID:
            if config.prepaid_balance_usd < additional_cost:
                return False, f"Insufficient prepaid balance (${config.prepaid_balance_usd} available)"

        return True, None


# =============================================================================
# Main Billing Service
# =============================================================================

class LLMBillingService:
    """
    Main service for LLM billing and key management.

    Supports multiple billing models:
    - BYOK: Customer provides keys, we just route requests
    - Managed: We manage keys, charge usage + markup
    - Prepaid: Customer buys credits upfront
    """

    def __init__(
        self,
        encryption_key: Optional[str] = None,
        default_markup: float = DEFAULT_MARKUP_PERCENTAGE
    ):
        self.encryption = KeyEncryptionService(encryption_key)
        self.cost_calculator = LLMCostCalculator()
        self.usage_tracker = LLMUsageTracker()
        self.default_markup = default_markup

        # In-memory config storage (replace with database in production)
        self._configs: Dict[str, CustomerLLMConfig] = {}

        # Managed keys storage (encrypted)
        self._managed_keys: Dict[str, Dict[LLMProvider, str]] = {}

    # =========================================================================
    # Customer Configuration
    # =========================================================================

    async def create_customer_config(
        self,
        customer_id: str,
        billing_model: BillingModel,
        **kwargs
    ) -> CustomerLLMConfig:
        """Create or update customer LLM configuration."""

        config = CustomerLLMConfig(
            customer_id=customer_id,
            billing_model=billing_model,
            **kwargs
        )

        self._configs[customer_id] = config

        logger.info(f"Created LLM config for customer {customer_id}: {billing_model.value}")

        return config

    async def get_customer_config(self, customer_id: str) -> Optional[CustomerLLMConfig]:
        """Get customer's LLM configuration."""
        return self._configs.get(customer_id)

    async def update_customer_config(
        self,
        customer_id: str,
        **updates
    ) -> Optional[CustomerLLMConfig]:
        """Update customer's LLM configuration."""
        config = self._configs.get(customer_id)
        if not config:
            return None

        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)

        config.updated_at = datetime.utcnow()
        return config

    # =========================================================================
    # BYOK Key Management
    # =========================================================================

    async def set_byok_key(
        self,
        customer_id: str,
        provider: LLMProvider,
        api_key: str,
        key_name: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        reminder_days_before: int = 7
    ) -> bool:
        """
        Store a customer's BYOK API key (encrypted) with metadata.

        Args:
            customer_id: Customer identifier
            provider: LLM provider (openai, anthropic, etc.)
            api_key: The customer's API key
            key_name: Optional user-friendly name for the key
            expires_at: Optional expiration date for reminder notifications
            reminder_days_before: Days before expiration to send reminder

        Returns:
            True if successful
        """
        config = self._configs.get(customer_id)
        if not config:
            logger.error(f"No config found for customer {customer_id}")
            return False

        if config.billing_model != BillingModel.BYOK:
            logger.error(f"Customer {customer_id} is not on BYOK plan")
            return False

        # Encrypt and store
        encrypted_key = self.encryption.encrypt(api_key)
        config.byok_keys[provider] = encrypted_key

        # Extract key prefix for identification (first 8 chars, masked)
        key_prefix = api_key[:8] + "..." if len(api_key) > 8 else api_key[:4] + "..."

        # Create or update metadata
        now = datetime.utcnow()
        if provider in config.byok_key_metadata:
            # Update existing metadata
            metadata = config.byok_key_metadata[provider]
            metadata.encrypted_key = encrypted_key
            metadata.key_prefix = key_prefix
            metadata.key_name = key_name or metadata.key_name
            metadata.expires_at = expires_at or metadata.expires_at
            metadata.reminder_days_before = reminder_days_before
            metadata.updated_at = now
            # Reset validation since key changed
            metadata.is_valid = None
            metadata.last_validated_at = None
            metadata.validation_error = None
        else:
            # Create new metadata
            config.byok_key_metadata[provider] = BYOKKeyMetadata(
                provider=provider,
                encrypted_key=encrypted_key,
                key_name=key_name,
                key_prefix=key_prefix,
                expires_at=expires_at,
                reminder_days_before=reminder_days_before,
                created_at=now,
                updated_at=now,
            )

        logger.info(
            f"Stored BYOK key for customer {customer_id}, "
            f"provider={provider.value}, key_hash={self.encryption.hash_key(api_key)}"
        )

        return True

    async def get_byok_key(
        self,
        customer_id: str,
        provider: LLMProvider
    ) -> Optional[str]:
        """Get a customer's decrypted BYOK API key."""
        config = self._configs.get(customer_id)
        if not config or provider not in config.byok_keys:
            return None

        encrypted_key = config.byok_keys[provider]
        return self.encryption.decrypt(encrypted_key)

    async def validate_byok_key(
        self,
        customer_id: str,
        provider: LLMProvider
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that a BYOK key works and persist the result.

        The validation result is stored in the key metadata so it persists
        across page refreshes and can be displayed in the UI.
        """
        config = self._configs.get(customer_id)
        api_key = await self.get_byok_key(customer_id, provider)
        if not api_key:
            return False, "No key configured"

        is_valid = False
        error_message = None

        # Test the key based on provider
        try:
            if provider == LLMProvider.OPENAI:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    ) as response:
                        if response.status == 200:
                            is_valid = True
                        elif response.status == 401:
                            error_message = "Invalid API key"
                        else:
                            error_message = f"API error: {response.status}"

            elif provider == LLMProvider.ANTHROPIC:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.anthropic.com/v1/models",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01"
                        }
                    ) as response:
                        if response.status in [200, 403]:  # 403 means valid key, just no access
                            is_valid = True
                        elif response.status == 401:
                            error_message = "Invalid API key"
                        else:
                            error_message = f"API error: {response.status}"

            elif provider == LLMProvider.GROQ:
                # Groq uses OpenAI-compatible API
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.groq.com/openai/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    ) as response:
                        if response.status == 200:
                            is_valid = True
                        elif response.status == 401:
                            error_message = "Invalid API key"
                        else:
                            error_text = await response.text()
                            error_message = f"API error: {response.status} - {error_text[:100]}"

            elif provider == LLMProvider.GOOGLE:
                # Google AI Studio API
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
                    ) as response:
                        if response.status == 200:
                            is_valid = True
                        elif response.status in [400, 401, 403]:
                            error_message = "Invalid API key"
                        else:
                            error_message = f"API error: {response.status}"

            elif provider == LLMProvider.MISTRAL:
                # Mistral API
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.mistral.ai/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    ) as response:
                        if response.status == 200:
                            is_valid = True
                        elif response.status == 401:
                            error_message = "Invalid API key"
                        else:
                            error_message = f"API error: {response.status}"

            elif provider == LLMProvider.COHERE:
                # Cohere API
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://api.cohere.ai/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    ) as response:
                        if response.status == 200:
                            is_valid = True
                        elif response.status == 401:
                            error_message = "Invalid API key"
                        else:
                            error_message = f"API error: {response.status}"

            else:
                # For Azure and AWS, validation is more complex (requires additional config)
                is_valid = True
                error_message = "Key validation not implemented for this provider (requires additional configuration)"

        except Exception as e:
            error_message = f"Validation error: {str(e)}"

        # Persist validation result in metadata
        if config and provider in config.byok_key_metadata:
            metadata = config.byok_key_metadata[provider]
            metadata.is_valid = is_valid
            metadata.last_validated_at = datetime.utcnow()
            metadata.validation_error = error_message
            metadata.updated_at = datetime.utcnow()
            logger.info(f"Persisted validation result for {customer_id}/{provider.value}: valid={is_valid}")

        return is_valid, error_message

    def get_byok_key_metadata(
        self,
        customer_id: str,
        provider: LLMProvider
    ) -> Optional[BYOKKeyMetadata]:
        """Get metadata for a BYOK key."""
        config = self._configs.get(customer_id)
        if not config:
            return None
        return config.byok_key_metadata.get(provider)

    def get_all_byok_key_metadata(
        self,
        customer_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all BYOK keys for a customer."""
        config = self._configs.get(customer_id)
        if not config:
            return {}
        return {
            provider.value: metadata.to_dict()
            for provider, metadata in config.byok_key_metadata.items()
        }

    # =========================================================================
    # Managed Keys
    # =========================================================================

    async def provision_managed_key(
        self,
        customer_id: str,
        provider: LLMProvider,
        api_key: str
    ) -> bool:
        """
        Provision a managed API key for a customer.
        This is a key WE own and provision for the customer.
        """
        config = self._configs.get(customer_id)
        if not config:
            return False

        if config.billing_model not in [BillingModel.MANAGED, BillingModel.ENTERPRISE]:
            logger.error(f"Customer {customer_id} is not on managed plan")
            return False

        # Store encrypted
        if customer_id not in self._managed_keys:
            self._managed_keys[customer_id] = {}

        encrypted_key = self.encryption.encrypt(api_key)
        self._managed_keys[customer_id][provider] = encrypted_key

        # Update config
        if provider not in config.managed_providers:
            config.managed_providers.append(provider)

        logger.info(f"Provisioned managed key for customer {customer_id}, provider={provider.value}")
        return True

    async def get_managed_key(
        self,
        customer_id: str,
        provider: LLMProvider
    ) -> Optional[str]:
        """Get managed API key for a customer."""
        if customer_id not in self._managed_keys:
            return None
        if provider not in self._managed_keys[customer_id]:
            return None

        encrypted_key = self._managed_keys[customer_id][provider]
        return self.encryption.decrypt(encrypted_key)

    # =========================================================================
    # Prepaid Credits
    # =========================================================================

    async def add_prepaid_credits(
        self,
        customer_id: str,
        amount_usd: Decimal,
        payment_reference: Optional[str] = None
    ) -> Decimal:
        """Add prepaid credits to a customer's account."""
        config = self._configs.get(customer_id)
        if not config:
            raise ValueError(f"No config for customer {customer_id}")

        config.prepaid_balance_usd += amount_usd

        logger.info(
            f"Added ${amount_usd} prepaid credits for customer {customer_id}, "
            f"new balance: ${config.prepaid_balance_usd}"
        )

        return config.prepaid_balance_usd

    async def deduct_prepaid_credits(
        self,
        customer_id: str,
        amount_usd: Decimal,
        reason: str = ""
    ) -> Tuple[bool, Decimal]:
        """Deduct prepaid credits from a customer's account."""
        config = self._configs.get(customer_id)
        if not config:
            return False, Decimal("0.00")

        if config.prepaid_balance_usd < amount_usd:
            return False, config.prepaid_balance_usd

        config.prepaid_balance_usd -= amount_usd

        logger.info(
            f"Deducted ${amount_usd} prepaid credits for customer {customer_id} ({reason}), "
            f"remaining: ${config.prepaid_balance_usd}"
        )

        return True, config.prepaid_balance_usd

    # =========================================================================
    # Request Handling (Main Entry Point)
    # =========================================================================

    async def get_api_key_for_request(
        self,
        customer_id: str,
        provider: LLMProvider,
        model: str,
        estimated_tokens: int = 1000
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the appropriate API key for an LLM request.

        This is the main entry point for getting an API key.
        It handles all billing models transparently.

        Returns:
            Tuple of (api_key, error_message)
        """
        config = await self.get_customer_config(customer_id)
        if not config:
            return None, "Customer not configured for LLM access"

        # Check if model is allowed
        if config.blocked_models and model in config.blocked_models:
            return None, f"Model {model} is blocked for this customer"

        if config.allowed_models and model not in config.allowed_models:
            return None, f"Model {model} is not in allowed list"

        # Estimate cost and check limits
        _, _, estimated_cost = self.cost_calculator.calculate_cost(
            provider, model,
            estimated_tokens, estimated_tokens,  # Rough estimate
            config.markup_percentage if config.billing_model == BillingModel.MANAGED else 0
        )

        allowed, reason = await self.usage_tracker.check_limit(
            customer_id, config, estimated_cost
        )
        if not allowed:
            return None, reason

        # Get API key based on billing model
        if config.billing_model == BillingModel.BYOK:
            api_key = await self.get_byok_key(customer_id, provider)
            if not api_key:
                return None, f"No BYOK key configured for {provider.value}"
            return api_key, None

        elif config.billing_model in [BillingModel.MANAGED, BillingModel.PREPAID, BillingModel.ENTERPRISE]:
            api_key = await self.get_managed_key(customer_id, provider)
            if not api_key:
                # Fall back to platform default keys
                api_key = os.getenv(f"{provider.value.upper()}_API_KEY")

            if not api_key:
                return None, f"No managed key available for {provider.value}"
            return api_key, None

        return None, "Unknown billing model"

    async def record_request_usage(
        self,
        customer_id: str,
        provider: LLMProvider,
        model: str,
        input_tokens: int,
        output_tokens: int,
        **kwargs
    ) -> LLMUsageRecord:
        """Record usage after an LLM request completes."""
        config = await self.get_customer_config(customer_id)
        if not config:
            raise ValueError(f"No config for customer {customer_id}")

        # Record usage
        record = await self.usage_tracker.record_usage(
            customer_id=customer_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            billing_model=config.billing_model,
            markup_percentage=config.markup_percentage,
            **kwargs
        )

        # Deduct from prepaid balance if applicable
        if config.billing_model == BillingModel.PREPAID:
            await self.deduct_prepaid_credits(
                customer_id,
                record.total_cost_usd,
                f"LLM usage: {model}"
            )

            # Check auto-recharge
            if (config.auto_recharge_threshold and
                config.prepaid_balance_usd < config.auto_recharge_threshold):
                # Trigger auto-recharge (in production, this would call payment API)
                logger.info(f"Auto-recharge triggered for customer {customer_id}")

        return record

    # =========================================================================
    # Billing & Reporting
    # =========================================================================

    async def get_billing_summary(
        self,
        customer_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get billing summary for a customer."""
        config = await self.get_customer_config(customer_id)
        if not config:
            return {"error": "Customer not found"}

        # Default to current month
        if not start_date:
            start_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        if not end_date:
            end_date = datetime.utcnow()

        summary = await self.usage_tracker.get_usage_summary(
            customer_id, start_date, end_date
        )

        return {
            "customer_id": customer_id,
            "billing_model": config.billing_model.value,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "usage": {
                "total_requests": summary.total_requests,
                "total_tokens": summary.total_input_tokens + summary.total_output_tokens,
                "input_tokens": summary.total_input_tokens,
                "output_tokens": summary.total_output_tokens,
            },
            "costs": {
                "raw_cost_usd": float(summary.raw_cost_usd),
                "markup_usd": float(summary.markup_usd),
                "total_cost_usd": float(summary.total_cost_usd),
            },
            "breakdown": {
                "by_provider": {k: {
                    "requests": v["requests"],
                    "tokens": v["tokens"],
                    "cost_usd": float(v["cost"])
                } for k, v in summary.by_provider.items()},
                "by_model": {k: {
                    "requests": v["requests"],
                    "tokens": v["tokens"],
                    "cost_usd": float(v["cost"])
                } for k, v in summary.by_model.items()},
                "by_agent": {k: {
                    "requests": v["requests"],
                    "tokens": v["tokens"],
                    "cost_usd": float(v["cost"])
                } for k, v in summary.by_agent.items()},
            },
            "limits": {
                "daily_limit_usd": float(config.daily_limit_usd) if config.daily_limit_usd else None,
                "monthly_limit_usd": float(config.monthly_limit_usd) if config.monthly_limit_usd else None,
            },
            "prepaid_balance_usd": float(config.prepaid_balance_usd) if config.billing_model == BillingModel.PREPAID else None,
        }

    async def generate_invoice_data(
        self,
        customer_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime
    ) -> Dict[str, Any]:
        """Generate invoice data for billing integration."""
        summary = await self.get_billing_summary(
            customer_id, billing_period_start, billing_period_end
        )

        config = await self.get_customer_config(customer_id)

        line_items = []

        # Add line items by model
        for model, data in summary.get("breakdown", {}).get("by_model", {}).items():
            line_items.append({
                "description": f"LLM Usage - {model}",
                "quantity": data["requests"],
                "unit": "requests",
                "unit_price": data["cost_usd"] / data["requests"] if data["requests"] > 0 else 0,
                "total": data["cost_usd"],
            })

        return {
            "customer_id": customer_id,
            "billing_period": {
                "start": billing_period_start.isoformat(),
                "end": billing_period_end.isoformat(),
            },
            "line_items": line_items,
            "subtotal": summary.get("costs", {}).get("raw_cost_usd", 0),
            "markup": summary.get("costs", {}).get("markup_usd", 0),
            "total": summary.get("costs", {}).get("total_cost_usd", 0),
            "currency": "USD",
            "billing_model": config.billing_model.value if config else "unknown",
        }


# =============================================================================
# Factory and Singleton
# =============================================================================

_billing_service: Optional[LLMBillingService] = None


def get_llm_billing_service() -> LLMBillingService:
    """Get the global LLM billing service instance."""
    global _billing_service
    if _billing_service is None:
        _billing_service = LLMBillingService()
    return _billing_service


# =============================================================================
# Example Usage
# =============================================================================

async def example_usage():
    """Demonstrate how to use the LLM billing service."""

    service = get_llm_billing_service()

    # === BYOK Customer ===
    # Customer brings their own OpenAI key
    await service.create_customer_config(
        customer_id="cust_byok_123",
        billing_model=BillingModel.BYOK,
        daily_limit_usd=Decimal("50.00"),
    )
    await service.set_byok_key(
        "cust_byok_123",
        LLMProvider.OPENAI,
        "sk-..."  # Customer's key
    )

    # When making requests:
    api_key, error = await service.get_api_key_for_request(
        "cust_byok_123",
        LLMProvider.OPENAI,
        "gpt-4o"
    )
    # Use api_key to make request...
    # No cost to us, customer pays OpenAI directly


    # === Managed Customer ===
    # We manage keys, charge usage + 15% markup
    await service.create_customer_config(
        customer_id="cust_managed_456",
        billing_model=BillingModel.MANAGED,
        markup_percentage=15.0,
        daily_limit_usd=Decimal("100.00"),
        monthly_limit_usd=Decimal("2000.00"),
    )
    # We provision our own key for them
    await service.provision_managed_key(
        "cust_managed_456",
        LLMProvider.OPENAI,
        os.getenv("OPENAI_API_KEY_POOL_1")  # Our pooled key
    )

    # When making requests:
    api_key, error = await service.get_api_key_for_request(
        "cust_managed_456",
        LLMProvider.OPENAI,
        "gpt-4o"
    )
    # After request completes, record usage:
    await service.record_request_usage(
        "cust_managed_456",
        LLMProvider.OPENAI,
        "gpt-4o",
        input_tokens=500,
        output_tokens=200,
        agent_name="triage_agent"
    )
    # We charge them: raw_cost + 15% markup


    # === Prepaid Customer ===
    await service.create_customer_config(
        customer_id="cust_prepaid_789",
        billing_model=BillingModel.PREPAID,
        auto_recharge_threshold=Decimal("50.00"),
        auto_recharge_amount=Decimal("200.00"),
    )
    await service.add_prepaid_credits("cust_prepaid_789", Decimal("500.00"))

    # Usage deducted from prepaid balance automatically


    # === Get Billing Summary ===
    summary = await service.get_billing_summary("cust_managed_456")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(example_usage())
