"""
Tests for Session 3.7 Integrations: Shopify and WooCommerce

Run with: pytest test_integrations_session3_7.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from .shopify import ShopifyIntegration
from .woocommerce import WooCommerceIntegration
from .base import IntegrationError, IntegrationResult


# =============================================================================
# Shopify Integration Tests
# =============================================================================


class TestShopifyIntegration:
    """Tests for Shopify integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid Shopify credentials."""
        return {
            "access_token": "shpat_test_token_12345",
            "store_domain": "mystore.myshopify.com",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create Shopify integration instance."""
        return ShopifyIntegration(valid_credentials)

    def test_init(self, integration):
        """Test Shopify integration initialization."""
        assert integration.name == "shopify"
        assert integration.display_name == "Shopify"
        assert len(integration.supported_actions) == 10

    def test_missing_access_token(self):
        """Test missing access token raises error."""
        with pytest.raises(IntegrationError) as exc:
            ShopifyIntegration({"store_domain": "store.myshopify.com"})
        assert "access_token" in str(exc.value)

    def test_missing_store_domain(self):
        """Test missing store domain raises error."""
        with pytest.raises(IntegrationError) as exc:
            ShopifyIntegration({"access_token": "token123"})
        assert "store_domain" in str(exc.value)

    def test_base_url(self, integration):
        """Test base URL generation."""
        url = integration._get_base_url()
        assert "mystore.myshopify.com" in url
        assert "admin/api/2024-01" in url

    def test_headers(self, integration):
        """Test request headers."""
        headers = integration._get_headers()
        assert headers["X-Shopify-Access-Token"] == "shpat_test_token_12345"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_list_products(self, integration):
        """Test list_products action."""
        mock_response = {
            "products": [
                {"id": 1, "title": "Product 1", "status": "active"},
                {"id": 2, "title": "Product 2", "status": "active"},
            ]
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "list_products",
                {"limit": 10, "status": "active"},
            )

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_product(self, integration):
        """Test get_product action."""
        mock_response = {
            "product": {"id": 123, "title": "Test Product", "vendor": "TestCo"}
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "get_product",
                {"product_id": 123},
            )

        assert result.success
        assert result.data["product"]["id"] == 123

    @pytest.mark.asyncio
    async def test_create_product(self, integration):
        """Test create_product action."""
        mock_response = {
            "product": {"id": 456, "title": "New Product"}
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "create_product",
                {"title": "New Product", "vendor": "TestCo", "product_type": "Widgets"},
            )

        assert result.success
        assert result.data["product_id"] == 456

    @pytest.mark.asyncio
    async def test_update_product(self, integration):
        """Test update_product action."""
        mock_response = {
            "product": {"id": 123, "title": "Updated Product"}
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "update_product",
                {"product_id": 123, "title": "Updated Product"},
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_list_orders(self, integration):
        """Test list_orders action."""
        mock_response = {
            "orders": [
                {"id": 1001, "total_price": "99.99", "financial_status": "paid"},
                {"id": 1002, "total_price": "149.99", "financial_status": "pending"},
            ]
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "list_orders",
                {"status": "open"},
            )

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_order(self, integration):
        """Test get_order action."""
        mock_response = {
            "order": {"id": 1001, "email": "customer@test.com", "total_price": "99.99"}
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "get_order",
                {"order_id": 1001},
            )

        assert result.success
        assert result.data["order"]["id"] == 1001

    @pytest.mark.asyncio
    async def test_update_order(self, integration):
        """Test update_order action."""
        mock_response = {
            "order": {"id": 1001, "note": "Rush order"}
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "update_order",
                {"order_id": 1001, "note": "Rush order"},
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_list_customers(self, integration):
        """Test list_customers action."""
        mock_response = {
            "customers": [
                {"id": 101, "email": "customer1@test.com"},
                {"id": 102, "email": "customer2@test.com"},
            ]
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "list_customers",
                {"limit": 50},
            )

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_customer(self, integration):
        """Test get_customer action."""
        mock_response = {
            "customer": {"id": 101, "email": "customer@test.com", "first_name": "John"}
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "get_customer",
                {"customer_id": 101},
            )

        assert result.success
        assert result.data["customer"]["email"] == "customer@test.com"

    @pytest.mark.asyncio
    async def test_create_customer(self, integration):
        """Test create_customer action."""
        mock_response = {
            "customer": {"id": 201, "email": "new@test.com", "first_name": "Jane"}
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "create_customer",
                {"email": "new@test.com", "first_name": "Jane", "last_name": "Doe"},
            )

        assert result.success
        assert result.data["customer_id"] == 201

    @pytest.mark.asyncio
    async def test_missing_product_id(self, integration):
        """Test missing product_id parameter."""
        result = await integration.execute_action("get_product", {})
        assert not result.success
        assert "product_id" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_title(self, integration):
        """Test missing title for create_product."""
        result = await integration.execute_action("create_product", {})
        assert not result.success
        assert "title" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_test_connection(self, integration):
        """Test connection testing."""
        mock_response = {
            "shop": {"name": "Test Store", "domain": "teststore.myshopify.com"}
        }

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.test_connection()

        assert result.success
        assert result.data["connected"]
        assert result.data["shop_name"] == "Test Store"


# =============================================================================
# WooCommerce Integration Tests
# =============================================================================


class TestWooCommerceIntegration:
    """Tests for WooCommerce integration."""

    @pytest.fixture
    def valid_credentials(self):
        """Valid WooCommerce credentials."""
        return {
            "consumer_key": "ck_test_key_12345",
            "consumer_secret": "cs_test_secret_67890",
            "store_url": "https://mystore.com",
        }

    @pytest.fixture
    def integration(self, valid_credentials):
        """Create WooCommerce integration instance."""
        return WooCommerceIntegration(valid_credentials)

    def test_init(self, integration):
        """Test WooCommerce integration initialization."""
        assert integration.name == "woocommerce"
        assert integration.display_name == "WooCommerce"
        assert len(integration.supported_actions) == 10

    def test_missing_consumer_key(self):
        """Test missing consumer key raises error."""
        with pytest.raises(IntegrationError) as exc:
            WooCommerceIntegration({
                "consumer_secret": "secret",
                "store_url": "https://store.com"
            })
        assert "consumer_key" in str(exc.value)

    def test_missing_consumer_secret(self):
        """Test missing consumer secret raises error."""
        with pytest.raises(IntegrationError) as exc:
            WooCommerceIntegration({
                "consumer_key": "key",
                "store_url": "https://store.com"
            })
        assert "consumer_secret" in str(exc.value)

    def test_missing_store_url(self):
        """Test missing store URL raises error."""
        with pytest.raises(IntegrationError) as exc:
            WooCommerceIntegration({
                "consumer_key": "key",
                "consumer_secret": "secret"
            })
        assert "store_url" in str(exc.value)

    def test_base_url(self, integration):
        """Test base URL generation."""
        url = integration._get_base_url()
        assert "mystore.com" in url
        assert "wp-json/wc/v3" in url

    def test_headers(self, integration):
        """Test request headers with Basic auth."""
        headers = integration._get_headers()
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_list_products(self, integration):
        """Test list_products action."""
        mock_response = [
            {"id": 1, "name": "Product 1", "status": "publish"},
            {"id": 2, "name": "Product 2", "status": "publish"},
        ]

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "list_products",
                {"per_page": 10, "status": "publish"},
            )

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_product(self, integration):
        """Test get_product action."""
        mock_response = {"id": 123, "name": "Test Product", "regular_price": "29.99"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "get_product",
                {"product_id": 123},
            )

        assert result.success
        assert result.data["product"]["id"] == 123

    @pytest.mark.asyncio
    async def test_create_product(self, integration):
        """Test create_product action."""
        mock_response = {"id": 456, "name": "New Product", "status": "publish"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "create_product",
                {"name": "New Product", "regular_price": "49.99", "type": "simple"},
            )

        assert result.success
        assert result.data["product_id"] == 456

    @pytest.mark.asyncio
    async def test_update_product(self, integration):
        """Test update_product action."""
        mock_response = {"id": 123, "name": "Updated Product", "sale_price": "39.99"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "update_product",
                {"product_id": 123, "sale_price": "39.99"},
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_list_orders(self, integration):
        """Test list_orders action."""
        mock_response = [
            {"id": 1001, "status": "processing", "total": "99.99"},
            {"id": 1002, "status": "completed", "total": "149.99"},
        ]

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "list_orders",
                {"status": "processing"},
            )

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_order(self, integration):
        """Test get_order action."""
        mock_response = {"id": 1001, "status": "processing", "customer_id": 101}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "get_order",
                {"order_id": 1001},
            )

        assert result.success
        assert result.data["order"]["id"] == 1001

    @pytest.mark.asyncio
    async def test_update_order(self, integration):
        """Test update_order action."""
        mock_response = {"id": 1001, "status": "completed"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "update_order",
                {"order_id": 1001, "status": "completed"},
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_list_customers(self, integration):
        """Test list_customers action."""
        mock_response = [
            {"id": 101, "email": "customer1@test.com"},
            {"id": 102, "email": "customer2@test.com"},
        ]

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "list_customers",
                {"per_page": 50},
            )

        assert result.success
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_customer(self, integration):
        """Test get_customer action."""
        mock_response = {"id": 101, "email": "customer@test.com", "first_name": "John"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "get_customer",
                {"customer_id": 101},
            )

        assert result.success
        assert result.data["customer"]["email"] == "customer@test.com"

    @pytest.mark.asyncio
    async def test_create_customer(self, integration):
        """Test create_customer action."""
        mock_response = {"id": 201, "email": "new@test.com", "first_name": "Jane"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.execute_action(
                "create_customer",
                {"email": "new@test.com", "first_name": "Jane", "last_name": "Doe"},
            )

        assert result.success
        assert result.data["customer_id"] == 201

    @pytest.mark.asyncio
    async def test_missing_product_id(self, integration):
        """Test missing product_id parameter."""
        result = await integration.execute_action("get_product", {})
        assert not result.success
        assert "product_id" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_name(self, integration):
        """Test missing name for create_product."""
        result = await integration.execute_action("create_product", {})
        assert not result.success
        assert "name" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_missing_email(self, integration):
        """Test missing email for create_customer."""
        result = await integration.execute_action("create_customer", {})
        assert not result.success
        assert "email" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_test_connection(self, integration):
        """Test connection testing."""
        mock_response = {"slug": "data", "description": "WooCommerce Data API"}

        with patch.object(integration, "_make_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await integration.test_connection()

        assert result.success
        assert result.data["connected"]


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
