"""
Shopify Integration - FULLY IMPLEMENTED

Real Shopify Admin API integration for e-commerce operations.

Supported Actions:
- list_products: List products in store
- get_product: Get product by ID
- create_product: Create new product
- update_product: Update existing product
- list_orders: List orders
- get_order: Get order by ID
- update_order: Update order
- list_customers: List customers
- get_customer: Get customer by ID
- create_customer: Create new customer

Authentication: API Key (Access Token) + Store Domain
API Docs: https://shopify.dev/docs/api/admin-rest
"""

import aiohttp
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class ShopifyIntegration(BaseIntegration):
    """Shopify integration with Admin REST API."""

    API_VERSION = "2024-01"

    @property
    def name(self) -> str:
        return "shopify"

    @property
    def display_name(self) -> str:
        return "Shopify"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "list_products",
            "get_product",
            "create_product",
            "update_product",
            "list_orders",
            "get_order",
            "update_order",
            "list_customers",
            "get_customer",
            "create_customer",
        ]

    def _validate_credentials(self) -> None:
        """Validate Shopify credentials."""
        super()._validate_credentials()

        if "access_token" not in self.auth_credentials:
            raise IntegrationError(
                "Shopify requires 'access_token'",
                code="MISSING_CREDENTIALS",
            )

        if "store_domain" not in self.auth_credentials:
            raise IntegrationError(
                "Shopify requires 'store_domain' (e.g., 'mystore.myshopify.com')",
                code="MISSING_CREDENTIALS",
            )

    def _get_base_url(self) -> str:
        """Get Shopify Admin API base URL."""
        store_domain = self.auth_credentials["store_domain"]
        # Remove protocol if included
        if store_domain.startswith("https://"):
            store_domain = store_domain[8:]
        elif store_domain.startswith("http://"):
            store_domain = store_domain[7:]
        # Remove trailing slash
        store_domain = store_domain.rstrip("/")

        return f"https://{store_domain}/admin/api/{self.API_VERSION}"

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        return {
            "X-Shopify-Access-Token": self.auth_credentials["access_token"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Shopify Admin API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/products.json")
            data: Request body for POST/PUT
            params: Query parameters

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
        url = f"{self._get_base_url()}{endpoint}"

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
                            error_msg = error_data.get("errors", response_text)
                        except json.JSONDecodeError:
                            error_msg = response_text

                        raise IntegrationError(
                            f"Shopify API error: {error_msg}",
                            code="SHOPIFY_ERROR",
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
        """Execute Shopify action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "list_products":
                result = await self._list_products(params)
            elif action == "get_product":
                result = await self._get_product(params)
            elif action == "create_product":
                result = await self._create_product(params)
            elif action == "update_product":
                result = await self._update_product(params)
            elif action == "list_orders":
                result = await self._list_orders(params)
            elif action == "get_order":
                result = await self._get_order(params)
            elif action == "update_order":
                result = await self._update_order(params)
            elif action == "list_customers":
                result = await self._list_customers(params)
            elif action == "get_customer":
                result = await self._get_customer(params)
            elif action == "create_customer":
                result = await self._create_customer(params)
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
        """Test Shopify connection by fetching shop info."""
        try:
            response = await self._make_request("GET", "/shop.json")
            shop = response.get("shop", {})
            return IntegrationResult(
                success=True,
                data={
                    "connected": True,
                    "shop_name": shop.get("name"),
                    "shop_domain": shop.get("domain"),
                },
            )
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
            )

    # ========================================================================
    # Product Actions
    # ========================================================================

    async def _list_products(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List products in store.

        Optional params:
            limit: Max products to return (default: 50, max: 250)
            status: Filter by status (active, archived, draft)
            product_type: Filter by product type
            vendor: Filter by vendor
            since_id: Return products after this ID
        """
        query_params = {}

        if "limit" in params:
            query_params["limit"] = min(params["limit"], 250)
        if "status" in params:
            query_params["status"] = params["status"]
        if "product_type" in params:
            query_params["product_type"] = params["product_type"]
        if "vendor" in params:
            query_params["vendor"] = params["vendor"]
        if "since_id" in params:
            query_params["since_id"] = params["since_id"]

        response = await self._make_request("GET", "/products.json", params=query_params)

        products = response.get("products", [])

        return IntegrationResult(
            success=True,
            data={
                "products": products,
                "count": len(products),
            },
        )

    async def _get_product(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get product by ID.

        Required params:
            product_id: Product ID
        """
        product_id = params.get("product_id")
        if not product_id:
            raise IntegrationError("Missing required parameter: 'product_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/products/{product_id}.json")

        return IntegrationResult(
            success=True,
            data={
                "product": response.get("product"),
            },
        )

    async def _create_product(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create new product.

        Required params:
            title: Product title

        Optional params:
            body_html: Product description HTML
            vendor: Product vendor
            product_type: Product type
            tags: Comma-separated tags
            variants: List of variant objects
            images: List of image objects
            status: Product status (active, archived, draft)
        """
        title = params.get("title")
        if not title:
            raise IntegrationError("Missing required parameter: 'title'", code="MISSING_PARAMS")

        product_data = {"title": title}

        optional_fields = ["body_html", "vendor", "product_type", "tags", "variants", "images", "status"]
        for field in optional_fields:
            if field in params:
                product_data[field] = params[field]

        response = await self._make_request("POST", "/products.json", data={"product": product_data})

        product = response.get("product", {})

        return IntegrationResult(
            success=True,
            data={
                "product": product,
                "product_id": product.get("id"),
            },
        )

    async def _update_product(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update existing product.

        Required params:
            product_id: Product ID

        Optional params:
            title: Product title
            body_html: Product description HTML
            vendor: Product vendor
            product_type: Product type
            tags: Comma-separated tags
            status: Product status
        """
        product_id = params.get("product_id")
        if not product_id:
            raise IntegrationError("Missing required parameter: 'product_id'", code="MISSING_PARAMS")

        product_data = {"id": product_id}

        optional_fields = ["title", "body_html", "vendor", "product_type", "tags", "status"]
        for field in optional_fields:
            if field in params:
                product_data[field] = params[field]

        response = await self._make_request(
            "PUT", f"/products/{product_id}.json", data={"product": product_data}
        )

        return IntegrationResult(
            success=True,
            data={
                "product": response.get("product"),
            },
        )

    # ========================================================================
    # Order Actions
    # ========================================================================

    async def _list_orders(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List orders.

        Optional params:
            limit: Max orders to return (default: 50, max: 250)
            status: Filter by status (open, closed, cancelled, any)
            financial_status: Filter by financial status
            fulfillment_status: Filter by fulfillment status
            created_at_min: Minimum creation date (ISO 8601)
            created_at_max: Maximum creation date (ISO 8601)
            since_id: Return orders after this ID
        """
        query_params = {}

        if "limit" in params:
            query_params["limit"] = min(params["limit"], 250)
        if "status" in params:
            query_params["status"] = params["status"]
        if "financial_status" in params:
            query_params["financial_status"] = params["financial_status"]
        if "fulfillment_status" in params:
            query_params["fulfillment_status"] = params["fulfillment_status"]
        if "created_at_min" in params:
            query_params["created_at_min"] = params["created_at_min"]
        if "created_at_max" in params:
            query_params["created_at_max"] = params["created_at_max"]
        if "since_id" in params:
            query_params["since_id"] = params["since_id"]

        response = await self._make_request("GET", "/orders.json", params=query_params)

        orders = response.get("orders", [])

        return IntegrationResult(
            success=True,
            data={
                "orders": orders,
                "count": len(orders),
            },
        )

    async def _get_order(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get order by ID.

        Required params:
            order_id: Order ID
        """
        order_id = params.get("order_id")
        if not order_id:
            raise IntegrationError("Missing required parameter: 'order_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/orders/{order_id}.json")

        return IntegrationResult(
            success=True,
            data={
                "order": response.get("order"),
            },
        )

    async def _update_order(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update order.

        Required params:
            order_id: Order ID

        Optional params:
            note: Order note
            tags: Comma-separated tags
            email: Customer email
            phone: Customer phone
        """
        order_id = params.get("order_id")
        if not order_id:
            raise IntegrationError("Missing required parameter: 'order_id'", code="MISSING_PARAMS")

        order_data = {"id": order_id}

        optional_fields = ["note", "tags", "email", "phone"]
        for field in optional_fields:
            if field in params:
                order_data[field] = params[field]

        response = await self._make_request(
            "PUT", f"/orders/{order_id}.json", data={"order": order_data}
        )

        return IntegrationResult(
            success=True,
            data={
                "order": response.get("order"),
            },
        )

    # ========================================================================
    # Customer Actions
    # ========================================================================

    async def _list_customers(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List customers.

        Optional params:
            limit: Max customers to return (default: 50, max: 250)
            created_at_min: Minimum creation date
            created_at_max: Maximum creation date
            since_id: Return customers after this ID
        """
        query_params = {}

        if "limit" in params:
            query_params["limit"] = min(params["limit"], 250)
        if "created_at_min" in params:
            query_params["created_at_min"] = params["created_at_min"]
        if "created_at_max" in params:
            query_params["created_at_max"] = params["created_at_max"]
        if "since_id" in params:
            query_params["since_id"] = params["since_id"]

        response = await self._make_request("GET", "/customers.json", params=query_params)

        customers = response.get("customers", [])

        return IntegrationResult(
            success=True,
            data={
                "customers": customers,
                "count": len(customers),
            },
        )

    async def _get_customer(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get customer by ID.

        Required params:
            customer_id: Customer ID
        """
        customer_id = params.get("customer_id")
        if not customer_id:
            raise IntegrationError("Missing required parameter: 'customer_id'", code="MISSING_PARAMS")

        response = await self._make_request("GET", f"/customers/{customer_id}.json")

        return IntegrationResult(
            success=True,
            data={
                "customer": response.get("customer"),
            },
        )

    async def _create_customer(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create new customer.

        Required params:
            email: Customer email

        Optional params:
            first_name: First name
            last_name: Last name
            phone: Phone number
            tags: Comma-separated tags
            note: Customer note
            addresses: List of address objects
            accepts_marketing: Whether customer accepts marketing
        """
        email = params.get("email")
        if not email:
            raise IntegrationError("Missing required parameter: 'email'", code="MISSING_PARAMS")

        customer_data = {"email": email}

        optional_fields = [
            "first_name", "last_name", "phone", "tags",
            "note", "addresses", "accepts_marketing"
        ]
        for field in optional_fields:
            if field in params:
                customer_data[field] = params[field]

        response = await self._make_request("POST", "/customers.json", data={"customer": customer_data})

        customer = response.get("customer", {})

        return IntegrationResult(
            success=True,
            data={
                "customer": customer,
                "customer_id": customer.get("id"),
            },
        )
