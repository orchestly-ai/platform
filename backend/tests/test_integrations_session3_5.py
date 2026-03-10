#!/usr/bin/env python3
"""
Tests for Session 3.5 Integrations: Datadog and PagerDuty

Tests verify:
- Integration initialization and credential validation
- Action routing and parameter validation
- Error handling
- Response parsing
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from backend.integrations.base import (
    BaseIntegration,
    IntegrationResult,
    IntegrationError,
    AuthType,
)
from backend.integrations.datadog import DatadogIntegration
from backend.integrations.pagerduty import PagerDutyIntegration


# ============================================================================
# Datadog Integration Tests
# ============================================================================

class TestDatadogIntegration:
    """Tests for Datadog integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Datadog credentials."""
        return {
            "api_key": "test-api-key-12345",
            "app_key": "test-app-key-12345",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Datadog integration instance."""
        return DatadogIntegration(auth_credentials=valid_credentials)

    def test_init_with_valid_credentials(self, integration):
        """Test initialization with valid credentials."""
        assert integration.name == "datadog"
        assert integration.display_name == "Datadog"
        assert integration.auth_type == AuthType.API_KEY

    def test_init_missing_api_key(self):
        """Test initialization without api_key."""
        with pytest.raises(IntegrationError) as exc:
            DatadogIntegration(auth_credentials={
                "application_key": "app-key",
            })
        assert "api_key" in str(exc.value)

    def test_init_missing_app_key(self):
        """Test initialization without app_key."""
        with pytest.raises(IntegrationError) as exc:
            DatadogIntegration(auth_credentials={
                "api_key": "api-key",
            })
        assert "app_key" in str(exc.value)

    def test_init_with_app_key_alias(self):
        """Test initialization with app_key alias."""
        integration = DatadogIntegration(auth_credentials={
            "api_key": "test-api-key",
            "app_key": "test-app-key",
        })
        assert integration.name == "datadog"

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "send_metric" in actions
        assert "send_event" in actions
        assert "send_log" in actions
        assert "list_monitors" in actions
        assert "get_monitor" in actions
        assert "mute_monitor" in actions
        assert "create_incident" in actions
        assert "test_connection" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("send_metric")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")
        assert "not supported" in str(exc.value)

    def test_get_headers(self, integration):
        """Test headers include DD-API-KEY and DD-APPLICATION-KEY."""
        headers = integration._get_headers()

        assert "DD-API-KEY" in headers
        assert "DD-APPLICATION-KEY" in headers

    @pytest.mark.asyncio
    async def test_send_metric_missing_params(self, integration):
        """Test send_metric without metric and points."""
        result = await integration.execute_action(
            "send_metric",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_send_log_missing_message(self, integration):
        """Test send_log without message."""
        result = await integration.execute_action(
            "send_log",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_send_event_missing_title(self, integration):
        """Test send_event without title."""
        result = await integration.execute_action(
            "send_event",
            {}  # Missing title
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_monitor_missing_id(self, integration):
        """Test get_monitor without monitor_id."""
        result = await integration.execute_action(
            "get_monitor",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_mute_monitor_missing_id(self, integration):
        """Test mute_monitor without monitor_id."""
        result = await integration.execute_action(
            "mute_monitor",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_create_incident_missing_title(self, integration):
        """Test create_incident without title."""
        result = await integration.execute_action(
            "create_incident",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_send_event_success(self, integration):
        """Test successful event sending."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json = MagicMock(return_value={
            "event": {"id": 12345},
            "status": "ok",
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(DatadogIntegration, '_get_client', return_value=mock_client):
            result = await integration.execute_action(
                "send_event",
                {
                    "title": "Test Event",
                    "text": "This is a test event",
                }
            )

        assert result.success is True
        assert result.data["event_id"] == 12345

    @pytest.mark.asyncio
    async def test_test_connection_success(self, integration):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"valid": True})

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(DatadogIntegration, '_get_client', return_value=mock_client):
            result = await integration.test_connection()

        assert result.success is True
        assert result.data["valid"] is True


# ============================================================================
# PagerDuty Integration Tests
# ============================================================================

class TestPagerDutyIntegration:
    """Tests for PagerDuty integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid PagerDuty credentials."""
        return {"api_token": "test-token-12345"}

    @pytest.fixture
    def routing_key_credentials(self):
        """Credentials with routing_key."""
        return {"routing_key": "test-routing-key-12345"}

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create PagerDuty integration instance."""
        return PagerDutyIntegration(auth_credentials=valid_credentials)

    def test_init_with_api_token(self, integration):
        """Test initialization with api_token."""
        assert integration.name == "pagerduty"
        assert integration.display_name == "PagerDuty"
        assert integration.auth_type == AuthType.API_KEY

    def test_init_with_routing_key(self, routing_key_credentials):
        """Test initialization with routing_key."""
        integration = PagerDutyIntegration(auth_credentials=routing_key_credentials)
        assert integration.name == "pagerduty"

    def test_init_missing_token(self):
        """Test initialization without token."""
        with pytest.raises(IntegrationError) as exc:
            PagerDutyIntegration(auth_credentials={"other": "value"})
        assert "api_token" in str(exc.value) or "routing_key" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "trigger_incident" in actions
        assert "get_incident" in actions
        assert "list_incidents" in actions
        assert "acknowledge_incident" in actions
        assert "resolve_incident" in actions
        assert "list_oncalls" in actions
        assert "list_services" in actions
        assert "test_connection" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("trigger_incident")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")
        assert "not supported" in str(exc.value)

    def test_has_api_token(self, integration):
        """Test that api_token is stored in credentials."""
        assert integration.auth_credentials.get("api_token") == "test-token-12345"

    def test_auth_type_is_api_key(self, integration):
        """Test that auth type is API_KEY."""
        assert integration.auth_type == AuthType.API_KEY

    @pytest.mark.asyncio
    async def test_trigger_incident_missing_summary(self, integration):
        """Test trigger_incident without summary."""
        result = await integration.execute_action(
            "trigger_incident",
            {}  # Missing summary
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_incident_missing_id(self, integration):
        """Test get_incident without incident_id."""
        result = await integration.execute_action(
            "get_incident",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_incident_missing_incident_id(self, integration):
        """Test get_incident without incident_id."""
        result = await integration.execute_action(
            "get_incident",
            {}  # Missing incident_id
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_acknowledge_incident_missing_dedup_key(self, integration):
        """Test acknowledge_incident without dedup_key."""
        result = await integration.execute_action(
            "acknowledge_incident",
            {}  # Missing dedup_key
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_resolve_incident_missing_dedup_key(self, integration):
        """Test resolve_incident without dedup_key."""
        result = await integration.execute_action(
            "resolve_incident",
            {}  # Missing dedup_key
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_trigger_incident_missing_summary_msg(self, integration):
        """Test trigger_incident requires summary."""
        result = await integration.execute_action(
            "trigger_incident",
            {"severity": "critical"}  # Missing summary
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_trigger_incident_success(self):
        """Test successful incident triggering via Events API."""
        integration = PagerDutyIntegration(auth_credentials={
            "api_token": "test-token",
            "routing_key": "test-routing-key",
        })

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json = MagicMock(return_value={
            "status": "success",
            "dedup_key": "dedup-123",
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(PagerDutyIntegration, '_get_client', return_value=mock_client):
            result = await integration.execute_action(
                "trigger_incident",
                {
                    "summary": "Test Incident",
                    "severity": "critical",
                }
            )

        assert result.success is True
        assert result.data["dedup_key"] == "dedup-123"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, integration):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "user": {
                "id": "user-123",
                "name": "Test User",
                "email": "test@example.com",
            }
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(PagerDutyIntegration, '_get_client', return_value=mock_client):
            result = await integration.test_connection()

        assert result.success is True
        assert result.data["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_list_incidents_success(self, integration):
        """Test successful incident listing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "incidents": [
                {
                    "id": "P1",
                    "incident_number": 1,
                    "title": "Incident 1",
                    "status": "triggered",
                    "urgency": "high",
                    "service": {"summary": "Service A"},
                    "created_at": "2025-01-01T00:00:00Z",
                },
                {
                    "id": "P2",
                    "incident_number": 2,
                    "title": "Incident 2",
                    "status": "acknowledged",
                    "urgency": "low",
                    "service": {"summary": "Service B"},
                    "created_at": "2025-01-02T00:00:00Z",
                },
            ],
            "total": 2,
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(PagerDutyIntegration, '_get_client', return_value=mock_client):
            result = await integration.execute_action(
                "list_incidents",
                {}
            )

        assert result.success is True
        assert result.data["count"] == 2
        assert len(result.data["incidents"]) == 2


# ============================================================================
# Base Integration Tests
# ============================================================================

class TestBaseIntegrationPattern:
    """Tests to verify integrations follow the base pattern."""

    def test_datadog_is_base_integration(self):
        """Verify Datadog inherits from BaseIntegration."""
        assert issubclass(DatadogIntegration, BaseIntegration)

    def test_pagerduty_is_base_integration(self):
        """Verify PagerDuty inherits from BaseIntegration."""
        assert issubclass(PagerDutyIntegration, BaseIntegration)

    def test_datadog_auth_type(self):
        """Verify Datadog uses API_KEY."""
        integration = DatadogIntegration(auth_credentials={
            "api_key": "test",
            "app_key": "test",
        })
        assert integration.auth_type == AuthType.API_KEY

    def test_pagerduty_auth_type(self):
        """Verify PagerDuty uses API_KEY."""
        integration = PagerDutyIntegration(auth_credentials={"api_token": "token"})
        assert integration.auth_type == AuthType.API_KEY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
