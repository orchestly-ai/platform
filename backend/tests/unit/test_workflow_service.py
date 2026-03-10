"""
Unit Tests for Workflow Execution Engine

Tests for DAG execution, topological sorting, node execution, and cost tracking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4, UUID
from enum import Enum

from backend.shared.workflow_service import (
    WorkflowExecutionEngine, strict_json_serialize, get_workflow_service
)
from backend.shared.workflow_models import (
    WorkflowNode, WorkflowEdge, Workflow, WorkflowExecution,
    NodeType, ExecutionStatus, WorkflowStatus
)


class TestJSONSerializer:
    """Tests for strict_json_serialize function."""

    def test_serialize_primitives(self):
        """Test serialization of basic types."""
        assert strict_json_serialize(None) is None
        assert strict_json_serialize("hello") == "hello"
        assert strict_json_serialize(42) == 42
        assert strict_json_serialize(3.14) == 3.14
        assert strict_json_serialize(True) is True

    def test_serialize_datetime(self):
        """Test datetime serialization."""
        dt = datetime(2025, 12, 26, 12, 0, 0)
        result = strict_json_serialize(dt)
        assert "2025-12-26" in result

    def test_serialize_uuid(self):
        """Test UUID serialization."""
        uid = uuid4()
        result = strict_json_serialize(uid)
        assert result == str(uid)

    def test_serialize_enum(self):
        """Test enum serialization."""
        result = strict_json_serialize(NodeType.AGENT_LLM)
        assert result == "agent_llm"

    def test_serialize_list(self):
        """Test list serialization."""
        result = strict_json_serialize([1, "two", 3.0])
        assert result == [1, "two", 3.0]

    def test_serialize_dict(self):
        """Test dict serialization."""
        data = {"key": "value", "num": 42}
        result = strict_json_serialize(data)
        assert result == {"key": "value", "num": 42}

    def test_serialize_nested(self):
        """Test nested structure serialization."""
        data = {
            "id": uuid4(),
            "items": [1, 2, {"nested": "value"}],
            "timestamp": datetime.utcnow()
        }
        result = strict_json_serialize(data)

        assert isinstance(result["id"], str)
        assert result["items"] == [1, 2, {"nested": "value"}]
        assert isinstance(result["timestamp"], str)

    def test_serialize_circular_reference(self):
        """Test handling of circular references."""
        data = {"key": "value"}
        data["self"] = data  # Circular reference

        result = strict_json_serialize(data)

        assert "Circular Reference" in str(result["self"])

    def test_serialize_max_depth(self):
        """Test max depth protection."""
        # Create deeply nested structure
        data = {"level": 0}
        current = data
        for i in range(60):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        result = strict_json_serialize(data, max_depth=50)

        # Should not throw, just truncate
        assert result is not None


class TestTopologicalSort:
    """Tests for dependency resolution."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def simple_nodes(self):
        """Create simple linear workflow nodes."""
        return [
            WorkflowNode(id="node1", type=NodeType.DATA_INPUT, position={"x": 0, "y": 0}, data={}),
            WorkflowNode(id="node2", type=NodeType.AGENT_LLM, position={"x": 100, "y": 0}, data={}),
            WorkflowNode(id="node3", type=NodeType.DATA_OUTPUT, position={"x": 200, "y": 0}, data={}),
        ]

    @pytest.fixture
    def simple_edges(self):
        """Create edges for linear workflow."""
        return [
            WorkflowEdge(id="e1", source="node1", target="node2"),
            WorkflowEdge(id="e2", source="node2", target="node3"),
        ]

    def test_build_dependency_graph(self, engine, simple_nodes, simple_edges):
        """Test dependency graph construction."""
        deps = engine._build_dependency_graph(simple_nodes, simple_edges)

        assert deps["node1"] == []  # No dependencies
        assert deps["node2"] == ["node1"]  # Depends on node1
        assert deps["node3"] == ["node2"]  # Depends on node2

    def test_topological_sort_linear(self, engine, simple_nodes, simple_edges):
        """Test topological sort for linear workflow."""
        deps = engine._build_dependency_graph(simple_nodes, simple_edges)
        order = engine._topological_sort(simple_nodes, deps)

        assert order.index("node1") < order.index("node2")
        assert order.index("node2") < order.index("node3")

    def test_topological_sort_parallel(self, engine):
        """Test topological sort with parallel nodes."""
        nodes = [
            WorkflowNode(id="start", type=NodeType.DATA_INPUT, position={"x": 0, "y": 0}, data={}),
            WorkflowNode(id="branch1", type=NodeType.AGENT_LLM, position={"x": 100, "y": 0}, data={}),
            WorkflowNode(id="branch2", type=NodeType.AGENT_LLM, position={"x": 100, "y": 100}, data={}),
            WorkflowNode(id="merge", type=NodeType.DATA_MERGE, position={"x": 200, "y": 50}, data={}),
        ]

        edges = [
            WorkflowEdge(id="e1", source="start", target="branch1"),
            WorkflowEdge(id="e2", source="start", target="branch2"),
            WorkflowEdge(id="e3", source="branch1", target="merge"),
            WorkflowEdge(id="e4", source="branch2", target="merge"),
        ]

        deps = engine._build_dependency_graph(nodes, edges)
        order = engine._topological_sort(nodes, deps)

        # start must come first
        assert order[0] == "start"
        # merge must come last
        assert order[-1] == "merge"
        # branch1 and branch2 can be in any order but must be before merge
        assert order.index("branch1") > order.index("start")
        assert order.index("branch2") > order.index("start")

    def test_topological_sort_circular_detection(self, engine):
        """Test detection of circular dependencies."""
        nodes = [
            WorkflowNode(id="node1", type=NodeType.AGENT_LLM, position={"x": 0, "y": 0}, data={}),
            WorkflowNode(id="node2", type=NodeType.AGENT_LLM, position={"x": 100, "y": 0}, data={}),
        ]

        # Circular dependency: node1 -> node2 -> node1
        edges = [
            WorkflowEdge(id="e1", source="node1", target="node2"),
            WorkflowEdge(id="e2", source="node2", target="node1"),
        ]

        deps = engine._build_dependency_graph(nodes, edges)

        with pytest.raises(ValueError, match="circular dependencies"):
            engine._topological_sort(nodes, deps)


class TestNodeExecution:
    """Tests for individual node execution."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_workflow(self):
        return Workflow(
            workflow_id=uuid4(),
            organization_id="org-123",
            name="Test Workflow",
            description="Test workflow description",
            status=WorkflowStatus.ACTIVE,
            version=1,
            nodes=[],
            edges=[]
        )

    @pytest.fixture
    def mock_execution(self):
        return WorkflowExecution(
            execution_id=uuid4(),
            workflow_id=uuid4(),
            workflow_version=1,
            organization_id="org-123",
            status=ExecutionStatus.RUNNING,
            triggered_by="test",
            trigger_source="manual",
            input_data={"test": "data"},
            node_states={}
        )

    @pytest.mark.asyncio
    async def test_execute_data_input_node(self, engine, mock_workflow, mock_execution, mock_db):
        """Test data input node execution."""
        node = WorkflowNode(
            id="input_1",
            type=NodeType.DATA_INPUT,
            position={"x": 0, "y": 0},
            data={}
        )

        result = await engine._execute_node(
            node,
            {"input": {"value": 42}},
            mock_workflow,
            mock_execution,
            mock_db
        )

        assert result == {"value": 42}

    @pytest.mark.asyncio
    async def test_execute_data_output_node(self, engine, mock_workflow, mock_execution, mock_db):
        """Test data output node execution."""
        node = WorkflowNode(
            id="output_1",
            type=NodeType.DATA_OUTPUT,
            position={"x": 0, "y": 0},
            data={}
        )

        result = await engine._execute_node(
            node,
            {"node1": {"result": "data"}},
            mock_workflow,
            mock_execution,
            mock_db
        )

        assert result["status"] == "output_complete"
        assert result["node_id"] == "output_1"

    @pytest.mark.asyncio
    async def test_execute_transform_node(self, engine, mock_workflow, mock_execution, mock_db):
        """Test data transform node execution."""
        node = WorkflowNode(
            id="transform_1",
            type=NodeType.DATA_TRANSFORM,
            position={"x": 0, "y": 0},
            data={"code": "x = 1 + 1"}
        )

        result = await engine._execute_transform_node(node, {"input": "test"})

        assert result["transformed"] is True
        assert "inputs" in result

    @pytest.mark.asyncio
    async def test_execute_if_node(self, engine, mock_workflow, mock_execution, mock_db):
        """Test conditional if node execution."""
        node = WorkflowNode(
            id="if_1",
            type=NodeType.CONTROL_IF,
            position={"x": 0, "y": 0},
            data={"condition": "x > 5"}
        )

        result = await engine._execute_if_node(node, {"x": 10})

        assert "condition_met" in result
        assert "branch" in result

    @pytest.mark.asyncio
    async def test_execute_http_node(self, engine, mock_workflow, mock_execution, mock_db):
        """Test HTTP request node execution."""
        node = WorkflowNode(
            id="http_1",
            type=NodeType.INTEGRATION_HTTP,
            position={"x": 0, "y": 0},
            data={"url": "https://api.example.com/data", "method": "GET"}
        )

        result = await engine._execute_http_node(node, {})

        assert result["status"] == 200
        assert "body" in result

    @pytest.mark.asyncio
    async def test_execute_merge_node(self, engine, mock_workflow, mock_execution, mock_db):
        """Test data merge node execution."""
        node = WorkflowNode(
            id="merge_1",
            type=NodeType.DATA_MERGE,
            position={"x": 0, "y": 0},
            data={}
        )

        inputs = {
            "branch1": {"result1": "value1"},
            "branch2": {"result2": "value2"}
        }

        result = await engine._execute_node(
            node,
            inputs,
            mock_workflow,
            mock_execution,
            mock_db
        )

        assert result["result1"] == "value1"
        assert result["result2"] == "value2"


class TestPromptFormatting:
    """Tests for prompt template formatting."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    def test_format_prompt_simple(self, engine):
        """Test simple variable substitution using double braces."""
        template = "Hello {{name}}, your order is {{order_id}}"
        inputs = {"name": "John", "order_id": "12345"}

        result = engine._format_prompt(template, inputs)

        assert result == "Hello John, your order is 12345"

    def test_format_prompt_missing_var(self, engine):
        """Test handling of missing variables."""
        template = "Hello {{name}}, value is {{missing}}"
        inputs = {"name": "John"}

        result = engine._format_prompt(template, inputs)

        # Missing variable stays as placeholder (with double braces)
        assert "{{missing}}" in result
        assert "John" in result


class TestCostCalculation:
    """Tests for LLM cost calculation."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    def test_calculate_gpt4_cost(self, engine):
        """Test GPT-4 cost calculation."""
        tokens = {"input": 1000, "output": 500, "total": 1500}
        cost = engine._calculate_llm_cost("gpt-4", tokens)

        # GPT-4 is $0.03 per 1K tokens
        expected = (1500 / 1000) * 0.03
        assert cost == expected

    def test_calculate_gpt35_cost(self, engine):
        """Test GPT-3.5-Turbo cost calculation."""
        tokens = {"input": 1000, "output": 500, "total": 1500}
        cost = engine._calculate_llm_cost("gpt-3.5-turbo", tokens)

        # GPT-3.5 is $0.002 per 1K tokens
        expected = (1500 / 1000) * 0.002
        assert cost == expected

    def test_calculate_claude_cost(self, engine):
        """Test Claude cost calculation."""
        tokens = {"input": 1000, "output": 500, "total": 1500}
        cost = engine._calculate_llm_cost("claude-3-sonnet", tokens)

        # Claude Sonnet is $0.015 per 1K tokens
        expected = (1500 / 1000) * 0.015
        assert cost == expected

    def test_calculate_unknown_model_cost(self, engine):
        """Test cost calculation for unknown model."""
        tokens = {"input": 1000, "output": 500, "total": 1500}
        cost = engine._calculate_llm_cost("unknown-model", tokens)

        # Default is $0.01 per 1K tokens
        expected = (1500 / 1000) * 0.01
        assert cost == expected


class TestWorkflowExecution:
    """Tests for full workflow execution."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_execute_simple_workflow(self, engine, mock_db):
        """Test execution of simple linear workflow."""
        workflow_id = uuid4()

        # Create mock workflow model
        mock_model = MagicMock()
        mock_model.workflow_id = workflow_id
        mock_model.organization_id = "org-123"
        mock_model.name = "Test Workflow"
        mock_model.description = "Test"
        mock_model.status = "active"
        mock_model.version = 1
        mock_model.nodes = [
            {"id": "input_1", "type": "data_input", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "output_1", "type": "data_output", "position": {"x": 100, "y": 0}, "data": {}},
        ]
        mock_model.edges = [
            {"id": "e1", "source": "input_1", "target": "output_1"}
        ]
        mock_model.max_execution_time_seconds = 300
        mock_model.retry_on_failure = False
        mock_model.max_retries = 0
        mock_model.variables = {}
        mock_model.environment = "development"
        mock_model.total_executions = 0
        mock_model.successful_executions = 0
        mock_model.failed_executions = 0
        mock_model.avg_execution_time_seconds = None
        mock_model.total_cost = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Execute workflow
        execution = await engine.execute_workflow(
            workflow_id,
            input_data={"test": "data"},
            triggered_by="test-user",
            db=mock_db
        )

        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.workflow_id == workflow_id


class TestGlobalWorkflowService:
    """Tests for global service instance."""

    def test_get_workflow_service_singleton(self):
        """Test that get_workflow_service returns same instance."""
        service1 = get_workflow_service()
        service2 = get_workflow_service()

        assert service1 is service2


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
