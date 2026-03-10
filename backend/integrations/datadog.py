"""
Datadog Integration

Real Datadog integration using Datadog API.
Supports sending metrics, events, logs, and querying monitors.

Authentication: API Key + Application Key

Required Credentials:
- api_key: Datadog API key
- app_key: Datadog Application key
- site: Datadog site (e.g., 'datadoghq.com', 'datadoghq.eu')

API Docs: https://docs.datadoghq.com/api/
"""

import asyncio
import random
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional, ClassVar

from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

logger = logging.getLogger(__name__)


class DatadogIntegration(BaseIntegration):
    """Datadog integration for monitoring and observability."""

    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 30.0
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "datadog"

    @property
    def display_name(self) -> str:
        return "Datadog"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return ["send_metric", "send_event", "send_log", "list_monitors", "get_monitor", "mute_monitor", "create_incident", "test_connection"]

    def _validate_credentials(self) -> None:
        super()._validate_credentials()
        required = ["api_key", "app_key"]
        missing = [k for k in required if not self.auth_credentials.get(k)]
        if missing:
            raise IntegrationError(f"Datadog requires: {', '.join(missing)}", code="MISSING_CREDENTIALS")

    def _get_base_url(self) -> str:
        site = self.auth_credentials.get("site", "datadoghq.com")
        return f"https://api.{site}"

    def _get_headers(self) -> Dict[str, str]:
        return {"DD-API-KEY": self.auth_credentials["api_key"], "DD-APPLICATION-KEY": self.auth_credentials["app_key"], "Content-Type": "application/json"}

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

    async def _make_request(self, method: str, endpoint: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None, api_version: str = "v1") -> httpx.Response:
        url = f"{self._get_base_url()}/api/{api_version}{endpoint}"
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                response = await client.request(method=method, url=url, json=json, params=params, headers=self._get_headers())
                if response.status_code == 429 and attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self._calculate_retry_delay(attempt, float(response.headers.get("X-RateLimit-Reset", 0)) or None))
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
            response = await self._make_request("GET", "/validate")
            if response.status_code == 200:
                return IntegrationResult(success=True, data={"valid": response.json().get("valid", True)})
            return IntegrationResult(success=False, error_message="API key validation failed", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="CONNECTION_ERROR")

    async def _send_metric(self, params: Dict[str, Any]) -> IntegrationResult:
        metric_name, points = params.get("metric"), params.get("points")
        if not metric_name or points is None:
            return IntegrationResult(success=False, error_message="Missing: metric, points", error_code="MISSING_PARAMS")
        try:
            if isinstance(points, (int, float)):
                points = [[int(datetime.utcnow().timestamp()), points]]
            response = await self._make_request("POST", "/series", json={"series": [{"metric": metric_name, "type": params.get("type", "gauge"), "points": points, "tags": params.get("tags", [])}]})
            if response.status_code in [200, 202]:
                return IntegrationResult(success=True, data={"metric": metric_name, "submitted": True})
            return IntegrationResult(success=False, error_message="Failed to submit metric", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _send_event(self, params: Dict[str, Any]) -> IntegrationResult:
        title = params.get("title")
        if not title:
            return IntegrationResult(success=False, error_message="Missing: title", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("POST", "/events", json={"title": title, "text": params.get("text", title), "alert_type": params.get("alert_type", "info"), "tags": params.get("tags", [])})
            if response.status_code in [200, 202]:
                return IntegrationResult(success=True, data={"event_id": response.json().get("event", {}).get("id"), "status": response.json().get("status")})
            return IntegrationResult(success=False, error_message="Failed to create event", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _send_log(self, params: Dict[str, Any]) -> IntegrationResult:
        message = params.get("message")
        if not message:
            return IntegrationResult(success=False, error_message="Missing: message", error_code="MISSING_PARAMS")
        try:
            site = self.auth_credentials.get("site", "datadoghq.com")
            client = await self._get_client()
            response = await client.post(f"https://http-intake.logs.{site}/api/v2/logs", json=[{"message": message, "ddsource": params.get("source", "api"), "service": params.get("service", "agent-orchestration"), "ddtags": ",".join(params.get("tags", []))}], headers=self._get_headers())
            if response.status_code in [200, 202]:
                return IntegrationResult(success=True, data={"submitted": True})
            return IntegrationResult(success=False, error_message="Failed to send log", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_monitors(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_request("GET", "/monitor", params={"name": params.get("name")} if params.get("name") else None)
            if response.status_code == 200:
                monitors = [{"id": m.get("id"), "name": m.get("name"), "type": m.get("type"), "status": m.get("overall_state")} for m in response.json()]
                return IntegrationResult(success=True, data={"monitors": monitors, "count": len(monitors)})
            return IntegrationResult(success=False, error_message="Failed to list monitors", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_monitor(self, params: Dict[str, Any]) -> IntegrationResult:
        monitor_id = params.get("monitor_id")
        if not monitor_id:
            return IntegrationResult(success=False, error_message="Missing: monitor_id", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("GET", f"/monitor/{monitor_id}")
            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(success=True, data={"id": data.get("id"), "name": data.get("name"), "type": data.get("type"), "status": data.get("overall_state"), "query": data.get("query")})
            return IntegrationResult(success=False, error_message="Failed to get monitor", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _mute_monitor(self, params: Dict[str, Any]) -> IntegrationResult:
        monitor_id = params.get("monitor_id")
        if not monitor_id:
            return IntegrationResult(success=False, error_message="Missing: monitor_id", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("POST", f"/monitor/{monitor_id}/mute", json={"end": params.get("end")} if params.get("end") else {})
            if response.status_code == 200:
                return IntegrationResult(success=True, data={"monitor_id": monitor_id, "muted": True})
            return IntegrationResult(success=False, error_message="Failed to mute monitor", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _create_incident(self, params: Dict[str, Any]) -> IntegrationResult:
        title = params.get("title")
        if not title:
            return IntegrationResult(success=False, error_message="Missing: title", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("POST", "/incidents", json={"data": {"type": "incidents", "attributes": {"title": title, "customer_impacted": params.get("customer_impacted", False)}}}, api_version="v2")
            if response.status_code in [200, 201]:
                incident = response.json().get("data", {})
                return IntegrationResult(success=True, data={"incident_id": incident.get("id"), "title": incident.get("attributes", {}).get("title")})
            return IntegrationResult(success=False, error_message="Failed to create incident", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
