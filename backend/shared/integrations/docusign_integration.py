"""
DocuSign E-Signature Integration

Real DocuSign integration for e-signature workflows.
Supports sending documents for signature, tracking status, and downloading signed documents.

Authentication:
- Primary: JWT Grant (server-to-server, recommended for automation)
- Secondary: OAuth 2.0 (user-interactive flows)

Required Credentials (JWT):
- integration_key: DocuSign Integration Key (client ID)
- user_id: DocuSign User ID for impersonation
- account_id: DocuSign Account ID
- private_key: RSA Private Key (PEM format)

Required Credentials (OAuth2):
- access_token: OAuth access token
- account_id: DocuSign Account ID

API Docs: https://developers.docusign.com/

Use Cases:
- Contract signature workflows
- Document approval processes
- Multi-party signing ceremonies
- Template-based envelope creation
"""

import os
import asyncio
import base64
import random
import logging
import httpx
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, ClassVar
from enum import Enum

from backend.shared.integrations.base import (
    BaseIntegration,
    OAuthConfig,
    OAuthTokens,
    IntegrationResult,
    AuthMethod,
)

logger = logging.getLogger(__name__)


class DocuSignEnvironment(str, Enum):
    """DocuSign API environments."""
    DEMO = "demo"
    PRODUCTION = "production"


class DocuSignIntegration(BaseIntegration):
    """
    DocuSign integration for e-signature workflows.

    Features resilient connection handling:
    - Connection pooling via shared httpx.AsyncClient
    - Automatic retries with exponential backoff
    - Rate limit handling
    - JWT token auto-refresh
    - Configurable timeouts

    Supports both JWT (server-to-server) and OAuth2 authentication.

    Actions:
    - send_envelope / create_envelope: Create and send a signing request
    - get_envelope_status: Check envelope signing status
    - download_document / get_envelope_documents: Download signed documents
    - void_envelope: Void/cancel an envelope
    - list_envelopes: List envelopes with filters
    - send_from_template: Send envelope from a template
    - test_connection: Validate connection
    """

    name = "docusign"
    display_name = "DocuSign"
    description = "E-signature platform for sending, signing, and managing documents"
    icon_url = "https://www.docusign.com/sites/default/files/docusign_logo_0.png"
    documentation_url = "https://developers.docusign.com/"

    # API URLs by environment
    API_URLS = {
        DocuSignEnvironment.DEMO: "https://demo.docusign.net/restapi",
        DocuSignEnvironment.PRODUCTION: "https://na1.docusign.net/restapi",
    }

    OAUTH_URLS = {
        DocuSignEnvironment.DEMO: "https://account-d.docusign.com",
        DocuSignEnvironment.PRODUCTION: "https://account.docusign.com",
    }

    # Shared client for connection pooling (class-level)
    _client: ClassVar[Optional[httpx.AsyncClient]] = None
    _client_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # JWT token cache (class-level)
    _token_cache: ClassVar[Dict[str, Dict[str, Any]]] = {}
    _token_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 60.0

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def get_auth_method(self) -> AuthMethod:
        """Return the authentication method."""
        if self.credentials.get("access_token"):
            return AuthMethod.OAUTH2
        return AuthMethod.BEARER_TOKEN  # JWT generates bearer tokens

    def get_oauth_config(self) -> Optional[OAuthConfig]:
        """Return OAuth configuration for DocuSign."""
        env = self._get_environment()
        oauth_base = self.OAUTH_URLS[env]

        return OAuthConfig(
            client_id=os.environ.get("DOCUSIGN_CLIENT_ID", ""),
            client_secret=os.environ.get("DOCUSIGN_CLIENT_SECRET", ""),
            authorize_url=f"{oauth_base}/oauth/auth",
            token_url=f"{oauth_base}/oauth/token",
            scopes=["signature", "impersonation"],
            redirect_uri=os.environ.get(
                "DOCUSIGN_REDIRECT_URI",
                "http://localhost:3000/integrations/docusign/callback"
            ),
        )

    def _get_environment(self) -> DocuSignEnvironment:
        """Get the DocuSign environment from config."""
        env = self.configuration.get("environment", "demo").lower()
        return DocuSignEnvironment.PRODUCTION if env == "production" else DocuSignEnvironment.DEMO

    def _get_api_base_url(self) -> str:
        """Get the API base URL."""
        if self.credentials.get("base_url"):
            return self.credentials["base_url"]
        return self.API_URLS[self._get_environment()]

    def _get_oauth_base_url(self) -> str:
        """Get the OAuth base URL."""
        if self.credentials.get("oauth_base_url"):
            return self.credentials["oauth_base_url"]
        return self.OAUTH_URLS[self._get_environment()]

    @classmethod
    async def _get_client(cls) -> httpx.AsyncClient:
        """Get or create shared AsyncClient with connection pooling."""
        async with cls._client_lock:
            if cls._client is None or cls._client.is_closed:
                cls._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout=cls.REQUEST_TIMEOUT, connect=10.0),
                    limits=httpx.Limits(
                        max_connections=100,
                        max_keepalive_connections=20,
                        keepalive_expiry=30.0,
                    ),
                )
                logger.info("Created new DocuSign API client with connection pooling")
            return cls._client

    @classmethod
    async def close_client(cls):
        """Close the shared client."""
        async with cls._client_lock:
            if cls._client and not cls._client.is_closed:
                await cls._client.aclose()
                cls._client = None

    def _calculate_retry_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        if retry_after:
            return min(retry_after, self.MAX_RETRY_DELAY)
        delay = self.BASE_RETRY_DELAY * (2 ** attempt)
        delay = min(delay, self.MAX_RETRY_DELAY)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0.1, delay + jitter)

    async def _get_jwt_token(self) -> str:
        """Get JWT access token."""
        integration_key = self.credentials.get("integration_key")
        user_id = self.credentials.get("user_id")
        private_key = self.credentials.get("private_key")

        if not all([integration_key, user_id, private_key]):
            raise ValueError("Missing JWT credentials: integration_key, user_id, or private_key")

        cache_key = f"{integration_key}:{user_id}"

        async with self._token_lock:
            cached = self._token_cache.get(cache_key)
            if cached and datetime.utcnow() < cached["expires_at"]:
                return cached["access_token"]

            try:
                import jwt as pyjwt

                oauth_base = self._get_oauth_base_url()
                now = datetime.utcnow()

                payload = {
                    "iss": integration_key,
                    "sub": user_id,
                    "aud": oauth_base.replace("https://", ""),
                    "iat": now,
                    "exp": now + timedelta(hours=1),
                    "scope": "signature impersonation",
                }

                assertion = pyjwt.encode(payload, private_key, algorithm="RS256")

                client = await self._get_client()
                response = await client.post(
                    f"{oauth_base}/oauth/token",
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": assertion,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code != 200:
                    raise ValueError(f"JWT token request failed: {response.text}")

                token_data = response.json()
                access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)

                self._token_cache[cache_key] = {
                    "access_token": access_token,
                    "expires_at": datetime.utcnow() + timedelta(seconds=expires_in - 300),
                }

                return access_token

            except Exception as e:
                logger.error(f"JWT token request failed: {e}")
                raise

    async def _get_access_token(self) -> str:
        """Get access token (OAuth2 or JWT)."""
        if self.credentials.get("access_token"):
            return self.credentials["access_token"]
        return await self._get_jwt_token()

    async def validate_credentials(self) -> bool:
        """Validate DocuSign credentials."""
        try:
            token = await self._get_access_token()
            return bool(token)
        except Exception as e:
            logger.error(f"DocuSign credential validation failed: {e}")
            return False

    async def refresh_tokens(self) -> Optional[OAuthTokens]:
        """Refresh tokens - JWT handles this automatically."""
        return None

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make HTTP request with automatic retries."""
        account_id = self.credentials.get("account_id", "")
        base_url = self._get_api_base_url()
        endpoint = endpoint.replace("{accountId}", account_id)
        url = f"{base_url}{endpoint}"

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                access_token = await self._get_access_token()
                client = await self._get_client()

                request_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    **(headers or {}),
                }

                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=request_headers,
                )

                if response.status_code == 429:
                    if attempt < self.MAX_RETRIES:
                        retry_after = response.headers.get("Retry-After")
                        delay = self._calculate_retry_delay(
                            attempt, float(retry_after) if retry_after else None
                        )
                        await asyncio.sleep(delay)
                        continue

                if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue

                return response

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                if attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise

        raise httpx.HTTPError("Request failed after all retries")

    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Return list of available DocuSign actions."""
        return [
            {
                "name": "send_envelope",
                "display_name": "Send Envelope",
                "description": "Send a document for e-signature",
                "input_schema": {
                    "type": "object",
                    "required": ["document_base64", "document_name", "signers"],
                    "properties": {
                        "document_base64": {"type": "string", "description": "Base64-encoded document"},
                        "document_name": {"type": "string", "description": "Document name"},
                        "signers": {
                            "type": "array",
                            "description": "List of signers",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "routing_order": {"type": "integer"},
                                },
                            },
                        },
                        "email_subject": {"type": "string", "description": "Email subject"},
                        "status": {
                            "type": "string",
                            "enum": ["sent", "created"],
                            "description": "sent to send immediately, created for draft"
                        },
                    },
                },
            },
            {
                "name": "create_envelope",
                "display_name": "Create & Send Envelope",
                "description": "Alias for send_envelope - create and send a signing request",
                "input_schema": {
                    "type": "object",
                    "required": ["document_base64", "document_name", "signers"],
                    "properties": {
                        "document_base64": {"type": "string", "description": "Base64-encoded document"},
                        "document_name": {"type": "string", "description": "Document name"},
                        "signers": {
                            "type": "array",
                            "description": "List of signers",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "routing_order": {"type": "integer"},
                                },
                            },
                        },
                        "email_subject": {"type": "string", "description": "Email subject"},
                        "status": {"type": "string", "enum": ["sent", "created"]},
                    },
                },
            },
            {
                "name": "get_envelope_status",
                "display_name": "Get Envelope Status",
                "description": "Get the status of an envelope",
                "input_schema": {
                    "type": "object",
                    "required": ["envelope_id"],
                    "properties": {
                        "envelope_id": {"type": "string", "description": "DocuSign envelope ID"},
                    },
                },
            },
            {
                "name": "list_envelopes",
                "display_name": "List Envelopes",
                "description": "List envelopes with optional filters",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "from_date": {"type": "string", "description": "Start date (ISO format)"},
                        "status": {"type": "string", "description": "Filter by status"},
                        "count": {"type": "integer", "description": "Number of results (max 100)"},
                    },
                },
            },
            {
                "name": "download_document",
                "display_name": "Download Document",
                "description": "Download signed document",
                "input_schema": {
                    "type": "object",
                    "required": ["envelope_id"],
                    "properties": {
                        "envelope_id": {"type": "string", "description": "DocuSign envelope ID"},
                        "document_id": {"type": "string", "description": "Document ID (default: combined)"},
                    },
                },
            },
            {
                "name": "get_envelope_documents",
                "display_name": "Get Envelope Documents",
                "description": "Alias for download_document - download documents from envelope",
                "input_schema": {
                    "type": "object",
                    "required": ["envelope_id"],
                    "properties": {
                        "envelope_id": {"type": "string", "description": "DocuSign envelope ID"},
                        "document_id": {"type": "string", "description": "Document ID (default: combined)"},
                    },
                },
            },
            {
                "name": "void_envelope",
                "display_name": "Void Envelope",
                "description": "Cancel an envelope",
                "input_schema": {
                    "type": "object",
                    "required": ["envelope_id"],
                    "properties": {
                        "envelope_id": {"type": "string"},
                        "void_reason": {"type": "string", "description": "Reason for voiding"},
                    },
                },
            },
            {
                "name": "send_from_template",
                "display_name": "Send from Template",
                "description": "Create and send envelope from a template",
                "input_schema": {
                    "type": "object",
                    "required": ["template_id", "signers"],
                    "properties": {
                        "template_id": {"type": "string", "description": "Template ID to use"},
                        "email_subject": {"type": "string", "description": "Email subject"},
                        "signers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"},
                                    "name": {"type": "string"},
                                    "role_name": {"type": "string"}
                                }
                            }
                        }
                    }
                },
            },
            {
                "name": "test_connection",
                "display_name": "Test Connection",
                "description": "Test DocuSign connection",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]

    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """Execute a DocuSign action."""
        start_time = datetime.utcnow()

        try:
            if action_name in ["send_envelope", "create_envelope"]:
                result = await self._send_envelope(parameters)
            elif action_name == "get_envelope_status":
                result = await self._get_envelope_status(parameters)
            elif action_name == "list_envelopes":
                result = await self._list_envelopes(parameters)
            elif action_name in ["download_document", "get_envelope_documents"]:
                result = await self._download_document(parameters)
            elif action_name == "void_envelope":
                result = await self._void_envelope(parameters)
            elif action_name == "send_from_template":
                result = await self._send_from_template(parameters)
            elif action_name == "test_connection":
                result = await self.test_connection()
            else:
                result = IntegrationResult(
                    success=False,
                    error_message=f"Unknown action: {action_name}",
                    error_code="UNKNOWN_ACTION",
                )

            result.duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return result

        except Exception as e:
            logger.error(f"DocuSign action {action_name} failed: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )

    async def test_connection(self) -> IntegrationResult:
        """Test DocuSign connection."""
        try:
            response = await self._make_request("GET", "/v2.1/accounts/{accountId}")

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "account_id": data.get("accountId"),
                        "account_name": data.get("accountName"),
                    },
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Connection test failed",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="CONNECTION_ERROR")

    async def _send_envelope(self, params: Dict[str, Any]) -> IntegrationResult:
        """Send a document for e-signature."""
        required = ["document_base64", "document_name", "signers"]
        missing = [k for k in required if not params.get(k)]
        if missing:
            return IntegrationResult(
                success=False,
                error_message=f"Missing: {', '.join(missing)}",
                error_code="MISSING_PARAMS",
            )

        try:
            signers = params["signers"]
            signer_objs = []
            for idx, signer in enumerate(signers, start=1):
                routing_order = signer.get("routing_order", idx)
                signer_objs.append({
                    "email": signer["email"],
                    "name": signer["name"],
                    "recipientId": str(idx),
                    "routingOrder": str(routing_order),
                    "tabs": {
                        "signHereTabs": [{
                            "documentId": "1",
                            "pageNumber": "1",
                            "xPosition": "100",
                            "yPosition": str(100 + (idx - 1) * 100),
                        }]
                    },
                })

            envelope = {
                "emailSubject": params.get("email_subject", f"Please sign: {params['document_name']}"),
                "documents": [{
                    "documentBase64": params["document_base64"],
                    "name": params["document_name"],
                    "fileExtension": params.get("file_extension", "pdf"),
                    "documentId": "1",
                }],
                "recipients": {"signers": signer_objs},
                "status": params.get("status", "sent"),
            }

            response = await self._make_request("POST", "/v2.1/accounts/{accountId}/envelopes", json=envelope)

            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "envelope_id": data.get("envelopeId"),
                        "status": data.get("status"),
                        "uri": data.get("uri"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Failed to create envelope"),
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _get_envelope_status(self, params: Dict[str, Any]) -> IntegrationResult:
        """Get envelope status."""
        envelope_id = params.get("envelope_id")
        if not envelope_id:
            return IntegrationResult(success=False, error_message="Missing envelope_id", error_code="MISSING_PARAMS")

        try:
            response = await self._make_request("GET", f"/v2.1/accounts/{{accountId}}/envelopes/{envelope_id}")

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "envelope_id": data.get("envelopeId"),
                        "status": data.get("status"),
                        "sent_datetime": data.get("sentDateTime"),
                        "completed_datetime": data.get("completedDateTime"),
                        "voided_datetime": data.get("voidedDateTime"),
                        "email_subject": data.get("emailSubject"),
                    },
                    raw_response=data,
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Failed to get envelope",
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _list_envelopes(self, params: Dict[str, Any]) -> IntegrationResult:
        """List envelopes."""
        try:
            query_params = {}
            if params.get("from_date"):
                query_params["from_date"] = params["from_date"]
            if params.get("status"):
                query_params["status"] = params["status"]
            if params.get("count"):
                query_params["count"] = str(min(params["count"], 100))

            response = await self._make_request("GET", "/v2.1/accounts/{accountId}/envelopes", params=query_params)

            if response.status_code == 200:
                data = response.json()
                envelopes = [
                    {
                        "envelope_id": env.get("envelopeId"),
                        "status": env.get("status"),
                        "email_subject": env.get("emailSubject"),
                        "sent_datetime": env.get("sentDateTime"),
                        "completed_datetime": env.get("completedDateTime"),
                    }
                    for env in data.get("envelopes", [])
                ]
                return IntegrationResult(
                    success=True,
                    data={
                        "envelopes": envelopes,
                        "total_count": data.get("totalSetSize", len(envelopes)),
                        "count": len(envelopes)
                    },
                    raw_response=data,
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to list", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _download_document(self, params: Dict[str, Any]) -> IntegrationResult:
        """Download signed document."""
        envelope_id = params.get("envelope_id")
        if not envelope_id:
            return IntegrationResult(success=False, error_message="Missing envelope_id", error_code="MISSING_PARAMS")

        document_id = params.get("document_id", "combined")

        try:
            response = await self._make_request(
                "GET",
                f"/v2.1/accounts/{{accountId}}/envelopes/{envelope_id}/documents/{document_id}",
                headers={"Accept": "application/pdf"},
            )

            if response.status_code == 200:
                doc_base64 = base64.b64encode(response.content).decode("utf-8")
                return IntegrationResult(
                    success=True,
                    data={
                        "envelope_id": envelope_id,
                        "document_base64": doc_base64,
                        "document_name": f"envelope_{envelope_id}_{document_id}.pdf",
                        "size_bytes": len(response.content),
                    },
                )
            else:
                return IntegrationResult(success=False, error_message="Failed to download", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _void_envelope(self, params: Dict[str, Any]) -> IntegrationResult:
        """Void an envelope."""
        envelope_id = params.get("envelope_id")
        if not envelope_id:
            return IntegrationResult(success=False, error_message="Missing envelope_id", error_code="MISSING_PARAMS")

        try:
            response = await self._make_request(
                "PUT",
                f"/v2.1/accounts/{{accountId}}/envelopes/{envelope_id}",
                json={"status": "voided", "voidedReason": params.get("void_reason", "Voided by workflow")},
            )

            if response.status_code == 200:
                return IntegrationResult(success=True, data={"envelope_id": envelope_id, "status": "voided", "success": True})
            else:
                return IntegrationResult(success=False, error_message="Failed to void", error_code=str(response.status_code))
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")

    async def _send_from_template(self, params: Dict[str, Any]) -> IntegrationResult:
        """Send envelope from template."""
        required = ["template_id", "signers"]
        missing = [k for k in required if not params.get(k)]
        if missing:
            return IntegrationResult(
                success=False,
                error_message=f"Missing: {', '.join(missing)}",
                error_code="MISSING_PARAMS",
            )

        try:
            template_roles = []
            for signer in params.get("signers", []):
                template_roles.append({
                    "email": signer["email"],
                    "name": signer["name"],
                    "roleName": signer.get("role_name", "Signer")
                })

            envelope_definition = {
                "templateId": params["template_id"],
                "templateRoles": template_roles,
                "status": "sent"
            }

            if params.get("email_subject"):
                envelope_definition["emailSubject"] = params["email_subject"]

            response = await self._make_request(
                "POST",
                "/v2.1/accounts/{accountId}/envelopes",
                json=envelope_definition,
            )

            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "envelope_id": data.get("envelopeId"),
                        "status": data.get("status"),
                        "uri": data.get("uri"),
                    },
                    raw_response=data,
                )
            else:
                data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=data.get("message", "Failed to create envelope from template"),
                    error_code=str(response.status_code),
                )
        except Exception as e:
            return IntegrationResult(success=False, error_message=str(e), error_code="EXECUTION_ERROR")
