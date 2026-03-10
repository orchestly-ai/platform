"""
OAuth Handler

Manages the OAuth2 authorization flow including:
- Generating authorization URLs
- Handling callbacks and token exchange
- Token refresh
- Revocation
"""

import os
import secrets
import urllib.parse
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List

try:
    import aiohttp
except ImportError:
    aiohttp = None

from .providers import OAuthProviderConfig, get_oauth_provider_registry
from .tokens import OAuthToken, get_token_storage
from .org_config import get_org_oauth_config_storage

# Singleton instance
_oauth_handler: Optional["OAuthHandler"] = None


@dataclass
class OAuthState:
    """OAuth state for CSRF protection."""

    state: str
    organization_id: str
    provider: str
    redirect_uri: str
    scopes: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=10))

    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at


class OAuthHandler:
    """
    Handles OAuth2 authorization flow.

    Usage:
        handler = get_oauth_handler()

        # Step 1: Generate authorization URL
        auth_url = await handler.get_authorization_url(
            provider="google",
            organization_id="org-123",
            redirect_uri="http://localhost:3000/oauth/callback"
        )

        # Step 2: User authorizes, callback received
        tokens = await handler.handle_callback(
            provider="google",
            code="auth-code-from-callback",
            state="state-from-callback"
        )

        # Step 3: Use tokens (auto-refreshed)
        access_token = await handler.get_access_token("google", "org-123")
    """

    def __init__(self):
        self._provider_registry = get_oauth_provider_registry()
        self._token_storage = get_token_storage()
        self._org_config_storage = get_org_oauth_config_storage()

        # In-memory state storage (use Redis in production)
        self._states: Dict[str, OAuthState] = {}

    def _generate_state(self) -> str:
        """Generate a random state token."""
        return secrets.token_urlsafe(32)

    async def _get_effective_credentials(
        self,
        provider: str,
        organization_id: str
    ) -> tuple[str, str, List[str], OAuthProviderConfig]:
        """
        Get effective OAuth credentials for an organization.

        Checks organization config first, falls back to platform defaults.

        Returns:
            Tuple of (client_id, client_secret, scopes, provider_config)
        """
        # Get base provider config (for endpoints, etc.)
        config = self._provider_registry.get(provider)
        if not config:
            raise ValueError(f"Unknown OAuth provider: {provider}")

        # Check for organization-specific config
        org_config = await self._org_config_storage.get(organization_id, provider)

        if org_config and org_config.enabled:
            # Use organization's custom credentials
            client_id = org_config.client_id
            client_secret = org_config.client_secret
            scopes = org_config.custom_scopes or config.default_scopes
        else:
            # Use platform defaults
            if not config.is_configured():
                raise ValueError(
                    f"OAuth provider {provider} is not configured. "
                    f"Either set {provider.upper()}_CLIENT_ID and {provider.upper()}_CLIENT_SECRET "
                    f"environment variables, or configure custom OAuth in Settings."
                )
            client_id = config.client_id
            client_secret = config.client_secret
            scopes = config.default_scopes

        return client_id, client_secret, scopes, config

    async def get_authorization_url(
        self,
        provider: str,
        organization_id: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None,
        extra_params: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate OAuth authorization URL.

        Args:
            provider: Provider ID (google, slack, github)
            organization_id: Organization requesting access
            redirect_uri: Callback URL after authorization
            scopes: Optional custom scopes (uses defaults if not provided)
            extra_params: Optional extra query parameters

        Returns:
            Authorization URL to redirect user to
        """
        # Get effective credentials (org config or platform default)
        client_id, client_secret, default_scopes, config = await self._get_effective_credentials(
            provider, organization_id
        )

        # Use provided scopes or defaults
        scopes = scopes or default_scopes

        # Generate state token
        state = self._generate_state()
        oauth_state = OAuthState(
            state=state,
            organization_id=organization_id,
            provider=provider,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )
        self._states[state] = oauth_state

        # Build authorization URL
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
        }

        # Add provider-specific extra params
        params.update(config.extra_params)

        # Add caller-provided extra params
        if extra_params:
            params.update(extra_params)

        return f"{config.authorization_url}?{urllib.parse.urlencode(params)}"

    async def handle_callback(
        self,
        provider: str,
        code: str,
        state: str
    ) -> OAuthToken:
        """
        Handle OAuth callback and exchange code for tokens.

        Args:
            provider: Provider ID
            code: Authorization code from callback
            state: State token from callback

        Returns:
            OAuthToken with access and refresh tokens
        """
        # Validate state
        oauth_state = self._states.get(state)
        if not oauth_state:
            raise ValueError("Invalid or expired state token")

        if oauth_state.is_expired():
            del self._states[state]
            raise ValueError("State token expired")

        if oauth_state.provider != provider:
            raise ValueError("Provider mismatch")

        # Clean up state
        del self._states[state]

        # Get effective credentials (org config or platform default)
        client_id, client_secret, _, config = await self._get_effective_credentials(
            provider, oauth_state.organization_id
        )

        # Exchange code for tokens
        token_data = await self._exchange_code(
            config, code, oauth_state.redirect_uri, client_id, client_secret
        )

        # Create token object
        token = OAuthToken(
            organization_id=oauth_state.organization_id,
            provider=provider,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=self._calculate_expiry(token_data.get("expires_in")),
            scopes=oauth_state.scopes,
        )

        # Fetch user info if available
        if config.userinfo_url:
            try:
                user_info = await self._fetch_user_info(config, token.access_token)
                token.user_info = user_info
            except Exception as e:
                print(f"Error fetching user info: {e}")

        # Store token
        await self._token_storage.store(token)

        return token

    async def _exchange_code(
        self,
        config: OAuthProviderConfig,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        if not aiohttp:
            raise RuntimeError("aiohttp is required for OAuth. Install with: pip install aiohttp")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        headers = {"Accept": "application/json"}
        headers.update(config.extra_headers)

        async with aiohttp.ClientSession() as session:
            async with session.post(config.token_url, data=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Token exchange failed: {error_text}")

                return await response.json()

    async def _fetch_user_info(
        self,
        config: OAuthProviderConfig,
        access_token: str
    ) -> Dict[str, Any]:
        """Fetch user info from provider."""
        if not aiohttp:
            return {}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        headers.update(config.extra_headers)

        async with aiohttp.ClientSession() as session:
            async with session.get(config.userinfo_url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return {}

    def _calculate_expiry(self, expires_in: Optional[int]) -> Optional[datetime]:
        """Calculate token expiry datetime."""
        if not expires_in:
            return None
        return datetime.utcnow() + timedelta(seconds=expires_in)

    async def get_access_token(
        self,
        provider: str,
        organization_id: str,
        auto_refresh: bool = True
    ) -> Optional[str]:
        """
        Get access token, refreshing if needed.

        Args:
            provider: Provider ID
            organization_id: Organization ID
            auto_refresh: Whether to auto-refresh expired tokens

        Returns:
            Access token string or None if not found
        """
        token = await self._token_storage.get(organization_id, provider)
        if not token:
            return None

        config = self._provider_registry.get(provider)
        if not config:
            return token.access_token

        # Check if refresh needed
        if auto_refresh and token.is_expired(config.token_expiry_buffer_seconds):
            if token.refresh_token:
                try:
                    await self.refresh_token(provider, organization_id)
                    token = await self._token_storage.get(organization_id, provider)
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    # Return existing token, may still work

        return token.access_token if token else None

    async def refresh_token(self, provider: str, organization_id: str) -> OAuthToken:
        """
        Refresh an expired access token.

        Args:
            provider: Provider ID
            organization_id: Organization ID

        Returns:
            Updated OAuthToken
        """
        token = await self._token_storage.get(organization_id, provider)
        if not token:
            raise ValueError("No token found to refresh")

        if not token.refresh_token:
            raise ValueError("No refresh token available")

        # Get effective credentials (org config or platform default)
        client_id, client_secret, _, config = await self._get_effective_credentials(
            provider, organization_id
        )

        if not aiohttp:
            raise RuntimeError("aiohttp is required for OAuth")

        # Request new access token
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        headers = {"Accept": "application/json"}
        headers.update(config.extra_headers)

        async with aiohttp.ClientSession() as session:
            async with session.post(config.token_url, data=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Token refresh failed: {error_text}")

                token_data = await response.json()

        # Update token
        token.access_token = token_data["access_token"]
        token.expires_at = self._calculate_expiry(token_data.get("expires_in"))

        # Some providers rotate refresh tokens
        if "refresh_token" in token_data:
            token.refresh_token = token_data["refresh_token"]

        await self._token_storage.store(token)
        return token

    async def revoke_token(self, provider: str, organization_id: str) -> bool:
        """
        Revoke OAuth tokens and remove from storage.

        Args:
            provider: Provider ID
            organization_id: Organization ID

        Returns:
            True if revoked successfully
        """
        token = await self._token_storage.get(organization_id, provider)
        if not token:
            return False

        config = self._provider_registry.get(provider)
        if not config or not config.revoke_url:
            # No revoke endpoint, just delete locally
            await self._token_storage.delete(organization_id, provider)
            return True

        if not aiohttp:
            await self._token_storage.delete(organization_id, provider)
            return True

        # Try to revoke at provider
        try:
            data = {"token": token.access_token}
            async with aiohttp.ClientSession() as session:
                async with session.post(config.revoke_url, data=data) as response:
                    # Most providers return 200 on success
                    pass
        except Exception as e:
            print(f"Error revoking token at provider: {e}")

        # Delete locally regardless
        await self._token_storage.delete(organization_id, provider)
        return True

    async def get_connection_status(
        self,
        provider: str,
        organization_id: str
    ) -> Dict[str, Any]:
        """
        Get OAuth connection status for a provider.

        Returns:
            Dict with connected status, user info, etc.
        """
        token = await self._token_storage.get(organization_id, provider)

        if not token:
            return {
                "connected": False,
                "provider": provider,
            }

        return {
            "connected": True,
            "provider": provider,
            "user_info": token.user_info,
            "scopes": token.scopes,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            "created_at": token.created_at.isoformat(),
        }


def get_oauth_handler() -> OAuthHandler:
    """Get singleton OAuth handler."""
    global _oauth_handler
    if _oauth_handler is None:
        _oauth_handler = OAuthHandler()
    return _oauth_handler
