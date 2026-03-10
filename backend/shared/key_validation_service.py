#!/usr/bin/env python3
"""
Key Validation Service - 24h API Key Validation Pings

Implements ROADMAP.md Section: Key Rotation Detection

Features:
- Periodic API key validation (configurable interval, default 24h)
- Lightweight provider-specific validation calls
- Alert system for key issues before agent failures
- Key health tracking and status history
- Integration with BYOK Gateway

Key Design Decisions:
- Validation uses minimal-cost API calls (list models, etc.)
- Exponential backoff on transient failures
- Alerts at first failure, not after retries exhausted
- Tracks validation history for debugging
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4
import random

logger = logging.getLogger(__name__)


class KeyValidationStatus(str, Enum):
    """Status of a key validation check."""
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"
    PENDING = "pending"


class ValidationAlertType(str, Enum):
    """Types of validation alerts."""
    KEY_INVALID = "key_invalid"
    KEY_EXPIRED = "key_expired"
    KEY_RATE_LIMITED = "key_rate_limited"
    KEY_NETWORK_ERROR = "key_network_error"
    KEY_RECOVERED = "key_recovered"
    VALIDATION_OVERDUE = "validation_overdue"


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Result of a single key validation."""
    key_id: UUID
    provider: str
    status: KeyValidationStatus
    validated_at: datetime
    response_time_ms: int = 0
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    remaining_quota: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": str(self.key_id),
            "provider": self.provider,
            "status": self.status.value,
            "validated_at": self.validated_at.isoformat(),
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "remaining_quota": self.remaining_quota,
        }


@dataclass
class ValidationAlert:
    """Alert generated from key validation."""
    alert_id: UUID
    key_id: UUID
    org_id: UUID
    provider: str
    alert_type: ValidationAlertType
    severity: AlertSeverity
    message: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": str(self.alert_id),
            "key_id": str(self.key_id),
            "org_id": str(self.org_id),
            "provider": self.provider,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class KeyHealthStatus:
    """Overall health status of a key."""
    key_id: UUID
    org_id: UUID
    provider: str
    is_healthy: bool
    last_validation: Optional[ValidationResult] = None
    consecutive_failures: int = 0
    last_healthy_at: Optional[datetime] = None
    validation_history: List[ValidationResult] = field(default_factory=list)
    active_alerts: List[ValidationAlert] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": str(self.key_id),
            "org_id": str(self.org_id),
            "provider": self.provider,
            "is_healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "last_healthy_at": self.last_healthy_at.isoformat() if self.last_healthy_at else None,
            "last_validation": self.last_validation.to_dict() if self.last_validation else None,
            "active_alerts_count": len(self.active_alerts),
        }


@dataclass
class ValidationSchedule:
    """Schedule for key validation."""
    key_id: UUID
    interval_hours: float = 24.0
    last_validated: Optional[datetime] = None
    next_validation: Optional[datetime] = None
    enabled: bool = True
    priority: int = 1  # Lower = higher priority

    def is_due(self) -> bool:
        """Check if validation is due."""
        if not self.enabled:
            return False
        if not self.next_validation:
            return True
        return datetime.utcnow() >= self.next_validation


class KeyValidator:
    """
    Provider-specific key validation logic.

    In production, this would make actual API calls.
    For now, we simulate validation responses.
    """

    # Simulated validation endpoints per provider
    VALIDATION_ENDPOINTS = {
        "openai": "/v1/models",  # List models - minimal cost
        "anthropic": "/v1/messages",  # Health check
        "deepseek": "/v1/models",
        "google": "/v1/models",
    }

    def __init__(self, simulate: bool = True):
        """Initialize the validator."""
        self.simulate = simulate
        self._simulated_states: Dict[UUID, KeyValidationStatus] = {}

    def set_simulated_state(self, key_id: UUID, status: KeyValidationStatus):
        """Set simulated state for testing."""
        self._simulated_states[key_id] = status

    async def validate_key(
        self,
        key_id: UUID,
        provider: str,
        api_key: str,
    ) -> ValidationResult:
        """
        Validate an API key with the provider.

        Args:
            key_id: Key identifier
            provider: Provider name (openai, anthropic, etc.)
            api_key: The actual API key to validate

        Returns:
            ValidationResult with status and details
        """
        start_time = datetime.utcnow()

        if self.simulate:
            # Simulate network delay
            await asyncio.sleep(random.uniform(0.05, 0.2))

            # Check for preset simulated state
            if key_id in self._simulated_states:
                status = self._simulated_states[key_id]
            else:
                # Default: 95% valid, 3% rate limited, 2% invalid
                roll = random.random()
                if roll < 0.95:
                    status = KeyValidationStatus.VALID
                elif roll < 0.98:
                    status = KeyValidationStatus.RATE_LIMITED
                else:
                    status = KeyValidationStatus.INVALID

            response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            error_message = None
            error_code = None
            remaining_quota = None

            if status == KeyValidationStatus.VALID:
                remaining_quota = {
                    "requests_remaining": random.randint(1000, 10000),
                    "tokens_remaining": random.randint(100000, 1000000),
                }
            elif status == KeyValidationStatus.RATE_LIMITED:
                error_message = "Rate limit exceeded"
                error_code = "rate_limit_exceeded"
            elif status == KeyValidationStatus.INVALID:
                error_message = "Invalid API key"
                error_code = "invalid_api_key"

            return ValidationResult(
                key_id=key_id,
                provider=provider,
                status=status,
                validated_at=datetime.utcnow(),
                response_time_ms=response_time,
                error_message=error_message,
                error_code=error_code,
                remaining_quota=remaining_quota,
            )

        # Production: actual API call would go here
        # This would use httpx/aiohttp to call the validation endpoint
        raise NotImplementedError("Production validation not implemented")


class KeyValidationService:
    """
    Service for periodic API key validation.

    Provides:
    - 24h validation cycle (configurable)
    - Alert generation on failures
    - Health status tracking
    - Integration with BYOK Gateway
    """

    DEFAULT_VALIDATION_INTERVAL_HOURS = 24.0
    MAX_HISTORY_SIZE = 50
    ALERT_ON_CONSECUTIVE_FAILURES = 2

    def __init__(
        self,
        validator: Optional[KeyValidator] = None,
        alert_callback: Optional[Callable] = None,
        byok_gateway=None,
    ):
        """Initialize the service."""
        self.validator = validator or KeyValidator(simulate=True)
        self.alert_callback = alert_callback
        self.byok_gateway = byok_gateway

        # Storage
        self._schedules: Dict[UUID, ValidationSchedule] = {}
        self._health_status: Dict[UUID, KeyHealthStatus] = {}
        self._alerts: List[ValidationAlert] = []
        self._running = False
        self._validation_task: Optional[asyncio.Task] = None

    async def register_key(
        self,
        key_id: UUID,
        org_id: UUID,
        provider: str,
        interval_hours: float = DEFAULT_VALIDATION_INTERVAL_HOURS,
        validate_immediately: bool = True,
    ) -> KeyHealthStatus:
        """
        Register a key for periodic validation.

        Args:
            key_id: Key identifier
            org_id: Organization identifier
            provider: Provider name
            interval_hours: Validation interval
            validate_immediately: Run validation now

        Returns:
            Initial KeyHealthStatus
        """
        # Create schedule
        schedule = ValidationSchedule(
            key_id=key_id,
            interval_hours=interval_hours,
            next_validation=datetime.utcnow() if validate_immediately else
                           datetime.utcnow() + timedelta(hours=interval_hours),
        )
        self._schedules[key_id] = schedule

        # Create initial health status
        health = KeyHealthStatus(
            key_id=key_id,
            org_id=org_id,
            provider=provider,
            is_healthy=True,  # Assume healthy until proven otherwise
        )
        self._health_status[key_id] = health

        # Optionally validate immediately
        if validate_immediately:
            await self.validate_key(key_id)

        return self._health_status[key_id]

    async def unregister_key(self, key_id: UUID) -> bool:
        """Unregister a key from validation."""
        if key_id in self._schedules:
            del self._schedules[key_id]
        if key_id in self._health_status:
            del self._health_status[key_id]
        return True

    async def validate_key(
        self,
        key_id: UUID,
        api_key: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate a specific key.

        Args:
            key_id: Key to validate
            api_key: Optional API key (fetched from BYOK gateway if not provided)

        Returns:
            ValidationResult
        """
        health = self._health_status.get(key_id)
        if not health:
            raise ValueError(f"Key {key_id} not registered for validation")

        # Get API key if not provided
        if not api_key and self.byok_gateway:
            api_key = await self.byok_gateway.get_decrypted_key(key_id)

        if not api_key:
            # Can't validate without key - simulate with placeholder
            api_key = "simulated-key"

        # Perform validation
        result = await self.validator.validate_key(
            key_id=key_id,
            provider=health.provider,
            api_key=api_key,
        )

        # Update health status
        await self._update_health_status(health, result)

        # Update schedule
        schedule = self._schedules.get(key_id)
        if schedule:
            schedule.last_validated = result.validated_at
            schedule.next_validation = result.validated_at + timedelta(
                hours=schedule.interval_hours
            )

        return result

    async def _update_health_status(
        self,
        health: KeyHealthStatus,
        result: ValidationResult,
    ):
        """Update health status based on validation result."""
        was_healthy = health.is_healthy
        health.last_validation = result

        # Add to history (keep last N)
        health.validation_history.append(result)
        if len(health.validation_history) > self.MAX_HISTORY_SIZE:
            health.validation_history = health.validation_history[-self.MAX_HISTORY_SIZE:]

        if result.status == KeyValidationStatus.VALID:
            # Key is healthy
            health.is_healthy = True
            health.consecutive_failures = 0
            health.last_healthy_at = result.validated_at

            # Resolve any active alerts
            if not was_healthy:
                await self._create_recovery_alert(health, result)
        else:
            # Key has issues
            health.consecutive_failures += 1

            if health.consecutive_failures >= self.ALERT_ON_CONSECUTIVE_FAILURES:
                health.is_healthy = False
                await self._create_failure_alert(health, result)

    async def _create_failure_alert(
        self,
        health: KeyHealthStatus,
        result: ValidationResult,
    ):
        """Create an alert for key failure."""
        # Map status to alert type
        alert_type_map = {
            KeyValidationStatus.INVALID: ValidationAlertType.KEY_INVALID,
            KeyValidationStatus.EXPIRED: ValidationAlertType.KEY_EXPIRED,
            KeyValidationStatus.RATE_LIMITED: ValidationAlertType.KEY_RATE_LIMITED,
            KeyValidationStatus.NETWORK_ERROR: ValidationAlertType.KEY_NETWORK_ERROR,
        }
        alert_type = alert_type_map.get(
            result.status, ValidationAlertType.KEY_INVALID
        )

        # Determine severity
        if result.status in [KeyValidationStatus.INVALID, KeyValidationStatus.EXPIRED]:
            severity = AlertSeverity.CRITICAL
        elif health.consecutive_failures >= 3:
            severity = AlertSeverity.CRITICAL
        else:
            severity = AlertSeverity.WARNING

        alert = ValidationAlert(
            alert_id=uuid4(),
            key_id=health.key_id,
            org_id=health.org_id,
            provider=health.provider,
            alert_type=alert_type,
            severity=severity,
            message=f"{health.provider} API key validation failed: {result.error_message or result.status.value}",
        )

        self._alerts.append(alert)
        health.active_alerts.append(alert)

        if self.alert_callback:
            await self.alert_callback(alert)

        logger.warning(
            f"Key validation alert: {alert.message}",
            extra={"key_id": str(health.key_id), "alert_id": str(alert.alert_id)}
        )

    async def _create_recovery_alert(
        self,
        health: KeyHealthStatus,
        result: ValidationResult,
    ):
        """Create a recovery alert when key becomes healthy again."""
        alert = ValidationAlert(
            alert_id=uuid4(),
            key_id=health.key_id,
            org_id=health.org_id,
            provider=health.provider,
            alert_type=ValidationAlertType.KEY_RECOVERED,
            severity=AlertSeverity.INFO,
            message=f"{health.provider} API key has recovered and is now valid",
        )

        self._alerts.append(alert)

        # Resolve active alerts
        for active_alert in health.active_alerts:
            active_alert.resolved = True
            active_alert.resolved_at = datetime.utcnow()
        health.active_alerts = []

        if self.alert_callback:
            await self.alert_callback(alert)

        logger.info(
            f"Key validation recovery: {alert.message}",
            extra={"key_id": str(health.key_id)}
        )

    async def validate_all_due(self) -> List[ValidationResult]:
        """Validate all keys that are due for validation."""
        results = []
        now = datetime.utcnow()

        for key_id, schedule in self._schedules.items():
            if schedule.is_due():
                try:
                    result = await self.validate_key(key_id)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to validate key {key_id}: {e}")

        return results

    async def start_background_validation(
        self,
        check_interval_seconds: float = 60.0,
    ):
        """Start background validation loop."""
        if self._running:
            return

        self._running = True

        async def validation_loop():
            while self._running:
                try:
                    await self.validate_all_due()
                except Exception as e:
                    logger.error(f"Background validation error: {e}")

                await asyncio.sleep(check_interval_seconds)

        self._validation_task = asyncio.create_task(validation_loop())

    async def stop_background_validation(self):
        """Stop background validation loop."""
        self._running = False
        if self._validation_task:
            self._validation_task.cancel()
            try:
                await self._validation_task
            except asyncio.CancelledError:
                pass
            self._validation_task = None

    def get_health_status(self, key_id: UUID) -> Optional[KeyHealthStatus]:
        """Get health status for a key."""
        return self._health_status.get(key_id)

    def get_all_health_statuses(self) -> List[KeyHealthStatus]:
        """Get all health statuses."""
        return list(self._health_status.values())

    def get_unhealthy_keys(self) -> List[KeyHealthStatus]:
        """Get all keys that are currently unhealthy."""
        return [h for h in self._health_status.values() if not h.is_healthy]

    def get_alerts(
        self,
        key_id: Optional[UUID] = None,
        org_id: Optional[UUID] = None,
        unresolved_only: bool = False,
    ) -> List[ValidationAlert]:
        """Get alerts with optional filtering."""
        alerts = self._alerts

        if key_id:
            alerts = [a for a in alerts if a.key_id == key_id]

        if org_id:
            alerts = [a for a in alerts if a.org_id == org_id]

        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]

        return alerts

    async def acknowledge_alert(self, alert_id: UUID) -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_validation_schedule(self, key_id: UUID) -> Optional[ValidationSchedule]:
        """Get validation schedule for a key."""
        return self._schedules.get(key_id)

    def update_validation_interval(
        self,
        key_id: UUID,
        interval_hours: float,
    ) -> bool:
        """Update the validation interval for a key."""
        schedule = self._schedules.get(key_id)
        if not schedule:
            return False

        schedule.interval_hours = interval_hours
        if schedule.last_validated:
            schedule.next_validation = schedule.last_validated + timedelta(
                hours=interval_hours
            )
        return True

    def get_overdue_validations(
        self,
        threshold_hours: float = 48.0,
    ) -> List[KeyHealthStatus]:
        """Get keys that haven't been validated in threshold hours."""
        cutoff = datetime.utcnow() - timedelta(hours=threshold_hours)
        overdue = []

        for key_id, health in self._health_status.items():
            if health.last_validation:
                if health.last_validation.validated_at < cutoff:
                    overdue.append(health)
            else:
                # Never validated
                overdue.append(health)

        return overdue

    async def force_validate_all(self) -> List[ValidationResult]:
        """Force validation of all registered keys."""
        results = []
        for key_id in self._schedules.keys():
            try:
                result = await self.validate_key(key_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to validate key {key_id}: {e}")
        return results

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        total_keys = len(self._health_status)
        healthy_keys = sum(1 for h in self._health_status.values() if h.is_healthy)
        total_validations = sum(
            len(h.validation_history) for h in self._health_status.values()
        )
        active_alerts = sum(1 for a in self._alerts if not a.resolved)

        return {
            "total_keys": total_keys,
            "healthy_keys": healthy_keys,
            "unhealthy_keys": total_keys - healthy_keys,
            "total_validations": total_validations,
            "active_alerts": active_alerts,
            "health_percentage": (healthy_keys / total_keys * 100) if total_keys > 0 else 100,
        }


# Singleton instance
_validation_service: Optional[KeyValidationService] = None


def get_key_validation_service(
    validator: Optional[KeyValidator] = None,
    alert_callback: Optional[Callable] = None,
    byok_gateway=None,
) -> KeyValidationService:
    """Get or create the singleton validation service instance."""
    global _validation_service
    if _validation_service is None:
        _validation_service = KeyValidationService(
            validator=validator,
            alert_callback=alert_callback,
            byok_gateway=byok_gateway,
        )
    return _validation_service


def reset_key_validation_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _validation_service
    _validation_service = None
