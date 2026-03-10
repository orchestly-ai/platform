"""
BigQuery Integration - FULLY IMPLEMENTED

Real Google BigQuery API integration for data warehouse operations.

Supported Actions:
- run_query: Execute SQL query and return results
- run_query_async: Execute query asynchronously, return job ID
- get_job_status: Check status of async job
- get_job_results: Get results of completed job
- list_datasets: List datasets in a project
- list_tables: List tables in a dataset
- get_table: Get table metadata
- create_dataset: Create a new dataset

Authentication: Service Account JSON (OAuth 2.0)
API Docs: https://cloud.google.com/bigquery/docs/reference/rest
"""

import aiohttp
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

# Optional imports for service account auth
try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    HAS_GOOGLE_AUTH = True
except ImportError:
    HAS_GOOGLE_AUTH = False


class BigQueryIntegration(BaseIntegration):
    """BigQuery integration with REST API."""

    API_BASE_URL = "https://bigquery.googleapis.com/bigquery/v2"
    SCOPES = ["https://www.googleapis.com/auth/bigquery"]

    def __init__(self, auth_credentials: Dict[str, Any]):
        """Initialize BigQuery integration."""
        super().__init__(auth_credentials)
        self._credentials = None
        self._token = None
        self._token_expiry = None

    @property
    def name(self) -> str:
        return "bigquery"

    @property
    def display_name(self) -> str:
        return "Google BigQuery"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.OAUTH2

    @property
    def supported_actions(self) -> List[str]:
        return [
            "run_query",
            "run_query_async",
            "get_job_status",
            "get_job_results",
            "list_datasets",
            "list_tables",
            "get_table",
            "create_dataset",
        ]

    def _validate_credentials(self) -> None:
        """Validate BigQuery credentials."""
        super()._validate_credentials()

        if "service_account_json" not in self.auth_credentials and "project_id" not in self.auth_credentials:
            raise IntegrationError(
                "BigQuery requires 'service_account_json' or 'project_id' with default credentials",
                code="MISSING_CREDENTIALS",
            )

    def _get_project_id(self) -> str:
        """Get project ID from credentials."""
        if "project_id" in self.auth_credentials:
            return self.auth_credentials["project_id"]

        if "service_account_json" in self.auth_credentials:
            sa_info = self.auth_credentials["service_account_json"]
            if isinstance(sa_info, str):
                sa_info = json.loads(sa_info)
            return sa_info.get("project_id", "")

        raise IntegrationError("Cannot determine project_id", code="MISSING_CREDENTIALS")

    def _get_access_token(self) -> str:
        """Get OAuth access token from service account."""
        # Check if we have a valid cached token
        if self._token and self._token_expiry and datetime.utcnow().timestamp() < self._token_expiry:
            return self._token

        # Use access_token if provided directly (for testing or pre-authenticated)
        if "access_token" in self.auth_credentials:
            return self.auth_credentials["access_token"]

        if "service_account_json" in self.auth_credentials:
            if not HAS_GOOGLE_AUTH:
                raise IntegrationError(
                    "Service account auth requires google-auth package",
                    code="MISSING_DEPENDENCY",
                )

            sa_info = self.auth_credentials["service_account_json"]
            if isinstance(sa_info, str):
                sa_info = json.loads(sa_info)

            credentials = service_account.Credentials.from_service_account_info(
                sa_info,
                scopes=self.SCOPES,
            )
            credentials.refresh(Request())

            self._token = credentials.token
            self._token_expiry = credentials.expiry.timestamp() if credentials.expiry else None
            return self._token

        raise IntegrationError("No valid credentials for authentication", code="AUTH_ERROR")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to BigQuery API.

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
        url = f"{self.API_BASE_URL}{endpoint}"

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
                        error = response_data.get("error", {})
                        error_msg = error.get("message", "Unknown error")
                        error_code = error.get("code", "BIGQUERY_ERROR")
                        raise IntegrationError(
                            f"BigQuery API error: {error_msg}",
                            code=str(error_code),
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
        """Execute BigQuery action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "run_query":
                result = await self._run_query(params)
            elif action == "run_query_async":
                result = await self._run_query_async(params)
            elif action == "get_job_status":
                result = await self._get_job_status(params)
            elif action == "get_job_results":
                result = await self._get_job_results(params)
            elif action == "list_datasets":
                result = await self._list_datasets(params)
            elif action == "list_tables":
                result = await self._list_tables(params)
            elif action == "get_table":
                result = await self._get_table(params)
            elif action == "create_dataset":
                result = await self._create_dataset(params)
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
        """Test BigQuery connection by listing datasets."""
        try:
            result = await self._list_datasets({})
            if result.success:
                return IntegrationResult(
                    success=True,
                    data={
                        "project_id": self._get_project_id(),
                        "connected": True,
                        "dataset_count": len(result.data.get("datasets", [])),
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
        Execute SQL query and return results (synchronous).

        Required params:
            sql: SQL query string

        Optional params:
            project_id: Project to run query in
            use_legacy_sql: Use legacy SQL syntax (default: False)
            max_results: Maximum rows to return
            timeout_ms: Query timeout in milliseconds
        """
        sql = params.get("sql")
        if not sql:
            raise IntegrationError("Missing required parameter: 'sql'", code="MISSING_PARAMS")

        project_id = params.get("project_id", self._get_project_id())

        payload = {
            "kind": "bigquery#queryRequest",
            "query": sql,
            "useLegacySql": params.get("use_legacy_sql", False),
            "maxResults": params.get("max_results", 1000),
        }

        if "timeout_ms" in params:
            payload["timeoutMs"] = params["timeout_ms"]

        response = await self._make_request(
            "POST",
            f"/projects/{project_id}/queries",
            payload,
        )

        # Parse schema and rows
        schema = response.get("schema", {}).get("fields", [])
        columns = [field["name"] for field in schema]

        rows = []
        for row in response.get("rows", []):
            row_values = [cell.get("v") for cell in row.get("f", [])]
            rows.append(row_values)

        return IntegrationResult(
            success=True,
            data={
                "job_id": response.get("jobReference", {}).get("jobId"),
                "columns": columns,
                "rows": rows,
                "total_rows": int(response.get("totalRows", 0)),
                "job_complete": response.get("jobComplete", False),
            },
        )

    async def _run_query_async(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Execute query asynchronously.

        Required params:
            sql: SQL query string

        Optional params:
            project_id: Project to run query in
            destination_table: Destination table for results
            write_disposition: WRITE_TRUNCATE, WRITE_APPEND, WRITE_EMPTY
        """
        sql = params.get("sql")
        if not sql:
            raise IntegrationError("Missing required parameter: 'sql'", code="MISSING_PARAMS")

        project_id = params.get("project_id", self._get_project_id())

        job_config = {
            "query": {
                "query": sql,
                "useLegacySql": params.get("use_legacy_sql", False),
            }
        }

        if "destination_table" in params:
            dest = params["destination_table"]
            job_config["query"]["destinationTable"] = {
                "projectId": dest.get("project_id", project_id),
                "datasetId": dest["dataset_id"],
                "tableId": dest["table_id"],
            }

        if "write_disposition" in params:
            job_config["query"]["writeDisposition"] = params["write_disposition"]

        payload = {
            "kind": "bigquery#job",
            "configuration": job_config,
        }

        response = await self._make_request(
            "POST",
            f"/projects/{project_id}/jobs",
            payload,
        )

        job_ref = response.get("jobReference", {})

        return IntegrationResult(
            success=True,
            data={
                "job_id": job_ref.get("jobId"),
                "project_id": job_ref.get("projectId"),
                "location": job_ref.get("location"),
                "status": response.get("status", {}).get("state"),
            },
        )

    async def _get_job_status(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get status of async job.

        Required params:
            job_id: Job ID

        Optional params:
            project_id: Project ID
            location: Job location
        """
        job_id = params.get("job_id")
        if not job_id:
            raise IntegrationError("Missing required parameter: 'job_id'", code="MISSING_PARAMS")

        project_id = params.get("project_id", self._get_project_id())
        location = params.get("location")

        endpoint = f"/projects/{project_id}/jobs/{job_id}"
        query_params = {}
        if location:
            query_params["location"] = location

        response = await self._make_request(
            "GET",
            endpoint,
            params=query_params if query_params else None,
        )

        status = response.get("status", {})

        return IntegrationResult(
            success=True,
            data={
                "job_id": job_id,
                "state": status.get("state"),
                "error_result": status.get("errorResult"),
                "creation_time": response.get("statistics", {}).get("creationTime"),
                "start_time": response.get("statistics", {}).get("startTime"),
                "end_time": response.get("statistics", {}).get("endTime"),
            },
        )

    async def _get_job_results(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get results of completed job.

        Required params:
            job_id: Job ID

        Optional params:
            project_id: Project ID
            max_results: Maximum rows to return
            page_token: Pagination token
            start_index: Start row index
        """
        job_id = params.get("job_id")
        if not job_id:
            raise IntegrationError("Missing required parameter: 'job_id'", code="MISSING_PARAMS")

        project_id = params.get("project_id", self._get_project_id())

        query_params = {}
        if "max_results" in params:
            query_params["maxResults"] = params["max_results"]
        if "page_token" in params:
            query_params["pageToken"] = params["page_token"]
        if "start_index" in params:
            query_params["startIndex"] = params["start_index"]

        response = await self._make_request(
            "GET",
            f"/projects/{project_id}/queries/{job_id}",
            params=query_params if query_params else None,
        )

        schema = response.get("schema", {}).get("fields", [])
        columns = [field["name"] for field in schema]

        rows = []
        for row in response.get("rows", []):
            row_values = [cell.get("v") for cell in row.get("f", [])]
            rows.append(row_values)

        return IntegrationResult(
            success=True,
            data={
                "columns": columns,
                "rows": rows,
                "total_rows": int(response.get("totalRows", 0)),
                "page_token": response.get("pageToken"),
                "job_complete": response.get("jobComplete", False),
            },
        )

    async def _list_datasets(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List datasets in a project.

        Optional params:
            project_id: Project ID
            max_results: Maximum results
            page_token: Pagination token
        """
        project_id = params.get("project_id", self._get_project_id())

        query_params = {}
        if "max_results" in params:
            query_params["maxResults"] = params["max_results"]
        if "page_token" in params:
            query_params["pageToken"] = params["page_token"]

        response = await self._make_request(
            "GET",
            f"/projects/{project_id}/datasets",
            params=query_params if query_params else None,
        )

        datasets = [
            {
                "dataset_id": ds.get("datasetReference", {}).get("datasetId"),
                "project_id": ds.get("datasetReference", {}).get("projectId"),
                "location": ds.get("location"),
                "friendly_name": ds.get("friendlyName"),
            }
            for ds in response.get("datasets", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "datasets": datasets,
                "next_page_token": response.get("nextPageToken"),
            },
        )

    async def _list_tables(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List tables in a dataset.

        Required params:
            dataset_id: Dataset ID

        Optional params:
            project_id: Project ID
            max_results: Maximum results
            page_token: Pagination token
        """
        dataset_id = params.get("dataset_id")
        if not dataset_id:
            raise IntegrationError("Missing required parameter: 'dataset_id'", code="MISSING_PARAMS")

        project_id = params.get("project_id", self._get_project_id())

        query_params = {}
        if "max_results" in params:
            query_params["maxResults"] = params["max_results"]
        if "page_token" in params:
            query_params["pageToken"] = params["page_token"]

        response = await self._make_request(
            "GET",
            f"/projects/{project_id}/datasets/{dataset_id}/tables",
            params=query_params if query_params else None,
        )

        tables = [
            {
                "table_id": tbl.get("tableReference", {}).get("tableId"),
                "dataset_id": tbl.get("tableReference", {}).get("datasetId"),
                "type": tbl.get("type"),
                "creation_time": tbl.get("creationTime"),
            }
            for tbl in response.get("tables", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "tables": tables,
                "next_page_token": response.get("nextPageToken"),
            },
        )

    async def _get_table(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get table metadata.

        Required params:
            dataset_id: Dataset ID
            table_id: Table ID

        Optional params:
            project_id: Project ID
        """
        dataset_id = params.get("dataset_id")
        table_id = params.get("table_id")

        if not dataset_id or not table_id:
            raise IntegrationError(
                "Missing required parameters: 'dataset_id' and 'table_id'",
                code="MISSING_PARAMS",
            )

        project_id = params.get("project_id", self._get_project_id())

        response = await self._make_request(
            "GET",
            f"/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}",
        )

        schema = response.get("schema", {}).get("fields", [])
        columns = [
            {
                "name": field["name"],
                "type": field["type"],
                "mode": field.get("mode", "NULLABLE"),
                "description": field.get("description"),
            }
            for field in schema
        ]

        return IntegrationResult(
            success=True,
            data={
                "table_id": table_id,
                "dataset_id": dataset_id,
                "type": response.get("type"),
                "creation_time": response.get("creationTime"),
                "last_modified_time": response.get("lastModifiedTime"),
                "num_rows": response.get("numRows"),
                "num_bytes": response.get("numBytes"),
                "columns": columns,
            },
        )

    async def _create_dataset(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a new dataset.

        Required params:
            dataset_id: Dataset ID to create

        Optional params:
            project_id: Project ID
            location: Dataset location (e.g., 'US', 'EU')
            description: Dataset description
            default_table_expiration_ms: Default table expiration
        """
        dataset_id = params.get("dataset_id")
        if not dataset_id:
            raise IntegrationError("Missing required parameter: 'dataset_id'", code="MISSING_PARAMS")

        project_id = params.get("project_id", self._get_project_id())

        payload = {
            "kind": "bigquery#dataset",
            "datasetReference": {
                "projectId": project_id,
                "datasetId": dataset_id,
            },
        }

        if "location" in params:
            payload["location"] = params["location"]
        if "description" in params:
            payload["description"] = params["description"]
        if "default_table_expiration_ms" in params:
            payload["defaultTableExpirationMs"] = params["default_table_expiration_ms"]

        response = await self._make_request(
            "POST",
            f"/projects/{project_id}/datasets",
            payload,
        )

        return IntegrationResult(
            success=True,
            data={
                "dataset_id": response.get("datasetReference", {}).get("datasetId"),
                "project_id": response.get("datasetReference", {}).get("projectId"),
                "location": response.get("location"),
                "creation_time": response.get("creationTime"),
            },
        )
