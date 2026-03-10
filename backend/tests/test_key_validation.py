#!/usr/bin/env python3
"""
Tests for Key Validation Service

Session 2.3: Key Rotation Detection
- 24h API key validation pings
- Alert generation on failures
- Health status tracking
- Integration with BYOK Gateway
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock

from backend.shared.key_validation_service import (
    KeyValidationService,
    KeyValidator,
    KeyValidationStatus,
    ValidationResult,
    ValidationAlert,
    ValidationAlertType,
    AlertSeverity,
    KeyHealthStatus,
    ValidationSchedule,
    get_key_validation_service,
    reset_key_validation_service,
)


# ============================================================================
# KeyValidator Tests
# ============================================================================

class TestKeyValidator:
    """Tests for KeyValidator."""

    @pytest.fixture
    def validator(self):
        """Create a validator in simulation mode."""
        return KeyValidator(simulate=True)

    @pytest.mark.asyncio
    async def test_validate_key_simulation(self, validator):
        """Test simulated key validation."""
        key_id = uuid4()

        result = await validator.validate_key(
            key_id=key_id,
            provider="openai",
            api_key="sk-test-key",
        )

        assert result.key_id == key_id
        assert result.provider == "openai"
        assert result.validated_at is not None
        assert result.response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_validate_key_with_preset_state(self, validator):
        """Test validation with preset simulated state."""
        key_id = uuid4()
        validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)

        result = await validator.validate_key(
            key_id=key_id,
            provider="openai",
            api_key="sk-test-key",
        )

        assert result.status == KeyValidationStatus.INVALID
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_validate_key_valid_has_quota_info(self, validator):
        """Test that valid keys include quota information."""
        key_id = uuid4()
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)

        result = await validator.validate_key(
            key_id=key_id,
            provider="openai",
            api_key="sk-test-key",
        )

        assert result.status == KeyValidationStatus.VALID
        assert result.remaining_quota is not None
        assert "requests_remaining" in result.remaining_quota

    @pytest.mark.asyncio
    async def test_validate_key_rate_limited(self, validator):
        """Test rate limited response."""
        key_id = uuid4()
        validator.set_simulated_state(key_id, KeyValidationStatus.RATE_LIMITED)

        result = await validator.validate_key(
            key_id=key_id,
            provider="anthropic",
            api_key="sk-ant-key",
        )

        assert result.status == KeyValidationStatus.RATE_LIMITED
        assert result.error_code == "rate_limit_exceeded"

    def test_validation_result_to_dict(self):
        """Test ValidationResult serialization."""
        result = ValidationResult(
            key_id=uuid4(),
            provider="openai",
            status=KeyValidationStatus.VALID,
            validated_at=datetime.utcnow(),
            response_time_ms=150,
        )

        output = result.to_dict()

        assert "key_id" in output
        assert output["provider"] == "openai"
        assert output["status"] == "valid"


# ============================================================================
# ValidationSchedule Tests
# ============================================================================

class TestValidationSchedule:
    """Tests for ValidationSchedule."""

    def test_schedule_is_due_no_next_validation(self):
        """Test schedule is due when no next_validation set."""
        schedule = ValidationSchedule(
            key_id=uuid4(),
            interval_hours=24.0,
            next_validation=None,
        )

        assert schedule.is_due() is True

    def test_schedule_is_due_past_time(self):
        """Test schedule is due when next_validation is in the past."""
        schedule = ValidationSchedule(
            key_id=uuid4(),
            interval_hours=24.0,
            next_validation=datetime.utcnow() - timedelta(hours=1),
        )

        assert schedule.is_due() is True

    def test_schedule_not_due_future_time(self):
        """Test schedule is not due when next_validation is in the future."""
        schedule = ValidationSchedule(
            key_id=uuid4(),
            interval_hours=24.0,
            next_validation=datetime.utcnow() + timedelta(hours=1),
        )

        assert schedule.is_due() is False

    def test_schedule_not_due_when_disabled(self):
        """Test schedule is not due when disabled."""
        schedule = ValidationSchedule(
            key_id=uuid4(),
            interval_hours=24.0,
            next_validation=datetime.utcnow() - timedelta(hours=1),
            enabled=False,
        )

        assert schedule.is_due() is False


# ============================================================================
# KeyValidationService Tests
# ============================================================================

class TestKeyValidationService:
    """Tests for KeyValidationService."""

    @pytest.fixture
    def validator(self):
        """Create a test validator."""
        return KeyValidator(simulate=True)

    @pytest.fixture
    def service(self, validator):
        """Create a validation service."""
        return KeyValidationService(validator=validator)

    @pytest.fixture
    def key_id(self):
        return uuid4()

    @pytest.fixture
    def org_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_register_key(self, service, key_id, org_id, validator):
        """Test registering a key for validation."""
        # Set to valid for predictable test
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)

        health = await service.register_key(
            key_id=key_id,
            org_id=org_id,
            provider="openai",
            validate_immediately=True,
        )

        assert health.key_id == key_id
        assert health.org_id == org_id
        assert health.provider == "openai"
        assert health.is_healthy is True

    @pytest.mark.asyncio
    async def test_register_key_without_immediate_validation(self, service, key_id, org_id):
        """Test registering a key without immediate validation."""
        health = await service.register_key(
            key_id=key_id,
            org_id=org_id,
            provider="openai",
            validate_immediately=False,
        )

        assert health.last_validation is None
        assert health.is_healthy is True  # Assumed healthy until validated

    @pytest.mark.asyncio
    async def test_unregister_key(self, service, key_id, org_id, validator):
        """Test unregistering a key."""
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai")

        result = await service.unregister_key(key_id)

        assert result is True
        assert service.get_health_status(key_id) is None

    @pytest.mark.asyncio
    async def test_validate_key_success(self, service, key_id, org_id, validator):
        """Test successful key validation."""
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai")

        result = await service.validate_key(key_id)

        assert result.status == KeyValidationStatus.VALID
        health = service.get_health_status(key_id)
        assert health.is_healthy is True
        assert health.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_validate_key_failure(self, service, key_id, org_id, validator):
        """Test key validation failure."""
        validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)
        await service.register_key(key_id, org_id, "openai", validate_immediately=False)

        # First failure
        result = await service.validate_key(key_id)
        health = service.get_health_status(key_id)
        assert result.status == KeyValidationStatus.INVALID
        assert health.consecutive_failures == 1
        assert health.is_healthy is True  # Still healthy after one failure

        # Second failure triggers unhealthy status
        result = await service.validate_key(key_id)
        health = service.get_health_status(key_id)
        assert health.consecutive_failures == 2
        assert health.is_healthy is False

    @pytest.mark.asyncio
    async def test_validate_key_not_registered(self, service):
        """Test validating a non-registered key."""
        with pytest.raises(ValueError) as exc:
            await service.validate_key(uuid4())

        assert "not registered" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validate_key_recovery(self, service, key_id, org_id, validator):
        """Test key recovery after failures."""
        await service.register_key(key_id, org_id, "openai", validate_immediately=False)

        # Cause failures
        validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)
        await service.validate_key(key_id)
        await service.validate_key(key_id)

        health = service.get_health_status(key_id)
        assert health.is_healthy is False

        # Recover
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.validate_key(key_id)

        health = service.get_health_status(key_id)
        assert health.is_healthy is True
        assert health.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_alert_generation_on_failure(self, service, key_id, org_id, validator):
        """Test that alerts are generated on failures."""
        alerts_received = []

        async def alert_callback(alert):
            alerts_received.append(alert)

        service.alert_callback = alert_callback

        await service.register_key(key_id, org_id, "openai", validate_immediately=False)
        validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)

        # Trigger alert threshold
        await service.validate_key(key_id)
        await service.validate_key(key_id)

        assert len(alerts_received) >= 1
        assert alerts_received[0].alert_type == ValidationAlertType.KEY_INVALID

    @pytest.mark.asyncio
    async def test_recovery_alert_generation(self, service, key_id, org_id, validator):
        """Test that recovery alerts are generated."""
        alerts_received = []

        async def alert_callback(alert):
            alerts_received.append(alert)

        service.alert_callback = alert_callback

        await service.register_key(key_id, org_id, "openai", validate_immediately=False)

        # Fail then recover
        validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)
        await service.validate_key(key_id)
        await service.validate_key(key_id)

        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.validate_key(key_id)

        recovery_alerts = [a for a in alerts_received if a.alert_type == ValidationAlertType.KEY_RECOVERED]
        assert len(recovery_alerts) >= 1

    @pytest.mark.asyncio
    async def test_validate_all_due(self, service, validator):
        """Test validating all due keys."""
        keys = [uuid4() for _ in range(3)]
        org_id = uuid4()

        for key_id in keys:
            validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
            await service.register_key(
                key_id, org_id, "openai",
                validate_immediately=False,
            )
            # Set next_validation to past to make them due
            schedule = service.get_validation_schedule(key_id)
            schedule.next_validation = datetime.utcnow() - timedelta(hours=1)

        # All should be due now
        results = await service.validate_all_due()

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_health_status(self, service, key_id, org_id, validator):
        """Test getting health status."""
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai")

        health = service.get_health_status(key_id)

        assert health is not None
        assert health.key_id == key_id

    def test_get_health_status_not_found(self, service):
        """Test getting health status for non-registered key."""
        result = service.get_health_status(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_health_statuses(self, service, validator):
        """Test getting all health statuses."""
        keys = [uuid4() for _ in range(3)]
        org_id = uuid4()

        for key_id in keys:
            validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
            await service.register_key(key_id, org_id, "openai")

        statuses = service.get_all_health_statuses()

        assert len(statuses) == 3

    @pytest.mark.asyncio
    async def test_get_unhealthy_keys(self, service, validator):
        """Test getting unhealthy keys."""
        healthy_key = uuid4()
        unhealthy_key = uuid4()
        org_id = uuid4()

        validator.set_simulated_state(healthy_key, KeyValidationStatus.VALID)
        await service.register_key(healthy_key, org_id, "openai")

        validator.set_simulated_state(unhealthy_key, KeyValidationStatus.INVALID)
        await service.register_key(unhealthy_key, org_id, "openai", validate_immediately=False)
        await service.validate_key(unhealthy_key)
        await service.validate_key(unhealthy_key)

        unhealthy = service.get_unhealthy_keys()

        assert len(unhealthy) == 1
        assert unhealthy[0].key_id == unhealthy_key

    @pytest.mark.asyncio
    async def test_get_alerts(self, service, key_id, org_id, validator):
        """Test getting alerts."""
        await service.register_key(key_id, org_id, "openai", validate_immediately=False)
        validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)
        await service.validate_key(key_id)
        await service.validate_key(key_id)

        alerts = service.get_alerts(key_id=key_id)

        assert len(alerts) >= 1

    @pytest.mark.asyncio
    async def test_get_alerts_by_org(self, service, validator):
        """Test getting alerts filtered by org."""
        org1 = uuid4()
        org2 = uuid4()
        key1 = uuid4()
        key2 = uuid4()

        for key, org in [(key1, org1), (key2, org2)]:
            validator.set_simulated_state(key, KeyValidationStatus.INVALID)
            await service.register_key(key, org, "openai", validate_immediately=False)
            await service.validate_key(key)
            await service.validate_key(key)

        alerts_org1 = service.get_alerts(org_id=org1)
        alerts_org2 = service.get_alerts(org_id=org2)

        assert all(a.org_id == org1 for a in alerts_org1)
        assert all(a.org_id == org2 for a in alerts_org2)

    @pytest.mark.asyncio
    async def test_get_unresolved_alerts(self, service, key_id, org_id, validator):
        """Test getting unresolved alerts only."""
        await service.register_key(key_id, org_id, "openai", validate_immediately=False)

        # Create failure alerts
        validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)
        await service.validate_key(key_id)
        await service.validate_key(key_id)

        # Resolve by recovering
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.validate_key(key_id)

        unresolved = service.get_alerts(unresolved_only=True)
        # After recovery, failure alerts should be resolved
        assert all(not a.resolved for a in unresolved)

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, service, key_id, org_id, validator):
        """Test acknowledging an alert."""
        await service.register_key(key_id, org_id, "openai", validate_immediately=False)
        validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)
        await service.validate_key(key_id)
        await service.validate_key(key_id)

        alerts = service.get_alerts()
        assert len(alerts) >= 1

        result = await service.acknowledge_alert(alerts[0].alert_id)

        assert result is True
        assert alerts[0].acknowledged is True

    @pytest.mark.asyncio
    async def test_acknowledge_alert_not_found(self, service):
        """Test acknowledging non-existent alert."""
        result = await service.acknowledge_alert(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_get_validation_schedule(self, service, key_id, org_id, validator):
        """Test getting validation schedule."""
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai", interval_hours=12.0)

        schedule = service.get_validation_schedule(key_id)

        assert schedule is not None
        assert schedule.interval_hours == 12.0

    @pytest.mark.asyncio
    async def test_update_validation_interval(self, service, key_id, org_id, validator):
        """Test updating validation interval."""
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai", interval_hours=24.0)

        result = service.update_validation_interval(key_id, 6.0)

        assert result is True
        schedule = service.get_validation_schedule(key_id)
        assert schedule.interval_hours == 6.0

    def test_update_validation_interval_not_found(self, service):
        """Test updating interval for non-registered key."""
        result = service.update_validation_interval(uuid4(), 6.0)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_overdue_validations(self, service, validator):
        """Test getting overdue validations."""
        key_id = uuid4()
        org_id = uuid4()

        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai")

        # Manipulate last validation time to be old
        health = service.get_health_status(key_id)
        if health.last_validation:
            health.last_validation.validated_at = datetime.utcnow() - timedelta(hours=50)

        overdue = service.get_overdue_validations(threshold_hours=48.0)

        assert len(overdue) >= 1

    @pytest.mark.asyncio
    async def test_force_validate_all(self, service, validator):
        """Test force validating all keys."""
        keys = [uuid4() for _ in range(3)]
        org_id = uuid4()

        for key_id in keys:
            validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
            await service.register_key(key_id, org_id, "openai", validate_immediately=False)

        results = await service.force_validate_all()

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_validation_stats(self, service, validator):
        """Test getting validation statistics."""
        keys = [uuid4() for _ in range(3)]
        org_id = uuid4()

        for i, key_id in enumerate(keys):
            if i < 2:
                validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
            else:
                validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)

            await service.register_key(key_id, org_id, "openai", validate_immediately=False)
            await service.validate_key(key_id)
            if i == 2:
                await service.validate_key(key_id)

        stats = service.get_validation_stats()

        assert stats["total_keys"] == 3
        assert stats["healthy_keys"] == 2
        assert stats["unhealthy_keys"] == 1
        assert stats["total_validations"] >= 3

    @pytest.mark.asyncio
    async def test_validation_history_limited(self, service, key_id, org_id, validator):
        """Test that validation history is limited."""
        validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai", validate_immediately=False)

        # Perform many validations
        for _ in range(60):
            await service.validate_key(key_id)

        health = service.get_health_status(key_id)

        assert len(health.validation_history) <= service.MAX_HISTORY_SIZE


# ============================================================================
# Alert Tests
# ============================================================================

class TestValidationAlert:
    """Tests for ValidationAlert."""

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = ValidationAlert(
            alert_id=uuid4(),
            key_id=uuid4(),
            org_id=uuid4(),
            provider="openai",
            alert_type=ValidationAlertType.KEY_INVALID,
            severity=AlertSeverity.CRITICAL,
            message="Test alert",
        )

        result = alert.to_dict()

        assert result["alert_type"] == "key_invalid"
        assert result["severity"] == "critical"
        assert "key_id" in result

    def test_alert_default_values(self):
        """Test alert default values."""
        alert = ValidationAlert(
            alert_id=uuid4(),
            key_id=uuid4(),
            org_id=uuid4(),
            provider="openai",
            alert_type=ValidationAlertType.KEY_INVALID,
            severity=AlertSeverity.WARNING,
            message="Test",
        )

        assert alert.acknowledged is False
        assert alert.resolved is False
        assert alert.resolved_at is None


# ============================================================================
# KeyHealthStatus Tests
# ============================================================================

class TestKeyHealthStatus:
    """Tests for KeyHealthStatus."""

    def test_health_status_to_dict(self):
        """Test health status serialization."""
        health = KeyHealthStatus(
            key_id=uuid4(),
            org_id=uuid4(),
            provider="openai",
            is_healthy=True,
            consecutive_failures=0,
        )

        result = health.to_dict()

        assert result["is_healthy"] is True
        assert result["provider"] == "openai"
        assert "key_id" in result


# ============================================================================
# Background Validation Tests
# ============================================================================

class TestBackgroundValidation:
    """Tests for background validation functionality."""

    @pytest.fixture
    def service(self):
        return KeyValidationService(validator=KeyValidator(simulate=True))

    @pytest.mark.asyncio
    async def test_start_stop_background_validation(self, service):
        """Test starting and stopping background validation."""
        await service.start_background_validation(check_interval_seconds=0.1)

        assert service._running is True
        assert service._validation_task is not None

        await service.stop_background_validation()

        assert service._running is False

    @pytest.mark.asyncio
    async def test_background_validation_validates_due_keys(self, service):
        """Test that background validation processes due keys."""
        key_id = uuid4()
        org_id = uuid4()

        service.validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai", validate_immediately=False)

        # Set next_validation to past to make it due
        schedule = service.get_validation_schedule(key_id)
        schedule.next_validation = datetime.utcnow() - timedelta(hours=1)

        await service.start_background_validation(check_interval_seconds=0.1)

        # Wait for at least one cycle
        await asyncio.sleep(0.3)

        await service.stop_background_validation()

        health = service.get_health_status(key_id)
        assert health.last_validation is not None


# ============================================================================
# Singleton Tests
# ============================================================================

class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_singleton(self):
        """Test getting singleton instance."""
        reset_key_validation_service()

        service1 = get_key_validation_service()
        service2 = get_key_validation_service()

        assert service1 is service2
        reset_key_validation_service()

    def test_reset_singleton(self):
        """Test resetting singleton."""
        reset_key_validation_service()

        service1 = get_key_validation_service()
        reset_key_validation_service()
        service2 = get_key_validation_service()

        assert service1 is not service2
        reset_key_validation_service()


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for key validation."""

    @pytest.mark.asyncio
    async def test_full_validation_lifecycle(self):
        """Test complete validation lifecycle."""
        service = KeyValidationService(validator=KeyValidator(simulate=True))
        key_id = uuid4()
        org_id = uuid4()

        alerts_received = []

        async def alert_callback(alert):
            alerts_received.append(alert)

        service.alert_callback = alert_callback

        # 1. Register key
        service.validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.register_key(key_id, org_id, "openai")

        # 2. Verify healthy
        health = service.get_health_status(key_id)
        assert health.is_healthy is True

        # 3. Simulate key becoming invalid
        service.validator.set_simulated_state(key_id, KeyValidationStatus.INVALID)
        await service.validate_key(key_id)
        await service.validate_key(key_id)

        # 4. Verify unhealthy and alerts
        health = service.get_health_status(key_id)
        assert health.is_healthy is False
        assert len(alerts_received) >= 1

        # 5. Acknowledge alert
        await service.acknowledge_alert(alerts_received[0].alert_id)
        assert alerts_received[0].acknowledged is True

        # 6. Key recovers
        service.validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
        await service.validate_key(key_id)

        # 7. Verify healthy again
        health = service.get_health_status(key_id)
        assert health.is_healthy is True

        # 8. Check stats
        stats = service.get_validation_stats()
        assert stats["healthy_keys"] == 1

    @pytest.mark.asyncio
    async def test_multiple_providers(self):
        """Test validating keys from multiple providers."""
        service = KeyValidationService(validator=KeyValidator(simulate=True))
        org_id = uuid4()

        providers = ["openai", "anthropic", "deepseek"]
        keys = {}

        for provider in providers:
            key_id = uuid4()
            service.validator.set_simulated_state(key_id, KeyValidationStatus.VALID)
            await service.register_key(key_id, org_id, provider)
            keys[provider] = key_id

        # Validate all
        results = await service.force_validate_all()

        assert len(results) == 3
        assert all(r.status == KeyValidationStatus.VALID for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
