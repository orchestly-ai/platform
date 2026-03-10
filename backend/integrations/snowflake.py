"""
Snowflake Integration - FULLY IMPLEMENTED

Real Snowflake API integration for data warehouse operations.

Supported Actions:
- run_query: Execute SQL query and return results
- run_query_async: Execute query asynchronously, return query ID
- get_query_status: Check status of async query
- get_query_results: Get results of completed async query
- list_databases: List accessible databases
- list_schemas: List schemas in a database
- list_tables: List tables in a schema
- describe_table: Get table schema/columns

Authentication: Key Pair (JWT) or Username/Password
API Docs: https://docs.snowflake.com/en/developer-guide/sql-api/
"""

import aiohttp
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

# Optional imports for key pair auth
try:
    import jwt
    import hashlib
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class SnowflakeIntegration(BaseIntegration):
    """Snowflake integration with SQL API."""

    @property
    def name(self) -> str:
        return "snowflake"

    @property
    def display_name(self) -> str:
        return "Snowflake"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY  # Key pair auth

    @property
    def supported_actions(self) -> List[str]:
        return [
            "run_query",
            "run_query_async",
            "get_query_status",
            "get_query_results",
            "list_databases",
            "list_schemas",
            "list_tables",
            "describe_table",
        ]

    def _validate_credentials(self) -> None:
        """Validate Snowflake credentials."""
        super()._validate_credentials()

        required = ["account", "user"]
        missing = [f for f in required if f not in self.auth_credentials]

        if missing:
            raise IntegrationError(
                f"Snowflake requires: {', '.join(missing)}",
                code="MISSING_CREDENTIALS",
            )

        # Must have either private_key or password
        if "private_key" not in self.auth_credentials and "password" not in self.auth_credentials:
            raise IntegrationError(
                "Snowflake requires 'private_key' or 'password'",
                code="MISSING_CREDENTIALS",
            )

    def _get_api_url(self) -> str:
        """Get Snowflake SQL API URL."""
        account = self.auth_credentials["account"]
        # Handle account identifier format
        if ".snowflakecomputing.com" in account:
            return f"https://{account}/api/v2"
        return f"https://{account}.snowflakecomputing.com/api/v2"

    def _generate_jwt_token(self) -> str:
        """Generate JWT token for key pair authentication."""
        if not HAS_CRYPTO:
            raise IntegrationError(
                "Key pair auth requires cryptography and PyJWT packages",
                code="MISSING_DEPENDENCY",
            )

        account = self.auth_credentials["account"].upper()
        user = self.auth_credentials["user"].upper()
        private_key_pem = self.auth_credentials["private_key"]

        # Parse private key
        if isinstance(private_key_pem, str):
            private_key_pem = private_key_pem.encode()

        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=self.auth_credentials.get("private_key_passphrase", "").encode() or None,
            backend=default_backend(),
        )

        # Get public key fingerprint
        public_key = private_key.public_key()
        public_key_bytes = public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        sha256hash = hashlib.sha256(public_key_bytes).digest()
        public_key_fp = "SHA256:" + base64.b64encode(sha256hash).decode()

        # Build JWT
        now = datetime.utcnow()
        qualified_username = f"{account}.{user}"

        payload = {
            "iss": f"{qualified_username}.{public_key_fp}",
            "sub": qualified_username,
            "iat": now,
            "exp": now + timedelta(hours=1),
        }

        return jwt.encode(payload, private_key, algorithm="RS256")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
        }

        if "private_key" in self.auth_credentials:
            token = self._generate_jwt_token()
            headers["Authorization"] = f"Bearer {token}"
        else:
            # Basic auth with username/password
            import base64
            user = self.auth_credentials["user"]
            password = self.auth_credentials["password"]
            auth_string = base64.b64encode(f"{user}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {auth_string}"
            headers["X-Snowflake-Authorization-Token-Type"] = "BASIC"

        return headers

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Snowflake SQL API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request payload
            params: Query parameters

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
        url = f"{self._get_api_url()}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {
                    "method": method,
                    "url": url,
                    "headers": self._get_headers(),
                }
                if data:
                    kwargs["json"] = data
                if params:
                    kwargs["params"] = params

                async with session.request(**kwargs) as response:
                    response_data = await response.json()

                    if response.status >= 400:
                        error_msg = response_data.get("message", "Unknown error")
                        error_code = response_data.get("code", "SNOWFLAKE_ERROR")
                        raise IntegrationError(
                            f"Snowflake API error: {error_msg}",
                            code=error_code,
                            status_code=response.status,
                            details=response_data,
                        )

                    return response_data

        except aiohttp.ClientError as e:
            raise IntegrationError(
                f"HTTP request failed: {str(e)}",
                code="HTTP_ERROR",
            )
        except Exception as e:
            if isinstance(e, IntegrationError):
                raise
            raise IntegrationError(
                f"Unexpected error: {str(e)}",
                code="UNKNOWN_ERROR",
            )

    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
    ) -> IntegrationResult:
        """Execute Snowflake action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "run_query":
                result = await self._run_query(params)
            elif action == "run_query_async":
                result = await self._run_query_async(params)
            elif action == "get_query_status":
                result = await self._get_query_status(params)
            elif action == "get_query_results":
                result = await self._get_query_results(params)
            elif action == "list_databases":
                result = await self._list_databases(params)
            elif action == "list_schemas":
                result = await self._list_schemas(params)
            elif action == "list_tables":
                result = await self._list_tables(params)
            elif action == "describe_table":
                result = await self._describe_table(params)
            else:
                raise IntegrationError(f"Action {action} not implemented", code="NOT_IMPLEMENTED")

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.duration_ms = duration_ms

            self._log_execution(action, params, result)
            return result

        except IntegrationError as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
                duration_ms=duration_ms,
            )
            self._log_execution(action, params, result)
            return result

    async def test_connection(self) -> IntegrationResult:
        """Test Snowflake connection with a simple query."""
        try:
            result = await self._run_query({"sql": "SELECT CURRENT_USER(), CURRENT_ROLE()"})
            if result.success and result.data.get("rows"):
                row = result.data["rows"][0]
                return IntegrationResult(
                    success=True,
                    data={
                        "current_user": row[0] if len(row) > 0 else None,
                        "current_role": row[1] if len(row) > 1 else None,
                        "connected": True,
                    },
                )
            return result
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )

    # ========================================================================
    # Action Implementations
    # ========================================================================

    async def _run_query(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Execute SQL query and return results.

        Required params:
            sql: SQL statement to execute

        Optional params:
            database: Database context
            schema: Schema context
            warehouse: Warehouse to use
            role: Role to use
            timeout: Query timeout in seconds
        """
        sql = params.get("sql")
        if not sql:
            raise IntegrationError("Missing required parameter: 'sql'", code="MISSING_PARAMS")

        payload = {
            "statement": sql,
            "timeout": params.get("timeout", 60),
        }

        if "database" in params:
            payload["database"] = params["database"]
        if "schema" in params:
            payload["schema"] = params["schema"]
        if "warehouse" in params:
            payload["warehouse"] = params["warehouse"]
        if "role" in params:
            payload["role"] = params["role"]

        response = await self._make_request("POST", "/statements", payload)

        # Parse results
        rows = []
        columns = []

        if "resultSetMetaData" in response:
            metadata = response["resultSetMetaData"]
            columns = [col["name"] for col in metadata.get("rowType", [])]

        if "data" in response:
            rows = response["data"]

        return IntegrationResult(
            success=True,
            data={
                "statement_handle": response.get("statementHandle"),
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            },
        )

    async def _run_query_async(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Execute query asynchronously.

        Required params:
            sql: SQL statement to execute

        Optional params:
            database, schema, warehouse, role: Context settings
        """
        sql = params.get("sql")
        if not sql:
            raise IntegrationError("Missing required parameter: 'sql'", code="MISSING_PARAMS")

        payload = {
            "statement": sql,
            "timeout": params.get("timeout", 0),  # 0 = async
        }

        if "database" in params:
            payload["database"] = params["database"]
        if "schema" in params:
            payload["schema"] = params["schema"]
        if "warehouse" in params:
            payload["warehouse"] = params["warehouse"]
        if "role" in params:
            payload["role"] = params["role"]

        response = await self._make_request(
            "POST",
            "/statements?async=true",
            payload,
        )

        return IntegrationResult(
            success=True,
            data={
                "statement_handle": response.get("statementHandle"),
                "status": response.get("statementStatus"),
            },
        )

    async def _get_query_status(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get status of async query.

        Required params:
            statement_handle: Statement handle from run_query_async
        """
        handle = params.get("statement_handle")
        if not handle:
            raise IntegrationError("Missing required parameter: 'statement_handle'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/statements/{handle}")

        return IntegrationResult(
            success=True,
            data={
                "statement_handle": handle,
                "status": response.get("statementStatus"),
                "message": response.get("message"),
            },
        )

    async def _get_query_results(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get results of completed async query.

        Required params:
            statement_handle: Statement handle

        Optional params:
            partition: Partition number for large results
        """
        handle = params.get("statement_handle")
        if not handle:
            raise IntegrationError("Missing required parameter: 'statement_handle'", code="MISSING_PARAMS")

        endpoint = f"/statements/{handle}"
        if "partition" in params:
            endpoint += f"?partition={params['partition']}"

        response = await self._make_request("GET", endpoint)

        columns = []
        if "resultSetMetaData" in response:
            columns = [col["name"] for col in response["resultSetMetaData"].get("rowType", [])]

        return IntegrationResult(
            success=True,
            data={
                "columns": columns,
                "rows": response.get("data", []),
                "row_count": len(response.get("data", [])),
            },
        )

    async def _list_databases(self, params: Dict[str, Any]) -> IntegrationResult:
        """List accessible databases."""
        result = await self._run_query({"sql": "SHOW DATABASES"})

        if result.success:
            databases = []
            for row in result.data.get("rows", []):
                # SHOW DATABASES returns: created_on, name, is_default, is_current, origin, owner, comment, options, retention_time
                if len(row) >= 2:
                    databases.append({
                        "name": row[1],
                        "created_on": row[0] if len(row) > 0 else None,
                        "owner": row[5] if len(row) > 5 else None,
                    })

            return IntegrationResult(
                success=True,
                data={"databases": databases, "count": len(databases)},
            )

        return result

    async def _list_schemas(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List schemas in a database.

        Required params:
            database: Database name
        """
        database = params.get("database")
        if not database:
            raise IntegrationError("Missing required parameter: 'database'", code="MISSING_PARAMS")

        result = await self._run_query({"sql": f"SHOW SCHEMAS IN DATABASE {database}"})

        if result.success:
            schemas = []
            for row in result.data.get("rows", []):
                if len(row) >= 2:
                    schemas.append({
                        "name": row[1],
                        "created_on": row[0] if len(row) > 0 else None,
                    })

            return IntegrationResult(
                success=True,
                data={"schemas": schemas, "count": len(schemas)},
            )

        return result

    async def _list_tables(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List tables in a schema.

        Required params:
            database: Database name
            schema: Schema name
        """
        database = params.get("database")
        schema = params.get("schema")

        if not database or not schema:
            raise IntegrationError(
                "Missing required parameters: 'database' and 'schema'",
                code="MISSING_PARAMS",
            )

        result = await self._run_query({
            "sql": f"SHOW TABLES IN {database}.{schema}"
        })

        if result.success:
            tables = []
            for row in result.data.get("rows", []):
                if len(row) >= 2:
                    tables.append({
                        "name": row[1],
                        "created_on": row[0] if len(row) > 0 else None,
                        "kind": row[3] if len(row) > 3 else None,
                        "rows": row[8] if len(row) > 8 else None,
                    })

            return IntegrationResult(
                success=True,
                data={"tables": tables, "count": len(tables)},
            )

        return result

    async def _describe_table(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get table schema/columns.

        Required params:
            table: Fully qualified table name (database.schema.table)
        """
        table = params.get("table")
        if not table:
            raise IntegrationError("Missing required parameter: 'table'", code="MISSING_PARAMS")

        result = await self._run_query({"sql": f"DESCRIBE TABLE {table}"})

        if result.success:
            columns = []
            for row in result.data.get("rows", []):
                if len(row) >= 2:
                    columns.append({
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[3] if len(row) > 3 else None,
                        "default": row[4] if len(row) > 4 else None,
                    })

            return IntegrationResult(
                success=True,
                data={"columns": columns, "count": len(columns)},
            )

        return result
