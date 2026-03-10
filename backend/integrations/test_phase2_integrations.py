"""
Tests for Phase 2 Enterprise Integrations

Tests for:
- DocuSign
- Microsoft Teams
- Jira
- Datadog
- PagerDuty
- Okta
- ServiceNow
- Auth0
- New Relic

Run with: pytest test_phase2_integrations.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import httpx


# =============================================================================
# DocuSign Integration Tests
# =============================================================================


class TestDocuSignIntegration:
    """Tests for DocuSign integration."""

    @pytest.fixture
    def jwt_credentials(self):
        """Valid DocuSign JWT credentials."""
        return {
            "integration_key": "test-integration-key",
            "user_id": "test-user-id",
            "account_id": "test-account-id",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIItest\n-----END RSA PRIVATE KEY-----",
        }

    @pytest.fixture
    def oauth_credentials(self):
        """Valid DocuSign OAuth credentials."""
        return {
            "access_token": "test-access-token",
            "account_id": "test-account-id",
        }

    @pytest.fixture
    def integration(self, jwt_credentials):
        """Create DocuSign integration instance."""
        from backend.integrations.docusign import DocuSignIntegration
        return DocuSignIntegration(jwt_credentials)

    def test_init_jwt(self, integration):
        """Test DocuSign integration initialization with JWT."""
        assert integration.name == "docusign"
        assert integration.display_name == "DocuSign"
        assert "send_envelope" in integration.supported_actions
        assert "get_envelope_status" in integration.supported_actions

    def test_init_oauth(self, oauth_credentials):
        """Test DocuSign integration initialization with OAuth."""
        from backend.integrations.docusign import DocuSignIntegration
        integration = DocuSignIntegration(oauth_credentials)
        assert integration.name == "docusign"

    def test_missing_credentials(self):
        """Test missing credentials raises error."""
        from backend.integrations.docusign import DocuSignIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError) as exc:
            DocuSignIntegration({})
        assert "required" in str(exc.value).lower()

    def test_missing_account_id(self):
        """Test missing account_id raises error."""
        from backend.integrations.docusign import DocuSignIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            DocuSignIntegration({"access_token": "token"})

    @pytest.mark.asyncio
    async def test_send_envelope(self, integration):
        """Test send_envelope action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "envelopeId": "env-123",
            "status": "sent",
            "statusDateTime": "2024-01-01T00:00:00Z",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("send_envelope", {
                "document_base64": "dGVzdA==",
                "document_name": "test.pdf",
                "signers": [{"name": "John Doe", "email": "john@example.com"}],
            })

        assert result.success
        assert result.data["envelope_id"] == "env-123"
        assert result.data["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_envelope_missing_params(self, integration):
        """Test send_envelope with missing parameters."""
        result = await integration.execute_action("send_envelope", {})
        assert not result.success
        assert "missing" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_get_envelope_status(self, integration):
        """Test get_envelope_status action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "envelopeId": "env-123",
            "status": "completed",
            "sentDateTime": "2024-01-01T00:00:00Z",
            "completedDateTime": "2024-01-02T00:00:00Z",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("get_envelope_status", {"envelope_id": "env-123"})

        assert result.success
        assert result.data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_void_envelope(self, integration):
        """Test void_envelope action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("void_envelope", {
                "envelope_id": "env-123",
                "void_reason": "Test void",
            })

        assert result.success
        assert result.data["status"] == "voided"


# =============================================================================
# Jira Integration Tests
# =============================================================================


class TestJiraIntegration:
    """Tests for Jira integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Jira credentials."""
        return {
            "email": "user@example.com",
            "api_token": "test-api-token",
            "domain": "mycompany.atlassian.net",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Jira integration instance."""
        from backend.integrations.jira import JiraIntegration
        return JiraIntegration(valid_credentials)

    def test_init(self, integration):
        """Test Jira integration initialization."""
        assert integration.name == "jira"
        assert integration.display_name == "Jira"
        assert "create_issue" in integration.supported_actions
        assert "search_issues" in integration.supported_actions

    def test_missing_credentials(self):
        """Test missing credentials raises error."""
        from backend.integrations.jira import JiraIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            JiraIntegration({})

    @pytest.mark.asyncio
    async def test_create_issue(self, integration):
        """Test create_issue action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "10001",
            "key": "PROJ-123",
            "self": "https://example.atlassian.net/rest/api/3/issue/10001",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("create_issue", {
                "project_key": "PROJ",
                "summary": "Test issue",
                "issue_type": "Task",
            })

        assert result.success
        assert result.data["issue_key"] == "PROJ-123"

    @pytest.mark.asyncio
    async def test_search_issues(self, integration):
        """Test search_issues action with JQL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "issues": [
                {"id": "1", "key": "PROJ-1", "fields": {"summary": "Issue 1", "status": {"name": "Open"}}},
                {"id": "2", "key": "PROJ-2", "fields": {"summary": "Issue 2", "status": {"name": "Done"}}},
            ],
            "total": 2,
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("search_issues", {
                "jql": "project = PROJ AND status = Open",
            })

        assert result.success
        assert result.data["total"] == 2
        assert len(result.data["issues"]) == 2

    @pytest.mark.asyncio
    async def test_add_comment(self, integration):
        """Test add_comment action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "comment-123"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("add_comment", {
                "issue_key": "PROJ-123",
                "body": "This is a test comment",
            })

        assert result.success


# =============================================================================
# Datadog Integration Tests
# =============================================================================


class TestDatadogIntegration:
    """Tests for Datadog integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Datadog credentials."""
        return {
            "api_key": "test-api-key",
            "app_key": "test-app-key",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Datadog integration instance."""
        from backend.integrations.datadog import DatadogIntegration
        return DatadogIntegration(valid_credentials)

    def test_init(self, integration):
        """Test Datadog integration initialization."""
        assert integration.name == "datadog"
        assert integration.display_name == "Datadog"
        assert "send_metric" in integration.supported_actions
        assert "send_event" in integration.supported_actions

    def test_missing_api_key(self):
        """Test missing API key raises error."""
        from backend.integrations.datadog import DatadogIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            DatadogIntegration({"app_key": "test"})

    @pytest.mark.asyncio
    async def test_send_event(self, integration):
        """Test send_event action."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("send_event", {
                "title": "Test Event",
                "text": "This is a test event",
                "alert_type": "info",
            })

        assert result.success

    @pytest.mark.asyncio
    async def test_send_metric(self, integration):
        """Test send_metric action."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("send_metric", {
                "metric": "custom.metric",
                "points": [[datetime.utcnow().timestamp(), 100]],
                "type": "gauge",
            })

        assert result.success

    @pytest.mark.asyncio
    async def test_list_monitors(self, integration):
        """Test list_monitors action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "name": "Monitor 1", "type": "metric alert"},
            {"id": 2, "name": "Monitor 2", "type": "service check"},
        ]

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_monitors", {})

        assert result.success
        assert len(result.data["monitors"]) == 2


# =============================================================================
# PagerDuty Integration Tests
# =============================================================================


class TestPagerDutyIntegration:
    """Tests for PagerDuty integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid PagerDuty credentials."""
        return {
            "api_token": "test-api-token",
            "routing_key": "test-routing-key",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create PagerDuty integration instance."""
        from backend.integrations.pagerduty import PagerDutyIntegration
        return PagerDutyIntegration(valid_credentials)

    def test_init(self, integration):
        """Test PagerDuty integration initialization."""
        assert integration.name == "pagerduty"
        assert integration.display_name == "PagerDuty"
        assert "trigger_incident" in integration.supported_actions
        assert "resolve_incident" in integration.supported_actions

    def test_missing_credentials(self):
        """Test missing credentials raises error."""
        from backend.integrations.pagerduty import PagerDutyIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            PagerDutyIntegration({})

    @pytest.mark.asyncio
    async def test_trigger_incident(self, integration):
        """Test trigger_incident action."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "status": "success",
            "dedup_key": "incident-123",
        }

        with patch.object(integration, "_make_events_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("trigger_incident", {
                "summary": "Test incident",
                "severity": "critical",
                "source": "test",
            })

        assert result.success
        assert result.data["dedup_key"] == "incident-123"

    @pytest.mark.asyncio
    async def test_resolve_incident(self, integration):
        """Test resolve_incident action."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"status": "success"}

        with patch.object(integration, "_make_events_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("resolve_incident", {
                "dedup_key": "incident-123",
            })

        assert result.success
        assert result.data["resolved"]

    @pytest.mark.asyncio
    async def test_list_oncalls(self, integration):
        """Test list_oncalls action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "oncalls": [
                {"user": {"summary": "User 1"}, "escalation_policy": {"summary": "Policy 1"}},
            ]
        }

        with patch.object(integration, "_make_rest_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_oncalls", {})

        assert result.success
        assert len(result.data["oncalls"]) == 1


# =============================================================================
# Okta Integration Tests
# =============================================================================


class TestOktaIntegration:
    """Tests for Okta integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Okta credentials."""
        return {
            "api_token": "test-api-token",
            "domain": "dev-123456.okta.com",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Okta integration instance."""
        from backend.integrations.okta import OktaIntegration
        return OktaIntegration(valid_credentials)

    def test_init(self, integration):
        """Test Okta integration initialization."""
        assert integration.name == "okta"
        assert integration.display_name == "Okta"
        assert "list_users" in integration.supported_actions
        assert "create_user" in integration.supported_actions

    def test_missing_credentials(self):
        """Test missing credentials raises error."""
        from backend.integrations.okta import OktaIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            OktaIntegration({})

    @pytest.mark.asyncio
    async def test_list_users(self, integration):
        """Test list_users action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "1", "profile": {"email": "user1@test.com", "firstName": "User", "lastName": "One"}, "status": "ACTIVE"},
            {"id": "2", "profile": {"email": "user2@test.com", "firstName": "User", "lastName": "Two"}, "status": "ACTIVE"},
        ]

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_users", {})

        assert result.success
        assert len(result.data["users"]) == 2

    @pytest.mark.asyncio
    async def test_create_user(self, integration):
        """Test create_user action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "new-user-id",
            "profile": {"email": "new@test.com"},
            "status": "PROVISIONED",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("create_user", {
                "email": "new@test.com",
                "first_name": "New",
                "last_name": "User",
            })

        assert result.success
        assert result.data["user_id"] == "new-user-id"

    @pytest.mark.asyncio
    async def test_add_user_to_group(self, integration):
        """Test add_user_to_group action."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("add_user_to_group", {
                "user_id": "user-123",
                "group_id": "group-456",
            })

        assert result.success
        assert result.data["added"]


# =============================================================================
# ServiceNow Integration Tests
# =============================================================================


class TestServiceNowIntegration:
    """Tests for ServiceNow integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid ServiceNow credentials."""
        return {
            "instance": "dev12345.service-now.com",
            "username": "admin",
            "password": "password123",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create ServiceNow integration instance."""
        from backend.integrations.servicenow import ServiceNowIntegration
        return ServiceNowIntegration(valid_credentials)

    def test_init(self, integration):
        """Test ServiceNow integration initialization."""
        assert integration.name == "servicenow"
        assert integration.display_name == "ServiceNow"
        assert "create_incident" in integration.supported_actions
        assert "search_records" in integration.supported_actions

    def test_missing_credentials(self):
        """Test missing credentials raises error."""
        from backend.integrations.servicenow import ServiceNowIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            ServiceNowIntegration({})

    @pytest.mark.asyncio
    async def test_create_incident(self, integration):
        """Test create_incident action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "result": {
                "sys_id": "inc-123",
                "number": "INC0010001",
                "state": "1",
                "short_description": "Test incident",
            }
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("create_incident", {
                "short_description": "Test incident",
                "urgency": "2",
            })

        assert result.success
        assert result.data["number"] == "INC0010001"

    @pytest.mark.asyncio
    async def test_list_incidents(self, integration):
        """Test list_incidents action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                {"sys_id": "1", "number": "INC0001", "short_description": "Issue 1", "state": "1", "urgency": "2"},
                {"sys_id": "2", "number": "INC0002", "short_description": "Issue 2", "state": "2", "urgency": "3"},
            ]
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_incidents", {"limit": 25})

        assert result.success
        assert len(result.data["incidents"]) == 2

    @pytest.mark.asyncio
    async def test_search_records(self, integration):
        """Test search_records action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [{"sys_id": "1", "name": "Record 1"}]
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("search_records", {
                "table": "cmdb_ci",
                "query": "name=server1",
            })

        assert result.success
        assert result.data["table"] == "cmdb_ci"


# =============================================================================
# Auth0 Integration Tests
# =============================================================================


class TestAuth0Integration:
    """Tests for Auth0 integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Auth0 credentials."""
        return {
            "domain": "mycompany.auth0.com",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Auth0 integration instance."""
        from backend.integrations.auth0 import Auth0Integration
        return Auth0Integration(valid_credentials)

    def test_init(self, integration):
        """Test Auth0 integration initialization."""
        assert integration.name == "auth0"
        assert integration.display_name == "Auth0"
        assert "list_users" in integration.supported_actions
        assert "assign_roles" in integration.supported_actions

    def test_missing_credentials(self):
        """Test missing credentials raises error."""
        from backend.integrations.auth0 import Auth0Integration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            Auth0Integration({})

    @pytest.mark.asyncio
    async def test_list_users(self, integration):
        """Test list_users action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"user_id": "auth0|1", "email": "user1@test.com", "name": "User 1"},
            {"user_id": "auth0|2", "email": "user2@test.com", "name": "User 2"},
        ]

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            with patch.object(integration, "_get_access_token", new_callable=AsyncMock) as token_mock:
                token_mock.return_value = "test-token"
                result = await integration.execute_action("list_users", {})

        assert result.success
        assert len(result.data["users"]) == 2

    @pytest.mark.asyncio
    async def test_create_user(self, integration):
        """Test create_user action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "user_id": "auth0|new",
            "email": "new@test.com",
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_response.text = "{}"

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            with patch.object(integration, "_get_access_token", new_callable=AsyncMock) as token_mock:
                token_mock.return_value = "test-token"
                result = await integration.execute_action("create_user", {
                    "email": "new@test.com",
                    "password": "SecureP@ss123",
                })

        assert result.success
        assert result.data["user_id"] == "auth0|new"

    @pytest.mark.asyncio
    async def test_assign_roles(self, integration):
        """Test assign_roles action."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            with patch.object(integration, "_get_access_token", new_callable=AsyncMock) as token_mock:
                token_mock.return_value = "test-token"
                result = await integration.execute_action("assign_roles", {
                    "user_id": "auth0|123",
                    "roles": ["role-admin"],
                })

        assert result.success


# =============================================================================
# New Relic Integration Tests
# =============================================================================


class TestNewRelicIntegration:
    """Tests for New Relic integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid New Relic credentials."""
        return {
            "api_key": "NRAK-test-api-key",
            "account_id": "1234567",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create New Relic integration instance."""
        from backend.integrations.newrelic import NewRelicIntegration
        return NewRelicIntegration(valid_credentials)

    def test_init(self, integration):
        """Test New Relic integration initialization."""
        assert integration.name == "newrelic"
        assert integration.display_name == "New Relic"
        assert "query_nrql" in integration.supported_actions
        assert "send_event" in integration.supported_actions

    def test_missing_credentials(self):
        """Test missing credentials raises error."""
        from backend.integrations.newrelic import NewRelicIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            NewRelicIntegration({})

    @pytest.mark.asyncio
    async def test_query_nrql(self, integration):
        """Test query_nrql action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [{"count": 100}]
                        }
                    }
                }
            }
        }

        with patch.object(integration, "_make_graphql_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("query_nrql", {
                "nrql": "SELECT count(*) FROM Transaction",
            })

        assert result.success
        assert len(result.data["results"]) == 1

    @pytest.mark.asyncio
    async def test_send_event(self, integration):
        """Test send_event action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch.object(integration, "_make_events_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("send_event", {
                "event_type": "CustomEvent",
                "attributes": {"key": "value"},
            })

        assert result.success

    @pytest.mark.asyncio
    async def test_list_applications(self, integration):
        """Test list_applications action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "applications": [
                {"id": 1, "name": "App 1", "language": "python", "health_status": "green"},
                {"id": 2, "name": "App 2", "language": "nodejs", "health_status": "gray"},
            ]
        }

        with patch.object(integration, "_make_rest_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_applications", {})

        assert result.success
        assert len(result.data["applications"]) == 2


# =============================================================================
# Microsoft Teams Integration Tests
# =============================================================================


class TestMicrosoftTeamsIntegration:
    """Tests for Microsoft Teams integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Microsoft Teams credentials."""
        return {
            "tenant_id": "test-tenant-id",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Microsoft Teams integration instance."""
        from backend.integrations.microsoft_teams import MicrosoftTeamsIntegration
        return MicrosoftTeamsIntegration(valid_credentials)

    def test_init(self, integration):
        """Test Microsoft Teams integration initialization."""
        assert integration.name == "microsoft_teams"
        assert integration.display_name == "Microsoft Teams"
        assert "send_message" in integration.supported_actions

    def test_missing_credentials(self):
        """Test missing credentials raises error."""
        from backend.integrations.microsoft_teams import MicrosoftTeamsIntegration
        from backend.integrations.base import IntegrationError

        with pytest.raises(IntegrationError):
            MicrosoftTeamsIntegration({})

    @pytest.mark.asyncio
    async def test_send_message(self, integration):
        """Test send_message action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "msg-123"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            with patch.object(integration, "_get_access_token", new_callable=AsyncMock) as token_mock:
                token_mock.return_value = "test-token"
                result = await integration.execute_action("send_message", {
                    "team_id": "team-123",
                    "channel_id": "channel-456",
                    "content": "Hello, Teams!",
                })

        assert result.success

    @pytest.mark.asyncio
    async def test_list_teams(self, integration):
        """Test list_teams action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"id": "1", "displayName": "Team 1"},
                {"id": "2", "displayName": "Team 2"},
            ]
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            with patch.object(integration, "_get_access_token", new_callable=AsyncMock) as token_mock:
                token_mock.return_value = "test-token"
                result = await integration.execute_action("list_teams", {})

        assert result.success
        assert len(result.data["teams"]) == 2


# =============================================================================
# Connection Pooling and Retry Tests
# =============================================================================


class TestConnectionResilience:
    """Tests for connection pooling and retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_429(self):
        """Test that 429 responses trigger retries."""
        from backend.integrations.okta import OktaIntegration

        integration = OktaIntegration({
            "api_token": "test-token",
            "domain": "test.okta.com",
        })

        # Mock responses: 429, 429, then 200
        mock_responses = [
            MagicMock(status_code=429, headers={"X-Rate-Limit-Reset": str(int(datetime.utcnow().timestamp()) + 1)}),
            MagicMock(status_code=429, headers={}),
            MagicMock(status_code=200, json=lambda: []),
        ]

        call_count = 0
        async def mock_request(*args, **kwargs):
            nonlocal call_count
            response = mock_responses[min(call_count, len(mock_responses) - 1)]
            call_count += 1
            return response

        with patch.object(integration, "_get_client", new_callable=AsyncMock) as mock_client:
            mock_client.return_value = MagicMock(request=mock_request)

            # This should succeed after retries
            result = await integration.execute_action("list_users", {})

        assert call_count >= 2  # Should have retried at least once

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        """Test that 5xx responses trigger retries."""
        from backend.integrations.datadog import DatadogIntegration

        integration = DatadogIntegration({
            "api_key": "test-key",
            "app_key": "test-app-key",
        })

        # First call fails with 503, second succeeds
        responses = [
            MagicMock(status_code=503),
            MagicMock(status_code=200, json=lambda: []),
        ]

        call_count = 0
        async def mock_request(*args, **kwargs):
            nonlocal call_count
            response = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return response

        with patch.object(integration, "_get_client", new_callable=AsyncMock) as mock_client:
            mock_client.return_value = MagicMock(request=mock_request)

            result = await integration.execute_action("list_monitors", {})

        assert call_count == 2  # Should have retried once


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_jira_invalid_issue_key_format(self):
        """Test Jira handles invalid issue key format."""
        from backend.integrations.jira import JiraIntegration

        integration = JiraIntegration({
            "email": "test@example.com",
            "api_token": "test-token",
            "domain": "test.atlassian.net",
        })

        result = await integration.execute_action("update_issue", {
            "issue_key": "",  # Empty issue key
            "summary": "Test",
        })

        assert not result.success
        assert "issue_key" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_servicenow_empty_incident_data(self):
        """Test ServiceNow handles missing required fields."""
        from backend.integrations.servicenow import ServiceNowIntegration

        integration = ServiceNowIntegration({
            "instance": "test",
            "username": "admin",
            "password": "secret",
        })

        result = await integration.execute_action("create_incident", {})

        assert not result.success
        assert "short_description" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_okta_deactivate_missing_user(self):
        """Test Okta deactivate handles missing user_id."""
        from backend.integrations.okta import OktaIntegration

        integration = OktaIntegration({
            "api_token": "test-token",
            "domain": "test.okta.com",
        })

        result = await integration.execute_action("deactivate_user", {})

        assert not result.success
        assert "user_id" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_datadog_invalid_metric_type(self):
        """Test Datadog handles metric submission."""
        from backend.integrations.datadog import DatadogIntegration

        integration = DatadogIntegration({
            "api_key": "test-key",
            "app_key": "test-app-key",
        })

        result = await integration.execute_action("send_metric", {
            "metric": "test.metric",
            # Missing value
        })

        assert not result.success

    @pytest.mark.asyncio
    async def test_pagerduty_trigger_missing_service(self):
        """Test PagerDuty trigger needs routing_key or service_key."""
        from backend.integrations.pagerduty import PagerDutyIntegration

        integration = PagerDutyIntegration({
            "api_token": "test-token",
        })

        result = await integration.execute_action("trigger_incident", {
            "summary": "Test incident",
            # Missing routing_key
        })

        assert not result.success

    @pytest.mark.asyncio
    async def test_auth0_create_user_validation(self):
        """Test Auth0 create_user validates required fields."""
        from backend.integrations.auth0 import Auth0Integration

        integration = Auth0Integration({
            "domain": "test.auth0.com",
            "client_id": "test-client",
            "client_secret": "test-secret",
        })

        result = await integration.execute_action("create_user", {
            # Missing email and connection
        })

        assert not result.success

    @pytest.mark.asyncio
    async def test_newrelic_nrql_missing_query(self):
        """Test New Relic NRQL action requires query."""
        from backend.integrations.newrelic import NewRelicIntegration

        integration = NewRelicIntegration({
            "api_key": "test-key",
            "account_id": "12345",
        })

        result = await integration.execute_action("query_nrql", {})

        assert not result.success
        assert "nrql" in result.error_message.lower() or "query" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_teams_send_message_missing_channel(self):
        """Test Teams send_message requires team and channel."""
        from backend.integrations.microsoft_teams import MicrosoftTeamsIntegration

        integration = MicrosoftTeamsIntegration({
            "client_id": "test-client",
            "client_secret": "test-secret",
            "tenant_id": "test-tenant",
        })

        result = await integration.execute_action("send_message", {
            "content": "Test message",
            # Missing team_id and channel_id
        })

        assert not result.success


class TestDocuSignEdgeCases:
    """Additional DocuSign edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.docusign import DocuSignIntegration
        return DocuSignIntegration({
            "access_token": "test-token",
            "account_id": "test-account",
        })

    @pytest.mark.asyncio
    async def test_void_envelope_missing_envelope_id(self, integration):
        """Test void_envelope requires envelope_id."""
        result = await integration.execute_action("void_envelope", {
            # Missing envelope_id
            "void_reason": "Test void",
        })

        assert not result.success
        assert "envelope_id" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_list_envelopes_default_params(self, integration):
        """Test list_envelopes with default parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "envelopes": [],
            "totalSetSize": "0",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_envelopes", {})

        assert result.success


class TestJiraEdgeCases:
    """Additional Jira edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.jira import JiraIntegration
        return JiraIntegration({
            "email": "test@example.com",
            "api_token": "test-token",
            "domain": "test.atlassian.net",
        })

    @pytest.mark.asyncio
    async def test_transition_issue_missing_transition_id(self, integration):
        """Test transition_issue requires transition_id."""
        result = await integration.execute_action("transition_issue", {
            "issue_key": "TEST-123",
            # Missing transition_id
        })

        assert not result.success
        assert "transition" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_get_issue_success(self, integration):
        """Test get_issue action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "10001",
            "key": "TEST-123",
            "fields": {
                "summary": "Test issue",
                "status": {"name": "Open"},
            },
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("get_issue", {
                "issue_key": "TEST-123",
            })

        assert result.success
        assert result.data["issue_key"] == "TEST-123"


class TestServiceNowEdgeCases:
    """Additional ServiceNow edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.servicenow import ServiceNowIntegration
        return ServiceNowIntegration({
            "instance": "test",
            "username": "admin",
            "password": "secret",
        })

    @pytest.mark.asyncio
    async def test_update_incident_requires_sys_id(self, integration):
        """Test update_incident requires sys_id."""
        result = await integration.execute_action("update_incident", {
            "state": "2",
        })

        assert not result.success

    @pytest.mark.asyncio
    async def test_create_change_request(self, integration):
        """Test create_change_request action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "result": {
                "sys_id": "cr-123",
                "number": "CHG0001234",
            },
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("create_change_request", {
                "short_description": "Test change",
            })

        assert result.success


class TestOktaEdgeCases:
    """Additional Okta edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.okta import OktaIntegration
        return OktaIntegration({
            "api_token": "test-token",
            "domain": "test.okta.com",
        })

    @pytest.mark.asyncio
    async def test_create_user_with_minimal_data(self, integration):
        """Test create_user with only required fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "user-123",
            "profile": {"email": "test@example.com"},
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("create_user", {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
            })

        assert result.success

    @pytest.mark.asyncio
    async def test_list_groups(self, integration):
        """Test list_groups action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "grp-1", "profile": {"name": "Group 1"}},
            {"id": "grp-2", "profile": {"name": "Group 2"}},
        ]

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_groups", {})

        assert result.success
        assert len(result.data["groups"]) == 2


class TestAuth0EdgeCases:
    """Additional Auth0 edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.auth0 import Auth0Integration
        return Auth0Integration({
            "domain": "test.auth0.com",
            "client_id": "test-client",
            "client_secret": "test-secret",
        })

    @pytest.mark.asyncio
    async def test_get_user(self, integration):
        """Test get_user action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user_id": "auth0|123",
            "email": "test@example.com",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("get_user", {
                "user_id": "auth0|123",
            })

        assert result.success
        assert result.data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_list_connections(self, integration):
        """Test list_connections action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "con-1", "name": "Username-Password"},
            {"id": "con-2", "name": "Google"},
        ]

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_connections", {})

        assert result.success


class TestNewRelicEdgeCases:
    """Additional New Relic edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.newrelic import NewRelicIntegration
        return NewRelicIntegration({
            "api_key": "test-key",
            "account_id": "12345",
        })

    @pytest.mark.asyncio
    async def test_list_alerts(self, integration):
        """Test list_alerts action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "policies": [
                {"id": 1, "name": "Alert Policy 1"},
            ],
        }

        with patch.object(integration, "_make_rest_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_alerts", {})

        assert result.success


class TestDatadogEdgeCases:
    """Additional Datadog edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.datadog import DatadogIntegration
        return DatadogIntegration({
            "api_key": "test-key",
            "app_key": "test-app-key",
        })

    @pytest.mark.asyncio
    async def test_create_incident(self, integration):
        """Test create_incident action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "id": "inc-123",
                "attributes": {"title": "Test Incident"},
            },
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("create_incident", {
                "title": "Test Incident",
            })

        assert result.success

    @pytest.mark.asyncio
    async def test_send_log(self, integration):
        """Test send_log action."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {}

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(integration, "_get_client", new_callable=AsyncMock) as mock:
            mock.return_value = mock_client
            result = await integration.execute_action("send_log", {
                "message": "Test log message",
            })

        assert result.success


class TestPagerDutyEdgeCases:
    """Additional PagerDuty edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.pagerduty import PagerDutyIntegration
        return PagerDutyIntegration({
            "api_token": "test-token",
        })

    @pytest.mark.asyncio
    async def test_list_services(self, integration):
        """Test list_services action."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "services": [
                {"id": "svc-1", "name": "Service 1"},
                {"id": "svc-2", "name": "Service 2"},
            ],
        }

        with patch.object(integration, "_make_rest_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_services", {})

        assert result.success
        assert len(result.data["services"]) == 2

    @pytest.mark.asyncio
    async def test_acknowledge_incident(self, integration):
        """Test acknowledge_incident action."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {}

        with patch.object(integration, "_make_events_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("acknowledge_incident", {
                "dedup_key": "dedup-123",
            })

        assert result.success
        assert result.data["acknowledged"] is True


class TestMicrosoftTeamsEdgeCases:
    """Additional Microsoft Teams edge case tests."""

    @pytest.fixture
    def integration(self):
        from backend.integrations.microsoft_teams import MicrosoftTeamsIntegration
        return MicrosoftTeamsIntegration({
            "client_id": "test-client",
            "client_secret": "test-secret",
            "tenant_id": "test-tenant",
        })

    @pytest.mark.asyncio
    async def test_create_channel(self, integration):
        """Test create_channel action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "channel-123",
            "displayName": "Test Channel",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("create_channel", {
                "team_id": "team-123",
                "display_name": "Test Channel",
            })

        assert result.success

    @pytest.mark.asyncio
    async def test_create_meeting(self, integration):
        """Test create_meeting action."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "meeting-123",
            "subject": "Test Meeting",
            "joinWebUrl": "https://teams.microsoft.com/l/meetup-join/...",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("create_meeting", {
                "subject": "Test Meeting",
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T11:00:00Z",
            })

        assert result.success


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
