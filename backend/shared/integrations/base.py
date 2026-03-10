"""
Base Integration Framework

Provides the base class for all real integrations. Each integration must
implement authentication, action execution, and credential validation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AuthMethod(str, Enum):
    """Authentication methods supported by integrations."""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC_AUTH = "basic_auth"
    BEARER_TOKEN = "bearer_token"


@dataclass
class IntegrationResult:
    """Result of an integration action execution."""
    success: bool
    data: Optional[Any] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OAuthConfig:
    """OAuth 2.0 configuration for an integration."""
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: List[str]
    redirect_uri: str


@dataclass
class OAuthTokens:
    """OAuth 2.0 tokens stored after authentication."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None


class BaseIntegration(ABC):
    """
    Base class for all integrations.

    Each integration must implement:
    - get_auth_method(): Return the authentication method
    - get_oauth_config(): Return OAuth config (if OAuth)
    - validate_credentials(): Validate stored credentials
    - execute_action(): Execute an action with given parameters
    - get_available_actions(): Return list of supported actions
    """

    # Integration metadata (override in subclass)
    name: str = "base"
    display_name: str = "Base Integration"
    description: str = "Base integration class"
    icon_url: str = ""
    documentation_url: str = ""

    def __init__(self, credentials: Dict[str, Any], configuration: Optional[Dict[str, Any]] = None):
        """
        Initialize integration with credentials and configuration.

        Args:
            credentials: Authentication credentials (OAuth tokens, API keys, etc.)
            configuration: Integration-specific configuration
        """
        self.credentials = credentials
        self.configuration = configuration or {}
        self._initialized = False

    @abstractmethod
    def get_auth_method(self) -> AuthMethod:
        """Return the authentication method for this integration."""
        pass

    @abstractmethod
    def get_oauth_config(self) -> Optional[OAuthConfig]:
        """Return OAuth configuration if this integration uses OAuth."""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate that credentials are valid and not expired."""
        pass

    @abstractmethod
    async def refresh_tokens(self) -> Optional[OAuthTokens]:
        """Refresh OAuth tokens if expired. Return new tokens or None."""
        pass

    @abstractmethod
    async def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> IntegrationResult:
        """
        Execute an integration action.

        Args:
            action_name: Name of the action to execute
            parameters: Parameters for the action

        Returns:
            IntegrationResult with success status and data/error
        """
        pass

    @abstractmethod
    def get_available_actions(self) -> List[Dict[str, Any]]:
        """
        Return list of available actions with their schemas.

        Returns:
            List of action definitions with name, description, and parameter schema
        """
        pass

    def get_action_schema(self, action_name: str) -> Optional[Dict[str, Any]]:
        """Get the parameter schema for a specific action."""
        actions = self.get_available_actions()
        for action in actions:
            if action["name"] == action_name:
                return action.get("input_schema")
        return None

    async def test_connection(self) -> IntegrationResult:
        """
        Test that the integration connection is working.

        Default implementation validates credentials.
        Subclasses can override for more specific tests.
        """
        try:
            is_valid = await self.validate_credentials()
            if is_valid:
                return IntegrationResult(
                    success=True,
                    data={"message": "Connection successful", "integration": self.name}
                )
            else:
                return IntegrationResult(
                    success=False,
                    error_message="Credentials validation failed"
                )
        except Exception as e:
            logger.error(f"Connection test failed for {self.name}: {e}")
            return IntegrationResult(
                success=False,
                error_message=str(e)
            )


class OAuthIntegration(BaseIntegration):
    """Base class for OAuth 2.0 integrations."""

    def get_auth_method(self) -> AuthMethod:
        return AuthMethod.OAUTH2

    def get_access_token(self) -> Optional[str]:
        """Get the access token from credentials."""
        return self.credentials.get("access_token")

    def get_refresh_token(self) -> Optional[str]:
        """Get the refresh token from credentials."""
        return self.credentials.get("refresh_token")

    def is_token_expired(self) -> bool:
        """Check if the access token is expired."""
        expires_at = self.credentials.get("expires_at")
        if not expires_at:
            return False
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        return datetime.utcnow() > expires_at


class APIKeyIntegration(BaseIntegration):
    """Base class for API key integrations."""

    def get_auth_method(self) -> AuthMethod:
        return AuthMethod.API_KEY

    def get_oauth_config(self) -> Optional[OAuthConfig]:
        return None  # API key integrations don't use OAuth

    async def refresh_tokens(self) -> Optional[OAuthTokens]:
        return None  # API key integrations don't have tokens to refresh

    def get_api_key(self) -> Optional[str]:
        """Get the API key from credentials."""
        return self.credentials.get("api_key")
