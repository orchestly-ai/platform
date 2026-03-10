"""
HTTP Action Executor

Executes HTTP-based integration actions defined in YAML configs.
Handles template substitution, authentication headers, response mapping,
rate limiting, and automatic retries with exponential backoff.
"""

import re
import json
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import aiohttp

from .schema import (
    ActionConfig,
    ActionExecutionResult,
    IntegrationConfig,
    IntegrationCredentials,
    AuthType,
    HttpMethod,
)

logger = logging.getLogger(__name__)


# ============ Rate Limiter ============

class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Tracks calls per integration and enforces rate limits.
    """

    def __init__(self):
        # Track request timestamps per integration
        self._requests: Dict[str, List[datetime]] = defaultdict(list)
        # Default limits per integration (requests per minute)
        self._limits: Dict[str, int] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()

    def set_limit(self, integration_id: str, requests_per_minute: int):
        """Set rate limit for an integration."""
        self._limits[integration_id] = requests_per_minute

    def get_limit(self, integration_id: str) -> int:
        """Get rate limit for an integration (default: 60/min)."""
        return self._limits.get(integration_id, 60)

    async def acquire(self, integration_id: str, rate_limit: Optional[int] = None) -> Tuple[bool, float]:
        """
        Try to acquire a request slot.

        Args:
            integration_id: Integration identifier
            rate_limit: Override rate limit (requests per minute)

        Returns:
            Tuple of (allowed, wait_seconds)
            - allowed: True if request can proceed
            - wait_seconds: Seconds to wait if not allowed
        """
        async with self._lock:
            limit = rate_limit or self.get_limit(integration_id)
            now = datetime.utcnow()
            window_start = now - timedelta(minutes=1)

            # Clean old requests
            self._requests[integration_id] = [
                ts for ts in self._requests[integration_id]
                if ts > window_start
            ]

            current_count = len(self._requests[integration_id])

            if current_count < limit:
                self._requests[integration_id].append(now)
                return True, 0.0

            # Calculate wait time until oldest request expires
            if self._requests[integration_id]:
                oldest = min(self._requests[integration_id])
                wait_seconds = (oldest + timedelta(minutes=1) - now).total_seconds()
                return False, max(0.1, wait_seconds)

            return False, 1.0

    async def wait_and_acquire(
        self,
        integration_id: str,
        rate_limit: Optional[int] = None,
        max_wait: float = 60.0
    ) -> bool:
        """
        Wait for a request slot if necessary.

        Args:
            integration_id: Integration identifier
            rate_limit: Override rate limit
            max_wait: Maximum seconds to wait

        Returns:
            True if acquired, False if max_wait exceeded
        """
        total_waited = 0.0

        while total_waited < max_wait:
            allowed, wait_seconds = await self.acquire(integration_id, rate_limit)

            if allowed:
                return True

            if total_waited + wait_seconds > max_wait:
                return False

            logger.debug(f"Rate limited for {integration_id}, waiting {wait_seconds:.1f}s")
            await asyncio.sleep(wait_seconds)
            total_waited += wait_seconds

        return False

    def get_stats(self, integration_id: str) -> Dict[str, Any]:
        """Get rate limiting statistics for an integration."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=1)
        recent = [ts for ts in self._requests.get(integration_id, []) if ts > window_start]

        return {
            "integration_id": integration_id,
            "requests_in_window": len(recent),
            "limit": self.get_limit(integration_id),
            "remaining": max(0, self.get_limit(integration_id) - len(recent)),
        }


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


# ============ Retry Configuration ============

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    retry_on_status: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry_on_errors: bool = True
    jitter: bool = True  # Add random jitter to prevent thundering herd

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a retry attempt (exponential backoff with jitter)."""
        import random
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add up to 25% jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0.1, delay)

    def should_retry_status(self, status_code: int) -> bool:
        """Check if a status code should trigger a retry."""
        return status_code in self.retry_on_status


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig()

# Per-integration retry configs (can be customized)
INTEGRATION_RETRY_CONFIGS: Dict[str, RetryConfig] = {
    # Stripe has specific rate limit behavior
    "stripe": RetryConfig(
        max_retries=3,
        base_delay=2.0,
        retry_on_status=[429, 500, 502, 503],
    ),
    # OpenAI often has 429s
    "openai": RetryConfig(
        max_retries=5,
        base_delay=1.0,
        max_delay=60.0,
        retry_on_status=[429, 500, 502, 503],
    ),
    # Discord rate limits need careful handling
    "discord": RetryConfig(
        max_retries=3,
        base_delay=1.0,
        retry_on_status=[429, 500, 502, 503, 504],
    ),
}


def get_retry_config(integration_id: str) -> RetryConfig:
    """Get retry configuration for an integration."""
    return INTEGRATION_RETRY_CONFIGS.get(integration_id, DEFAULT_RETRY_CONFIG)


class TemplateEngine:
    """
    Simple template engine for substituting {{variable}} placeholders.

    Supports:
    - {{auth.field}} - Authentication credentials
    - {{parameters.field}} - Action parameters
    - {{env.VARIABLE}} - Environment variables (optional)
    """

    PATTERN = re.compile(r'\{\{([^}]+)\}\}')

    @classmethod
    def substitute(
        cls,
        template: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Substitute all {{variable}} placeholders in a template.

        Args:
            template: String with {{}} placeholders
            context: Dictionary with values for substitution

        Returns:
            String with placeholders replaced
        """
        def replace(match):
            path = match.group(1).strip()
            value = cls._get_nested_value(context, path)
            if value is None:
                logger.warning(f"Template variable not found: {path}")
                return match.group(0)  # Keep original if not found
            return str(value)

        return cls.PATTERN.sub(replace, template)

    @classmethod
    def substitute_dict(
        cls,
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recursively substitute templates in a dictionary.

        Args:
            data: Dictionary that may contain template strings
            context: Values for substitution

        Returns:
            Dictionary with all templates substituted
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = cls.substitute(value, context)
            elif isinstance(value, dict):
                result[key] = cls.substitute_dict(value, context)
            elif isinstance(value, list):
                result[key] = [
                    cls.substitute(v, context) if isinstance(v, str)
                    else cls.substitute_dict(v, context) if isinstance(v, dict)
                    else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    @classmethod
    def _get_nested_value(cls, data: Dict[str, Any], path: str) -> Any:
        """
        Get a nested value from a dictionary using dot notation.

        Args:
            data: Dictionary to search
            path: Dot-separated path like "auth.api_key"

        Returns:
            Value at path or None if not found
        """
        parts = path.split('.')
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

            if current is None:
                return None

        return current


class HttpActionExecutor:
    """
    Executes HTTP-based actions from integration configs.

    Features:
    - Template substitution for URLs, headers, and body
    - Authentication header injection
    - Rate limiting per integration
    - Automatic retries with exponential backoff
    - Response mapping

    Usage:
        executor = HttpActionExecutor()
        result = await executor.execute(
            integration=discord_config,
            action=discord_config.actions['send_message'],
            credentials=credentials,
            parameters={'channel_id': '123', 'content': 'Hello!'}
        )
    """

    def __init__(
        self,
        timeout: int = 30,
        rate_limiter: Optional[RateLimiter] = None,
        retry_config: Optional[RetryConfig] = None,
        enable_rate_limiting: bool = True,
        enable_retries: bool = True,
    ):
        """
        Initialize executor.

        Args:
            timeout: Default request timeout in seconds
            rate_limiter: Rate limiter instance (uses global if not provided)
            retry_config: Default retry configuration
            enable_rate_limiting: Whether to enforce rate limits
            enable_retries: Whether to enable automatic retries
        """
        self.timeout = timeout
        self.template_engine = TemplateEngine()
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.default_retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_retries = enable_retries

    async def execute(
        self,
        integration: IntegrationConfig,
        action: ActionConfig,
        credentials: IntegrationCredentials,
        parameters: Dict[str, Any]
    ) -> ActionExecutionResult:
        """
        Execute an HTTP action with rate limiting and retries.

        Args:
            integration: Integration configuration
            action: Action configuration
            credentials: User's credentials for this integration
            parameters: Action parameters

        Returns:
            ActionExecutionResult with response data
        """
        start_time = datetime.utcnow()

        if not action.http:
            return ActionExecutionResult(
                success=False,
                error="Action is not HTTP-based",
                error_code="INVALID_ACTION_TYPE"
            )

        # Apply rate limiting
        if self.enable_rate_limiting:
            rate_limit = action.rate_limit
            acquired = await self.rate_limiter.wait_and_acquire(
                integration.id,
                rate_limit=rate_limit,
                max_wait=30.0
            )
            if not acquired:
                return ActionExecutionResult(
                    success=False,
                    error="Rate limit exceeded - too many requests",
                    error_code="RATE_LIMIT_EXCEEDED",
                    duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )

        # Get retry config for this integration
        retry_config = get_retry_config(integration.id) if self.enable_retries else None

        # Execute with retries
        return await self._execute_with_retries(
            integration=integration,
            action=action,
            credentials=credentials,
            parameters=parameters,
            start_time=start_time,
            retry_config=retry_config,
        )

    async def _execute_with_retries(
        self,
        integration: IntegrationConfig,
        action: ActionConfig,
        credentials: IntegrationCredentials,
        parameters: Dict[str, Any],
        start_time: datetime,
        retry_config: Optional[RetryConfig],
    ) -> ActionExecutionResult:
        """Execute request with automatic retries on failure."""
        http_config = action.http
        max_attempts = (retry_config.max_retries + 1) if retry_config else 1
        last_result: Optional[ActionExecutionResult] = None

        for attempt in range(max_attempts):
            if attempt > 0:
                delay = retry_config.get_delay(attempt - 1)
                logger.info(f"Retry attempt {attempt}/{retry_config.max_retries} for {integration.id}.{action.name} after {delay:.1f}s")
                await asyncio.sleep(delay)

            result = await self._execute_single(
                integration=integration,
                action=action,
                credentials=credentials,
                parameters=parameters,
                start_time=start_time,
            )

            last_result = result

            # Success - return immediately
            if result.success:
                if attempt > 0:
                    logger.info(f"Succeeded on retry attempt {attempt} for {integration.id}.{action.name}")
                return result

            # Check if we should retry
            if not retry_config:
                break

            # Check error type
            should_retry = False

            if result.error_code and result.error_code.startswith("HTTP_"):
                try:
                    status_code = int(result.error_code.split("_")[1])
                    should_retry = retry_config.should_retry_status(status_code)

                    # Special handling for 429 - check Retry-After header
                    if status_code == 429 and result.raw_response:
                        retry_after = result.raw_response.get("retry_after")
                        if retry_after and attempt < max_attempts - 1:
                            logger.info(f"Rate limited (429), waiting {retry_after}s")
                            await asyncio.sleep(min(float(retry_after), 60.0))
                            continue
                except (ValueError, IndexError):
                    pass

            elif result.error_code == "CONNECTION_ERROR" and retry_config.retry_on_errors:
                should_retry = True

            if not should_retry:
                break

        return last_result or ActionExecutionResult(
            success=False,
            error="Unknown error",
            error_code="UNKNOWN_ERROR",
            duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
        )

    async def _execute_single(
        self,
        integration: IntegrationConfig,
        action: ActionConfig,
        credentials: IntegrationCredentials,
        parameters: Dict[str, Any],
        start_time: datetime,
    ) -> ActionExecutionResult:
        """Execute a single HTTP request."""
        http_config = action.http

        # Build context for template substitution
        context = {
            'auth': credentials.data,
            'parameters': parameters,
            'integration': {'id': integration.id, 'name': integration.name},
        }

        try:
            # Build URL
            url = self.template_engine.substitute(http_config.url, context)

            # Build headers
            headers = self._build_headers(integration, credentials, http_config, context)

            # Build body
            body = None
            if http_config.body:
                body = self.template_engine.substitute_dict(http_config.body, context)

            # Build query params (filter out unresolved templates)
            query_params = None
            if http_config.query_params:
                substituted = self.template_engine.substitute_dict(http_config.query_params, context)
                # Remove params that still contain {{ }} (unresolved templates)
                query_params = {
                    k: v for k, v in substituted.items()
                    if not (isinstance(v, str) and '{{' in v)
                }
                # Set to None if empty
                if not query_params:
                    query_params = None

            logger.info(f"Executing HTTP action: {http_config.method} {url}")

            # SSRF protection: validate URL before making request
            from backend.shared.url_validator import validate_url
            validate_url(url)

            # Make request
            async with aiohttp.ClientSession() as session:
                request_kwargs = {
                    'method': http_config.method.value,
                    'url': url,
                    'headers': headers,
                    'timeout': aiohttp.ClientTimeout(total=self.timeout),
                }

                if body:
                    request_kwargs['json'] = body

                if query_params:
                    request_kwargs['params'] = query_params

                async with session.request(**request_kwargs) as response:
                    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                    # Check status
                    if response.status not in http_config.success_codes:
                        error_text = await response.text()
                        logger.error(f"HTTP action failed: {response.status} - {error_text}")

                        # Extract Retry-After header for rate limit responses
                        raw_response = {"status": response.status, "body": error_text[:500]}
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            raw_response["retry_after"] = retry_after

                        return ActionExecutionResult(
                            success=False,
                            error=f"HTTP {response.status}: {error_text[:200]}",
                            error_code=f"HTTP_{response.status}",
                            duration_ms=duration_ms,
                            raw_response=raw_response
                        )

                    # Parse response
                    response_data = await self._parse_response(response, http_config.response_type)

                    # Apply response mapping
                    mapped_data = self._apply_response_mapping(
                        response_data,
                        action.response
                    )

                    return ActionExecutionResult(
                        success=True,
                        data=mapped_data,
                        duration_ms=duration_ms,
                        raw_response=response_data if isinstance(response_data, dict) else {"text": str(response_data)}
                    )

        except aiohttp.ClientError as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"HTTP client error: {e}")
            return ActionExecutionResult(
                success=False,
                error=f"Connection error: {str(e)}",
                error_code="CONNECTION_ERROR",
                duration_ms=duration_ms
            )
        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.exception(f"HTTP action execution failed: {e}")
            return ActionExecutionResult(
                success=False,
                error=str(e),
                error_code="EXECUTION_ERROR",
                duration_ms=duration_ms
            )

    def _build_headers(
        self,
        integration: IntegrationConfig,
        credentials: IntegrationCredentials,
        http_config,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Build HTTP headers including authentication."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # Add auth header based on type
        auth = integration.auth
        if auth.type == AuthType.API_KEY:
            api_key = credentials.api_key
            if api_key:
                header_name = auth.header_name or 'Authorization'
                header_prefix = auth.header_prefix or 'Bearer'
                headers[header_name] = f"{header_prefix} {api_key}"

        elif auth.type == AuthType.BOT_TOKEN:
            bot_token = credentials.bot_token
            if bot_token:
                header_name = auth.header_name or 'Authorization'
                header_prefix = auth.header_prefix or 'Bot'
                headers[header_name] = f"{header_prefix} {bot_token}"

        elif auth.type == AuthType.BEARER:
            access_token = credentials.access_token
            if access_token:
                headers['Authorization'] = f"Bearer {access_token}"

        elif auth.type == AuthType.OAUTH2:
            access_token = credentials.access_token
            if access_token:
                headers['Authorization'] = f"Bearer {access_token}"

        # Add custom headers from config
        if http_config.headers:
            custom_headers = self.template_engine.substitute_dict(http_config.headers, context)
            headers.update(custom_headers)

        return headers

    async def _parse_response(
        self,
        response: aiohttp.ClientResponse,
        response_type: str
    ) -> Any:
        """Parse HTTP response based on expected type."""
        if response_type == 'json':
            try:
                return await response.json()
            except json.JSONDecodeError:
                return await response.text()
        elif response_type == 'text':
            return await response.text()
        elif response_type == 'binary':
            return await response.read()
        else:
            return await response.json()

    def _apply_response_mapping(
        self,
        response_data: Any,
        mapping
    ) -> Dict[str, Any]:
        """
        Apply response mapping to extract specific fields.

        Args:
            response_data: Raw response data
            mapping: ResponseMapping config

        Returns:
            Mapped data dictionary
        """
        if not mapping or not mapping.mappings:
            # Return raw data if no mapping specified
            if isinstance(response_data, dict):
                return response_data
            return {"result": response_data}

        result = {}
        for output_field, json_path in mapping.mappings.items():
            value = self._extract_json_path(response_data, json_path)
            result[output_field] = value

        return result

    def _extract_json_path(self, data: Any, path: str) -> Any:
        """
        Extract value using a simple JSONPath-like expression.

        Supports:
        - $.field - Root field
        - $.field.nested - Nested field
        - $.array[0] - Array index

        Args:
            data: Data to extract from
            path: JSONPath expression

        Returns:
            Extracted value or None
        """
        if not path.startswith('$'):
            path = '$.' + path

        # Remove $ prefix
        path = path[1:]
        if path.startswith('.'):
            path = path[1:]

        if not path:
            return data

        current = data
        parts = re.split(r'\.|\[|\]', path)
        parts = [p for p in parts if p]  # Remove empty strings

        for part in parts:
            if current is None:
                return None

            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index] if index < len(current) else None
                except ValueError:
                    return None
            else:
                return None

        return current


# ============ Test Connection Helper ============

async def test_connection(
    integration: IntegrationConfig,
    credentials: IntegrationCredentials
) -> ActionExecutionResult:
    """
    Test connection to an integration.

    Attempts to make a simple API call to verify credentials work.

    Args:
        integration: Integration config
        credentials: User credentials

    Returns:
        ActionExecutionResult indicating success/failure
    """
    executor = HttpActionExecutor(timeout=10)

    # Look for a test_connection action
    test_action = integration.get_action('test_connection')
    if test_action and test_action.http:
        return await executor.execute(
            integration=integration,
            action=test_action,
            credentials=credentials,
            parameters={}
        )

    # Fallback: Try the first available action with no required params
    for action_name, action in integration.actions.items():
        if action.http and all(not p.required for p in action.parameters):
            result = await executor.execute(
                integration=integration,
                action=action,
                credentials=credentials,
                parameters={}
            )
            return result

    # No suitable action found
    return ActionExecutionResult(
        success=True,  # Assume connected if we can't test
        data={"message": "No test action available, credentials stored"},
        duration_ms=0
    )
