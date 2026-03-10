"""
GitHub Integration

Real GitHub integration using GitHub API and OAuth 2.0.
Supports creating issues, PRs, managing repositories, etc.

Authentication:
- Personal Access Token (API Key)
- OAuth 2.0 App authentication
"""

import os
import httpx
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging

from backend.shared.integrations.base import (
    OAuthIntegration,
    OAuthConfig,
    OAuthTokens,
    IntegrationResult,
    AuthMethod,
)

logger = logging.getLogger(__name__)

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"


class GitHubIntegration(OAuthIntegration):
    """
    GitHub integration with OAuth 2.0 or Personal Access Token.

    Supports:
    - create_issue: Create a new issue
    - create_pr: Create a pull request
    - list_repos: List repositories
    - get_repo: Get repository details
    - list_issues: List issues
    - list_prs: List pull requests
    - add_comment: Add comment to issue/PR
    - create_branch: Create a new branch
    - get_user: Get user information
    """

    name = "github"
    display_name = "GitHub"
    description = "Manage repositories, issues, and pull requests on GitHub"
    icon_url = "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
    documentation_url = "https://docs.github.com/en/rest"

    # OAuth configuration
    OAUTH_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
    OAUTH_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
    OAUTH_REDIRECT_URI = os.environ.get("GITHUB_REDIRECT_URI", "http://localhost:3000/integrations/github/callback")

    DEFAULT_SCOPES = [
        "repo",
        "read:user",
        "user:email",
    ]

    def get_auth_method(self) -> AuthMethod:
        # Support both OAuth and PAT
        if self.credentials.get("access_token"):
            return AuthMethod.OAUTH2
        return AuthMethod.BEARER_TOKEN

    def get_oauth_config(self) -> Optional[OAuthConfig]:
        """Return GitHub OAuth configuration."""
        return OAuthConfig(
            client_id=self.OAUTH_CLIENT_ID,
            client_secret=self.OAUTH_CLIENT_SECRET,
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scopes=self.DEFAULT_SCOPES,
            redirect_uri=self.OAUTH_REDIRECT_URI,
        )

    def get_token(self) -> Optional[str]:
        """Get the access token (OAuth or PAT)."""
        return (
            self.credentials.get("access_token")
            or self.credentials.get("personal_access_token")
            or self.credentials.get("api_key")
        )

    async def validate_credentials(self) -> bool:
        """Validate GitHub credentials by getting current user."""
        token = self.get_token()
        if not token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GITHUB_API_BASE}/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"GitHub credential validation failed: {e}")
            return False

    async def refresh_tokens(self) -> Optional[OAuthTokens]:
        """GitHub OAuth tokens don't expire, so no refresh needed."""
        # GitHub OAuth tokens don't have refresh tokens by default
        return None

    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Return list of available GitHub actions."""
        return [
            {
                "name": "create_issue",
                "display_name": "Create Issue",
                "description": "Create a new issue in a repository",
                "input_schema": {
                    "type": "object",
                    "required": ["owner", "repo", "title"],
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "Repository owner (user or org)",
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository name",
                        },
                        "title": {
                            "type": "string",
                            "description": "Issue title",
                        },
                        "body": {
                            "type": "string",
                            "description": "Issue body (markdown)",
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Labels to add",
                        },
                        "assignees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Usernames to assign",
                        },
                    },
                },
            },
            {
                "name": "create_pr",
                "display_name": "Create Pull Request",
                "description": "Create a new pull request",
                "input_schema": {
                    "type": "object",
                    "required": ["owner", "repo", "title", "head", "base"],
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "Repository owner",
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository name",
                        },
                        "title": {
                            "type": "string",
                            "description": "PR title",
                        },
                        "body": {
                            "type": "string",
                            "description": "PR description (markdown)",
                        },
                        "head": {
                            "type": "string",
                            "description": "Branch containing changes",
                        },
                        "base": {
                            "type": "string",
                            "description": "Branch to merge into",
                        },
                        "draft": {
                            "type": "boolean",
                            "description": "Create as draft PR",
                            "default": False,
                        },
                    },
                },
            },
            {
                "name": "list_repos",
                "display_name": "List Repositories",
                "description": "List repositories for authenticated user",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Type of repos (all, owner, public, private)",
                            "default": "all",
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort by (created, updated, pushed, full_name)",
                            "default": "updated",
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "Results per page",
                            "default": 30,
                        },
                    },
                },
            },
            {
                "name": "get_repo",
                "display_name": "Get Repository",
                "description": "Get repository details",
                "input_schema": {
                    "type": "object",
                    "required": ["owner", "repo"],
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "Repository owner",
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository name",
                        },
                    },
                },
            },
            {
                "name": "list_issues",
                "display_name": "List Issues",
                "description": "List issues in a repository",
                "input_schema": {
                    "type": "object",
                    "required": ["owner", "repo"],
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "Repository owner",
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository name",
                        },
                        "state": {
                            "type": "string",
                            "description": "Issue state (open, closed, all)",
                            "default": "open",
                        },
                        "labels": {
                            "type": "string",
                            "description": "Comma-separated label names",
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "Results per page",
                            "default": 30,
                        },
                    },
                },
            },
            {
                "name": "list_prs",
                "display_name": "List Pull Requests",
                "description": "List pull requests in a repository",
                "input_schema": {
                    "type": "object",
                    "required": ["owner", "repo"],
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "Repository owner",
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository name",
                        },
                        "state": {
                            "type": "string",
                            "description": "PR state (open, closed, all)",
                            "default": "open",
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "Results per page",
                            "default": 30,
                        },
                    },
                },
            },
            {
                "name": "add_comment",
                "display_name": "Add Comment",
                "description": "Add a comment to an issue or PR",
                "input_schema": {
                    "type": "object",
                    "required": ["owner", "repo", "issue_number", "body"],
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "Repository owner",
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository name",
                        },
                        "issue_number": {
                            "type": "integer",
                            "description": "Issue or PR number",
                        },
                        "body": {
                            "type": "string",
                            "description": "Comment body (markdown)",
                        },
                    },
                },
            },
            {
                "name": "get_user",
                "display_name": "Get User",
                "description": "Get authenticated user information",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "test_connection",
                "display_name": "Test Connection",
                "description": "Test the GitHub connection",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute a GitHub action."""
        start_time = datetime.utcnow()

        token = self.get_token()
        if not token:
            return IntegrationResult(
                success=False,
                error_message="No token available. Please authenticate with GitHub.",
                error_code="NO_TOKEN",
            )

        try:
            # Route to appropriate action handler
            if action_name == "create_issue":
                result = await self._create_issue(token, parameters)
            elif action_name == "create_pr":
                result = await self._create_pr(token, parameters)
            elif action_name == "list_repos":
                result = await self._list_repos(token, parameters)
            elif action_name == "get_repo":
                result = await self._get_repo(token, parameters)
            elif action_name == "list_issues":
                result = await self._list_issues(token, parameters)
            elif action_name == "list_prs":
                result = await self._list_prs(token, parameters)
            elif action_name == "add_comment":
                result = await self._add_comment(token, parameters)
            elif action_name == "get_user":
                result = await self._get_user(token)
            elif action_name == "test_connection":
                result = await self.test_connection()
            else:
                result = IntegrationResult(
                    success=False,
                    error_message=f"Unknown action: {action_name}",
                    error_code="UNKNOWN_ACTION",
                )

            # Calculate duration
            end_time = datetime.utcnow()
            result.duration_ms = (end_time - start_time).total_seconds() * 1000
            return result

        except Exception as e:
            logger.error(f"GitHub action {action_name} failed: {e}")
            end_time = datetime.utcnow()
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                duration_ms=(end_time - start_time).total_seconds() * 1000,
            )

    def _get_headers(self, token: str) -> Dict[str, str]:
        """Get common headers for GitHub API requests."""
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _create_issue(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new issue."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{params['owner']}/{params['repo']}/issues",
                headers=self._get_headers(token),
                json={
                    "title": params["title"],
                    "body": params.get("body"),
                    "labels": params.get("labels", []),
                    "assignees": params.get("assignees", []),
                },
            )

            if response.status_code == 201:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "issue_number": data.get("number"),
                        "issue_url": data.get("html_url"),
                        "title": data.get("title"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _create_pr(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new pull request."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{params['owner']}/{params['repo']}/pulls",
                headers=self._get_headers(token),
                json={
                    "title": params["title"],
                    "body": params.get("body"),
                    "head": params["head"],
                    "base": params["base"],
                    "draft": params.get("draft", False),
                },
            )

            if response.status_code == 201:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "pr_number": data.get("number"),
                        "pr_url": data.get("html_url"),
                        "title": data.get("title"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _list_repos(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """List repositories."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user/repos",
                headers=self._get_headers(token),
                params={
                    "type": params.get("type", "all"),
                    "sort": params.get("sort", "updated"),
                    "per_page": params.get("per_page", 30),
                },
            )

            if response.status_code == 200:
                data = response.json()
                repos = [
                    {
                        "id": repo["id"],
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "private": repo["private"],
                        "html_url": repo["html_url"],
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "stargazers_count": repo.get("stargazers_count", 0),
                    }
                    for repo in data
                ]
                return IntegrationResult(
                    success=True,
                    data={"repos": repos, "count": len(repos)},
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _get_repo(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Get repository details."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{params['owner']}/{params['repo']}",
                headers=self._get_headers(token),
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "id": data["id"],
                        "name": data["name"],
                        "full_name": data["full_name"],
                        "description": data.get("description"),
                        "private": data["private"],
                        "html_url": data["html_url"],
                        "language": data.get("language"),
                        "default_branch": data.get("default_branch"),
                        "stargazers_count": data.get("stargazers_count", 0),
                        "forks_count": data.get("forks_count", 0),
                        "open_issues_count": data.get("open_issues_count", 0),
                    },
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _list_issues(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """List issues in a repository."""
        query_params = {
            "state": params.get("state", "open"),
            "per_page": params.get("per_page", 30),
        }
        if params.get("labels"):
            query_params["labels"] = params["labels"]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{params['owner']}/{params['repo']}/issues",
                headers=self._get_headers(token),
                params=query_params,
            )

            if response.status_code == 200:
                data = response.json()
                issues = [
                    {
                        "number": issue["number"],
                        "title": issue["title"],
                        "state": issue["state"],
                        "html_url": issue["html_url"],
                        "user": issue["user"]["login"],
                        "labels": [l["name"] for l in issue.get("labels", [])],
                        "created_at": issue["created_at"],
                    }
                    for issue in data
                    if "pull_request" not in issue  # Exclude PRs
                ]
                return IntegrationResult(
                    success=True,
                    data={"issues": issues, "count": len(issues)},
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _list_prs(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """List pull requests in a repository."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{params['owner']}/{params['repo']}/pulls",
                headers=self._get_headers(token),
                params={
                    "state": params.get("state", "open"),
                    "per_page": params.get("per_page", 30),
                },
            )

            if response.status_code == 200:
                data = response.json()
                prs = [
                    {
                        "number": pr["number"],
                        "title": pr["title"],
                        "state": pr["state"],
                        "html_url": pr["html_url"],
                        "user": pr["user"]["login"],
                        "head": pr["head"]["ref"],
                        "base": pr["base"]["ref"],
                        "created_at": pr["created_at"],
                        "draft": pr.get("draft", False),
                    }
                    for pr in data
                ]
                return IntegrationResult(
                    success=True,
                    data={"pull_requests": prs, "count": len(prs)},
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _add_comment(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Add a comment to an issue or PR."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{params['owner']}/{params['repo']}/issues/{params['issue_number']}/comments",
                headers=self._get_headers(token),
                json={"body": params["body"]},
            )

            if response.status_code == 201:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "comment_id": data.get("id"),
                        "comment_url": data.get("html_url"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )

    async def _get_user(self, token: str) -> IntegrationResult:
        """Get authenticated user information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers=self._get_headers(token),
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "id": data["id"],
                        "login": data["login"],
                        "name": data.get("name"),
                        "email": data.get("email"),
                        "avatar_url": data.get("avatar_url"),
                        "html_url": data.get("html_url"),
                        "public_repos": data.get("public_repos", 0),
                    },
                    raw_response=data,
                )
            else:
                data = response.json()
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )


# OAuth flow helper functions
def get_github_oauth_url(state: str, scopes: Optional[List[str]] = None) -> str:
    """Generate the GitHub OAuth authorization URL."""
    config = GitHubIntegration({}, {}).get_oauth_config()
    if not config:
        raise ValueError("GitHub OAuth not configured")

    scope_str = " ".join(scopes or config.scopes)
    return (
        f"{config.authorize_url}"
        f"?client_id={config.client_id}"
        f"&redirect_uri={config.redirect_uri}"
        f"&scope={scope_str}"
        f"&state={state}"
    )


async def exchange_github_code(code: str) -> Optional[Dict[str, Any]]:
    """Exchange OAuth code for tokens."""
    config = GitHubIntegration({}, {}).get_oauth_config()
    if not config:
        return None

    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.token_url,
            headers={"Accept": "application/json"},
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": config.redirect_uri,
            },
        )
        data = response.json()

        if "access_token" in data:
            return {
                "access_token": data["access_token"],
                "token_type": data.get("token_type", "bearer"),
                "scope": data.get("scope"),
            }
        else:
            logger.error(f"GitHub OAuth exchange failed: {data.get('error')}")
            return None
