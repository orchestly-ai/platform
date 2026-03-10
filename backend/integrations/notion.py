"""
Notion Integration - FULLY IMPLEMENTED

Real Notion API integration for workspace and content management.

Supported Actions:
- create_page: Create a new page in a database or as a child of another page
- get_page: Get page properties and content
- update_page: Update page properties
- search: Search across the workspace
- create_database: Create a new database
- query_database: Query a database with filters
- append_blocks: Append content blocks to a page
- get_block_children: Get child blocks of a page or block

Authentication: Integration Token (Bearer)
API Docs: https://developers.notion.com/reference
"""

import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class NotionIntegration(BaseIntegration):
    """Notion integration with official API."""

    API_BASE_URL = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"

    @property
    def name(self) -> str:
        return "notion"

    @property
    def display_name(self) -> str:
        return "Notion"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "create_page",
            "get_page",
            "update_page",
            "search",
            "create_database",
            "query_database",
            "append_blocks",
            "get_block_children",
        ]

    def _validate_credentials(self) -> None:
        """Validate Notion credentials."""
        super()._validate_credentials()

        if "integration_token" not in self.auth_credentials and "api_key" not in self.auth_credentials:
            raise IntegrationError(
                "Notion requires 'integration_token' or 'api_key'",
                code="MISSING_CREDENTIALS",
            )

    def _get_token(self) -> str:
        """Get the integration token."""
        return self.auth_credentials.get("integration_token") or self.auth_credentials.get("api_key")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
            "Notion-Version": self.API_VERSION,
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Notion API.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., '/pages')
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
                    kwargs["json"] = data
                if params:
                    kwargs["params"] = params

                async with session.request(**kwargs) as response:
                    response_data = await response.json()

                    if response.status >= 400:
                        error_msg = response_data.get("message", "Unknown error")
                        error_code = response_data.get("code", "NOTION_ERROR")
                        raise IntegrationError(
                            f"Notion API error: {error_msg}",
                            code=error_code,
                            status_code=response.status,
                            details=response_data,
                        )

                    return response_data

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
        """Execute Notion action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "create_page":
                result = await self._create_page(params)
            elif action == "get_page":
                result = await self._get_page(params)
            elif action == "update_page":
                result = await self._update_page(params)
            elif action == "search":
                result = await self._search(params)
            elif action == "create_database":
                result = await self._create_database(params)
            elif action == "query_database":
                result = await self._query_database(params)
            elif action == "append_blocks":
                result = await self._append_blocks(params)
            elif action == "get_block_children":
                result = await self._get_block_children(params)
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
        """Test Notion connection using /users/me endpoint."""
        try:
            response = await self._make_request("GET", "/users/me")
            return IntegrationResult(
                success=True,
                data={
                    "user_id": response.get("id"),
                    "name": response.get("name"),
                    "type": response.get("type"),
                    "avatar_url": response.get("avatar_url"),
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

    async def _create_page(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a new page.

        Required params:
            parent_id: Parent page ID or database ID
            parent_type: 'page_id' or 'database_id'

        Optional params:
            title: Page title (for database pages, use properties)
            properties: Dict of properties (for database pages)
            children: List of block content
            icon: Emoji or external icon
            cover: External cover image URL
        """
        parent_id = params.get("parent_id")
        parent_type = params.get("parent_type", "page_id")

        if not parent_id:
            raise IntegrationError(
                "Missing required parameter: 'parent_id'",
                code="MISSING_PARAMS",
            )

        payload = {
            "parent": {parent_type: parent_id}
        }

        # Handle title for page parents
        if "title" in params and parent_type == "page_id":
            payload["properties"] = {
                "title": {
                    "title": [{"text": {"content": params["title"]}}]
                }
            }

        # Handle properties for database pages
        if "properties" in params:
            payload["properties"] = params["properties"]

        if "children" in params:
            payload["children"] = params["children"]
        if "icon" in params:
            if isinstance(params["icon"], str) and len(params["icon"]) <= 2:
                payload["icon"] = {"type": "emoji", "emoji": params["icon"]}
            else:
                payload["icon"] = params["icon"]
        if "cover" in params:
            payload["cover"] = {"type": "external", "external": {"url": params["cover"]}}

        response = await self._make_request("POST", "/pages", payload)

        return IntegrationResult(
            success=True,
            data={
                "page_id": response.get("id"),
                "url": response.get("url"),
                "created_time": response.get("created_time"),
            },
        )

    async def _get_page(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get page properties.

        Required params:
            page_id: Page ID
        """
        page_id = params.get("page_id")
        if not page_id:
            raise IntegrationError("Missing required parameter: 'page_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/pages/{page_id}")

        return IntegrationResult(
            success=True,
            data={
                "page_id": response.get("id"),
                "url": response.get("url"),
                "created_time": response.get("created_time"),
                "last_edited_time": response.get("last_edited_time"),
                "properties": response.get("properties", {}),
                "parent": response.get("parent"),
                "archived": response.get("archived"),
            },
        )

    async def _update_page(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update page properties.

        Required params:
            page_id: Page ID

        Optional params:
            properties: Dict of properties to update
            archived: Boolean to archive/unarchive
            icon: New icon
            cover: New cover
        """
        page_id = params.get("page_id")
        if not page_id:
            raise IntegrationError("Missing required parameter: 'page_id'", code="MISSING_PARAMS")

        payload = {}

        if "properties" in params:
            payload["properties"] = params["properties"]
        if "archived" in params:
            payload["archived"] = params["archived"]
        if "icon" in params:
            if isinstance(params["icon"], str) and len(params["icon"]) <= 2:
                payload["icon"] = {"type": "emoji", "emoji": params["icon"]}
            else:
                payload["icon"] = params["icon"]
        if "cover" in params:
            payload["cover"] = {"type": "external", "external": {"url": params["cover"]}}

        if not payload:
            raise IntegrationError("No properties to update", code="MISSING_PARAMS")

        response = await self._make_request("PATCH", f"/pages/{page_id}", payload)

        return IntegrationResult(
            success=True,
            data={
                "page_id": response.get("id"),
                "last_edited_time": response.get("last_edited_time"),
                "updated": True,
            },
        )

    async def _search(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Search across workspace.

        Optional params:
            query: Search query string
            filter: Object filter (e.g., {"property": "object", "value": "page"})
            sort: Sort direction
            page_size: Number of results (default: 100)
            start_cursor: Pagination cursor
        """
        payload = {}

        if "query" in params:
            payload["query"] = params["query"]
        if "filter" in params:
            payload["filter"] = params["filter"]
        if "sort" in params:
            payload["sort"] = params["sort"]
        if "page_size" in params:
            payload["page_size"] = min(params["page_size"], 100)
        if "start_cursor" in params:
            payload["start_cursor"] = params["start_cursor"]

        response = await self._make_request("POST", "/search", payload)

        results = [
            {
                "id": item.get("id"),
                "object": item.get("object"),
                "url": item.get("url"),
                "title": self._extract_title(item),
            }
            for item in response.get("results", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "results": results,
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor"),
            },
        )

    async def _create_database(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a new database.

        Required params:
            parent_id: Parent page ID
            title: Database title

        Optional params:
            properties: Dict of property schema definitions
            icon: Database icon
        """
        parent_id = params.get("parent_id")
        title = params.get("title")

        if not parent_id or not title:
            raise IntegrationError(
                "Missing required parameters: 'parent_id' and 'title'",
                code="MISSING_PARAMS",
            )

        payload = {
            "parent": {"page_id": parent_id},
            "title": [{"text": {"content": title}}],
            "properties": params.get("properties", {
                "Name": {"title": {}}
            }),
        }

        if "icon" in params:
            if isinstance(params["icon"], str) and len(params["icon"]) <= 2:
                payload["icon"] = {"type": "emoji", "emoji": params["icon"]}
            else:
                payload["icon"] = params["icon"]

        response = await self._make_request("POST", "/databases", payload)

        return IntegrationResult(
            success=True,
            data={
                "database_id": response.get("id"),
                "url": response.get("url"),
                "created_time": response.get("created_time"),
            },
        )

    async def _query_database(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Query a database with optional filters.

        Required params:
            database_id: Database ID

        Optional params:
            filter: Filter conditions
            sorts: Sort conditions
            page_size: Number of results (default: 100)
            start_cursor: Pagination cursor
        """
        database_id = params.get("database_id")
        if not database_id:
            raise IntegrationError("Missing required parameter: 'database_id'", code="MISSING_PARAMS")

        payload = {}

        if "filter" in params:
            payload["filter"] = params["filter"]
        if "sorts" in params:
            payload["sorts"] = params["sorts"]
        if "page_size" in params:
            payload["page_size"] = min(params["page_size"], 100)
        if "start_cursor" in params:
            payload["start_cursor"] = params["start_cursor"]

        response = await self._make_request("POST", f"/databases/{database_id}/query", payload)

        results = [
            {
                "id": item.get("id"),
                "url": item.get("url"),
                "properties": item.get("properties", {}),
                "created_time": item.get("created_time"),
            }
            for item in response.get("results", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "results": results,
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor"),
            },
        )

    async def _append_blocks(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Append blocks to a page.

        Required params:
            block_id: Parent block/page ID
            children: List of block objects

        Block types: paragraph, heading_1, heading_2, heading_3,
                    bulleted_list_item, numbered_list_item, to_do,
                    toggle, code, quote, callout, divider, etc.
        """
        block_id = params.get("block_id")
        children = params.get("children")

        if not block_id or not children:
            raise IntegrationError(
                "Missing required parameters: 'block_id' and 'children'",
                code="MISSING_PARAMS",
            )

        payload = {"children": children}

        response = await self._make_request("PATCH", f"/blocks/{block_id}/children", payload)

        return IntegrationResult(
            success=True,
            data={
                "block_id": block_id,
                "blocks_added": len(response.get("results", [])),
            },
        )

    async def _get_block_children(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get child blocks of a page or block.

        Required params:
            block_id: Block or page ID

        Optional params:
            page_size: Number of results (default: 100)
            start_cursor: Pagination cursor
        """
        block_id = params.get("block_id")
        if not block_id:
            raise IntegrationError("Missing required parameter: 'block_id'", code="MISSING_PARAMS")

        query_params = {}
        if "page_size" in params:
            query_params["page_size"] = min(params["page_size"], 100)
        if "start_cursor" in params:
            query_params["start_cursor"] = params["start_cursor"]

        response = await self._make_request(
            "GET",
            f"/blocks/{block_id}/children",
            params=query_params if query_params else None,
        )

        blocks = [
            {
                "id": block.get("id"),
                "type": block.get("type"),
                "has_children": block.get("has_children", False),
                "content": block.get(block.get("type"), {}),
            }
            for block in response.get("results", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "blocks": blocks,
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor"),
            },
        )

    def _extract_title(self, item: Dict) -> Optional[str]:
        """Extract title from a Notion object."""
        if item.get("object") == "page":
            props = item.get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title":
                    title_arr = prop.get("title", [])
                    if title_arr:
                        return title_arr[0].get("plain_text", "")
        elif item.get("object") == "database":
            title_arr = item.get("title", [])
            if title_arr:
                return title_arr[0].get("plain_text", "")
        return None
