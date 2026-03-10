"""
SendGrid Integration - FULLY IMPLEMENTED

Real SendGrid API integration for email sending.

Supported Actions:
- send_email: Send single email
- send_bulk_email: Send to multiple recipients
- add_contact: Add contact to list
- list_contacts: List all contacts
- get_stats: Get email statistics

Authentication: API Key
API Docs: https://docs.sendgrid.com/api-reference
"""

import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class SendGridIntegration(BaseIntegration):
    """SendGrid email integration with real API client."""

    API_BASE_URL = "https://api.sendgrid.com/v3"

    @property
    def name(self) -> str:
        return "sendgrid"

    @property
    def display_name(self) -> str:
        return "SendGrid"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return ["send_email", "send_bulk_email", "add_contact", "list_contacts", "get_stats"]

    def _validate_credentials(self) -> None:
        """Validate SendGrid credentials."""
        super()._validate_credentials()
        if not self.auth_credentials.get("api_key"):
            raise IntegrationError("SendGrid requires 'api_key'", code="MISSING_API_KEY")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for SendGrid API."""
        return {
            "Authorization": f"Bearer {self.auth_credentials['api_key']}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to SendGrid API."""
        url = f"{self.API_BASE_URL}/{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method, url=url, headers=self._get_headers(), json=data
                ) as response:
                    # SendGrid returns 202 for successful email send
                    if response.status in [200, 201, 202]:
                        if response.content_length and response.content_length > 0:
                            return await response.json()
                        return {"status": "success"}

                    error_data = await response.json() if response.content_length else {}
                    raise IntegrationError(
                        f"SendGrid API error: {error_data.get('errors', 'Unknown error')}",
                        code=str(response.status),
                        status_code=response.status,
                        details=error_data,
                    )

        except aiohttp.ClientError as e:
            raise IntegrationError(f"HTTP request failed: {str(e)}", code="HTTP_ERROR")
        except Exception as e:
            if isinstance(e, IntegrationError):
                raise
            raise IntegrationError(f"Unexpected error: {str(e)}", code="UNKNOWN_ERROR")

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        """Execute SendGrid action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "send_email":
                result = await self._send_email(params)
            elif action == "send_bulk_email":
                result = await self._send_bulk_email(params)
            elif action == "add_contact":
                result = await self._add_contact(params)
            elif action == "list_contacts":
                result = await self._list_contacts(params)
            elif action == "get_stats":
                result = await self._get_stats(params)
            else:
                raise IntegrationError(f"Action {action} not implemented", code="NOT_IMPLEMENTED")

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result.duration_ms = duration_ms
            self._log_execution(action, params, result)
            return result

        except IntegrationError as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = IntegrationResult(
                success=False, error_message=e.message, error_code=e.code, duration_ms=duration_ms
            )
            self._log_execution(action, params, result)
            return result

    async def test_connection(self) -> IntegrationResult:
        """Test SendGrid connection."""
        try:
            await self._make_request("GET", "scopes")
            return IntegrationResult(success=True, data={"status": "connected"})
        except IntegrationError as e:
            return IntegrationResult(success=False, error_message=e.message, error_code=e.code)

    async def _send_email(self, params: Dict[str, Any]) -> IntegrationResult:
        """Send single email."""
        required = ["to_email", "from_email", "subject", "content"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(
                f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS"
            )

        payload = {
            "personalizations": [{"to": [{"email": params["to_email"]}]}],
            "from": {"email": params["from_email"]},
            "subject": params["subject"],
            "content": [{"type": "text/html" if params.get("html") else "text/plain", "value": params["content"]}],
        }

        await self._make_request("POST", "mail/send", payload)
        return IntegrationResult(success=True, data={"status": "sent", "to": params["to_email"]})

    async def _send_bulk_email(self, params: Dict[str, Any]) -> IntegrationResult:
        """Send to multiple recipients."""
        required = ["to_emails", "from_email", "subject", "content"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(
                f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS"
            )

        payload = {
            "personalizations": [{"to": [{"email": email} for email in params["to_emails"]]}],
            "from": {"email": params["from_email"]},
            "subject": params["subject"],
            "content": [{"type": "text/html" if params.get("html") else "text/plain", "value": params["content"]}],
        }

        await self._make_request("POST", "mail/send", payload)
        return IntegrationResult(
            success=True, data={"status": "sent", "recipients": len(params["to_emails"])}
        )

    async def _add_contact(self, params: Dict[str, Any]) -> IntegrationResult:
        """Add contact to list."""
        if "email" not in params:
            raise IntegrationError("Missing required parameter: 'email'", code="MISSING_PARAMS")

        payload = {
            "contacts": [
                {
                    "email": params["email"],
                    "first_name": params.get("first_name", ""),
                    "last_name": params.get("last_name", ""),
                }
            ]
        }

        response = await self._make_request("PUT", "marketing/contacts", payload)
        return IntegrationResult(success=True, data={"status": "added", "email": params["email"]})

    async def _list_contacts(self, params: Dict[str, Any]) -> IntegrationResult:
        """List all contacts."""
        response = await self._make_request("GET", "marketing/contacts")
        contacts = response.get("result", [])
        return IntegrationResult(success=True, data={"contacts": contacts, "total": len(contacts)})

    async def _get_stats(self, params: Dict[str, Any]) -> IntegrationResult:
        """Get email statistics."""
        start_date = params.get("start_date", "2024-01-01")
        response = await self._make_request("GET", f"stats?start_date={start_date}")
        return IntegrationResult(success=True, data={"stats": response})
