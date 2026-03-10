"""
Zendesk Integration - FULLY IMPLEMENTED

Real Zendesk API integration for support tickets.

Supported Actions:
- create_ticket: Create a new support ticket
- update_ticket: Update an existing ticket
- list_tickets: List all tickets
- get_ticket: Get specific ticket details
- add_comment: Add comment to a ticket

Authentication: API Token (email + token)
API Docs: https://developer.zendesk.com/api-reference/
"""

import aiohttp
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class ZendeskIntegration(BaseIntegration):
    """Zendesk support ticket integration with real API client."""

    @property
    def name(self) -> str:
        return "zendesk"

    @property
    def display_name(self) -> str:
        return "Zendesk"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return ["create_ticket", "update_ticket", "list_tickets", "get_ticket", "add_comment"]

    def _validate_credentials(self) -> None:
        """Validate Zendesk credentials."""
        super()._validate_credentials()
        if not self.auth_credentials.get("subdomain"):
            raise IntegrationError(
                "Zendesk requires 'subdomain' in credentials",
                code="MISSING_SUBDOMAIN",
            )
        if not self.auth_credentials.get("email") or not self.auth_credentials.get("api_token"):
            raise IntegrationError(
                "Zendesk requires 'email' and 'api_token'",
                code="MISSING_CREDENTIALS",
            )

    def _get_base_url(self) -> str:
        """Get base URL with subdomain."""
        subdomain = self.auth_credentials.get("subdomain")
        return f"https://{subdomain}.zendesk.com/api/v2"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with Basic Auth using email + /token + api_token."""
        email = self.auth_credentials.get("email")
        api_token = self.auth_credentials.get("api_token")
        credentials = f"{email}/token:{api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
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
        """Make HTTP request to Zendesk API."""
        url = f"{self._get_base_url()}{endpoint}"
        headers = self._get_headers()

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method, url=url, headers=headers, json=data, params=params
            ) as response:
                if response.status >= 400:
                    error_data = await response.json()
                    raise IntegrationError(
                        f"Zendesk API error: {error_data.get('error', 'Unknown error')}",
                        code=f"API_ERROR_{response.status}",
                    )
                return await response.json()

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        """Execute Zendesk action."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "create_ticket":
                result = await self._create_ticket(params)
            elif action == "update_ticket":
                result = await self._update_ticket(params)
            elif action == "list_tickets":
                result = await self._list_tickets(params)
            elif action == "get_ticket":
                result = await self._get_ticket(params)
            elif action == "add_comment":
                result = await self._add_comment(params)
            else:
                raise IntegrationError(f"Action {action} not implemented", code="NOT_IMPLEMENTED")

            result.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._log_execution(action, params, result)
            return result
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )

    async def test_connection(self) -> IntegrationResult:
        """Test Zendesk connection by listing tickets."""
        try:
            await self._make_request("GET", "/tickets.json", params={"page[size]": 1})
            return IntegrationResult(success=True, data={"status": "connected"})
        except IntegrationError as e:
            return IntegrationResult(success=False, error_message=e.message, error_code=e.code)

    async def _create_ticket(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new support ticket."""
        required = ["subject", "description"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        ticket_data = {
            "ticket": {
                "subject": params["subject"],
                "comment": {"body": params["description"]},
                "priority": params.get("priority", "normal"),
                "status": params.get("status", "new"),
            }
        }

        if "requester_email" in params:
            ticket_data["ticket"]["requester"] = {"email": params["requester_email"]}

        response = await self._make_request("POST", "/tickets.json", data=ticket_data)
        ticket = response.get("ticket", {})

        return IntegrationResult(
            success=True,
            data={
                "ticket_id": ticket.get("id"),
                "subject": ticket.get("subject"),
                "status": ticket.get("status"),
                "url": ticket.get("url"),
            },
        )

    async def _update_ticket(self, params: Dict[str, Any]) -> IntegrationResult:
        """Update an existing ticket."""
        if "ticket_id" not in params:
            raise IntegrationError("Missing required parameter: 'ticket_id'", code="MISSING_PARAMS")

        ticket_id = params["ticket_id"]
        update_data = {"ticket": {}}

        if "status" in params:
            update_data["ticket"]["status"] = params["status"]
        if "priority" in params:
            update_data["ticket"]["priority"] = params["priority"]
        if "assignee_id" in params:
            update_data["ticket"]["assignee_id"] = params["assignee_id"]

        response = await self._make_request("PUT", f"/tickets/{ticket_id}.json", data=update_data)
        ticket = response.get("ticket", {})

        return IntegrationResult(
            success=True,
            data={
                "ticket_id": ticket.get("id"),
                "status": ticket.get("status"),
                "updated_at": ticket.get("updated_at"),
            },
        )

    async def _list_tickets(self, params: Dict[str, Any]) -> IntegrationResult:
        """List all tickets."""
        query_params = {"page[size]": params.get("limit", 25)}

        if "status" in params:
            query_params["status"] = params["status"]

        response = await self._make_request("GET", "/tickets.json", params=query_params)
        tickets = response.get("tickets", [])

        return IntegrationResult(
            success=True,
            data={
                "tickets": [
                    {
                        "id": t.get("id"),
                        "subject": t.get("subject"),
                        "status": t.get("status"),
                        "priority": t.get("priority"),
                        "created_at": t.get("created_at"),
                    }
                    for t in tickets
                ],
                "total": len(tickets),
            },
        )

    async def _get_ticket(self, params: Dict[str, Any]) -> IntegrationResult:
        """Get specific ticket details."""
        if "ticket_id" not in params:
            raise IntegrationError("Missing required parameter: 'ticket_id'", code="MISSING_PARAMS")

        ticket_id = params["ticket_id"]
        response = await self._make_request("GET", f"/tickets/{ticket_id}.json")
        ticket = response.get("ticket", {})

        return IntegrationResult(
            success=True,
            data={
                "ticket_id": ticket.get("id"),
                "subject": ticket.get("subject"),
                "description": ticket.get("description"),
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "created_at": ticket.get("created_at"),
                "updated_at": ticket.get("updated_at"),
            },
        )

    async def _add_comment(self, params: Dict[str, Any]) -> IntegrationResult:
        """Add comment to a ticket."""
        required = ["ticket_id", "comment"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        ticket_id = params["ticket_id"]
        comment_data = {
            "ticket": {
                "comment": {
                    "body": params["comment"],
                    "public": params.get("public", True),
                }
            }
        }

        response = await self._make_request("PUT", f"/tickets/{ticket_id}.json", data=comment_data)
        ticket = response.get("ticket", {})

        return IntegrationResult(
            success=True,
            data={
                "ticket_id": ticket.get("id"),
                "comment_added": True,
                "updated_at": ticket.get("updated_at"),
            },
        )
