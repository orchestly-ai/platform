"""
Base Integration Class

Provides the foundation for all integration implementations.
All integrations must inherit from BaseIntegration and implement execute_action().
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AuthType(str, Enum):
    """Authentication types supported."""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"


@dataclass
class IntegrationResult:
    """Result of an integration action execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class IntegrationError(Exception):
    """Base exception for integration errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class BaseIntegration(ABC):
    """
    Abstract base class for all integrations.

    All integrations must:
    1. Inherit from this class
    2. Implement execute_action()
    3. Define supported_actions
    4. Handle authentication
    """

    def __init__(
        self,
        auth_credentials: Dict[str, Any],
        configuration: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize integration.

        Args:
            auth_credentials: Authentication credentials (API key, OAuth token, etc.)
            configuration: Optional configuration parameters
        """
        self.auth_credentials = auth_credentials
        self.configuration = configuration or {}
        self.logger = logging.getLogger(self.__class__.__name__)

        # Validate credentials on init
        self._validate_credentials()

    @property
    @abstractmethod
    def name(self) -> str:
        """Integration name (e.g., 'slack', 'stripe')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g., 'Slack', 'Stripe')."""
        pass

    @property
    @abstractmethod
    def auth_type(self) -> AuthType:
        """Authentication type required."""
        pass

    @property
    @abstractmethod
    def supported_actions(self) -> List[str]:
        """List of supported action names."""
        pass

    @abstractmethod
    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
    ) -> IntegrationResult:
        """
        Execute an integration action.

        Args:
            action: Action name (must be in supported_actions)
            params: Action parameters

        Returns:
            IntegrationResult with success/failure and data

        Raises:
            IntegrationError: If action fails
        """
        pass

    @abstractmethod
    async def test_connection(self) -> IntegrationResult:
        """
        Test if the integration connection is working.

        Returns:
            IntegrationResult indicating connection health
        """
        pass

    def _validate_credentials(self) -> None:
        """
        Validate that required credentials are present.
        Override in subclass for specific validation.
        """
        if not self.auth_credentials:
            raise IntegrationError(
                f"Authentication credentials required for {self.display_name}",
                code="MISSING_CREDENTIALS",
            )

    def _validate_action(self, action: str) -> None:
        """Validate that action is supported."""
        if action not in self.supported_actions:
            raise IntegrationError(
                f"Action '{action}' not supported. "
                f"Supported actions: {', '.join(self.supported_actions)}",
                code="UNSUPPORTED_ACTION",
            )

    def _log_execution(
        self,
        action: str,
        params: Dict[str, Any],
        result: IntegrationResult,
    ) -> None:
        """Log action execution for debugging."""
        status = "SUCCESS" if result.success else "FAILED"
        self.logger.info(
            f"[{self.name}] Action '{action}' {status} "
            f"(duration: {result.duration_ms}ms)"
        )

        if not result.success:
            self.logger.error(
                f"[{self.name}] Error: {result.error_message} "
                f"(code: {result.error_code})"
            )
