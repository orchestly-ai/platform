"""
PagerDuty Integration

Real PagerDuty integration using PagerDuty Events API v2 and REST API.
Supports creating incidents, managing alerts, and on-call scheduling.

Authentication:
- api_token: PagerDuty REST API token
- routing_key: PagerDuty Events API routing key (for trigger_incident)

API Docs: https://developer.pagerduty.com/docs/
"""

import asyncio
import random
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional, ClassVar

from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

logger = logging.getLogger(__name__)


class PagerDutyIntegration(BaseIntegration):
    """PagerDuty integration for incident management."""

    REST_API_URL = "https://api.pagerduty.com"
    EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"

    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 30.0
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "pagerduty"

    @property
    def display_name(self) -> str:
        return "PagerDuty"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return ["trigger_incident", "resolve_incident", "acknowledge_incident", "list_incidents", "get_incident", "list_oncalls", "list_services", "test_connection"]

    def _validate_credentials(self) -> None:
        super()._validate_credentials()
        if not self.auth_credentials.get("api_token") and not self.auth_credentials.get("routing_key"):
            raise IntegrationError("PagerDuty requires 'api_token' or 'routing_key'", code="MISSING_CREDENTIALS")

    @classmethod
    async def _get_client(cls) -> httpx.AsyncClient:
        async with cls._client_lock:
            if cls._client is None or cls._client.is_closed:
                cls._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout=cls.REQUEST_TIMEOUT, connect=10.0), limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30.0))
            return cls._client

    @classmethod
    async def close_client(cls):
        """Close the shared client (call on application shutdown)."""
        async with cls._client_lock:
            if cls._client and not cls._client.is_closed:
                await cls._client.aclose()
                cls._client = None

    def _calculate_retry_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        if retry_after:
            return min(retry_after, self.MAX_RETRY_DELAY)
        delay = min(self.BASE_RETRY_DELAY * (2 ** attempt), self.MAX_RETRY_DELAY)
        return max(0.1, delay + delay * 0.25 * (2 * random.random() - 1))

    async def _make_rest_request(self, method: str, endpoint: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        api_token = self.auth_credentials.get("api_token")
        if not api_token:
            raise IntegrationError("REST API requires api_token", code="MISSING_CREDENTIALS")
        url = f"{self.REST_API_URL}{endpoint}"
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                response = await client.request(method=method, url=url, json=json, params=params, headers={"Authorization": f"Token token={api_token}", "Content-Type": "application/json", "Accept": "application/vnd.pagerduty+json;version=2"})
                if response.status_code == 429 and attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self._calculate_retry_delay(attempt, float(response.headers.get("Retry-After", 0)) or None))
                    continue
                if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self._calculate_retry_delay(attempt))
                    continue
                return response
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self._calculate_retry_delay(attempt))
                    continue
                raise IntegrationError(f"Connection failed: {str(e)}", code="CONNECTION_ERROR")
        raise IntegrationError("Request failed after all retries", code="MAX_RETRIES_EXCEEDED")

    async def _make_events_request(self, event_data: Dict[str, Any]) -> httpx.Response:
        routing_key = self.auth_credentials.get("routing_key")
        if not routing_key:
            raise IntegrationError("Events API requires routing_key", code="MISSING_CREDENTIALS")
        event_data["routing_key"] = routing_key
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                response = await client.post(self.EVENTS_API_URL, json=event_data, headers={"Content-Type": "application/json"})
                if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self._calculate_retry_delay(attempt))
                    continue
                return response
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self._calculate_retry_delay(attempt))
                    continue
                raise IntegrationError(f"Connection failed: {str(e)}", code="CONNECTION_ERROR")
        raise IntegrationError("Request failed after all retries", code="MAX_RETRIES_EXCEEDED")

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        self._validate_action(action)
        start_time = datetime.utcnow()
        try:
            result = await getattr(self, f"_{action}")(params) if action != "test_connection" else await self.test_connection()
            result.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return result
        except IntegrationError as e:
            return IntegrationResult(success=False, error_message=e.message, error_code=e.code, duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000)

    async def test_connection(self) -> IntegrationResult:
        try:
            if self.auth_credentials.get("api_token"):
                response = await self._make_rest_request("GET", "/users/me")
                if response.status_code == 200:
                    user = response.json().get("user", {})
                    return IntegrationResult(success=True, data={"user_id": user.get("id"), "name": user.get("name"), "email": user.get("email")})
                return IntegrationResult(success=False, error_message="Connection test failed", error_code=str(response.status_code))
            return IntegrationResult(success=True, data={"message": "Routing key configured"})
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="CONNECTION_ERROR")

    async def _trigger_incident(self, params: Dict[str, Any]) -> IntegrationResult:
        summary = params.get("summary")
        if not summary:
            return IntegrationResult(success=False, error_message="Missing: summary", error_code="MISSING_PARAMS")
        try:
            event_data = {"event_action": "trigger", "payload": {"summary": summary, "severity": params.get("severity", "warning"), "source": params.get("source", "agent-orchestration"), "custom_details": params.get("custom_details", {})}}
            if params.get("dedup_key"):
                event_data["dedup_key"] = params["dedup_key"]
            response = await self._make_events_request(event_data)
            if response.status_code in [200, 202]:
                data = response.json()
                return IntegrationResult(success=True, data={"status": data.get("status"), "dedup_key": data.get("dedup_key")})
            return IntegrationResult(success=False, error_message="Failed to trigger incident", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _resolve_incident(self, params: Dict[str, Any]) -> IntegrationResult:
        dedup_key = params.get("dedup_key")
        if not dedup_key:
            return IntegrationResult(success=False, error_message="Missing: dedup_key", error_code="MISSING_PARAMS")
        try:
            response = await self._make_events_request({"event_action": "resolve", "dedup_key": dedup_key})
            if response.status_code in [200, 202]:
                return IntegrationResult(success=True, data={"dedup_key": dedup_key, "resolved": True})
            return IntegrationResult(success=False, error_message="Failed to resolve incident", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _acknowledge_incident(self, params: Dict[str, Any]) -> IntegrationResult:
        dedup_key = params.get("dedup_key")
        if not dedup_key:
            return IntegrationResult(success=False, error_message="Missing: dedup_key", error_code="MISSING_PARAMS")
        try:
            response = await self._make_events_request({"event_action": "acknowledge", "dedup_key": dedup_key})
            if response.status_code in [200, 202]:
                return IntegrationResult(success=True, data={"dedup_key": dedup_key, "acknowledged": True})
            return IntegrationResult(success=False, error_message="Failed to acknowledge incident", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_incidents(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_rest_request("GET", "/incidents", params={"limit": params.get("limit", 25)})
            if response.status_code == 200:
                incidents = [{"id": i.get("id"), "incident_number": i.get("incident_number"), "title": i.get("title"), "status": i.get("status"), "urgency": i.get("urgency")} for i in response.json().get("incidents", [])]
                return IntegrationResult(success=True, data={"incidents": incidents, "count": len(incidents)})
            return IntegrationResult(success=False, error_message="Failed to list incidents", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_incident(self, params: Dict[str, Any]) -> IntegrationResult:
        incident_id = params.get("incident_id")
        if not incident_id:
            return IntegrationResult(success=False, error_message="Missing: incident_id", error_code="MISSING_PARAMS")
        try:
            response = await self._make_rest_request("GET", f"/incidents/{incident_id}")
            if response.status_code == 200:
                inc = response.json().get("incident", {})
                return IntegrationResult(success=True, data={"id": inc.get("id"), "title": inc.get("title"), "status": inc.get("status"), "urgency": inc.get("urgency"), "created_at": inc.get("created_at")})
            return IntegrationResult(success=False, error_message="Failed to get incident", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_oncalls(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_rest_request("GET", "/oncalls")
            if response.status_code == 200:
                oncalls = [{"user": oc.get("user", {}).get("summary"), "schedule": oc.get("schedule", {}).get("summary") if oc.get("schedule") else None, "escalation_policy": oc.get("escalation_policy", {}).get("summary")} for oc in response.json().get("oncalls", [])]
                return IntegrationResult(success=True, data={"oncalls": oncalls, "count": len(oncalls)})
            return IntegrationResult(success=False, error_message="Failed to list on-calls", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_services(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_rest_request("GET", "/services", params={"limit": params.get("limit", 25)})
            if response.status_code == 200:
                services = [{"id": s.get("id"), "name": s.get("name"), "status": s.get("status")} for s in response.json().get("services", [])]
                return IntegrationResult(success=True, data={"services": services, "count": len(services)})
            return IntegrationResult(success=False, error_message="Failed to list services", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
