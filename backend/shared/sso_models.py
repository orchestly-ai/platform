"""
SSO/SAML Authentication Models

Enterprise authentication with support for SAML 2.0, OAuth 2.0, and OpenID Connect.
90% customer requirement, sales blocker for enterprise deals.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Text,
    ForeignKey, Index, Integer
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from backend.database.session import Base


class AuthProvider(Enum):
    """Supported authentication providers"""
    # SAML 2.0
    SAML = "saml"

    # OAuth 2.0 / OpenID Connect
    OAUTH_AZURE_AD = "oauth_azure_ad"
    OAUTH_OKTA = "oauth_okta"
    OAUTH_AUTH0 = "oauth_auth0"
    OAUTH_GOOGLE = "oauth_google"
    OAUTH_GENERIC = "oauth_generic"

    # Local (username/password)
    LOCAL = "local"


class SAMLBinding(Enum):
    """SAML protocol bindings"""
    HTTP_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
    HTTP_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"


class SSOConfigModel(Base):
    """
    SSO configuration per organization.

    Supports SAML 2.0, OAuth 2.0, and OpenID Connect.
    """
    __tablename__ = "sso_configs"

    # Primary key
    config_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Organization
    organization_id = Column(String(255), nullable=False, unique=True, index=True)

    # Provider
    provider = Column(String(50), nullable=False)  # saml, oauth_azure_ad, etc.
    enabled = Column(Boolean, nullable=False, default=True)

    # SAML Configuration
    saml_entity_id = Column(String(512), nullable=True)  # IdP entity ID
    saml_sso_url = Column(String(512), nullable=True)   # IdP SSO URL
    saml_slo_url = Column(String(512), nullable=True)   # IdP SLO URL (logout)
    saml_x509_cert = Column(Text, nullable=True)        # IdP X.509 certificate
    saml_binding = Column(String(100), nullable=True)   # HTTP-POST or HTTP-Redirect

    # OAuth 2.0 / OIDC Configuration
    oauth_client_id = Column(String(255), nullable=True)
    oauth_client_secret = Column(String(512), nullable=True)  # Encrypted
    oauth_authorization_url = Column(String(512), nullable=True)
    oauth_token_url = Column(String(512), nullable=True)
    oauth_userinfo_url = Column(String(512), nullable=True)
    oauth_jwks_url = Column(String(512), nullable=True)
    oauth_scopes = Column(JSON, nullable=True)  # ["openid", "email", "profile"]

    # Attribute Mapping (map IdP attributes to our user model)
    attribute_mapping = Column(JSON, nullable=False, default=dict)
    # Example: {
    #   "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    #   "first_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
    #   "last_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
    # }

    # JIT (Just-In-Time) User Provisioning
    jit_provisioning_enabled = Column(Boolean, nullable=False, default=True)
    default_role = Column(String(100), nullable=True)  # Role assigned to new users

    # Session Settings
    session_timeout_minutes = Column(Integer, nullable=False, default=480)  # 8 hours
    require_mfa = Column(Boolean, nullable=False, default=False)

    # Security
    require_signed_assertions = Column(Boolean, nullable=False, default=True)
    require_encrypted_assertions = Column(Boolean, nullable=False, default=False)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)

    # Foreign keys
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')

    # Indexes
    __table_args__ = (
        Index('idx_sso_org', 'organization_id'),
        Index('idx_sso_enabled', 'enabled'),
    )

    def __repr__(self):
        return f"<SSOConfig(org={self.organization_id}, provider={self.provider})>"


class SSOSessionModel(Base):
    """
    SSO session tracking.

    Stores active SSO sessions for logout and session management.
    """
    __tablename__ = "sso_sessions"

    # Primary key
    session_id = Column(String(255), primary_key=True)  # SAML session ID

    # User
    user_id = Column(String(255), nullable=False, index=True)
    organization_id = Column(String(255), nullable=False, index=True)

    # Provider
    provider = Column(String(50), nullable=False)

    # Session data
    name_id = Column(String(255), nullable=True)  # SAML NameID
    session_index = Column(String(255), nullable=True)  # SAML SessionIndex

    # Tokens (for OAuth/OIDC)
    access_token = Column(Text, nullable=True)  # Encrypted
    refresh_token = Column(Text, nullable=True)  # Encrypted
    id_token = Column(Text, nullable=True)      # JWT

    # Expiration
    expires_at = Column(DateTime, nullable=False)

    # Metadata
    extra_metadata = Column(JSON, nullable=True)  # IP, user agent, etc.

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_activity = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Foreign keys
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE')
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE')

    # Indexes
    __table_args__ = (
        Index('idx_sso_session_user', 'user_id'),
        Index('idx_sso_session_org', 'organization_id'),
        Index('idx_sso_session_expires', 'expires_at'),
    )

    def __repr__(self):
        return f"<SSOSession(id={self.session_id}, user={self.user_id})>"


class SAMLRequestModel(Base):
    """
    Pending SAML authentication requests.

    Stores state for SAML AuthnRequest validation.
    """
    __tablename__ = "saml_requests"

    # Primary key
    request_id = Column(String(255), primary_key=True)

    # Organization
    organization_id = Column(String(255), nullable=False, index=True)

    # Request data
    relay_state = Column(String(255), nullable=True)
    return_url = Column(String(512), nullable=False)

    # Expiration (requests expire after 5 minutes)
    expires_at = Column(DateTime, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_saml_request_org', 'organization_id'),
        Index('idx_saml_request_expires', 'expires_at'),
    )

    def __repr__(self):
        return f"<SAMLRequest(id={self.request_id})>"


# Dataclasses for application logic

@dataclass
class SSOConfig:
    """SSO configuration data structure"""
    config_id: UUID
    organization_id: str
    provider: AuthProvider
    enabled: bool

    # SAML
    saml_entity_id: Optional[str] = None
    saml_sso_url: Optional[str] = None
    saml_slo_url: Optional[str] = None
    saml_x509_cert: Optional[str] = None
    saml_binding: Optional[SAMLBinding] = None

    # OAuth/OIDC
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_authorization_url: Optional[str] = None
    oauth_token_url: Optional[str] = None
    oauth_userinfo_url: Optional[str] = None
    oauth_scopes: Optional[List[str]] = None

    # Settings
    attribute_mapping: Dict[str, str] = field(default_factory=dict)
    jit_provisioning_enabled: bool = True
    default_role: Optional[str] = None
    session_timeout_minutes: int = 480


@dataclass
class SAMLAssertion:
    """Parsed SAML assertion"""
    name_id: str
    session_index: Optional[str]
    attributes: Dict[str, Any]
    issuer: str
    audience: str
    not_before: datetime
    not_on_or_after: datetime
    authn_instant: datetime


@dataclass
class OAuthUserInfo:
    """OAuth/OIDC user info"""
    sub: str  # Subject (user ID)
    email: str
    email_verified: bool = False
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SSOSession:
    """Active SSO session"""
    session_id: str
    user_id: str
    organization_id: str
    provider: AuthProvider
    expires_at: datetime

    # SAML
    name_id: Optional[str] = None
    session_index: Optional[str] = None

    # OAuth/OIDC
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None


@dataclass
class SSOLoginRequest:
    """SSO login request"""
    organization_id: str
    return_url: str
    relay_state: Optional[str] = None


@dataclass
class SSOLoginResponse:
    """SSO login response"""
    redirect_url: str
    method: str = "GET"  # GET or POST
    form_data: Optional[Dict[str, str]] = None  # For POST binding


@dataclass
class SSOCallbackData:
    """Data from SSO callback"""
    organization_id: str
    provider: AuthProvider

    # SAML
    saml_response: Optional[str] = None
    relay_state: Optional[str] = None

    # OAuth
    code: Optional[str] = None
    state: Optional[str] = None


@dataclass
class SSOUserData:
    """User data extracted from SSO"""
    external_id: str  # User ID from IdP
    email: str
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


# Provider-specific configurations

SAML_ATTRIBUTE_MAPPINGS = {
    "azure_ad": {
        "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        "first_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
        "last_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",
        "display_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
    },
    "okta": {
        "email": "email",
        "first_name": "firstName",
        "last_name": "lastName",
        "display_name": "displayName"
    },
    "auth0": {
        "email": "email",
        "first_name": "given_name",
        "last_name": "family_name",
        "display_name": "name"
    },
    "generic": {
        "email": "email",
        "first_name": "givenName",
        "last_name": "surname",
        "display_name": "displayName"
    }
}

OAUTH_PROVIDER_CONFIGS = {
    "azure_ad": {
        "authorization_endpoint": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token_endpoint": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "userinfo_endpoint": "https://graph.microsoft.com/v1.0/me",
        "scopes": ["openid", "email", "profile"]
    },
    "okta": {
        "authorization_endpoint": "https://{domain}/oauth2/v1/authorize",
        "token_endpoint": "https://{domain}/oauth2/v1/token",
        "userinfo_endpoint": "https://{domain}/oauth2/v1/userinfo",
        "scopes": ["openid", "email", "profile"]
    },
    "auth0": {
        "authorization_endpoint": "https://{domain}/authorize",
        "token_endpoint": "https://{domain}/oauth/token",
        "userinfo_endpoint": "https://{domain}/userinfo",
        "scopes": ["openid", "email", "profile"]
    },
    "google": {
        "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.googleapis.com/token",
        "userinfo_endpoint": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": ["openid", "email", "profile"]
    }
}
