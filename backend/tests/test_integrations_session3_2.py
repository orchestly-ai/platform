#!/usr/bin/env python3
"""
Tests for Session 3.2 Integrations: Jira and Asana

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
from backend.integrations.jira import JiraIntegration
from backend.integrations.asana import AsanaIntegration


# ============================================================================
# Jira Integration Tests
# ============================================================================

class TestJiraIntegration:
    """Tests for Jira integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Jira credentials."""
        return {
            "domain": "mycompany",
            "email": "user@example.com",
            "api_token": "test-api-token-12345",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Jira integration instance."""
        return JiraIntegration(auth_credentials=valid_credentials)

    def test_init_with_valid_credentials(self, integration):
        """Test initialization with valid credentials."""
        assert integration.name == "jira"
        assert integration.display_name == "Jira"
        assert integration.auth_type == AuthType.BASIC_AUTH

    def test_init_missing_domain(self):
        """Test initialization without domain."""
        with pytest.raises(IntegrationError) as exc:
            JiraIntegration(auth_credentials={
                "email": "user@example.com",
                "api_token": "token",
            })
        assert "domain" in str(exc.value)

    def test_init_missing_email(self):
        """Test initialization without email."""
        with pytest.raises(IntegrationError) as exc:
            JiraIntegration(auth_credentials={
                "domain": "mycompany",
                "api_token": "token",
            })
        assert "email" in str(exc.value)

    def test_init_missing_api_token(self):
        """Test initialization without api_token."""
        with pytest.raises(IntegrationError) as exc:
            JiraIntegration(auth_credentials={
                "domain": "mycompany",
                "email": "user@example.com",
            })
        assert "api_token" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "create_issue" in actions
        assert "get_issue" in actions
        assert "update_issue" in actions
        assert "add_comment" in actions
        assert "transition_issue" in actions
        assert "search_issues" in actions
        assert "list_projects" in actions
        assert "test_connection" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("create_issue")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")
        assert "not supported" in str(exc.value)

    def test_get_base_url_short_domain(self, integration):
        """Test base URL with short domain."""
        url = integration._get_base_url()
        assert url == "https://mycompany/rest/api/3"

    def test_get_base_url_full_url(self):
        """Test base URL with full URL domain."""
        integration = JiraIntegration(auth_credentials={
            "domain": "https://mycompany.atlassian.net",
            "email": "user@example.com",
            "api_token": "token",
        })
        url = integration._get_base_url()
        assert url == "https://mycompany.atlassian.net/rest/api/3"

    def test_get_auth_header(self, integration):
        """Test that auth header is Basic auth."""
        auth_header = integration._get_auth_header()

        assert auth_header.startswith("Basic ")

    @pytest.mark.asyncio
    async def test_create_issue_missing_params(self, integration):
        """Test create_issue with missing parameters."""
        result = await integration.execute_action(
            "create_issue",
            {"project_key": "PROJ"}  # Missing summary and issue_type
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_issue_missing_key(self, integration):
        """Test get_issue without issue_key."""
        result = await integration.execute_action(
            "get_issue",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_update_issue_missing_key(self, integration):
        """Test update_issue without issue_key."""
        result = await integration.execute_action(
            "update_issue",
            {}  # No issue_key
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_add_comment_missing_params(self, integration):
        """Test add_comment without required params."""
        result = await integration.execute_action(
            "add_comment",
            {"issue_key": "PROJ-123"}  # Missing body
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_transition_missing_params(self, integration):
        """Test transition_issue without transition info."""
        result = await integration.execute_action(
            "transition_issue",
            {"issue_key": "PROJ-123"}  # Missing transition_id/name
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_transition_missing_transition_id(self, integration):
        """Test transition_issue without transition_id."""
        result = await integration.execute_action(
            "transition_issue",
            {"issue_key": "PROJ-123"}  # Missing transition_id
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_add_comment_missing_body(self, integration):
        """Test add_comment without body."""
        result = await integration.execute_action(
            "add_comment",
            {"issue_key": "PROJ-123"}  # Missing body
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_create_issue_success(self, integration):
        """Test successful issue creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json = MagicMock(return_value={
            "id": "12345",
            "key": "PROJ-123",
            "self": "https://mycompany.atlassian.net/rest/api/3/issue/12345",
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(JiraIntegration, '_get_client', return_value=mock_client):
            result = await integration.execute_action(
                "create_issue",
                {
                    "project_key": "PROJ",
                    "summary": "Test Issue",
                    "issue_type": "Story",
                }
            )

        assert result.success is True
        assert result.data["issue_key"] == "PROJ-123"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, integration):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "accountId": "123456",
            "emailAddress": "user@example.com",
            "displayName": "Test User",
            "active": True,
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(JiraIntegration, '_get_client', return_value=mock_client):
            result = await integration.test_connection()

        assert result.success is True
        assert result.data["account_id"] == "123456"

    @pytest.mark.asyncio
    async def test_search_issues_success(self, integration):
        """Test successful issue search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "issues": [
                {
                    "key": "PROJ-1",
                    "fields": {
                        "summary": "Issue 1",
                        "status": {"name": "Open"},
                        "issuetype": {"name": "Story"},
                        "priority": {"name": "High"},
                    }
                },
                {
                    "key": "PROJ-2",
                    "fields": {
                        "summary": "Issue 2",
                        "status": {"name": "Done"},
                        "issuetype": {"name": "Bug"},
                        "priority": {"name": "Low"},
                    }
                },
            ],
            "total": 2,
            "startAt": 0,
            "maxResults": 50,
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(JiraIntegration, '_get_client', return_value=mock_client):
            result = await integration.execute_action(
                "search_issues",
                {"jql": "project = PROJ"}
            )

        assert result.success is True
        assert result.data["total"] == 2
        assert len(result.data["issues"]) == 2


# ============================================================================
# Asana Integration Tests
# ============================================================================

class TestAsanaIntegration:
    """Tests for Asana integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Asana credentials."""
        return {"access_token": "test-access-token-12345"}

    @pytest.fixture
    def valid_pat_credentials(self):
        """Valid Personal Access Token credentials."""
        return {"personal_access_token": "test-pat-12345"}

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Asana integration instance."""
        return AsanaIntegration(auth_credentials=valid_credentials)

    def test_init_with_access_token(self, integration):
        """Test initialization with access token."""
        assert integration.name == "asana"
        assert integration.display_name == "Asana"
        assert integration.auth_type == AuthType.OAUTH2

    def test_init_with_personal_token(self, valid_pat_credentials):
        """Test initialization with personal access token."""
        integration = AsanaIntegration(auth_credentials=valid_pat_credentials)
        assert integration.name == "asana"

    def test_init_missing_token(self):
        """Test initialization without token."""
        with pytest.raises(IntegrationError) as exc:
            AsanaIntegration(auth_credentials={"other": "value"})
        assert "access_token" in str(exc.value) or "personal_access_token" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "create_task" in actions
        assert "get_task" in actions
        assert "update_task" in actions
        assert "complete_task" in actions
        assert "add_comment" in actions
        assert "list_projects" in actions
        assert "list_tasks" in actions
        assert "assign_task" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("create_task")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")
        assert "not supported" in str(exc.value)

    def test_get_headers(self, integration):
        """Test that headers include Bearer token."""
        headers = integration._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert "Content-Type" in headers

    @pytest.mark.asyncio
    async def test_create_task_missing_name(self, integration):
        """Test create_task without name."""
        result = await integration.execute_action(
            "create_task",
            {"project_gid": "123"}  # Missing name
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_create_task_missing_context(self, integration):
        """Test create_task without project or workspace."""
        result = await integration.execute_action(
            "create_task",
            {"name": "My Task"}  # Missing project_gid or workspace_gid
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_task_missing_gid(self, integration):
        """Test get_task without task_gid."""
        result = await integration.execute_action(
            "get_task",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_update_task_no_fields(self, integration):
        """Test update_task without fields to update."""
        result = await integration.execute_action(
            "update_task",
            {"task_gid": "123"}  # No update fields
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_complete_task_missing_gid(self, integration):
        """Test complete_task without task_gid."""
        result = await integration.execute_action(
            "complete_task",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_add_comment_missing_params(self, integration):
        """Test add_comment without required params."""
        result = await integration.execute_action(
            "add_comment",
            {"task_gid": "123"}  # Missing text
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_list_projects_missing_workspace(self, integration):
        """Test list_projects without workspace_gid."""
        result = await integration.execute_action(
            "list_projects",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_list_tasks_missing_context(self, integration):
        """Test list_tasks without project or section."""
        result = await integration.execute_action(
            "list_tasks",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_assign_task_missing_params(self, integration):
        """Test assign_task without required params."""
        result = await integration.execute_action(
            "assign_task",
            {"task_gid": "123"}  # Missing assignee
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_create_task_success(self, mock_session_class, integration):
        """Test successful task creation."""
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json = AsyncMock(return_value={
            "data": {
                "gid": "12345",
                "name": "My Task",
                "permalink_url": "https://app.asana.com/0/project/12345",
            }
        })

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(),
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_class.return_value = mock_session

        result = await integration.execute_action(
            "create_task",
            {
                "name": "My Task",
                "project_gid": "project-123",
            }
        )

        assert result.success is True
        assert result.data["task_gid"] == "12345"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_test_connection_success(self, mock_session_class, integration):
        """Test successful connection test."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "gid": "user-123",
                "name": "Test User",
                "email": "user@example.com",
                "workspaces": [
                    {"gid": "ws-1", "name": "My Workspace"},
                ],
            }
        })

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(),
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_class.return_value = mock_session

        result = await integration.test_connection()

        assert result.success is True
        assert result.data["user_id"] == "user-123"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_list_projects_success(self, mock_session_class, integration):
        """Test successful project listing."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": [
                {"gid": "proj-1", "name": "Project 1"},
                {"gid": "proj-2", "name": "Project 2"},
            ]
        })

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(),
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_class.return_value = mock_session

        result = await integration.execute_action(
            "list_projects",
            {"workspace_gid": "ws-123"}
        )

        assert result.success is True
        assert result.data["total"] == 2

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_complete_task_success(self, mock_session_class, integration):
        """Test successful task completion."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "gid": "12345",
                "completed": True,
            }
        })

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(),
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_class.return_value = mock_session

        result = await integration.execute_action(
            "complete_task",
            {"task_gid": "12345"}
        )

        assert result.success is True
        assert result.data["completed"] is True


# ============================================================================
# Base Integration Tests
# ============================================================================

class TestBaseIntegrationPattern:
    """Tests to verify integrations follow the base pattern."""

    def test_jira_is_base_integration(self):
        """Verify Jira inherits from BaseIntegration."""
        assert issubclass(JiraIntegration, BaseIntegration)

    def test_asana_is_base_integration(self):
        """Verify Asana inherits from BaseIntegration."""
        assert issubclass(AsanaIntegration, BaseIntegration)

    def test_jira_auth_type(self):
        """Verify Jira uses BASIC_AUTH."""
        integration = JiraIntegration(auth_credentials={
            "domain": "test",
            "email": "test@example.com",
            "api_token": "token",
        })
        assert integration.auth_type == AuthType.BASIC_AUTH

    def test_asana_auth_type(self):
        """Verify Asana uses OAUTH2."""
        integration = AsanaIntegration(auth_credentials={"access_token": "token"})
        assert integration.auth_type == AuthType.OAUTH2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
