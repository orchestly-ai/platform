"""
Asana Integration - FULLY IMPLEMENTED

Real Asana API integration for task and project management.

Supported Actions:
- create_task: Create new task
- get_task: Get task details
- update_task: Update task fields
- complete_task: Mark task as complete
- add_comment: Add comment/story to task
- list_projects: List workspace projects
- list_tasks: List tasks in project/section
- assign_task: Assign task to user

Authentication: OAuth 2.0 or Personal Access Token
API Docs: https://developers.asana.com/reference/rest-api-reference
"""

import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class AsanaIntegration(BaseIntegration):
    """Asana integration with REST API."""

    API_BASE_URL = "https://app.asana.com/api/1.0"

    @property
    def name(self) -> str:
        return "asana"

    @property
    def display_name(self) -> str:
        return "Asana"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.OAUTH2

    @property
    def supported_actions(self) -> List[str]:
        return [
            "create_task",
            "get_task",
            "update_task",
            "complete_task",
            "add_comment",
            "list_projects",
            "list_tasks",
            "assign_task",
        ]

    def _validate_credentials(self) -> None:
        """Validate Asana credentials."""
        super()._validate_credentials()

        token = self.auth_credentials.get("access_token") or self.auth_credentials.get("personal_access_token")
        if not token:
            raise IntegrationError(
                "Asana requires 'access_token' or 'personal_access_token'",
                code="MISSING_TOKEN",
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Asana API."""
        token = self.auth_credentials.get("access_token") or self.auth_credentials.get("personal_access_token")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Asana API.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., '/tasks')
            data: Request payload
            params: Query parameters

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
        url = f"{self.API_BASE_URL}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {
                    "method": method,
                    "url": url,
                    "headers": self._get_headers(),
                }
                if data:
                    kwargs["json"] = {"data": data}
                if params:
                    kwargs["params"] = params

                async with session.request(**kwargs) as response:
                    if response.status == 204:
                        return {"success": True}

                    response_data = await response.json()

                    if response.status >= 400:
                        errors = response_data.get("errors", [])
                        error_msg = "; ".join([e.get("message", str(e)) for e in errors])
                        raise IntegrationError(
                            f"Asana API error: {error_msg}",
                            code="ASANA_ERROR",
                            status_code=response.status,
                            details=response_data,
                        )

                    return response_data.get("data", response_data)

        except aiohttp.ClientError as e:
            raise IntegrationError(
                f"HTTP request failed: {str(e)}",
                code="HTTP_ERROR",
            )
        except Exception as e:
            if isinstance(e, IntegrationError):
                raise
            raise IntegrationError(
                f"Unexpected error: {str(e)}",
                code="UNKNOWN_ERROR",
            )

    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
    ) -> IntegrationResult:
        """Execute Asana action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "create_task":
                result = await self._create_task(params)
            elif action == "get_task":
                result = await self._get_task(params)
            elif action == "update_task":
                result = await self._update_task(params)
            elif action == "complete_task":
                result = await self._complete_task(params)
            elif action == "add_comment":
                result = await self._add_comment(params)
            elif action == "list_projects":
                result = await self._list_projects(params)
            elif action == "list_tasks":
                result = await self._list_tasks(params)
            elif action == "assign_task":
                result = await self._assign_task(params)
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
        """Test Asana connection using /users/me endpoint."""
        try:
            response = await self._make_request("GET", "/users/me")
            return IntegrationResult(
                success=True,
                data={
                    "user_id": response.get("gid"),
                    "name": response.get("name"),
                    "email": response.get("email"),
                    "workspaces": [
                        {"gid": w.get("gid"), "name": w.get("name")}
                        for w in response.get("workspaces", [])
                    ],
                },
            )
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )

    # ========================================================================
    # Action Implementations
    # ========================================================================

    async def _create_task(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create new Asana task.

        Required params:
            name: Task name
            AND one of:
                project_gid: Project GID to add task to
                workspace_gid: Workspace GID (for personal tasks)

        Optional params:
            notes: Task description
            due_on: Due date (YYYY-MM-DD)
            due_at: Due datetime (ISO 8601)
            assignee: Assignee GID or 'me'
            followers: List of follower GIDs
            tags: List of tag GIDs
            parent: Parent task GID (for subtasks)
            custom_fields: Dict of custom field GIDs to values
        """
        name = params.get("name")
        project_gid = params.get("project_gid")
        workspace_gid = params.get("workspace_gid")

        if not name:
            raise IntegrationError("Missing required parameter: 'name'", code="MISSING_PARAMS")

        if not project_gid and not workspace_gid:
            raise IntegrationError(
                "Missing required parameter: 'project_gid' or 'workspace_gid'",
                code="MISSING_PARAMS",
            )

        data = {"name": name}

        if project_gid:
            data["projects"] = [project_gid]
        if workspace_gid:
            data["workspace"] = workspace_gid

        # Optional fields
        if "notes" in params:
            data["notes"] = params["notes"]
        if "due_on" in params:
            data["due_on"] = params["due_on"]
        if "due_at" in params:
            data["due_at"] = params["due_at"]
        if "assignee" in params:
            data["assignee"] = params["assignee"]
        if "followers" in params:
            data["followers"] = params["followers"]
        if "tags" in params:
            data["tags"] = params["tags"]
        if "parent" in params:
            data["parent"] = params["parent"]
        if "custom_fields" in params:
            data["custom_fields"] = params["custom_fields"]

        response = await self._make_request("POST", "/tasks", data)

        return IntegrationResult(
            success=True,
            data={
                "task_gid": response.get("gid"),
                "name": response.get("name"),
                "permalink_url": response.get("permalink_url"),
            },
        )

    async def _get_task(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get task details.

        Required params:
            task_gid: Task GID

        Optional params:
            opt_fields: List of fields to return
        """
        task_gid = params.get("task_gid")
        if not task_gid:
            raise IntegrationError("Missing required parameter: 'task_gid'", code="MISSING_PARAMS")

        query_params = {}
        if "opt_fields" in params:
            query_params["opt_fields"] = ",".join(params["opt_fields"])

        response = await self._make_request(
            "GET",
            f"/tasks/{task_gid}",
            params=query_params if query_params else None,
        )

        return IntegrationResult(
            success=True,
            data={
                "task_gid": response.get("gid"),
                "name": response.get("name"),
                "notes": response.get("notes"),
                "completed": response.get("completed"),
                "due_on": response.get("due_on"),
                "due_at": response.get("due_at"),
                "assignee": response.get("assignee", {}).get("name") if response.get("assignee") else None,
                "projects": [p.get("name") for p in response.get("projects", [])],
                "tags": [t.get("name") for t in response.get("tags", [])],
                "permalink_url": response.get("permalink_url"),
            },
        )

    async def _update_task(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update task fields.

        Required params:
            task_gid: Task GID

        Optional params:
            name: New name
            notes: New description
            due_on: New due date
            due_at: New due datetime
            assignee: New assignee GID
            completed: Boolean to mark complete/incomplete
        """
        task_gid = params.get("task_gid")
        if not task_gid:
            raise IntegrationError("Missing required parameter: 'task_gid'", code="MISSING_PARAMS")

        data = {}
        for field in ["name", "notes", "due_on", "due_at", "assignee", "completed"]:
            if field in params:
                data[field] = params[field]

        if not data:
            raise IntegrationError("No fields to update", code="MISSING_PARAMS")

        response = await self._make_request("PUT", f"/tasks/{task_gid}", data)

        return IntegrationResult(
            success=True,
            data={
                "task_gid": response.get("gid"),
                "name": response.get("name"),
                "updated": True,
            },
        )

    async def _complete_task(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Mark task as complete.

        Required params:
            task_gid: Task GID

        Optional params:
            completed: Boolean (default: True)
        """
        task_gid = params.get("task_gid")
        if not task_gid:
            raise IntegrationError("Missing required parameter: 'task_gid'", code="MISSING_PARAMS")

        completed = params.get("completed", True)
        response = await self._make_request("PUT", f"/tasks/{task_gid}", {"completed": completed})

        return IntegrationResult(
            success=True,
            data={
                "task_gid": response.get("gid"),
                "completed": response.get("completed"),
            },
        )

    async def _add_comment(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Add comment/story to task.

        Required params:
            task_gid: Task GID
            text: Comment text
        """
        task_gid = params.get("task_gid")
        text = params.get("text")

        if not task_gid or not text:
            raise IntegrationError(
                "Missing required parameters: 'task_gid' and 'text'",
                code="MISSING_PARAMS",
            )

        response = await self._make_request(
            "POST",
            f"/tasks/{task_gid}/stories",
            {"text": text},
        )

        return IntegrationResult(
            success=True,
            data={
                "story_gid": response.get("gid"),
                "task_gid": task_gid,
                "created_at": response.get("created_at"),
            },
        )

    async def _list_projects(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List projects in workspace.

        Required params:
            workspace_gid: Workspace GID

        Optional params:
            archived: Include archived projects (default: False)
            limit: Max results (default: 50)
            offset: Pagination token
        """
        workspace_gid = params.get("workspace_gid")
        if not workspace_gid:
            raise IntegrationError("Missing required parameter: 'workspace_gid'", code="MISSING_PARAMS")

        query_params = {
            "workspace": workspace_gid,
            "limit": params.get("limit", 50),
        }

        if "archived" in params:
            query_params["archived"] = str(params["archived"]).lower()
        if "offset" in params:
            query_params["offset"] = params["offset"]

        response = await self._make_request("GET", "/projects", params=query_params)

        # Handle list response
        projects = response if isinstance(response, list) else response.get("data", []) if isinstance(response, dict) else []

        project_list = [
            {
                "project_gid": proj.get("gid"),
                "name": proj.get("name"),
            }
            for proj in projects
        ]

        return IntegrationResult(
            success=True,
            data={
                "projects": project_list,
                "total": len(project_list),
            },
        )

    async def _list_tasks(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List tasks in project or section.

        Required params:
            project_gid: Project GID OR
            section_gid: Section GID

        Optional params:
            completed_since: ISO datetime to filter by completion
            limit: Max results (default: 50)
            offset: Pagination token
        """
        project_gid = params.get("project_gid")
        section_gid = params.get("section_gid")

        if not project_gid and not section_gid:
            raise IntegrationError(
                "Missing required parameter: 'project_gid' or 'section_gid'",
                code="MISSING_PARAMS",
            )

        query_params = {"limit": params.get("limit", 50)}

        if project_gid:
            query_params["project"] = project_gid
        if section_gid:
            query_params["section"] = section_gid
        if "completed_since" in params:
            query_params["completed_since"] = params["completed_since"]
        if "offset" in params:
            query_params["offset"] = params["offset"]

        response = await self._make_request("GET", "/tasks", params=query_params)

        # Handle list response
        tasks = response if isinstance(response, list) else response.get("data", []) if isinstance(response, dict) else []

        task_list = [
            {
                "task_gid": task.get("gid"),
                "name": task.get("name"),
            }
            for task in tasks
        ]

        return IntegrationResult(
            success=True,
            data={
                "tasks": task_list,
                "total": len(task_list),
            },
        )

    async def _assign_task(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Assign task to user.

        Required params:
            task_gid: Task GID
            assignee: User GID or 'me' or null to unassign
        """
        task_gid = params.get("task_gid")

        if not task_gid:
            raise IntegrationError("Missing required parameter: 'task_gid'", code="MISSING_PARAMS")

        if "assignee" not in params:
            raise IntegrationError("Missing required parameter: 'assignee'", code="MISSING_PARAMS")

        assignee = params["assignee"]
        response = await self._make_request("PUT", f"/tasks/{task_gid}", {"assignee": assignee})

        return IntegrationResult(
            success=True,
            data={
                "task_gid": response.get("gid"),
                "assignee": response.get("assignee", {}).get("gid") if response.get("assignee") else None,
                "assigned": True,
            },
        )
