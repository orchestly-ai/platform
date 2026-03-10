"""
Salesforce Integration - FULLY IMPLEMENTED

Real Salesforce CRM API integration.

Supported Actions:
- create_lead: Create a new lead
- create_contact: Create a new contact
- create_opportunity: Create a new opportunity
- query_records: Query records using SOQL
- update_record: Update an existing record

Authentication: OAuth2 (Access Token)
API Docs: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/
"""

import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType


class SalesforceIntegration(BaseIntegration):
    """Salesforce CRM integration with real API client."""

    @property
    def name(self) -> str:
        return "salesforce"

    @property
    def display_name(self) -> str:
        return "Salesforce"

    @property
    def auth_type(self) -> AuthType:
        return AuthType.OAUTH2

    @property
    def supported_actions(self) -> List[str]:
        return ["create_lead", "create_contact", "create_opportunity", "query_records", "update_record"]

    def _validate_credentials(self) -> None:
        """Validate Salesforce credentials."""
        super()._validate_credentials()
        if not self.auth_credentials.get("access_token"):
            raise IntegrationError(
                "Salesforce requires 'access_token' from OAuth2 flow",
                code="MISSING_CREDENTIALS",
            )
        if not self.auth_credentials.get("instance_url"):
            raise IntegrationError(
                "Salesforce requires 'instance_url' (e.g., https://mycompany.salesforce.com)",
                code="MISSING_INSTANCE_URL",
            )

    def _get_base_url(self) -> str:
        """Get base URL with instance URL."""
        instance_url = self.auth_credentials.get("instance_url")
        return f"{instance_url}/services/data/v57.0"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with OAuth2 access token."""
        access_token = self.auth_credentials.get("access_token")
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Salesforce API."""
        url = f"{self._get_base_url()}{endpoint}"
        headers = self._get_headers()

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method, url=url, headers=headers, json=data, params=params
            ) as response:
                if response.status >= 400:
                    error_data = await response.json()
                    error_msg = error_data[0].get("message", "Unknown error") if error_data else "Unknown error"
                    raise IntegrationError(
                        f"Salesforce API error: {error_msg}",
                        code=f"API_ERROR_{response.status}",
                    )

                # Some endpoints return 204 No Content
                if response.status == 204:
                    return {"success": True}

                return await response.json()

    async def execute_action(self, action: str, params: Dict[str, Any]) -> IntegrationResult:
        """Execute Salesforce action."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "create_lead":
                result = await self._create_lead(params)
            elif action == "create_contact":
                result = await self._create_contact(params)
            elif action == "create_opportunity":
                result = await self._create_opportunity(params)
            elif action == "query_records":
                result = await self._query_records(params)
            elif action == "update_record":
                result = await self._update_record(params)
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
        """Test Salesforce connection by querying limits."""
        try:
            await self._make_request("GET", "/limits")
            return IntegrationResult(success=True, data={"status": "connected"})
        except IntegrationError as e:
            return IntegrationResult(success=False, error_message=e.message, error_code=e.code)

    async def _create_lead(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new lead."""
        required = ["LastName", "Company"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        lead_data = {
            "LastName": params["LastName"],
            "Company": params["Company"],
        }

        if "FirstName" in params:
            lead_data["FirstName"] = params["FirstName"]
        if "Email" in params:
            lead_data["Email"] = params["Email"]
        if "Phone" in params:
            lead_data["Phone"] = params["Phone"]
        if "Status" in params:
            lead_data["Status"] = params["Status"]

        response = await self._make_request("POST", "/sobjects/Lead", data=lead_data)

        return IntegrationResult(
            success=True,
            data={
                "lead_id": response.get("id"),
                "success": response.get("success"),
            },
        )

    async def _create_contact(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new contact."""
        required = ["LastName"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        contact_data = {"LastName": params["LastName"]}

        if "FirstName" in params:
            contact_data["FirstName"] = params["FirstName"]
        if "Email" in params:
            contact_data["Email"] = params["Email"]
        if "Phone" in params:
            contact_data["Phone"] = params["Phone"]
        if "AccountId" in params:
            contact_data["AccountId"] = params["AccountId"]

        response = await self._make_request("POST", "/sobjects/Contact", data=contact_data)

        return IntegrationResult(
            success=True,
            data={
                "contact_id": response.get("id"),
                "success": response.get("success"),
            },
        )

    async def _create_opportunity(self, params: Dict[str, Any]) -> IntegrationResult:
        """Create a new opportunity."""
        required = ["Name", "StageName", "CloseDate"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        opportunity_data = {
            "Name": params["Name"],
            "StageName": params["StageName"],
            "CloseDate": params["CloseDate"],
        }

        if "Amount" in params:
            opportunity_data["Amount"] = params["Amount"]
        if "AccountId" in params:
            opportunity_data["AccountId"] = params["AccountId"]
        if "Probability" in params:
            opportunity_data["Probability"] = params["Probability"]

        response = await self._make_request("POST", "/sobjects/Opportunity", data=opportunity_data)

        return IntegrationResult(
            success=True,
            data={
                "opportunity_id": response.get("id"),
                "success": response.get("success"),
            },
        )

    async def _query_records(self, params: Dict[str, Any]) -> IntegrationResult:
        """Query records using SOQL."""
        if "query" not in params:
            raise IntegrationError("Missing required parameter: 'query' (SOQL query)", code="MISSING_PARAMS")

        query = params["query"]
        response = await self._make_request("GET", "/query", params={"q": query})

        return IntegrationResult(
            success=True,
            data={
                "records": response.get("records", []),
                "total_size": response.get("totalSize", 0),
                "done": response.get("done", True),
            },
        )

    async def _update_record(self, params: Dict[str, Any]) -> IntegrationResult:
        """Update an existing record."""
        required = ["object_type", "record_id"]
        missing = [f for f in required if f not in params]
        if missing:
            raise IntegrationError(f"Missing required parameters: {', '.join(missing)}", code="MISSING_PARAMS")

        object_type = params["object_type"]
        record_id = params["record_id"]

        # Remove metadata fields from update data
        update_data = {k: v for k, v in params.items() if k not in ["object_type", "record_id"]}

        if not update_data:
            raise IntegrationError("No fields to update", code="MISSING_PARAMS")

        response = await self._make_request("PATCH", f"/sobjects/{object_type}/{record_id}", data=update_data)

        return IntegrationResult(
            success=True,
            data={
                "record_id": record_id,
                "object_type": object_type,
                "success": response.get("success", True),
            },
        )
