"""
PostgreSQL Integration - FULLY IMPLEMENTED

Real PostgreSQL database integration for SQL operations.

Supported Actions:
- run_query: Execute SQL query and return results
- run_query_one: Execute query and return single row
- execute: Execute SQL statement (INSERT/UPDATE/DELETE)
- execute_many: Execute statement with multiple parameter sets
- list_tables: List tables in schema
- describe_table: Get table schema/columns
- list_schemas: List database schemas
- create_table: Create a new table

Authentication: Connection String or individual parameters
Requires: asyncpg package (optional)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

# Optional imports for PostgreSQL
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


class PostgreSQLIntegration(BaseIntegration):
    """PostgreSQL integration with asyncpg."""

    def __init__(self, auth_credentials: Dict[str, Any]):
        """Initialize PostgreSQL integration."""
        super().__init__(auth_credentials)
        self._pool = None

    @property
    def name(self) -> str:
        return "postgresql"

    @property
    def display_name(self) -> str:
        return "PostgreSQL"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.BASIC_AUTH

    @property
    def supported_actions(self) -> List[str]:
        return [
            "run_query",
            "run_query_one",
            "execute",
            "execute_many",
            "list_tables",
            "describe_table",
            "list_schemas",
            "create_table",
        ]

    def _validate_credentials(self) -> None:
        """Validate PostgreSQL credentials."""
        super()._validate_credentials()

        # Either connection_string or individual params
        if "connection_string" in self.auth_credentials:
            return

        required = ["host", "database"]
        missing = [f for f in required if f not in self.auth_credentials]

        if missing:
            raise IntegrationError(
                f"PostgreSQL requires 'connection_string' or: {', '.join(missing)}",
                code="MISSING_CREDENTIALS",
            )

    def _get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters."""
        if "connection_string" in self.auth_credentials:
            return {"dsn": self.auth_credentials["connection_string"]}

        params = {
            "host": self.auth_credentials["host"],
            "database": self.auth_credentials["database"],
        }

        if "port" in self.auth_credentials:
            params["port"] = int(self.auth_credentials["port"])
        if "user" in self.auth_credentials:
            params["user"] = self.auth_credentials["user"]
        if "password" in self.auth_credentials:
            params["password"] = self.auth_credentials["password"]
        if "ssl" in self.auth_credentials:
            params["ssl"] = self.auth_credentials["ssl"]

        return params

    async def _get_connection(self):
        """Get a database connection."""
        if not HAS_ASYNCPG:
            raise IntegrationError(
                "PostgreSQL integration requires asyncpg package",
                code="MISSING_DEPENDENCY",
            )

        params = self._get_connection_params()

        if "dsn" in params:
            return await asyncpg.connect(params["dsn"])
        else:
            return await asyncpg.connect(**params)

    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
    ) -> IntegrationResult:
        """Execute PostgreSQL action with real database call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "run_query":
                result = await self._run_query(params)
            elif action == "run_query_one":
                result = await self._run_query_one(params)
            elif action == "execute":
                result = await self._execute(params)
            elif action == "execute_many":
                result = await self._execute_many(params)
            elif action == "list_tables":
                result = await self._list_tables(params)
            elif action == "describe_table":
                result = await self._describe_table(params)
            elif action == "list_schemas":
                result = await self._list_schemas(params)
            elif action == "create_table":
                result = await self._create_table(params)
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
        """Test PostgreSQL connection."""
        try:
            conn = await self._get_connection()
            try:
                result = await conn.fetchval("SELECT version()")
                return IntegrationResult(
                    success=True,
                    data={
                        "connected": True,
                        "version": result,
                    },
                )
            finally:
                await conn.close()
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )
        except Exception as e:
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    # ========================================================================
    # Action Implementations
    # ========================================================================

    async def _run_query(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Execute SQL query and return results.

        Required params:
            sql: SQL query string

        Optional params:
            args: Query parameters (list or dict)
            timeout: Query timeout in seconds
        """
        sql = params.get("sql")
        if not sql:
            raise IntegrationError("Missing required parameter: 'sql'", code="MISSING_PARAMS")

        args = params.get("args", [])
        timeout = params.get("timeout")

        conn = await self._get_connection()
        try:
            if timeout:
                rows = await conn.fetch(sql, *args, timeout=timeout)
            else:
                rows = await conn.fetch(sql, *args)

            # Convert records to dicts
            results = [dict(row) for row in rows]

            # Get column names from first row
            columns = list(results[0].keys()) if results else []

            return IntegrationResult(
                success=True,
                data={
                    "columns": columns,
                    "rows": results,
                    "row_count": len(results),
                },
            )
        except Exception as e:
            raise IntegrationError(f"Query failed: {str(e)}", code="QUERY_ERROR")
        finally:
            await conn.close()

    async def _run_query_one(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Execute query and return single row.

        Required params:
            sql: SQL query string

        Optional params:
            args: Query parameters
        """
        sql = params.get("sql")
        if not sql:
            raise IntegrationError("Missing required parameter: 'sql'", code="MISSING_PARAMS")

        args = params.get("args", [])

        conn = await self._get_connection()
        try:
            row = await conn.fetchrow(sql, *args)

            result = dict(row) if row else None

            return IntegrationResult(
                success=True,
                data={
                    "row": result,
                },
            )
        except Exception as e:
            raise IntegrationError(f"Query failed: {str(e)}", code="QUERY_ERROR")
        finally:
            await conn.close()

    async def _execute(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Execute SQL statement (INSERT/UPDATE/DELETE).

        Required params:
            sql: SQL statement

        Optional params:
            args: Statement parameters
        """
        sql = params.get("sql")
        if not sql:
            raise IntegrationError("Missing required parameter: 'sql'", code="MISSING_PARAMS")

        args = params.get("args", [])

        conn = await self._get_connection()
        try:
            result = await conn.execute(sql, *args)

            # Parse result like "INSERT 0 1" or "UPDATE 5"
            parts = result.split()
            affected = int(parts[-1]) if parts else 0

            return IntegrationResult(
                success=True,
                data={
                    "command": parts[0] if parts else None,
                    "rows_affected": affected,
                },
            )
        except Exception as e:
            raise IntegrationError(f"Execute failed: {str(e)}", code="EXECUTE_ERROR")
        finally:
            await conn.close()

    async def _execute_many(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Execute statement with multiple parameter sets.

        Required params:
            sql: SQL statement
            args_list: List of parameter tuples/lists
        """
        sql = params.get("sql")
        args_list = params.get("args_list")

        if not sql or not args_list:
            raise IntegrationError(
                "Missing required parameters: 'sql' and 'args_list'",
                code="MISSING_PARAMS",
            )

        conn = await self._get_connection()
        try:
            await conn.executemany(sql, args_list)

            return IntegrationResult(
                success=True,
                data={
                    "rows_processed": len(args_list),
                },
            )
        except Exception as e:
            raise IntegrationError(f"Execute failed: {str(e)}", code="EXECUTE_ERROR")
        finally:
            await conn.close()

    async def _list_tables(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List tables in schema.

        Optional params:
            schema: Schema name (default: 'public')
        """
        schema = params.get("schema", "public")

        sql = """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = $1
            ORDER BY table_name
        """

        conn = await self._get_connection()
        try:
            rows = await conn.fetch(sql, schema)

            tables = [
                {
                    "name": row["table_name"],
                    "type": row["table_type"],
                }
                for row in rows
            ]

            return IntegrationResult(
                success=True,
                data={
                    "tables": tables,
                    "schema": schema,
                    "count": len(tables),
                },
            )
        finally:
            await conn.close()

    async def _describe_table(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get table schema/columns.

        Required params:
            table: Table name

        Optional params:
            schema: Schema name (default: 'public')
        """
        table = params.get("table")
        if not table:
            raise IntegrationError("Missing required parameter: 'table'", code="MISSING_PARAMS")

        schema = params.get("schema", "public")

        sql = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
        """

        conn = await self._get_connection()
        try:
            rows = await conn.fetch(sql, schema, table)

            columns = [
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                    "default": row["column_default"],
                    "max_length": row["character_maximum_length"],
                }
                for row in rows
            ]

            return IntegrationResult(
                success=True,
                data={
                    "table": table,
                    "schema": schema,
                    "columns": columns,
                    "count": len(columns),
                },
            )
        finally:
            await conn.close()

    async def _list_schemas(self, params: Dict[str, Any]) -> IntegrationResult:
        """List database schemas."""
        sql = """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT LIKE 'pg_%'
            AND schema_name != 'information_schema'
            ORDER BY schema_name
        """

        conn = await self._get_connection()
        try:
            rows = await conn.fetch(sql)

            schemas = [row["schema_name"] for row in rows]

            return IntegrationResult(
                success=True,
                data={
                    "schemas": schemas,
                    "count": len(schemas),
                },
            )
        finally:
            await conn.close()

    async def _create_table(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a new table.

        Required params:
            table: Table name
            columns: List of column definitions, each with:
                - name: Column name
                - type: Data type
                - nullable: Allow nulls (default: True)
                - primary_key: Is primary key (default: False)
                - default: Default value

        Optional params:
            schema: Schema name (default: 'public')
            if_not_exists: Add IF NOT EXISTS (default: True)
        """
        table = params.get("table")
        columns = params.get("columns")

        if not table or not columns:
            raise IntegrationError(
                "Missing required parameters: 'table' and 'columns'",
                code="MISSING_PARAMS",
            )

        schema = params.get("schema", "public")
        if_not_exists = params.get("if_not_exists", True)

        # Build column definitions
        col_defs = []
        for col in columns:
            if "name" not in col or "type" not in col:
                raise IntegrationError(
                    "Each column requires 'name' and 'type'",
                    code="MISSING_PARAMS",
                )

            col_def = f'"{col["name"]}" {col["type"]}'

            if col.get("primary_key"):
                col_def += " PRIMARY KEY"
            elif not col.get("nullable", True):
                col_def += " NOT NULL"

            if "default" in col:
                col_def += f" DEFAULT {col['default']}"

            col_defs.append(col_def)

        exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        sql = f'CREATE TABLE {exists_clause}"{schema}"."{table}" ({", ".join(col_defs)})'

        conn = await self._get_connection()
        try:
            await conn.execute(sql)

            return IntegrationResult(
                success=True,
                data={
                    "table": table,
                    "schema": schema,
                    "created": True,
                },
            )
        except Exception as e:
            raise IntegrationError(f"Create table failed: {str(e)}", code="CREATE_ERROR")
        finally:
            await conn.close()
