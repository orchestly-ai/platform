"""
Twilio Integration - FULLY IMPLEMENTED

Real Twilio API integration for SMS and voice.

Supported Actions:
- send_sms: Send SMS message
- make_call: Make phone call
- send_whatsapp: Send WhatsApp message
- list_messages: List sent messages
- get_message: Get message details

Authentication: API Key (Account SID + Auth Token)
API Docs: https://www.twilio.com/docs/usage/api
"""

import aiohttp
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class TwilioIntegration(BaseIntegration):
    """Twilio SMS/Voice integration with real API client."""

    API_BASE_URL = "https://api.twilio.com/2010-04-01"

    @property
    def name(self) -> str:
        return "twilio"

    @property
    def display_name(self) -> str:
        return "Twilio"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.BASIC_AUTH

    @property
    def supported_actions(self) -> List[str]:
        return ["send_sms", "make_call", "send_whatsapp", "list_messages", "get_message"]

    def _validate_credentials(self) -> None:
        """Validate Twilio credentials."""
        super()._validate_credentials()
        if not self.auth_credentials.get("account_sid") or not self.auth_credentials.get("auth_token"):
            raise IntegrationError(
                "Twilio requires 'account_sid' and 'auth_token'", code="MISSING_CREDENTIALS"
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Twilio API."""
        account_sid = self.auth_credentials["account_sid"]
        auth_token = self.auth_credentials["auth_token"]
        credentials = f"{account_sid}:{auth_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Twilio API."""
        account_sid = self.auth_credentials["account_sid"]
        url = f"{self.API_BASE_URL}/Accounts/{account_sid}/{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method, url=url, headers=self._get_headers(), data=data
                ) as response:
                    response_data = await response.json()
                    if response.status >= 400:
                        raise IntegrationError(
                            f"Twilio API error: {response_data.get('message', 'Unknown error')}",
                            code=str(response_data.get('code', response.status)),
                            status_code=response.status,
                        )
                    return response_data
        except aiohttp.ClientError as e:
            raise IntegrationError(f"HTTP request failed: {str(e)}", code="HTTP_ERROR")

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        """Execute Twilio action."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "send_sms":
                result = await self._send_sms(params)
            elif action == "make_call":
                result = await self._make_call(params)
            elif action == "send_whatsapp":
                result = await self._send_whatsapp(params)
            elif action == "list_messages":
                result = await self._list_messages(params)
            elif action == "get_message":
                result = await self._get_message(params)
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
        """Test Twilio connection."""
        try:
            account_sid = self.auth_credentials["account_sid"]
            response = await self._make_request("GET", f".json")
            return IntegrationResult(success=True, data={"account_sid": response.get("sid")})
        except IntegrationError as e:
            return IntegrationResult(success=False, error_message=e.message, error_code=e.code)

    async def _send_sms(self, params: Dict[str, Any]) -> IntegrationResult:
        """Send SMS message."""
        required = ["to", "from_", "body"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        payload = {"To": params["to"], "From": params["from_"], "Body": params["body"]}
        response = await self._make_request("POST", "Messages.json", payload)

        return IntegrationResult(
            success=True,
            data={"message_sid": response.get("sid"), "status": response.get("status")},
        )

    async def _make_call(self, params: Dict[str, Any]) -> IntegrationResult:
        """Make phone call."""
        required = ["to", "from_", "url"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        payload = {"To": params["to"], "From": params["from_"], "Url": params["url"]}
        response = await self._make_request("POST", "Calls.json", payload)

        return IntegrationResult(
            success=True,
            data={"call_sid": response.get("sid"), "status": response.get("status")},
        )

    async def _send_whatsapp(self, params: Dict[str, Any]) -> IntegrationResult:
        """Send WhatsApp message."""
        required = ["to", "from_", "body"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        payload = {
            "To": f"whatsapp:{params['to']}",
            "From": f"whatsapp:{params['from_']}",
            "Body": params["body"],
        }
        response = await self._make_request("POST", "Messages.json", payload)

        return IntegrationResult(
            success=True,
            data={"message_sid": response.get("sid"), "status": response.get("status")},
        )

    async def _list_messages(self, params: Dict[str, Any]) -> IntegrationResult:
        """List sent messages."""
        response = await self._make_request("GET", "Messages.json")
        messages = response.get("messages", [])
        return IntegrationResult(success=True, data={"messages": messages, "total": len(messages)})

    async def _get_message(self, params: Dict[str, Any]) -> IntegrationResult:
        """Get message details."""
        if "message_sid" not in params:
            raise IntegrationError("Missing required parameter: 'message_sid'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"Messages/{params['message_sid']}.json")
        return IntegrationResult(success=True, data={"message": response})
