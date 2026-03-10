"""
Unit Tests for WorkflowContext

Tests for context creation, propagation, and extraction from various sources.
"""

import pytest
from unittest.mock import MagicMock
from dataclasses import asdict

from backend.services.workflow_executor import WorkflowContext


class TestWorkflowContext:
    """Tests for WorkflowContext dataclass."""

    def test_default_values(self):
        """Test default context values."""
        ctx = WorkflowContext()

        assert ctx.organization_id == "default-org"
        assert ctx.user_id == "system"
        assert ctx.embedding_api_key is None
        assert ctx.llm_api_keys == {}
        assert ctx.variables == {}

    def test_custom_values(self):
        """Test context with custom values."""
        ctx = WorkflowContext(
            organization_id="org-123",
            user_id="user-456",
            embedding_api_key="sk-embed-xxx",
            llm_api_keys={"openai": "sk-openai-xxx", "anthropic": "sk-ant-xxx"},
            variables={"env": "production"}
        )

        assert ctx.organization_id == "org-123"
        assert ctx.user_id == "user-456"
        assert ctx.embedding_api_key == "sk-embed-xxx"
        assert ctx.llm_api_keys["openai"] == "sk-openai-xxx"
        assert ctx.variables["env"] == "production"

    def test_from_execution(self):
        """Test creating context from workflow execution object."""
        # Mock execution object
        execution = MagicMock()
        execution.organization_id = "exec-org"
        execution.triggered_by = "exec-user"
        execution.input_data = {"key": "value"}

        ctx = WorkflowContext.from_execution(execution)

        assert ctx.organization_id == "exec-org"
        assert ctx.user_id == "exec-user"
        assert ctx.variables == {"key": "value"}

    def test_from_execution_with_missing_fields(self):
        """Test creating context from execution with missing optional fields."""
        execution = MagicMock(spec=[])  # Empty spec means no attributes

        ctx = WorkflowContext.from_execution(execution)

        # Should use defaults
        assert ctx.organization_id == "default-org"
        assert ctx.user_id == "system"
        assert ctx.variables == {}

    def test_from_execution_with_none_input_data(self):
        """Test creating context when input_data is None."""
        execution = MagicMock()
        execution.organization_id = "org"
        execution.triggered_by = "user"
        execution.input_data = None

        ctx = WorkflowContext.from_execution(execution)

        assert ctx.variables == {}

    def test_from_request(self):
        """Test creating context from API request parameters."""
        ctx = WorkflowContext.from_request(
            organization_id="req-org",
            user_id="req-user",
            embedding_api_key="sk-embed",
            llm_api_keys={"openai": "sk-xxx"}
        )

        assert ctx.organization_id == "req-org"
        assert ctx.user_id == "req-user"
        assert ctx.embedding_api_key == "sk-embed"
        assert ctx.llm_api_keys == {"openai": "sk-xxx"}

    def test_from_request_minimal(self):
        """Test creating context with minimal request parameters."""
        ctx = WorkflowContext.from_request(
            organization_id="org",
            user_id="user"
        )

        assert ctx.organization_id == "org"
        assert ctx.user_id == "user"
        assert ctx.embedding_api_key is None
        assert ctx.llm_api_keys == {}

    def test_context_is_dataclass(self):
        """Test that context can be converted to dict."""
        ctx = WorkflowContext(
            organization_id="org",
            user_id="user"
        )

        data = asdict(ctx)

        assert isinstance(data, dict)
        assert data["organization_id"] == "org"
        assert data["user_id"] == "user"

    def test_context_llm_api_keys_isolation(self):
        """Test that llm_api_keys dict is isolated between instances."""
        ctx1 = WorkflowContext()
        ctx2 = WorkflowContext()

        ctx1.llm_api_keys["openai"] = "key1"

        # ctx2 should not be affected
        assert "openai" not in ctx2.llm_api_keys

    def test_context_variables_isolation(self):
        """Test that variables dict is isolated between instances."""
        ctx1 = WorkflowContext()
        ctx2 = WorkflowContext()

        ctx1.variables["key"] = "value"

        # ctx2 should not be affected
        assert "key" not in ctx2.variables
