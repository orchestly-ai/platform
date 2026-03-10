"""
SSO/SAML Authentication API

Enterprise authentication endpoints with SAML 2.0, OAuth 2.0, and OpenID Connect support.
90% customer requirement, sales blocker for enterprise deals.
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from backend.database.session import get_db
from backend.shared.sso_service import get_sso_service
from backend.shared.sso_models import (
    SSOConfig, SSOLoginRequest, SSOLoginResponse, SSOCallbackData,
    SSOSession, AuthProvider
)
from backend.shared.rbac_service import get_rbac_service, requires_permission, Permission
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEventType
from backend.shared.plan_enforcement import enforce_feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sso", tags=["SSO/SAML"])


# Request/Response Models

class SSOConfigRequest(BaseModel):
    """SSO configuration creation/update request"""
    organization_id: str
    provider: str = Field(..., description="saml, oauth_azure_ad, oauth_okta, etc.")
    enabled: bool = True

    # SAML fields
    saml_entity_id: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_slo_url: Optional[str] = None
    saml_x509_cert: Optional[str] = None

    # OAuth fields
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_authorization_url: Optional[str] = None
    oauth_token_url: Optional[str] = None
    oauth_userinfo_url: Optional[str] = None
    oauth_scopes: Optional[list[str]] = None

    # Settings
    attribute_mapping: dict[str, str] = Field(default_factory=dict)
    jit_provisioning_enabled: bool = True
    default_role: Optional[str] = None
    session_timeout_minutes: int = 480


class SSOConfigResponse(BaseModel):
    """SSO configuration response"""
    config_id: str
    organization_id: str
    provider: str
    enabled: bool

    saml_entity_id: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_slo_url: Optional[str] = None

    oauth_client_id: Optional[str] = None
    oauth_authorization_url: Optional[str] = None
    oauth_scopes: Optional[list[str]] = None

    attribute_mapping: dict[str, str]
    jit_provisioning_enabled: bool
    default_role: Optional[str] = None
    session_timeout_minutes: int

    created_at: datetime
    updated_at: datetime


class LoginInitiateRequest(BaseModel):
    """SSO login initiation request"""
    organization_id: str
    return_url: str
    relay_state: Optional[str] = None


class LoginInitiateResponse(BaseModel):
    """SSO login initiation response"""
    redirect_url: str
    method: str = "GET"
    form_data: Optional[dict[str, str]] = None


class SAMLCallbackRequest(BaseModel):
    """SAML callback request"""
    organization_id: str
    saml_response: str
    relay_state: Optional[str] = None


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request"""
    organization_id: str
    code: str
    state: str


class LoginCallbackResponse(BaseModel):
    """SSO login callback response"""
    session_id: str
    user_id: str
    organization_id: str
    provider: str
    expires_at: datetime
    return_url: Optional[str] = None


class SessionResponse(BaseModel):
    """SSO session response"""
    session_id: str
    user_id: str
    organization_id: str
    provider: str
    expires_at: datetime
    last_activity: datetime


# SSO Configuration Management

@router.post("/config", response_model=SSOConfigResponse, status_code=status.HTTP_201_CREATED)
@requires_permission(Permission.CONFIG_UPDATE)
async def create_sso_config(
    request: SSOConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(lambda: "admin")  # Replace with real auth
):
    """
    Create SSO configuration for organization.

    Requires CONFIG_UPDATE permission.
    """
    await enforce_feature("sso_saml", request.organization_id, db)

    from backend.shared.sso_models import SSOConfigModel
    from uuid import uuid4

    sso_service = get_sso_service()

    # Check if config already exists
    existing = await sso_service.get_sso_config(request.organization_id, db)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"SSO config already exists for organization: {request.organization_id}"
        )

    # Encrypt the client secret before storing
    encrypted_client_secret = None
    if request.oauth_client_secret:
        from backend.shared.credential_manager import get_credential_manager
        cred_manager = get_credential_manager()
        encrypted_client_secret = cred_manager.encrypt(
            {"oauth_client_secret": request.oauth_client_secret}
        )

    # Create config
    config_model = SSOConfigModel(
        config_id=uuid4(),
        organization_id=request.organization_id,
        provider=request.provider,
        enabled=request.enabled,
        saml_entity_id=request.saml_entity_id,
        saml_sso_url=request.saml_sso_url,
        saml_slo_url=request.saml_slo_url,
        saml_x509_cert=request.saml_x509_cert,
        oauth_client_id=request.oauth_client_id,
        oauth_client_secret=encrypted_client_secret,
        oauth_authorization_url=request.oauth_authorization_url,
        oauth_token_url=request.oauth_token_url,
        oauth_userinfo_url=request.oauth_userinfo_url,
        oauth_scopes=request.oauth_scopes,
        attribute_mapping=request.attribute_mapping,
        jit_provisioning_enabled=request.jit_provisioning_enabled,
        default_role=request.default_role,
        session_timeout_minutes=request.session_timeout_minutes,
        created_by=current_user
    )

    db.add(config_model)
    await db.commit()
    await db.refresh(config_model)

    # Audit log
    audit_logger = get_audit_logger()
    await audit_logger.log_config_event(
        event_type=AuditEventType.CONFIG_UPDATED,
        action="create",
        description=f"SSO config created for {request.organization_id} with {request.provider}",
        db=db
    )

    return SSOConfigResponse(
        config_id=str(config_model.config_id),
        organization_id=config_model.organization_id,
        provider=config_model.provider,
        enabled=config_model.enabled,
        saml_entity_id=config_model.saml_entity_id,
        saml_sso_url=config_model.saml_sso_url,
        saml_slo_url=config_model.saml_slo_url,
        oauth_client_id=config_model.oauth_client_id,
        oauth_authorization_url=config_model.oauth_authorization_url,
        oauth_scopes=config_model.oauth_scopes,
        attribute_mapping=config_model.attribute_mapping,
        jit_provisioning_enabled=config_model.jit_provisioning_enabled,
        default_role=config_model.default_role,
        session_timeout_minutes=config_model.session_timeout_minutes,
        created_at=config_model.created_at,
        updated_at=config_model.updated_at
    )


@router.get("/config/{organization_id}", response_model=SSOConfigResponse)
async def get_sso_config(
    organization_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get SSO configuration for organization"""
    sso_service = get_sso_service()
    config = await sso_service.get_sso_config(organization_id, db)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSO config not found for organization: {organization_id}"
        )

    return SSOConfigResponse(
        config_id=str(config.config_id),
        organization_id=config.organization_id,
        provider=config.provider.value,
        enabled=config.enabled,
        saml_entity_id=config.saml_entity_id,
        saml_sso_url=config.saml_sso_url,
        saml_slo_url=config.saml_slo_url,
        oauth_client_id=config.oauth_client_id,
        oauth_authorization_url=config.oauth_authorization_url,
        oauth_scopes=config.oauth_scopes,
        attribute_mapping=config.attribute_mapping,
        jit_provisioning_enabled=config.jit_provisioning_enabled,
        default_role=config.default_role,
        session_timeout_minutes=config.session_timeout_minutes,
        created_at=datetime.utcnow(),  # Placeholder
        updated_at=datetime.utcnow()
    )


# SSO Login Flow

@router.post("/login/initiate", response_model=LoginInitiateResponse)
async def initiate_sso_login(
    request: LoginInitiateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate SSO login flow.

    Returns redirect URL to IdP for authentication.
    """
    sso_service = get_sso_service()

    try:
        login_request = SSOLoginRequest(
            organization_id=request.organization_id,
            return_url=request.return_url,
            relay_state=request.relay_state
        )

        response = await sso_service.initiate_sso_login(login_request, db)

        # Audit log
        audit_logger = get_audit_logger()
        await audit_logger.log_auth_event(
            event_type=AuditEventType.AUTH_LOGIN,
            description=f"SSO login initiated for {request.organization_id}",
            success=True,
            db=db
        )

        return LoginInitiateResponse(
            redirect_url=response.redirect_url,
            method=response.method,
            form_data=response.form_data
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/callback/saml", response_model=LoginCallbackResponse)
async def handle_saml_callback(
    request: SAMLCallbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle SAML callback from IdP.

    Validates SAML response and creates session.
    """
    sso_service = get_sso_service()

    try:
        callback_data = SSOCallbackData(
            organization_id=request.organization_id,
            provider=AuthProvider.SAML,
            saml_response=request.saml_response,
            relay_state=request.relay_state
        )

        user_id, session = await sso_service.handle_sso_callback(callback_data, db)

        return LoginCallbackResponse(
            session_id=session.session_id,
            user_id=user_id,
            organization_id=session.organization_id,
            provider=session.provider.value,
            expires_at=session.expires_at
        )

    except ValueError as e:
        # Log failed authentication
        audit_logger = get_audit_logger()
        await audit_logger.log_auth_event(
            event_type=AuditEventType.AUTH_FAILED,
            description=f"SAML callback failed: {str(e)}",
            success=False,
            db=db
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"SAML authentication failed: {str(e)}"
        )


@router.post("/callback/oauth", response_model=LoginCallbackResponse)
async def handle_oauth_callback(
    request: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle OAuth/OIDC callback from provider.

    Exchanges code for tokens and creates session.
    """
    sso_service = get_sso_service()

    # Determine provider from organization config
    config = await sso_service.get_sso_config(request.organization_id, db)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSO not configured for organization: {request.organization_id}"
        )

    try:
        callback_data = SSOCallbackData(
            organization_id=request.organization_id,
            provider=config.provider,
            code=request.code,
            state=request.state
        )

        user_id, session = await sso_service.handle_sso_callback(callback_data, db)

        return LoginCallbackResponse(
            session_id=session.session_id,
            user_id=user_id,
            organization_id=session.organization_id,
            provider=session.provider.value,
            expires_at=session.expires_at
        )

    except ValueError as e:
        # Log failed authentication
        audit_logger = get_audit_logger()
        await audit_logger.log_auth_event(
            event_type=AuditEventType.AUTH_FAILED,
            description=f"OAuth callback failed: {str(e)}",
            success=False,
            db=db
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OAuth authentication failed: {str(e)}"
        )


# Session Management

@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get SSO session details"""
    sso_service = get_sso_service()
    session = await sso_service.validate_session(session_id, db)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found or expired: {session_id}"
        )

    return SessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        organization_id=session.organization_id,
        provider=session.provider.value,
        expires_at=session.expires_at,
        last_activity=datetime.utcnow()
    )


@router.post("/logout")
async def logout(
    session_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout user and destroy SSO session.

    Returns SLO URL for SAML if applicable.
    """
    sso_service = get_sso_service()
    slo_url = await sso_service.logout(session_id, db)

    if slo_url:
        # SAML Single Logout - redirect to IdP
        return {"slo_url": slo_url, "message": "Redirect to IdP for logout"}
    else:
        # OAuth logout - session destroyed
        return {"message": "Logged out successfully"}


# Provider Information

@router.get("/providers")
async def list_providers():
    """List supported SSO providers"""
    return {
        "providers": [
            {
                "id": "saml",
                "name": "SAML 2.0",
                "type": "saml",
                "description": "Generic SAML 2.0 identity provider"
            },
            {
                "id": "oauth_azure_ad",
                "name": "Microsoft Azure AD",
                "type": "oauth",
                "description": "Azure Active Directory with OAuth 2.0/OIDC"
            },
            {
                "id": "oauth_okta",
                "name": "Okta",
                "type": "oauth",
                "description": "Okta with OAuth 2.0/OIDC"
            },
            {
                "id": "oauth_auth0",
                "name": "Auth0",
                "type": "oauth",
                "description": "Auth0 with OAuth 2.0/OIDC"
            },
            {
                "id": "oauth_google",
                "name": "Google",
                "type": "oauth",
                "description": "Google Workspace with OAuth 2.0/OIDC"
            }
        ]
    }


@router.get("/metadata/sp")
async def get_sp_metadata(organization_id: str):
    """
    Get Service Provider (SP) metadata for SAML configuration.

    Use this to configure your IdP.
    """
    # In production, generate actual SAML SP metadata XML
    sp_metadata = {
        "entity_id": f"https://platform.example.com/saml/{organization_id}",
        "acs_url": f"https://platform.example.com/api/v1/sso/callback/saml",
        "slo_url": f"https://platform.example.com/api/v1/sso/logout",
        "x509_cert": "SP certificate would go here",
        "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    }

    return sp_metadata
