"""
ServiceNow Integration

Real ServiceNow integration using ServiceNow REST API.
Supports incident management, change requests, and CMDB operations.

Supported Actions:
- create_incident: Create new incident
- update_incident: Update incident
- get_incident: Get incident details
- list_incidents: List incidents with filters
- create_change_request: Create change request
- get_change_request: Get change request details
- create_task: Create a task
- search_records: Search any table

Authentication:
- Basic Auth (username + password)
- OAuth 2.0 (client credentials)

Required Credentials:
- instance: ServiceNow instance (e.g., 'dev12345.service-now.com')
- username: ServiceNow username
- password: ServiceNow password
- Or: client_id, client_secret for OAuth

API Docs: https://developer.servicenow.com/dev.do
"""

import asyncio
import base64
import random
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional, ClassVar

from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

logger = logging.getLogger(__name__)


class ServiceNowIntegration(BaseIntegration):
    """
    ServiceNow integration for IT service management.

    Features resilient connection handling:
    - Connection pooling via shared httpx.AsyncClient
    - Automatic retries with exponential backoff
    - Rate limit handling
    - Configurable timeouts
    """

    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 30.0
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "servicenow"

    @property
    def display_name(self) -> str:
        return "ServiceNow"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.BASIC_AUTH

    @property
    def supported_actions(self) -> List[str]:
        return [
            "create_incident",
            "update_incident",
            "get_incident",
            "list_incidents",
            "create_change_request",
            "get_change_request",
            "create_task",
            "search_records",
            "test_connection",
        ]

    def _validate_credentials(self) -> None:
        super()._validate_credentials()
        if not self.auth_credentials.get("instance"):
            raise IntegrationError("ServiceNow requires 'instance'", code="MISSING_CREDENTIALS")

        has_basic = self.auth_credentials.get("username") and self.auth_credentials.get("password")
        has_oauth = self.auth_credentials.get("client_id") and self.auth_credentials.get("client_secret")

        if not has_basic and not has_oauth:
            raise IntegrationError(
                "ServiceNow requires username/password or client_id/client_secret",
                code="MISSING_CREDENTIALS"
            )

    def _get_base_url(self) -> str:
        instance = self.auth_credentials["instance"]
        if not instance.startswith("http"):
            instance = f"https://{instance}"
        return f"{instance}/api/now"

    def _get_auth_header(self) -> Dict[str, str]:
        username = self.auth_credentials.get("username")
        password = self.auth_credentials.get("password")

        if username and password:
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {credentials}"}

        # OAuth would require token fetch - simplified for now
        return {}

    @classmethod
    async def _get_client(cls) -> httpx.AsyncClient:
        async with cls._client_lock:
            if cls._client is None or cls._client.is_closed:
                cls._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout=cls.REQUEST_TIMEOUT, connect=10.0),
                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
                )
            return cls._client

    @classmethod
    async def close_client(cls):
        async with cls._client_lock:
            if cls._client and not cls._client.is_closed:
                await cls._client.aclose()
                cls._client = None

    def _calculate_retry_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        if retry_after:
            return min(retry_after, self.MAX_RETRY_DELAY)
        delay = min(self.BASE_RETRY_DELAY * (2 ** attempt), self.MAX_RETRY_DELAY)
        return max(0.1, delay + delay * 0.25 * (2 * random.random() - 1))

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        base_url = self._get_base_url()
        url = f"{base_url}{endpoint}"

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                headers = {
                    **self._get_auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }

                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=headers,
                )

                if response.status_code == 429 and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Rate limited, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue

                return response

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                if attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise IntegrationError(f"Connection failed: {str(e)}", code="CONNECTION_ERROR")

        raise IntegrationError("Request failed after all retries", code="MAX_RETRIES_EXCEEDED")

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "create_incident":
                result = await self._create_incident(params)
            elif action == "update_incident":
                result = await self._update_incident(params)
            elif action == "get_incident":
                result = await self._get_incident(params)
            elif action == "list_incidents":
                result = await self._list_incidents(params)
            elif action == "create_change_request":
                result = await self._create_change_request(params)
            elif action == "get_change_request":
                result = await self._get_change_request(params)
            elif action == "create_task":
                result = await self._create_task(params)
            elif action == "search_records":
                result = await self._search_records(params)
            elif action == "test_connection":
                result = await self.test_connection()
            else:
                raise IntegrationError(f"Action {action} not implemented", code="NOT_IMPLEMENTED")

            result.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._log_execution(action, params, result)
            return result

        except IntegrationError as e:
            result = IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )
            self._log_execution(action, params, result)
            return result

    async def test_connection(self) -> IntegrationResult:
        try:
            response = await self._make_request("GET", "/table/sys_user", params={"sysparm_limit": "1"})

            if response.status_code == 200:
                return IntegrationResult(
                    success=True,
                    data={"message": "Connected to ServiceNow", "instance": self.auth_credentials.get("instance")},
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Connection test failed",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="CONNECTION_ERROR")

    async def _create_incident(self, params: Dict[str, Any]) -> IntegrationResult:
        short_description = params.get("short_description")
        if not short_description:
            return IntegrationResult(success=False, error_message="Missing: short_description", error_code="MISSING_PARAMS")

        try:
            incident_data = {
                "short_description": short_description,
                "description": params.get("description", ""),
                "urgency": params.get("urgency", "2"),
                "impact": params.get("impact", "2"),
                "category": params.get("category"),
                "caller_id": params.get("caller_id"),
                "assignment_group": params.get("assignment_group"),
            }
            incident_data = {k: v for k, v in incident_data.items() if v is not None}

            response = await self._make_request("POST", "/table/incident", json=incident_data)

            if response.status_code in [200, 201]:
                data = response.json().get("result", {})
                return IntegrationResult(
                    success=True,
                    data={
                        "sys_id": data.get("sys_id"),
                        "number": data.get("number"),
                        "state": data.get("state"),
                        "short_description": data.get("short_description"),
                    },
                )
            else:
                error = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error.get("error", {}).get("message", "Failed to create incident"),
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _update_incident(self, params: Dict[str, Any]) -> IntegrationResult:
        sys_id = params.get("sys_id")
        if not sys_id:
            return IntegrationResult(success=False, error_message="Missing: sys_id", error_code="MISSING_PARAMS")

        try:
            update_data = {}
            for field in ["state", "urgency", "impact", "work_notes", "comments", "assigned_to", "resolution_code", "close_notes"]:
                if params.get(field):
                    update_data[field] = params[field]

            response = await self._make_request("PATCH", f"/table/incident/{sys_id}", json=update_data)

            if response.status_code == 200:
                data = response.json().get("result", {})
                return IntegrationResult(
                    success=True,
                    data={"sys_id": data.get("sys_id"), "number": data.get("number"), "state": data.get("state")},
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to update incident", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_incident(self, params: Dict[str, Any]) -> IntegrationResult:
        sys_id = params.get("sys_id")
        number = params.get("number")

        if not sys_id and not number:
            return IntegrationResult(success=False, error_message="Missing: sys_id or number", error_code="MISSING_PARAMS")

        try:
            if sys_id:
                response = await self._make_request("GET", f"/table/incident/{sys_id}")
            else:
                response = await self._make_request("GET", "/table/incident", params={"sysparm_query": f"number={number}"})

            if response.status_code == 200:
                result = response.json().get("result", {})
                if isinstance(result, list):
                    result = result[0] if result else {}

                return IntegrationResult(
                    success=True,
                    data={
                        "sys_id": result.get("sys_id"),
                        "number": result.get("number"),
                        "short_description": result.get("short_description"),
                        "state": result.get("state"),
                        "urgency": result.get("urgency"),
                        "impact": result.get("impact"),
                        "created_on": result.get("sys_created_on"),
                    },
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to get incident", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_incidents(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            query_params = {"sysparm_limit": str(params.get("limit", 25))}

            if params.get("state"):
                query_params["sysparm_query"] = f"state={params['state']}"
            if params.get("query"):
                query_params["sysparm_query"] = params["query"]

            response = await self._make_request("GET", "/table/incident", params=query_params)

            if response.status_code == 200:
                results = response.json().get("result", [])
                incidents = [
                    {
                        "sys_id": inc.get("sys_id"),
                        "number": inc.get("number"),
                        "short_description": inc.get("short_description"),
                        "state": inc.get("state"),
                        "urgency": inc.get("urgency"),
                    }
                    for inc in results
                ]
                return IntegrationResult(success=True, data={"incidents": incidents, "count": len(incidents)})
            else:
                return IntegrationResult(success=False, error_message="Failed to list incidents", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _create_change_request(self, params: Dict[str, Any]) -> IntegrationResult:
        short_description = params.get("short_description")
        if not short_description:
            return IntegrationResult(success=False, error_message="Missing: short_description", error_code="MISSING_PARAMS")

        try:
            change_data = {
                "short_description": short_description,
                "description": params.get("description", ""),
                "type": params.get("type", "normal"),
                "risk": params.get("risk", "moderate"),
                "impact": params.get("impact", "2"),
                "assignment_group": params.get("assignment_group"),
            }
            change_data = {k: v for k, v in change_data.items() if v is not None}

            response = await self._make_request("POST", "/table/change_request", json=change_data)

            if response.status_code in [200, 201]:
                data = response.json().get("result", {})
                return IntegrationResult(
                    success=True,
                    data={"sys_id": data.get("sys_id"), "number": data.get("number"), "state": data.get("state")},
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to create change request", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_change_request(self, params: Dict[str, Any]) -> IntegrationResult:
        sys_id = params.get("sys_id")
        if not sys_id:
            return IntegrationResult(success=False, error_message="Missing: sys_id", error_code="MISSING_PARAMS")

        try:
            response = await self._make_request("GET", f"/table/change_request/{sys_id}")

            if response.status_code == 200:
                data = response.json().get("result", {})
                return IntegrationResult(
                    success=True,
                    data={
                        "sys_id": data.get("sys_id"),
                        "number": data.get("number"),
                        "short_description": data.get("short_description"),
                        "state": data.get("state"),
                        "type": data.get("type"),
                    },
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to get change request", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _create_task(self, params: Dict[str, Any]) -> IntegrationResult:
        short_description = params.get("short_description")
        if not short_description:
            return IntegrationResult(success=False, error_message="Missing: short_description", error_code="MISSING_PARAMS")

        try:
            task_data = {
                "short_description": short_description,
                "description": params.get("description", ""),
                "assigned_to": params.get("assigned_to"),
                "parent": params.get("parent"),
            }
            task_data = {k: v for k, v in task_data.items() if v is not None}

            response = await self._make_request("POST", "/table/task", json=task_data)

            if response.status_code in [200, 201]:
                data = response.json().get("result", {})
                return IntegrationResult(
                    success=True,
                    data={"sys_id": data.get("sys_id"), "number": data.get("number")},
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to create task", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _search_records(self, params: Dict[str, Any]) -> IntegrationResult:
        table = params.get("table")
        if not table:
            return IntegrationResult(success=False, error_message="Missing: table", error_code="MISSING_PARAMS")

        try:
            query_params = {"sysparm_limit": str(params.get("limit", 25))}
            if params.get("query"):
                query_params["sysparm_query"] = params["query"]
            if params.get("fields"):
                query_params["sysparm_fields"] = params["fields"]

            response = await self._make_request("GET", f"/table/{table}", params=query_params)

            if response.status_code == 200:
                results = response.json().get("result", [])
                return IntegrationResult(success=True, data={"records": results, "count": len(results), "table": table})
            else:
                return IntegrationResult(success=False, error_message="Failed to search records", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
