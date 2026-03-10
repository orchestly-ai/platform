#!/usr/bin/env python3
"""
Tests for Session 3.3 Integrations: Notion and Airtable

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
from backend.integrations.notion import NotionIntegration
from backend.integrations.airtable import AirtableIntegration


# ============================================================================
# Notion Integration Tests
# ============================================================================

class TestNotionIntegration:
    """Tests for Notion integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Notion credentials."""
        return {"integration_token": "secret_test_token_12345"}

    @pytest.fixture
    def api_key_credentials(self):
        """Credentials with api_key instead of integration_token."""
        return {"api_key": "secret_test_token_12345"}

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Notion integration instance."""
        return NotionIntegration(auth_credentials=valid_credentials)

    def test_init_with_integration_token(self, integration):
        """Test initialization with integration token."""
        assert integration.name == "notion"
        assert integration.display_name == "Notion"
        assert integration.auth_type == AuthType.API_KEY

    def test_init_with_api_key(self, api_key_credentials):
        """Test initialization with api_key."""
        integration = NotionIntegration(auth_credentials=api_key_credentials)
        assert integration.name == "notion"

    def test_init_missing_token(self):
        """Test initialization without token."""
        with pytest.raises(IntegrationError) as exc:
            NotionIntegration(auth_credentials={"other": "value"})
        assert "integration_token" in str(exc.value) or "api_key" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "create_page" in actions
        assert "get_page" in actions
        assert "update_page" in actions
        assert "search" in actions
        assert "create_database" in actions
        assert "query_database" in actions
        assert "append_blocks" in actions
        assert "get_block_children" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("create_page")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")
        assert "not supported" in str(exc.value)

    def test_get_headers(self, integration):
        """Test that headers include Bearer token and Notion-Version."""
        headers = integration._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert "Notion-Version" in headers
        assert headers["Notion-Version"] == "2022-06-28"

    @pytest.mark.asyncio
    async def test_create_page_missing_parent(self, integration):
        """Test create_page without parent_id."""
        result = await integration.execute_action(
            "create_page",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_page_missing_id(self, integration):
        """Test get_page without page_id."""
        result = await integration.execute_action(
            "get_page",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_update_page_no_changes(self, integration):
        """Test update_page without properties to update."""
        result = await integration.execute_action(
            "update_page",
            {"page_id": "page-123"}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_create_database_missing_params(self, integration):
        """Test create_database without required params."""
        result = await integration.execute_action(
            "create_database",
            {"parent_id": "page-123"}  # Missing title
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_query_database_missing_id(self, integration):
        """Test query_database without database_id."""
        result = await integration.execute_action(
            "query_database",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_append_blocks_missing_params(self, integration):
        """Test append_blocks without required params."""
        result = await integration.execute_action(
            "append_blocks",
            {"block_id": "block-123"}  # Missing children
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_block_children_missing_id(self, integration):
        """Test get_block_children without block_id."""
        result = await integration.execute_action(
            "get_block_children",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_create_page_success(self, mock_session_class, integration):
        """Test successful page creation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "page-123",
            "url": "https://notion.so/page-123",
            "created_time": "2025-01-01T00:00:00.000Z",
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
            "create_page",
            {
                "parent_id": "parent-page-123",
                "title": "Test Page",
            }
        )

        assert result.success is True
        assert result.data["page_id"] == "page-123"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_test_connection_success(self, mock_session_class, integration):
        """Test successful connection test."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "user-123",
            "name": "Test Integration",
            "type": "bot",
            "avatar_url": None,
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
    async def test_search_success(self, mock_session_class, integration):
        """Test successful search."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "results": [
                {
                    "id": "page-1",
                    "object": "page",
                    "url": "https://notion.so/page-1",
                    "properties": {
                        "title": {"title": [{"plain_text": "Page 1"}]}
                    }
                },
            ],
            "has_more": False,
            "next_cursor": None,
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
            "search",
            {"query": "test"}
        )

        assert result.success is True
        assert len(result.data["results"]) == 1


# ============================================================================
# Airtable Integration Tests
# ============================================================================

class TestAirtableIntegration:
    """Tests for Airtable integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Airtable credentials."""
        return {"api_key": "pat_test_12345"}

    @pytest.fixture
    def access_token_credentials(self):
        """Credentials with access_token."""
        return {"access_token": "pat_test_12345"}

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Airtable integration instance."""
        return AirtableIntegration(auth_credentials=valid_credentials)

    def test_init_with_api_key(self, integration):
        """Test initialization with api_key."""
        assert integration.name == "airtable"
        assert integration.display_name == "Airtable"
        assert integration.auth_type == AuthType.API_KEY

    def test_init_with_access_token(self, access_token_credentials):
        """Test initialization with access_token."""
        integration = AirtableIntegration(auth_credentials=access_token_credentials)
        assert integration.name == "airtable"

    def test_init_missing_key(self):
        """Test initialization without API key."""
        with pytest.raises(IntegrationError) as exc:
            AirtableIntegration(auth_credentials={"other": "value"})
        assert "api_key" in str(exc.value) or "access_token" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "list_bases" in actions
        assert "list_tables" in actions
        assert "list_records" in actions
        assert "get_record" in actions
        assert "create_record" in actions
        assert "update_record" in actions
        assert "delete_record" in actions
        assert "batch_create" in actions
        assert "batch_update" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("list_records")  # Should not raise

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

    @pytest.mark.asyncio
    async def test_list_tables_missing_base(self, integration):
        """Test list_tables without base_id."""
        result = await integration.execute_action(
            "list_tables",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_list_records_missing_params(self, integration):
        """Test list_records without required params."""
        result = await integration.execute_action(
            "list_records",
            {"base_id": "app123"}  # Missing table_id
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_record_missing_params(self, integration):
        """Test get_record without all required params."""
        result = await integration.execute_action(
            "get_record",
            {"base_id": "app123", "table_id": "tbl123"}  # Missing record_id
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_create_record_missing_params(self, integration):
        """Test create_record without fields."""
        result = await integration.execute_action(
            "create_record",
            {"base_id": "app123", "table_id": "tbl123"}  # Missing fields
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_update_record_missing_params(self, integration):
        """Test update_record without all params."""
        result = await integration.execute_action(
            "update_record",
            {"base_id": "app123", "table_id": "tbl123", "record_id": "rec123"}  # Missing fields
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_delete_record_missing_params(self, integration):
        """Test delete_record without all params."""
        result = await integration.execute_action(
            "delete_record",
            {"base_id": "app123", "table_id": "tbl123"}  # Missing record_id
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_batch_create_too_many_records(self, integration):
        """Test batch_create with more than 10 records."""
        records = [{"fields": {"Name": f"Record {i}"}} for i in range(11)]

        result = await integration.execute_action(
            "batch_create",
            {"base_id": "app123", "table_id": "tbl123", "records": records}
        )

        assert result.success is False
        assert "BATCH_LIMIT_EXCEEDED" in result.error_code

    @pytest.mark.asyncio
    async def test_batch_update_too_many_records(self, integration):
        """Test batch_update with more than 10 records."""
        records = [{"id": f"rec{i}", "fields": {"Name": f"Record {i}"}} for i in range(11)]

        result = await integration.execute_action(
            "batch_update",
            {"base_id": "app123", "table_id": "tbl123", "records": records}
        )

        assert result.success is False
        assert "BATCH_LIMIT_EXCEEDED" in result.error_code

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_create_record_success(self, mock_session_class, integration):
        """Test successful record creation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "rec123",
            "fields": {"Name": "Test Record"},
            "createdTime": "2025-01-01T00:00:00.000Z",
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
            "create_record",
            {
                "base_id": "app123",
                "table_id": "tbl123",
                "fields": {"Name": "Test Record"},
            }
        )

        assert result.success is True
        assert result.data["record_id"] == "rec123"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_test_connection_success(self, mock_session_class, integration):
        """Test successful connection test."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "usr123",
            "email": "test@example.com",
            "scopes": ["data.records:read", "data.records:write"],
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
        assert result.data["user_id"] == "usr123"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_list_bases_success(self, mock_session_class, integration):
        """Test successful base listing."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "bases": [
                {"id": "app1", "name": "Base 1", "permissionLevel": "create"},
                {"id": "app2", "name": "Base 2", "permissionLevel": "edit"},
            ],
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
            "list_bases",
            {}
        )

        assert result.success is True
        assert len(result.data["bases"]) == 2


# ============================================================================
# Base Integration Tests
# ============================================================================

class TestBaseIntegrationPattern:
    """Tests to verify integrations follow the base pattern."""

    def test_notion_is_base_integration(self):
        """Verify Notion inherits from BaseIntegration."""
        assert issubclass(NotionIntegration, BaseIntegration)

    def test_airtable_is_base_integration(self):
        """Verify Airtable inherits from BaseIntegration."""
        assert issubclass(AirtableIntegration, BaseIntegration)

    def test_notion_auth_type(self):
        """Verify Notion uses API_KEY."""
        integration = NotionIntegration(auth_credentials={"integration_token": "token"})
        assert integration.auth_type == AuthType.API_KEY

    def test_airtable_auth_type(self):
        """Verify Airtable uses API_KEY."""
        integration = AirtableIntegration(auth_credentials={"api_key": "token"})
        assert integration.auth_type == AuthType.API_KEY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
