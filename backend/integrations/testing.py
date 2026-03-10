"""
Integration Testing Framework

Provides utilities for testing integration YAML configs with mocked responses.
Supports mock API responses, request validation, and automated test generation.

Usage:
    from backend.integrations.testing import IntegrationTestRunner, MockResponse

    # Create test runner
    runner = IntegrationTestRunner('stripe')

    # Add mock responses
    runner.mock('list_customers', MockResponse(
        status=200,
        json={'data': [{'id': 'cus_123', 'email': 'test@example.com'}]}
    ))

    # Run tests
    results = await runner.run_all()
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock, patch, MagicMock

import yaml

from .schema import (
    IntegrationConfig,
    ActionConfig,
    IntegrationCredentials,
    ActionExecutionResult,
    AuthType,
)
from .registry import IntegrationRegistry
from .http_executor import HttpActionExecutor, TemplateEngine

logger = logging.getLogger(__name__)


# ============ Mock Response Types ============

@dataclass
class MockResponse:
    """Mock HTTP response for testing."""
    status: int = 200
    json: Optional[Dict[str, Any]] = None
    text: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    raise_error: Optional[Exception] = None
    delay_ms: int = 0  # Simulate latency

    async def read(self):
        """Return binary content."""
        if self.text:
            return self.text.encode()
        if self.json:
            return json.dumps(self.json).encode()
        return b''


@dataclass
class MockRequest:
    """Captured request for validation."""
    method: str
    url: str
    headers: Dict[str, str]
    body: Optional[Dict[str, Any]]
    params: Optional[Dict[str, str]]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TestResult:
    """Result of a single test case."""
    test_name: str
    action_name: str
    passed: bool
    duration_ms: float
    error: Optional[str] = None
    request: Optional[MockRequest] = None
    response: Optional[Dict[str, Any]] = None
    assertions_passed: int = 0
    assertions_failed: int = 0


@dataclass
class TestSuiteResult:
    """Result of running all tests for an integration."""
    integration_id: str
    total_tests: int
    passed: int
    failed: int
    duration_ms: float
    results: List[TestResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100


# ============ Mock HTTP Client ============

class MockHttpClient:
    """Mock HTTP client that returns configured responses."""

    def __init__(self):
        self.responses: Dict[str, List[MockResponse]] = {}  # url_pattern -> responses
        self.requests: List[MockRequest] = []
        self.default_response = MockResponse(status=200, json={'success': True})

    def add_response(self, url_pattern: str, response: MockResponse):
        """Add a mock response for a URL pattern."""
        if url_pattern not in self.responses:
            self.responses[url_pattern] = []
        self.responses[url_pattern].append(response)

    def get_response(self, url: str) -> MockResponse:
        """Get mock response for a URL."""
        for pattern, responses in self.responses.items():
            if re.search(pattern, url):
                if responses:
                    return responses.pop(0)
        return self.default_response

    def clear(self):
        """Clear all mocks and captured requests."""
        self.responses.clear()
        self.requests.clear()

    async def request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str] = None,
        json: Dict[str, Any] = None,
        params: Dict[str, str] = None,
        **kwargs
    ):
        """Simulate HTTP request."""
        # Capture request
        request = MockRequest(
            method=method,
            url=url,
            headers=headers or {},
            body=json,
            params=params,
        )
        self.requests.append(request)

        # Get mock response
        response = self.get_response(url)

        # Simulate delay
        if response.delay_ms > 0:
            await asyncio.sleep(response.delay_ms / 1000)

        # Simulate error
        if response.raise_error:
            raise response.raise_error

        # Create mock response object
        mock = AsyncMock()
        mock.status = response.status
        mock.headers = response.headers

        async def mock_json():
            return response.json or {}

        async def mock_text():
            return response.text or json.dumps(response.json) if response.json else ''

        mock.json = mock_json
        mock.text = mock_text
        mock.read = response.read

        return mock


# ============ Test Assertions ============

class TestAssertions:
    """Fluent assertion builder for test validation."""

    def __init__(self, result: ActionExecutionResult, request: Optional[MockRequest] = None):
        self.result = result
        self.request = request
        self.passed = 0
        self.failed = 0
        self.errors: List[str] = []

    def succeeded(self) -> 'TestAssertions':
        """Assert action succeeded."""
        if self.result.success:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"Expected success but got error: {self.result.error}")
        return self

    def failed_with(self, error_code: str) -> 'TestAssertions':
        """Assert action failed with specific error code."""
        if not self.result.success and self.result.error_code == error_code:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"Expected error_code={error_code} but got {self.result.error_code}")
        return self

    def has_data(self, key: str, expected: Any = None) -> 'TestAssertions':
        """Assert response data contains key with optional value check."""
        data = self.result.data or {}
        if key not in data:
            self.failed += 1
            self.errors.append(f"Expected data to contain key '{key}'")
        elif expected is not None and data[key] != expected:
            self.failed += 1
            self.errors.append(f"Expected data['{key}'] = {expected} but got {data[key]}")
        else:
            self.passed += 1
        return self

    def request_method(self, method: str) -> 'TestAssertions':
        """Assert request used specific method."""
        if not self.request:
            self.failed += 1
            self.errors.append("No request captured")
        elif self.request.method.upper() == method.upper():
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"Expected method {method} but got {self.request.method}")
        return self

    def request_url_contains(self, substring: str) -> 'TestAssertions':
        """Assert request URL contains substring."""
        if not self.request:
            self.failed += 1
            self.errors.append("No request captured")
        elif substring in self.request.url:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"Expected URL to contain '{substring}' but got {self.request.url}")
        return self

    def request_has_header(self, header: str, value: Optional[str] = None) -> 'TestAssertions':
        """Assert request has header with optional value check."""
        if not self.request:
            self.failed += 1
            self.errors.append("No request captured")
        elif header not in self.request.headers:
            self.failed += 1
            self.errors.append(f"Expected header '{header}' not found")
        elif value is not None and self.request.headers[header] != value:
            self.failed += 1
            self.errors.append(f"Expected header '{header}' = '{value}' but got '{self.request.headers[header]}'")
        else:
            self.passed += 1
        return self

    def request_body_has(self, key: str, value: Any = None) -> 'TestAssertions':
        """Assert request body contains key."""
        if not self.request or not self.request.body:
            self.failed += 1
            self.errors.append("No request body captured")
        elif key not in self.request.body:
            self.failed += 1
            self.errors.append(f"Expected body to contain key '{key}'")
        elif value is not None and self.request.body[key] != value:
            self.failed += 1
            self.errors.append(f"Expected body['{key}'] = {value} but got {self.request.body[key]}")
        else:
            self.passed += 1
        return self

    def duration_under(self, max_ms: float) -> 'TestAssertions':
        """Assert execution completed under time limit."""
        if self.result.duration_ms <= max_ms:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"Expected duration < {max_ms}ms but got {self.result.duration_ms}ms")
        return self


# ============ Test Runner ============

class IntegrationTestRunner:
    """
    Test runner for integration configs.

    Executes actions against mock HTTP responses and validates behavior.
    """

    def __init__(self, integration_id: str, registry: Optional[IntegrationRegistry] = None):
        """
        Initialize test runner.

        Args:
            integration_id: Integration ID to test
            registry: Integration registry (uses default if not provided)
        """
        self.integration_id = integration_id
        self.registry = registry or IntegrationRegistry()
        self.registry.load_all()

        self.integration = self.registry.get(integration_id)
        if not self.integration:
            raise ValueError(f"Integration not found: {integration_id}")

        self.mock_client = MockHttpClient()
        self.test_cases: List[Tuple[str, str, MockResponse, Dict[str, Any], Callable[[TestAssertions], None]]] = []

        # Default test credentials
        self.credentials = IntegrationCredentials(
            integration_id=integration_id,
            auth_type=self.integration.auth.type,
            data={'api_key': 'test_api_key_12345', 'bot_token': 'test_bot_token'}
        )

    def set_credentials(self, credentials: Dict[str, Any]):
        """Set test credentials."""
        self.credentials = IntegrationCredentials(
            integration_id=self.integration_id,
            auth_type=self.integration.auth.type,
            data=credentials
        )

    def mock(
        self,
        action_name: str,
        response: MockResponse,
        parameters: Optional[Dict[str, Any]] = None,
        assertions: Optional[Callable[[TestAssertions], None]] = None
    ) -> 'IntegrationTestRunner':
        """
        Add a mock response for an action.

        Args:
            action_name: Action to mock
            response: Mock response to return
            parameters: Action parameters for this test
            assertions: Assertion function to validate

        Returns:
            Self for chaining
        """
        action = self.integration.get_action(action_name)
        if not action:
            raise ValueError(f"Action not found: {action_name}")

        if not action.http:
            raise ValueError(f"Action is not HTTP-based: {action_name}")

        # Extract URL pattern from action config
        url_pattern = re.escape(action.http.url).replace(r'\{\{', '.*').replace(r'\}\}', '.*')

        self.mock_client.add_response(url_pattern, response)
        self.test_cases.append((
            f"test_{action_name}",
            action_name,
            response,
            parameters or {},
            assertions or (lambda a: a.succeeded())
        ))

        return self

    async def run_action(
        self,
        action_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Tuple[ActionExecutionResult, Optional[MockRequest]]:
        """
        Run a single action with mocked HTTP.

        Args:
            action_name: Action to execute
            parameters: Action parameters

        Returns:
            Tuple of (result, captured_request)
        """
        action = self.integration.get_action(action_name)
        if not action:
            return ActionExecutionResult(
                success=False,
                error=f"Action not found: {action_name}",
                error_code="ACTION_NOT_FOUND"
            ), None

        # Clear previous requests
        self.mock_client.requests.clear()

        # Create executor with mocked session
        executor = HttpActionExecutor(timeout=10, enable_rate_limiting=False, enable_retries=False)

        # Patch aiohttp.ClientSession
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.request = AsyncMock(side_effect=self._mock_request_handler)
            mock_session_class.return_value = mock_session

            result = await executor.execute(
                integration=self.integration,
                action=action,
                credentials=self.credentials,
                parameters=parameters or {}
            )

        captured_request = self.mock_client.requests[-1] if self.mock_client.requests else None
        return result, captured_request

    async def _mock_request_handler(self, **kwargs):
        """Handle mocked HTTP request."""
        return await self.mock_client.request(
            method=kwargs.get('method', 'GET'),
            url=kwargs.get('url', ''),
            headers=kwargs.get('headers', {}),
            json=kwargs.get('json'),
            params=kwargs.get('params'),
        )

    async def run_all(self) -> TestSuiteResult:
        """
        Run all configured test cases.

        Returns:
            TestSuiteResult with all test outcomes
        """
        start_time = datetime.utcnow()
        results: List[TestResult] = []

        for test_name, action_name, response, parameters, assertions_fn in self.test_cases:
            # Reset mock for this test
            action = self.integration.get_action(action_name)
            if action and action.http:
                url_pattern = re.escape(action.http.url).replace(r'\{\{', '.*').replace(r'\}\}', '.*')
                self.mock_client.add_response(url_pattern, response)

            test_start = datetime.utcnow()

            try:
                result, request = await self.run_action(action_name, parameters)
                test_duration = (datetime.utcnow() - test_start).total_seconds() * 1000

                # Run assertions
                assertions = TestAssertions(result, request)
                assertions_fn(assertions)

                test_result = TestResult(
                    test_name=test_name,
                    action_name=action_name,
                    passed=assertions.failed == 0,
                    duration_ms=test_duration,
                    error='; '.join(assertions.errors) if assertions.errors else None,
                    request=request,
                    response=result.data,
                    assertions_passed=assertions.passed,
                    assertions_failed=assertions.failed,
                )

            except Exception as e:
                test_duration = (datetime.utcnow() - test_start).total_seconds() * 1000
                test_result = TestResult(
                    test_name=test_name,
                    action_name=action_name,
                    passed=False,
                    duration_ms=test_duration,
                    error=str(e),
                )

            results.append(test_result)

        total_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        passed = sum(1 for r in results if r.passed)

        return TestSuiteResult(
            integration_id=self.integration_id,
            total_tests=len(results),
            passed=passed,
            failed=len(results) - passed,
            duration_ms=total_duration,
            results=results,
        )

    def generate_test_file(self, output_path: Optional[Path] = None) -> str:
        """
        Generate a pytest test file for this integration.

        Args:
            output_path: Optional path to write file

        Returns:
            Generated test file content
        """
        lines = [
            '"""',
            f'Auto-generated tests for {self.integration.display_name or self.integration.name}',
            f'Integration ID: {self.integration_id}',
            '"""',
            '',
            'import pytest',
            'from backend.integrations.testing import IntegrationTestRunner, MockResponse',
            '',
            '',
            f'class Test{self.integration_id.title().replace("_", "")}Integration:',
            f'    """Tests for {self.integration.display_name or self.integration.name}"""',
            '',
            '    @pytest.fixture',
            '    def runner(self):',
            f'        return IntegrationTestRunner("{self.integration_id}")',
            '',
        ]

        # Generate test for each action
        for action_name, action in self.integration.actions.items():
            if not action.http:
                continue

            method = action.http.method.value
            test_name = f'test_{action_name}'

            lines.extend([
                '    @pytest.mark.asyncio',
                f'    async def {test_name}(self, runner):',
                f'        """Test {action.display_name or action_name}"""',
                '        runner.mock(',
                f'            "{action_name}",',
                '            MockResponse(status=200, json={"success": True}),',
                '        )',
                '',
                f'        result, request = await runner.run_action("{action_name}")',
                '',
                '        assert result.success',
                f'        assert request.method == "{method}"',
                '',
            ])

        content = '\n'.join(lines)

        if output_path:
            output_path.write_text(content)
            logger.info(f"Generated test file: {output_path}")

        return content


# ============ Helper Functions ============

async def run_integration_tests(integration_id: str, verbose: bool = True) -> TestSuiteResult:
    """
    Run basic tests for an integration.

    Automatically creates test cases for each action with mock success responses.

    Args:
        integration_id: Integration to test
        verbose: Print results to console

    Returns:
        TestSuiteResult
    """
    runner = IntegrationTestRunner(integration_id)

    # Add mock for each action
    for action_name, action in runner.integration.actions.items():
        if not action.http:
            continue

        # Generate default parameters for required fields
        params = {}
        for param in action.parameters:
            if param.required:
                if param.default is not None:
                    params[param.name] = param.default
                elif param.type.value == 'string':
                    params[param.name] = f'test_{param.name}'
                elif param.type.value in ('number', 'integer'):
                    params[param.name] = 1
                elif param.type.value == 'boolean':
                    params[param.name] = True

        runner.mock(
            action_name,
            MockResponse(status=200, json={'success': True, 'action': action_name}),
            parameters=params,
        )

    results = await runner.run_all()

    if verbose:
        print(f"\n{'='*60}")
        print(f"Test Results: {runner.integration.display_name or integration_id}")
        print(f"{'='*60}")
        print(f"Total: {results.total_tests} | Passed: {results.passed} | Failed: {results.failed}")
        print(f"Success Rate: {results.success_rate:.1f}%")
        print(f"Duration: {results.duration_ms:.1f}ms")
        print()

        for result in results.results:
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {result.test_name} ({result.duration_ms:.1f}ms)")
            if result.error:
                print(f"         Error: {result.error}")

        print()

    return results


def generate_all_test_files(output_dir: Path):
    """
    Generate pytest files for all integrations.

    Args:
        output_dir: Directory to write test files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    registry = IntegrationRegistry()
    registry.load_all()

    for integration in registry.list_all():
        try:
            runner = IntegrationTestRunner(integration.id, registry)
            filename = f"test_{integration.id}.py"
            runner.generate_test_file(output_dir / filename)
            print(f"Generated: {filename}")
        except Exception as e:
            print(f"Failed to generate tests for {integration.id}: {e}")
