"""
Auth0 Integration

Real Auth0 integration using Auth0 Management API.
Supports user management, roles, and authentication operations.

Supported Actions:
- list_users: List users with filters
- get_user: Get user details
- create_user: Create new user
- update_user: Update user profile
- delete_user: Delete user
- list_roles: List roles
- assign_roles: Assign roles to user
- remove_roles: Remove roles from user
- list_connections: List identity connections

Authentication:
- Client Credentials (client_id + client_secret)
- Management API Token

Required Credentials:
- domain: Auth0 domain (e.g., 'yourcompany.auth0.com')
- client_id: Auth0 Management API client ID
- client_secret: Auth0 Management API client secret

API Docs: https://auth0.com/docs/api/management/v2
"""

import asyncio
import random
import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, ClassVar

from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

logger = logging.getLogger(__name__)


class Auth0Integration(BaseIntegration):
    """
    Auth0 integration for identity and access management.

    Features resilient connection handling:
    - Connection pooling via shared httpx.AsyncClient
    - Automatic retries with exponential backoff
    - Token caching with auto-refresh
    - Rate limit handling
    """

    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # Token cache
    _token_cache: ClassVar[Dict[str, Dict[str, Any]]] = {}
    _token_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 30.0
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "auth0"

    @property
    def display_name(self) -> str:
        return "Auth0"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.OAUTH2

    @property
    def supported_actions(self) -> List[str]:
        return [
            "list_users",
            "get_user",
            "create_user",
            "update_user",
            "delete_user",
            "list_roles",
            "assign_roles",
            "remove_roles",
            "list_connections",
            "test_connection",
        ]

    def _validate_credentials(self) -> None:
        super()._validate_credentials()

        required = ["domain", "client_id", "client_secret"]
        missing = [k for k in required if not self.auth_credentials.get(k)]

        if missing:
            raise IntegrationError(f"Auth0 requires: {', '.join(missing)}", code="MISSING_CREDENTIALS")

    def _get_domain(self) -> str:
        domain = self.auth_credentials["domain"]
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return domain.rstrip("/")

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

    async def _get_access_token(self) -> str:
        """Get Management API access token with caching."""
        domain = self._get_domain()
        client_id = self.auth_credentials["client_id"]
        cache_key = f"{domain}:{client_id}"

        async with self._token_lock:
            cached = self._token_cache.get(cache_key)
            if cached and datetime.utcnow() < cached["expires_at"]:
                return cached["access_token"]

            try:
                client = await self._get_client()
                response = await client.post(
                    f"{domain}/oauth/token",
                    json={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": self.auth_credentials["client_secret"],
                        "audience": f"{domain}/api/v2/",
                    },
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code != 200:
                    raise IntegrationError(f"Token request failed: {response.text}", code="AUTH_ERROR")

                data = response.json()
                access_token = data["access_token"]
                expires_in = data.get("expires_in", 86400)

                self._token_cache[cache_key] = {
                    "access_token": access_token,
                    "expires_at": datetime.utcnow() + timedelta(seconds=expires_in - 300),
                }

                return access_token

            except IntegrationError:
                raise
            except Exception as e:
                raise IntegrationError(f"Token request failed: {str(e)}", code="AUTH_ERROR")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        domain = self._get_domain()
        url = f"{domain}/api/v2{endpoint}"

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                access_token = await self._get_access_token()
                client = await self._get_client()

                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code == 429 and attempt < self.MAX_RETRIES:
                    retry_after = response.headers.get("X-RateLimit-Reset")
                    delay = self._calculate_retry_delay(attempt, float(retry_after) if retry_after else None)
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
            if action == "list_users":
                result = await self._list_users(params)
            elif action == "get_user":
                result = await self._get_user(params)
            elif action == "create_user":
                result = await self._create_user(params)
            elif action == "update_user":
                result = await self._update_user(params)
            elif action == "delete_user":
                result = await self._delete_user(params)
            elif action == "list_roles":
                result = await self._list_roles(params)
            elif action == "assign_roles":
                result = await self._assign_roles(params)
            elif action == "remove_roles":
                result = await self._remove_roles(params)
            elif action == "list_connections":
                result = await self._list_connections(params)
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
            response = await self._make_request("GET", "/users", params={"per_page": "1"})

            if response.status_code == 200:
                return IntegrationResult(
                    success=True,
                    data={"message": "Connected to Auth0", "domain": self.auth_credentials.get("domain")},
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
        try:
            query_params = {
                "per_page": str(params.get("per_page", 25)),
                "page": str(params.get("page", 0)),
            }
            if params.get("q"):
                query_params["q"] = params["q"]
            if params.get("search_engine"):
                query_params["search_engine"] = params["search_engine"]

            response = await self._make_request("GET", "/users", params=query_params)

            if response.status_code == 200:
                users = [
                    {
                        "user_id": u.get("user_id"),
                        "email": u.get("email"),
                        "name": u.get("name"),
                        "nickname": u.get("nickname"),
                        "created_at": u.get("created_at"),
                        "last_login": u.get("last_login"),
                        "email_verified": u.get("email_verified"),
                    }
                    for u in response.json()
                ]
                return IntegrationResult(success=True, data={"users": users, "count": len(users)})
            else:
                return IntegrationResult(success=False, error_message="Failed to list users", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_user(self, params: Dict[str, Any]) -> IntegrationResult:
        user_id = params.get("user_id")
        if not user_id:
            return IntegrationResult(success=False, error_message="Missing: user_id", error_code="MISSING_PARAMS")

        try:
            response = await self._make_request("GET", f"/users/{user_id}")

            if response.status_code == 200:
                u = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "user_id": u.get("user_id"),
                        "email": u.get("email"),
                        "name": u.get("name"),
                        "nickname": u.get("nickname"),
                        "picture": u.get("picture"),
                        "created_at": u.get("created_at"),
                        "last_login": u.get("last_login"),
                        "logins_count": u.get("logins_count"),
                        "email_verified": u.get("email_verified"),
                        "identities": u.get("identities"),
                    },
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to get user", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _create_user(self, params: Dict[str, Any]) -> IntegrationResult:
        email = params.get("email")
        connection = params.get("connection", "Username-Password-Authentication")

        if not email:
            return IntegrationResult(success=False, error_message="Missing: email", error_code="MISSING_PARAMS")

        try:
            user_data = {
                "email": email,
                "connection": connection,
                "email_verified": params.get("email_verified", False),
            }

            if params.get("password"):
                user_data["password"] = params["password"]
            if params.get("name"):
                user_data["name"] = params["name"]
            if params.get("nickname"):
                user_data["nickname"] = params["nickname"]
            if params.get("user_metadata"):
                user_data["user_metadata"] = params["user_metadata"]

            response = await self._make_request("POST", "/users", json=user_data)

            if response.status_code in [200, 201]:
                u = response.json()
                return IntegrationResult(
                    success=True,
                    data={"user_id": u.get("user_id"), "email": u.get("email"), "created_at": u.get("created_at")},
                )
            else:
                error = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error.get("message", "Failed to create user"),
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _update_user(self, params: Dict[str, Any]) -> IntegrationResult:
        user_id = params.get("user_id")
        if not user_id:
            return IntegrationResult(success=False, error_message="Missing: user_id", error_code="MISSING_PARAMS")

        try:
            update_data = {}
            for field in ["email", "name", "nickname", "password", "email_verified", "blocked", "user_metadata", "app_metadata"]:
                if field in params:
                    update_data[field] = params[field]

            response = await self._make_request("PATCH", f"/users/{user_id}", json=update_data)

            if response.status_code == 200:
                u = response.json()
                return IntegrationResult(success=True, data={"user_id": u.get("user_id"), "updated": True})
            else:
                return IntegrationResult(success=False, error_message="Failed to update user", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _delete_user(self, params: Dict[str, Any]) -> IntegrationResult:
        user_id = params.get("user_id")
        if not user_id:
            return IntegrationResult(success=False, error_message="Missing: user_id", error_code="MISSING_PARAMS")

        try:
            response = await self._make_request("DELETE", f"/users/{user_id}")

            if response.status_code in [200, 204]:
                return IntegrationResult(success=True, data={"user_id": user_id, "deleted": True})
            else:
                return IntegrationResult(success=False, error_message="Failed to delete user", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_roles(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            query_params = {"per_page": str(params.get("per_page", 25))}

            response = await self._make_request("GET", "/roles", params=query_params)

            if response.status_code == 200:
                roles = [
                    {"id": r.get("id"), "name": r.get("name"), "description": r.get("description")}
                    for r in response.json()
                ]
                return IntegrationResult(success=True, data={"roles": roles, "count": len(roles)})
            else:
                return IntegrationResult(success=False, error_message="Failed to list roles", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _assign_roles(self, params: Dict[str, Any]) -> IntegrationResult:
        user_id = params.get("user_id")
        roles = params.get("roles")

        if not user_id or not roles:
            return IntegrationResult(success=False, error_message="Missing: user_id, roles", error_code="MISSING_PARAMS")

        try:
            response = await self._make_request("POST", f"/users/{user_id}/roles", json={"roles": roles})

            if response.status_code in [200, 204]:
                return IntegrationResult(success=True, data={"user_id": user_id, "roles_assigned": roles})
            else:
                return IntegrationResult(success=False, error_message="Failed to assign roles", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _remove_roles(self, params: Dict[str, Any]) -> IntegrationResult:
        user_id = params.get("user_id")
        roles = params.get("roles")

        if not user_id or not roles:
            return IntegrationResult(success=False, error_message="Missing: user_id, roles", error_code="MISSING_PARAMS")

        try:
            response = await self._make_request("DELETE", f"/users/{user_id}/roles", json={"roles": roles})

            if response.status_code in [200, 204]:
                return IntegrationResult(success=True, data={"user_id": user_id, "roles_removed": roles})
            else:
                return IntegrationResult(success=False, error_message="Failed to remove roles", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_connections(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            query_params = {"per_page": str(params.get("per_page", 25))}

            response = await self._make_request("GET", "/connections", params=query_params)

            if response.status_code == 200:
                connections = [
                    {
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "strategy": c.get("strategy"),
                        "enabled_clients": c.get("enabled_clients"),
                    }
                    for c in response.json()
                ]
                return IntegrationResult(success=True, data={"connections": connections, "count": len(connections)})
            else:
                return IntegrationResult(success=False, error_message="Failed to list connections", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
