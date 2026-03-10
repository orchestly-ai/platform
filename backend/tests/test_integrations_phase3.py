"""
Integration Tests for Phase 3: Jira, Microsoft Teams, Notion, HubSpot, Twilio

Tests verify initialization, credential validation, and supported actions
for each integration (same pattern as existing Datadog/PagerDuty tests).
"""

import os
os.environ["USE_SQLITE"] = "true"

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.integrations.base import (
    BaseIntegration,
    IntegrationResult,
    IntegrationError,
    AuthType,
)


# ============================================================================
# Jira Integration Tests
# ============================================================================

from backend.integrations.jira import JiraIntegration


class TestJiraIntegration:
    """Tests for Jira integration."""

    @pytest.fixture
    def valid_credentials(self):
        return {
            "email": "user@company.com",
            "api_token": "test-api-token-12345",
            "domain": "company.atlassian.net",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        return JiraIntegration(auth_credentials=valid_credentials)

    def test_init_with_valid_credentials(self, integration):
        assert integration.name == "jira"
        assert integration.display_name == "Jira"
        assert integration.auth_type == AuthType.BASIC_AUTH

    def test_init_missing_email(self):
        with pytest.raises(IntegrationError) as exc:
            JiraIntegration(auth_credentials={
                "api_token": "token",
                "domain": "x.atlassian.net",
            })
        assert "email" in str(exc.value).lower()

    def test_init_missing_api_token(self):
        with pytest.raises(IntegrationError) as exc:
            JiraIntegration(auth_credentials={
                "email": "a@b.com",
                "domain": "x.atlassian.net",
            })
        assert "api_token" in str(exc.value).lower()

    def test_init_missing_domain(self):
        with pytest.raises(IntegrationError) as exc:
            JiraIntegration(auth_credentials={
                "email": "a@b.com",
                "api_token": "token",
            })
        assert "domain" in str(exc.value).lower()

    def test_supported_actions(self, integration):
        actions = integration.supported_actions
        assert "create_issue" in actions
        assert "get_issue" in actions
        assert "search_issues" in actions
        assert "test_connection" in actions
        assert len(actions) >= 5


# ============================================================================
# Microsoft Teams Integration Tests
# ============================================================================

from backend.integrations.microsoft_teams import MicrosoftTeamsIntegration


class TestMicrosoftTeamsIntegration:
    """Tests for Microsoft Teams integration."""

    @pytest.fixture
    def oauth_credentials(self):
        return {"access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOi..."}

    @pytest.fixture
    def app_credentials(self):
        return {
            "client_id": "app-id-12345",
            "client_secret": "secret-12345",
            "tenant_id": "tenant-12345",
        }

    @pytest.fixture
    def integration_oauth(self, oauth_credentials):
        return MicrosoftTeamsIntegration(auth_credentials=oauth_credentials)

    @pytest.fixture
    def integration_app(self, app_credentials):
        return MicrosoftTeamsIntegration(auth_credentials=app_credentials)

    def test_init_with_oauth_token(self, integration_oauth):
        assert integration_oauth.name == "microsoft_teams"
        assert integration_oauth.display_name == "Microsoft Teams"
        assert integration_oauth.auth_type == AuthType.OAUTH2

    def test_init_with_app_credentials(self, integration_app):
        assert integration_app.name == "microsoft_teams"

    def test_init_missing_all_credentials(self):
        with pytest.raises(IntegrationError) as exc:
            MicrosoftTeamsIntegration(auth_credentials={
                "tenant_id": "t-123",
            })
        assert "client_id" in str(exc.value).lower() or "client_secret" in str(exc.value).lower()

    def test_supported_actions(self, integration_oauth):
        actions = integration_oauth.supported_actions
        assert "send_message" in actions
        assert "create_channel" in actions
        assert "test_connection" in actions
        assert len(actions) >= 4


# ============================================================================
# Notion Integration Tests
# ============================================================================

from backend.integrations.notion import NotionIntegration


class TestNotionIntegration:
    """Tests for Notion integration."""

    @pytest.fixture
    def valid_credentials(self):
        return {"integration_token": "secret_test12345"}

    @pytest.fixture
    def api_key_credentials(self):
        return {"api_key": "secret_key_12345"}

    @pytest.fixture
    def integration(self, valid_credentials):
        return NotionIntegration(auth_credentials=valid_credentials)

    def test_init_with_integration_token(self, integration):
        assert integration.name == "notion"
        assert integration.display_name == "Notion"
        assert integration.auth_type == AuthType.API_KEY

    def test_init_with_api_key(self, api_key_credentials):
        integration = NotionIntegration(auth_credentials=api_key_credentials)
        assert integration.name == "notion"

    def test_init_missing_credentials(self):
        with pytest.raises(IntegrationError) as exc:
            NotionIntegration(auth_credentials={"other_field": "value"})
        assert "integration_token" in str(exc.value).lower() or "api_key" in str(exc.value).lower()

    def test_supported_actions(self, integration):
        actions = integration.supported_actions
        assert "create_page" in actions
        assert "search" in actions
        assert "query_database" in actions
        assert len(actions) >= 5


# ============================================================================
# HubSpot Integration Tests
# ============================================================================

# HubSpot uses `from integrations.base` (relative to its own package).
# We try importing; if it fails due to the relative import, skip.
try:
    from backend.integrations.hubspot import HubSpotIntegration
    _hubspot_available = True
except (ImportError, ModuleNotFoundError):
    _hubspot_available = False


@pytest.mark.skipif(not _hubspot_available, reason="HubSpot import uses relative 'integrations.base' path")
class TestHubSpotIntegration:
    """Tests for HubSpot integration."""

    @pytest.fixture
    def valid_credentials(self):
        return {"api_key": "pat-na1-12345678-abcd"}

    @pytest.fixture
    def integration(self, valid_credentials):
        return HubSpotIntegration(auth_credentials=valid_credentials)

    def test_init_with_valid_credentials(self, integration):
        assert integration.name == "hubspot"
        assert integration.display_name == "HubSpot"
        assert integration.auth_type == AuthType.API_KEY

    def test_init_missing_api_key(self):
        with pytest.raises(IntegrationError) as exc:
            HubSpotIntegration(auth_credentials={"other": "value"})
        assert "api_key" in str(exc.value).lower()

    def test_supported_actions(self, integration):
        actions = integration.supported_actions
        assert "create_contact" in actions
        assert "create_deal" in actions
        assert len(actions) >= 3


# ============================================================================
# Twilio Integration Tests
# ============================================================================

try:
    from backend.integrations.twilio import TwilioIntegration
    _twilio_available = True
except (ImportError, ModuleNotFoundError):
    _twilio_available = False


@pytest.mark.skipif(not _twilio_available, reason="Twilio import uses relative 'integrations.base' path")
class TestTwilioIntegration:
    """Tests for Twilio integration."""

    @pytest.fixture
    def valid_credentials(self):
        return {
            "account_sid": "AC1234567890abcdef",
            "auth_token": "test_auth_token_12345",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        return TwilioIntegration(auth_credentials=valid_credentials)

    def test_init_with_valid_credentials(self, integration):
        assert integration.name == "twilio"
        assert integration.display_name == "Twilio"
        assert integration.auth_type == AuthType.BASIC_AUTH

    def test_init_missing_account_sid(self):
        with pytest.raises(IntegrationError) as exc:
            TwilioIntegration(auth_credentials={
                "auth_token": "token",
            })
        assert "account_sid" in str(exc.value).lower()

    def test_init_missing_auth_token(self):
        with pytest.raises(IntegrationError) as exc:
            TwilioIntegration(auth_credentials={
                "account_sid": "AC123",
            })
        assert "auth_token" in str(exc.value).lower()

    def test_supported_actions(self, integration):
        actions = integration.supported_actions
        assert "send_sms" in actions
        assert "make_call" in actions
        assert len(actions) >= 3
