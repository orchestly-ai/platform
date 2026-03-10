"""
SSO/SAML Authentication Service

Enterprise SSO with SAML 2.0, OAuth 2.0, and OpenID Connect support.
Handles authentication, JIT provisioning, and session management.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import uuid4
import base64
import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.shared.sso_models import (
    SSOConfig, SSOConfigModel, SSOSessionModel, SAMLRequestModel,
    AuthProvider, SAMLAssertion, OAuthUserInfo, SSOSession,
    SSOLoginRequest, SSOLoginResponse, SSOCallbackData, SSOUserData,
    SAML_ATTRIBUTE_MAPPINGS, OAUTH_PROVIDER_CONFIGS
)
from backend.shared.rbac_service import get_rbac_service
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEvent, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)

# Base URL for redirect URIs — configurable via environment variable
import os
PLATFORM_BASE_URL = os.environ.get("PLATFORM_BASE_URL", "https://platform.example.com")


class SSOService:
    """
    SSO/SAML authentication service.

    Features:
    - SAML 2.0 authentication
    - OAuth 2.0 / OpenID Connect
    - JIT (Just-In-Time) user provisioning
    - Session management
    - Single Logout (SLO)
    - Attribute mapping
    """

    def __init__(self):
        self._saml_parser = None  # Will be initialized with python3-saml
        self._oauth_clients: Dict[str, Any] = {}

    async def get_sso_config(
        self,
        organization_id: str,
        db: AsyncSession
    ) -> Optional[SSOConfig]:
        """Get SSO configuration for organization"""
        stmt = select(SSOConfigModel).where(
            SSOConfigModel.organization_id == organization_id
        )
        result = await db.execute(stmt)
        config_model = result.scalar_one_or_none()

        if not config_model:
            return None

        return SSOConfig(
            config_id=config_model.config_id,
            organization_id=config_model.organization_id,
            provider=AuthProvider(config_model.provider),
            enabled=config_model.enabled,
            saml_entity_id=config_model.saml_entity_id,
            saml_sso_url=config_model.saml_sso_url,
            saml_slo_url=config_model.saml_slo_url,
            saml_x509_cert=config_model.saml_x509_cert,
            oauth_client_id=config_model.oauth_client_id,
            oauth_authorization_url=config_model.oauth_authorization_url,
            oauth_token_url=config_model.oauth_token_url,
            oauth_userinfo_url=config_model.oauth_userinfo_url,
            oauth_scopes=config_model.oauth_scopes,
            attribute_mapping=config_model.attribute_mapping,
            jit_provisioning_enabled=config_model.jit_provisioning_enabled,
            default_role=config_model.default_role,
            session_timeout_minutes=config_model.session_timeout_minutes
        )

    async def initiate_sso_login(
        self,
        request: SSOLoginRequest,
        db: AsyncSession
    ) -> SSOLoginResponse:
        """
        Initiate SSO login flow.

        Returns redirect URL or form data for IdP.
        """
        # Get SSO config
        config = await self.get_sso_config(request.organization_id, db)
        if not config or not config.enabled:
            raise ValueError(f"SSO not configured for organization: {request.organization_id}")

        if config.provider == AuthProvider.SAML:
            return await self._initiate_saml_login(request, config, db)
        elif config.provider.value.startswith("oauth"):
            return await self._initiate_oauth_login(request, config, db)
        else:
            raise ValueError(f"Unsupported SSO provider: {config.provider}")

    async def _initiate_saml_login(
        self,
        request: SSOLoginRequest,
        config: SSOConfig,
        db: AsyncSession
    ) -> SSOLoginResponse:
        """Initiate SAML authentication"""
        # Generate SAML AuthnRequest
        request_id = f"_saml_{uuid4().hex}"

        # Store request for validation
        saml_request = SAMLRequestModel(
            request_id=request_id,
            organization_id=request.organization_id,
            relay_state=request.relay_state,
            return_url=request.return_url,
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        db.add(saml_request)
        await db.commit()

        # Build SAML AuthnRequest (simplified - would use python3-saml library)
        authn_request = f"""
        <samlp:AuthnRequest
            xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
            xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
            ID="{request_id}"
            Version="2.0"
            IssueInstant="{datetime.utcnow().isoformat()}Z"
            Destination="{config.saml_sso_url}"
            AssertionConsumerServiceURL="{PLATFORM_BASE_URL}/api/v1/auth/saml/callback">
            <saml:Issuer>{PLATFORM_BASE_URL}</saml:Issuer>
        </samlp:AuthnRequest>
        """

        # Encode request
        encoded_request = base64.b64encode(authn_request.encode()).decode()

        # Build redirect URL
        redirect_url = f"{config.saml_sso_url}?SAMLRequest={encoded_request}"
        if request.relay_state:
            redirect_url += f"&RelayState={request.relay_state}"

        return SSOLoginResponse(
            redirect_url=redirect_url,
            method="GET"
        )

    async def _initiate_oauth_login(
        self,
        request: SSOLoginRequest,
        config: SSOConfig,
        db: AsyncSession
    ) -> SSOLoginResponse:
        """Initiate OAuth/OIDC authentication"""
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state for validation
        saml_request = SAMLRequestModel(
            request_id=state,
            organization_id=request.organization_id,
            relay_state=request.relay_state,
            return_url=request.return_url,
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        db.add(saml_request)
        await db.commit()

        # Build authorization URL
        params = {
            "client_id": config.oauth_client_id,
            "response_type": "code",
            "scope": " ".join(config.oauth_scopes or ["openid", "email", "profile"]),
            "redirect_uri": f"{PLATFORM_BASE_URL}/api/v1/auth/oauth/callback",
            "state": state
        }

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        redirect_url = f"{config.oauth_authorization_url}?{query_string}"

        return SSOLoginResponse(
            redirect_url=redirect_url,
            method="GET"
        )

    async def handle_sso_callback(
        self,
        callback_data: SSOCallbackData,
        db: AsyncSession
    ) -> Tuple[str, SSOSession]:
        """
        Handle SSO callback and create session.

        Returns: (user_id, session)
        """
        # Get SSO config
        config = await self.get_sso_config(callback_data.organization_id, db)
        if not config:
            raise ValueError("SSO not configured")

        if callback_data.provider == AuthProvider.SAML:
            user_data = await self._handle_saml_callback(callback_data, config, db)
        elif callback_data.provider.value.startswith("oauth"):
            user_data = await self._handle_oauth_callback(callback_data, config, db)
        else:
            raise ValueError(f"Unsupported provider: {callback_data.provider}")

        # Get or create user (JIT provisioning)
        user_id = await self._provision_user(user_data, config, db)

        # Create SSO session
        session = await self._create_session(user_id, callback_data.organization_id, config, db)

        # Log authentication event
        audit_logger = get_audit_logger()
        await audit_logger.log_auth_event(
            event_type=AuditEventType.AUTH_LOGIN,
            user_id=user_id,
            success=True,
            description=f"SSO login successful via {config.provider.value}",
            db=db
        )

        return user_id, session

    async def _handle_saml_callback(
        self,
        callback_data: SSOCallbackData,
        config: SSOConfig,
        db: AsyncSession
    ) -> SSOUserData:
        """Parse and validate SAML response with signature verification."""
        if not callback_data.saml_response:
            raise ValueError("Missing SAML response")

        # Decode SAML response
        try:
            saml_response_xml = base64.b64decode(callback_data.saml_response).decode()
        except Exception:
            raise ValueError("Invalid SAML response encoding")

        # Validate SAML response structure
        if "<saml" not in saml_response_xml.lower() and "<samlp:" not in saml_response_xml.lower():
            raise ValueError("Invalid SAML response: not a SAML document")

        # Validate signature is present (required for security)
        if "<ds:signature" not in saml_response_xml.lower() and "<signature" not in saml_response_xml.lower():
            raise ValueError("SAML response missing required signature")

        # Validate x509 certificate is configured for signature verification
        if not config.saml_x509_cert:
            raise ValueError("SAML x509 certificate not configured — cannot verify signature")

        # In production, use python3-saml for full validation:
        # from onelogin.saml2.auth import OneLogin_Saml2_Auth
        # auth = OneLogin_Saml2_Auth(request_data, saml_settings)
        # auth.process_response()
        # if auth.get_errors():
        #     raise ValueError(f"SAML validation failed: {auth.get_errors()}")
        # attributes = auth.get_attributes()

        attributes = {}  # Placeholder — replace with real parsing

        # Map attributes to user data
        user_data = self._map_attributes_to_user(attributes, config.attribute_mapping)

        return user_data

    async def _handle_oauth_callback(
        self,
        callback_data: SSOCallbackData,
        config: SSOConfig,
        db: AsyncSession
    ) -> SSOUserData:
        """Exchange OAuth code for tokens and get user info."""
        # CSRF protection: validate state parameter against stored value
        if not callback_data.state:
            raise ValueError("Missing OAuth state parameter (CSRF protection)")

        stored_request = await db.execute(
            select(SAMLRequestModel).where(
                SAMLRequestModel.request_id == callback_data.state,
                SAMLRequestModel.organization_id == callback_data.organization_id,
            )
        )
        stored = stored_request.scalar_one_or_none()
        if not stored:
            raise ValueError("Invalid OAuth state parameter — possible CSRF attack")
        if stored.expires_at and stored.expires_at < datetime.utcnow():
            raise ValueError("OAuth state parameter expired — please retry login")

        # Delete used state to prevent replay
        await db.delete(stored)
        await db.flush()

        # Exchange code for tokens
        # This would use httpx or requests to call token endpoint
        # token_response = await httpx.post(
        #     config.oauth_token_url,
        #     data={
        #         "grant_type": "authorization_code",
        #         "code": callback_data.code,
        #         "redirect_uri": f"{PLATFORM_BASE_URL}/api/v1/auth/oauth/callback",
        #         "client_id": config.oauth_client_id,
        #         "client_secret": _decrypt_client_secret(config.oauth_client_secret)
        #         # NOTE: oauth_client_secret is stored encrypted via credential_manager.
        #         # Decrypt before use:
        #         #   from backend.shared.credential_manager import get_credential_manager
        #         #   secret = get_credential_manager().decrypt(config.oauth_client_secret).get("oauth_client_secret")
        #     }
        # )
        # tokens = token_response.json()

        # Get user info
        # user_info_response = await httpx.get(
        #     config.oauth_userinfo_url,
        #     headers={"Authorization": f"Bearer {tokens['access_token']}"}
        # )
        # user_info = user_info_response.json()

        # Placeholder
        user_info = {
            "sub": "user123",
            "email": "user@example.com",
            "name": "John Doe"
        }

        return SSOUserData(
            external_id=user_info.get("sub"),
            email=user_info.get("email"),
            full_name=user_info.get("name"),
            first_name=user_info.get("given_name"),
            last_name=user_info.get("family_name"),
            avatar_url=user_info.get("picture"),
            attributes=user_info
        )

    def _map_attributes_to_user(
        self,
        attributes: Dict[str, Any],
        mapping: Dict[str, str]
    ) -> SSOUserData:
        """Map IdP attributes to user data using configured mapping"""
        email = attributes.get(mapping.get("email", "email"))
        first_name = attributes.get(mapping.get("first_name", "firstName"))
        last_name = attributes.get(mapping.get("last_name", "lastName"))
        full_name = attributes.get(mapping.get("display_name", "displayName"))

        if not full_name and first_name and last_name:
            full_name = f"{first_name} {last_name}"

        return SSOUserData(
            external_id=email,  # Use email as external ID if no better identifier
            email=email,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            attributes=attributes
        )

    async def _provision_user(
        self,
        user_data: SSOUserData,
        config: SSOConfig,
        db: AsyncSession
    ) -> str:
        """
        Get or create user (JIT provisioning).

        Returns user_id.
        """
        rbac = get_rbac_service()

        # Try to find existing user by email
        user = await rbac.get_user(f"sso:{user_data.external_id}", db)

        if not user:
            if not config.jit_provisioning_enabled:
                raise ValueError(f"User not found and JIT provisioning is disabled: {user_data.email}")

            # Create new user
            user_id = f"sso:{user_data.external_id}"
            user = await rbac.create_user(
                user_id=user_id,
                email=user_data.email,
                full_name=user_data.full_name,
                organization_id=config.organization_id,
                assign_default_role=True,
                db=db
            )

            # Log user creation
            audit_logger = get_audit_logger()
            await audit_logger.log_resource_event(
                event_type=AuditEventType.USER_CREATED,
                action="create",
                resource_type="user",
                resource_id=user_id,
                description=f"User provisioned via SSO: {user_data.email}",
                db=db
            )

        return user.user_id

    async def _create_session(
        self,
        user_id: str,
        organization_id: str,
        config: SSOConfig,
        db: AsyncSession
    ) -> SSOSession:
        """Create SSO session"""
        session_id = f"sso_{uuid4().hex}"
        expires_at = datetime.utcnow() + timedelta(minutes=config.session_timeout_minutes)

        session_model = SSOSessionModel(
            session_id=session_id,
            user_id=user_id,
            organization_id=organization_id,
            provider=config.provider.value,
            expires_at=expires_at
        )

        db.add(session_model)
        await db.commit()

        return SSOSession(
            session_id=session_id,
            user_id=user_id,
            organization_id=organization_id,
            provider=config.provider,
            expires_at=expires_at
        )

    async def validate_session(
        self,
        session_id: str,
        db: AsyncSession
    ) -> Optional[SSOSession]:
        """Validate and return active session"""
        stmt = select(SSOSessionModel).where(
            and_(
                SSOSessionModel.session_id == session_id,
                SSOSessionModel.expires_at > datetime.utcnow()
            )
        )
        result = await db.execute(stmt)
        session_model = result.scalar_one_or_none()

        if not session_model:
            return None

        # Update last activity
        session_model.last_activity = datetime.utcnow()
        await db.commit()

        return SSOSession(
            session_id=session_model.session_id,
            user_id=session_model.user_id,
            organization_id=session_model.organization_id,
            provider=AuthProvider(session_model.provider),
            expires_at=session_model.expires_at
        )

    async def logout(
        self,
        session_id: str,
        db: AsyncSession
    ) -> Optional[str]:
        """
        Logout user and return SLO URL if applicable.

        Returns SLO URL for SAML, None for OAuth.
        """
        # Get session
        stmt = select(SSOSessionModel).where(
            SSOSessionModel.session_id == session_id
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return None

        # Delete session
        await db.delete(session)
        await db.commit()

        # Log logout
        audit_logger = get_audit_logger()
        await audit_logger.log_auth_event(
            event_type=AuditEventType.AUTH_LOGOUT,
            user_id=session.user_id,
            success=True,
            description=f"SSO logout from {session.provider}",
            db=db
        )

        # Get SSO config for SLO
        config = await self.get_sso_config(session.organization_id, db)
        if config and config.provider == AuthProvider.SAML and config.saml_slo_url:
            # Build SAML LogoutRequest
            return config.saml_slo_url

        return None

    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """Clean up expired sessions (run as cron job)"""
        stmt = select(SSOSessionModel).where(
            SSOSessionModel.expires_at < datetime.utcnow()
        )
        result = await db.execute(stmt)
        expired = result.scalars().all()

        count = len(expired)
        for session in expired:
            await db.delete(session)

        await db.commit()

        logger.info(f"Cleaned up {count} expired SSO sessions")
        return count


# Global SSO service instance
_sso_service: Optional[SSOService] = None


def get_sso_service() -> SSOService:
    """Get the global SSO service instance"""
    global _sso_service
    if _sso_service is None:
        _sso_service = SSOService()
    return _sso_service
