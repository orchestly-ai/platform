"""
DocuSign E-Signature Integration

Real DocuSign API integration for e-signature workflows.
Supports sending documents for signature, tracking status, and downloading signed documents.

Supported Actions:
- send_envelope: Send document for e-signature
- get_envelope_status: Get signing status
- list_envelopes: List envelopes with filters
- download_document: Download signed document
- void_envelope: Cancel an envelope
- resend_envelope: Resend envelope notifications

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
"""

import asyncio
import base64
import random
import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, ClassVar
from enum import Enum

from .base import BaseIntegration, IntegrationResult, IntegrationError, AuthType

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
    """

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

    # JWT token cache (class-level, keyed by integration_key)
    _token_cache: ClassVar[Dict[str, Dict[str, Any]]] = {}
    _token_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0
    REQUEST_TIMEOUT = 60.0  # DocuSign can be slow for large documents

    # Status codes that should trigger retries
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    @property
    def name(self) -> str:
        return "docusign"

    @property
    def display_name(self) -> str:
        return "DocuSign"

    @property
    def auth_type(self) -> AuthType:
        # JWT is essentially a special bearer token
        return AuthType.BEARER_TOKEN

    @property
    def supported_actions(self) -> List[str]:
        return [
            "send_envelope",
            "get_envelope_status",
            "list_envelopes",
            "download_document",
            "void_envelope",
            "resend_envelope",
            "test_connection",
        ]

    def _validate_credentials(self) -> None:
        """Validate DocuSign credentials."""
        super()._validate_credentials()

        # Check for OAuth2 token
        if self.auth_credentials.get("access_token"):
            if not self.auth_credentials.get("account_id"):
                raise IntegrationError(
                    "DocuSign OAuth requires 'account_id'",
                    code="MISSING_ACCOUNT_ID",
                )
            return

        # Check for JWT credentials
        jwt_required = ["integration_key", "user_id", "account_id", "private_key"]
        missing = [k for k in jwt_required if not self.auth_credentials.get(k)]

        if missing:
            raise IntegrationError(
                f"DocuSign JWT requires: {', '.join(missing)}. "
                f"Or provide 'access_token' + 'account_id' for OAuth2.",
                code="MISSING_CREDENTIALS",
            )

    def _get_environment(self) -> DocuSignEnvironment:
        """Get the DocuSign environment from config."""
        env = self.configuration.get("environment", "demo").lower()
        return DocuSignEnvironment.PRODUCTION if env == "production" else DocuSignEnvironment.DEMO

    def _get_api_base_url(self) -> str:
        """Get the API base URL for current environment."""
        # Allow custom base_url override (for different regions)
        if self.auth_credentials.get("base_url"):
            return self.auth_credentials["base_url"]
        return self.API_URLS[self._get_environment()]

    def _get_oauth_base_url(self) -> str:
        """Get the OAuth base URL for current environment."""
        if self.auth_credentials.get("oauth_base_url"):
            return self.auth_credentials["oauth_base_url"]
        return self.OAUTH_URLS[self._get_environment()]

    @classmethod
    async def _get_client(cls) -> httpx.AsyncClient:
        """Get or create shared AsyncClient with connection pooling."""
        async with cls._client_lock:
            if cls._client is None or cls._client.is_closed:
                cls._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        timeout=cls.REQUEST_TIMEOUT,
                        connect=10.0,
                    ),
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
        """Close the shared client (call on application shutdown)."""
        async with cls._client_lock:
            if cls._client and not cls._client.is_closed:
                await cls._client.aclose()
                cls._client = None
                logger.info("Closed DocuSign API client")

    def _calculate_retry_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        if retry_after:
            return min(retry_after, self.MAX_RETRY_DELAY)

        delay = self.BASE_RETRY_DELAY * (2 ** attempt)
        delay = min(delay, self.MAX_RETRY_DELAY)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0.1, delay + jitter)

    async def _get_jwt_token(self) -> str:
        """
        Get JWT access token, using cache or requesting new one.

        Returns:
            Access token string

        Raises:
            IntegrationError: If token request fails
        """
        integration_key = self.auth_credentials["integration_key"]
        cache_key = f"{integration_key}:{self.auth_credentials['user_id']}"

        async with self._token_lock:
            # Check cache
            cached = self._token_cache.get(cache_key)
            if cached and datetime.utcnow() < cached["expires_at"]:
                return cached["access_token"]

            # Request new token
            try:
                import jwt as pyjwt

                private_key = self.auth_credentials["private_key"]
                user_id = self.auth_credentials["user_id"]
                oauth_base = self._get_oauth_base_url()

                # Build JWT assertion
                now = datetime.utcnow()
                payload = {
                    "iss": integration_key,
                    "sub": user_id,
                    "aud": oauth_base.replace("https://", ""),
                    "iat": now,
                    "exp": now + timedelta(hours=1),
                    "scope": "signature impersonation",
                }

                # Sign JWT
                assertion = pyjwt.encode(payload, private_key, algorithm="RS256")

                # Exchange for access token
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
                    error_data = response.json() if response.text else {}
                    raise IntegrationError(
                        f"JWT token request failed: {error_data.get('error_description', response.text)}",
                        code="JWT_AUTH_FAILED",
                        status_code=response.status_code,
                    )

                token_data = response.json()
                access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)

                # Cache token (expire 5 min early)
                self._token_cache[cache_key] = {
                    "access_token": access_token,
                    "expires_at": datetime.utcnow() + timedelta(seconds=expires_in - 300),
                }

                logger.info("Successfully obtained DocuSign JWT access token")
                return access_token

            except IntegrationError:
                raise
            except Exception as e:
                logger.error(f"JWT token request failed: {e}")
                raise IntegrationError(
                    f"Failed to obtain JWT token: {str(e)}",
                    code="JWT_AUTH_FAILED",
                )

    async def _get_access_token(self) -> str:
        """Get access token (OAuth2 or JWT)."""
        if self.auth_credentials.get("access_token"):
            return self.auth_credentials["access_token"]
        return await self._get_jwt_token()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[bytes] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Make HTTP request to DocuSign API with automatic retries.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., '/v2.1/accounts/{accountId}/envelopes')
            json: JSON payload
            data: Raw bytes data
            params: Query parameters
            headers: Additional headers

        Returns:
            httpx.Response

        Raises:
            IntegrationError: If request fails after all retries
        """
        account_id = self.auth_credentials["account_id"]
        base_url = self._get_api_base_url()

        # Substitute account_id in endpoint
        endpoint = endpoint.replace("{accountId}", account_id)
        url = f"{base_url}{endpoint}"

        last_error: Optional[Exception] = None

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
                    content=data,
                    params=params,
                    headers=request_headers,
                )

                # Handle rate limiting
                if response.status_code == 429:
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
                            f"DocuSign rate limited on {method} {endpoint}, "
                            f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Handle server errors
                if response.status_code in self.RETRYABLE_STATUS_CODES and attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"DocuSign API returned {response.status_code} for {method} {endpoint}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue

                return response

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"DocuSign connection error: {str(e)}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise IntegrationError(
                    f"Connection failed after {self.MAX_RETRIES + 1} attempts: {str(e)}",
                    code="CONNECTION_ERROR",
                )

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during DocuSign API request: {str(e)}")
                raise IntegrationError(
                    f"Unexpected error: {str(e)}",
                    code="UNKNOWN_ERROR",
                )

        raise IntegrationError(
            f"Request failed after all retries: {str(last_error)}",
            code="MAX_RETRIES_EXCEEDED",
        )

    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
    ) -> IntegrationResult:
        """Execute DocuSign action."""
        self._validate_action(action)
        start_time = datetime.utcnow()

        try:
            if action == "send_envelope":
                result = await self._send_envelope(params)
            elif action == "get_envelope_status":
                result = await self._get_envelope_status(params)
            elif action == "list_envelopes":
                result = await self._list_envelopes(params)
            elif action == "download_document":
                result = await self._download_document(params)
            elif action == "void_envelope":
                result = await self._void_envelope(params)
            elif action == "resend_envelope":
                result = await self._resend_envelope(params)
            elif action == "test_connection":
                result = await self.test_connection()
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
        """Test DocuSign connection by getting account info."""
        try:
            response = await self._make_request(
                method="GET",
                endpoint="/v2.1/accounts/{accountId}",
            )

            if response.status_code == 200:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "account_id": data.get("accountId"),
                        "account_name": data.get("accountName"),
                        "plan_name": data.get("billingPlanName"),
                        "is_default": data.get("isDefault"),
                    },
                )
            else:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("message", "Connection test failed"),
                    error_code=str(response.status_code),
                )

        except Exception as e:
            logger.error(f"DocuSign connection test failed: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="CONNECTION_ERROR",
            )

    async def _send_envelope(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Send a document for e-signature.

        Required params:
            document_base64: Base64-encoded document content
            document_name: Document display name
            signers: List of signers [{"name": "...", "email": "..."}]

        Optional params:
            email_subject: Custom email subject
            email_body: Custom email body
            cc_recipients: List of CC recipients
            status: "sent" (default) or "created" (draft)
        """
        # Validate required params
        required = ["document_base64", "document_name", "signers"]
        missing = [k for k in required if not params.get(k)]
        if missing:
            return IntegrationResult(
                success=False,
                error_message=f"Missing required parameters: {', '.join(missing)}",
                error_code="MISSING_PARAMS",
            )

        signers = params["signers"]
        if not signers or not isinstance(signers, list):
            return IntegrationResult(
                success=False,
                error_message="'signers' must be a non-empty list",
                error_code="INVALID_PARAMS",
            )

        try:
            # Build signers array
            signer_objs = []
            for idx, signer in enumerate(signers, start=1):
                signer_obj = {
                    "email": signer["email"],
                    "name": signer["name"],
                    "recipientId": str(idx),
                    "routingOrder": str(idx),
                    "tabs": {
                        "signHereTabs": [
                            {
                                "documentId": "1",
                                "pageNumber": "1",
                                "xPosition": "100",
                                "yPosition": str(100 + (idx - 1) * 100),
                            }
                        ]
                    },
                }
                signer_objs.append(signer_obj)

            # Build CC recipients
            cc_objs = []
            cc_recipients = params.get("cc_recipients", [])
            for idx, cc in enumerate(cc_recipients, start=len(signers) + 1):
                cc_objs.append({
                    "email": cc["email"],
                    "name": cc["name"],
                    "recipientId": str(idx),
                    "routingOrder": str(idx),
                })

            # Build envelope
            envelope = {
                "emailSubject": params.get("email_subject", f"Please sign: {params['document_name']}"),
                "emailBlurb": params.get("email_body", "Please review and sign the attached document."),
                "documents": [
                    {
                        "documentBase64": params["document_base64"],
                        "name": params["document_name"],
                        "fileExtension": params.get("file_extension", "pdf"),
                        "documentId": "1",
                    }
                ],
                "recipients": {
                    "signers": signer_objs,
                    "carbonCopies": cc_objs if cc_objs else None,
                },
                "status": params.get("status", "sent"),
            }

            response = await self._make_request(
                method="POST",
                endpoint="/v2.1/accounts/{accountId}/envelopes",
                json=envelope,
            )

            if response.status_code in [200, 201]:
                data = response.json()
                return IntegrationResult(
                    success=True,
                    data={
                        "envelope_id": data.get("envelopeId"),
                        "status": data.get("status"),
                        "status_datetime": data.get("statusDateTime"),
                        "uri": data.get("uri"),
                    },
                )
            else:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("message", "Failed to create envelope"),
                    error_code=str(error_data.get("errorCode", response.status_code)),
                )

        except Exception as e:
            logger.error(f"Failed to send DocuSign envelope: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
            )

    async def _get_envelope_status(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Get envelope status.

        Required params:
            envelope_id: DocuSign envelope ID
        """
        envelope_id = params.get("envelope_id")
        if not envelope_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameter: envelope_id",
                error_code="MISSING_PARAMS",
            )

        try:
            # Get envelope info
            response = await self._make_request(
                method="GET",
                endpoint=f"/v2.1/accounts/{{accountId}}/envelopes/{envelope_id}",
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("message", "Failed to get envelope"),
                    error_code=str(response.status_code),
                )

            envelope = response.json()

            # Get recipients
            recipients_response = await self._make_request(
                method="GET",
                endpoint=f"/v2.1/accounts/{{accountId}}/envelopes/{envelope_id}/recipients",
            )

            recipients = []
            if recipients_response.status_code == 200:
                recipients_data = recipients_response.json()
                for signer in recipients_data.get("signers", []):
                    recipients.append({
                        "name": signer.get("name"),
                        "email": signer.get("email"),
                        "status": signer.get("status"),
                        "signed_datetime": signer.get("signedDateTime"),
                        "declined_reason": signer.get("declinedReason"),
                    })

            return IntegrationResult(
                success=True,
                data={
                    "envelope_id": envelope.get("envelopeId"),
                    "status": envelope.get("status"),
                    "sent_datetime": envelope.get("sentDateTime"),
                    "delivered_datetime": envelope.get("deliveredDateTime"),
                    "completed_datetime": envelope.get("completedDateTime"),
                    "declined_datetime": envelope.get("declinedDateTime"),
                    "voided_datetime": envelope.get("voidedDateTime"),
                    "recipients": recipients,
                },
            )

        except Exception as e:
            logger.error(f"Failed to get DocuSign envelope status: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
            )

    async def _list_envelopes(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        List envelopes with optional filters.

        Optional params:
            from_date: Start date (ISO format)
            to_date: End date (ISO format)
            status: Filter by status
            count: Number of results (default 25)
        """
        try:
            query_params = {}

            if params.get("from_date"):
                query_params["from_date"] = params["from_date"]
            if params.get("to_date"):
                query_params["to_date"] = params["to_date"]
            if params.get("status"):
                query_params["status"] = params["status"]
            if params.get("count"):
                query_params["count"] = str(params["count"])

            response = await self._make_request(
                method="GET",
                endpoint="/v2.1/accounts/{accountId}/envelopes",
                params=query_params,
            )

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
                        "total_count": data.get("totalSetSize"),
                        "result_count": len(envelopes),
                    },
                )
            else:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("message", "Failed to list envelopes"),
                    error_code=str(response.status_code),
                )

        except Exception as e:
            logger.error(f"Failed to list DocuSign envelopes: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
            )

    async def _download_document(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Download signed document.

        Required params:
            envelope_id: DocuSign envelope ID

        Optional params:
            document_id: Specific document ID (default "combined" for all)
        """
        envelope_id = params.get("envelope_id")
        if not envelope_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameter: envelope_id",
                error_code="MISSING_PARAMS",
            )

        document_id = params.get("document_id", "combined")

        try:
            response = await self._make_request(
                method="GET",
                endpoint=f"/v2.1/accounts/{{accountId}}/envelopes/{envelope_id}/documents/{document_id}",
                headers={"Accept": "application/pdf"},
            )

            if response.status_code == 200:
                # Return base64-encoded document
                document_bytes = response.content
                document_base64 = base64.b64encode(document_bytes).decode("utf-8")

                return IntegrationResult(
                    success=True,
                    data={
                        "envelope_id": envelope_id,
                        "document_id": document_id,
                        "document_base64": document_base64,
                        "content_type": response.headers.get("Content-Type", "application/pdf"),
                        "size_bytes": len(document_bytes),
                    },
                )
            else:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("message", "Failed to download document"),
                    error_code=str(response.status_code),
                )

        except Exception as e:
            logger.error(f"Failed to download DocuSign document: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
            )

    async def _void_envelope(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Void (cancel) an envelope.

        Required params:
            envelope_id: DocuSign envelope ID
            void_reason: Reason for voiding
        """
        envelope_id = params.get("envelope_id")
        void_reason = params.get("void_reason", "Voided by workflow")

        if not envelope_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameter: envelope_id",
                error_code="MISSING_PARAMS",
            )

        try:
            response = await self._make_request(
                method="PUT",
                endpoint=f"/v2.1/accounts/{{accountId}}/envelopes/{envelope_id}",
                json={
                    "status": "voided",
                    "voidedReason": void_reason,
                },
            )

            if response.status_code == 200:
                return IntegrationResult(
                    success=True,
                    data={
                        "envelope_id": envelope_id,
                        "status": "voided",
                        "void_reason": void_reason,
                    },
                )
            else:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("message", "Failed to void envelope"),
                    error_code=str(response.status_code),
                )

        except Exception as e:
            logger.error(f"Failed to void DocuSign envelope: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
            )

    async def _resend_envelope(self, params: Dict[str, Any]) -> IntegrationResult:
        """
        Resend envelope notifications.

        Required params:
            envelope_id: DocuSign envelope ID
        """
        envelope_id = params.get("envelope_id")
        if not envelope_id:
            return IntegrationResult(
                success=False,
                error_message="Missing required parameter: envelope_id",
                error_code="MISSING_PARAMS",
            )

        try:
            response = await self._make_request(
                method="PUT",
                endpoint=f"/v2.1/accounts/{{accountId}}/envelopes/{envelope_id}/recipients",
                params={"resend_envelope": "true"},
            )

            if response.status_code in [200, 201]:
                return IntegrationResult(
                    success=True,
                    data={
                        "envelope_id": envelope_id,
                        "resent": True,
                    },
                )
            else:
                error_data = response.json() if response.text else {}
                return IntegrationResult(
                    success=False,
                    error_message=error_data.get("message", "Failed to resend envelope"),
                    error_code=str(response.status_code),
                )

        except Exception as e:
            logger.error(f"Failed to resend DocuSign envelope: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
            )
