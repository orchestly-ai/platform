#!/usr/bin/env python3
"""
Tests for Session 3.4 Integrations: Snowflake and BigQuery

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
from backend.integrations.snowflake import SnowflakeIntegration
from backend.integrations.bigquery import BigQueryIntegration


# ============================================================================
# Snowflake Integration Tests
# ============================================================================

class TestSnowflakeIntegration:
    """Tests for Snowflake integration."""

    @pytest.fixture
    def valid_credentials_password(self):
        """Valid Snowflake credentials with password."""
        return {
            "account": "myaccount",
            "user": "myuser",
            "password": "mypassword",
        }

    @pytest.fixture
    def integration(self, valid_credentials_password):
        """Create Snowflake integration instance with password auth."""
        return SnowflakeIntegration(auth_credentials=valid_credentials_password)

    def test_init_with_password(self, integration):
        """Test initialization with password."""
        assert integration.name == "snowflake"
        assert integration.display_name == "Snowflake"
        assert integration.auth_type == AuthType.API_KEY

    def test_init_missing_account(self):
        """Test initialization without account."""
        with pytest.raises(IntegrationError) as exc:
            SnowflakeIntegration(auth_credentials={
                "user": "myuser",
                "password": "mypassword",
            })
        assert "account" in str(exc.value)

    def test_init_missing_user(self):
        """Test initialization without user."""
        with pytest.raises(IntegrationError) as exc:
            SnowflakeIntegration(auth_credentials={
                "account": "myaccount",
                "password": "mypassword",
            })
        assert "user" in str(exc.value)

    def test_init_missing_auth(self):
        """Test initialization without password or private_key."""
        with pytest.raises(IntegrationError) as exc:
            SnowflakeIntegration(auth_credentials={
                "account": "myaccount",
                "user": "myuser",
            })
        assert "private_key" in str(exc.value) or "password" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "run_query" in actions
        assert "run_query_async" in actions
        assert "get_query_status" in actions
        assert "get_query_results" in actions
        assert "list_databases" in actions
        assert "list_schemas" in actions
        assert "list_tables" in actions
        assert "describe_table" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("run_query")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")
        assert "not supported" in str(exc.value)

    def test_get_api_url(self, integration):
        """Test API URL construction."""
        url = integration._get_api_url()
        assert "myaccount.snowflakecomputing.com" in url

    def test_get_headers_password(self, integration):
        """Test headers include Basic auth for password auth."""
        headers = integration._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    async def test_run_query_missing_sql(self, integration):
        """Test run_query without sql."""
        result = await integration.execute_action(
            "run_query",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_run_query_async_missing_sql(self, integration):
        """Test run_query_async without sql."""
        result = await integration.execute_action(
            "run_query_async",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_query_status_missing_handle(self, integration):
        """Test get_query_status without statement_handle."""
        result = await integration.execute_action(
            "get_query_status",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_query_results_missing_handle(self, integration):
        """Test get_query_results without statement_handle."""
        result = await integration.execute_action(
            "get_query_results",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_list_schemas_missing_database(self, integration):
        """Test list_schemas without database."""
        result = await integration.execute_action(
            "list_schemas",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_list_tables_missing_params(self, integration):
        """Test list_tables without database and schema."""
        result = await integration.execute_action(
            "list_tables",
            {"database": "mydb"}  # Missing schema
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_describe_table_missing_table(self, integration):
        """Test describe_table without table."""
        result = await integration.execute_action(
            "describe_table",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_run_query_success(self, mock_session_class, integration):
        """Test successful query execution."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "statementHandle": "handle-123",
            "resultSetMetaData": {
                "rowType": [
                    {"name": "ID"},
                    {"name": "NAME"},
                ]
            },
            "data": [
                ["1", "Alice"],
                ["2", "Bob"],
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
            "run_query",
            {"sql": "SELECT * FROM users"}
        )

        assert result.success is True
        assert result.data["row_count"] == 2
        assert result.data["columns"] == ["ID", "NAME"]


# ============================================================================
# BigQuery Integration Tests
# ============================================================================

class TestBigQueryIntegration:
    """Tests for BigQuery integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid BigQuery credentials."""
        return {
            "project_id": "my-project",
            "access_token": "test-access-token",
        }

    @pytest.fixture
    def service_account_credentials(self):
        """Service account credentials."""
        return {
            "service_account_json": {
                "type": "service_account",
                "project_id": "my-project",
                "private_key_id": "key-id",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
                "client_email": "test@my-project.iam.gserviceaccount.com",
                "client_id": "123456789",
            }
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create BigQuery integration instance."""
        return BigQueryIntegration(auth_credentials=valid_credentials)

    def test_init_with_project_id(self, integration):
        """Test initialization with project_id."""
        assert integration.name == "bigquery"
        assert integration.display_name == "Google BigQuery"
        assert integration.auth_type == AuthType.OAUTH2

    def test_init_missing_credentials(self):
        """Test initialization without required credentials."""
        with pytest.raises(IntegrationError) as exc:
            BigQueryIntegration(auth_credentials={"other": "value"})
        assert "service_account_json" in str(exc.value) or "project_id" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "run_query" in actions
        assert "run_query_async" in actions
        assert "get_job_status" in actions
        assert "get_job_results" in actions
        assert "list_datasets" in actions
        assert "list_tables" in actions
        assert "get_table" in actions
        assert "create_dataset" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("run_query")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")
        assert "not supported" in str(exc.value)

    def test_get_project_id(self, integration):
        """Test project ID retrieval."""
        project_id = integration._get_project_id()
        assert project_id == "my-project"

    def test_get_headers(self, integration):
        """Test headers include Bearer token."""
        headers = integration._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    @pytest.mark.asyncio
    async def test_run_query_missing_sql(self, integration):
        """Test run_query without sql."""
        result = await integration.execute_action(
            "run_query",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_run_query_async_missing_sql(self, integration):
        """Test run_query_async without sql."""
        result = await integration.execute_action(
            "run_query_async",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_job_status_missing_job_id(self, integration):
        """Test get_job_status without job_id."""
        result = await integration.execute_action(
            "get_job_status",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_job_results_missing_job_id(self, integration):
        """Test get_job_results without job_id."""
        result = await integration.execute_action(
            "get_job_results",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_list_tables_missing_dataset(self, integration):
        """Test list_tables without dataset_id."""
        result = await integration.execute_action(
            "list_tables",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_get_table_missing_params(self, integration):
        """Test get_table without required params."""
        result = await integration.execute_action(
            "get_table",
            {"dataset_id": "my_dataset"}  # Missing table_id
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_create_dataset_missing_id(self, integration):
        """Test create_dataset without dataset_id."""
        result = await integration.execute_action(
            "create_dataset",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_run_query_success(self, mock_session_class, integration):
        """Test successful query execution."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "kind": "bigquery#queryResponse",
            "jobReference": {"jobId": "job-123"},
            "schema": {
                "fields": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "name", "type": "STRING"},
                ]
            },
            "rows": [
                {"f": [{"v": "1"}, {"v": "Alice"}]},
                {"f": [{"v": "2"}, {"v": "Bob"}]},
            ],
            "totalRows": "2",
            "jobComplete": True,
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
            "run_query",
            {"sql": "SELECT * FROM users"}
        )

        assert result.success is True
        assert result.data["total_rows"] == 2
        assert result.data["columns"] == ["id", "name"]

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_list_datasets_success(self, mock_session_class, integration):
        """Test successful dataset listing."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "kind": "bigquery#datasetList",
            "datasets": [
                {
                    "datasetReference": {"datasetId": "dataset1", "projectId": "my-project"},
                    "location": "US",
                },
                {
                    "datasetReference": {"datasetId": "dataset2", "projectId": "my-project"},
                    "location": "EU",
                },
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
            "list_datasets",
            {}
        )

        assert result.success is True
        assert len(result.data["datasets"]) == 2


# ============================================================================
# Base Integration Tests
# ============================================================================

class TestBaseIntegrationPattern:
    """Tests to verify integrations follow the base pattern."""

    def test_snowflake_is_base_integration(self):
        """Verify Snowflake inherits from BaseIntegration."""
        assert issubclass(SnowflakeIntegration, BaseIntegration)

    def test_bigquery_is_base_integration(self):
        """Verify BigQuery inherits from BaseIntegration."""
        assert issubclass(BigQueryIntegration, BaseIntegration)

    def test_snowflake_auth_type(self):
        """Verify Snowflake uses API_KEY."""
        integration = SnowflakeIntegration(auth_credentials={
            "account": "test",
            "user": "test",
            "password": "test",
        })
        assert integration.auth_type == AuthType.API_KEY

    def test_bigquery_auth_type(self):
        """Verify BigQuery uses OAUTH2."""
        integration = BigQueryIntegration(auth_credentials={"project_id": "test", "access_token": "token"})
        assert integration.auth_type == AuthType.OAUTH2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
