"""
New Relic Integration

Real New Relic integration using New Relic APIs.
Supports querying metrics, sending custom events, and managing alerts.

Supported Actions:
- query_nrql: Execute NRQL queries
- send_event: Send custom events
- list_alerts: List alert policies
- list_alert_conditions: List alert conditions
- create_alert_condition: Create NRQL alert condition
- list_applications: List APM applications
- get_application: Get application details

Authentication:
- api_key: New Relic User API key (or License key for events)
- account_id: New Relic Account ID

API Docs: https://docs.newrelic.com/docs/apis/rest-api-v2/
"""

import asyncio
import random
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional, ClassVar

from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

logger = logging.getLogger(__name__)


class NewRelicIntegration(BaseIntegration):
    """
    New Relic integration for observability and monitoring.

    Features resilient connection handling:
    - Connection pooling via shared httpx.AsyncClient
    - Automatic retries with exponential backoff
    - Rate limit handling
    - Multiple API endpoint support (REST, GraphQL, Events)
    """

    REST_API_URL = "https://api.newrelic.com/v2"
    GRAPHQL_API_URL = "https://api.newrelic.com/graphql"
    EVENTS_API_URL = "https://insights-collector.newrelic.com/v1/accounts"

    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 30.0
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "newrelic"

    @property
    def display_name(self) -> str:
        return "New Relic"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "query_nrql",
            "send_event",
            "list_alerts",
            "list_alert_conditions",
            "create_alert_condition",
            "list_applications",
            "get_application",
            "test_connection",
        ]

    def _validate_credentials(self) -> None:
        super()._validate_credentials()

        if not self.auth_credentials.get("api_key"):
            raise IntegrationError("New Relic requires 'api_key'", code="MISSING_CREDENTIALS")
        if not self.auth_credentials.get("account_id"):
            raise IntegrationError("New Relic requires 'account_id'", code="MISSING_CREDENTIALS")

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

    async def _make_rest_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        api_key = self.auth_credentials["api_key"]
        url = f"{self.REST_API_URL}{endpoint}"

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()

                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers={
                        "Api-Key": api_key,
                        "Content-Type": "application/json",
                    },
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

    async def _make_graphql_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> httpx.Response:
        api_key = self.auth_credentials["api_key"]

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()

                response = await client.post(
                    self.GRAPHQL_API_URL,
                    json={"query": query, "variables": variables or {}},
                    headers={
                        "Api-Key": api_key,
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 429 and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
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

    async def _make_events_request(self, events: List[Dict[str, Any]]) -> httpx.Response:
        api_key = self.auth_credentials.get("insert_key") or self.auth_credentials["api_key"]
        account_id = self.auth_credentials["account_id"]
        url = f"{self.EVENTS_API_URL}/{account_id}/events"

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()

                response = await client.post(
                    url,
                    json=events,
                    headers={
                        "Api-Key": api_key,
                        "Content-Type": "application/json",
                    },
                )

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
            if action == "query_nrql":
                result = await self._query_nrql(params)
            elif action == "send_event":
                result = await self._send_event(params)
            elif action == "list_alerts":
                result = await self._list_alerts(params)
            elif action == "list_alert_conditions":
                result = await self._list_alert_conditions(params)
            elif action == "create_alert_condition":
                result = await self._create_alert_condition(params)
            elif action == "list_applications":
                result = await self._list_applications(params)
            elif action == "get_application":
                result = await self._get_application(params)
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
            account_id = self.auth_credentials["account_id"]
            query = f"""
            {{
                actor {{
                    account(id: {account_id}) {{
                        id
                        name
                    }}
                }}
            }}
            """

            response = await self._make_graphql_request(query)

            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("actor", {}).get("account"):
                    account = data["data"]["actor"]["account"]
                    return IntegrationResult(
                        success=True,
                        data={"account_id": account.get("id"), "account_name": account.get("name")},
                    )

            return IntegrationResult(success=False, error_message="Connection test failed", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="CONNECTION_ERROR")

    async def _query_nrql(self, params: Dict[str, Any]) -> IntegrationResult:
        nrql = params.get("nrql")
        if not nrql:
            return IntegrationResult(success=False, error_message="Missing: nrql", error_code="MISSING_PARAMS")

        try:
            account_id = self.auth_credentials["account_id"]
            escaped_nrql = nrql.replace('"', '\\"')
            query = f"""
            {{
                actor {{
                    account(id: {account_id}) {{
                        nrql(query: "{escaped_nrql}") {{
                            results
                        }}
                    }}
                }}
            }}
            """

            response = await self._make_graphql_request(query)

            if response.status_code == 200:
                data = response.json()
                results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
                return IntegrationResult(success=True, data={"results": results, "count": len(results)})
            else:
                return IntegrationResult(success=False, error_message="NRQL query failed", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _send_event(self, params: Dict[str, Any]) -> IntegrationResult:
        event_type = params.get("event_type")
        if not event_type:
            return IntegrationResult(success=False, error_message="Missing: event_type", error_code="MISSING_PARAMS")

        try:
            event = {
                "eventType": event_type,
                "timestamp": int(datetime.utcnow().timestamp()),
                **params.get("attributes", {}),
            }

            response = await self._make_events_request([event])

            if response.status_code in [200, 202]:
                return IntegrationResult(success=True, data={"event_type": event_type, "sent": True})
            else:
                return IntegrationResult(success=False, error_message="Failed to send event", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_alerts(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_rest_request("GET", "/alerts_policies.json")

            if response.status_code == 200:
                policies = [
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "incident_preference": p.get("incident_preference"),
                    }
                    for p in response.json().get("policies", [])
                ]
                return IntegrationResult(success=True, data={"policies": policies, "count": len(policies)})
            else:
                return IntegrationResult(success=False, error_message="Failed to list alerts", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_alert_conditions(self, params: Dict[str, Any]) -> IntegrationResult:
        policy_id = params.get("policy_id")
        if not policy_id:
            return IntegrationResult(success=False, error_message="Missing: policy_id", error_code="MISSING_PARAMS")

        try:
            response = await self._make_rest_request(
                "GET",
                "/alerts_nrql_conditions.json",
                params={"policy_id": str(policy_id)},
            )

            if response.status_code == 200:
                conditions = [
                    {
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "enabled": c.get("enabled"),
                        "type": c.get("type"),
                    }
                    for c in response.json().get("nrql_conditions", [])
                ]
                return IntegrationResult(success=True, data={"conditions": conditions, "count": len(conditions)})
            else:
                return IntegrationResult(success=False, error_message="Failed to list conditions", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _create_alert_condition(self, params: Dict[str, Any]) -> IntegrationResult:
        policy_id = params.get("policy_id")
        name = params.get("name")
        nrql = params.get("nrql")

        if not all([policy_id, name, nrql]):
            return IntegrationResult(success=False, error_message="Missing: policy_id, name, nrql", error_code="MISSING_PARAMS")

        try:
            condition_data = {
                "nrql_condition": {
                    "name": name,
                    "enabled": params.get("enabled", True),
                    "terms": [
                        {
                            "duration": str(params.get("duration", 5)),
                            "operator": params.get("operator", "above"),
                            "threshold": str(params.get("threshold", 0)),
                            "time_function": params.get("time_function", "all"),
                            "priority": params.get("priority", "critical"),
                        }
                    ],
                    "nrql": {"query": nrql},
                    "type": "static",
                    "value_function": params.get("value_function", "single_value"),
                }
            }

            response = await self._make_rest_request(
                "POST",
                f"/alerts_nrql_conditions/policies/{policy_id}.json",
                json=condition_data,
            )

            if response.status_code in [200, 201]:
                data = response.json().get("nrql_condition", {})
                return IntegrationResult(
                    success=True,
                    data={"id": data.get("id"), "name": data.get("name"), "enabled": data.get("enabled")},
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to create condition", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_applications(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_rest_request("GET", "/applications.json")

            if response.status_code == 200:
                apps = [
                    {
                        "id": a.get("id"),
                        "name": a.get("name"),
                        "language": a.get("language"),
                        "health_status": a.get("health_status"),
                        "reporting": a.get("reporting"),
                    }
                    for a in response.json().get("applications", [])
                ]
                return IntegrationResult(success=True, data={"applications": apps, "count": len(apps)})
            else:
                return IntegrationResult(success=False, error_message="Failed to list applications", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_application(self, params: Dict[str, Any]) -> IntegrationResult:
        app_id = params.get("application_id")
        if not app_id:
            return IntegrationResult(success=False, error_message="Missing: application_id", error_code="MISSING_PARAMS")

        try:
            response = await self._make_rest_request("GET", f"/applications/{app_id}.json")

            if response.status_code == 200:
                app = response.json().get("application", {})
                return IntegrationResult(
                    success=True,
                    data={
                        "id": app.get("id"),
                        "name": app.get("name"),
                        "language": app.get("language"),
                        "health_status": app.get("health_status"),
                        "reporting": app.get("reporting"),
                        "last_reported_at": app.get("last_reported_at"),
                        "application_summary": app.get("application_summary"),
                    },
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to get application", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
