"""
Jira Integration

Real Jira integration using Atlassian REST API.
Supports creating issues, managing projects, and tracking work.

Authentication: API Token (Basic Auth with email:token)

Required Credentials:
- email: Atlassian account email
- api_token: Jira API token
- domain: Jira cloud domain (e.g., 'yourcompany.atlassian.net')

API Docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
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


class JiraIntegration(BaseIntegration):
    """Jira integration using Atlassian REST API."""

    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 30.0
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "jira"

    @property
    def display_name(self) -> str:
        return "Jira"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.BASIC_AUTH

    @property
    def supported_actions(self) -> List[str]:
        return ["create_issue", "update_issue", "get_issue", "search_issues", "add_comment", "transition_issue", "list_projects", "test_connection"]

    def _validate_credentials(self) -> None:
        super()._validate_credentials()
        required = ["email", "api_token", "domain"]
        missing = [k for k in required if not self.auth_credentials.get(k)]
        if missing:
            raise IntegrationError(f"Jira requires: {', '.join(missing)}", code="MISSING_CREDENTIALS")

    def _get_base_url(self) -> str:
        domain = self.auth_credentials["domain"]
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return f"{domain}/rest/api/3"

    def _get_auth_header(self) -> str:
        credentials = f"{self.auth_credentials['email']}:{self.auth_credentials['api_token']}"
        return f"Basic {base64.b64encode(credentials.encode()).decode()}"

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

    async def _make_request(self, method: str, endpoint: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        url = f"{self._get_base_url()}{endpoint}"
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()
                response = await client.request(method=method, url=url, json=json, params=params, headers={"Authorization": self._get_auth_header(), "Content-Type": "application/json", "Accept": "application/json"})
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
            response = await self._make_request("GET", "/myself")
            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(success=True, data={"account_id": data.get("accountId"), "display_name": data.get("displayName"), "email": data.get("emailAddress")})
            return IntegrationResult(success=False, error_message="Connection test failed", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="CONNECTION_ERROR")

    async def _create_issue(self, params: Dict[str, Any]) -> IntegrationResult:
        project_key, summary = params.get("project_key"), params.get("summary")
        if not project_key or not summary:
            return IntegrationResult(success=False, error_message="Missing: project_key, summary", error_code="MISSING_PARAMS")
        try:
            issue_data = {"fields": {"project": {"key": project_key}, "summary": summary, "issuetype": {"name": params.get("issue_type", "Task")}}}
            if params.get("description"):
                issue_data["fields"]["description"] = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": params["description"]}]}]}
            if params.get("priority"):
                issue_data["fields"]["priority"] = {"name": params["priority"]}
            if params.get("assignee"):
                issue_data["fields"]["assignee"] = {"accountId": params["assignee"]}
            response = await self._make_request("POST", "/issue", json=issue_data)
            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(success=True, data={"issue_id": data.get("id"), "issue_key": data.get("key")})
            return IntegrationResult(success=False, error_message="Failed to create issue", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _update_issue(self, params: Dict[str, Any]) -> IntegrationResult:
        issue_key = params.get("issue_key")
        if not issue_key:
            return IntegrationResult(success=False, error_message="Missing: issue_key", error_code="MISSING_PARAMS")
        try:
            fields = {}
            if params.get("summary"):
                fields["summary"] = params["summary"]
            if params.get("description"):
                fields["description"] = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": params["description"]}]}]}
            response = await self._make_request("PUT", f"/issue/{issue_key}", json={"fields": fields})
            if response.status_code in [200, 204]:
                return IntegrationResult(success=True, data={"issue_key": issue_key, "updated": True})
            return IntegrationResult(success=False, error_message="Failed to update issue", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_issue(self, params: Dict[str, Any]) -> IntegrationResult:
        issue_key = params.get("issue_key")
        if not issue_key:
            return IntegrationResult(success=False, error_message="Missing: issue_key", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("GET", f"/issue/{issue_key}")
            if response.status_code == 200:
                data = response.json()
                fields = data.get("fields", {})
                return IntegrationResult(success=True, data={"issue_key": data.get("key"), "summary": fields.get("summary"), "status": fields.get("status", {}).get("name"), "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None, "issue_type": fields.get("issuetype", {}).get("name")})
            return IntegrationResult(success=False, error_message="Failed to get issue", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _search_issues(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_request("GET", "/search", params={"jql": params.get("jql", ""), "maxResults": params.get("max_results", 50)})
            if response.status_code == 200:
                data = response.json()
                issues = [{"issue_key": i.get("key"), "summary": i.get("fields", {}).get("summary"), "status": i.get("fields", {}).get("status", {}).get("name")} for i in data.get("issues", [])]
                return IntegrationResult(success=True, data={"issues": issues, "total": data.get("total"), "count": len(issues)})
            return IntegrationResult(success=False, error_message="Failed to search issues", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _add_comment(self, params: Dict[str, Any]) -> IntegrationResult:
        issue_key, body = params.get("issue_key"), params.get("body")
        if not issue_key or not body:
            return IntegrationResult(success=False, error_message="Missing: issue_key, body", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("POST", f"/issue/{issue_key}/comment", json={"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}})
            if response.status_code in [200, 201]:
                return IntegrationResult(success=True, data={"comment_id": response.json().get("id"), "issue_key": issue_key})
            return IntegrationResult(success=False, error_message="Failed to add comment", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _transition_issue(self, params: Dict[str, Any]) -> IntegrationResult:
        issue_key, transition_id = params.get("issue_key"), params.get("transition_id")
        if not issue_key or not transition_id:
            return IntegrationResult(success=False, error_message="Missing: issue_key, transition_id", error_code="MISSING_PARAMS")
        try:
            response = await self._make_request("POST", f"/issue/{issue_key}/transitions", json={"transition": {"id": transition_id}})
            if response.status_code in [200, 204]:
                return IntegrationResult(success=True, data={"issue_key": issue_key, "transitioned": True})
            return IntegrationResult(success=False, error_message="Failed to transition issue", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_projects(self, params: Dict[str, Any]) -> IntegrationResult:
        try:
            response = await self._make_request("GET", "/project")
            if response.status_code == 200:
                projects = [{"id": p.get("id"), "key": p.get("key"), "name": p.get("name")} for p in response.json()]
                return IntegrationResult(success=True, data={"projects": projects, "count": len(projects)})
            return IntegrationResult(success=False, error_message="Failed to list projects", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
