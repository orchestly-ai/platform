"""
Intercom Integration - FULLY IMPLEMENTED

Real Intercom API integration for customer messaging and support.

Supported Actions:
- list_contacts: List contacts/users
- get_contact: Get contact by ID
- create_contact: Create new contact
- update_contact: Update existing contact
- list_conversations: List conversations
- get_conversation: Get conversation by ID
- reply_conversation: Reply to conversation
- create_message: Send a message to a contact
- list_companies: List companies
- create_company: Create a company

Authentication: Access Token (Bearer)
API Docs: https://developers.intercom.com/docs/build-an-integration/
"""

import aiohttp
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class IntercomIntegration(BaseIntegration):
    """Intercom integration with REST API."""

    BASE_URL = "https://api.intercom.io"
    API_VERSION = "2.10"

    @property
    def name(self) -> str:
        return "intercom"

    @property
    def display_name(self) -> str:
        return "Intercom"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "list_contacts",
            "get_contact",
            "create_contact",
            "update_contact",
            "list_conversations",
            "get_conversation",
            "reply_conversation",
            "create_message",
            "list_companies",
            "create_company",
        ]

    def _validate_credentials(self) -> None:
        """Validate Intercom credentials."""
        super()._validate_credentials()

        if "access_token" not in self.auth_credentials:
            raise IntegrationError(
                "Intercom requires 'access_token'",
                code="MISSING_CREDENTIALS",
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        return {
            "Authorization": f"Bearer {self.auth_credentials['access_token']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Intercom-Version": self.API_VERSION,
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Intercom API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/contacts")
            data: Request body for POST/PUT
            params: Query parameters

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
        url = f"{self.BASE_URL}{endpoint}"

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
                            errors = error_data.get("errors", [])
                            error_msg = errors[0].get("message") if errors else response_text
                        except (json.JSONDecodeError, IndexError):
                            error_msg = response_text

                        raise IntegrationError(
                            f"Intercom API error: {error_msg}",
                            code="INTERCOM_ERROR",
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
        """Execute Intercom action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "list_contacts":
                result = await self._list_contacts(params)
            elif action == "get_contact":
                result = await self._get_contact(params)
            elif action == "create_contact":
                result = await self._create_contact(params)
            elif action == "update_contact":
                result = await self._update_contact(params)
            elif action == "list_conversations":
                result = await self._list_conversations(params)
            elif action == "get_conversation":
                result = await self._get_conversation(params)
            elif action == "reply_conversation":
                result = await self._reply_conversation(params)
            elif action == "create_message":
                result = await self._create_message(params)
            elif action == "list_companies":
                result = await self._list_companies(params)
            elif action == "create_company":
                result = await self._create_company(params)
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
        """Test Intercom connection by fetching current admin."""
        try:
            response = await self._make_request("GET", "/me")
            return IntegrationResult(
                success=True,
                data={
                    "connected": True,
                    "admin_id": response.get("id"),
                    "admin_name": response.get("name"),
                    "app_id": response.get("app", {}).get("id_code"),
                },
            )
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )

    # ========================================================================
    # Contact Actions
    # ========================================================================

    async def _list_contacts(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List contacts/users.

        Optional params:
            per_page: Items per page (default: 50)
            starting_after: Cursor for pagination
        """
        query_params = {}

        if "per_page" in params:
            query_params["per_page"] = params["per_page"]
        if "starting_after" in params:
            query_params["starting_after"] = params["starting_after"]

        response = await self._make_request("GET", "/contacts", params=query_params)

        contacts = response.get("data", [])

        return IntegrationResult(
            success=True,
            data={
                "contacts": contacts,
                "count": len(contacts),
                "total_count": response.get("total_count"),
                "pages": response.get("pages"),
            },
        )

    async def _get_contact(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get contact by ID.

        Required params:
            contact_id: Contact ID
        """
        contact_id = params.get("contact_id")
        if not contact_id:
            raise IntegrationError("Missing required parameter: 'contact_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/contacts/{contact_id}")

        return IntegrationResult(
            success=True,
            data={
                "contact": response,
            },
        )

    async def _create_contact(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create new contact.

        Required params:
            role: Contact role ('user' or 'lead')

        Optional params:
            email: Contact email
            phone: Contact phone
            name: Contact name
            external_id: External ID from your system
            custom_attributes: Dict of custom attributes
        """
        role = params.get("role")
        if not role:
            raise IntegrationError("Missing required parameter: 'role'", code="MISSING_PARAMS")

        contact_data = {"role": role}

        optional_fields = ["email", "phone", "name", "external_id", "custom_attributes"]
        for field in optional_fields:
            if field in params:
                contact_data[field] = params[field]

        response = await self._make_request("POST", "/contacts", data=contact_data)

        return IntegrationResult(
            success=True,
            data={
                "contact": response,
                "contact_id": response.get("id"),
            },
        )

    async def _update_contact(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update existing contact.

        Required params:
            contact_id: Contact ID

        Optional params:
            email: Contact email
            phone: Contact phone
            name: Contact name
            custom_attributes: Dict of custom attributes
        """
        contact_id = params.get("contact_id")
        if not contact_id:
            raise IntegrationError("Missing required parameter: 'contact_id'", code="MISSING_PARAMS")

        contact_data = {}

        optional_fields = ["email", "phone", "name", "custom_attributes"]
        for field in optional_fields:
            if field in params:
                contact_data[field] = params[field]

        response = await self._make_request("PUT", f"/contacts/{contact_id}", data=contact_data)

        return IntegrationResult(
            success=True,
            data={
                "contact": response,
            },
        )

    # ========================================================================
    # Conversation Actions
    # ========================================================================

    async def _list_conversations(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List conversations.

        Optional params:
            per_page: Items per page (default: 20)
            starting_after: Cursor for pagination
        """
        query_params = {}

        if "per_page" in params:
            query_params["per_page"] = params["per_page"]
        if "starting_after" in params:
            query_params["starting_after"] = params["starting_after"]

        response = await self._make_request("GET", "/conversations", params=query_params)

        conversations = response.get("conversations", [])

        return IntegrationResult(
            success=True,
            data={
                "conversations": conversations,
                "count": len(conversations),
                "pages": response.get("pages"),
            },
        )

    async def _get_conversation(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get conversation by ID.

        Required params:
            conversation_id: Conversation ID
        """
        conversation_id = params.get("conversation_id")
        if not conversation_id:
            raise IntegrationError("Missing required parameter: 'conversation_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/conversations/{conversation_id}")

        return IntegrationResult(
            success=True,
            data={
                "conversation": response,
            },
        )

    async def _reply_conversation(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Reply to a conversation.

        Required params:
            conversation_id: Conversation ID
            body: Reply message body
            message_type: Type of reply ('comment', 'note')

        Optional params:
            admin_id: Admin ID (required for admin replies)
            attachment_urls: List of attachment URLs
        """
        conversation_id = params.get("conversation_id")
        body = params.get("body")
        message_type = params.get("message_type", "comment")

        if not conversation_id or not body:
            raise IntegrationError(
                "Missing required parameters: 'conversation_id' and 'body'",
                code="MISSING_PARAMS",
            )

        reply_data = {
            "body": body,
            "message_type": message_type,
            "type": "admin",
        }

        if "admin_id" in params:
            reply_data["admin_id"] = params["admin_id"]
        if "attachment_urls" in params:
            reply_data["attachment_urls"] = params["attachment_urls"]

        response = await self._make_request(
            "POST", f"/conversations/{conversation_id}/reply", data=reply_data
        )

        return IntegrationResult(
            success=True,
            data={
                "conversation": response,
            },
        )

    async def _create_message(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Send a message to a contact.

        Required params:
            from_admin_id: Admin ID sending the message
            to_contact_id: Contact ID to send to
            body: Message body

        Optional params:
            message_type: Message type ('inapp' or 'email', default: 'inapp')
            subject: Email subject (for email type)
        """
        from_admin_id = params.get("from_admin_id")
        to_contact_id = params.get("to_contact_id")
        body = params.get("body")

        if not from_admin_id or not to_contact_id or not body:
            raise IntegrationError(
                "Missing required parameters: 'from_admin_id', 'to_contact_id', and 'body'",
                code="MISSING_PARAMS",
            )

        message_data = {
            "message_type": params.get("message_type", "inapp"),
            "body": body,
            "from": {
                "type": "admin",
                "id": from_admin_id,
            },
            "to": {
                "type": "contact",
                "id": to_contact_id,
            },
        }

        if "subject" in params:
            message_data["subject"] = params["subject"]

        response = await self._make_request("POST", "/messages", data=message_data)

        return IntegrationResult(
            success=True,
            data={
                "message": response,
                "message_id": response.get("id"),
            },
        )

    # ========================================================================
    # Company Actions
    # ========================================================================

    async def _list_companies(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List companies.

        Optional params:
            per_page: Items per page (default: 50)
            page: Page number
        """
        query_params = {}

        if "per_page" in params:
            query_params["per_page"] = params["per_page"]
        if "page" in params:
            query_params["page"] = params["page"]

        response = await self._make_request("GET", "/companies", params=query_params)

        companies = response.get("data", [])

        return IntegrationResult(
            success=True,
            data={
                "companies": companies,
                "count": len(companies),
                "total_count": response.get("total_count"),
                "pages": response.get("pages"),
            },
        )

    async def _create_company(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a company.

        Required params:
            company_id: Unique company ID (from your system)

        Optional params:
            name: Company name
            plan: Company plan
            size: Company size
            website: Company website
            industry: Industry
            custom_attributes: Dict of custom attributes
        """
        company_id = params.get("company_id")
        if not company_id:
            raise IntegrationError("Missing required parameter: 'company_id'", code="MISSING_PARAMS")

        company_data = {"company_id": company_id}

        optional_fields = ["name", "plan", "size", "website", "industry", "custom_attributes"]
        for field in optional_fields:
            if field in params:
                company_data[field] = params[field]

        response = await self._make_request("POST", "/companies", data=company_data)

        return IntegrationResult(
            success=True,
            data={
                "company": response,
                "id": response.get("id"),
            },
        )
