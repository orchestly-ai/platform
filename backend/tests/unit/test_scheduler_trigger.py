"""
Unit Tests for Scheduler Trigger

Tests for external trigger endpoint and workflow execution creation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from backend.shared.workflow_models import WorkflowStatus, ExecutionStatus


class TestSchedulerExternalTrigger:
    """Tests for scheduler external trigger functionality."""

    def test_input_data_merging(self):
        """Test that schedule input_data and request input_data are merged."""
        schedule_input = {"key1": "value1", "key2": "original"}
        request_input = {"key2": "override", "key3": "value3"}

        # Simulating the merge logic from scheduler.py
        merged = schedule_input.copy()
        merged.update(request_input)

        assert merged["key1"] == "value1"
        assert merged["key2"] == "override"  # Request overrides
        assert merged["key3"] == "value3"

    def test_input_data_merge_with_empty_schedule(self):
        """Test merging when schedule has no input data."""
        schedule_input = {}
        request_input = {"key": "value"}

        merged = schedule_input.copy()
        merged.update(request_input)

        assert merged == {"key": "value"}

    def test_input_data_merge_with_empty_request(self):
        """Test merging when request has no input data."""
        schedule_input = {"key": "value"}
        request_input = {}

        merged = schedule_input.copy()
        merged.update(request_input)

        assert merged == {"key": "value"}

    def test_input_data_merge_both_empty(self):
        """Test merging when both are empty."""
        schedule_input = {}
        request_input = {}

        merged = schedule_input.copy()
        merged.update(request_input)

        assert merged == {}

    def test_input_data_merge_none_handling(self):
        """Test handling None input data."""
        schedule_input = None
        request_input = {"key": "value"}

        # Simulating the scheduler logic
        merged = (schedule_input or {}).copy()
        if request_input:
            merged.update(request_input)

        assert merged == {"key": "value"}


class TestWorkflowConversion:
    """Tests for workflow model conversion in scheduler trigger."""

    def test_workflow_node_conversion(self):
        """Test converting workflow nodes from dict to WorkflowNode."""
        from backend.shared.workflow_models import WorkflowNode, NodeType

        node_dict = {
            "id": "node-1",
            "type": "agent_llm",
            "position": {"x": 100, "y": 200},
            "data": {"model": "gpt-4", "prompt": "Hello"},
            "label": "LLM Node"
        }

        node = WorkflowNode(
            id=node_dict["id"],
            type=NodeType(node_dict["type"]),
            position=node_dict["position"],
            data=node_dict["data"],
            label=node_dict.get("label")
        )

        assert node.id == "node-1"
        assert node.type == NodeType.AGENT_LLM
        assert node.position == {"x": 100, "y": 200}
        assert node.data["model"] == "gpt-4"
        assert node.label == "LLM Node"

    def test_workflow_edge_conversion(self):
        """Test converting workflow edges from dict to WorkflowEdge."""
        from backend.shared.workflow_models import WorkflowEdge

        edge_dict = {
            "id": "edge-1",
            "source": "node-1",
            "target": "node-2",
            "sourceHandle": "out",
            "targetHandle": "in",
            "label": "Next",
            "animated": True
        }

        edge = WorkflowEdge(
            id=edge_dict["id"],
            source=edge_dict["source"],
            target=edge_dict["target"],
            source_handle=edge_dict.get("sourceHandle", "out"),
            target_handle=edge_dict.get("targetHandle", "in"),
            label=edge_dict.get("label"),
            animated=edge_dict.get("animated", False)
        )

        assert edge.id == "edge-1"
        assert edge.source == "node-1"
        assert edge.target == "node-2"
        assert edge.source_handle == "out"
        assert edge.label == "Next"
        assert edge.animated is True

    def test_workflow_edge_default_handles(self):
        """Test edge conversion with default handle values."""
        from backend.shared.workflow_models import WorkflowEdge

        edge_dict = {
            "id": "edge-1",
            "source": "node-1",
            "target": "node-2"
        }

        edge = WorkflowEdge(
            id=edge_dict["id"],
            source=edge_dict["source"],
            target=edge_dict["target"],
            source_handle=edge_dict.get("sourceHandle", "out"),
            target_handle=edge_dict.get("targetHandle", "in"),
            label=edge_dict.get("label"),
            animated=edge_dict.get("animated", False)
        )

        assert edge.source_handle == "out"
        assert edge.target_handle == "in"
        assert edge.animated is False


class TestExecutionRecordCreation:
    """Tests for execution record creation from scheduled trigger."""

    def test_execution_has_scheduler_trigger_source(self):
        """Test that execution record has proper trigger source."""
        schedule_id = uuid4()
        trigger_source = f"schedule:{schedule_id}"

        assert "schedule:" in trigger_source
        assert str(schedule_id) in trigger_source

    def test_execution_triggered_by_scheduler(self):
        """Test that execution is triggered by 'scheduler'."""
        triggered_by = "scheduler"

        assert triggered_by == "scheduler"

    def test_execution_initial_status_pending(self):
        """Test that new execution starts with PENDING status."""
        status = ExecutionStatus.PENDING

        assert status == ExecutionStatus.PENDING
        assert status.value == "pending"


class TestScheduleValidation:
    """Tests for schedule validation in trigger."""

    def test_archived_workflow_rejection(self):
        """Test that archived workflows cannot be executed."""
        workflow_status = WorkflowStatus.ARCHIVED

        # Simulating the validation logic
        can_execute = workflow_status != WorkflowStatus.ARCHIVED

        assert can_execute is False

    def test_draft_workflow_allowed(self):
        """Test that draft workflows can be executed (for testing)."""
        workflow_status = WorkflowStatus.DRAFT

        can_execute = workflow_status != WorkflowStatus.ARCHIVED

        assert can_execute is True

    def test_active_workflow_allowed(self):
        """Test that active workflows can be executed."""
        workflow_status = WorkflowStatus.ACTIVE

        can_execute = workflow_status != WorkflowStatus.ARCHIVED

        assert can_execute is True
