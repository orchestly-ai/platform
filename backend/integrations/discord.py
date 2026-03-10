"""
Discord Integration - FULLY IMPLEMENTED

Real Discord API integration for bot operations.

Supported Actions:
- send_message: Send message to channel
- create_channel: Create new channel in guild
- list_channels: List guild channels
- list_members: List guild members
- delete_message: Delete a message
- add_reaction: Add reaction to message
- create_thread: Create thread from message

Authentication: Bot Token
API Docs: https://discord.com/developers/docs/intro
"""

import asyncio
import random
import logging
import aiohttp
from typing import Dict, Any, List, Optional, ClassVar
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

logger = logging.getLogger(__name__)


class DiscordIntegration(BaseIntegration):
    """Discord integration with real Discord API.

    Features resilient connection handling:
    - Connection pooling via shared ClientSession
    - Automatic retries with exponential backoff
    - Rate limit (429) handling with Retry-After
    - Configurable timeouts
    """

    API_BASE_URL = "https://discord.com/api/v10"

    # Shared session for connection pooling (class-level)
    _session: ClassVar[Optional[aiohttp.ClientSession]] = None
    _session_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 30.0  # seconds
    REQUEST_TIMEOUT = 30  # seconds

    # Status codes that should trigger retries
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "discord"

    @property
    def display_name(self) -> str:
        return "Discord"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.BEARER_TOKEN

    @property
    def supported_actions(self) -> List[str]:
        return [
            "send_message",
            "create_channel",
            "list_channels",
            "list_members",
            "delete_message",
            "add_reaction",
            "create_thread",
        ]

    def _validate_credentials(self) -> None:
        """Validate Discord credentials."""
        super()._validate_credentials()

        if "bot_token" not in self.auth_credentials:
            raise IntegrationError(
                "Discord requires 'bot_token'",
                code="MISSING_TOKEN",
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Discord API."""
        return {
            "Authorization": f"Bot {self.auth_credentials['bot_token']}",
            "Content-Type": "application/json",
        }

    @classmethod
    async def _get_session(cls) -> aiohttp.ClientSession:
        """Get or create shared ClientSession with connection pooling."""
        async with cls._session_lock:
            if cls._session is None or cls._session.closed:
                # Create session with connection pooling and timeouts
                timeout = aiohttp.ClientTimeout(
                    total=cls.REQUEST_TIMEOUT,
                    connect=10,
                    sock_read=cls.REQUEST_TIMEOUT,
                )
                connector = aiohttp.TCPConnector(
                    limit=100,  # Max connections in pool
                    limit_per_host=20,  # Max connections per host
                    keepalive_timeout=30,  # Keep connections alive
                    enable_cleanup_closed=True,
                )
                cls._session = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                )
                logger.info("Created new Discord API session with connection pooling")
            return cls._session

    @classmethod
    async def close_session(cls):
        """Close the shared session (call on application shutdown)."""
        async with cls._session_lock:
            if cls._session and not cls._session.closed:
                await cls._session.close()
                cls._session = None
                logger.info("Closed Discord API session")

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
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Discord API with automatic retries.

        Features:
        - Connection pooling via shared session
        - Automatic retries with exponential backoff
        - Rate limit (429) handling with Retry-After header
        - Configurable timeouts

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint (e.g., '/channels/{channel_id}/messages')
            data: Request payload

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails after all retries
        """
        url = f"{self.API_BASE_URL}{endpoint}"
        last_error: Optional[Exception] = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                session = await self._get_session()

                kwargs: Dict[str, Any] = {
                    "method": method,
                    "url": url,
                    "headers": self._get_headers(),
                }
                if data:
                    kwargs["json"] = data

                async with session.request(**kwargs) as response:
                    # Handle different response types
                    if response.status == 204:  # No content
                        return {"success": True}

                    # Check for rate limiting
                    if response.status == 429:
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
                                f"Discord rate limited on {method} {endpoint}, "
                                f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                            )
                            await asyncio.sleep(delay)
                            continue

                    # Check for server errors that should be retried
                    if response.status in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                        delay = self._calculate_retry_delay(attempt)
                        logger.warning(
                            f"Discord API returned {response.status} for {method} {endpoint}, "
                            f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Try to parse response
                    try:
                        response_data = await response.json()
                    except Exception:
                        response_data = {"raw_text": await response.text()}

                    if response.status >= 400:
                        error_msg = response_data.get("message", "Unknown error")
                        error_code = str(response_data.get("code", "UNKNOWN"))
                        raise IntegrationError(
                            f"Discord API error: {error_msg}",
                            code=error_code,
                            status_code=response.status,
                            details=response_data,
                        )

                    return response_data

            except aiohttp.ClientError as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Discord connection error: {str(e)}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise IntegrationError(
                    f"HTTP request failed after {self.MAX_RETRIES + 1} attempts: {str(e)}",
                    code="HTTP_ERROR",
                )
            except asyncio.TimeoutError as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Discord request timeout for {method} {endpoint}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise IntegrationError(
                    f"Request timed out after {self.MAX_RETRIES + 1} attempts",
                    code="TIMEOUT_ERROR",
                )
            except IntegrationError:
                raise
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during Discord API request: {str(e)}")
                raise IntegrationError(
                    f"Unexpected error: {str(e)}",
                    code="UNKNOWN_ERROR",
                )

        # Should not reach here, but just in case
        raise IntegrationError(
            f"Request failed after all retries: {str(last_error)}",
            code="MAX_RETRIES_EXCEEDED",
        )

    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
    ) -> IntegrationResult:
        """Execute Discord action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "send_message":
                result = await self._send_message(params)
            elif action == "create_channel":
                result = await self._create_channel(params)
            elif action == "list_channels":
                result = await self._list_channels(params)
            elif action == "list_members":
                result = await self._list_members(params)
            elif action == "delete_message":
                result = await self._delete_message(params)
            elif action == "add_reaction":
                result = await self._add_reaction(params)
            elif action == "create_thread":
                result = await self._create_thread(params)
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
        """Test Discord connection using /users/@me endpoint."""
        try:
            response = await self._make_request("GET", "/users/@me")
            return IntegrationResult(
                success=True,
                data={
                    "bot_id": response.get("id"),
                    "username": response.get("username"),
                    "discriminator": response.get("discriminator"),
                    "verified": response.get("verified"),
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
        Send message to Discord channel.

        Required params:
            channel_id: Channel ID
            content: Message content (up to 2000 chars)

        Optional params:
            tts: Text-to-speech (default: False)
            embeds: List of embed objects
            allowed_mentions: Allowed mentions configuration
            message_reference: Reference to reply to
        """
        channel_id = params.get("channel_id")
        content = params.get("content")

        if not channel_id:
            raise IntegrationError("Missing required parameter: 'channel_id'", code="MISSING_PARAMS")

        if not content and not params.get("embeds"):
            raise IntegrationError(
                "Missing required parameter: 'content' or 'embeds'",
                code="MISSING_PARAMS",
            )

        payload = {}
        if content:
            payload["content"] = content[:2000]  # Discord limit

        if "tts" in params:
            payload["tts"] = params["tts"]
        if "embeds" in params:
            payload["embeds"] = params["embeds"]
        if "allowed_mentions" in params:
            payload["allowed_mentions"] = params["allowed_mentions"]
        if "message_reference" in params:
            payload["message_reference"] = params["message_reference"]

        endpoint = f"/channels/{channel_id}/messages"
        response = await self._make_request("POST", endpoint, payload)

        return IntegrationResult(
            success=True,
            data={
                "message_id": response.get("id"),
                "channel_id": response.get("channel_id"),
                "timestamp": response.get("timestamp"),
                "content": response.get("content"),
            },
        )

    async def _create_channel(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create new channel in a guild.

        Required params:
            guild_id: Guild (server) ID
            name: Channel name

        Optional params:
            type: Channel type (0=text, 2=voice, 4=category, 5=announcement, 13=stage, 15=forum)
            topic: Channel topic
            parent_id: Category ID
            nsfw: NSFW channel (default: False)
            position: Sorting position
        """
        guild_id = params.get("guild_id")
        name = params.get("name")

        if not guild_id or not name:
            raise IntegrationError(
                "Missing required parameters: 'guild_id' and 'name'",
                code="MISSING_PARAMS",
            )

        payload = {
            "name": name,
            "type": params.get("type", 0),  # Default to text channel
        }

        if "topic" in params:
            payload["topic"] = params["topic"]
        if "parent_id" in params:
            payload["parent_id"] = params["parent_id"]
        if "nsfw" in params:
            payload["nsfw"] = params["nsfw"]
        if "position" in params:
            payload["position"] = params["position"]

        endpoint = f"/guilds/{guild_id}/channels"
        response = await self._make_request("POST", endpoint, payload)

        return IntegrationResult(
            success=True,
            data={
                "channel_id": response.get("id"),
                "name": response.get("name"),
                "type": response.get("type"),
                "guild_id": response.get("guild_id"),
            },
        )

    async def _list_channels(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List all channels in a guild.

        Required params:
            guild_id: Guild (server) ID
        """
        guild_id = params.get("guild_id")
        if not guild_id:
            raise IntegrationError("Missing required parameter: 'guild_id'", code="MISSING_PARAMS")

        endpoint = f"/guilds/{guild_id}/channels"
        response = await self._make_request("GET", endpoint)

        # Discord returns a list directly
        channels = [
            {
                "id": ch.get("id"),
                "name": ch.get("name"),
                "type": ch.get("type"),
                "position": ch.get("position"),
                "parent_id": ch.get("parent_id"),
                "topic": ch.get("topic"),
            }
            for ch in response
        ] if isinstance(response, list) else []

        return IntegrationResult(
            success=True,
            data={
                "channels": channels,
                "total": len(channels),
            },
        )

    async def _list_members(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List members of a guild.

        Required params:
            guild_id: Guild (server) ID

        Optional params:
            limit: Max members to return (1-1000, default: 100)
            after: User ID to list members after
        """
        guild_id = params.get("guild_id")
        if not guild_id:
            raise IntegrationError("Missing required parameter: 'guild_id'", code="MISSING_PARAMS")

        limit = params.get("limit", 100)
        endpoint = f"/guilds/{guild_id}/members?limit={limit}"

        if "after" in params:
            endpoint += f"&after={params['after']}"

        response = await self._make_request("GET", endpoint)

        # Discord returns a list directly
        members = [
            {
                "user_id": member.get("user", {}).get("id"),
                "username": member.get("user", {}).get("username"),
                "nick": member.get("nick"),
                "joined_at": member.get("joined_at"),
                "roles": member.get("roles", []),
                "is_bot": member.get("user", {}).get("bot", False),
            }
            for member in response
        ] if isinstance(response, list) else []

        return IntegrationResult(
            success=True,
            data={
                "members": members,
                "total": len(members),
            },
        )

    async def _delete_message(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Delete a message.

        Required params:
            channel_id: Channel ID
            message_id: Message ID
        """
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")

        if not channel_id or not message_id:
            raise IntegrationError(
                "Missing required parameters: 'channel_id' and 'message_id'",
                code="MISSING_PARAMS",
            )

        endpoint = f"/channels/{channel_id}/messages/{message_id}"
        await self._make_request("DELETE", endpoint)

        return IntegrationResult(
            success=True,
            data={
                "deleted": True,
                "message_id": message_id,
                "channel_id": channel_id,
            },
        )

    async def _add_reaction(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Add reaction to a message.

        Required params:
            channel_id: Channel ID
            message_id: Message ID
            emoji: Emoji (e.g., '👍' or 'custom_emoji:123456')
        """
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        emoji = params.get("emoji")

        if not channel_id or not message_id or not emoji:
            raise IntegrationError(
                "Missing required parameters: 'channel_id', 'message_id', and 'emoji'",
                code="MISSING_PARAMS",
            )

        # URL encode the emoji
        import urllib.parse
        encoded_emoji = urllib.parse.quote(emoji)

        endpoint = f"/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me"
        await self._make_request("PUT", endpoint)

        return IntegrationResult(
            success=True,
            data={
                "added": True,
                "emoji": emoji,
                "message_id": message_id,
            },
        )

    async def _create_thread(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create thread from a message.

        Required params:
            channel_id: Channel ID
            message_id: Message ID to create thread from
            name: Thread name

        Optional params:
            auto_archive_duration: Minutes until auto-archive (60, 1440, 4320, 10080)
        """
        channel_id = params.get("channel_id")
        message_id = params.get("message_id")
        name = params.get("name")

        if not channel_id or not message_id or not name:
            raise IntegrationError(
                "Missing required parameters: 'channel_id', 'message_id', and 'name'",
                code="MISSING_PARAMS",
            )

        payload = {
            "name": name,
            "auto_archive_duration": params.get("auto_archive_duration", 1440),
        }

        endpoint = f"/channels/{channel_id}/messages/{message_id}/threads"
        response = await self._make_request("POST", endpoint, payload)

        return IntegrationResult(
            success=True,
            data={
                "thread_id": response.get("id"),
                "name": response.get("name"),
                "parent_id": response.get("parent_id"),
                "owner_id": response.get("owner_id"),
            },
        )
