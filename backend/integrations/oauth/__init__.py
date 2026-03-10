"""
OAuth2 Integration Module

Provides OAuth2 authentication flow for external services like
Google, Slack, GitHub, etc.

Usage:
    from backend.integrations.oauth import OAuthHandler, get_oauth_handler

    handler = get_oauth_handler()

    # Start OAuth flow
    auth_url = await handler.get_authorization_url("google", org_id, redirect_uri)

    # Handle callback
    tokens = await handler.handle_callback("google", code, state)

    # Get fresh token (auto-refreshes if needed)
    access_token = await handler.get_access_token("google", org_id)
"""

from .providers import (
    OAuthProviderConfig,
    OAuthProviderRegistry,
    get_oauth_provider_registry,
)
from .tokens import (
    OAuthToken,
    OAuthTokenStorage,
    get_token_storage,
)
from .handler import (
    OAuthHandler,
    OAuthState,
    get_oauth_handler,
)
from .org_config import (
    OrganizationOAuthConfig,
    OrganizationOAuthConfigStorage,
    get_org_oauth_config_storage,
)

__all__ = [
    # Provider configs
    "OAuthProviderConfig",
    "OAuthProviderRegistry",
    "get_oauth_provider_registry",
    # Organization OAuth configs
    "OrganizationOAuthConfig",
    "OrganizationOAuthConfigStorage",
    "get_org_oauth_config_storage",
    # Token storage
    "OAuthToken",
    "OAuthTokenStorage",
    "get_token_storage",
    # Handler
    "OAuthHandler",
    "OAuthState",
    "get_oauth_handler",
]
