"""
HubSpot Integration - FULLY IMPLEMENTED

Real HubSpot CRM API integration.

Supported Actions:
- create_contact: Create a new contact
- update_contact: Update an existing contact
- create_deal: Create a new deal
- list_contacts: List all contacts
- get_contact: Get specific contact details

Authentication: API Key (Private App Token)
API Docs: https://developers.hubspot.com/docs/api/overview
"""

import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class HubSpotIntegration(BaseIntegration):
    """HubSpot CRM integration with real API client."""

    API_BASE_URL = "https://api.hubapi.com"

    @property
    def name(self) -> str:
        return "hubspot"

    @property
    def display_name(self) -> str:
        return "HubSpot"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.API_KEY

    @property
    def supported_actions(self) -> List[str]:
        return ["create_contact", "update_contact", "create_deal", "list_contacts", "get_contact"]

    def _validate_credentials(self) -> None:
        """Validate HubSpot credentials."""
        super()._validate_credentials()
        if not self.auth_credentials.get("api_key"):
            raise IntegrationError(
                "HubSpot requires 'api_key' (Private App Token)",
                code="MISSING_CREDENTIALS",
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with API key."""
        api_key = self.auth_credentials.get("api_key")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to HubSpot API."""
        url = f"{self.API_BASE_URL}{endpoint}"
        headers = self._get_headers()

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method, url=url, headers=headers, json=data, params=params
            ) as response:
                if response.status >= 400:
                    error_data = await response.json()
                    raise IntegrationError(
                        f"HubSpot API error: {error_data.get('message', 'Unknown error')}",
                        code=f"API_ERROR_{response.status}",
                    )
                return await response.json()

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        """Execute HubSpot action."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "create_contact":
                result = await self._create_contact(params)
            elif action == "update_contact":
                result = await self._update_contact(params)
            elif action == "create_deal":
                result = await self._create_deal(params)
            elif action == "list_contacts":
                result = await self._list_contacts(params)
            elif action == "get_contact":
                result = await self._get_contact(params)
            else:
                raise IntegrationError(f"Action {action} not implemented", code="NOT_IMPLEMENTED")

            result.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._log_execution(action, params, result)
            return result
        except IntegrationError as e:
            return IntegrationResult(
                success=False,
                error_message=e.message,
                error_code=e.code,
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )

    async def test_connection(self) -> IntegrationResult:
        """Test HubSpot connection by getting account info."""
        try:
            await self._make_request("GET", "/crm/v3/objects/contacts", params={"limit": 1})
            return IntegrationResult(success=True, data={"status": "connected"})
        except IntegrationError as e:
            return IntegrationResult(success=False, error_message=e.message, error_code=e.code)

    async def _create_contact(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new contact."""
        required = ["email"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        properties = {"email": params["email"]}

        if "firstname" in params:
            properties["firstname"] = params["firstname"]
        if "lastname" in params:
            properties["lastname"] = params["lastname"]
        if "company" in params:
            properties["company"] = params["company"]
        if "phone" in params:
            properties["phone"] = params["phone"]

        contact_data = {"properties": properties}

        response = await self._make_request("POST", "/crm/v3/objects/contacts", data=contact_data)

        return IntegrationResult(
            success=True,
            data={
                "contact_id": response.get("id"),
                "email": response.get("properties", {}).get("email"),
                "created_at": response.get("createdAt"),
            },
        )

    async def _update_contact(self, params: Dict[str, Any]) -> IntegrationResult:
        """Update an existing contact."""
        if "contact_id" not in params:
            raise IntegrationError("Missing required parameter: 'contact_id'", code="MISSING_PARAMS")

        contact_id = params["contact_id"]
        properties = {}

        if "email" in params:
            properties["email"] = params["email"]
        if "firstname" in params:
            properties["firstname"] = params["firstname"]
        if "lastname" in params:
            properties["lastname"] = params["lastname"]
        if "company" in params:
            properties["company"] = params["company"]
        if "phone" in params:
            properties["phone"] = params["phone"]

        if not properties:
            raise IntegrationError("No properties to update", code="MISSING_PARAMS")

        update_data = {"properties": properties}

        response = await self._make_request(
            "PATCH", f"/crm/v3/objects/contacts/{contact_id}", data=update_data
        )

        return IntegrationResult(
            success=True,
            data={
                "contact_id": response.get("id"),
                "updated_at": response.get("updatedAt"),
            },
        )

    async def _create_deal(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new deal."""
        required = ["dealname", "amount"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        properties = {
            "dealname": params["dealname"],
            "amount": params["amount"],
            "dealstage": params.get("dealstage", "appointmentscheduled"),
            "pipeline": params.get("pipeline", "default"),
        }

        if "closedate" in params:
            properties["closedate"] = params["closedate"]

        deal_data = {"properties": properties}

        response = await self._make_request("POST", "/crm/v3/objects/deals", data=deal_data)

        return IntegrationResult(
            success=True,
            data={
                "deal_id": response.get("id"),
                "dealname": response.get("properties", {}).get("dealname"),
                "amount": response.get("properties", {}).get("amount"),
                "created_at": response.get("createdAt"),
            },
        )

    async def _list_contacts(self, params: Dict[str, Any]) -> IntegrationResult:
        """List all contacts."""
        query_params = {"limit": params.get("limit", 100)}

        if "properties" in params:
            query_params["properties"] = ",".join(params["properties"])

        response = await self._make_request("GET", "/crm/v3/objects/contacts", params=query_params)
        contacts = response.get("results", [])

        return IntegrationResult(
            success=True,
            data={
                "contacts": [
                    {
                        "id": c.get("id"),
                        "email": c.get("properties", {}).get("email"),
                        "firstname": c.get("properties", {}).get("firstname"),
                        "lastname": c.get("properties", {}).get("lastname"),
                        "created_at": c.get("createdAt"),
                    }
                    for c in contacts
                ],
                "total": len(contacts),
            },
        )

    async def _get_contact(self, params: Dict[str, Any]) -> IntegrationResult:
        """Get specific contact details."""
        if "contact_id" not in params:
            raise IntegrationError("Missing required parameter: 'contact_id'", code="MISSING_PARAMS")

        contact_id = params["contact_id"]
        response = await self._make_request("GET", f"/crm/v3/objects/contacts/{contact_id}")

        return IntegrationResult(
            success=True,
            data={
                "contact_id": response.get("id"),
                "email": response.get("properties", {}).get("email"),
                "firstname": response.get("properties", {}).get("firstname"),
                "lastname": response.get("properties", {}).get("lastname"),
                "company": response.get("properties", {}).get("company"),
                "phone": response.get("properties", {}).get("phone"),
                "created_at": response.get("createdAt"),
                "updated_at": response.get("updatedAt"),
            },
        )
