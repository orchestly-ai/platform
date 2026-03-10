"""
Tests for Session 3.8 Integrations: Intercom and Mailchimp

Run with: pytest test_integrations_session3_8.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from .intercom import IntercomIntegration
from .mailchimp import MailchimpIntegration
from .base import IntegrationError, IntegrationResult


# =============================================================================
# Intercom Integration Tests
# =============================================================================


class TestIntercomIntegration:
    """Tests for Intercom integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Intercom credentials."""
        return {
            "access_token": "dG9rOmFiY2RlZjEyMzQ1Njc4OTA=",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Intercom integration instance."""
        return IntercomIntegration(valid_credentials)

    def test_init(self, integration):
        """Test Intercom integration initialization."""
        assert integration.name == "intercom"
        assert integration.display_name == "Intercom"
        assert len(integration.supported_actions) == 10

    def test_missing_access_token(self):
        """Test missing access token raises error."""
        with pytest.raises(IntegrationError) as exc:
            IntercomIntegration({})
        assert "credentials" in str(exc.value).lower() or "access_token" in str(exc.value)

    def test_headers(self, integration):
        """Test request headers."""
        headers = integration._get_headers()
        assert "Bearer" in headers["Authorization"]
        assert headers["Intercom-Version"] == "2.10"

    @pytest.mark.asyncio
    async def test_list_contacts(self, integration):
        """Test list_contacts action."""
        mock_response = {
            "type": "list",
            "data": [
                {"id": "1", "email": "user1@test.com", "role": "user"},
                {"id": "2", "email": "user2@test.com", "role": "lead"},
            ],
            "total_count": 2,
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_contacts", {"per_page": 50})

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_contact(self, integration):
        """Test get_contact action."""
        mock_response = {"id": "123", "email": "user@test.com", "name": "Test User"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("get_contact", {"contact_id": "123"})

        assert result.success
        assert result.data["contact"]["id"] == "123"

    @pytest.mark.asyncio
    async def test_create_contact(self, integration):
        """Test create_contact action."""
        mock_response = {"id": "456", "email": "new@test.com", "role": "user"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "create_contact",
                {"role": "user", "email": "new@test.com", "name": "New User"},
            )

        assert result.success
        assert result.data["contact_id"] == "456"

    @pytest.mark.asyncio
    async def test_update_contact(self, integration):
        """Test update_contact action."""
        mock_response = {"id": "123", "email": "updated@test.com", "name": "Updated User"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "update_contact",
                {"contact_id": "123", "name": "Updated User"},
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_list_conversations(self, integration):
        """Test list_conversations action."""
        mock_response = {
            "type": "conversation.list",
            "conversations": [
                {"id": "conv1", "state": "open"},
                {"id": "conv2", "state": "closed"},
            ],
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_conversations", {})

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_conversation(self, integration):
        """Test get_conversation action."""
        mock_response = {"id": "conv123", "state": "open", "source": {"type": "conversation"}}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "get_conversation",
                {"conversation_id": "conv123"},
            )

        assert result.success
        assert result.data["conversation"]["id"] == "conv123"

    @pytest.mark.asyncio
    async def test_reply_conversation(self, integration):
        """Test reply_conversation action."""
        mock_response = {"id": "conv123", "state": "open"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "reply_conversation",
                {
                    "conversation_id": "conv123",
                    "body": "Thank you for contacting us!",
                    "message_type": "comment",
                    "admin_id": "admin1",
                },
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_create_message(self, integration):
        """Test create_message action."""
        mock_response = {"id": "msg123", "type": "inapp"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "create_message",
                {
                    "from_admin_id": "admin1",
                    "to_contact_id": "contact1",
                    "body": "Hello! How can I help you?",
                },
            )

        assert result.success
        assert result.data["message_id"] == "msg123"

    @pytest.mark.asyncio
    async def test_list_companies(self, integration):
        """Test list_companies action."""
        mock_response = {
            "type": "list",
            "data": [
                {"id": "comp1", "name": "Company 1"},
                {"id": "comp2", "name": "Company 2"},
            ],
            "total_count": 2,
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_companies", {})

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_create_company(self, integration):
        """Test create_company action."""
        mock_response = {"id": "comp123", "company_id": "ext-123", "name": "New Company"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "create_company",
                {"company_id": "ext-123", "name": "New Company", "industry": "Technology"},
            )

        assert result.success
        assert result.data["id"] == "comp123"

    @pytest.mark.asyncio
    async def test_missing_contact_id(self, integration):
        """Test missing contact_id parameter."""
        result = await integration.execute_action("get_contact", {})
        assert not result.success
        assert "contact_id" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_role(self, integration):
        """Test missing role for create_contact."""
        result = await integration.execute_action("create_contact", {"email": "test@test.com"})
        assert not result.success
        assert "role" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_test_connection(self, integration):
        """Test connection testing."""
        mock_response = {
            "id": "admin123",
            "name": "Test Admin",
            "app": {"id_code": "abc123"},
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.test_connection()

        assert result.success
        assert result.data["connected"]
        assert result.data["admin_id"] == "admin123"


# =============================================================================
# Mailchimp Integration Tests
# =============================================================================


class TestMailchimpIntegration:
    """Tests for Mailchimp integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Mailchimp credentials."""
        return {
            "api_key": "abc123def456ghi789-us21",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Mailchimp integration instance."""
        return MailchimpIntegration(valid_credentials)

    def test_init(self, integration):
        """Test Mailchimp integration initialization."""
        assert integration.name == "mailchimp"
        assert integration.display_name == "Mailchimp"
        assert len(integration.supported_actions) == 10

    def test_missing_api_key(self):
        """Test missing API key raises error."""
        with pytest.raises(IntegrationError) as exc:
            MailchimpIntegration({})
        assert "credentials" in str(exc.value).lower() or "api_key" in str(exc.value)

    def test_invalid_api_key_format(self):
        """Test invalid API key format raises error."""
        with pytest.raises(IntegrationError) as exc:
            MailchimpIntegration({"api_key": "nodatacentersuffix"})
        assert "datacenter" in str(exc.value).lower()

    def test_datacenter_extraction(self, integration):
        """Test datacenter extraction from API key."""
        dc = integration._get_datacenter()
        assert dc == "us21"

    def test_base_url(self, integration):
        """Test base URL generation."""
        url = integration._get_base_url()
        assert "us21.api.mailchimp.com" in url
        assert "/3.0" in url

    def test_subscriber_hash(self):
        """Test subscriber hash generation."""
        hash_result = MailchimpIntegration._get_subscriber_hash("test@example.com")
        assert len(hash_result) == 32  # MD5 hash length

    @pytest.mark.asyncio
    async def test_list_audiences(self, integration):
        """Test list_audiences action."""
        mock_response = {
            "lists": [
                {"id": "list1", "name": "Newsletter"},
                {"id": "list2", "name": "Promotions"},
            ],
            "total_items": 2,
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_audiences", {})

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_audience(self, integration):
        """Test get_audience action."""
        mock_response = {"id": "list123", "name": "Newsletter", "stats": {"member_count": 1000}}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("get_audience", {"list_id": "list123"})

        assert result.success
        assert result.data["audience"]["id"] == "list123"

    @pytest.mark.asyncio
    async def test_list_members(self, integration):
        """Test list_members action."""
        mock_response = {
            "members": [
                {"id": "mem1", "email_address": "user1@test.com", "status": "subscribed"},
                {"id": "mem2", "email_address": "user2@test.com", "status": "subscribed"},
            ],
            "total_items": 2,
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "list_members",
                {"list_id": "list123", "status": "subscribed"},
            )

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_member(self, integration):
        """Test get_member action."""
        mock_response = {
            "id": "mem123",
            "email_address": "user@test.com",
            "status": "subscribed",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "get_member",
                {"list_id": "list123", "email": "user@test.com"},
            )

        assert result.success
        assert result.data["member"]["email_address"] == "user@test.com"

    @pytest.mark.asyncio
    async def test_add_member(self, integration):
        """Test add_member action."""
        mock_response = {
            "id": "mem456",
            "email_address": "new@test.com",
            "status": "subscribed",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "add_member",
                {
                    "list_id": "list123",
                    "email": "new@test.com",
                    "status": "subscribed",
                    "merge_fields": {"FNAME": "John", "LNAME": "Doe"},
                },
            )

        assert result.success
        assert result.data["member_id"] == "mem456"

    @pytest.mark.asyncio
    async def test_update_member(self, integration):
        """Test update_member action."""
        mock_response = {
            "id": "mem123",
            "email_address": "user@test.com",
            "status": "unsubscribed",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "update_member",
                {"list_id": "list123", "email": "user@test.com", "status": "unsubscribed"},
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_list_campaigns(self, integration):
        """Test list_campaigns action."""
        mock_response = {
            "campaigns": [
                {"id": "camp1", "type": "regular", "status": "sent"},
                {"id": "camp2", "type": "regular", "status": "save"},
            ],
            "total_items": 2,
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("list_campaigns", {"status": "sent"})

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_campaign(self, integration):
        """Test get_campaign action."""
        mock_response = {
            "id": "camp123",
            "type": "regular",
            "status": "sent",
            "settings": {"subject_line": "Hello!"},
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action("get_campaign", {"campaign_id": "camp123"})

        assert result.success
        assert result.data["campaign"]["id"] == "camp123"

    @pytest.mark.asyncio
    async def test_create_campaign(self, integration):
        """Test create_campaign action."""
        mock_response = {"id": "camp456", "type": "regular", "status": "save"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "create_campaign",
                {
                    "type": "regular",
                    "list_id": "list123",
                    "subject_line": "Monthly Newsletter",
                    "from_name": "Company",
                    "reply_to": "news@company.com",
                },
            )

        assert result.success
        assert result.data["campaign_id"] == "camp456"

    @pytest.mark.asyncio
    async def test_send_campaign(self, integration):
        """Test send_campaign action."""
        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = {}
            result = await integration.execute_action("send_campaign", {"campaign_id": "camp123"})

        assert result.success
        assert result.data["sent"]

    @pytest.mark.asyncio
    async def test_missing_list_id(self, integration):
        """Test missing list_id parameter."""
        result = await integration.execute_action("list_members", {})
        assert not result.success
        assert "list_id" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_email_for_add(self, integration):
        """Test missing email for add_member."""
        result = await integration.execute_action(
            "add_member",
            {"list_id": "list123", "status": "subscribed"},
        )
        assert not result.success
        assert "email" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_type_for_campaign(self, integration):
        """Test missing type for create_campaign."""
        result = await integration.execute_action(
            "create_campaign",
            {"list_id": "list123"},
        )
        assert not result.success
        assert "type" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_test_connection(self, integration):
        """Test connection testing."""
        mock_response = {
            "account_id": "abc123",
            "account_name": "Test Account",
            "email": "admin@test.com",
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.test_connection()

        assert result.success
        assert result.data["connected"]
        assert result.data["account_id"] == "abc123"


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
