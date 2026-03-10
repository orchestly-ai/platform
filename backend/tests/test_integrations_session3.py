#!/usr/bin/env python3
"""
Tests for Session 3.1 Integrations: Microsoft Teams and Discord

Tests verify:
- Integration initialization and credential validation
- Action routing and parameter validation
- Error handling
- Response parsing
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from backend.integrations.base import (
    BaseIntegration,
    IntegrationResult,
    IntegrationError,
    AuthType,
)
from backend.integrations.microsoft_teams import MicrosoftTeamsIntegration
from backend.integrations.discord import DiscordIntegration


# ============================================================================
# Microsoft Teams Integration Tests
# ============================================================================

class TestMicrosoftTeamsIntegration:
    """Tests for Microsoft Teams integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid OAuth credentials."""
        return {"access_token": "test-access-token-12345"}

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Teams integration instance."""
        return MicrosoftTeamsIntegration(auth_credentials=valid_credentials)

    def test_init_with_valid_credentials(self, integration):
        """Test initialization with valid credentials."""
        assert integration.name == "microsoft_teams"
        assert integration.display_name == "Microsoft Teams"
        assert integration.auth_type == AuthType.OAUTH2

    def test_init_missing_token(self):
        """Test initialization without access token or app credentials."""
        with pytest.raises(IntegrationError) as exc:
            MicrosoftTeamsIntegration(auth_credentials={"other": "value"})

        assert "client_id" in str(exc.value) or "access_token" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "send_message" in actions
        assert "create_channel" in actions
        assert "list_channels" in actions
        assert "list_teams" in actions
        assert "create_meeting" in actions
        assert "get_user" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("send_message")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")

        assert "not supported" in str(exc.value)

    @pytest.mark.asyncio
    async def test_send_message_missing_params(self, integration):
        """Test send_message with missing parameters."""
        result = await integration.execute_action(
            "send_message",
            {"content": "Hello"}  # Missing team_id/channel_id or chat_id
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_send_message_missing_content(self, integration):
        """Test send_message without content."""
        result = await integration.execute_action(
            "send_message",
            {"team_id": "123", "channel_id": "456"}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_create_channel_missing_params(self, integration):
        """Test create_channel with missing parameters."""
        result = await integration.execute_action(
            "create_channel",
            {"team_id": "123"}  # Missing display_name
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_channels_missing_team_id(self, integration):
        """Test list_channels without team_id."""
        result = await integration.execute_action(
            "list_channels",
            {}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_list_teams(self, integration):
        """Test list_teams is a supported action."""
        assert "list_teams" in integration.supported_actions

    @pytest.mark.asyncio
    async def test_create_meeting_missing_subject(self, integration):
        """Test create_meeting without subject."""
        result = await integration.execute_action(
            "create_meeting",
            {}
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_send_message_success(self, integration):
        """Test successful message sending."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json = MagicMock(return_value={
            "id": "msg-123",
            "createdDateTime": "2025-01-01T12:00:00Z",
            "webUrl": "https://teams.microsoft.com/...",
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(MicrosoftTeamsIntegration, '_get_client', return_value=mock_client):
            result = await integration.execute_action(
                "send_message",
                {
                    "team_id": "team-123",
                    "channel_id": "channel-456",
                    "content": "Hello Teams!",
                }
            )

        assert result.success is True
        assert result.data["message_id"] == "msg-123"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, integration):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={
            "id": "user-123",
            "displayName": "Test User",
            "mail": "test@example.com",
        })

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch.object(MicrosoftTeamsIntegration, '_get_client', return_value=mock_client):
            result = await integration.test_connection()

        assert result.success is True
        assert result.data["user_id"] == "user-123"

    def test_auth_token_present(self, integration):
        """Test that access token is available for API calls."""
        assert integration.auth_credentials.get("access_token") == "test-access-token-12345"


# ============================================================================
# Discord Integration Tests
# ============================================================================

class TestDiscordIntegration:
    """Tests for Discord integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid bot token credentials."""
        return {"bot_token": "test-bot-token-12345"}

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Discord integration instance."""
        return DiscordIntegration(auth_credentials=valid_credentials)

    def test_init_with_valid_credentials(self, integration):
        """Test initialization with valid credentials."""
        assert integration.name == "discord"
        assert integration.display_name == "Discord"
        assert integration.auth_type == AuthType.BEARER_TOKEN

    def test_init_missing_token(self):
        """Test initialization without bot token."""
        with pytest.raises(IntegrationError) as exc:
            DiscordIntegration(auth_credentials={"other": "value"})

        assert "bot_token" in str(exc.value)

    def test_supported_actions(self, integration):
        """Test supported actions list."""
        actions = integration.supported_actions

        assert "send_message" in actions
        assert "create_channel" in actions
        assert "list_channels" in actions
        assert "list_members" in actions
        assert "delete_message" in actions
        assert "add_reaction" in actions
        assert "create_thread" in actions

    def test_validate_action_valid(self, integration):
        """Test action validation for valid action."""
        integration._validate_action("send_message")  # Should not raise

    def test_validate_action_invalid(self, integration):
        """Test action validation for invalid action."""
        with pytest.raises(IntegrationError) as exc:
            integration._validate_action("invalid_action")

        assert "not supported" in str(exc.value)

    @pytest.mark.asyncio
    async def test_send_message_missing_channel(self, integration):
        """Test send_message without channel_id."""
        result = await integration.execute_action(
            "send_message",
            {"content": "Hello"}
        )

        assert result.success is False
        assert "MISSING_PARAMS" in result.error_code

    @pytest.mark.asyncio
    async def test_send_message_missing_content(self, integration):
        """Test send_message without content or embeds."""
        result = await integration.execute_action(
            "send_message",
            {"channel_id": "123"}
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_create_channel_missing_params(self, integration):
        """Test create_channel with missing parameters."""
        result = await integration.execute_action(
            "create_channel",
            {"guild_id": "123"}  # Missing name
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_channels_missing_guild(self, integration):
        """Test list_channels without guild_id."""
        result = await integration.execute_action(
            "list_channels",
            {}
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_members_missing_guild(self, integration):
        """Test list_members without guild_id."""
        result = await integration.execute_action(
            "list_members",
            {}
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_delete_message_missing_params(self, integration):
        """Test delete_message without required params."""
        result = await integration.execute_action(
            "delete_message",
            {"channel_id": "123"}  # Missing message_id
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_add_reaction_missing_params(self, integration):
        """Test add_reaction without required params."""
        result = await integration.execute_action(
            "add_reaction",
            {"channel_id": "123", "message_id": "456"}  # Missing emoji
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_create_thread_missing_params(self, integration):
        """Test create_thread without required params."""
        result = await integration.execute_action(
            "create_thread",
            {"channel_id": "123", "message_id": "456"}  # Missing name
        )

        assert result.success is False

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_send_message_success(self, mock_session_class, integration):
        """Test successful message sending."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "msg-123",
            "channel_id": "channel-456",
            "timestamp": "2025-01-01T12:00:00.000Z",
            "content": "Hello Discord!",
        })

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(),
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_class.return_value = mock_session

        result = await integration.execute_action(
            "send_message",
            {
                "channel_id": "channel-456",
                "content": "Hello Discord!",
            }
        )

        assert result.success is True
        assert result.data["message_id"] == "msg-123"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_list_channels_success(self, mock_session_class, integration):
        """Test successful channel listing."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[
            {"id": "1", "name": "general", "type": 0, "position": 0},
            {"id": "2", "name": "random", "type": 0, "position": 1},
        ])

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(),
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_class.return_value = mock_session

        result = await integration.execute_action(
            "list_channels",
            {"guild_id": "guild-123"}
        )

        assert result.success is True
        assert result.data["total"] == 2

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_test_connection_success(self, mock_session_class, integration):
        """Test successful connection test."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "bot-123",
            "username": "TestBot",
            "discriminator": "1234",
            "verified": True,
        })

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(),
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_class.return_value = mock_session

        result = await integration.test_connection()

        assert result.success is True
        assert result.data["bot_id"] == "bot-123"

    def test_get_headers(self, integration):
        """Test that headers include bot token."""
        headers = integration._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bot ")
        assert "Content-Type" in headers

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_delete_message_success(self, mock_session_class, integration):
        """Test successful message deletion."""
        mock_response = AsyncMock()
        mock_response.status = 204  # No content

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(),
        ))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_class.return_value = mock_session

        result = await integration.execute_action(
            "delete_message",
            {"channel_id": "123", "message_id": "456"}
        )

        assert result.success is True
        assert result.data["deleted"] is True


# ============================================================================
# Base Integration Tests
# ============================================================================

class TestBaseIntegrationPattern:
    """Tests to verify integrations follow the base pattern."""

    def test_teams_is_base_integration(self):
        """Verify Teams inherits from BaseIntegration."""
        assert issubclass(MicrosoftTeamsIntegration, BaseIntegration)

    def test_discord_is_base_integration(self):
        """Verify Discord inherits from BaseIntegration."""
        assert issubclass(DiscordIntegration, BaseIntegration)

    def test_integration_result_structure(self):
        """Test IntegrationResult data class."""
        result = IntegrationResult(
            success=True,
            data={"key": "value"},
            duration_ms=150.5,
        )

        assert result.success is True
        assert result.data["key"] == "value"
        assert result.duration_ms == 150.5

    def test_integration_error_structure(self):
        """Test IntegrationError exception."""
        error = IntegrationError(
            message="Test error",
            code="TEST_CODE",
            status_code=400,
            details={"extra": "info"},
        )

        assert error.message == "Test error"
        assert error.code == "TEST_CODE"
        assert error.status_code == 400

    def test_auth_types(self):
        """Test AuthType enumeration."""
        assert AuthType.OAUTH2.value == "oauth2"
        assert AuthType.BEARER_TOKEN.value == "bearer_token"
        assert AuthType.API_KEY.value == "api_key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
