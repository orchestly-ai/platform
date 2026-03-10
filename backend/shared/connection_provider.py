"""
Connection Provider - Hybrid Authentication Layer

Provides a scalable abstraction for customer integration connections.
Supports multiple backends:
- Nango: For OAuth-based integrations (Discord, Slack, Google, etc.)
- Direct: For API key-based integrations (OpenAI, Stripe, etc.)
- Custom: For enterprise SSO/SAML integrations

This abstraction allows swapping providers without changing application code.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class AuthType(str, Enum):
    """Authentication types supported by the connection provider."""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC = "basic"
    BEARER = "bearer"
    CUSTOM = "custom"


@dataclass
class Credentials:
    """Unified credentials structure returned by all providers."""
    auth_type: AuthType
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    api_key: Optional[str] = None
    expires_at: Optional[datetime] = None
    scopes: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    provider_id: Optional[str] = None  # e.g., "nango", "direct"

    @property
    def is_expired(self) -> bool:
        """Check if credentials are expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def needs_refresh(self) -> bool:
        """Check if credentials should be refreshed (within 5 min of expiry)."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > (self.expires_at - timedelta(minutes=5))

    def to_auth_header(self) -> Dict[str, str]:
        """Convert credentials to HTTP authorization header."""
        if self.auth_type == AuthType.OAUTH2 or self.auth_type == AuthType.BEARER:
            return {"Authorization": f"Bearer {self.access_token}"}
        elif self.auth_type == AuthType.API_KEY:
            # Different APIs use different header names
            return {"Authorization": f"Bearer {self.api_key}"}
        elif self.auth_type == AuthType.BASIC:
            import base64
            encoded = base64.b64encode(f"{self.raw_data.get('username', '')}:{self.raw_data.get('password', '')}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        return {}


@dataclass
class ConnectionStatus:
    """Status of a user's connection to an integration."""
    connected: bool
    integration_id: str
    user_id: str
    provider: str  # Which provider manages this connection
    last_used: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectionProvider(ABC):
    """
    Abstract base class for connection providers.

    Each provider implementation handles a specific authentication method
    or external service (Nango, custom OAuth, direct API keys, etc.)
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider."""
        pass

    @abstractmethod
    async def initiate_connection(
        self,
        integration_id: str,
        user_id: str,
        redirect_url: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Initiate a new connection (e.g., start OAuth flow).

        Returns:
            Authorization URL to redirect user to, or empty string for direct auth
        """
        pass

    @abstractmethod
    async def complete_connection(
        self,
        integration_id: str,
        user_id: str,
        auth_data: Dict[str, Any]
    ) -> Credentials:
        """
        Complete a connection after user authorization.

        Args:
            auth_data: Could be OAuth callback params, API key, etc.

        Returns:
            Credentials object with access tokens/keys
        """
        pass

    @abstractmethod
    async def get_credentials(
        self,
        integration_id: str,
        user_id: str
    ) -> Optional[Credentials]:
        """
        Get credentials for an existing connection.

        Returns:
            Credentials if connection exists, None otherwise
        """
        pass

    @abstractmethod
    async def refresh_credentials(
        self,
        integration_id: str,
        user_id: str
    ) -> Optional[Credentials]:
        """
        Refresh expired credentials.

        Returns:
            New credentials if refresh successful, None otherwise
        """
        pass

    @abstractmethod
    async def revoke_connection(
        self,
        integration_id: str,
        user_id: str
    ) -> bool:
        """
        Revoke a connection and delete stored credentials.

        Returns:
            True if revocation successful
        """
        pass

    @abstractmethod
    async def get_connection_status(
        self,
        integration_id: str,
        user_id: str
    ) -> ConnectionStatus:
        """
        Get the status of a connection.
        """
        pass

    @abstractmethod
    def supports_integration(self, integration_id: str) -> bool:
        """Check if this provider supports the given integration."""
        pass


class NangoProvider(ConnectionProvider):
    """
    Nango-based connection provider for OAuth integrations.

    Nango handles:
    - OAuth flow initiation and callback
    - Token storage and encryption
    - Automatic token refresh
    - 100+ pre-built integrations

    See: https://docs.nango.dev/
    """

    # Integrations supported via Nango OAuth
    SUPPORTED_INTEGRATIONS = {
        "discord", "slack", "google", "github", "notion",
        "salesforce", "hubspot", "jira", "asana", "trello",
        "dropbox", "box", "microsoft", "zoom", "calendly",
        "stripe", "quickbooks", "xero", "shopify", "zendesk"
    }

    def __init__(
        self,
        secret_key: Optional[str] = None,
        public_key: Optional[str] = None,
        base_url: str = "https://api.nango.dev"
    ):
        self.secret_key = secret_key or os.environ.get("NANGO_SECRET_KEY")
        self.public_key = public_key or os.environ.get("NANGO_PUBLIC_KEY")
        self.base_url = base_url

        if not self.secret_key:
            logger.warning(
                "Nango secret key not configured. "
                "Set NANGO_SECRET_KEY environment variable for OAuth integrations."
            )

    @property
    def provider_id(self) -> str:
        return "nango"

    def supports_integration(self, integration_id: str) -> bool:
        return integration_id.lower() in self.SUPPORTED_INTEGRATIONS

    async def initiate_connection(
        self,
        integration_id: str,
        user_id: str,
        redirect_url: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate Nango OAuth authorization URL."""
        if not self.public_key:
            raise ValueError("Nango public key not configured")

        # Nango uses the frontend SDK to initiate OAuth
        # Return the configuration for the frontend
        params = {
            "integration": integration_id,
            "user_id": user_id,
            "public_key": self.public_key,
        }
        if redirect_url:
            params["redirect_url"] = redirect_url
        if scopes:
            params["scopes"] = ",".join(scopes)

        # The frontend will use nango.auth() with these params
        # For server-side initiation, we'd call Nango's API
        logger.info(f"Initiating Nango OAuth for {integration_id}, user {user_id}")

        # Return auth URL (frontend typically handles this via Nango SDK)
        return f"nango://auth?integration={integration_id}&user={user_id}"

    async def complete_connection(
        self,
        integration_id: str,
        user_id: str,
        auth_data: Dict[str, Any]
    ) -> Credentials:
        """Nango handles this automatically via callback."""
        # After Nango OAuth completes, credentials are stored in Nango
        # We just fetch them
        creds = await self.get_credentials(integration_id, user_id)
        if not creds:
            raise ValueError("Failed to get credentials after OAuth completion")
        return creds

    async def get_credentials(
        self,
        integration_id: str,
        user_id: str
    ) -> Optional[Credentials]:
        """Fetch credentials from Nango."""
        if not self.secret_key:
            logger.warning("Nango not configured, returning None")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/connection/{user_id}",
                    headers={"Authorization": f"Bearer {self.secret_key}"},
                    params={"provider_config_key": integration_id}
                ) as response:
                    if response.status == 404:
                        return None
                    response.raise_for_status()
                    data = await response.json()

                    return Credentials(
                        auth_type=AuthType.OAUTH2,
                        access_token=data.get("credentials", {}).get("access_token"),
                        refresh_token=data.get("credentials", {}).get("refresh_token"),
                        expires_at=datetime.fromisoformat(data["credentials"]["expires_at"]) if data.get("credentials", {}).get("expires_at") else None,
                        scopes=data.get("credentials", {}).get("scopes", []),
                        raw_data=data,
                        provider_id=self.provider_id
                    )
        except Exception as e:
            logger.error(f"Failed to get Nango credentials: {e}")
            return None

    async def refresh_credentials(
        self,
        integration_id: str,
        user_id: str
    ) -> Optional[Credentials]:
        """Nango handles refresh automatically, just fetch fresh credentials."""
        return await self.get_credentials(integration_id, user_id)

    async def revoke_connection(
        self,
        integration_id: str,
        user_id: str
    ) -> bool:
        """Revoke connection in Nango."""
        if not self.secret_key:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.base_url}/connection/{user_id}",
                    headers={"Authorization": f"Bearer {self.secret_key}"},
                    params={"provider_config_key": integration_id}
                ) as response:
                    return response.status in (200, 204, 404)
        except Exception as e:
            logger.error(f"Failed to revoke Nango connection: {e}")
            return False

    async def get_connection_status(
        self,
        integration_id: str,
        user_id: str
    ) -> ConnectionStatus:
        """Get Nango connection status."""
        creds = await self.get_credentials(integration_id, user_id)
        return ConnectionStatus(
            connected=creds is not None,
            integration_id=integration_id,
            user_id=user_id,
            provider=self.provider_id,
            error=None if creds else "Not connected"
        )


class DirectAPIKeyProvider(ConnectionProvider):
    """
    Direct API key provider for simple key-based integrations.

    Handles integrations that just need an API key:
    - OpenAI, Anthropic, Google AI (LLM providers)
    - Stripe, Twilio (service APIs)
    - Custom webhooks

    Credentials are stored in our database, not a third-party service.
    """

    # Integrations that use simple API keys
    SUPPORTED_INTEGRATIONS = {
        "openai", "anthropic", "google-ai", "deepseek", "groq",
        "stripe", "twilio", "sendgrid", "mailgun",
        "custom_webhook", "custom_api"
    }

    def __init__(self, db_session_factory=None):
        """
        Initialize with database session factory.

        In production, pass the actual async session factory.
        """
        self.db_session_factory = db_session_factory
        self._credentials_cache: Dict[str, Credentials] = {}

    @property
    def provider_id(self) -> str:
        return "direct"

    def supports_integration(self, integration_id: str) -> bool:
        return integration_id.lower() in self.SUPPORTED_INTEGRATIONS

    async def initiate_connection(
        self,
        integration_id: str,
        user_id: str,
        redirect_url: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """API key auth doesn't need OAuth flow, return empty."""
        # No redirect needed for API key auth
        return ""

    async def complete_connection(
        self,
        integration_id: str,
        user_id: str,
        auth_data: Dict[str, Any]
    ) -> Credentials:
        """Store API key credentials."""
        api_key = auth_data.get("api_key") or auth_data.get("bot_token")
        if not api_key:
            raise ValueError("API key required for direct auth")

        credentials = Credentials(
            auth_type=AuthType.API_KEY,
            api_key=api_key,
            raw_data=auth_data,
            provider_id=self.provider_id
        )

        # Cache locally (in production, store in database)
        cache_key = f"{integration_id}:{user_id}"
        self._credentials_cache[cache_key] = credentials

        logger.info(f"Stored API key credentials for {integration_id}, user {user_id}")
        return credentials

    async def get_credentials(
        self,
        integration_id: str,
        user_id: str
    ) -> Optional[Credentials]:
        """Get stored API key credentials."""
        cache_key = f"{integration_id}:{user_id}"
        return self._credentials_cache.get(cache_key)

    async def refresh_credentials(
        self,
        integration_id: str,
        user_id: str
    ) -> Optional[Credentials]:
        """API keys don't need refresh."""
        return await self.get_credentials(integration_id, user_id)

    async def revoke_connection(
        self,
        integration_id: str,
        user_id: str
    ) -> bool:
        """Remove stored API key."""
        cache_key = f"{integration_id}:{user_id}"
        if cache_key in self._credentials_cache:
            del self._credentials_cache[cache_key]
            return True
        return False

    async def get_connection_status(
        self,
        integration_id: str,
        user_id: str
    ) -> ConnectionStatus:
        """Get API key connection status."""
        creds = await self.get_credentials(integration_id, user_id)
        return ConnectionStatus(
            connected=creds is not None,
            integration_id=integration_id,
            user_id=user_id,
            provider=self.provider_id,
            error=None if creds else "API key not configured"
        )


class DatabaseAPIKeyProvider(ConnectionProvider):
    """
    Database-backed API key provider.

    Uses the existing integration_installations table to store credentials.
    This integrates with the current system while providing the ConnectionProvider interface.
    """

    SUPPORTED_INTEGRATIONS = {
        "openai", "anthropic", "google-ai", "deepseek", "groq",
        "discord", "slack", "github",  # These can use bot tokens stored in DB
        "stripe", "twilio", "sendgrid"
    }

    def __init__(self, db_session):
        self.db = db_session

    @property
    def provider_id(self) -> str:
        return "database"

    def supports_integration(self, integration_id: str) -> bool:
        # Database provider can handle any integration with stored credentials
        return True

    async def initiate_connection(
        self,
        integration_id: str,
        user_id: str,
        redirect_url: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """No OAuth needed, credentials entered directly."""
        return ""

    async def complete_connection(
        self,
        integration_id: str,
        user_id: str,
        auth_data: Dict[str, Any]
    ) -> Credentials:
        """This is handled by the existing integration installation flow."""
        # The existing system stores credentials in integration_installations.auth_credentials
        # Just convert to Credentials format
        api_key = auth_data.get("api_key") or auth_data.get("bot_token")

        return Credentials(
            auth_type=AuthType.API_KEY if api_key else AuthType.OAUTH2,
            api_key=api_key,
            access_token=auth_data.get("access_token"),
            refresh_token=auth_data.get("refresh_token"),
            raw_data=auth_data,
            provider_id=self.provider_id
        )

    async def get_credentials(
        self,
        integration_id: str,
        user_id: str
    ) -> Optional[Credentials]:
        """
        Get credentials from integration_installations table.

        Note: user_id here maps to organization_id in the current schema.
        """
        from sqlalchemy import select, and_
        from backend.models import IntegrationInstallation as IntegrationInstallationModel
        from backend.models import Integration as IntegrationModel
        from backend.shared.credential_manager import decrypt_credentials

        try:
            query = select(IntegrationInstallationModel).join(
                IntegrationModel,
                IntegrationInstallationModel.integration_id == IntegrationModel.integration_id
            ).where(
                and_(
                    IntegrationModel.slug == integration_id,
                    IntegrationInstallationModel.status == "active"
                )
            )

            result = await self.db.execute(query)
            installation = result.scalar_one_or_none()

            if not installation:
                return None

            # Decrypt stored credentials
            auth_data = decrypt_credentials(installation.auth_credentials) if installation.auth_credentials else {}

            api_key = auth_data.get("api_key") or auth_data.get("bot_token")

            return Credentials(
                auth_type=AuthType.API_KEY if api_key else AuthType.OAUTH2,
                api_key=api_key,
                access_token=auth_data.get("access_token"),
                refresh_token=auth_data.get("refresh_token"),
                raw_data=auth_data,
                provider_id=self.provider_id
            )

        except Exception as e:
            logger.error(f"Failed to get credentials from database: {e}")
            return None

    async def refresh_credentials(
        self,
        integration_id: str,
        user_id: str
    ) -> Optional[Credentials]:
        """Database-stored credentials don't auto-refresh."""
        return await self.get_credentials(integration_id, user_id)

    async def revoke_connection(
        self,
        integration_id: str,
        user_id: str
    ) -> bool:
        """Handled by existing uninstall flow."""
        return True

    async def get_connection_status(
        self,
        integration_id: str,
        user_id: str
    ) -> ConnectionStatus:
        creds = await self.get_credentials(integration_id, user_id)
        return ConnectionStatus(
            connected=creds is not None,
            integration_id=integration_id,
            user_id=user_id,
            provider=self.provider_id,
            error=None if creds else "Not installed"
        )


class ConnectionManager:
    """
    Orchestrates multiple connection providers.

    Routes connection requests to the appropriate provider based on
    integration type. Provides a unified interface for the application.

    Usage:
        manager = ConnectionManager()

        # Get credentials (auto-selects provider)
        creds = await manager.get_credentials("discord", "user_123")

        # Initiate new connection
        auth_url = await manager.initiate_connection("slack", "user_123")
    """

    def __init__(
        self,
        providers: Optional[List[ConnectionProvider]] = None,
        db_session=None
    ):
        """
        Initialize with list of providers.

        Providers are checked in order; first one that supports the
        integration handles the request.
        """
        if providers:
            self.providers = providers
        else:
            # Default provider stack
            self.providers = [
                NangoProvider(),  # Try Nango first for OAuth
                DirectAPIKeyProvider(),  # Fallback for API keys
            ]

            # Add database provider if session available
            if db_session:
                self.providers.append(DatabaseAPIKeyProvider(db_session))

    def _get_provider(self, integration_id: str) -> Optional[ConnectionProvider]:
        """Find the provider that supports this integration."""
        for provider in self.providers:
            if provider.supports_integration(integration_id):
                return provider
        return None

    async def initiate_connection(
        self,
        integration_id: str,
        user_id: str,
        redirect_url: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Initiate connection via appropriate provider."""
        provider = self._get_provider(integration_id)
        if not provider:
            raise ValueError(f"No provider supports integration: {integration_id}")

        logger.info(f"Initiating connection for {integration_id} via {provider.provider_id}")
        return await provider.initiate_connection(
            integration_id, user_id, redirect_url, scopes, metadata
        )

    async def complete_connection(
        self,
        integration_id: str,
        user_id: str,
        auth_data: Dict[str, Any]
    ) -> Credentials:
        """Complete connection via appropriate provider."""
        provider = self._get_provider(integration_id)
        if not provider:
            raise ValueError(f"No provider supports integration: {integration_id}")

        return await provider.complete_connection(integration_id, user_id, auth_data)

    async def get_credentials(
        self,
        integration_id: str,
        user_id: str,
        auto_refresh: bool = True
    ) -> Optional[Credentials]:
        """
        Get credentials, trying each provider in order.

        If auto_refresh is True, will attempt to refresh expired credentials.
        """
        for provider in self.providers:
            if not provider.supports_integration(integration_id):
                continue

            creds = await provider.get_credentials(integration_id, user_id)
            if creds:
                # Check if refresh needed
                if auto_refresh and creds.needs_refresh and creds.refresh_token:
                    refreshed = await provider.refresh_credentials(integration_id, user_id)
                    if refreshed:
                        return refreshed
                return creds

        return None

    async def revoke_connection(
        self,
        integration_id: str,
        user_id: str
    ) -> bool:
        """Revoke connection from all providers that have it."""
        success = False
        for provider in self.providers:
            if provider.supports_integration(integration_id):
                if await provider.revoke_connection(integration_id, user_id):
                    success = True
        return success

    async def get_connection_status(
        self,
        integration_id: str,
        user_id: str
    ) -> ConnectionStatus:
        """Get connection status from first supporting provider."""
        provider = self._get_provider(integration_id)
        if not provider:
            return ConnectionStatus(
                connected=False,
                integration_id=integration_id,
                user_id=user_id,
                provider="none",
                error=f"No provider supports {integration_id}"
            )

        return await provider.get_connection_status(integration_id, user_id)

    async def list_connections(
        self,
        user_id: str,
        integration_ids: Optional[List[str]] = None
    ) -> List[ConnectionStatus]:
        """List all connections for a user."""
        if integration_ids is None:
            # Get all supported integrations
            integration_ids = set()
            for provider in self.providers:
                if hasattr(provider, "SUPPORTED_INTEGRATIONS"):
                    integration_ids.update(provider.SUPPORTED_INTEGRATIONS)

        statuses = []
        for integration_id in integration_ids:
            status = await self.get_connection_status(integration_id, user_id)
            statuses.append(status)

        return statuses


# Singleton instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager(db_session=None) -> ConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager(db_session=db_session)
    return _connection_manager


# Convenience functions
async def get_integration_credentials(
    integration_id: str,
    user_id: str,
    db_session=None
) -> Optional[Credentials]:
    """Get credentials for an integration."""
    manager = get_connection_manager(db_session)
    return await manager.get_credentials(integration_id, user_id)


async def initiate_integration_connection(
    integration_id: str,
    user_id: str,
    redirect_url: Optional[str] = None
) -> str:
    """Start OAuth flow for an integration."""
    manager = get_connection_manager()
    return await manager.initiate_connection(integration_id, user_id, redirect_url)
