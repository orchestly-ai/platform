"""
Integration Implementations

This package contains TWO integration systems:

1. SDK-based Integrations (Original)
   - BaseIntegration: Abstract base class
   - Individual files: slack.py, stripe.py, github.py, etc.
   - Full control for complex integrations

2. Declarative Integrations (New)
   - YAML config files define integrations
   - HTTP actions executed automatically
   - SDK fallback for complex actions
   - Faster to add new integrations

Usage (SDK-based):
    from backend.integrations.slack import SlackIntegration
    integration = SlackIntegration(api_token="xoxb-...")
    result = await integration.execute_action("send_message", {...})

Usage (Declarative):
    from backend.integrations import get_action_executor
    executor = get_action_executor()
    result = await executor.execute("discord", "send_message", credentials, {...})
"""

# SDK-based integration system (original)
from .base import BaseIntegration, IntegrationResult, IntegrationError
from .base import AuthType as SDKAuthType

# Declarative integration system (new)
from .schema import (
    AuthType,
    IntegrationCategory,
    ActionType,
    IntegrationConfig,
    ActionConfig,
    IntegrationCredentials,
    ActionExecutionRequest,
    ActionExecutionResult,
)
from .registry import (
    IntegrationRegistry,
    get_integration_registry,
    reload_integrations,
)
from .executor import (
    IntegrationActionExecutor,
    get_action_executor,
)
from .http_executor import (
    HttpActionExecutor,
    TemplateEngine,
    test_connection,
    RateLimiter,
    get_rate_limiter,
    RetryConfig,
    get_retry_config,
)

# Testing framework (optional import)
try:
    from .testing import (
        IntegrationTestRunner,
        MockResponse,
        TestResult,
        TestSuiteResult,
        run_integration_tests,
    )
    _testing_available = True
except ImportError:
    _testing_available = False

__all__ = [
    # SDK-based (original)
    "BaseIntegration",
    "IntegrationResult",
    "IntegrationError",
    "SDKAuthType",
    # Declarative schema
    "AuthType",
    "IntegrationCategory",
    "ActionType",
    "IntegrationConfig",
    "ActionConfig",
    "IntegrationCredentials",
    "ActionExecutionRequest",
    "ActionExecutionResult",
    # Declarative registry
    "IntegrationRegistry",
    "get_integration_registry",
    "reload_integrations",
    # Declarative executor
    "IntegrationActionExecutor",
    "get_action_executor",
    # HTTP executor
    "HttpActionExecutor",
    "TemplateEngine",
    "test_connection",
    "RateLimiter",
    "get_rate_limiter",
    "RetryConfig",
    "get_retry_config",
    # Testing framework
    "IntegrationTestRunner",
    "MockResponse",
    "TestResult",
    "TestSuiteResult",
    "run_integration_tests",
]
