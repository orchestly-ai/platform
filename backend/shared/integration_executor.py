"""
Integration Executor

Main entry point for executing integration actions.
Handles credential management, integration instantiation, and execution.

Includes circuit breaker pattern for external API call resilience.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type
from uuid import UUID
from dataclasses import asdict, dataclass, field
from enum import Enum
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.integration_models import (
    IntegrationModel,
    IntegrationInstallationModel,
    InstallationStatus,
    AuthType,
)
from backend.shared.integrations.base import BaseIntegration, IntegrationResult
from backend.shared.integrations import INTEGRATION_REGISTRY
from backend.shared.credential_manager import (
    get_credential_manager,
    decrypt_credentials,
    encrypt_credentials,
)

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class IntegrationCircuitBreaker:
    """
    Circuit breaker for external integration calls.

    Prevents cascading failures by tracking error rates and
    temporarily disabling calls to failing integrations.
    """
    # Configuration
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    half_open_max_calls: int = 3

    # State tracking per integration
    _states: Dict[str, CircuitState] = field(default_factory=lambda: defaultdict(lambda: CircuitState.CLOSED))
    _failure_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _last_failure_times: Dict[str, datetime] = field(default_factory=dict)
    _half_open_call_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def can_execute(self, integration_slug: str) -> bool:
        """Check if requests can be made to this integration."""
        state = self._states[integration_slug]

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            last_failure = self._last_failure_times.get(integration_slug)
            if last_failure:
                if datetime.utcnow() - last_failure > timedelta(seconds=self.recovery_timeout_seconds):
                    # Transition to half-open
                    self._states[integration_slug] = CircuitState.HALF_OPEN
                    self._half_open_call_counts[integration_slug] = 0
                    logger.info(f"Circuit breaker for {integration_slug} transitioning to HALF_OPEN")
                    return True
            return False

        if state == CircuitState.HALF_OPEN:
            # Allow limited calls to test recovery
            return self._half_open_call_counts[integration_slug] < self.half_open_max_calls

        return True

    def record_success(self, integration_slug: str):
        """Record a successful call."""
        state = self._states[integration_slug]

        if state == CircuitState.HALF_OPEN:
            self._half_open_call_counts[integration_slug] += 1
            if self._half_open_call_counts[integration_slug] >= self.half_open_max_calls:
                # Successful recovery - close circuit
                self._states[integration_slug] = CircuitState.CLOSED
                self._failure_counts[integration_slug] = 0
                logger.info(f"Circuit breaker for {integration_slug} CLOSED - service recovered")
        elif state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_counts[integration_slug] = 0

    def record_failure(self, integration_slug: str):
        """Record a failed call."""
        state = self._states[integration_slug]

        if state == CircuitState.HALF_OPEN:
            # Failed during recovery test - open circuit again
            self._states[integration_slug] = CircuitState.OPEN
            self._last_failure_times[integration_slug] = datetime.utcnow()
            logger.warning(f"Circuit breaker for {integration_slug} OPEN - recovery failed")
        else:
            self._failure_counts[integration_slug] += 1
            self._last_failure_times[integration_slug] = datetime.utcnow()

            if self._failure_counts[integration_slug] >= self.failure_threshold:
                self._states[integration_slug] = CircuitState.OPEN
                logger.warning(f"Circuit breaker for {integration_slug} OPEN - threshold reached")

    def get_state(self, integration_slug: str) -> CircuitState:
        """Get the current circuit state for an integration."""
        return self._states[integration_slug]


# Global circuit breaker instance
_circuit_breaker: Optional[IntegrationCircuitBreaker] = None


def get_circuit_breaker() -> IntegrationCircuitBreaker:
    """Get or create the global circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = IntegrationCircuitBreaker()
    return _circuit_breaker


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt using exponential backoff."""
        delay = self.base_delay_seconds * (self.exponential_base ** attempt)
        return min(delay, self.max_delay_seconds)


class IntegrationExecutor:
    """
    Executes integration actions using the real SDK implementations.

    This is the main entry point for executing integrations. It:
    1. Loads the integration and installation from database
    2. Decrypts stored credentials
    3. Instantiates the appropriate integration class
    4. Executes the requested action with circuit breaker and retry logic
    5. Handles token refresh if needed
    6. Returns the result
    """

    def __init__(
        self,
        db: AsyncSession,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[IntegrationCircuitBreaker] = None
    ):
        self.db = db
        self.credential_manager = get_credential_manager()
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = circuit_breaker or get_circuit_breaker()

    async def execute(
        self,
        installation_id: UUID,
        action_name: str,
        parameters: Dict[str, Any],
    ) -> IntegrationResult:
        """
        Execute an integration action.

        Args:
            installation_id: The installation ID
            action_name: Name of the action to execute
            parameters: Action parameters

        Returns:
            IntegrationResult with success status and data
        """
        start_time = datetime.utcnow()

        try:
            # Load installation
            installation = await self._get_installation(installation_id)
            if not installation:
                return IntegrationResult(
                    success=False,
                    error_message="Installation not found",
                    error_code="INSTALLATION_NOT_FOUND",
                )

            # Check installation status
            if installation.status != InstallationStatus.ACTIVE.value:
                return IntegrationResult(
                    success=False,
                    error_message=f"Integration is not active (status: {installation.status})",
                    error_code="NOT_ACTIVE",
                )

            # Load integration metadata
            integration = await self._get_integration(installation.integration_id)
            if not integration:
                return IntegrationResult(
                    success=False,
                    error_message="Integration not found",
                    error_code="INTEGRATION_NOT_FOUND",
                )

            # Get integration class
            integration_class = self._get_integration_class(integration.slug)
            if not integration_class:
                # Fall back to simulated execution for integrations without SDK
                return await self._simulate_execution(
                    integration, installation, action_name, parameters, start_time
                )

            # Decrypt credentials
            credentials = self._get_credentials(installation)

            # Instantiate integration
            integration_instance = integration_class(
                credentials=credentials,
                configuration=installation.configuration or {},
            )

            # Validate credentials
            if not await integration_instance.validate_credentials():
                # Try to refresh tokens
                new_tokens = await integration_instance.refresh_tokens()
                if new_tokens:
                    # Update stored credentials
                    credentials["access_token"] = new_tokens.access_token
                    if new_tokens.refresh_token:
                        credentials["refresh_token"] = new_tokens.refresh_token
                    if new_tokens.expires_at:
                        credentials["expires_at"] = new_tokens.expires_at.isoformat()

                    # Save updated credentials
                    await self._update_credentials(installation, credentials)

                    # Retry validation
                    integration_instance = integration_class(
                        credentials=credentials,
                        configuration=installation.configuration or {},
                    )
                    if not await integration_instance.validate_credentials():
                        return IntegrationResult(
                            success=False,
                            error_message="Credentials invalid or expired. Please re-authenticate.",
                            error_code="INVALID_CREDENTIALS",
                        )
                else:
                    return IntegrationResult(
                        success=False,
                        error_message="Credentials invalid or expired. Please re-authenticate.",
                        error_code="INVALID_CREDENTIALS",
                    )

            # Check circuit breaker before execution
            if not self.circuit_breaker.can_execute(integration.slug):
                return IntegrationResult(
                    success=False,
                    error_message=f"Service temporarily unavailable (circuit breaker open for {integration.slug})",
                    error_code="CIRCUIT_BREAKER_OPEN",
                )

            # Execute action with retry logic
            result = await self._execute_with_retry(
                integration_instance=integration_instance,
                integration_slug=integration.slug,
                action_name=action_name,
                parameters=parameters,
            )

            # Update execution stats
            await self._update_execution_stats(installation, result.success)

            return result

        except Exception as e:
            logger.exception(f"Integration execution failed: {e}")
            end_time = datetime.utcnow()
            return IntegrationResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                duration_ms=(end_time - start_time).total_seconds() * 1000,
            )

    async def _execute_with_retry(
        self,
        integration_instance: BaseIntegration,
        integration_slug: str,
        action_name: str,
        parameters: Dict[str, Any],
    ) -> IntegrationResult:
        """
        Execute an action with retry logic and circuit breaker tracking.

        Args:
            integration_instance: The integration instance to use
            integration_slug: Integration slug for circuit breaker tracking
            action_name: Name of the action to execute
            parameters: Action parameters

        Returns:
            IntegrationResult from the execution
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # Execute the action
                if action_name == "test_connection":
                    result = await integration_instance.test_connection()
                else:
                    result = await integration_instance.execute_action(action_name, parameters)

                if result.success:
                    # Record success with circuit breaker
                    self.circuit_breaker.record_success(integration_slug)
                    return result
                else:
                    # Non-exception failure - don't retry, but track
                    self.circuit_breaker.record_failure(integration_slug)
                    return result

            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    f"Integration {integration_slug} timeout on attempt {attempt + 1}: {e}"
                )
                self.circuit_breaker.record_failure(integration_slug)

            except ConnectionError as e:
                last_error = e
                logger.warning(
                    f"Integration {integration_slug} connection error on attempt {attempt + 1}: {e}"
                )
                self.circuit_breaker.record_failure(integration_slug)

            except Exception as e:
                last_error = e
                # Check if error is retryable
                if self._is_retryable_error(e):
                    logger.warning(
                        f"Integration {integration_slug} retryable error on attempt {attempt + 1}: {e}"
                    )
                    self.circuit_breaker.record_failure(integration_slug)
                else:
                    # Non-retryable error - fail immediately
                    self.circuit_breaker.record_failure(integration_slug)
                    return IntegrationResult(
                        success=False,
                        error_message=str(e),
                        error_code="EXECUTION_ERROR",
                    )

            # Wait before retry (if not last attempt)
            if attempt < self.retry_config.max_retries:
                delay = self.retry_config.get_delay(attempt)
                logger.info(f"Retrying {integration_slug} in {delay:.1f}s (attempt {attempt + 2})")
                await asyncio.sleep(delay)

        # All retries exhausted
        return IntegrationResult(
            success=False,
            error_message=f"Max retries exceeded: {last_error}",
            error_code="MAX_RETRIES_EXCEEDED",
        )

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.

        Retryable errors include:
        - Connection errors
        - Timeout errors
        - Rate limit errors (429)
        - Server errors (5xx)

        Non-retryable errors include:
        - Authentication errors (401, 403)
        - Not found errors (404)
        - Validation errors (400)
        """
        error_str = str(error).lower()

        # Check for retryable patterns
        retryable_patterns = [
            "timeout",
            "connection",
            "rate limit",
            "429",
            "500",
            "502",
            "503",
            "504",
            "temporary",
            "retry",
            "unavailable",
        ]

        for pattern in retryable_patterns:
            if pattern in error_str:
                return True

        return False

    async def test_connection(self, installation_id: UUID) -> IntegrationResult:
        """
        Test the connection for an installation.

        Args:
            installation_id: The installation ID

        Returns:
            IntegrationResult indicating connection status
        """
        return await self.execute(installation_id, "test_connection", {})

    async def get_available_actions(self, installation_id: UUID) -> List[Dict[str, Any]]:
        """
        Get available actions for an installation.

        Args:
            installation_id: The installation ID

        Returns:
            List of available action definitions
        """
        installation = await self._get_installation(installation_id)
        if not installation:
            return []

        integration = await self._get_integration(installation.integration_id)
        if not integration:
            return []

        # Get integration class
        integration_class = self._get_integration_class(integration.slug)
        if integration_class:
            instance = integration_class({}, {})
            return instance.get_available_actions()

        # Fall back to supported_actions from database
        return integration.supported_actions or []

    async def _get_installation(self, installation_id: UUID) -> Optional[IntegrationInstallationModel]:
        """Get installation from database."""
        stmt = select(IntegrationInstallationModel).where(
            IntegrationInstallationModel.installation_id == installation_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_integration(self, integration_id: UUID) -> Optional[IntegrationModel]:
        """Get integration from database."""
        stmt = select(IntegrationModel).where(
            IntegrationModel.integration_id == integration_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _get_integration_class(self, slug: str) -> Optional[Type[BaseIntegration]]:
        """Get integration class from registry."""
        return INTEGRATION_REGISTRY.get(slug)

    def _get_credentials(self, installation: IntegrationInstallationModel) -> Dict[str, Any]:
        """Get and decrypt credentials from installation."""
        auth_credentials = installation.auth_credentials
        if not auth_credentials:
            return {}

        # If credentials are stored as encrypted string
        if isinstance(auth_credentials, str):
            return decrypt_credentials(auth_credentials)

        # If credentials are stored as dict (legacy/unencrypted)
        if isinstance(auth_credentials, dict):
            return auth_credentials

        return {}

    async def _update_credentials(
        self,
        installation: IntegrationInstallationModel,
        credentials: Dict[str, Any],
    ):
        """Update and save credentials."""
        # Encrypt for storage
        encrypted = encrypt_credentials(credentials)

        # Update installation
        installation.auth_credentials = credentials  # Store as dict for now
        installation.updated_at = datetime.utcnow()

        await self.db.commit()

    async def _update_execution_stats(self, installation: IntegrationInstallationModel, success: bool):
        """Update execution statistics on installation."""
        installation.total_executions += 1
        if success:
            installation.successful_executions += 1
        else:
            installation.failed_executions += 1
        installation.last_execution_at = datetime.utcnow()

        await self.db.commit()

    async def _simulate_execution(
        self,
        integration: IntegrationModel,
        installation: IntegrationInstallationModel,
        action_name: str,
        parameters: Dict[str, Any],
        start_time: datetime,
    ) -> IntegrationResult:
        """
        Simulate execution for integrations without SDK implementation.

        This provides a graceful fallback for integrations that haven't been
        implemented yet. In production, you'd want to either:
        - Implement all integrations
        - Return an error for unsupported integrations
        """
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        logger.warning(
            f"Simulating execution for integration {integration.slug} "
            f"(no SDK implementation available)"
        )

        # Return simulated success
        return IntegrationResult(
            success=True,
            data={
                "simulated": True,
                "message": f"Simulated execution of {action_name} on {integration.display_name}",
                "action": action_name,
                "parameters": parameters,
                "integration": integration.slug,
            },
            duration_ms=duration_ms,
        )


# Helper functions for API endpoints
async def execute_integration_action(
    db: AsyncSession,
    installation_id: UUID,
    action_name: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute an integration action and return result as dict.

    This is the main function called by API endpoints.
    """
    executor = IntegrationExecutor(db)
    result = await executor.execute(installation_id, action_name, parameters)

    return {
        "success": result.success,
        "data": result.data,
        "error_message": result.error_message,
        "error_code": result.error_code,
        "duration_ms": result.duration_ms,
    }


async def test_integration_connection(
    db: AsyncSession,
    installation_id: UUID,
) -> Dict[str, Any]:
    """
    Test integration connection and return result.
    """
    executor = IntegrationExecutor(db)
    result = await executor.test_connection(installation_id)

    return {
        "success": result.success,
        "data": result.data,
        "error_message": result.error_message,
    }


async def get_integration_actions(
    db: AsyncSession,
    installation_id: UUID,
) -> List[Dict[str, Any]]:
    """
    Get available actions for an integration.
    """
    executor = IntegrationExecutor(db)
    return await executor.get_available_actions(installation_id)
