"""
GitHub Integration - FULLY IMPLEMENTED

Real GitHub API integration for repository management.

Supported Actions:
- create_issue: Create new issue
- create_pr: Create pull request
- add_comment: Add comment to issue/PR
- list_repos: List repositories
- get_repo: Get repository details

Authentication: OAuth 2.0 or Personal Access Token
API Docs: https://docs.github.com/en/rest
"""

import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class GitHubIntegration(BaseIntegration):
    """GitHub integration with real API client."""

    API_BASE_URL = "https://api.github.com"

    @property
    def name(self) -> str:
        return "github"

    @property
    def display_name(self) -> str:
        return "GitHub"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.OAUTH2

    @property
    def supported_actions(self) -> List[str]:
        return [
            "create_issue",
            "create_pr",
            "add_comment",
            "list_repos",
            "get_repo",
        ]

    def _validate_credentials(self) -> None:
        """Validate GitHub credentials."""
        super()._validate_credentials()

        token = self.auth_credentials.get("access_token") or self.auth_credentials.get("token")
        if not token:
            raise IntegrationError(
                "GitHub requires 'access_token' or 'token'",
                code="MISSING_TOKEN",
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for GitHub API."""
        token = self.auth_credentials.get("access_token") or self.auth_credentials.get("token")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to GitHub API."""
        url = f"{self.API_BASE_URL}/{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=data,
                ) as response:
                    response_data = await response.json()

                    if response.status >= 400:
                        error_msg = response_data.get("message", "Unknown error")
                        raise IntegrationError(
                            f"GitHub API error: {error_msg}",
                            code=str(response.status),
                            status_code=response.status,
                            details=response_data,
                        )

                    return response_data

        except aiohttp.ClientError as e:
            raise IntegrationError(f"HTTP request failed: {str(e)}", code="HTTP_ERROR")
        except Exception as e:
            if isinstance(e, IntegrationError):
                raise
            raise IntegrationError(f"Unexpected error: {str(e)}", code="UNKNOWN_ERROR")

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        """Execute GitHub action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "create_issue":
                result = await self._create_issue(params)
            elif action == "create_pr":
                result = await self._create_pr(params)
            elif action == "add_comment":
                result = await self._add_comment(params)
            elif action == "list_repos":
                result = await self._list_repos(params)
            elif action == "get_repo":
                result = await self._get_repo(params)
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
        """Test GitHub connection using user endpoint."""
        try:
            response = await self._make_request("GET", "user")
            return IntegrationResult(
                success=True,
                data={
                    "login": response.get("login"),
                    "name": response.get("name"),
                    "email": response.get("email"),
                },
            )
        except IntegrationError as e:
            return IntegrationResult(success=False, error_message=e.message, error_code=e.code)

    async def _create_issue(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create GitHub issue."""
        if "owner" not in params or "repo" not in params or "title" not in params:
            raise IntegrationError(
                "Missing required parameters: 'owner', 'repo', 'title'",
                code="MISSING_PARAMS",
            )

        payload = {"title": params["title"]}
        if "body" in params:
            payload["body"] = params["body"]
        if "labels" in params:
            payload["labels"] = params["labels"]
        if "assignees" in params:
            payload["assignees"] = params["assignees"]

        endpoint = f"repos/{params['owner']}/{params['repo']}/issues"
        response = await self._make_request("POST", endpoint, payload)

        return IntegrationResult(
            success=True,
            data={
                "issue_number": response.get("number"),
                "url": response.get("html_url"),
                "state": response.get("state"),
            },
        )

    async def _create_pr(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create pull request."""
        required = ["owner", "repo", "title", "head", "base"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(
                f"Missing required parameters: {', '.join(missing)}",
                code="MISSING_PARAMS",
            )

        payload = {
            "title": params["title"],
            "head": params["head"],
            "base": params["base"],
        }
        if "body" in params:
            payload["body"] = params["body"]

        endpoint = f"repos/{params['owner']}/{params['repo']}/pulls"
        response = await self._make_request("POST", endpoint, payload)

        return IntegrationResult(
            success=True,
            data={
                "pr_number": response.get("number"),
                "url": response.get("html_url"),
                "state": response.get("state"),
            },
        )

    async def _add_comment(self, params: Dict[str, Any]) -> IntegrationResult:
        """Add comment to issue or PR."""
        required = ["owner", "repo", "issue_number", "body"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(
                f"Missing required parameters: {', '.join(missing)}",
                code="MISSING_PARAMS",
            )

        payload = {"body": params["body"]}
        endpoint = f"repos/{params['owner']}/{params['repo']}/issues/{params['issue_number']}/comments"
        response = await self._make_request("POST", endpoint, payload)

        return IntegrationResult(
            success=True,
            data={
                "comment_id": response.get("id"),
                "url": response.get("html_url"),
            },
        )

    async def _list_repos(self, params: Dict[str, Any]) -> IntegrationResult:
        """List repositories."""
        endpoint = f"users/{params['username']}/repos" if "username" in params else "user/repos"
        response = await self._make_request("GET", endpoint)

        repos = [
            {
                "name": r.get("name"),
                "full_name": r.get("full_name"),
                "private": r.get("private"),
                "url": r.get("html_url"),
            }
            for r in response
        ]

        return IntegrationResult(success=True, data={"repos": repos, "total": len(repos)})

    async def _get_repo(self, params: Dict[str, Any]) -> IntegrationResult:
        """Get repository details."""
        if "owner" not in params or "repo" not in params:
            raise IntegrationError(
                "Missing required parameters: 'owner', 'repo'",
                code="MISSING_PARAMS",
            )

        endpoint = f"repos/{params['owner']}/{params['repo']}"
        response = await self._make_request("GET", endpoint)

        return IntegrationResult(
            success=True,
            data={
                "name": response.get("name"),
                "full_name": response.get("full_name"),
                "description": response.get("description"),
                "stars": response.get("stargazers_count"),
                "forks": response.get("forks_count"),
                "url": response.get("html_url"),
            },
        )
