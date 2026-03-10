"""
Tests for Session 3.6 Integrations: MongoDB and PostgreSQL

Run with: pytest test_integrations_session3_6.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from .mongodb import MongoDBIntegration
from .postgresql import PostgreSQLIntegration, HAS_ASYNCPG
from .base import IntegrationError, IntegrationResult


# =============================================================================
# MongoDB Integration Tests
# =============================================================================


class TestMongoDBIntegration:
    """Tests for MongoDB integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid MongoDB Data API credentials."""
        return {
            "api_key": "test-api-key-12345",
            "app_id": "myapp-abcde",
            "data_source": "MyCluster",
        }

    @pytest.fixture
    def valid_credentials_with_endpoint(self):
        """Valid credentials with custom endpoint."""
        return {
            "api_key": "test-api-key-12345",
            "endpoint": "https://custom.mongodb-api.com/data/v1",
            "data_source": "MyCluster",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create MongoDB integration instance."""
        return MongoDBIntegration(valid_credentials)

    def test_init(self, integration):
        """Test MongoDB integration initialization."""
        assert integration.name == "mongodb"
        assert integration.display_name == "MongoDB"
        assert len(integration.supported_actions) == 10

    def test_init_with_endpoint(self, valid_credentials_with_endpoint):
        """Test initialization with custom endpoint."""
        integration = MongoDBIntegration(valid_credentials_with_endpoint)
        assert integration._get_endpoint_url() == "https://custom.mongodb-api.com/data/v1"

    def test_missing_api_key(self):
        """Test missing API key raises error."""
        with pytest.raises(IntegrationError) as exc:
            MongoDBIntegration({"data_source": "cluster", "app_id": "app123"})
        assert "api_key" in str(exc.value)

    def test_missing_data_source(self):
        """Test missing data source raises error."""
        with pytest.raises(IntegrationError) as exc:
            MongoDBIntegration({"api_key": "key", "app_id": "app123"})
        assert "data_source" in str(exc.value)

    def test_missing_endpoint(self):
        """Test missing endpoint/app_id raises error."""
        with pytest.raises(IntegrationError) as exc:
            MongoDBIntegration({"api_key": "key", "data_source": "cluster"})
        assert "app_id" in str(exc.value) or "endpoint" in str(exc.value)

    def test_endpoint_url_generation(self, valid_credentials):
        """Test endpoint URL generation."""
        integration = MongoDBIntegration(valid_credentials)
        url = integration._get_endpoint_url()
        assert "myapp-abcde" in url
        assert "data.mongodb-api.com" in url

    def test_headers(self, integration):
        """Test request headers."""
        headers = integration._get_headers()
        assert headers["api-key"] == "test-api-key-12345"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_find_one(self, integration):
        """Test find_one action."""
        mock_response = {"document": {"_id": "123", "name": "Test"}}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "find_one",
                {"database": "testdb", "collection": "users", "filter": {"name": "Test"}},
            )

        assert result.success
        assert result.data["document"]["_id"] == "123"

    @pytest.mark.asyncio
    async def test_find(self, integration):
        """Test find action."""
        mock_response = {
            "documents": [
                {"_id": "1", "name": "User1"},
                {"_id": "2", "name": "User2"},
            ]
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "find",
                {"database": "testdb", "collection": "users", "filter": {}, "limit": 10},
            )

        assert result.success
        assert result.data["count"] == 2
        assert len(result.data["documents"]) == 2

    @pytest.mark.asyncio
    async def test_insert_one(self, integration):
        """Test insert_one action."""
        mock_response = {"insertedId": "new-id-123"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "insert_one",
                {
                    "database": "testdb",
                    "collection": "users",
                    "document": {"name": "New User", "email": "new@test.com"},
                },
            )

        assert result.success
        assert result.data["inserted_id"] == "new-id-123"

    @pytest.mark.asyncio
    async def test_insert_many(self, integration):
        """Test insert_many action."""
        mock_response = {"insertedIds": ["id1", "id2", "id3"]}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "insert_many",
                {
                    "database": "testdb",
                    "collection": "users",
                    "documents": [{"name": "User1"}, {"name": "User2"}, {"name": "User3"}],
                },
            )

        assert result.success
        assert result.data["count"] == 3

    @pytest.mark.asyncio
    async def test_update_one(self, integration):
        """Test update_one action."""
        mock_response = {"matchedCount": 1, "modifiedCount": 1}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "update_one",
                {
                    "database": "testdb",
                    "collection": "users",
                    "filter": {"_id": "123"},
                    "update": {"$set": {"name": "Updated"}},
                },
            )

        assert result.success
        assert result.data["modified_count"] == 1

    @pytest.mark.asyncio
    async def test_update_many(self, integration):
        """Test update_many action."""
        mock_response = {"matchedCount": 5, "modifiedCount": 5}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "update_many",
                {
                    "database": "testdb",
                    "collection": "users",
                    "filter": {"active": False},
                    "update": {"$set": {"archived": True}},
                },
            )

        assert result.success
        assert result.data["matched_count"] == 5

    @pytest.mark.asyncio
    async def test_delete_one(self, integration):
        """Test delete_one action."""
        mock_response = {"deletedCount": 1}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "delete_one",
                {
                    "database": "testdb",
                    "collection": "users",
                    "filter": {"_id": "123"},
                },
            )

        assert result.success
        assert result.data["deleted_count"] == 1

    @pytest.mark.asyncio
    async def test_delete_many(self, integration):
        """Test delete_many action."""
        mock_response = {"deletedCount": 10}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "delete_many",
                {
                    "database": "testdb",
                    "collection": "users",
                    "filter": {"archived": True},
                },
            )

        assert result.success
        assert result.data["deleted_count"] == 10

    @pytest.mark.asyncio
    async def test_aggregate(self, integration):
        """Test aggregate action."""
        mock_response = {
            "documents": [
                {"_id": "category1", "total": 100},
                {"_id": "category2", "total": 200},
            ]
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "aggregate",
                {
                    "database": "testdb",
                    "collection": "orders",
                    "pipeline": [
                        {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
                    ],
                },
            )

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_count(self, integration):
        """Test count action."""
        mock_response = {"documents": [{"count": 42}]}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "count",
                {"database": "testdb", "collection": "users", "filter": {"active": True}},
            )

        assert result.success
        assert result.data["count"] == 42

    @pytest.mark.asyncio
    async def test_missing_database(self, integration):
        """Test missing database parameter."""
        result = await integration.execute_action(
            "find_one",
            {"collection": "users"},
        )
        assert not result.success
        assert "database" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_collection(self, integration):
        """Test missing collection parameter."""
        result = await integration.execute_action(
            "find_one",
            {"database": "testdb"},
        )
        assert not result.success
        assert "collection" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_document(self, integration):
        """Test missing document for insert_one."""
        result = await integration.execute_action(
            "insert_one",
            {"database": "testdb", "collection": "users"},
        )
        assert not result.success
        assert "document" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_test_connection(self, integration):
        """Test connection testing."""
        with patch.object(integration, "_find_one", new_callable=AsyncMock) as mock:
            mock.return_value = IntegrationResult(success=True, data={"document": None})
            result = await integration.test_connection()

        assert result.success
        assert result.data["connected"]


# =============================================================================
# PostgreSQL Integration Tests
# =============================================================================


class TestPostgreSQLIntegration:
    """Tests for PostgreSQL integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid PostgreSQL credentials."""
        return {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
        }

    @pytest.fixture
    def valid_credentials_connection_string(self):
        """Valid credentials with connection string."""
        return {
            "connection_string": "postgresql://user:pass@localhost:5432/testdb"
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create PostgreSQL integration instance."""
        return PostgreSQLIntegration(valid_credentials)

    def test_init(self, integration):
        """Test PostgreSQL integration initialization."""
        assert integration.name == "postgresql"
        assert integration.display_name == "PostgreSQL"
        assert len(integration.supported_actions) == 8

    def test_init_with_connection_string(self, valid_credentials_connection_string):
        """Test initialization with connection string."""
        integration = PostgreSQLIntegration(valid_credentials_connection_string)
        params = integration._get_connection_params()
        assert "dsn" in params

    def test_missing_host(self):
        """Test missing host raises error."""
        with pytest.raises(IntegrationError) as exc:
            PostgreSQLIntegration({"database": "testdb"})
        assert "host" in str(exc.value).lower()

    def test_missing_database(self):
        """Test missing database raises error."""
        with pytest.raises(IntegrationError) as exc:
            PostgreSQLIntegration({"host": "localhost"})
        assert "database" in str(exc.value).lower()

    def test_connection_params(self, integration):
        """Test connection parameters extraction."""
        params = integration._get_connection_params()
        assert params["host"] == "localhost"
        assert params["database"] == "testdb"
        assert params["user"] == "testuser"

    @pytest.mark.asyncio
    async def test_run_query(self, integration):
        """Test run_query action."""
        mock_conn = AsyncMock()
        mock_rows = [
            {"id": 1, "name": "User1"},
            {"id": 2, "name": "User2"},
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action(
                "run_query",
                {"sql": "SELECT * FROM users"},
            )

        assert result.success
        assert result.data["row_count"] == 2

    @pytest.mark.asyncio
    async def test_run_query_one(self, integration):
        """Test run_query_one action."""
        mock_conn = AsyncMock()
        mock_row = {"id": 1, "name": "User1", "email": "user1@test.com"}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action(
                "run_query_one",
                {"sql": "SELECT * FROM users WHERE id = $1", "args": [1]},
            )

        assert result.success
        assert result.data["row"]["id"] == 1

    @pytest.mark.asyncio
    async def test_execute(self, integration):
        """Test execute action."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action(
                "execute",
                {"sql": "INSERT INTO users (name) VALUES ($1)", "args": ["TestUser"]},
            )

        assert result.success
        assert result.data["rows_affected"] == 1
        assert result.data["command"] == "INSERT"

    @pytest.mark.asyncio
    async def test_execute_many(self, integration):
        """Test execute_many action."""
        mock_conn = AsyncMock()
        mock_conn.executemany = AsyncMock()
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action(
                "execute_many",
                {
                    "sql": "INSERT INTO users (name) VALUES ($1)",
                    "args_list": [["User1"], ["User2"], ["User3"]],
                },
            )

        assert result.success
        assert result.data["rows_processed"] == 3

    @pytest.mark.asyncio
    async def test_list_tables(self, integration):
        """Test list_tables action."""
        mock_conn = AsyncMock()
        mock_rows = [
            {"table_name": "users", "table_type": "BASE TABLE"},
            {"table_name": "orders", "table_type": "BASE TABLE"},
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action(
                "list_tables",
                {"schema": "public"},
            )

        assert result.success
        assert result.data["count"] == 2
        assert result.data["tables"][0]["name"] == "users"

    @pytest.mark.asyncio
    async def test_describe_table(self, integration):
        """Test describe_table action."""
        mock_conn = AsyncMock()
        mock_rows = [
            {
                "column_name": "id",
                "data_type": "integer",
                "is_nullable": "NO",
                "column_default": "nextval('users_id_seq')",
                "character_maximum_length": None,
            },
            {
                "column_name": "name",
                "data_type": "varchar",
                "is_nullable": "YES",
                "column_default": None,
                "character_maximum_length": 255,
            },
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action(
                "describe_table",
                {"table": "users"},
            )

        assert result.success
        assert result.data["count"] == 2
        assert result.data["columns"][0]["name"] == "id"
        assert result.data["columns"][1]["nullable"] is True

    @pytest.mark.asyncio
    async def test_list_schemas(self, integration):
        """Test list_schemas action."""
        mock_conn = AsyncMock()
        mock_rows = [
            {"schema_name": "public"},
            {"schema_name": "audit"},
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action(
                "list_schemas",
                {},
            )

        assert result.success
        assert "public" in result.data["schemas"]

    @pytest.mark.asyncio
    async def test_create_table(self, integration):
        """Test create_table action."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action(
                "create_table",
                {
                    "table": "new_table",
                    "columns": [
                        {"name": "id", "type": "SERIAL", "primary_key": True},
                        {"name": "name", "type": "VARCHAR(255)", "nullable": False},
                        {"name": "created_at", "type": "TIMESTAMP", "default": "NOW()"},
                    ],
                },
            )

        assert result.success
        assert result.data["created"]
        assert result.data["table"] == "new_table"

    @pytest.mark.asyncio
    async def test_missing_sql(self, integration):
        """Test missing SQL parameter."""
        result = await integration.execute_action("run_query", {})
        assert not result.success
        assert "sql" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_table_for_describe(self, integration):
        """Test missing table parameter for describe_table."""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.execute_action("describe_table", {})

        assert not result.success
        assert "table" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_columns_for_create_table(self, integration):
        """Test missing columns parameter for create_table."""
        result = await integration.execute_action(
            "create_table",
            {"table": "test_table"},
        )
        assert not result.success
        assert "columns" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_test_connection(self, integration):
        """Test connection testing."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value="PostgreSQL 15.0")
        mock_conn.close = AsyncMock()

        with patch.object(integration, "_get_connection", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conn
            result = await integration.test_connection()

        assert result.success
        assert result.data["connected"]
        assert "PostgreSQL" in result.data["version"]

    @pytest.mark.asyncio
    async def test_connection_error(self, integration):
        """Test connection error handling."""
        with patch.object(
            integration, "_get_connection", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            result = await integration.test_connection()

        assert not result.success
        assert "refused" in result.error_message.lower()


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
