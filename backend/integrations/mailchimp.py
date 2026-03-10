"""
Mailchimp Integration - FULLY IMPLEMENTED

Real Mailchimp Marketing API integration for email marketing.

Supported Actions:
- list_audiences: List audiences (lists)
- get_audience: Get audience by ID
- list_members: List members in audience
- get_member: Get member by email hash
- add_member: Add member to audience
- update_member: Update member info
- list_campaigns: List campaigns
- get_campaign: Get campaign by ID
- create_campaign: Create new campaign
- send_campaign: Send a campaign

Authentication: API Key (Basic Auth with any username)
API Docs: https://mailchimp.com/developer/marketing/api/
"""

import aiohttp
import base64
import hashlib
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class MailchimpIntegration(BaseIntegration):
    """Mailchimp integration with Marketing API."""

    @property
    def name(self) -> str:
        return "mailchimp"

    @property
    def display_name(self) -> str:
        return "Mailchimp"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "list_audiences",
            "get_audience",
            "list_members",
            "get_member",
            "add_member",
            "update_member",
            "list_campaigns",
            "get_campaign",
            "create_campaign",
            "send_campaign",
        ]

    def _validate_credentials(self) -> None:
        """Validate Mailchimp credentials."""
        super()._validate_credentials()

        if "api_key" not in self.auth_credentials:
            raise IntegrationError(
                "Mailchimp requires 'api_key'",
                code="MISSING_CREDENTIALS",
            )

        # API key format: <key>-<dc> (e.g., abc123-us21)
        api_key = self.auth_credentials["api_key"]
        if "-" not in api_key:
            raise IntegrationError(
                "Mailchimp API key must include datacenter suffix (e.g., key-us21)",
                code="INVALID_CREDENTIALS",
            )

    def _get_datacenter(self) -> str:
        """Extract datacenter from API key."""
        api_key = self.auth_credentials["api_key"]
        return api_key.split("-")[-1]

    def _get_base_url(self) -> str:
        """Get Mailchimp API base URL."""
        dc = self._get_datacenter()
        return f"https://{dc}.api.mailchimp.com/3.0"

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        # Mailchimp uses HTTP Basic Auth with any username and API key as password
        api_key = self.auth_credentials["api_key"]
        credentials = f"anystring:{api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _get_subscriber_hash(email: str) -> str:
        """Get MD5 hash of lowercase email for member operations."""
        return hashlib.md5(email.lower().encode()).hexdigest()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Mailchimp API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint (e.g., "/lists")
            data: Request body for POST/PUT/PATCH
            params: Query parameters

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
        url = f"{self._get_base_url()}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {
                    "headers": self._get_headers(),
                }
                if params:
                    kwargs["params"] = params
                if data:
                    kwargs["json"] = data

                async with session.request(method, url, **kwargs) as response:
                    response_text = await response.text()

                    if response.status >= 400:
                        try:
                            error_data = json.loads(response_text)
                            error_msg = error_data.get("detail", error_data.get("title", response_text))
                        except json.JSONDecodeError:
                            error_msg = response_text

                        raise IntegrationError(
                            f"Mailchimp API error: {error_msg}",
                            code="MAILCHIMP_ERROR",
                            status_code=response.status,
                            details={"response": response_text},
                        )

                    if response_text:
                        return json.loads(response_text)
                    return {}

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
        """Execute Mailchimp action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "list_audiences":
                result = await self._list_audiences(params)
            elif action == "get_audience":
                result = await self._get_audience(params)
            elif action == "list_members":
                result = await self._list_members(params)
            elif action == "get_member":
                result = await self._get_member(params)
            elif action == "add_member":
                result = await self._add_member(params)
            elif action == "update_member":
                result = await self._update_member(params)
            elif action == "list_campaigns":
                result = await self._list_campaigns(params)
            elif action == "get_campaign":
                result = await self._get_campaign(params)
            elif action == "create_campaign":
                result = await self._create_campaign(params)
            elif action == "send_campaign":
                result = await self._send_campaign(params)
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
        """Test Mailchimp connection by fetching account info."""
        try:
            response = await self._make_request("GET", "/")
            return IntegrationResult(
                success=True,
                data={
                    "connected": True,
                    "account_id": response.get("account_id"),
                    "account_name": response.get("account_name"),
                    "email": response.get("email"),
                },
            )
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )

    # ========================================================================
    # Audience Actions
    # ========================================================================

    async def _list_audiences(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List audiences (lists).

        Optional params:
            count: Number of records to return (default: 10, max: 1000)
            offset: Number of records to skip
        """
        query_params = {}

        if "count" in params:
            query_params["count"] = min(params["count"], 1000)
        if "offset" in params:
            query_params["offset"] = params["offset"]

        response = await self._make_request("GET", "/lists", params=query_params)

        audiences = response.get("lists", [])

        return IntegrationResult(
            success=True,
            data={
                "audiences": audiences,
                "count": len(audiences),
                "total_items": response.get("total_items"),
            },
        )

    async def _get_audience(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get audience by ID.

        Required params:
            list_id: Audience/list ID
        """
        list_id = params.get("list_id")
        if not list_id:
            raise IntegrationError("Missing required parameter: 'list_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/lists/{list_id}")

        return IntegrationResult(
            success=True,
            data={
                "audience": response,
            },
        )

    # ========================================================================
    # Member Actions
    # ========================================================================

    async def _list_members(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List members in audience.

        Required params:
            list_id: Audience/list ID

        Optional params:
            count: Number of records (default: 10, max: 1000)
            offset: Number of records to skip
            status: Filter by status (subscribed, unsubscribed, cleaned, pending, transactional, archived)
        """
        list_id = params.get("list_id")
        if not list_id:
            raise IntegrationError("Missing required parameter: 'list_id'", code="MISSING_PARAMS")

        query_params = {}

        if "count" in params:
            query_params["count"] = min(params["count"], 1000)
        if "offset" in params:
            query_params["offset"] = params["offset"]
        if "status" in params:
            query_params["status"] = params["status"]

        response = await self._make_request("GET", f"/lists/{list_id}/members", params=query_params)

        members = response.get("members", [])

        return IntegrationResult(
            success=True,
            data={
                "members": members,
                "count": len(members),
                "total_items": response.get("total_items"),
            },
        )

    async def _get_member(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get member by email.

        Required params:
            list_id: Audience/list ID
            email: Member email address
        """
        list_id = params.get("list_id")
        email = params.get("email")

        if not list_id or not email:
            raise IntegrationError(
                "Missing required parameters: 'list_id' and 'email'",
                code="MISSING_PARAMS",
            )

        subscriber_hash = self._get_subscriber_hash(email)
        response = await self._make_request("GET", f"/lists/{list_id}/members/{subscriber_hash}")

        return IntegrationResult(
            success=True,
            data={
                "member": response,
            },
        )

    async def _add_member(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Add member to audience.

        Required params:
            list_id: Audience/list ID
            email: Member email address
            status: Subscription status (subscribed, unsubscribed, cleaned, pending, transactional)

        Optional params:
            merge_fields: Dict of merge fields (e.g., FNAME, LNAME)
            tags: List of tag names
            language: Member language preference
        """
        list_id = params.get("list_id")
        email = params.get("email")
        status = params.get("status")

        if not list_id or not email or not status:
            raise IntegrationError(
                "Missing required parameters: 'list_id', 'email', and 'status'",
                code="MISSING_PARAMS",
            )

        member_data = {
            "email_address": email,
            "status": status,
        }

        if "merge_fields" in params:
            member_data["merge_fields"] = params["merge_fields"]
        if "tags" in params:
            member_data["tags"] = params["tags"]
        if "language" in params:
            member_data["language"] = params["language"]

        response = await self._make_request("POST", f"/lists/{list_id}/members", data=member_data)

        return IntegrationResult(
            success=True,
            data={
                "member": response,
                "member_id": response.get("id"),
            },
        )

    async def _update_member(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update member info.

        Required params:
            list_id: Audience/list ID
            email: Member email address

        Optional params:
            status: Subscription status
            merge_fields: Dict of merge fields
        """
        list_id = params.get("list_id")
        email = params.get("email")

        if not list_id or not email:
            raise IntegrationError(
                "Missing required parameters: 'list_id' and 'email'",
                code="MISSING_PARAMS",
            )

        member_data = {}

        if "status" in params:
            member_data["status"] = params["status"]
        if "merge_fields" in params:
            member_data["merge_fields"] = params["merge_fields"]

        subscriber_hash = self._get_subscriber_hash(email)
        response = await self._make_request(
            "PATCH", f"/lists/{list_id}/members/{subscriber_hash}", data=member_data
        )

        return IntegrationResult(
            success=True,
            data={
                "member": response,
            },
        )

    # ========================================================================
    # Campaign Actions
    # ========================================================================

    async def _list_campaigns(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List campaigns.

        Optional params:
            count: Number of records (default: 10, max: 1000)
            offset: Number of records to skip
            status: Filter by status (save, paused, schedule, sending, sent)
            type: Filter by type (regular, plaintext, absplit, rss, variate)
        """
        query_params = {}

        if "count" in params:
            query_params["count"] = min(params["count"], 1000)
        if "offset" in params:
            query_params["offset"] = params["offset"]
        if "status" in params:
            query_params["status"] = params["status"]
        if "type" in params:
            query_params["type"] = params["type"]

        response = await self._make_request("GET", "/campaigns", params=query_params)

        campaigns = response.get("campaigns", [])

        return IntegrationResult(
            success=True,
            data={
                "campaigns": campaigns,
                "count": len(campaigns),
                "total_items": response.get("total_items"),
            },
        )

    async def _get_campaign(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get campaign by ID.

        Required params:
            campaign_id: Campaign ID
        """
        campaign_id = params.get("campaign_id")
        if not campaign_id:
            raise IntegrationError("Missing required parameter: 'campaign_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/campaigns/{campaign_id}")

        return IntegrationResult(
            success=True,
            data={
                "campaign": response,
            },
        )

    async def _create_campaign(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create new campaign.

        Required params:
            type: Campaign type (regular, plaintext, absplit, rss, variate)
            list_id: Audience/list ID

        Optional params:
            subject_line: Email subject line
            from_name: From name
            reply_to: Reply-to email
            title: Campaign title (internal)
        """
        campaign_type = params.get("type")
        list_id = params.get("list_id")

        if not campaign_type or not list_id:
            raise IntegrationError(
                "Missing required parameters: 'type' and 'list_id'",
                code="MISSING_PARAMS",
            )

        campaign_data = {
            "type": campaign_type,
            "recipients": {
                "list_id": list_id,
            },
        }

        # Build settings
        settings = {}
        if "subject_line" in params:
            settings["subject_line"] = params["subject_line"]
        if "from_name" in params:
            settings["from_name"] = params["from_name"]
        if "reply_to" in params:
            settings["reply_to"] = params["reply_to"]
        if "title" in params:
            settings["title"] = params["title"]

        if settings:
            campaign_data["settings"] = settings

        response = await self._make_request("POST", "/campaigns", data=campaign_data)

        return IntegrationResult(
            success=True,
            data={
                "campaign": response,
                "campaign_id": response.get("id"),
            },
        )

    async def _send_campaign(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Send a campaign.

        Required params:
            campaign_id: Campaign ID
        """
        campaign_id = params.get("campaign_id")
        if not campaign_id:
            raise IntegrationError("Missing required parameter: 'campaign_id'", code="MISSING_PARAMS")

        await self._make_request("POST", f"/campaigns/{campaign_id}/actions/send")

        return IntegrationResult(
            success=True,
            data={
                "sent": True,
                "campaign_id": campaign_id,
            },
        )
