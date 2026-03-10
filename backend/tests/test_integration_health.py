#!/usr/bin/env python3
"""
Tests for Integration Health Service

Tests credential health checking, alerting, and history tracking.
Reference: ROADMAP.md Section "Integration Credential Health Checks"
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from backend.shared.integration_health_service import (
    IntegrationHealthService,
    HealthStatus,
    HealthCheckReason,
    HealthCheckResult,
    IntegrationCredential,
    HealthAlert,
    HealthCheckStats,
    get_integration_health_service,
    reset_integration_health_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def health_service():
    """Create a fresh health service for testing."""
    return IntegrationHealthService()


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    reset_integration_health_service()
    yield
    reset_integration_health_service()


# ============================================================================
# Credential Registration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_register_credential(health_service):
    """Should register a credential for health monitoring."""
    cred_id = uuid4()
    org_id = uuid4()

    cred = await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=org_id,
    )

    assert cred.credential_id == cred_id
    assert cred.integration_name == "slack"
    assert cred.org_id == org_id
    assert cred.status == "active"
    assert cred.health_status == HealthStatus.UNKNOWN


@pytest.mark.asyncio
async def test_register_multiple_credentials(health_service):
    """Should register multiple credentials."""
    org_id = uuid4()

    cred1 = await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="slack",
        org_id=org_id,
    )
    cred2 = await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="github",
        org_id=org_id,
    )

    all_creds = health_service.get_all_credentials()
    assert len(all_creds) == 2


@pytest.mark.asyncio
async def test_get_credential(health_service):
    """Should retrieve registered credential by ID."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="stripe",
        org_id=uuid4(),
    )

    cred = health_service.get_credential(cred_id)
    assert cred is not None
    assert cred.credential_id == cred_id


@pytest.mark.asyncio
async def test_get_nonexistent_credential(health_service):
    """Should return None for nonexistent credential."""
    cred = health_service.get_credential(uuid4())
    assert cred is None


# ============================================================================
# Health Check Tests
# ============================================================================


@pytest.mark.asyncio
async def test_check_credential_healthy(health_service):
    """Should mark credential as healthy after successful check."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    result = await health_service.check_credential(cred_id)

    assert result.healthy
    assert result.status == HealthStatus.HEALTHY

    cred = health_service.get_credential(cred_id)
    assert cred.health_status == HealthStatus.HEALTHY
    assert cred.consecutive_failures == 0


@pytest.mark.asyncio
async def test_check_credential_not_found(health_service):
    """Should handle check for nonexistent credential."""
    result = await health_service.check_credential(uuid4())

    assert not result.healthy
    assert result.status == HealthStatus.UNKNOWN
    assert "not found" in result.reason.lower()


@pytest.mark.asyncio
async def test_check_unsupported_integration(health_service):
    """Should skip unsupported integrations."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="unsupported_integration",
        org_id=uuid4(),
    )

    result = await health_service.check_credential(cred_id)

    assert result.healthy
    assert result.skipped
    assert "no health endpoint" in result.reason.lower()


@pytest.mark.asyncio
async def test_simulate_check_failure_expired(health_service):
    """Should handle credential expiration failure."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    result = await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Token expired",
        reason_code=HealthCheckReason.CREDENTIAL_EXPIRED,
    )

    assert not result.healthy
    assert result.status == HealthStatus.UNHEALTHY
    assert result.reason_code == HealthCheckReason.CREDENTIAL_EXPIRED

    cred = health_service.get_credential(cred_id)
    assert cred.consecutive_failures == 1


@pytest.mark.asyncio
async def test_simulate_check_failure_permissions(health_service):
    """Should handle permission failure."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="github",
        org_id=uuid4(),
    )

    result = await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Insufficient permissions",
        reason_code=HealthCheckReason.INSUFFICIENT_PERMISSIONS,
    )

    assert not result.healthy
    assert result.reason_code == HealthCheckReason.INSUFFICIENT_PERMISSIONS


@pytest.mark.asyncio
async def test_simulate_check_warning(health_service):
    """Should handle warning status."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="stripe",
        org_id=uuid4(),
    )

    result = await health_service.simulate_check_warning(
        credential_id=cred_id,
        warning="Token expires in 7 days",
    )

    assert result.healthy
    assert result.status == HealthStatus.WARNING
    assert result.warning == "Token expires in 7 days"


@pytest.mark.asyncio
async def test_consecutive_failures_increment(health_service):
    """Should increment consecutive failures count."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    # Fail 3 times
    for i in range(3):
        await health_service.simulate_check_failure(
            credential_id=cred_id,
            reason=f"Failure {i + 1}",
            reason_code=HealthCheckReason.NETWORK_ERROR,
        )

    cred = health_service.get_credential(cred_id)
    assert cred.consecutive_failures == 3


@pytest.mark.asyncio
async def test_consecutive_failures_reset_on_success(health_service):
    """Should reset consecutive failures on success."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    # Fail twice
    await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Failure",
        reason_code=HealthCheckReason.TIMEOUT,
    )
    await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Failure",
        reason_code=HealthCheckReason.TIMEOUT,
    )

    cred = health_service.get_credential(cred_id)
    assert cred.consecutive_failures == 2

    # Now succeed
    await health_service.check_credential(cred_id)

    cred = health_service.get_credential(cred_id)
    assert cred.consecutive_failures == 0
    assert cred.health_status == HealthStatus.HEALTHY


# ============================================================================
# Check All Credentials Tests
# ============================================================================


@pytest.mark.asyncio
async def test_check_all_credentials(health_service):
    """Should check all active credentials."""
    org_id = uuid4()

    await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="slack",
        org_id=org_id,
    )
    await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="github",
        org_id=org_id,
    )

    stats = await health_service.check_all_credentials()

    assert stats.total_checked == 2
    assert stats.healthy_count == 2
    assert stats.unhealthy_count == 0
    assert stats.duration_ms >= 0


@pytest.mark.asyncio
async def test_check_all_credentials_skip_inactive(health_service):
    """Should skip inactive credentials."""
    org_id = uuid4()

    await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="slack",
        org_id=org_id,
        status="active",
    )
    await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="github",
        org_id=org_id,
        status="inactive",
    )

    stats = await health_service.check_all_credentials()

    # Only active credential checked
    assert stats.total_checked == 1


@pytest.mark.asyncio
async def test_check_all_credentials_respects_interval(health_service):
    """Should skip recently checked credentials unless forced."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    # First check
    stats1 = await health_service.check_all_credentials()
    assert stats1.total_checked == 1

    # Second check without force - should skip
    stats2 = await health_service.check_all_credentials()
    assert stats2.total_checked == 0

    # Third check with force
    stats3 = await health_service.check_all_credentials(force=True)
    assert stats3.total_checked == 1


# ============================================================================
# Alert Tests
# ============================================================================


@pytest.mark.asyncio
async def test_alert_on_consecutive_failures(health_service):
    """Should generate alert after consecutive failures."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    # First failure - no alert yet (threshold not met)
    await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Timeout",
        reason_code=HealthCheckReason.TIMEOUT,
    )

    alerts = health_service.get_alerts(credential_id=cred_id)
    assert len(alerts) == 1  # Warning threshold is 1


@pytest.mark.asyncio
async def test_alert_severity_warning(health_service):
    """Should create warning severity alert for 1 failure."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Network error",
        reason_code=HealthCheckReason.NETWORK_ERROR,
    )

    alerts = health_service.get_alerts(credential_id=cred_id)
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"


@pytest.mark.asyncio
async def test_alert_severity_critical(health_service):
    """Should create critical severity alert for 3+ failures."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    # Fail 3 times
    for _ in range(3):
        await health_service.simulate_check_failure(
            credential_id=cred_id,
            reason="Server error",
            reason_code=HealthCheckReason.SERVER_ERROR,
        )

    alerts = health_service.get_alerts(credential_id=cred_id)
    # Last alert should be critical
    assert alerts[-1].severity == "critical"


@pytest.mark.asyncio
async def test_alert_type_credential_expired(health_service):
    """Should set correct alert type for expired credentials."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Token expired",
        reason_code=HealthCheckReason.CREDENTIAL_EXPIRED,
    )

    alerts = health_service.get_alerts(credential_id=cred_id)
    assert alerts[0].alert_type == "credential_expired"


@pytest.mark.asyncio
async def test_acknowledge_alert(health_service):
    """Should acknowledge an alert."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Error",
        reason_code=HealthCheckReason.NETWORK_ERROR,
    )

    alerts = health_service.get_alerts(unacknowledged_only=True)
    assert len(alerts) == 1

    result = await health_service.acknowledge_alert(alerts[0].alert_id)
    assert result is True

    unacked = health_service.get_alerts(unacknowledged_only=True)
    assert len(unacked) == 0


@pytest.mark.asyncio
async def test_acknowledge_nonexistent_alert(health_service):
    """Should return False for nonexistent alert."""
    result = await health_service.acknowledge_alert(uuid4())
    assert result is False


@pytest.mark.asyncio
async def test_alert_callback(health_service):
    """Should call alert callback when alert is generated."""
    received_alerts = []

    async def alert_callback(alert):
        received_alerts.append(alert)

    service = IntegrationHealthService(alert_callback=alert_callback)

    cred_id = uuid4()
    await service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    await service.simulate_check_failure(
        credential_id=cred_id,
        reason="Error",
        reason_code=HealthCheckReason.TIMEOUT,
    )

    assert len(received_alerts) == 1
    assert received_alerts[0].integration_name == "slack"


# ============================================================================
# Health History Tests
# ============================================================================


@pytest.mark.asyncio
async def test_health_history_tracking(health_service):
    """Should track health check history."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    # Run 3 checks
    await health_service.check_credential(cred_id)
    await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Fail",
        reason_code=HealthCheckReason.TIMEOUT,
    )
    await health_service.check_credential(cred_id)

    history = health_service.get_health_history(cred_id)
    assert len(history) == 3
    assert history[0].healthy  # First check
    assert not history[1].healthy  # Failure
    assert history[2].healthy  # Recovery


@pytest.mark.asyncio
async def test_health_history_limit(health_service):
    """Should limit history retrieval."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    # Run 5 checks
    for _ in range(5):
        await health_service.check_credential(cred_id)

    # Get limited history
    history = health_service.get_health_history(cred_id, limit=3)
    assert len(history) == 3


# ============================================================================
# Query Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_unhealthy_credentials(health_service):
    """Should return only unhealthy credentials."""
    org_id = uuid4()

    cred1 = await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="slack",
        org_id=org_id,
    )
    cred2 = await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="github",
        org_id=org_id,
    )

    # Make first healthy
    await health_service.check_credential(cred1.credential_id)

    # Make second unhealthy
    await health_service.simulate_check_failure(
        credential_id=cred2.credential_id,
        reason="Error",
        reason_code=HealthCheckReason.TIMEOUT,
    )

    unhealthy = health_service.get_unhealthy_credentials()
    assert len(unhealthy) == 1
    assert unhealthy[0].credential_id == cred2.credential_id


@pytest.mark.asyncio
async def test_get_credentials_by_org(health_service):
    """Should filter credentials by organization."""
    org1 = uuid4()
    org2 = uuid4()

    await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="slack",
        org_id=org1,
    )
    await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="github",
        org_id=org1,
    )
    await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="stripe",
        org_id=org2,
    )

    org1_creds = health_service.get_credentials_by_org(org1)
    assert len(org1_creds) == 2

    org2_creds = health_service.get_credentials_by_org(org2)
    assert len(org2_creds) == 1


# ============================================================================
# Error Classification Tests
# ============================================================================


def test_classify_error_401():
    """Should classify 401 as credential expired."""
    service = IntegrationHealthService()
    reason = service._classify_error("401", "Unauthorized")
    assert reason == HealthCheckReason.CREDENTIAL_EXPIRED


def test_classify_error_403():
    """Should classify 403 as insufficient permissions."""
    service = IntegrationHealthService()
    reason = service._classify_error("403", "Forbidden")
    assert reason == HealthCheckReason.INSUFFICIENT_PERMISSIONS


def test_classify_error_429():
    """Should classify 429 as rate limited."""
    service = IntegrationHealthService()
    reason = service._classify_error("429", "Rate limit exceeded")
    assert reason == HealthCheckReason.RATE_LIMITED


def test_classify_error_500():
    """Should classify 500 as server error."""
    service = IntegrationHealthService()
    reason = service._classify_error("500", "Internal server error")
    assert reason == HealthCheckReason.SERVER_ERROR


def test_classify_error_timeout():
    """Should classify timeout message."""
    service = IntegrationHealthService()
    reason = service._classify_error(None, "Request timeout")
    assert reason == HealthCheckReason.TIMEOUT


def test_classify_error_network():
    """Should classify network error message."""
    service = IntegrationHealthService()
    reason = service._classify_error(None, "Network connection failed")
    assert reason == HealthCheckReason.NETWORK_ERROR


# ============================================================================
# Serialization Tests
# ============================================================================


@pytest.mark.asyncio
async def test_health_check_result_to_dict(health_service):
    """Should serialize HealthCheckResult correctly."""
    result = HealthCheckResult(
        healthy=True,
        status=HealthStatus.HEALTHY,
        response_time_ms=50.5,
    )

    d = result.to_dict()
    assert d["healthy"] is True
    assert d["status"] == "healthy"
    assert d["response_time_ms"] == 50.5


@pytest.mark.asyncio
async def test_credential_to_dict(health_service):
    """Should serialize IntegrationCredential correctly."""
    cred_id = uuid4()
    cred = await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    d = cred.to_dict()
    assert d["credential_id"] == str(cred_id)
    assert d["integration_name"] == "slack"
    assert d["health_status"] == "unknown"


@pytest.mark.asyncio
async def test_alert_to_dict(health_service):
    """Should serialize HealthAlert correctly."""
    cred_id = uuid4()
    await health_service.register_credential(
        credential_id=cred_id,
        integration_name="slack",
        org_id=uuid4(),
    )

    await health_service.simulate_check_failure(
        credential_id=cred_id,
        reason="Error",
        reason_code=HealthCheckReason.TIMEOUT,
    )

    alerts = health_service.get_alerts()
    d = alerts[0].to_dict()

    assert "alert_id" in d
    assert d["integration_name"] == "slack"
    assert d["severity"] in ["warning", "critical"]


@pytest.mark.asyncio
async def test_stats_to_dict(health_service):
    """Should serialize HealthCheckStats correctly."""
    await health_service.register_credential(
        credential_id=uuid4(),
        integration_name="slack",
        org_id=uuid4(),
    )

    stats = await health_service.check_all_credentials()
    d = stats.to_dict()

    assert d["total_checked"] == 1
    assert d["healthy_count"] == 1
    assert "duration_ms" in d


# ============================================================================
# Singleton Tests
# ============================================================================


def test_get_singleton():
    """Should return singleton instance."""
    s1 = get_integration_health_service()
    s2 = get_integration_health_service()
    assert s1 is s2


def test_reset_singleton():
    """Should reset singleton instance."""
    s1 = get_integration_health_service()
    reset_integration_health_service()
    s2 = get_integration_health_service()
    assert s1 is not s2
