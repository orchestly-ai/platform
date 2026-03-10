"""
Microsoft Teams Integration

Real Microsoft Teams integration using Microsoft Graph API.
Supports sending messages, creating channels, managing teams, and scheduling meetings.

Authentication:
- OAuth 2.0 with Microsoft identity platform
- Application permissions for daemon apps

Required Credentials (OAuth2):
- access_token: OAuth access token
- tenant_id: Azure AD tenant ID

Required Credentials (App-only):
- client_id: Azure AD application ID
- client_secret: Azure AD client secret
- tenant_id: Azure AD tenant ID

API Docs: https://docs.microsoft.com/en-us/graph/api/overview
"""

import asyncio
import random
import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, ClassVar

from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

logger = logging.getLogger(__name__)


class MicrosoftTeamsIntegration(BaseIntegration):
    """Microsoft Teams integration using Microsoft Graph API."""

    GRAPH_API_URL = "https://graph.microsoft.com/v1.0"
    AUTH_URL = "https://login.microsoftonline.com"

    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _token_cache: ClassVar[Dict[str, Dict[str, Any]]] = {}
    _token_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 30.0
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "microsoft_teams"

    @property
    def display_name(self) -> str:
        return "Microsoft Teams"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.OAUTH2

    @property
    def supported_actions(self) -> List[str]:
        return ["send_message", "create_channel", "list_channels", "list_teams", "create_meeting", "get_user", "test_connection"]

    def _validate_credentials(self) -> None:
        super()._validate_credentials()
        if self.auth_credentials.get("access_token"):
            return
        required = ["client_id", "client_secret", "tenant_id"]
        missing = [k for k in required if not self.auth_credentials.get(k)]
        if missing:
            raise IntegrationError(f"Microsoft Teams requires: {', '.join(missing)}", code="MISSING_CREDENTIALS")

    @classmethod
    async def _get_client(cls) -> httpx.AsyncClient:
        async with cls._client_lock:
            if cls._client is None or cls._client.is_closed:
                cls._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout=cls.REQUEST_TIMEOUT, connect=10.0),
                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30.0),
                )
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
        delay = self.BASE_RETRY_DELAY * (2 ** attempt)
        delay = min(delay, self.MAX_RETRY_DELAY)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0.1, delay + jitter)

    async def _get_app_token(self) -> str:
        client_id = self.auth_credentials["client_id"]
        client_secret = self.auth_credentials["client_secret"]
        tenant_id = self.auth_credentials.get("tenant_id", "common")
        cache_key = f"{client_id}:{tenant_id}"

        async with self._token_lock:
            cached = self._token_cache.get(cache_key)
            if cached and datetime.utcnow() < cached["expires_at"]:
                return cached["access_token"]

            client = await self._get_client()
            response = await client.post(
                f"{self.AUTH_URL}/{tenant_id}/oauth2/v2.0/token",
                data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "scope": "https://graph.microsoft.com/.default"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code != 200:
                raise IntegrationError(f"Token request failed: {response.text}", code="AUTH_FAILED")

            token_data = response.json()
            self._token_cache[cache_key] = {"access_token": token_data["access_token"], "expires_at": datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600) - 300)}
            return token_data["access_token"]

    async def _get_access_token(self) -> str:
        if self.auth_credentials.get("access_token"):
            return self.auth_credentials["access_token"]
        return await self._get_app_token()

    async def _make_request(self, method: str, endpoint: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        url = f"{self.GRAPH_API_URL}{endpoint}"
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                access_token = await self._get_access_token()
                client = await self._get_client()
                response = await client.request(method=method, url=url, json=json, params=params, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"})
                if response.status_code == 429 and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt, float(response.headers.get("Retry-After", 0)) or None)
                    await asyncio.sleep(delay)
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
            if action == "send_message":
                result = await self._send_message(params)
            elif action == "create_channel":
                result = await self._create_channel(params)
            elif action == "list_channels":
                result = await self._list_channels(params)
            elif action == "list_teams":
                result = await self._list_teams(params)
            elif action == "create_meeting":
                result = await self._create_meeting(params)
            elif action == "get_user":
                result = await self._get_user(params)
            elif action == "test_connection":
                result = await self.test_connection()
            else:
                raise IntegrationError(f"Action {action} not implemented", code="NOT_IMPLEMENTED")
            result.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return result
        except IntegrationError as e:
            return IntegrationResult(success=False, error_message=e.message, error_code=e.code, duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000)

    async def test_connection(self) -> IntegrationResult:
        try:
            response = await self._make_request("GET", "/me")
            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(success=True, data={"user_id": data.get("id"), "display_name": data.get("displayName"), "email": data.get("mail") or data.get("userPrincipalName")})
            return IntegrationResult(success=False, error_message="Connection test failed", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="CONNECTION_ERROR")

    async def _send_message(self, params: Dict[str, Any]) -> IntegrationResult:
        team_id, channel_id, chat_id, content = params.get("team_id"), params.get("channel_id"), params.get("chat_id"), params.get("content")
        if not content:
            return IntegrationResult(success=False, error_message="Missing: content", error_code="MISSING_PARAMS")
        endpoint = f"/chats/{chat_id}/messages" if chat_id else f"/teams/{team_id}/channels/{channel_id}/messages" if team_id and channel_id else None
        if not endpoint:
            return IntegrationResult(success=False, error_message="Provide chat_id or team_id+channel_id", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("POST", endpoint, json={"body": {"contentType": params.get("content_type", "text"), "content": content}})
            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(success=True, data={"message_id": data.get("id"), "web_url": data.get("webUrl")})
            return IntegrationResult(success=False, error_message="Failed to send message", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _create_channel(self, params: Dict[str, Any]) -> IntegrationResult:
        team_id, display_name = params.get("team_id"), params.get("display_name")
        if not team_id or not display_name:
            return IntegrationResult(success=False, error_message="Missing: team_id, display_name", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("POST", f"/teams/{team_id}/channels", json={"displayName": display_name, "description": params.get("description", ""), "membershipType": params.get("membership_type", "standard")})
            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(success=True, data={"channel_id": data.get("id"), "display_name": data.get("displayName")})
            return IntegrationResult(success=False, error_message="Failed to create channel", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_channels(self, params: Dict[str, Any]) -> IntegrationResult:
        team_id = params.get("team_id")
        if not team_id:
            return IntegrationResult(success=False, error_message="Missing: team_id", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("GET", f"/teams/{team_id}/channels")
            if response.status_code == 200:
                channels = [{"id": ch.get("id"), "display_name": ch.get("displayName"), "description": ch.get("description")} for ch in response.json().get("value", [])]
                return IntegrationResult(success=True, data={"channels": channels, "count": len(channels)})
            return IntegrationResult(success=False, error_message="Failed to list channels", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_teams(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_request("GET", "/me/joinedTeams")
            if response.status_code == 200:
                teams = [{"id": t.get("id"), "display_name": t.get("displayName"), "description": t.get("description")} for t in response.json().get("value", [])]
                return IntegrationResult(success=True, data={"teams": teams, "count": len(teams)})
            return IntegrationResult(success=False, error_message="Failed to list teams", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _create_meeting(self, params: Dict[str, Any]) -> IntegrationResult:
        subject = params.get("subject")
        if not subject:
            return IntegrationResult(success=False, error_message="Missing: subject", error_code="MISSING_PARAMS")
        try:
            meeting_data = {"subject": subject}
            if params.get("start_time"):
                meeting_data["startDateTime"] = params["start_time"]
            if params.get("end_time"):
                meeting_data["endDateTime"] = params["end_time"]
            response = await self._make_request("POST", "/me/onlineMeetings", json=meeting_data)
            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(success=True, data={"meeting_id": data.get("id"), "join_url": data.get("joinWebUrl"), "subject": data.get("subject")})
            return IntegrationResult(success=False, error_message="Failed to create meeting", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_user(self, params: Dict[str, Any]) -> IntegrationResult:
        user_id = params.get("user_id", "me")
        try:
            endpoint = "/me" if user_id == "me" else f"/users/{user_id}"
            response = await self._make_request("GET", endpoint)
            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(success=True, data={"id": data.get("id"), "display_name": data.get("displayName"), "email": data.get("mail") or data.get("userPrincipalName")})
            return IntegrationResult(success=False, error_message="Failed to get user", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
