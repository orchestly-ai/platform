"""
Unit Tests for Workflow Models

Tests for workflow data models, validations, and database operations.
Ensures data integrity and proper model behavior.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from backend.shared.workflow_models import (
    WorkflowModel, WorkflowExecutionModel, WorkflowTemplateModel,
    WorkflowStatus, ExecutionStatus, NodeType,
    Workflow, WorkflowExecution, WorkflowTemplate,
    WorkflowNode, WorkflowEdge,
    NODE_TYPE_CONFIGS, TEMPLATE_CATEGORIES
)


class TestWorkflowDataClasses:
    """Test workflow dataclasses"""

    def test_workflow_node_creation(self):
        """Test creating a workflow node"""
        node = WorkflowNode(
            id="node_1",
            type=NodeType.AGENT_LLM,
            position={"x": 100, "y": 200},
            data={"model": "gpt-4", "temperature": 0.7},
            label="LLM Agent"
        )

        assert node.id == "node_1"
        assert node.type == NodeType.AGENT_LLM
        assert node.position["x"] == 100
        assert node.data["model"] == "gpt-4"
        assert node.label == "LLM Agent"

    def test_workflow_edge_creation(self):
        """Test creating a workflow edge"""
        edge = WorkflowEdge(
            id="edge_1",
            source="node_1",
            target="node_2",
            source_handle="out",
            target_handle="in",
            animated=True
        )

        assert edge.id == "edge_1"
        assert edge.source == "node_1"
        assert edge.target == "node_2"
        assert edge.animated is True

    def test_workflow_creation(self):
        """Test creating a complete workflow"""
        workflow_id = uuid4()
        nodes = [
            WorkflowNode(
                id="input_1",
                type=NodeType.DATA_INPUT,
                position={"x": 0, "y": 0},
                data={}
            ),
            WorkflowNode(
                id="llm_1",
                type=NodeType.LLM_OPENAI,
                position={"x": 200, "y": 0},
                data={"model": "gpt-4"}
            )
        ]
        edges = [
            WorkflowEdge(
                id="e1",
                source="input_1",
                target="llm_1"
            )
        ]

        workflow = Workflow(
            workflow_id=workflow_id,
            organization_id="org_123",
            name="Test Workflow",
            description="A test workflow",
            status=WorkflowStatus.DRAFT,
            version=1,
            nodes=nodes,
            edges=edges,
            variables={"api_key": "test"},
            environment="development"
        )

        assert workflow.workflow_id == workflow_id
        assert workflow.name == "Test Workflow"
        assert len(workflow.nodes) == 2
        assert len(workflow.edges) == 1
        assert workflow.status == WorkflowStatus.DRAFT

    def test_workflow_execution_creation(self):
        """Test creating a workflow execution"""
        execution_id = uuid4()
        workflow_id = uuid4()

        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            workflow_version=1,
            organization_id="org_123",
            status=ExecutionStatus.PENDING,
            input_data={"query": "test"},
            triggered_by="user_1"
        )

        assert execution.execution_id == execution_id
        assert execution.workflow_id == workflow_id
        assert execution.status == ExecutionStatus.PENDING
        assert execution.input_data["query"] == "test"


class TestNodeTypeConfigs:
    """Test node type configurations"""

    def test_all_node_types_have_configs(self):
        """Test that all basic node types have configurations"""
        required_types = [
            "agent_llm",
            "data_transform",
            "control_if",
            "llm_openai"
        ]

        for node_type in required_types:
            assert node_type in NODE_TYPE_CONFIGS
            config = NODE_TYPE_CONFIGS[node_type]
            assert "name" in config
            assert "category" in config
            assert "description" in config

    def test_node_config_structure(self):
        """Test node config has required fields"""
        config = NODE_TYPE_CONFIGS["agent_llm"]

        assert config["name"] == "LLM Agent"
        assert config["category"] == "agents"
        assert "icon" in config
        assert "inputs" in config
        assert "outputs" in config
        assert "config_schema" in config


class TestTemplateCategories:
    """Test template categories"""

    def test_template_categories_defined(self):
        """Test that template categories are defined"""
        assert len(TEMPLATE_CATEGORIES) > 0
        assert "Data Processing" in TEMPLATE_CATEGORIES
        assert "LLM Chains" in TEMPLATE_CATEGORIES


class TestWorkflowStatus:
    """Test workflow status enum"""

    def test_workflow_status_values(self):
        """Test workflow status enum values"""
        assert WorkflowStatus.DRAFT.value == "draft"
        assert WorkflowStatus.ACTIVE.value == "active"
        assert WorkflowStatus.PAUSED.value == "paused"
        assert WorkflowStatus.ARCHIVED.value == "archived"


class TestExecutionStatus:
    """Test execution status enum"""

    def test_execution_status_values(self):
        """Test execution status enum values"""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"
        assert ExecutionStatus.TIMEOUT.value == "timeout"


class TestNodeType:
    """Test node type enum"""

    def test_node_type_categories(self):
        """Test that node types cover all categories"""
        # Agent nodes
        assert NodeType.AGENT_LLM.value == "agent_llm"
        assert NodeType.AGENT_FUNCTION.value == "agent_function"
        assert NodeType.AGENT_TOOL.value == "agent_tool"

        # Data nodes
        assert NodeType.DATA_INPUT.value == "data_input"
        assert NodeType.DATA_OUTPUT.value == "data_output"
        assert NodeType.DATA_TRANSFORM.value == "data_transform"

        # Control flow
        assert NodeType.CONTROL_IF.value == "control_if"
        assert NodeType.CONTROL_SWITCH.value == "control_switch"
        assert NodeType.CONTROL_LOOP.value == "control_loop"

        # Integration nodes
        assert NodeType.INTEGRATION_HTTP.value == "integration_http"
        assert NodeType.INTEGRATION_DATABASE.value == "integration_database"

        # LLM providers
        assert NodeType.LLM_OPENAI.value == "llm_openai"
        assert NodeType.LLM_ANTHROPIC.value == "llm_anthropic"
        assert NodeType.LLM_DEEPSEEK.value == "llm_deepseek"

    def test_node_type_count(self):
        """Test that we have the expected number of node types"""
        node_types = list(NodeType)
        # We defined 30+ node types
        assert len(node_types) >= 25


class TestWorkflowValidation:
    """Test workflow validation logic"""

    def test_workflow_requires_nodes(self):
        """Test that workflow must have nodes"""
        workflow_id = uuid4()

        # Creating workflow with empty nodes should be allowed
        # (validation happens at execution time)
        workflow = Workflow(
            workflow_id=workflow_id,
            organization_id="org_123",
            name="Empty Workflow",
            description="Test",
            status=WorkflowStatus.DRAFT,
            version=1,
            nodes=[],
            edges=[]
        )

        assert len(workflow.nodes) == 0

    def test_workflow_defaults(self):
        """Test workflow default values"""
        workflow_id = uuid4()

        workflow = Workflow(
            workflow_id=workflow_id,
            organization_id="org_123",
            name="Test",
            description=None,
            status=WorkflowStatus.DRAFT,
            version=1,
            nodes=[],
            edges=[]
        )

        assert workflow.max_execution_time_seconds == 3600
        assert workflow.retry_on_failure is True
        assert workflow.max_retries == 3
        assert workflow.environment == "development"
        assert workflow.total_executions == 0
        assert workflow.total_cost == 0.0


class TestWorkflowExecutionValidation:
    """Test workflow execution validation"""

    def test_execution_node_states_structure(self):
        """Test node states structure in execution"""
        execution = WorkflowExecution(
            execution_id=uuid4(),
            workflow_id=uuid4(),
            workflow_version=1,
            organization_id="org_123",
            status=ExecutionStatus.RUNNING,
            node_states={
                "node_1": {
                    "status": "completed",
                    "output": {"result": "success"},
                    "duration": 1.5,
                    "cost": 0.002
                },
                "node_2": {
                    "status": "running",
                    "output": None,
                    "duration": None,
                    "cost": 0.0
                }
            }
        )

        assert "node_1" in execution.node_states
        assert execution.node_states["node_1"]["status"] == "completed"
        assert execution.node_states["node_1"]["duration"] == 1.5
        assert execution.node_states["node_2"]["status"] == "running"

    def test_execution_timing(self):
        """Test execution timing calculations"""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=5)

        execution = WorkflowExecution(
            execution_id=uuid4(),
            workflow_id=uuid4(),
            workflow_version=1,
            organization_id="org_123",
            status=ExecutionStatus.COMPLETED,
            started_at=start_time,
            completed_at=end_time,
            duration_seconds=5.0
        )

        assert execution.started_at == start_time
        assert execution.completed_at == end_time
        assert execution.duration_seconds == 5.0


class TestWorkflowTemplate:
    """Test workflow template model"""

    def test_template_creation(self):
        """Test creating a workflow template"""
        template_id = uuid4()

        template = WorkflowTemplate(
            template_id=template_id,
            name="Email Processor",
            description="Process emails with AI",
            category="Automation",
            tags=["email", "ai", "automation"],
            nodes=[],
            edges=[],
            variables={},
            is_public=True,
            is_featured=False,
            use_count=0
        )

        assert template.template_id == template_id
        assert template.name == "Email Processor"
        assert template.category == "Automation"
        assert template.is_public is True
        assert template.use_count == 0

    def test_template_marketplace_fields(self):
        """Test template has marketplace-specific fields"""
        template = WorkflowTemplate(
            template_id=uuid4(),
            name="Test Template",
            description="Test",
            category="Data Processing",
            tags=["test"],
            nodes=[],
            edges=[],
            thumbnail_url="https://example.com/thumb.png",
            rating=4.5,
            use_count=100,
            is_featured=True
        )

        assert template.thumbnail_url is not None
        assert template.rating == 4.5
        assert template.use_count == 100
        assert template.is_featured is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
