"""
Airtable Integration - FULLY IMPLEMENTED

Real Airtable API integration for database and record management.

Supported Actions:
- list_bases: List accessible bases
- list_tables: List tables in a base
- list_records: List records from a table
- get_record: Get a single record
- create_record: Create a new record
- update_record: Update an existing record
- delete_record: Delete a record
- batch_create: Create multiple records
- batch_update: Update multiple records

Authentication: API Key or Personal Access Token (Bearer)
API Docs: https://airtable.com/developers/web/api/introduction
"""

import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class AirtableIntegration(BaseIntegration):
    """Airtable integration with official API."""

    API_BASE_URL = "https://api.airtable.com/v0"
    META_API_URL = "https://api.airtable.com/v0/meta"

    @property
    def name(self) -> str:
        return "airtable"

    @property
    def display_name(self) -> str:
        return "Airtable"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "list_bases",
            "list_tables",
            "list_records",
            "get_record",
            "create_record",
            "update_record",
            "delete_record",
            "batch_create",
            "batch_update",
        ]

    def _validate_credentials(self) -> None:
        """Validate Airtable credentials."""
        super()._validate_credentials()

        if "api_key" not in self.auth_credentials and "access_token" not in self.auth_credentials:
            raise IntegrationError(
                "Airtable requires 'api_key' or 'access_token'",
                code="MISSING_CREDENTIALS",
            )

    def _get_token(self) -> str:
        """Get the API key or access token."""
        return self.auth_credentials.get("api_key") or self.auth_credentials.get("access_token")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Airtable API.

        Args:
            method: HTTP method
            url: Full API URL
            data: Request payload
            params: Query parameters

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
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
                    # Handle 204 No Content
                    if response.status == 204:
                        return {"deleted": True}

                    response_data = await response.json()

                    if response.status >= 400:
                        error = response_data.get("error", {})
                        error_msg = error.get("message", "Unknown error")
                        error_type = error.get("type", "AIRTABLE_ERROR")
                        raise IntegrationError(
                            f"Airtable API error: {error_msg}",
                            code=error_type,
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
        """Execute Airtable action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "list_bases":
                result = await self._list_bases(params)
            elif action == "list_tables":
                result = await self._list_tables(params)
            elif action == "list_records":
                result = await self._list_records(params)
            elif action == "get_record":
                result = await self._get_record(params)
            elif action == "create_record":
                result = await self._create_record(params)
            elif action == "update_record":
                result = await self._update_record(params)
            elif action == "delete_record":
                result = await self._delete_record(params)
            elif action == "batch_create":
                result = await self._batch_create(params)
            elif action == "batch_update":
                result = await self._batch_update(params)
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
        """Test Airtable connection using /meta/whoami endpoint."""
        try:
            response = await self._make_request("GET", f"{self.META_API_URL}/whoami")
            return IntegrationResult(
                success=True,
                data={
                    "user_id": response.get("id"),
                    "email": response.get("email"),
                    "scopes": response.get("scopes", []),
                },
            )
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )

    # ========================================================================
    # Action Implementations
    # ========================================================================

    async def _list_bases(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List accessible bases.

        Optional params:
            offset: Pagination offset
        """
        query_params = {}
        if "offset" in params:
            query_params["offset"] = params["offset"]

        response = await self._make_request(
            "GET",
            f"{self.META_API_URL}/bases",
            params=query_params if query_params else None,
        )

        bases = [
            {
                "base_id": base.get("id"),
                "name": base.get("name"),
                "permission_level": base.get("permissionLevel"),
            }
            for base in response.get("bases", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "bases": bases,
                "offset": response.get("offset"),
            },
        )

    async def _list_tables(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List tables in a base.

        Required params:
            base_id: Base ID
        """
        base_id = params.get("base_id")
        if not base_id:
            raise IntegrationError("Missing required parameter: 'base_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"{self.META_API_URL}/bases/{base_id}/tables")

        tables = [
            {
                "table_id": table.get("id"),
                "name": table.get("name"),
                "primary_field_id": table.get("primaryFieldId"),
                "fields": [
                    {"id": f.get("id"), "name": f.get("name"), "type": f.get("type")}
                    for f in table.get("fields", [])
                ],
            }
            for table in response.get("tables", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "tables": tables,
            },
        )

    async def _list_records(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List records from a table.

        Required params:
            base_id: Base ID
            table_id: Table ID or name

        Optional params:
            fields: List of field names to return
            filter_by_formula: Airtable formula filter
            max_records: Maximum records to return
            page_size: Records per page (max 100)
            sort: List of {field, direction} objects
            view: View ID or name
            offset: Pagination offset
        """
        base_id = params.get("base_id")
        table_id = params.get("table_id")

        if not base_id or not table_id:
            raise IntegrationError(
                "Missing required parameters: 'base_id' and 'table_id'",
                code="MISSING_PARAMS",
            )

        query_params = {}

        if "fields" in params:
            query_params["fields[]"] = params["fields"]
        if "filter_by_formula" in params:
            query_params["filterByFormula"] = params["filter_by_formula"]
        if "max_records" in params:
            query_params["maxRecords"] = params["max_records"]
        if "page_size" in params:
            query_params["pageSize"] = min(params["page_size"], 100)
        if "sort" in params:
            for i, sort in enumerate(params["sort"]):
                query_params[f"sort[{i}][field]"] = sort["field"]
                query_params[f"sort[{i}][direction]"] = sort.get("direction", "asc")
        if "view" in params:
            query_params["view"] = params["view"]
        if "offset" in params:
            query_params["offset"] = params["offset"]

        response = await self._make_request(
            "GET",
            f"{self.API_BASE_URL}/{base_id}/{table_id}",
            params=query_params if query_params else None,
        )

        records = [
            {
                "record_id": record.get("id"),
                "fields": record.get("fields", {}),
                "created_time": record.get("createdTime"),
            }
            for record in response.get("records", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "records": records,
                "offset": response.get("offset"),
            },
        )

    async def _get_record(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get a single record.

        Required params:
            base_id: Base ID
            table_id: Table ID or name
            record_id: Record ID
        """
        base_id = params.get("base_id")
        table_id = params.get("table_id")
        record_id = params.get("record_id")

        if not all([base_id, table_id, record_id]):
            raise IntegrationError(
                "Missing required parameters: 'base_id', 'table_id', 'record_id'",
                code="MISSING_PARAMS",
            )

        response = await self._make_request(
            "GET",
            f"{self.API_BASE_URL}/{base_id}/{table_id}/{record_id}",
        )

        return IntegrationResult(
            success=True,
            data={
                "record_id": response.get("id"),
                "fields": response.get("fields", {}),
                "created_time": response.get("createdTime"),
            },
        )

    async def _create_record(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a new record.

        Required params:
            base_id: Base ID
            table_id: Table ID or name
            fields: Dict of field values

        Optional params:
            typecast: Enable automatic type conversion (default: False)
        """
        base_id = params.get("base_id")
        table_id = params.get("table_id")
        fields = params.get("fields")

        if not all([base_id, table_id, fields]):
            raise IntegrationError(
                "Missing required parameters: 'base_id', 'table_id', 'fields'",
                code="MISSING_PARAMS",
            )

        payload = {"fields": fields}
        if params.get("typecast"):
            payload["typecast"] = True

        response = await self._make_request(
            "POST",
            f"{self.API_BASE_URL}/{base_id}/{table_id}",
            payload,
        )

        return IntegrationResult(
            success=True,
            data={
                "record_id": response.get("id"),
                "fields": response.get("fields", {}),
                "created_time": response.get("createdTime"),
            },
        )

    async def _update_record(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update an existing record.

        Required params:
            base_id: Base ID
            table_id: Table ID or name
            record_id: Record ID
            fields: Dict of field values to update

        Optional params:
            typecast: Enable automatic type conversion (default: False)
        """
        base_id = params.get("base_id")
        table_id = params.get("table_id")
        record_id = params.get("record_id")
        fields = params.get("fields")

        if not all([base_id, table_id, record_id, fields]):
            raise IntegrationError(
                "Missing required parameters: 'base_id', 'table_id', 'record_id', 'fields'",
                code="MISSING_PARAMS",
            )

        payload = {"fields": fields}
        if params.get("typecast"):
            payload["typecast"] = True

        response = await self._make_request(
            "PATCH",
            f"{self.API_BASE_URL}/{base_id}/{table_id}/{record_id}",
            payload,
        )

        return IntegrationResult(
            success=True,
            data={
                "record_id": response.get("id"),
                "fields": response.get("fields", {}),
                "updated": True,
            },
        )

    async def _delete_record(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Delete a record.

        Required params:
            base_id: Base ID
            table_id: Table ID or name
            record_id: Record ID
        """
        base_id = params.get("base_id")
        table_id = params.get("table_id")
        record_id = params.get("record_id")

        if not all([base_id, table_id, record_id]):
            raise IntegrationError(
                "Missing required parameters: 'base_id', 'table_id', 'record_id'",
                code="MISSING_PARAMS",
            )

        response = await self._make_request(
            "DELETE",
            f"{self.API_BASE_URL}/{base_id}/{table_id}/{record_id}",
        )

        return IntegrationResult(
            success=True,
            data={
                "record_id": record_id,
                "deleted": response.get("deleted", True),
            },
        )

    async def _batch_create(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create multiple records (up to 10).

        Required params:
            base_id: Base ID
            table_id: Table ID or name
            records: List of {fields: {...}} objects

        Optional params:
            typecast: Enable automatic type conversion
        """
        base_id = params.get("base_id")
        table_id = params.get("table_id")
        records = params.get("records")

        if not all([base_id, table_id, records]):
            raise IntegrationError(
                "Missing required parameters: 'base_id', 'table_id', 'records'",
                code="MISSING_PARAMS",
            )

        if len(records) > 10:
            raise IntegrationError(
                "Airtable batch operations support max 10 records",
                code="BATCH_LIMIT_EXCEEDED",
            )

        payload = {"records": records}
        if params.get("typecast"):
            payload["typecast"] = True

        response = await self._make_request(
            "POST",
            f"{self.API_BASE_URL}/{base_id}/{table_id}",
            payload,
        )

        created = [
            {
                "record_id": record.get("id"),
                "fields": record.get("fields", {}),
            }
            for record in response.get("records", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "records": created,
                "count": len(created),
            },
        )

    async def _batch_update(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update multiple records (up to 10).

        Required params:
            base_id: Base ID
            table_id: Table ID or name
            records: List of {id: "...", fields: {...}} objects

        Optional params:
            typecast: Enable automatic type conversion
        """
        base_id = params.get("base_id")
        table_id = params.get("table_id")
        records = params.get("records")

        if not all([base_id, table_id, records]):
            raise IntegrationError(
                "Missing required parameters: 'base_id', 'table_id', 'records'",
                code="MISSING_PARAMS",
            )

        if len(records) > 10:
            raise IntegrationError(
                "Airtable batch operations support max 10 records",
                code="BATCH_LIMIT_EXCEEDED",
            )

        payload = {"records": records}
        if params.get("typecast"):
            payload["typecast"] = True

        response = await self._make_request(
            "PATCH",
            f"{self.API_BASE_URL}/{base_id}/{table_id}",
            payload,
        )

        updated = [
            {
                "record_id": record.get("id"),
                "fields": record.get("fields", {}),
            }
            for record in response.get("records", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "records": updated,
                "count": len(updated),
            },
        )
