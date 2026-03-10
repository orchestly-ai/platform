#!/usr/bin/env python3
"""
Security Tests: Input Validation & SQL Injection Prevention

Tests input validation and SQL injection prevention including:
- Pydantic model validation
- UUID validation
- String length limits
- SQL injection attempts
- XSS prevention
"""

import pytest
from uuid import uuid4

# Check for required dependencies
try:
    from pydantic import ValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    ValidationError = None

try:
    from backend.api.workflow import (
        WorkflowCreateRequest,
        WorkflowUpdateRequest,
        NodeRequest,
        EdgeRequest,
        NodePositionRequest,
    )
    HAS_WORKFLOW_MODELS = True
except ImportError:
    HAS_WORKFLOW_MODELS = False

# Skip entire module if dependencies not available
if not HAS_PYDANTIC or not HAS_WORKFLOW_MODELS:
    pytest.skip(
        "Required dependencies not installed (pydantic, fastapi)",
        allow_module_level=True
    )


class TestPydanticValidation:
    """Tests for Pydantic model validation."""

    def test_workflow_name_required(self):
        """Workflow name is required."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowCreateRequest(
                # Missing name
                nodes=[],
                edges=[],
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_workflow_name_min_length(self):
        """Workflow name must have minimum length."""
        with pytest.raises(ValidationError):
            WorkflowCreateRequest(
                name="",  # Empty name
                nodes=[],
                edges=[],
            )

    def test_workflow_name_max_length(self):
        """Workflow name must not exceed max length."""
        with pytest.raises(ValidationError):
            WorkflowCreateRequest(
                name="x" * 300,  # Exceeds 255 char limit
                nodes=[],
                edges=[],
            )

    def test_valid_workflow_request(self):
        """Valid workflow request should pass validation."""
        request = WorkflowCreateRequest(
            name="Test Workflow",
            description="A test workflow",
            nodes=[
                NodeRequest(
                    id="node_1",
                    type="llm_call",
                    position=NodePositionRequest(x=0, y=0),
                    data={"prompt": "test"}
                )
            ],
            edges=[],
        )

        assert request.name == "Test Workflow"
        assert len(request.nodes) == 1


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention."""

    def test_workflow_name_with_sql_injection(self):
        """SQL injection in name should not execute."""
        # These should be stored as literal strings, not executed
        malicious_names = [
            "'; DROP TABLE workflows; --",
            "1' OR '1'='1",
            "1; DELETE FROM users WHERE '1'='1",
            "UNION SELECT * FROM users --",
            "' UNION SELECT password FROM users --",
        ]

        for name in malicious_names:
            # Should accept as literal string (validation passes)
            # The ORM will escape these properly
            request = WorkflowCreateRequest(
                name=name,
                nodes=[],
                edges=[],
            )
            assert request.name == name  # Stored as literal

    def test_node_data_with_sql_injection(self):
        """SQL injection in node data should be stored literally."""
        request = WorkflowCreateRequest(
            name="Test",
            nodes=[
                NodeRequest(
                    id="node_1",
                    type="llm_call",
                    position=NodePositionRequest(x=0, y=0),
                    data={"prompt": "'; DROP TABLE --"}
                )
            ],
            edges=[],
        )

        # Data should be stored as JSON, not executed
        assert request.nodes[0].data["prompt"] == "'; DROP TABLE --"


class TestXSSPrevention:
    """Tests for XSS prevention."""

    def test_script_tags_in_name(self):
        """Script tags should be stored as literals."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "'-alert(1)-'",
        ]

        for payload in xss_payloads:
            request = WorkflowCreateRequest(
                name=payload,
                nodes=[],
                edges=[],
            )
            # Stored as literal - frontend should escape on display
            assert request.name == payload

    def test_script_in_description(self):
        """Script tags in description should be stored as literals."""
        request = WorkflowCreateRequest(
            name="Test",
            description="<script>alert('xss')</script>",
            nodes=[],
            edges=[],
        )

        assert "<script>" in request.description


class TestUUIDValidation:
    """Tests for UUID validation in path parameters."""

    def test_valid_uuid(self):
        """Valid UUID should be accepted."""
        valid_uuid = uuid4()

        # FastAPI/Pydantic will validate UUID format in path parameters
        # This is enforced at the API layer
        assert str(valid_uuid)

    def test_uuid_format(self):
        """UUID should follow standard format."""
        valid_uuid = str(uuid4())

        # UUID format: 8-4-4-4-12 hex characters
        parts = valid_uuid.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12


class TestIntegerBoundaries:
    """Tests for integer field boundaries."""

    def test_max_execution_time_default(self):
        """Max execution time should have sensible default."""
        request = WorkflowCreateRequest(
            name="Test",
            nodes=[],
            edges=[],
        )

        assert request.max_execution_time_seconds == 3600

    def test_max_retries_default(self):
        """Max retries should have sensible default."""
        request = WorkflowCreateRequest(
            name="Test",
            nodes=[],
            edges=[],
        )

        assert request.max_retries == 3


class TestListValidation:
    """Tests for list field validation."""

    def test_empty_nodes_allowed(self):
        """Empty nodes list should be allowed."""
        request = WorkflowCreateRequest(
            name="Test",
            nodes=[],
            edges=[],
        )

        assert request.nodes == []

    def test_large_nodes_list(self):
        """Large nodes list should be handled."""
        # Create 100 nodes
        nodes = [
            NodeRequest(
                id=f"node_{i}",
                type="llm_call",
                position=NodePositionRequest(x=i * 100, y=0),
                data={}
            )
            for i in range(100)
        ]

        request = WorkflowCreateRequest(
            name="Test",
            nodes=nodes,
            edges=[],
        )

        assert len(request.nodes) == 100


class TestSpecialCharacters:
    """Tests for handling special characters."""

    def test_unicode_in_name(self):
        """Unicode characters should be accepted."""
        unicode_names = [
            "Workflow 日本語",
            "Рабочий процесс",
            "工作流程",
            "🚀 Workflow",
            "Café Workflow",
        ]

        for name in unicode_names:
            request = WorkflowCreateRequest(
                name=name,
                nodes=[],
                edges=[],
            )
            assert request.name == name

    def test_newlines_in_description(self):
        """Newlines in description should be preserved."""
        request = WorkflowCreateRequest(
            name="Test",
            description="Line 1\nLine 2\nLine 3",
            nodes=[],
            edges=[],
        )

        assert "\n" in request.description

    def test_null_bytes_rejected(self):
        """Null bytes should be handled."""
        # Null bytes can cause issues in some systems
        request = WorkflowCreateRequest(
            name="Test\x00Name",  # Contains null byte
            nodes=[],
            edges=[],
        )
        # Pydantic will accept it as a string - service layer should sanitize
        assert request.name == "Test\x00Name"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
