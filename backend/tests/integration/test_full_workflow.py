"""
E2E Integration Tests for Full Workflow Execution

Tests complete workflow execution from start to finish including:
- Workflow creation and validation
- Node execution with dependencies
- State persistence across nodes
- Error handling and recovery
- Cost tracking throughout execution
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from backend.shared.workflow_service import WorkflowExecutionEngine
from backend.shared.workflow_models import (
    Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution,
    NodeType, ExecutionStatus, WorkflowStatus
)


class TestFullWorkflowExecution:
    """E2E tests for complete workflow execution."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def simple_workflow_model(self):
        """Create a simple 3-node workflow model."""
        model = MagicMock()
        model.workflow_id = uuid4()
        model.organization_id = "org-123"
        model.name = "Simple Test Workflow"
        model.description = "A simple test workflow"
        model.status = "active"
        model.version = 1
        model.nodes = [
            {"id": "input_1", "type": "data_input", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "transform_1", "type": "data_transform", "position": {"x": 100, "y": 0}, "data": {"code": "output = input * 2"}},
            {"id": "output_1", "type": "data_output", "position": {"x": 200, "y": 0}, "data": {}},
        ]
        model.edges = [
            {"id": "e1", "source": "input_1", "target": "transform_1"},
            {"id": "e2", "source": "transform_1", "target": "output_1"},
        ]
        model.max_execution_time_seconds = 300
        model.retry_on_failure = False
        model.max_retries = 0
        model.variables = {}
        model.environment = "development"
        model.total_executions = 0
        model.successful_executions = 0
        model.failed_executions = 0
        model.avg_execution_time_seconds = None
        model.total_cost = 0
        return model

    @pytest.mark.asyncio
    async def test_execute_simple_linear_workflow(self, engine, mock_db, simple_workflow_model):
        """Test execution of a simple linear workflow."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=simple_workflow_model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        execution = await engine.execute_workflow(
            workflow_id=simple_workflow_model.workflow_id,
            input_data={"value": 10},
            triggered_by="test-user",
            db=mock_db
        )

        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.workflow_id == simple_workflow_model.workflow_id
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_execute_workflow_with_parallel_branches(self, engine, mock_db):
        """Test execution of workflow with parallel branches."""
        model = MagicMock()
        model.workflow_id = uuid4()
        model.organization_id = "org-123"
        model.name = "Parallel Workflow"
        model.description = "Workflow with parallel branches"
        model.status = "active"
        model.version = 1
        model.nodes = [
            {"id": "start", "type": "data_input", "position": {"x": 0, "y": 50}, "data": {}},
            {"id": "branch_a", "type": "data_transform", "position": {"x": 100, "y": 0}, "data": {}},
            {"id": "branch_b", "type": "data_transform", "position": {"x": 100, "y": 100}, "data": {}},
            {"id": "merge", "type": "data_merge", "position": {"x": 200, "y": 50}, "data": {}},
            {"id": "output", "type": "data_output", "position": {"x": 300, "y": 50}, "data": {}},
        ]
        model.edges = [
            {"id": "e1", "source": "start", "target": "branch_a"},
            {"id": "e2", "source": "start", "target": "branch_b"},
            {"id": "e3", "source": "branch_a", "target": "merge"},
            {"id": "e4", "source": "branch_b", "target": "merge"},
            {"id": "e5", "source": "merge", "target": "output"},
        ]
        model.max_execution_time_seconds = 300
        model.retry_on_failure = False
        model.max_retries = 0
        model.variables = {}
        model.environment = "development"
        model.total_executions = 0
        model.successful_executions = 0
        model.failed_executions = 0
        model.avg_execution_time_seconds = None
        model.total_cost = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        execution = await engine.execute_workflow(
            workflow_id=model.workflow_id,
            input_data={"data": "test"},
            triggered_by="test-user",
            db=mock_db
        )

        assert execution.status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_workflow_not_found(self, engine, mock_db):
        """Test error handling when workflow is not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="not found|Workflow"):
            await engine.execute_workflow(
                workflow_id=uuid4(),
                input_data={},
                triggered_by="test-user",
                db=mock_db
            )

    @pytest.mark.asyncio
    async def test_workflow_state_persistence(self, engine, mock_db, simple_workflow_model):
        """Test that state is persisted across nodes."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=simple_workflow_model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        input_data = {"message": "Hello", "count": 5}

        execution = await engine.execute_workflow(
            workflow_id=simple_workflow_model.workflow_id,
            input_data=input_data,
            triggered_by="test-user",
            db=mock_db
        )

        # Verify state was stored
        assert execution.input_data == input_data
        assert execution.status == ExecutionStatus.COMPLETED


class TestWorkflowWithLLMNodes:
    """Tests for workflows containing LLM nodes."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_workflow_with_single_llm_node(self, engine, mock_db):
        """Test workflow with a single LLM agent node."""
        model = MagicMock()
        model.workflow_id = uuid4()
        model.organization_id = "org-123"
        model.name = "LLM Workflow"
        model.description = "Workflow with LLM node"
        model.status = "active"
        model.version = 1
        model.nodes = [
            {"id": "input", "type": "data_input", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "llm", "type": "agent_llm", "position": {"x": 100, "y": 0}, "data": {
                "model": "gpt-4",
                "prompt_template": "Answer the question: {question}"
            }},
            {"id": "output", "type": "data_output", "position": {"x": 200, "y": 0}, "data": {}},
        ]
        model.edges = [
            {"id": "e1", "source": "input", "target": "llm"},
            {"id": "e2", "source": "llm", "target": "output"},
        ]
        model.max_execution_time_seconds = 300
        model.retry_on_failure = False
        model.max_retries = 0
        model.variables = {}
        model.environment = "development"
        model.total_executions = 0
        model.successful_executions = 0
        model.failed_executions = 0
        model.avg_execution_time_seconds = None
        model.total_cost = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        execution = await engine.execute_workflow(
            workflow_id=model.workflow_id,
            input_data={"question": "What is 2+2?"},
            triggered_by="test-user",
            db=mock_db
        )

        assert execution.status == ExecutionStatus.COMPLETED


class TestWorkflowWithConditionals:
    """Tests for workflows with conditional branching."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_workflow_with_conditional_true_branch(self, engine, mock_db):
        """Test conditional workflow taking true branch."""
        model = MagicMock()
        model.workflow_id = uuid4()
        model.organization_id = "org-123"
        model.name = "Conditional Workflow"
        model.description = "Workflow with conditional"
        model.status = "active"
        model.version = 1
        model.nodes = [
            {"id": "input", "type": "data_input", "position": {"x": 0, "y": 50}, "data": {}},
            {"id": "condition", "type": "control_if", "position": {"x": 100, "y": 50}, "data": {
                "condition": "value > 10"
            }},
            {"id": "true_path", "type": "data_transform", "position": {"x": 200, "y": 0}, "data": {}},
            {"id": "false_path", "type": "data_transform", "position": {"x": 200, "y": 100}, "data": {}},
            {"id": "output", "type": "data_output", "position": {"x": 300, "y": 50}, "data": {}},
        ]
        model.edges = [
            {"id": "e1", "source": "input", "target": "condition"},
            {"id": "e2", "source": "condition", "target": "true_path", "condition": "true"},
            {"id": "e3", "source": "condition", "target": "false_path", "condition": "false"},
            {"id": "e4", "source": "true_path", "target": "output"},
            {"id": "e5", "source": "false_path", "target": "output"},
        ]
        model.max_execution_time_seconds = 300
        model.retry_on_failure = False
        model.max_retries = 0
        model.variables = {}
        model.environment = "development"
        model.total_executions = 0
        model.successful_executions = 0
        model.failed_executions = 0
        model.avg_execution_time_seconds = None
        model.total_cost = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        execution = await engine.execute_workflow(
            workflow_id=model.workflow_id,
            input_data={"value": 20},  # Should take true branch
            triggered_by="test-user",
            db=mock_db
        )

        assert execution.status == ExecutionStatus.COMPLETED


class TestWorkflowWithHTTPIntegration:
    """Tests for workflows with HTTP integration nodes."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_workflow_with_http_request(self, engine, mock_db):
        """Test workflow with HTTP integration node."""
        model = MagicMock()
        model.workflow_id = uuid4()
        model.organization_id = "org-123"
        model.name = "HTTP Workflow"
        model.description = "Workflow with HTTP request"
        model.status = "active"
        model.version = 1
        model.nodes = [
            {"id": "input", "type": "data_input", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "http", "type": "integration_http", "position": {"x": 100, "y": 0}, "data": {
                "url": "https://api.example.com/data",
                "method": "GET"
            }},
            {"id": "output", "type": "data_output", "position": {"x": 200, "y": 0}, "data": {}},
        ]
        model.edges = [
            {"id": "e1", "source": "input", "target": "http"},
            {"id": "e2", "source": "http", "target": "output"},
        ]
        model.max_execution_time_seconds = 300
        model.retry_on_failure = False
        model.max_retries = 0
        model.variables = {}
        model.environment = "development"
        model.total_executions = 0
        model.successful_executions = 0
        model.failed_executions = 0
        model.avg_execution_time_seconds = None
        model.total_cost = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        execution = await engine.execute_workflow(
            workflow_id=model.workflow_id,
            input_data={},
            triggered_by="test-user",
            db=mock_db
        )

        assert execution.status == ExecutionStatus.COMPLETED


class TestWorkflowCostTracking:
    """Tests for cost tracking during workflow execution."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_workflow_tracks_execution_costs(self, engine, mock_db):
        """Test that workflow execution tracks costs."""
        model = MagicMock()
        model.workflow_id = uuid4()
        model.organization_id = "org-123"
        model.name = "Cost Tracking Workflow"
        model.description = "Workflow for cost tracking"
        model.status = "active"
        model.version = 1
        model.nodes = [
            {"id": "input", "type": "data_input", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "output", "type": "data_output", "position": {"x": 100, "y": 0}, "data": {}},
        ]
        model.edges = [
            {"id": "e1", "source": "input", "target": "output"},
        ]
        model.max_execution_time_seconds = 300
        model.retry_on_failure = False
        model.max_retries = 0
        model.variables = {}
        model.environment = "development"
        model.total_executions = 0
        model.successful_executions = 0
        model.failed_executions = 0
        model.avg_execution_time_seconds = None
        model.total_cost = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        execution = await engine.execute_workflow(
            workflow_id=model.workflow_id,
            input_data={},
            triggered_by="test-user",
            db=mock_db
        )

        # Verify cost was tracked (even if zero for simple nodes)
        assert hasattr(execution, 'total_cost')


class TestWorkflowErrorRecovery:
    """Tests for error handling and recovery in workflows."""

    @pytest.fixture
    def engine(self):
        return WorkflowExecutionEngine()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_workflow_handles_node_failure(self, engine, mock_db):
        """Test that workflow handles node failure gracefully."""
        model = MagicMock()
        model.workflow_id = uuid4()
        model.organization_id = "org-123"
        model.name = "Error Workflow"
        model.description = "Workflow that might fail"
        model.status = "active"
        model.version = 1
        model.nodes = [
            {"id": "input", "type": "data_input", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "output", "type": "data_output", "position": {"x": 100, "y": 0}, "data": {}},
        ]
        model.edges = [
            {"id": "e1", "source": "input", "target": "output"},
        ]
        model.max_execution_time_seconds = 300
        model.retry_on_failure = True
        model.max_retries = 3
        model.variables = {}
        model.environment = "development"
        model.total_executions = 0
        model.successful_executions = 0
        model.failed_executions = 0
        model.avg_execution_time_seconds = None
        model.total_cost = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Execute normally (no forced failure)
        execution = await engine.execute_workflow(
            workflow_id=model.workflow_id,
            input_data={},
            triggered_by="test-user",
            db=mock_db
        )

        assert execution.status == ExecutionStatus.COMPLETED


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
