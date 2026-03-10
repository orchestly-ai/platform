"""
Discord Integration

Real Discord integration using Discord Bot API.
Supports sending messages, managing channels, and interacting with servers.

Authentication:
- Uses Bot Token (API Key style)
- Or OAuth 2.0 for user authentication

Features:
- Connection pooling for better performance
- Automatic retries with exponential backoff
- Rate limit (429) handling with Retry-After header
- Configurable timeouts for stability
"""

import os
import asyncio
import random
import httpx
from datetime import datetime
from typing import Any, Dict, List, Optional, ClassVar
import logging

from backend.shared.integrations.base import (
    APIKeyIntegration,
    IntegrationResult,
    AuthMethod,
)

logger = logging.getLogger(__name__)

# Discord API base URL
DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordIntegration(APIKeyIntegration):
    """
    Discord integration using Bot Token or User OAuth.

    Features resilient connection handling:
    - Connection pooling via shared httpx.AsyncClient
    - Automatic retries with exponential backoff
    - Rate limit (429) handling with Retry-After header
    - Configurable timeouts

    Supports:
    - send_message: Send messages to channels
    - create_channel: Create new channels
    - list_channels: List server channels
    - get_guild_info: Get server information
    - add_reaction: Add emoji reactions
    - create_thread: Create thread from message
    - get_user: Get user information
    """

    name = "discord"
    display_name = "Discord"
    description = "Send messages and manage channels in Discord"
    icon_url = "https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png"
    documentation_url = "https://discord.com/developers/docs"

    # Shared client for connection pooling (class-level)
    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 30.0  # seconds
    REQUEST_TIMEOUT = 30.0  # seconds

    # Status codes that should trigger retries
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def get_auth_method(self) -> AuthMethod:
        return AuthMethod.BEARER_TOKEN

    def get_bot_token(self) -> Optional[str]:
        """Get the bot token from credentials."""
        return self.credentials.get("bot_token") or self.credentials.get("api_key")

    @classmethod
    async def _get_client(cls) -> httpx.AsyncClient:
        """Get or create shared AsyncClient with connection pooling."""
        async with cls._client_lock:
            if cls._client is None or cls._client.is_closed:
                # Create client with connection pooling and timeouts
                cls._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        timeout=cls.REQUEST_TIMEOUT,
                        connect=10.0,
                    ),
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                        keepalive_expiry=30.0,
                    ),
                )
                logger.info("Created new Discord API client with connection pooling")
            return cls._client

    @classmethod
    async def close_client(cls):
        """Close the shared client (call on application shutdown)."""
        async with cls._client_lock:
            if cls._client and not cls._client.is_closed:
                await cls._client.aclose()
                cls._client = None
                logger.info("Closed Discord API client")

    def _calculate_retry_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        if retry_after:
            # Use Retry-After header value, but cap it
            return min(retry_after, self.MAX_RETRY_DELAY)

        # Exponential backoff: base_delay * 2^attempt
        delay = self.BASE_RETRY_DELAY * (2 ** attempt)
        delay = min(delay, self.MAX_RETRY_DELAY)

        # Add jitter (±25%) to prevent thundering herd
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0.1, delay + jitter)

    async def _make_request(
        self,
        method: str,
        url: str,
        token: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Make HTTP request with automatic retries.

        Features:
        - Connection pooling via shared client
        - Automatic retries with exponential backoff
        - Rate limit (429) handling with Retry-After header
        - Configurable timeouts

        Args:
            method: HTTP method
            url: Full URL
            token: Bot token
            json: Optional JSON payload

        Returns:
            httpx.Response

        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        last_error: Optional[Exception] = None
        headers = {"Authorization": f"Bot {token}"}

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                client = await self._get_client()

                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                )

                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = None
                    retry_after_header = response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            retry_after = float(retry_after_header)
                        except ValueError:
                            pass

                    if attempt < self.MAX_RETRIES:
                        delay = self._calculate_retry_delay(attempt, retry_after)
                        logger.warning(
                            f"Discord rate limited on {method} {url}, "
                            f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Check for server errors that should be retried
                if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Discord API returned {response.status_code} for {method} {url}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue

                return response

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Discord connection error: {str(e)}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during Discord API request: {str(e)}")
                raise

        # Should not reach here, but just in case
        raise last_error or httpx.HTTPError(f"Request failed after {self.MAX_RETRIES + 1} attempts")

    async def validate_credentials(self) -> bool:
        """Validate Discord credentials by getting current user."""
        token = self.get_bot_token()
        if not token:
            return False

        try:
            response = await self._make_request(
                method="GET",
                url=f"{DISCORD_API_BASE}/users/@me",
                token=token,
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Discord credential validation failed: {e}")
            return False

    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Return list of available Discord actions."""
        return [
            {
                "name": "send_message",
                "display_name": "Send Message",
                "description": "Send a message to a Discord channel",
                "input_schema": {
                    "type": "object",
                    "required": ["channel_id", "content"],
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Channel ID to send message to",
                        },
                        "content": {
                            "type": "string",
                            "description": "Message content (max 2000 chars)",
                        },
                        "tts": {
                            "type": "boolean",
                            "description": "Text-to-speech message",
                            "default": False,
                        },
                    },
                },
            },
            {
                "name": "send_embed",
                "display_name": "Send Embed",
                "description": "Send a rich embed message",
                "input_schema": {
                    "type": "object",
                    "required": ["channel_id", "title"],
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Channel ID",
                        },
                        "title": {
                            "type": "string",
                            "description": "Embed title",
                        },
                        "description": {
                            "type": "string",
                            "description": "Embed description",
                        },
                        "color": {
                            "type": "integer",
                            "description": "Embed color (decimal)",
                        },
                        "url": {
                            "type": "string",
                            "description": "URL for the title",
                        },
                    },
                },
            },
            {
                "name": "create_channel",
                "display_name": "Create Channel",
                "description": "Create a new channel in a server",
                "input_schema": {
                    "type": "object",
                    "required": ["guild_id", "name"],
                    "properties": {
                        "guild_id": {
                            "type": "string",
                            "description": "Server (guild) ID",
                        },
                        "name": {
                            "type": "string",
                            "description": "Channel name",
                        },
                        "type": {
                            "type": "integer",
                            "description": "Channel type (0=text, 2=voice)",
                            "default": 0,
                        },
                        "topic": {
                            "type": "string",
                            "description": "Channel topic",
                        },
                    },
                },
            },
            {
                "name": "list_channels",
                "display_name": "List Channels",
                "description": "List channels in a server",
                "input_schema": {
                    "type": "object",
                    "required": ["guild_id"],
                    "properties": {
                        "guild_id": {
                            "type": "string",
                            "description": "Server (guild) ID",
                        },
                    },
                },
            },
            {
                "name": "get_guild_info",
                "display_name": "Get Server Info",
                "description": "Get information about a Discord server",
                "input_schema": {
                    "type": "object",
                    "required": ["guild_id"],
                    "properties": {
                        "guild_id": {
                            "type": "string",
                            "description": "Server (guild) ID",
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
                    "required": ["channel_id", "message_id", "emoji"],
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Channel ID",
                        },
                        "message_id": {
                            "type": "string",
                            "description": "Message ID",
                        },
                        "emoji": {
                            "type": "string",
                            "description": "Emoji (unicode or custom format)",
                        },
                    },
                },
            },
            {
                "name": "create_thread",
                "display_name": "Create Thread",
                "description": "Create a thread from a message",
                "input_schema": {
                    "type": "object",
                    "required": ["channel_id", "message_id", "name"],
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Channel ID",
                        },
                        "message_id": {
                            "type": "string",
                            "description": "Message ID to start thread from",
                        },
                        "name": {
                            "type": "string",
                            "description": "Thread name",
                        },
                    },
                },
            },
            {
                "name": "get_user",
                "display_name": "Get User",
                "description": "Get user information",
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
                "description": "Test the Discord connection",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute a Discord action."""
        start_time = datetime.utcnow()

        token = self.get_bot_token()
        if not token:
            return IntegrationResult(
                success=False,
                error_message="No bot token available. Please provide Discord bot token.",
                error_code="NO_TOKEN",
            )

        try:
            # Route to appropriate action handler
            if action_name == "send_message":
                result = await self._send_message(token, parameters)
            elif action_name == "send_embed":
                result = await self._send_embed(token, parameters)
            elif action_name == "create_channel":
                result = await self._create_channel(token, parameters)
            elif action_name == "list_channels":
                result = await self._list_channels(token, parameters)
            elif action_name == "get_guild_info":
                result = await self._get_guild_info(token, parameters)
            elif action_name == "add_reaction":
                result = await self._add_reaction(token, parameters)
            elif action_name == "create_thread":
                result = await self._create_thread(token, parameters)
            elif action_name == "get_user":
                result = await self._get_user(token, parameters)
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
            logger.error(f"Discord action {action_name} failed: {e}")
            end_time = datetime.utcnow()
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                duration_ms=(end_time - start_time).total_seconds() * 1000,
            )

    async def _send_message(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Send a message to a channel."""
        try:
            response = await self._make_request(
                method="POST",
                url=f"{DISCORD_API_BASE}/channels/{params['channel_id']}/messages",
                token=token,
                json={
                    "content": params["content"],
                    "tts": params.get("tts", False),
                },
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "message_id": data.get("id"),
                        "channel_id": data.get("channel_id"),
                        "content": data.get("content"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(data.get("code", response.status_code)),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def _send_embed(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Send a rich embed message."""
        embed = {
            "title": params["title"],
            "description": params.get("description"),
            "color": params.get("color", 0x7289DA),
            "url": params.get("url"),
        }

        try:
            response = await self._make_request(
                method="POST",
                url=f"{DISCORD_API_BASE}/channels/{params['channel_id']}/messages",
                token=token,
                json={"embeds": [embed]},
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={"message_id": data.get("id")},
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(data.get("code", response.status_code)),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Failed to send Discord embed: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def _create_channel(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new channel."""
        try:
            response = await self._make_request(
                method="POST",
                url=f"{DISCORD_API_BASE}/guilds/{params['guild_id']}/channels",
                token=token,
                json={
                    "name": params["name"],
                    "type": params.get("type", 0),
                    "topic": params.get("topic"),
                },
            )

            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "channel_id": data.get("id"),
                        "channel_name": data.get("name"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(data.get("code", response.status_code)),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Failed to create Discord channel: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def _list_channels(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """List channels in a guild."""
        try:
            response = await self._make_request(
                method="GET",
                url=f"{DISCORD_API_BASE}/guilds/{params['guild_id']}/channels",
                token=token,
            )

            if response.status_code == 200:
                data = response.json()
                channels = [
                    {
                        "id": ch["id"],
                        "name": ch["name"],
                        "type": ch["type"],
                        "position": ch.get("position"),
                    }
                    for ch in data
                ]
                return IntegrationResult(
                    success=True,
                    data={"channels": channels, "count": len(channels)},
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(data.get("code", response.status_code)),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Failed to list Discord channels: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def _get_guild_info(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Get guild information."""
        try:
            response = await self._make_request(
                method="GET",
                url=f"{DISCORD_API_BASE}/guilds/{params['guild_id']}",
                token=token,
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "icon": data.get("icon"),
                        "owner_id": data.get("owner_id"),
                        "member_count": data.get("approximate_member_count"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(data.get("code", response.status_code)),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Failed to get Discord guild info: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def _add_reaction(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Add a reaction to a message."""
        import urllib.parse
        emoji = urllib.parse.quote(params["emoji"])

        try:
            response = await self._make_request(
                method="PUT",
                url=f"{DISCORD_API_BASE}/channels/{params['channel_id']}/messages/{params['message_id']}/reactions/{emoji}/@me",
                token=token,
            )

            if response.status_code == 204:
                return IntegrationResult(success=True, data={"added": True})
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Failed to add Discord reaction: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def _create_thread(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Create a thread from a message."""
        try:
            response = await self._make_request(
                method="POST",
                url=f"{DISCORD_API_BASE}/channels/{params['channel_id']}/messages/{params['message_id']}/threads",
                token=token,
                json={"name": params["name"]},
            )

            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "thread_id": data.get("id"),
                        "thread_name": data.get("name"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(data.get("code", response.status_code)),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Failed to create Discord thread: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def _get_user(self, token: str, params: Dict[str, Any]) -> IntegrationResult:
        """Get user information."""
        try:
            response = await self._make_request(
                method="GET",
                url=f"{DISCORD_API_BASE}/users/{params['user_id']}",
                token=token,
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "id": data.get("id"),
                        "username": data.get("username"),
                        "discriminator": data.get("discriminator"),
                        "global_name": data.get("global_name"),
                        "avatar": data.get("avatar"),
                        "bot": data.get("bot", False),
                    },
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Unknown error"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Failed to get Discord user: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def test_connection(self) -> IntegrationResult:
        """Test Discord connection by fetching bot user info."""
        token = self.get_bot_token()
        if not token:
            return IntegrationResult(
                success=False,
                error_message="No bot token available",
                error_code="NO_TOKEN",
            )

        try:
            response = await self._make_request(
                method="GET",
                url=f"{DISCORD_API_BASE}/users/@me",
                token=token,
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "bot_id": data.get("id"),
                        "username": data.get("username"),
                        "discriminator": data.get("discriminator"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Failed to connect"),
                    error_code=str(response.status_code),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Discord connection test failed: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )
