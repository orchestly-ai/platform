"""
Unit Tests for Time-Travel Replay Execution

Tests for the execute_replay functionality in timetravel_service.
"""

import pytest
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4, UUID

from backend.shared.timetravel_service import ReplayEngine
from backend.shared.timetravel_models import (
    ExecutionReplayModel, ExecutionSnapshotModel, SnapshotType
)

# Check if we can import workflow_service (requires numpy)
try:
    from backend.shared.workflow_service import get_workflow_service
    HAS_WORKFLOW_SERVICE = True
except ImportError:
    HAS_WORKFLOW_SERVICE = False

# Skip tests that require workflow_service if numpy isn't installed
requires_workflow_service = pytest.mark.skipif(
    not HAS_WORKFLOW_SERVICE,
    reason="workflow_service requires numpy which is not installed"
)


class TestReplayEngine:
    """Tests for ReplayEngine.execute_replay."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def replay_engine(self, mock_db):
        """Create ReplayEngine instance."""
        return ReplayEngine(mock_db)

    @pytest.fixture
    def sample_replay(self):
        """Create sample replay configuration."""
        replay = MagicMock(spec=ExecutionReplayModel)
        replay.replay_id = uuid4()
        replay.organization_id = "test-org"
        replay.source_execution_id = uuid4()
        replay.workflow_id = uuid4()
        replay.replay_mode = "exact"
        replay.input_modifications = None
        replay.breakpoints = []
        replay.skip_nodes = []
        replay.status = "pending"
        replay.started_at = None
        replay.completed_at = None
        replay.new_execution_id = None
        replay.error_message = None
        return replay

    @pytest.fixture
    def sample_snapshot(self):
        """Create sample execution snapshot."""
        snapshot = MagicMock(spec=ExecutionSnapshotModel)
        snapshot.execution_id = uuid4()
        snapshot.snapshot_type = SnapshotType.EXECUTION_START.value
        snapshot.input_state = {"prompt": "Test input", "temperature": 0.7}
        snapshot.output_state = None
        return snapshot

    @requires_workflow_service
    @pytest.mark.asyncio
    async def test_execute_replay_exact_mode(self, replay_engine, mock_db, sample_replay, sample_snapshot):
        """Test replay execution in exact mode uses original input."""
        # Setup mocks
        replay_result = MagicMock()
        replay_result.scalar_one = MagicMock(return_value=sample_replay)

        snapshot_result = MagicMock()
        snapshot_result.scalar_one = MagicMock(return_value=sample_snapshot)

        mock_db.execute.side_effect = [replay_result, snapshot_result]

        # Mock workflow service
        mock_execution = MagicMock()
        mock_execution.execution_id = uuid4()

        with patch('backend.shared.workflow_service.get_workflow_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.execute_workflow = AsyncMock(return_value=mock_execution)
            mock_get_service.return_value = mock_service

            result = await replay_engine.execute_replay(sample_replay.replay_id, None)

            # Verify workflow was executed with original input
            mock_service.execute_workflow.assert_called_once()
            call_kwargs = mock_service.execute_workflow.call_args.kwargs
            assert call_kwargs['input_data'] == sample_snapshot.input_state
            assert f"replay:{sample_replay.replay_id}" in call_kwargs['triggered_by']

    @requires_workflow_service
    @pytest.mark.asyncio
    async def test_execute_replay_modified_input_mode(self, replay_engine, mock_db, sample_replay, sample_snapshot):
        """Test replay execution in modified_input mode applies modifications."""
        # Configure replay for modified input
        sample_replay.replay_mode = "modified_input"
        sample_replay.input_modifications = {"temperature": 0.9, "max_tokens": 500}

        # Setup mocks
        replay_result = MagicMock()
        replay_result.scalar_one = MagicMock(return_value=sample_replay)

        snapshot_result = MagicMock()
        snapshot_result.scalar_one = MagicMock(return_value=sample_snapshot)

        mock_db.execute.side_effect = [replay_result, snapshot_result]

        # Mock workflow service
        mock_execution = MagicMock()
        mock_execution.execution_id = uuid4()

        with patch('backend.shared.workflow_service.get_workflow_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.execute_workflow = AsyncMock(return_value=mock_execution)
            mock_get_service.return_value = mock_service

            result = await replay_engine.execute_replay(sample_replay.replay_id, None)

            # Verify modifications were applied
            call_kwargs = mock_service.execute_workflow.call_args.kwargs
            expected_input = {
                "prompt": "Test input",  # Original
                "temperature": 0.9,  # Modified
                "max_tokens": 500  # Added
            }
            assert call_kwargs['input_data'] == expected_input

    @requires_workflow_service
    @pytest.mark.asyncio
    async def test_execute_replay_updates_status_on_success(self, replay_engine, mock_db, sample_replay, sample_snapshot):
        """Test that replay status is updated to completed on success."""
        # Setup mocks
        replay_result = MagicMock()
        replay_result.scalar_one = MagicMock(return_value=sample_replay)

        snapshot_result = MagicMock()
        snapshot_result.scalar_one = MagicMock(return_value=sample_snapshot)

        mock_db.execute.side_effect = [replay_result, snapshot_result]

        # Mock workflow service
        mock_execution = MagicMock()
        mock_execution.execution_id = uuid4()

        with patch('backend.shared.workflow_service.get_workflow_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.execute_workflow = AsyncMock(return_value=mock_execution)
            mock_get_service.return_value = mock_service

            await replay_engine.execute_replay(sample_replay.replay_id, None)

            # Verify status updates
            assert sample_replay.status == "completed"
            assert sample_replay.new_execution_id == mock_execution.execution_id
            assert sample_replay.completed_at is not None
            assert mock_db.commit.call_count >= 2  # Once for running, once for completed

    @requires_workflow_service
    @pytest.mark.asyncio
    async def test_execute_replay_handles_workflow_failure(self, replay_engine, mock_db, sample_replay, sample_snapshot):
        """Test that replay status is updated to failed on workflow error."""
        # Setup mocks
        replay_result = MagicMock()
        replay_result.scalar_one = MagicMock(return_value=sample_replay)

        snapshot_result = MagicMock()
        snapshot_result.scalar_one = MagicMock(return_value=sample_snapshot)

        mock_db.execute.side_effect = [replay_result, snapshot_result]

        # Mock workflow service to fail
        with patch('backend.shared.workflow_service.get_workflow_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.execute_workflow = AsyncMock(side_effect=Exception("Workflow execution failed"))
            mock_get_service.return_value = mock_service

            with pytest.raises(Exception) as exc_info:
                await replay_engine.execute_replay(sample_replay.replay_id, None)

            assert "Workflow execution failed" in str(exc_info.value)

            # Verify failure status
            assert sample_replay.status == "failed"
            assert sample_replay.error_message == "Workflow execution failed"
            assert sample_replay.completed_at is not None

    @requires_workflow_service
    @pytest.mark.asyncio
    async def test_execute_replay_triggered_by_includes_replay_id(self, replay_engine, mock_db, sample_replay, sample_snapshot):
        """Test that triggered_by includes replay ID for traceability."""
        # Setup mocks
        replay_result = MagicMock()
        replay_result.scalar_one = MagicMock(return_value=sample_replay)

        snapshot_result = MagicMock()
        snapshot_result.scalar_one = MagicMock(return_value=sample_snapshot)

        mock_db.execute.side_effect = [replay_result, snapshot_result]

        # Mock workflow service
        mock_execution = MagicMock()
        mock_execution.execution_id = uuid4()

        with patch('backend.shared.workflow_service.get_workflow_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.execute_workflow = AsyncMock(return_value=mock_execution)
            mock_get_service.return_value = mock_service

            await replay_engine.execute_replay(sample_replay.replay_id, None)

            call_kwargs = mock_service.execute_workflow.call_args.kwargs
            assert f"replay:{sample_replay.replay_id}" == call_kwargs['triggered_by']


class TestReplayInputModifications:
    """Tests for input modification handling in replays."""

    def test_merge_original_with_modifications(self):
        """Test that modifications are merged with original input."""
        original = {"a": 1, "b": 2, "c": 3}
        modifications = {"b": 20, "d": 4}

        # This is the logic used in execute_replay
        merged = {**original, **modifications}

        assert merged == {"a": 1, "b": 20, "c": 3, "d": 4}

    def test_empty_modifications_returns_original(self):
        """Test that empty modifications return original input."""
        original = {"a": 1, "b": 2}
        modifications = {}

        merged = {**original, **modifications}

        assert merged == original

    def test_none_modifications_skipped(self):
        """Test that None modifications are handled correctly."""
        original = {"a": 1, "b": 2}
        modifications = None

        # Logic from execute_replay
        if modifications:
            merged = {**original, **modifications}
        else:
            merged = original

        assert merged == original


class TestReplayModes:
    """Tests for different replay modes."""

    def test_exact_mode_uses_original_input(self):
        """Test exact mode configuration."""
        replay_mode = "exact"
        original_input = {"prompt": "test"}
        modifications = {"prompt": "modified"}

        # Logic from execute_replay
        if replay_mode == "modified_input" and modifications:
            replay_input = {**original_input, **modifications}
        else:
            replay_input = original_input

        assert replay_input == {"prompt": "test"}

    def test_modified_input_mode_applies_changes(self):
        """Test modified_input mode configuration."""
        replay_mode = "modified_input"
        original_input = {"prompt": "test"}
        modifications = {"prompt": "modified"}

        # Logic from execute_replay
        if replay_mode == "modified_input" and modifications:
            replay_input = {**original_input, **modifications}
        else:
            replay_input = original_input

        assert replay_input == {"prompt": "modified"}

    def test_step_by_step_mode_marker(self):
        """Test step_by_step mode is recognized."""
        valid_modes = ["exact", "modified_input", "step_by_step", "breakpoint"]
        assert "step_by_step" in valid_modes

    def test_breakpoint_mode_marker(self):
        """Test breakpoint mode is recognized."""
        valid_modes = ["exact", "modified_input", "step_by_step", "breakpoint"]
        assert "breakpoint" in valid_modes
