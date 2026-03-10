"""
Stripe Integration - FULLY IMPLEMENTED

Real Stripe API integration for payment processing.

Supported Actions:
- create_customer: Create new customer
- create_charge: Create one-time charge
- create_subscription: Create subscription
- list_customers: List all customers
- refund_charge: Refund a charge

Authentication: API Key (Secret Key)
API Docs: https://stripe.com/docs/api
"""

import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class StripeIntegration(BaseIntegration):
    """Stripe payment integration with real API client."""

    API_BASE_URL = "https://api.stripe.com/v1"

    @property
    def name(self) -> str:
        return "stripe"

    @property
    def display_name(self) -> str:
        return "Stripe"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return [
            "create_customer",
            "create_charge",
            "create_subscription",
            "list_customers",
            "refund_charge",
        ]

    def _validate_credentials(self) -> None:
        """Validate Stripe credentials."""
        super()._validate_credentials()

        api_key = self.auth_credentials.get("api_key") or self.auth_credentials.get("secret_key")
        if not api_key:
            raise IntegrationError(
                "Stripe requires 'api_key' or 'secret_key'",
                code="MISSING_API_KEY",
            )

        # Validate key format (should start with sk_)
        if not api_key.startswith("sk_"):
            raise IntegrationError(
                "Invalid Stripe API key format (should start with 'sk_')",
                code="INVALID_API_KEY",
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Stripe API."""
        api_key = self.auth_credentials.get("api_key") or self.auth_credentials.get("secret_key")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Stripe API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., 'customers', 'charges')
            data: Request payload

        Returns:
            API response as dict

        Raises:
            IntegrationError: If API call fails
        """
        url = f"{self.API_BASE_URL}/{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    data=data,  # Stripe uses form-encoded data
                ) as response:
                    response_data = await response.json()

                    # Stripe returns error object on failure
                    if response.status >= 400:
                        error = response_data.get("error", {})
                        raise IntegrationError(
                            f"Stripe API error: {error.get('message', 'Unknown error')}",
                            code=error.get("code", "UNKNOWN").upper(),
                            status_code=response.status,
                            details=error,
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
        """Execute Stripe action with real API call."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "create_customer":
                result = await self._create_customer(params)
            elif action == "create_charge":
                result = await self._create_charge(params)
            elif action == "create_subscription":
                result = await self._create_subscription(params)
            elif action == "list_customers":
                result = await self._list_customers(params)
            elif action == "refund_charge":
                result = await self._refund_charge(params)
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
        """Test Stripe connection by retrieving account info."""
        try:
            response = await self._make_request("GET", "account")
            return IntegrationResult(
                success=True,
                data={
                    "account_id": response.get("id"),
                    "email": response.get("email"),
                    "country": response.get("country"),
                    "charges_enabled": response.get("charges_enabled"),
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

    async def _create_customer(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a new Stripe customer.

        Required params:
            email: Customer email

        Optional params:
            name: Customer name
            description: Customer description
            metadata: Custom metadata dict
        """
        if "email" not in params:
            raise IntegrationError("Missing required parameter: 'email'", code="MISSING_PARAMS")

        payload = {
            "email": params["email"],
        }

        if "name" in params:
            payload["name"] = params["name"]
        if "description" in params:
            payload["description"] = params["description"]
        if "metadata" in params:
            # Flatten metadata for form encoding
            for key, value in params["metadata"].items():
                payload[f"metadata[{key}]"] = value

        response = await self._make_request("POST", "customers", payload)

        return IntegrationResult(
            success=True,
            data={
                "customer_id": response.get("id"),
                "email": response.get("email"),
                "name": response.get("name"),
                "created": response.get("created"),
            },
        )

    async def _create_charge(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a one-time charge.

        Required params:
            amount: Amount in cents (e.g., 2000 for $20.00)
            currency: Three-letter currency code (e.g., 'usd')
            source: Payment source (token or customer ID)

        Optional params:
            description: Charge description
            customer: Customer ID (if not using source)
            metadata: Custom metadata dict
        """
        required_fields = ["amount", "currency", "source"]
        missing = [f for f in required_fields if f not in params]
        if missing:
            raise IntegrationError(
                f"Missing required parameters: {', '.join(missing)}",
                code="MISSING_PARAMS",
            )

        payload = {
            "amount": params["amount"],
            "currency": params["currency"],
            "source": params["source"],
        }

        if "description" in params:
            payload["description"] = params["description"]
        if "customer" in params:
            payload["customer"] = params["customer"]
        if "metadata" in params:
            for key, value in params["metadata"].items():
                payload[f"metadata[{key}]"] = value

        response = await self._make_request("POST", "charges", payload)

        return IntegrationResult(
            success=True,
            data={
                "charge_id": response.get("id"),
                "amount": response.get("amount"),
                "currency": response.get("currency"),
                "status": response.get("status"),
                "paid": response.get("paid"),
                "receipt_url": response.get("receipt_url"),
            },
        )

    async def _create_subscription(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Create a subscription.

        Required params:
            customer: Customer ID
            items: List of subscription items with price IDs
                   e.g., [{"price": "price_123"}]

        Optional params:
            trial_period_days: Trial period in days
            metadata: Custom metadata dict
        """
        if "customer" not in params or "items" not in params:
            raise IntegrationError(
                "Missing required parameters: 'customer' and 'items'",
                code="MISSING_PARAMS",
            )

        payload = {
            "customer": params["customer"],
        }

        # Add subscription items
        for i, item in enumerate(params["items"]):
            payload[f"items[{i}][price]"] = item.get("price")
            if "quantity" in item:
                payload[f"items[{i}][quantity]"] = item["quantity"]

        if "trial_period_days" in params:
            payload["trial_period_days"] = params["trial_period_days"]
        if "metadata" in params:
            for key, value in params["metadata"].items():
                payload[f"metadata[{key}]"] = value

        response = await self._make_request("POST", "subscriptions", payload)

        return IntegrationResult(
            success=True,
            data={
                "subscription_id": response.get("id"),
                "customer": response.get("customer"),
                "status": response.get("status"),
                "current_period_start": response.get("current_period_start"),
                "current_period_end": response.get("current_period_end"),
            },
        )

    async def _list_customers(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List all customers.

        Optional params:
            limit: Max customers to return (default: 10, max: 100)
            starting_after: Customer ID to start after (for pagination)
        """
        payload = {
            "limit": params.get("limit", 10),
        }

        if "starting_after" in params:
            payload["starting_after"] = params["starting_after"]

        response = await self._make_request("GET", "customers", payload)

        customers = [
            {
                "id": c.get("id"),
                "email": c.get("email"),
                "name": c.get("name"),
                "created": c.get("created"),
            }
            for c in response.get("data", [])
        ]

        return IntegrationResult(
            success=True,
            data={
                "customers": customers,
                "has_more": response.get("has_more"),
                "total": len(customers),
            },
        )

    async def _refund_charge(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Refund a charge.

        Required params:
            charge: Charge ID to refund

        Optional params:
            amount: Amount to refund in cents (partial refund)
            reason: Refund reason ('duplicate', 'fraudulent', 'requested_by_customer')
        """
        if "charge" not in params:
            raise IntegrationError("Missing required parameter: 'charge'", code="MISSING_PARAMS")

        payload = {
            "charge": params["charge"],
        }

        if "amount" in params:
            payload["amount"] = params["amount"]
        if "reason" in params:
            payload["reason"] = params["reason"]

        response = await self._make_request("POST", "refunds", payload)

        return IntegrationResult(
            success=True,
            data={
                "refund_id": response.get("id"),
                "charge": response.get("charge"),
                "amount": response.get("amount"),
                "currency": response.get("currency"),
                "status": response.get("status"),
                "reason": response.get("reason"),
            },
        )
