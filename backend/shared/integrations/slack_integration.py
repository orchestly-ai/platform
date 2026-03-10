"""
Slack Integration

Real Slack integration using OAuth 2.0 and the Slack Web API.
Supports sending messages, creating channels, managing users, etc.

OAuth Scopes Required:
- chat:write - Send messages
- channels:read - List channels
- channels:write - Create/manage channels
- users:read - View user information
- files:write - Upload files
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
)

logger = logging.getLogger(__name__)

# Slack API base URL
SLACK_API_BASE = "https://slack.com/api"


class SlackIntegration(OAuthIntegration):
    """
    Slack integration with full OAuth 2.0 support.

    Supports:
    - send_message: Send messages to channels
    - send_dm: Send direct messages to users
    - create_channel: Create new channels
    - list_channels: List available channels
    - upload_file: Upload files to Slack
    - add_reaction: Add emoji reactions to messages
    - get_user_info: Get user profile information
    """

    name = "slack"
    display_name = "Slack"
    description = "Send messages, create channels, and collaborate in Slack"
    icon_url = "https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png"
    documentation_url = "https://api.slack.com/docs"

    # OAuth configuration - in production, load from environment
    OAUTH_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID", "")
    OAUTH_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET", "")
    OAUTH_REDIRECT_URI = os.environ.get("SLACK_REDIRECT_URI", "http://localhost:3000/integrations/slack/callback")

    DEFAULT_SCOPES = [
        "chat:write",
        "channels:read",
        "channels:write",
        "channels:join",
        "users:read",
        "files:write",
        "reactions:write",
        "groups:read",
        "im:read",
    ]

    def get_oauth_config(self) -> Optional[OAuthConfig]:
        """Return Slack OAuth configuration."""
        return OAuthConfig(
            client_id=self.OAUTH_CLIENT_ID,
            client_secret=self.OAUTH_CLIENT_SECRET,
            authorize_url="https://slack.com/oauth/v2/authorize",
            token_url="https://slack.com/api/oauth.v2.access",
            scopes=self.DEFAULT_SCOPES,
            redirect_uri=self.OAUTH_REDIRECT_URI,
        )

    async def validate_credentials(self) -> bool:
        """Validate Slack credentials by calling auth.test."""
        access_token = self.get_access_token()
        if not access_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/auth.test",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                data = response.json()
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"Slack credential validation failed: {e}")
            return False

    async def refresh_tokens(self) -> Optional[OAuthTokens]:
        """Refresh Slack OAuth tokens."""
        refresh_token = self.get_refresh_token()
        if not refresh_token:
            return None

        oauth_config = self.get_oauth_config()
        if not oauth_config:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    oauth_config.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": oauth_config.client_id,
                        "client_secret": oauth_config.client_secret,
                        "refresh_token": refresh_token,
                    },
                )
                data = response.json()

                if data.get("ok"):
                    expires_at = datetime.utcnow() + timedelta(
                        seconds=data.get("expires_in", 3600)
                    )
                    return OAuthTokens(
                        access_token=data["access_token"],
                        refresh_token=data.get("refresh_token", refresh_token),
                        token_type="Bearer",
                        expires_at=expires_at,
                        scope=data.get("scope"),
                    )
                else:
                    logger.error(f"Slack token refresh failed: {data.get('error')}")
                    return None
        except Exception as e:
            logger.error(f"Slack token refresh error: {e}")
            return None

    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Return list of available Slack actions."""
        return [
            {
                "name": "send_message",
                "display_name": "Send Message",
                "description": "Send a message to a Slack channel",
                "input_schema": {
                    "type": "object",
                    "required": ["channel", "text"],
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel ID or name (e.g., #general or C01234567)",
                        },
                        "text": {
                            "type": "string",
                            "description": "Message text (supports Slack markdown)",
                        },
                        "thread_ts": {
                            "type": "string",
                            "description": "Thread timestamp to reply to",
                        },
                        "unfurl_links": {
                            "type": "boolean",
                            "description": "Whether to unfurl URLs",
                            "default": True,
                        },
                    },
                },
            },
            {
                "name": "send_dm",
                "display_name": "Send Direct Message",
                "description": "Send a direct message to a user",
                "input_schema": {
                    "type": "object",
                    "required": ["user_id", "text"],
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User ID to message (e.g., U01234567)",
                        },
                        "text": {
                            "type": "string",
                            "description": "Message text",
                        },
                    },
                },
            },
            {
                "name": "create_channel",
                "display_name": "Create Channel",
                "description": "Create a new Slack channel",
                "input_schema": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Channel name (lowercase, no spaces)",
                        },
                        "is_private": {
                            "type": "boolean",
                            "description": "Whether the channel is private",
                            "default": False,
                        },
                    },
                },
            },
            {
                "name": "list_channels",
                "display_name": "List Channels",
                "description": "List available Slack channels",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "types": {
                            "type": "string",
                            "description": "Channel types (public_channel, private_channel)",
                            "default": "public_channel",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum channels to return",
                            "default": 100,
                        },
                    },
                },
            },
            {
                "name": "upload_file",
                "display_name": "Upload File",
                "description": "Upload a file to Slack",
                "input_schema": {
                    "type": "object",
                    "required": ["channels", "content"],
                    "properties": {
                        "channels": {
                            "type": "string",
                            "description": "Comma-separated channel IDs",
                        },
                        "content": {
                            "type": "string",
                            "description": "File content (for text files)",
                        },
                        "filename": {
                            "type": "string",
                            "description": "File name",
                        },
                        "title": {
                            "type": "string",
                            "description": "File title",
                        },
                    },
                },
            },
            {
                "name": "add_reaction",
                "display_name": "Add Reaction",
                "description": "Add an emoji reaction to a message",
                "input_schema": {
                    "type": "object",
                    "required": ["channel", "timestamp", "name"],
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel ID",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Message timestamp",
                        },
                        "name": {
                            "type": "string",
                            "description": "Emoji name (without colons)",
                        },
                    },
                },
            },
            {
                "name": "get_user_info",
                "display_name": "Get User Info",
                "description": "Get information about a Slack user",
                "input_schema": {
                    "type": "object",
                    "required": ["user_id"],
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User ID",
                        },
                    },
                },
            },
            {
                "name": "test_connection",
                "display_name": "Test Connection",
                "description": "Test the Slack connection",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute a Slack action."""
        start_time = datetime.utcnow()

        # Check if token needs refresh
        if self.is_token_expired():
            new_tokens = await self.refresh_tokens()
            if new_tokens:
                self.credentials["access_token"] = new_tokens.access_token
                if new_tokens.refresh_token:
                    self.credentials["refresh_token"] = new_tokens.refresh_token

        access_token = self.get_access_token()
        if not access_token:
            return IntegrationResult(
                success=False,
                error_message="No access token available. Please authenticate with Slack.",
                error_code="NO_TOKEN",
            )

        try:
            # Route to appropriate action handler
            if action_name == "send_message":
                result = await self._send_message(access_token, parameters)
            elif action_name == "send_dm":
                result = await self._send_dm(access_token, parameters)
            elif action_name == "create_channel":
                result = await self._create_channel(access_token, parameters)
            elif action_name == "list_channels":
                result = await self._list_channels(access_token, parameters)
            elif action_name == "upload_file":
                result = await self._upload_file(access_token, parameters)
            elif action_name == "add_reaction":
                result = await self._add_reaction(access_token, parameters)
            elif action_name == "get_user_info":
                result = await self._get_user_info(access_token, parameters)
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
            logger.error(f"Slack action {action_name} failed: {e}")
            end_time = datetime.utcnow()
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                duration_ms=(end_time - start_time).total_seconds() * 1000,
            )

    async def _send_message(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Send a message to a Slack channel."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SLACK_API_BASE}/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "channel": params["channel"],
                    "text": params["text"],
                    "thread_ts": params.get("thread_ts"),
                    "unfurl_links": params.get("unfurl_links", True),
                },
            )
            data = response.json()

            if data.get("ok"):
                return IntegrationResult(
                    success=True,
                    data={
                        "message_ts": data.get("ts"),
                        "channel": data.get("channel"),
                        "message": data.get("message"),
                    },
                    raw_response=data,
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", "Unknown error"),
                    error_code=data.get("error"),
                    raw_response=data,
                )

    async def _send_dm(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Send a direct message to a user."""
        async with httpx.AsyncClient() as client:
            # First, open a DM channel
            open_response = await client.post(
                f"{SLACK_API_BASE}/conversations.open",
                headers={"Authorization": f"Bearer {token}"},
                json={"users": params["user_id"]},
            )
            open_data = open_response.json()

            if not open_data.get("ok"):
                return IntegrationResult(
                    success=False,
                    error_message=f"Failed to open DM: {open_data.get('error')}",
                    error_code=open_data.get("error"),
                )

            channel_id = open_data["channel"]["id"]

            # Send the message
            return await self._send_message(token, {
                "channel": channel_id,
                "text": params["text"],
            })

    async def _create_channel(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new Slack channel."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SLACK_API_BASE}/conversations.create",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "name": params["name"],
                    "is_private": params.get("is_private", False),
                },
            )
            data = response.json()

            if data.get("ok"):
                return IntegrationResult(
                    success=True,
                    data={
                        "channel_id": data["channel"]["id"],
                        "channel_name": data["channel"]["name"],
                    },
                    raw_response=data,
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", "Unknown error"),
                    error_code=data.get("error"),
                    raw_response=data,
                )

    async def _list_channels(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """List Slack channels."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SLACK_API_BASE}/conversations.list",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "types": params.get("types", "public_channel"),
                    "limit": params.get("limit", 100),
                },
            )
            data = response.json()

            if data.get("ok"):
                channels = [
                    {
                        "id": ch["id"],
                        "name": ch["name"],
                        "is_private": ch.get("is_private", False),
                        "num_members": ch.get("num_members", 0),
                    }
                    for ch in data.get("channels", [])
                ]
                return IntegrationResult(
                    success=True,
                    data={"channels": channels, "count": len(channels)},
                    raw_response=data,
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", "Unknown error"),
                    error_code=data.get("error"),
                    raw_response=data,
                )

    async def _upload_file(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Upload a file to Slack."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SLACK_API_BASE}/files.upload",
                headers={"Authorization": f"Bearer {token}"},
                data={
                    "channels": params["channels"],
                    "content": params["content"],
                    "filename": params.get("filename", "file.txt"),
                    "title": params.get("title"),
                },
            )
            data = response.json()

            if data.get("ok"):
                return IntegrationResult(
                    success=True,
                    data={
                        "file_id": data["file"]["id"],
                        "file_url": data["file"].get("url_private"),
                    },
                    raw_response=data,
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", "Unknown error"),
                    error_code=data.get("error"),
                    raw_response=data,
                )

    async def _add_reaction(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Add a reaction to a message."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SLACK_API_BASE}/reactions.add",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "channel": params["channel"],
                    "timestamp": params["timestamp"],
                    "name": params["name"],
                },
            )
            data = response.json()

            if data.get("ok"):
                return IntegrationResult(success=True, data={"added": True}, raw_response=data)
            else:
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", "Unknown error"),
                    error_code=data.get("error"),
                    raw_response=data,
                )

    async def _get_user_info(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Get user information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SLACK_API_BASE}/users.info",
                headers={"Authorization": f"Bearer {token}"},
                params={"user": params["user_id"]},
            )
            data = response.json()

            if data.get("ok"):
                user = data.get("user", {})
                return IntegrationResult(
                    success=True,
                    data={
                        "user_id": user.get("id"),
                        "name": user.get("name"),
                        "real_name": user.get("real_name"),
                        "email": user.get("profile", {}).get("email"),
                        "is_admin": user.get("is_admin", False),
                    },
                    raw_response=data,
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message=data.get("error", "Unknown error"),
                    error_code=data.get("error"),
                    raw_response=data,
                )


# OAuth flow helper functions
def get_slack_oauth_url(state: str, scopes: Optional[List[str]] = None) -> str:
    """Generate the Slack OAuth authorization URL."""
    config = SlackIntegration({}, {}).get_oauth_config()
    if not config:
        raise ValueError("Slack OAuth not configured")

    scope_str = ",".join(scopes or config.scopes)
    return (
        f"{config.authorize_url}"
        f"?client_id={config.client_id}"
        f"&scope={scope_str}"
        f"&redirect_uri={config.redirect_uri}"
        f"&state={state}"
    )


async def exchange_slack_code(code: str) -> Optional[Dict[str, Any]]:
    """Exchange OAuth code for tokens."""
    config = SlackIntegration({}, {}).get_oauth_config()
    if not config:
        return None

    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.token_url,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": config.redirect_uri,
            },
        )
        data = response.json()

        if data.get("ok"):
            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "token_type": data.get("token_type", "Bearer"),
                "scope": data.get("scope"),
                "team_id": data.get("team", {}).get("id"),
                "team_name": data.get("team", {}).get("name"),
                "authed_user_id": data.get("authed_user", {}).get("id"),
            }
        else:
            logger.error(f"Slack OAuth exchange failed: {data.get('error')}")
            return None
