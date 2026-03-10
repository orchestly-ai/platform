"""
Integration Action Executor

Main entry point for executing integration actions.
Routes to HTTP or SDK executor based on action type.
"""

import logging
import importlib
from datetime import datetime
from typing import Any, Dict, Optional

from .schema import (
    ActionConfig,
    ActionExecutionRequest,
    ActionExecutionResult,
    ActionType,
    IntegrationConfig,
    IntegrationCredentials,
)
from .registry import get_integration_registry
from .http_executor import HttpActionExecutor, test_connection

logger = logging.getLogger(__name__)


class IntegrationActionExecutor:
    """
    Main executor for integration actions.

    Routes actions to the appropriate executor (HTTP or SDK) based on
    the action configuration.

    Usage:
        executor = IntegrationActionExecutor()

        result = await executor.execute(
            integration_id="discord",
            action_name="send_message",
            credentials=credentials,
            parameters={"channel_id": "123", "content": "Hello!"}
        )
    """

    def __init__(self):
        self.registry = get_integration_registry()
        self.http_executor = HttpActionExecutor()
        self._sdk_handlers: Dict[str, Any] = {}

    async def execute(
        self,
        integration_id: str,
        action_name: str,
        credentials: IntegrationCredentials,
        parameters: Dict[str, Any]
    ) -> ActionExecutionResult:
        """
        Execute an integration action.

        Args:
            integration_id: Integration identifier
            action_name: Action to execute
            credentials: User credentials for the integration
            parameters: Action parameters

        Returns:
            ActionExecutionResult with response data
        """
        start_time = datetime.utcnow()

        # Get integration config
        integration = self.registry.get(integration_id)
        if not integration:
            return ActionExecutionResult(
                success=False,
                error=f"Integration not found: {integration_id}",
                error_code="INTEGRATION_NOT_FOUND"
            )

        # Get action config
        action = integration.get_action(action_name)
        if not action:
            return ActionExecutionResult(
                success=False,
                error=f"Action not found: {action_name}",
                error_code="ACTION_NOT_FOUND"
            )

        # Validate required parameters
        validation_error = self._validate_parameters(action, parameters)
        if validation_error:
            return ActionExecutionResult(
                success=False,
                error=validation_error,
                error_code="INVALID_PARAMETERS"
            )

        # Route to appropriate executor
        if action.type == ActionType.HTTP:
            return await self._execute_http(integration, action, credentials, parameters)
        elif action.type == ActionType.SDK:
            return await self._execute_sdk(integration, action, credentials, parameters)
        else:
            return ActionExecutionResult(
                success=False,
                error=f"Unknown action type: {action.type}",
                error_code="INVALID_ACTION_TYPE"
            )

    async def execute_request(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        """Execute from an ActionExecutionRequest object."""
        if not request.credentials:
            return ActionExecutionResult(
                success=False,
                error="Credentials required",
                error_code="MISSING_CREDENTIALS"
            )

        return await self.execute(
            integration_id=request.integration_id,
            action_name=request.action_name,
            credentials=request.credentials,
            parameters=request.parameters
        )

    async def test_connection(
        self,
        integration_id: str,
        credentials: IntegrationCredentials
    ) -> ActionExecutionResult:
        """
        Test connection to an integration.

        Args:
            integration_id: Integration identifier
            credentials: User credentials

        Returns:
            ActionExecutionResult indicating connection status
        """
        integration = self.registry.get(integration_id)
        if not integration:
            return ActionExecutionResult(
                success=False,
                error=f"Integration not found: {integration_id}",
                error_code="INTEGRATION_NOT_FOUND"
            )

        return await test_connection(integration, credentials)

    def _validate_parameters(
        self,
        action: ActionConfig,
        parameters: Dict[str, Any]
    ) -> Optional[str]:
        """
        Validate action parameters.

        Returns error message if invalid, None if valid.
        """
        for param in action.parameters:
            if param.required and param.name not in parameters:
                return f"Missing required parameter: {param.name}"

            if param.name in parameters:
                value = parameters[param.name]

                # Type validation (basic)
                if param.enum and value not in param.enum:
                    return f"Invalid value for {param.name}: must be one of {param.enum}"

        return None

    async def _execute_http(
        self,
        integration: IntegrationConfig,
        action: ActionConfig,
        credentials: IntegrationCredentials,
        parameters: Dict[str, Any]
    ) -> ActionExecutionResult:
        """Execute an HTTP-based action."""
        logger.info(f"Executing HTTP action: {integration.id}.{action.name}")
        return await self.http_executor.execute(
            integration=integration,
            action=action,
            credentials=credentials,
            parameters=parameters
        )

    async def _execute_sdk(
        self,
        integration: IntegrationConfig,
        action: ActionConfig,
        credentials: IntegrationCredentials,
        parameters: Dict[str, Any]
    ) -> ActionExecutionResult:
        """Execute an SDK-based action."""
        if not action.sdk:
            return ActionExecutionResult(
                success=False,
                error="SDK configuration missing",
                error_code="INVALID_SDK_CONFIG"
            )

        handler_path = action.sdk.handler
        logger.info(f"Executing SDK action: {integration.id}.{action.name} via {handler_path}")

        try:
            # Load handler function
            handler = self._load_sdk_handler(handler_path)
            if not handler:
                return ActionExecutionResult(
                    success=False,
                    error=f"SDK handler not found: {handler_path}",
                    error_code="HANDLER_NOT_FOUND"
                )

            # Execute handler
            start_time = datetime.utcnow()

            if action.sdk.async_handler:
                result = await handler(credentials, parameters)
            else:
                result = handler(credentials, parameters)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Normalize result
            if isinstance(result, ActionExecutionResult):
                return result
            elif isinstance(result, dict):
                return ActionExecutionResult(
                    success=True,
                    data=result,
                    duration_ms=duration_ms
                )
            else:
                return ActionExecutionResult(
                    success=True,
                    data={"result": result},
                    duration_ms=duration_ms
                )

        except Exception as e:
            logger.exception(f"SDK handler execution failed: {e}")
            return ActionExecutionResult(
                success=False,
                error=str(e),
                error_code="SDK_EXECUTION_ERROR"
            )

    def _load_sdk_handler(self, handler_path: str):
        """
        Load an SDK handler function from a module path.

        Args:
            handler_path: Path like "integrations.discord.create_thread"

        Returns:
            Handler function or None
        """
        if handler_path in self._sdk_handlers:
            return self._sdk_handlers[handler_path]

        try:
            # Split into module and function
            parts = handler_path.rsplit('.', 1)
            if len(parts) != 2:
                logger.error(f"Invalid handler path: {handler_path}")
                return None

            module_path, function_name = parts

            # Import module
            module = importlib.import_module(module_path)

            # Get function
            handler = getattr(module, function_name, None)
            if handler:
                self._sdk_handlers[handler_path] = handler

            return handler

        except ImportError as e:
            logger.error(f"Failed to import SDK handler module: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load SDK handler: {e}")
            return None

    def get_available_actions(self, integration_id: str) -> list:
        """Get list of available actions for an integration."""
        integration = self.registry.get(integration_id)
        if not integration:
            return []

        return [
            {
                "name": action.name,
                "display_name": action.display_name,
                "description": action.description,
                "parameters": [
                    {
                        "name": p.name,
                        "label": p.label,
                        "type": p.type.value,
                        "required": p.required,
                        "description": p.description,
                    }
                    for p in action.parameters
                ]
            }
            for action in integration.actions.values()
        ]


# ============ Singleton Instance ============

_executor: Optional[IntegrationActionExecutor] = None


def get_action_executor() -> IntegrationActionExecutor:
    """Get the global action executor instance."""
    global _executor
    if _executor is None:
        _executor = IntegrationActionExecutor()
    return _executor
