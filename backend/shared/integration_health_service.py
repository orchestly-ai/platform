#!/usr/bin/env python3
"""
Integration Health Checker Service

Implements ROADMAP.md Section: Integration Credential Health Checks

Features:
- Daily credential validation pings
- Health endpoints per integration
- Proactive alerting before failure
- Background job scheduling
- Health status tracking with history

Key Design Decisions:
- Uses each integration's test_connection() method
- Tracks consecutive failures for alerting
- Supports health check intervals per integration
- Alerts on 401 (expired), 403 (permissions), and network failures
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4
import logging

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status for integration credentials."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    WARNING = "warning"
    UNKNOWN = "unknown"
    CHECKING = "checking"


class HealthCheckReason(str, Enum):
    """Reason for health check failure."""
    CREDENTIAL_EXPIRED = "credential_expired"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    healthy: bool
    status: HealthStatus
    reason: Optional[str] = None
    reason_code: Optional[HealthCheckReason] = None
    response_time_ms: Optional[float] = None
    checked_at: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "status": self.status.value,
            "reason": self.reason,
            "reason_code": self.reason_code.value if self.reason_code else None,
            "response_time_ms": self.response_time_ms,
            "checked_at": self.checked_at.isoformat(),
            "skipped": self.skipped,
            "warning": self.warning,
        }


@dataclass
class IntegrationCredential:
    """Represents an integration credential to check."""
    credential_id: UUID
    integration_name: str
    org_id: UUID
    status: str
    last_health_check: Optional[datetime] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    health_message: Optional[str] = None
    consecutive_failures: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "credential_id": str(self.credential_id),
            "integration_name": self.integration_name,
            "org_id": str(self.org_id),
            "status": self.status,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "health_status": self.health_status.value,
            "health_message": self.health_message,
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class HealthAlert:
    """Alert generated for unhealthy credentials."""
    alert_id: UUID
    credential_id: UUID
    integration_name: str
    org_id: UUID
    alert_type: str  # "credential_expired", "permissions_changed", etc.
    message: str
    severity: str  # "warning", "critical"
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": str(self.alert_id),
            "credential_id": str(self.credential_id),
            "integration_name": self.integration_name,
            "org_id": str(self.org_id),
            "alert_type": self.alert_type,
            "message": self.message,
            "severity": self.severity,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
        }


@dataclass
class HealthCheckStats:
    """Statistics for health check runs."""
    total_checked: int = 0
    healthy_count: int = 0
    unhealthy_count: int = 0
    warning_count: int = 0
    skipped_count: int = 0
    alerts_sent: int = 0
    duration_ms: float = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_checked": self.total_checked,
            "healthy_count": self.healthy_count,
            "unhealthy_count": self.unhealthy_count,
            "warning_count": self.warning_count,
            "skipped_count": self.skipped_count,
            "alerts_sent": self.alerts_sent,
            "duration_ms": self.duration_ms,
        }


class IntegrationHealthService:
    """
    Service for checking and managing integration credential health.

    Implements daily credential validation with proactive alerting.
    """

    # Health check interval per integration (default 24 hours)
    DEFAULT_CHECK_INTERVAL_HOURS = 24

    # Number of consecutive failures before alerting
    FAILURE_THRESHOLD_WARNING = 1
    FAILURE_THRESHOLD_CRITICAL = 3

    # Request timeout for health checks
    HEALTH_CHECK_TIMEOUT_SECONDS = 30

    # Health endpoints for each integration type
    HEALTH_ENDPOINTS: Dict[str, Dict[str, str]] = {
        "slack": {"method": "POST", "path": "auth.test"},
        "salesforce": {"method": "GET", "path": "/services/data/v57.0/limits"},
        "github": {"method": "GET", "path": "/user"},
        "hubspot": {"method": "GET", "path": "/crm/v3/objects/contacts?limit=1"},
        "zendesk": {"method": "GET", "path": "/api/v2/users/me.json"},
        "stripe": {"method": "GET", "path": "/v1/balance"},
        "sendgrid": {"method": "GET", "path": "/v3/user/profile"},
        "twilio": {"method": "GET", "path": "/2010-04-01/Accounts.json"},
        "google_sheets": {"method": "GET", "path": "/v4/spreadsheets"},
        "aws_s3": {"method": "GET", "path": "/"},
    }

    def __init__(
        self,
        db=None,
        integration_factory: Optional[Callable] = None,
        alert_callback: Optional[Callable] = None,
    ):
        """
        Initialize the health service.

        Args:
            db: Database connection (optional for testing)
            integration_factory: Factory to create integration instances
            alert_callback: Callback for sending alerts
        """
        self.db = db
        self.integration_factory = integration_factory
        self.alert_callback = alert_callback

        # In-memory storage for testing
        self._credentials: Dict[UUID, IntegrationCredential] = {}
        self._health_history: Dict[UUID, List[HealthCheckResult]] = {}
        self._alerts: List[HealthAlert] = []
        self._last_check_run: Optional[HealthCheckStats] = None

    async def register_credential(
        self,
        credential_id: UUID,
        integration_name: str,
        org_id: UUID,
        status: str = "active",
    ) -> IntegrationCredential:
        """Register a credential for health monitoring."""
        cred = IntegrationCredential(
            credential_id=credential_id,
            integration_name=integration_name,
            org_id=org_id,
            status=status,
        )
        self._credentials[credential_id] = cred
        self._health_history[credential_id] = []
        return cred

    async def check_all_credentials(
        self,
        force: bool = False,
    ) -> HealthCheckStats:
        """
        Run health checks on all active credentials.

        Args:
            force: Force check even if recently checked

        Returns:
            Statistics about the health check run
        """
        stats = HealthCheckStats(started_at=datetime.utcnow())
        start_time = datetime.utcnow()

        # Get credentials that need checking
        credentials = await self._get_credentials_to_check(force)

        for cred in credentials:
            stats.total_checked += 1

            # Check the credential
            result = await self.check_credential(cred.credential_id)

            # Update stats
            if result.skipped:
                stats.skipped_count += 1
            elif result.healthy:
                if result.warning:
                    stats.warning_count += 1
                else:
                    stats.healthy_count += 1
            else:
                stats.unhealthy_count += 1

            # Handle alerts
            alert = await self._handle_check_result(cred, result)
            if alert:
                stats.alerts_sent += 1

        stats.completed_at = datetime.utcnow()
        stats.duration_ms = (stats.completed_at - start_time).total_seconds() * 1000
        self._last_check_run = stats

        return stats

    async def check_credential(
        self,
        credential_id: UUID,
    ) -> HealthCheckResult:
        """
        Check health of a specific credential.

        Args:
            credential_id: The credential to check

        Returns:
            HealthCheckResult with the check outcome
        """
        cred = self._credentials.get(credential_id)
        if not cred:
            return HealthCheckResult(
                healthy=False,
                status=HealthStatus.UNKNOWN,
                reason="Credential not found",
                reason_code=HealthCheckReason.UNKNOWN_ERROR,
            )

        # Check if integration type is supported
        if cred.integration_name not in self.HEALTH_ENDPOINTS:
            return HealthCheckResult(
                healthy=True,
                status=HealthStatus.HEALTHY,
                skipped=True,
                reason=f"No health endpoint for {cred.integration_name}",
            )

        start_time = datetime.utcnow()

        try:
            # Use integration factory if available, otherwise simulate
            if self.integration_factory:
                integration = await self.integration_factory(
                    cred.integration_name,
                    credential_id,
                )
                test_result = await asyncio.wait_for(
                    integration.test_connection(),
                    timeout=self.HEALTH_CHECK_TIMEOUT_SECONDS,
                )

                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                if test_result.success:
                    result = HealthCheckResult(
                        healthy=True,
                        status=HealthStatus.HEALTHY,
                        response_time_ms=response_time,
                        details=test_result.data or {},
                    )
                else:
                    reason_code = self._classify_error(
                        test_result.error_code,
                        test_result.error_message,
                    )
                    result = HealthCheckResult(
                        healthy=False,
                        status=HealthStatus.UNHEALTHY,
                        reason=test_result.error_message,
                        reason_code=reason_code,
                        response_time_ms=response_time,
                    )
            else:
                # Mock successful check for testing
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                result = HealthCheckResult(
                    healthy=True,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                )

        except asyncio.TimeoutError:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = HealthCheckResult(
                healthy=False,
                status=HealthStatus.UNHEALTHY,
                reason=f"Health check timed out after {self.HEALTH_CHECK_TIMEOUT_SECONDS}s",
                reason_code=HealthCheckReason.TIMEOUT,
                response_time_ms=response_time,
            )

        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = HealthCheckResult(
                healthy=False,
                status=HealthStatus.UNHEALTHY,
                reason=str(e),
                reason_code=HealthCheckReason.UNKNOWN_ERROR,
                response_time_ms=response_time,
            )

        # Update credential state
        await self._update_credential_health(cred, result)

        # Store in history
        if credential_id in self._health_history:
            self._health_history[credential_id].append(result)
            # Keep last 100 results
            if len(self._health_history[credential_id]) > 100:
                self._health_history[credential_id] = self._health_history[credential_id][-100:]

        return result

    async def simulate_check_failure(
        self,
        credential_id: UUID,
        reason: str,
        reason_code: HealthCheckReason,
    ) -> HealthCheckResult:
        """Simulate a check failure for testing."""
        cred = self._credentials.get(credential_id)
        if not cred:
            return HealthCheckResult(
                healthy=False,
                status=HealthStatus.UNKNOWN,
                reason="Credential not found",
            )

        result = HealthCheckResult(
            healthy=False,
            status=HealthStatus.UNHEALTHY,
            reason=reason,
            reason_code=reason_code,
        )

        await self._update_credential_health(cred, result)

        if credential_id in self._health_history:
            self._health_history[credential_id].append(result)

        # Generate alert
        await self._handle_check_result(cred, result)

        return result

    async def simulate_check_warning(
        self,
        credential_id: UUID,
        warning: str,
    ) -> HealthCheckResult:
        """Simulate a check with warning for testing."""
        cred = self._credentials.get(credential_id)
        if not cred:
            return HealthCheckResult(
                healthy=False,
                status=HealthStatus.UNKNOWN,
                reason="Credential not found",
            )

        result = HealthCheckResult(
            healthy=True,
            status=HealthStatus.WARNING,
            warning=warning,
        )

        await self._update_credential_health(cred, result)

        if credential_id in self._health_history:
            self._health_history[credential_id].append(result)

        return result

    def get_credential(self, credential_id: UUID) -> Optional[IntegrationCredential]:
        """Get a credential by ID."""
        return self._credentials.get(credential_id)

    def get_all_credentials(self) -> List[IntegrationCredential]:
        """Get all registered credentials."""
        return list(self._credentials.values())

    def get_health_history(
        self,
        credential_id: UUID,
        limit: int = 10,
    ) -> List[HealthCheckResult]:
        """Get health check history for a credential."""
        history = self._health_history.get(credential_id, [])
        return history[-limit:] if limit else history

    def get_alerts(
        self,
        unacknowledged_only: bool = False,
        credential_id: Optional[UUID] = None,
    ) -> List[HealthAlert]:
        """Get alerts, optionally filtered."""
        alerts = self._alerts

        if credential_id:
            alerts = [a for a in alerts if a.credential_id == credential_id]

        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]

        return alerts

    async def acknowledge_alert(self, alert_id: UUID) -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_last_check_stats(self) -> Optional[HealthCheckStats]:
        """Get statistics from the last check run."""
        return self._last_check_run

    def get_unhealthy_credentials(self) -> List[IntegrationCredential]:
        """Get all credentials with unhealthy status."""
        return [
            c for c in self._credentials.values()
            if c.health_status == HealthStatus.UNHEALTHY
        ]

    def get_credentials_by_org(self, org_id: UUID) -> List[IntegrationCredential]:
        """Get all credentials for an organization."""
        return [c for c in self._credentials.values() if c.org_id == org_id]

    async def _get_credentials_to_check(
        self,
        force: bool = False,
    ) -> List[IntegrationCredential]:
        """Get credentials that need checking."""
        now = datetime.utcnow()
        check_threshold = now - timedelta(hours=self.DEFAULT_CHECK_INTERVAL_HOURS)

        credentials = []
        for cred in self._credentials.values():
            if cred.status != "active":
                continue

            if force:
                credentials.append(cred)
            elif cred.last_health_check is None:
                credentials.append(cred)
            elif cred.last_health_check < check_threshold:
                credentials.append(cred)

        return credentials

    async def _update_credential_health(
        self,
        cred: IntegrationCredential,
        result: HealthCheckResult,
    ) -> None:
        """Update credential health status based on check result."""
        cred.last_health_check = datetime.utcnow()
        cred.health_status = result.status

        if result.healthy:
            cred.consecutive_failures = 0
            cred.health_message = result.warning if result.warning else "OK"
        else:
            cred.consecutive_failures += 1
            cred.health_message = result.reason

    async def _handle_check_result(
        self,
        cred: IntegrationCredential,
        result: HealthCheckResult,
    ) -> Optional[HealthAlert]:
        """Handle check result and generate alerts if needed."""
        if result.healthy or result.skipped:
            return None

        # Determine alert severity
        if cred.consecutive_failures >= self.FAILURE_THRESHOLD_CRITICAL:
            severity = "critical"
        elif cred.consecutive_failures >= self.FAILURE_THRESHOLD_WARNING:
            severity = "warning"
        else:
            return None

        # Determine alert type
        alert_type = "health_check_failed"
        if result.reason_code == HealthCheckReason.CREDENTIAL_EXPIRED:
            alert_type = "credential_expired"
        elif result.reason_code == HealthCheckReason.INSUFFICIENT_PERMISSIONS:
            alert_type = "permissions_changed"
        elif result.reason_code == HealthCheckReason.RATE_LIMITED:
            alert_type = "rate_limited"

        # Create alert
        alert = HealthAlert(
            alert_id=uuid4(),
            credential_id=cred.credential_id,
            integration_name=cred.integration_name,
            org_id=cred.org_id,
            alert_type=alert_type,
            message=f"{cred.integration_name} credential failed health check: {result.reason}",
            severity=severity,
        )

        self._alerts.append(alert)

        # Send alert via callback if configured
        if self.alert_callback:
            await self.alert_callback(alert)

        return alert

    def _classify_error(
        self,
        error_code: Optional[str],
        error_message: Optional[str],
    ) -> HealthCheckReason:
        """Classify error into a reason code."""
        if not error_code and not error_message:
            return HealthCheckReason.UNKNOWN_ERROR

        code = (error_code or "").upper()
        message = (error_message or "").lower()

        if "401" in code or "unauthorized" in message or "expired" in message:
            return HealthCheckReason.CREDENTIAL_EXPIRED
        elif "403" in code or "forbidden" in message or "permission" in message:
            return HealthCheckReason.INSUFFICIENT_PERMISSIONS
        elif "429" in code or "rate" in message or "limit" in message:
            return HealthCheckReason.RATE_LIMITED
        elif "timeout" in message:
            return HealthCheckReason.TIMEOUT
        elif "500" in code or "502" in code or "503" in code or "504" in code:
            return HealthCheckReason.SERVER_ERROR
        elif "network" in message or "connection" in message:
            return HealthCheckReason.NETWORK_ERROR
        else:
            return HealthCheckReason.UNKNOWN_ERROR


# Singleton instance
_service_instance: Optional[IntegrationHealthService] = None


def get_integration_health_service(
    db=None,
    integration_factory: Optional[Callable] = None,
    alert_callback: Optional[Callable] = None,
) -> IntegrationHealthService:
    """Get or create the singleton health service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = IntegrationHealthService(
            db=db,
            integration_factory=integration_factory,
            alert_callback=alert_callback,
        )
    return _service_instance


def reset_integration_health_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    _service_instance = None
