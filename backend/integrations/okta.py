"""
Okta Integration

Real Okta integration using Okta Management API.
Supports user management, group operations, and authentication events.

Supported Actions:
- list_users: List users with filters
- get_user: Get user details
- create_user: Create new user
- update_user: Update user profile
- deactivate_user: Deactivate a user
- list_groups: List groups
- add_user_to_group: Add user to group
- remove_user_from_group: Remove user from group
- list_apps: List applications

Authentication:
- API Token (SSWS)
- OAuth 2.0 (for OAuth apps)

Required Credentials:
- api_token: Okta API token
- domain: Okta domain (e.g., 'yourcompany.okta.com')

API Docs: https://developer.okta.com/docs/reference/api/
"""

import asyncio
import random
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional, ClassVar

from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

logger = logging.getLogger(__name__)


class OktaIntegration(BaseIntegration):
    """
    Okta integration for identity and access management.

    Features resilient connection handling:
    - Connection pooling via shared httpx.AsyncClient
    - Automatic retries with exponential backoff
    - Rate limit handling with X-Rate-Limit headers
    - Configurable timeouts
    """

    # Shared client for connection pooling
    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 30.0

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "okta"

    @property
    def display_name(self) -> str:
        return "Okta"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "list_users",
            "get_user",
            "create_user",
            "update_user",
            "deactivate_user",
            "list_groups",
            "add_user_to_group",
            "remove_user_from_group",
            "list_apps",
            "test_connection",
        ]

    def _validate_credentials(self) -> None:
        """Validate Okta credentials."""
        super()._validate_credentials()

        required = ["api_token", "domain"]
        missing = [k for k in required if not self.auth_credentials.get(k)]

        if missing:
            raise IntegrationError(
                f"Okta requires: {', '.join(missing)}",
                code="MISSING_CREDENTIALS",
            )

    def _get_base_url(self) -> str:
        """Get Okta API base URL."""
        domain = self.auth_credentials["domain"]
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return f"{domain}/api/v1"

    @classmethod
    async def _get_client(cls) -> httpx.AsyncClient:
        """Get or create shared AsyncClient."""
        async with cls._client_lock:
            if cls._client is None or cls._client.is_closed:
                cls._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout=cls.REQUEST_TIMEOUT, connect=10.0),
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                        keepalive_expiry=30.0,
                    ),
                )
                logger.info("Created new Okta API client")
            return cls._client

    @classmethod
    async def close_client(cls):
        """Close the shared client."""
        async with cls._client_lock:
            if cls._client and not cls._client.is_closed:
                await cls._client.aclose()
                cls._client = None

    def _calculate_retry_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        if retry_after:
            return min(retry_after, self.MAX_RETRY_DELAY)
        delay = self.BASE_RETRY_DELAY * (2 ** attempt)
        delay = min(delay, self.MAX_RETRY_DELAY)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0.1, delay + jitter)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make HTTP request with automatic retries."""
        base_url = self._get_base_url()
        url = f"{base_url}{endpoint}"
        api_token = self.auth_credentials["api_token"]

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()

                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers={
                        "Authorization": f"SSWS {api_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )

                if response.status_code == 429:
                    if attempt < self.MAX_RETRIES:
                        # Okta uses X-Rate-Limit-Reset header
                        reset_time = response.headers.get("X-Rate-Limit-Reset")
                        if reset_time:
                            wait_time = int(reset_time) - int(datetime.utcnow().timestamp())
                            delay = max(1, min(wait_time, self.MAX_RETRY_DELAY))
                        else:
                            delay = self._calculate_retry_delay(attempt)
                        logger.warning(f"Rate limited, retrying in {delay:.1f}s")
                        await asyncio.sleep(delay)
                        continue

                if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Server error {response.status_code}, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue

                return response

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                if attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Connection error, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue
                raise IntegrationError(f"Connection failed: {str(e)}", code="CONNECTION_ERROR")

        raise IntegrationError("Request failed after all retries", code="MAX_RETRIES_EXCEEDED")

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        """Execute Okta action."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "list_users":
                result = await self._list_users(params)
            elif action == "get_user":
                result = await self._get_user(params)
            elif action == "create_user":
                result = await self._create_user(params)
            elif action == "update_user":
                result = await self._update_user(params)
            elif action == "deactivate_user":
                result = await self._deactivate_user(params)
            elif action == "list_groups":
                result = await self._list_groups(params)
            elif action == "add_user_to_group":
                result = await self._add_user_to_group(params)
            elif action == "remove_user_from_group":
                result = await self._remove_user_from_group(params)
            elif action == "list_apps":
                result = await self._list_apps(params)
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
        """Test Okta connection."""
        try:
            response = await self._make_request("GET", "/users/me")

            if response.status_code == 200:
                data = response.json()
                profile = data.get("profile", {})
                return IntegrationResult(
                    success=True,
                    data={
                        "user_id": data.get("id"),
                        "email": profile.get("email"),
                        "name": f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
                    },
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Connection test failed",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="CONNECTION_ERROR")

    async def _list_users(self, params: Dict[str, Any]) -> IntegrationResult:
        """List users with filters."""
        try:
            query_params = {"limit": params.get("limit", 200)}

            if params.get("filter"):
                query_params["filter"] = params["filter"]
            if params.get("search"):
                query_params["search"] = params["search"]
            if params.get("q"):
                query_params["q"] = params["q"]

            response = await self._make_request("GET", "/users", params=query_params)

            if response.status_code == 200:
                data = response.json()
                users = [
                    {
                        "id": u.get("id"),
                        "email": u.get("profile", {}).get("email"),
                        "first_name": u.get("profile", {}).get("firstName"),
                        "last_name": u.get("profile", {}).get("lastName"),
                        "status": u.get("status"),
                        "created": u.get("created"),
                    }
                    for u in data
                ]
                return IntegrationResult(
                    success=True,
                    data={"users": users, "count": len(users)},
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to list users",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_user(self, params: Dict[str, Any]) -> IntegrationResult:
        """Get user details."""
        user_id = params.get("user_id")

        if not user_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameter: user_id",
                error_code="MISSING_PARAMS",
            )

        try:
            response = await self._make_request("GET", f"/users/{user_id}")

            if response.status_code == 200:
                data = response.json()
                profile = data.get("profile", {})
                return IntegrationResult(
                    success=True,
                    data={
                        "id": data.get("id"),
                        "email": profile.get("email"),
                        "first_name": profile.get("firstName"),
                        "last_name": profile.get("lastName"),
                        "login": profile.get("login"),
                        "status": data.get("status"),
                        "created": data.get("created"),
                        "last_login": data.get("lastLogin"),
                        "last_updated": data.get("lastUpdated"),
                    },
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to get user",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _create_user(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new user."""
        email = params.get("email")
        first_name = params.get("first_name")
        last_name = params.get("last_name")

        if not email or not first_name or not last_name:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameters: email, first_name, last_name",
                error_code="MISSING_PARAMS",
            )

        try:
            user_data = {
                "profile": {
                    "firstName": first_name,
                    "lastName": last_name,
                    "email": email,
                    "login": params.get("login", email),
                }
            }

            if params.get("password"):
                user_data["credentials"] = {
                    "password": {"value": params["password"]}
                }

            activate = params.get("activate", True)
            endpoint = f"/users?activate={str(activate).lower()}"

            response = await self._make_request("POST", endpoint, json=user_data)

            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "user_id": data.get("id"),
                        "email": data.get("profile", {}).get("email"),
                        "status": data.get("status"),
                    },
                )
            else:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("errorSummary", "Failed to create user"),
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _update_user(self, params: Dict[str, Any]) -> IntegrationResult:
        """Update user profile."""
        user_id = params.get("user_id")

        if not user_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameter: user_id",
                error_code="MISSING_PARAMS",
            )

        try:
            profile = {}
            if params.get("first_name"):
                profile["firstName"] = params["first_name"]
            if params.get("last_name"):
                profile["lastName"] = params["last_name"]
            if params.get("email"):
                profile["email"] = params["email"]

            response = await self._make_request("POST", f"/users/{user_id}", json={"profile": profile})

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "user_id": data.get("id"),
                        "updated": True,
                    },
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to update user",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _deactivate_user(self, params: Dict[str, Any]) -> IntegrationResult:
        """Deactivate a user."""
        user_id = params.get("user_id")

        if not user_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameter: user_id",
                error_code="MISSING_PARAMS",
            )

        try:
            response = await self._make_request("POST", f"/users/{user_id}/lifecycle/deactivate")

            if response.status_code in [200, 204]:
                return IntegrationResult(
                    success=True,
                    data={"user_id": user_id, "deactivated": True},
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to deactivate user",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_groups(self, params: Dict[str, Any]) -> IntegrationResult:
        """List groups."""
        try:
            query_params = {"limit": params.get("limit", 200)}
            if params.get("q"):
                query_params["q"] = params["q"]
            if params.get("filter"):
                query_params["filter"] = params["filter"]

            response = await self._make_request("GET", "/groups", params=query_params)

            if response.status_code == 200:
                data = response.json()
                groups = [
                    {
                        "id": g.get("id"),
                        "name": g.get("profile", {}).get("name"),
                        "description": g.get("profile", {}).get("description"),
                        "type": g.get("type"),
                    }
                    for g in data
                ]
                return IntegrationResult(
                    success=True,
                    data={"groups": groups, "count": len(groups)},
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to list groups",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _add_user_to_group(self, params: Dict[str, Any]) -> IntegrationResult:
        """Add user to group."""
        user_id = params.get("user_id")
        group_id = params.get("group_id")

        if not user_id or not group_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameters: user_id, group_id",
                error_code="MISSING_PARAMS",
            )

        try:
            response = await self._make_request("PUT", f"/groups/{group_id}/users/{user_id}")

            if response.status_code in [200, 204]:
                return IntegrationResult(
                    success=True,
                    data={"user_id": user_id, "group_id": group_id, "added": True},
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to add user to group",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _remove_user_from_group(self, params: Dict[str, Any]) -> IntegrationResult:
        """Remove user from group."""
        user_id = params.get("user_id")
        group_id = params.get("group_id")

        if not user_id or not group_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameters: user_id, group_id",
                error_code="MISSING_PARAMS",
            )

        try:
            response = await self._make_request("DELETE", f"/groups/{group_id}/users/{user_id}")

            if response.status_code in [200, 204]:
                return IntegrationResult(
                    success=True,
                    data={"user_id": user_id, "group_id": group_id, "removed": True},
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to remove user from group",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_apps(self, params: Dict[str, Any]) -> IntegrationResult:
        """List applications."""
        try:
            query_params = {"limit": params.get("limit", 200)}
            if params.get("q"):
                query_params["q"] = params["q"]

            response = await self._make_request("GET", "/apps", params=query_params)

            if response.status_code == 200:
                data = response.json()
                apps = [
                    {
                        "id": app.get("id"),
                        "name": app.get("name"),
                        "label": app.get("label"),
                        "status": app.get("status"),
                        "sign_on_mode": app.get("signOnMode"),
                    }
                    for app in data
                ]
                return IntegrationResult(
                    success=True,
                    data={"apps": apps, "count": len(apps)},
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to list apps",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
