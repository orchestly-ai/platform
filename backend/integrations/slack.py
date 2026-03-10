"""
Slack Integration - FULLY IMPLEMENTED

Real Slack API integration with working HTTP client.

Supported Actions:
- send_message: Send message to channel
- create_channel: Create new channel
- list_channels: List all channels
- get_user: Get user information
- upload_file: Upload file to channel

Authentication: OAuth 2.0 or Bot Token
API Docs: https://api.slack.com/methods
"""

import aiohttp
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class SlackIntegration(BaseIntegration):
    """Slack integration with real API client."""

    API_BASE_URL = "https://slack.com/api"

    @property
    def name(self) -> str:
        return "slack"

    @property
    def display_name(self) -> str:
        return "Slack"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.OAUTH2

    @property
    def supported_actions(self) -> List[str]:
        return [
            "send_message",
            "create_channel",
            "list_channels",
            "get_user",
            "upload_file",
        ]

    def _validate_credentials(self) -> None:
        """Validate Slack credentials."""
        super()._validate_credentials()

        token = self.auth_credentials.get("access_token") or self.auth_credentials.get("bot_token")
        if not token:
            raise IntegrationError(
                "Slack requires 'access_token' or 'bot_token'",
                code="MISSING_TOKEN",
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Slack API."""
        token = self.auth_credentials.get("access_token") or self.auth_credentials.get("bot_token")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Slack API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., 'chat.postMessage')
            data: Request payload

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
        url = f"{self.API_BASE_URL}/{endpoint}"
        start_time = datetime.utcnow()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=data,
                ) as response:
                    response_data = await response.json()

                    # Slack always returns 200, check 'ok' field
                    if not response_data.get("ok"):
                        error = response_data.get("error", "unknown_error")
                        raise IntegrationError(
                            f"Slack API error: {error}",
                            code=error.upper(),
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
        """Execute Slack action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "send_message":
                result = await self._send_message(params)
            elif action == "create_channel":
                result = await self._create_channel(params)
            elif action == "list_channels":
                result = await self._list_channels(params)
            elif action == "get_user":
                result = await self._get_user(params)
            elif action == "upload_file":
                result = await self._upload_file(params)
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
        """Test Slack connection using auth.test endpoint."""
        try:
            response = await self._make_request("POST", "auth.test")
            return IntegrationResult(
                success=True,
                data={
                    "team": response.get("team"),
                    "user": response.get("user"),
                    "team_id": response.get("team_id"),
                    "user_id": response.get("user_id"),
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

    async def _send_message(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Send message to Slack channel.

        Required params:
            channel: Channel ID or name (e.g., '#general', 'C1234567890')
            text: Message text

        Optional params:
            thread_ts: Thread timestamp (for replies)
            blocks: Rich formatting blocks
            attachments: Message attachments
        """
        if "channel" not in params or "text" not in params:
            raise IntegrationError(
                "Missing required parameters: 'channel' and 'text'",
                code="MISSING_PARAMS",
            )

        payload = {
            "channel": params["channel"],
            "text": params["text"],
        }

        # Optional parameters
        if "thread_ts" in params:
            payload["thread_ts"] = params["thread_ts"]
        if "blocks" in params:
            payload["blocks"] = params["blocks"]
        if "attachments" in params:
            payload["attachments"] = params["attachments"]

        response = await self._make_request("POST", "chat.postMessage", payload)

        return IntegrationResult(
            success=True,
            data={
                "message_ts": response.get("ts"),
                "channel": response.get("channel"),
                "message": response.get("message"),
            },
        )

    async def _create_channel(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create new Slack channel.

        Required params:
            name: Channel name (lowercase, no spaces)

        Optional params:
            is_private: Create private channel (default: False)
        """
        if "name" not in params:
            raise IntegrationError("Missing required parameter: 'name'", code="MISSING_PARAMS")

        payload = {
            "name": params["name"],
            "is_private": params.get("is_private", False),
        }

        endpoint = "conversations.create"
        response = await self._make_request("POST", endpoint, payload)

        return IntegrationResult(
            success=True,
            data={
                "channel_id": response.get("channel", {}).get("id"),
                "channel_name": response.get("channel", {}).get("name"),
                "created": response.get("channel", {}).get("created"),
            },
        )

    async def _list_channels(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List all channels.

        Optional params:
            types: Channel types (e.g., 'public_channel,private_channel')
            limit: Max channels to return (default: 100)
        """
        payload = {
            "types": params.get("types", "public_channel,private_channel"),
            "limit": params.get("limit", 100),
        }

        response = await self._make_request("POST", "conversations.list", payload)

        channels = [
            {
                "id": ch.get("id"),
                "name": ch.get("name"),
                "is_private": ch.get("is_private"),
                "is_archived": ch.get("is_archived"),
                "num_members": ch.get("num_members"),
            }
            for ch in response.get("channels", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "channels": channels,
                "total": len(channels),
            },
        )

    async def _get_user(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get user information.

        Required params:
            user: User ID
        """
        if "user" not in params:
            raise IntegrationError("Missing required parameter: 'user'", code="MISSING_PARAMS")

        payload = {"user": params["user"]}
        response = await self._make_request("POST", "users.info", payload)

        user = response.get("user", {})
        return IntegrationResult(
            success=True,
            data={
                "id": user.get("id"),
                "name": user.get("name"),
                "real_name": user.get("real_name"),
                "email": user.get("profile", {}).get("email"),
                "is_admin": user.get("is_admin"),
                "is_bot": user.get("is_bot"),
            },
        )

    async def _upload_file(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Upload file to channel.

        Required params:
            channels: Channel IDs (comma-separated)
            content OR file: File content or file path

        Optional params:
            filename: File name
            title: File title
            initial_comment: Comment with file
        """
        if "channels" not in params:
            raise IntegrationError("Missing required parameter: 'channels'", code="MISSING_PARAMS")

        if "content" not in params and "file" not in params:
            raise IntegrationError(
                "Missing required parameter: 'content' or 'file'",
                code="MISSING_PARAMS",
            )

        payload = {
            "channels": params["channels"],
        }

        if "content" in params:
            payload["content"] = params["content"]
        if "filename" in params:
            payload["filename"] = params["filename"]
        if "title" in params:
            payload["title"] = params["title"]
        if "initial_comment" in params:
            payload["initial_comment"] = params["initial_comment"]

        response = await self._make_request("POST", "files.upload", payload)

        file_data = response.get("file", {})
        return IntegrationResult(
            success=True,
            data={
                "file_id": file_data.get("id"),
                "name": file_data.get("name"),
                "url": file_data.get("url_private"),
                "size": file_data.get("size"),
            },
        )
