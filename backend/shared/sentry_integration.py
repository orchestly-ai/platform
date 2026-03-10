"""
Sentry Integration

Error tracking and performance monitoring with Sentry.
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from backend.shared.config import get_settings


def init_sentry():
    """
    Initialize Sentry SDK.

    Call this during application startup.
    """
    settings = get_settings()

    # Only initialize if DSN is configured
    if not hasattr(settings, 'SENTRY_DSN') or not settings.SENTRY_DSN:
        print("⚠️  Sentry DSN not configured - error tracking disabled")
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=settings.APP_VERSION,

        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
            LoggingIntegration(
                level=None,  # Capture logs at all levels
                event_level="error"  # Send logs at error level and above as events
            ),
        ],

        # Performance monitoring
        traces_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 1.0,

        # Error sampling
        sample_rate=1.0,

        # Send PII (personally identifiable information)
        send_default_pii=False,

        # Attach stack locals to error events
        attach_stacktrace=True,

        # Maximum breadcrumbs
        max_breadcrumbs=50,

        # Debug mode
        debug=settings.DEBUG,

        # Before send hook (filter sensitive data)
        before_send=before_send_filter,

        # Before breadcrumb hook
        before_breadcrumb=before_breadcrumb_filter,
    )

    print(f"✅ Sentry initialized - Environment: {settings.ENVIRONMENT}")


def before_send_filter(event, hint):
    """
    Filter events before sending to Sentry.

    Remove sensitive information like API keys, passwords, etc.
    """
    # Remove sensitive headers
    if 'request' in event and 'headers' in event['request']:
        headers = event['request']['headers']
        sensitive_headers = [
            'Authorization',
            'X-API-Key',
            'Cookie',
            'Set-Cookie',
        ]
        for header in sensitive_headers:
            if header in headers:
                headers[header] = '[Filtered]'

    # Remove sensitive environment variables
    if 'contexts' in event and 'runtime' in event['contexts']:
        runtime = event['contexts']['runtime']
        if 'env' in runtime:
            env = runtime['env']
            sensitive_env_vars = [
                'OPENAI_API_KEY',
                'ANTHROPIC_API_KEY',
                'JWT_SECRET_KEY',
                'POSTGRES_PASSWORD',
                'REDIS_PASSWORD',
            ]
            for var in sensitive_env_vars:
                if var in env:
                    env[var] = '[Filtered]'

    # Ignore certain exceptions
    if 'exception' in event:
        for exception in event['exception'].get('values', []):
            exception_type = exception.get('type', '')

            # Ignore 404 errors
            if '404' in exception_type or 'NotFound' in exception_type:
                return None

            # Ignore client disconnects
            if 'ClientDisconnect' in exception_type:
                return None

    return event


def before_breadcrumb_filter(crumb, hint):
    """
    Filter breadcrumbs before adding to event.

    Reduce noise by filtering out certain breadcrumb types.
    """
    # Filter out HTTP requests to health check endpoints
    if crumb.get('category') == 'http':
        url = crumb.get('data', {}).get('url', '')
        if '/health' in url or '/metrics' in url:
            return None

    return crumb


def capture_exception(error: Exception, context: dict = None):
    """
    Capture exception and send to Sentry.

    Args:
        error: Exception to capture
        context: Additional context to attach
    """
    with sentry_sdk.push_scope() as scope:
        if context:
            for key, value in context.items():
                scope.set_context(key, value)

        sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", context: dict = None):
    """
    Capture message and send to Sentry.

    Args:
        message: Message to capture
        level: Severity level (debug, info, warning, error, fatal)
        context: Additional context to attach
    """
    with sentry_sdk.push_scope() as scope:
        if context:
            for key, value in context.items():
                scope.set_context(key, value)

        sentry_sdk.capture_message(message, level=level)


def set_user_context(user_id: str, email: str = None, ip_address: str = None):
    """
    Set user context for error tracking.

    Args:
        user_id: User ID
        email: User email (optional)
        ip_address: User IP address (optional)
    """
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "ip_address": ip_address,
    })


def set_tag(key: str, value: str):
    """
    Set tag for error tracking.

    Args:
        key: Tag key
        value: Tag value
    """
    sentry_sdk.set_tag(key, value)


def add_breadcrumb(message: str, category: str = "default", level: str = "info", data: dict = None):
    """
    Add breadcrumb for debugging.

    Args:
        message: Breadcrumb message
        category: Breadcrumb category
        level: Severity level
        data: Additional data
    """
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data or {}
    )
