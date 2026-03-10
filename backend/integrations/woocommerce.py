"""
WooCommerce Integration - FULLY IMPLEMENTED

Real WooCommerce REST API integration for e-commerce operations.

Supported Actions:
- list_products: List products
- get_product: Get product by ID
- create_product: Create new product
- update_product: Update existing product
- list_orders: List orders
- get_order: Get order by ID
- update_order: Update order status/details
- list_customers: List customers
- get_customer: Get customer by ID
- create_customer: Create new customer

Authentication: Consumer Key + Consumer Secret (REST API)
API Docs: https://woocommerce.github.io/woocommerce-rest-api-docs/
"""

import aiohttp
import base64
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class WooCommerceIntegration(BaseIntegration):
    """WooCommerce integration with REST API."""

    API_VERSION = "wc/v3"

    @property
    def name(self) -> str:
        return "woocommerce"

    @property
    def display_name(self) -> str:
        return "WooCommerce"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.BASIC_AUTH

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
        """Validate WooCommerce credentials."""
        super()._validate_credentials()

        if "consumer_key" not in self.auth_credentials:
            raise IntegrationError(
                "WooCommerce requires 'consumer_key'",
                code="MISSING_CREDENTIALS",
            )

        if "consumer_secret" not in self.auth_credentials:
            raise IntegrationError(
                "WooCommerce requires 'consumer_secret'",
                code="MISSING_CREDENTIALS",
            )

        if "store_url" not in self.auth_credentials:
            raise IntegrationError(
                "WooCommerce requires 'store_url' (e.g., 'https://mystore.com')",
                code="MISSING_CREDENTIALS",
            )

    def _get_base_url(self) -> str:
        """Get WooCommerce REST API base URL."""
        store_url = self.auth_credentials["store_url"]
        # Remove trailing slash
        store_url = store_url.rstrip("/")

        return f"{store_url}/wp-json/{self.API_VERSION}"

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with auth."""
        # WooCommerce uses HTTP Basic Auth with consumer key/secret
        consumer_key = self.auth_credentials["consumer_key"]
        consumer_secret = self.auth_credentials["consumer_secret"]
        credentials = f"{consumer_key}:{consumer_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {encoded}",
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
        Make HTTP request to WooCommerce REST API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/products")
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
                            error_msg = error_data.get("message", response_text)
                            error_code = error_data.get("code", "WOOCOMMERCE_ERROR")
                        except json.JSONDecodeError:
                            error_msg = response_text
                            error_code = "WOOCOMMERCE_ERROR"

                        raise IntegrationError(
                            f"WooCommerce API error: {error_msg}",
                            code=error_code,
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
        """Execute WooCommerce action with real API call."""
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
        """Test WooCommerce connection by fetching system status."""
        try:
            # Use the simpler /data endpoint as a connection test
            response = await self._make_request("GET", "/data")
            return IntegrationResult(
                success=True,
                data={
                    "connected": True,
                    "store_url": self.auth_credentials["store_url"],
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
        List products.

        Optional params:
            per_page: Items per page (default: 10, max: 100)
            page: Page number
            status: Filter by status (draft, pending, private, publish, any)
            category: Filter by category ID
            type: Filter by type (simple, grouped, external, variable)
            search: Search term
            orderby: Sort by field (date, id, include, title, slug, price, popularity, rating)
            order: Sort order (asc, desc)
        """
        query_params = {}

        if "per_page" in params:
            query_params["per_page"] = min(params["per_page"], 100)
        if "page" in params:
            query_params["page"] = params["page"]
        if "status" in params:
            query_params["status"] = params["status"]
        if "category" in params:
            query_params["category"] = params["category"]
        if "type" in params:
            query_params["type"] = params["type"]
        if "search" in params:
            query_params["search"] = params["search"]
        if "orderby" in params:
            query_params["orderby"] = params["orderby"]
        if "order" in params:
            query_params["order"] = params["order"]

        response = await self._make_request("GET", "/products", params=query_params)

        products = response if isinstance(response, list) else []

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

        response = await self._make_request("GET", f"/products/{product_id}")

        return IntegrationResult(
            success=True,
            data={
                "product": response,
            },
        )

    async def _create_product(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create new product.

        Required params:
            name: Product name

        Optional params:
            type: Product type (simple, grouped, external, variable)
            status: Product status (draft, pending, private, publish)
            description: Product description
            short_description: Short description
            sku: Stock Keeping Unit
            regular_price: Regular price
            sale_price: Sale price
            categories: List of category objects [{id: 1}]
            images: List of image objects [{src: "url"}]
            manage_stock: Enable stock management
            stock_quantity: Stock quantity
        """
        name = params.get("name")
        if not name:
            raise IntegrationError("Missing required parameter: 'name'", code="MISSING_PARAMS")

        product_data = {"name": name}

        optional_fields = [
            "type", "status", "description", "short_description", "sku",
            "regular_price", "sale_price", "categories", "images",
            "manage_stock", "stock_quantity"
        ]
        for field in optional_fields:
            if field in params:
                product_data[field] = params[field]

        response = await self._make_request("POST", "/products", data=product_data)

        return IntegrationResult(
            success=True,
            data={
                "product": response,
                "product_id": response.get("id"),
            },
        )

    async def _update_product(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update existing product.

        Required params:
            product_id: Product ID

        Optional params:
            name: Product name
            status: Product status
            description: Product description
            regular_price: Regular price
            sale_price: Sale price
            stock_quantity: Stock quantity
        """
        product_id = params.get("product_id")
        if not product_id:
            raise IntegrationError("Missing required parameter: 'product_id'", code="MISSING_PARAMS")

        product_data = {}

        optional_fields = [
            "name", "status", "description", "short_description", "sku",
            "regular_price", "sale_price", "stock_quantity"
        ]
        for field in optional_fields:
            if field in params:
                product_data[field] = params[field]

        response = await self._make_request("PUT", f"/products/{product_id}", data=product_data)

        return IntegrationResult(
            success=True,
            data={
                "product": response,
            },
        )

    # ========================================================================
    # Order Actions
    # ========================================================================

    async def _list_orders(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List orders.

        Optional params:
            per_page: Items per page (default: 10, max: 100)
            page: Page number
            status: Filter by status (pending, processing, on-hold, completed, cancelled, refunded, failed, trash, any)
            customer: Customer ID
            after: Limit to orders placed after date (ISO 8601)
            before: Limit to orders placed before date (ISO 8601)
            orderby: Sort by field (date, id, include, title, slug)
            order: Sort order (asc, desc)
        """
        query_params = {}

        if "per_page" in params:
            query_params["per_page"] = min(params["per_page"], 100)
        if "page" in params:
            query_params["page"] = params["page"]
        if "status" in params:
            query_params["status"] = params["status"]
        if "customer" in params:
            query_params["customer"] = params["customer"]
        if "after" in params:
            query_params["after"] = params["after"]
        if "before" in params:
            query_params["before"] = params["before"]
        if "orderby" in params:
            query_params["orderby"] = params["orderby"]
        if "order" in params:
            query_params["order"] = params["order"]

        response = await self._make_request("GET", "/orders", params=query_params)

        orders = response if isinstance(response, list) else []

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

        response = await self._make_request("GET", f"/orders/{order_id}")

        return IntegrationResult(
            success=True,
            data={
                "order": response,
            },
        )

    async def _update_order(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Update order status/details.

        Required params:
            order_id: Order ID

        Optional params:
            status: Order status (pending, processing, on-hold, completed, cancelled, refunded, failed)
            customer_note: Note to customer
            billing: Billing address object
            shipping: Shipping address object
        """
        order_id = params.get("order_id")
        if not order_id:
            raise IntegrationError("Missing required parameter: 'order_id'", code="MISSING_PARAMS")

        order_data = {}

        optional_fields = ["status", "customer_note", "billing", "shipping"]
        for field in optional_fields:
            if field in params:
                order_data[field] = params[field]

        response = await self._make_request("PUT", f"/orders/{order_id}", data=order_data)

        return IntegrationResult(
            success=True,
            data={
                "order": response,
            },
        )

    # ========================================================================
    # Customer Actions
    # ========================================================================

    async def _list_customers(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List customers.

        Optional params:
            per_page: Items per page (default: 10, max: 100)
            page: Page number
            search: Search term (searches in email, first_name, last_name, username)
            email: Filter by email
            role: Filter by role (all, administrator, editor, author, contributor, subscriber, customer)
            orderby: Sort by field (id, include, name, registered_date)
            order: Sort order (asc, desc)
        """
        query_params = {}

        if "per_page" in params:
            query_params["per_page"] = min(params["per_page"], 100)
        if "page" in params:
            query_params["page"] = params["page"]
        if "search" in params:
            query_params["search"] = params["search"]
        if "email" in params:
            query_params["email"] = params["email"]
        if "role" in params:
            query_params["role"] = params["role"]
        if "orderby" in params:
            query_params["orderby"] = params["orderby"]
        if "order" in params:
            query_params["order"] = params["order"]

        response = await self._make_request("GET", "/customers", params=query_params)

        customers = response if isinstance(response, list) else []

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

        response = await self._make_request("GET", f"/customers/{customer_id}")

        return IntegrationResult(
            success=True,
            data={
                "customer": response,
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
            username: Username (defaults to email)
            password: Password (auto-generated if not provided)
            billing: Billing address object
            shipping: Shipping address object
        """
        email = params.get("email")
        if not email:
            raise IntegrationError("Missing required parameter: 'email'", code="MISSING_PARAMS")

        customer_data = {"email": email}

        optional_fields = ["first_name", "last_name", "username", "password", "billing", "shipping"]
        for field in optional_fields:
            if field in params:
                customer_data[field] = params[field]

        response = await self._make_request("POST", "/customers", data=customer_data)

        return IntegrationResult(
            success=True,
            data={
                "customer": response,
                "customer_id": response.get("id"),
            },
        )
