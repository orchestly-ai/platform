"""
Unit Tests for Shared State Manager

Tests state storage, retrieval, scoping, TTL, and variable substitution.
"""

import asyncio
import pytest
from datetime import timedelta
from backend.shared.shared_state_manager import (
    SharedStateManager,
    StateScope,
    StateEntry,
    StateSnapshot,
    get_shared_state_manager,
    reset_shared_state_manager
)


@pytest.fixture
def state_manager():
    """Create a fresh state manager for each test."""
    reset_shared_state_manager()
    manager = SharedStateManager()
    yield manager
    # Cleanup
    asyncio.run(cleanup_state(manager))


async def cleanup_state(manager):
    """Clean up all state after test."""
    for scope in StateScope:
        try:
            await manager.clear(scope, "test")
        except:
            pass


class TestStateStorage:
    """Test basic state storage and retrieval."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, state_manager):
        """Test setting and getting values."""
        # Set a value
        success = await state_manager.set(
            key="test_key",
            value="test_value",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123"
        )
        assert success is True

        # Get the value
        value = await state_manager.get(
            key="test_key",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123"
        )
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, state_manager):
        """Test getting a non-existent key returns default."""
        value = await state_manager.get(
            key="nonexistent",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123",
            default="default_value"
        )
        assert value == "default_value"

    @pytest.mark.asyncio
    async def test_delete(self, state_manager):
        """Test deleting a value."""
        # Set a value
        await state_manager.set(
            key="to_delete",
            value="value",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123"
        )

        # Delete it
        deleted = await state_manager.delete(
            key="to_delete",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123"
        )
        assert deleted is True

        # Verify it's gone
        value = await state_manager.get(
            key="to_delete",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123"
        )
        assert value is None

    @pytest.mark.asyncio
    async def test_exists(self, state_manager):
        """Test checking if a key exists."""
        # Should not exist initially
        exists = await state_manager.exists(
            key="test_key",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123"
        )
        assert exists is False

        # Set a value
        await state_manager.set(
            key="test_key",
            value="value",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123"
        )

        # Should exist now
        exists = await state_manager.exists(
            key="test_key",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123"
        )
        assert exists is True


class TestStateScoping:
    """Test state scoping and isolation."""

    @pytest.mark.asyncio
    async def test_workflow_scope_isolation(self, state_manager):
        """Test that workflow scopes are isolated."""
        # Set value in workflow 1
        await state_manager.set(
            key="shared_key",
            value="workflow_1_value",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_1"
        )

        # Set different value in workflow 2
        await state_manager.set(
            key="shared_key",
            value="workflow_2_value",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_2"
        )

        # Verify isolation
        value1 = await state_manager.get(
            key="shared_key",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_1"
        )
        value2 = await state_manager.get(
            key="shared_key",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_2"
        )

        assert value1 == "workflow_1_value"
        assert value2 == "workflow_2_value"

    @pytest.mark.asyncio
    async def test_different_scopes_isolated(self, state_manager):
        """Test that different scopes are isolated."""
        # Set in workflow scope
        await state_manager.set(
            key="test_key",
            value="workflow_value",
            scope=StateScope.WORKFLOW,
            scope_id="id_123"
        )

        # Set in agent scope
        await state_manager.set(
            key="test_key",
            value="agent_value",
            scope=StateScope.AGENT,
            scope_id="id_123"
        )

        # Verify isolation
        workflow_value = await state_manager.get(
            key="test_key",
            scope=StateScope.WORKFLOW,
            scope_id="id_123"
        )
        agent_value = await state_manager.get(
            key="test_key",
            scope=StateScope.AGENT,
            scope_id="id_123"
        )

        assert workflow_value == "workflow_value"
        assert agent_value == "agent_value"


class TestBulkOperations:
    """Test bulk state operations."""

    @pytest.mark.asyncio
    async def test_get_all(self, state_manager):
        """Test getting all values for a scope."""
        # Set multiple values
        await state_manager.set("key1", "value1", StateScope.WORKFLOW, "workflow_123")
        await state_manager.set("key2", "value2", StateScope.WORKFLOW, "workflow_123")
        await state_manager.set("key3", "value3", StateScope.WORKFLOW, "workflow_123")

        # Get all
        all_values = await state_manager.get_all(StateScope.WORKFLOW, "workflow_123")

        assert len(all_values) == 3
        assert all_values["key1"] == "value1"
        assert all_values["key2"] == "value2"
        assert all_values["key3"] == "value3"

    @pytest.mark.asyncio
    async def test_clear(self, state_manager):
        """Test clearing all values for a scope."""
        # Set multiple values
        await state_manager.set("key1", "value1", StateScope.WORKFLOW, "workflow_123")
        await state_manager.set("key2", "value2", StateScope.WORKFLOW, "workflow_123")
        await state_manager.set("key3", "value3", StateScope.WORKFLOW, "workflow_123")

        # Clear
        count = await state_manager.clear(StateScope.WORKFLOW, "workflow_123")

        assert count == 3

        # Verify all are gone
        all_values = await state_manager.get_all(StateScope.WORKFLOW, "workflow_123")
        assert len(all_values) == 0

    @pytest.mark.asyncio
    async def test_keys(self, state_manager):
        """Test getting all keys for a scope."""
        # Set multiple values
        await state_manager.set("key1", "value1", StateScope.WORKFLOW, "workflow_123")
        await state_manager.set("key2", "value2", StateScope.WORKFLOW, "workflow_123")
        await state_manager.set("key3", "value3", StateScope.WORKFLOW, "workflow_123")

        # Get keys
        keys = await state_manager.keys(StateScope.WORKFLOW, "workflow_123")

        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys


class TestStateSnapshots:
    """Test state snapshot and restore functionality."""

    @pytest.mark.asyncio
    async def test_snapshot(self, state_manager):
        """Test creating a state snapshot."""
        # Set some values
        await state_manager.set("key1", "value1", StateScope.WORKFLOW, "workflow_123")
        await state_manager.set("key2", {"nested": "data"}, StateScope.WORKFLOW, "workflow_123")

        # Create snapshot
        snapshot = await state_manager.snapshot(StateScope.WORKFLOW, "workflow_123")

        assert snapshot.scope == StateScope.WORKFLOW
        assert snapshot.scope_id == "workflow_123"
        assert len(snapshot.entries) == 2
        assert snapshot.entries["key1"] == "value1"
        assert snapshot.entries["key2"] == {"nested": "data"}

    @pytest.mark.asyncio
    async def test_restore_snapshot(self, state_manager):
        """Test restoring from a snapshot."""
        # Set initial values
        await state_manager.set("key1", "value1", StateScope.WORKFLOW, "workflow_123")
        await state_manager.set("key2", "value2", StateScope.WORKFLOW, "workflow_123")

        # Create snapshot
        snapshot = await state_manager.snapshot(StateScope.WORKFLOW, "workflow_123")

        # Modify state
        await state_manager.set("key1", "modified", StateScope.WORKFLOW, "workflow_123")
        await state_manager.delete("key2", StateScope.WORKFLOW, "workflow_123")

        # Restore snapshot
        count = await state_manager.restore_snapshot(snapshot)

        assert count == 2

        # Verify restored values
        value1 = await state_manager.get("key1", StateScope.WORKFLOW, "workflow_123")
        value2 = await state_manager.get("key2", StateScope.WORKFLOW, "workflow_123")

        assert value1 == "value1"
        assert value2 == "value2"


class TestComplexDataTypes:
    """Test storing complex data types."""

    @pytest.mark.asyncio
    async def test_dict_storage(self, state_manager):
        """Test storing dictionaries."""
        data = {
            "user": "John",
            "age": 30,
            "nested": {
                "city": "New York",
                "country": "USA"
            }
        }

        await state_manager.set("user_data", data, StateScope.WORKFLOW, "workflow_123")
        retrieved = await state_manager.get("user_data", StateScope.WORKFLOW, "workflow_123")

        assert retrieved == data
        assert retrieved["user"] == "John"
        assert retrieved["nested"]["city"] == "New York"

    @pytest.mark.asyncio
    async def test_list_storage(self, state_manager):
        """Test storing lists."""
        data = ["apple", "banana", "cherry"]

        await state_manager.set("fruits", data, StateScope.WORKFLOW, "workflow_123")
        retrieved = await state_manager.get("fruits", StateScope.WORKFLOW, "workflow_123")

        assert retrieved == data
        assert len(retrieved) == 3
        assert "banana" in retrieved


class TestMetadata:
    """Test metadata storage and tracking."""

    @pytest.mark.asyncio
    async def test_metadata_storage(self, state_manager):
        """Test storing metadata with values."""
        metadata = {
            "source": "node_123",
            "timestamp": "2024-01-15T10:00:00Z",
            "cost": 0.001
        }

        await state_manager.set(
            key="test_key",
            value="test_value",
            scope=StateScope.WORKFLOW,
            scope_id="workflow_123",
            metadata=metadata
        )

        # Note: Metadata is stored but not returned by get()
        # It's for internal tracking and debugging
        value = await state_manager.get("test_key", StateScope.WORKFLOW, "workflow_123")
        assert value == "test_value"


class TestWorkflowIntegration:
    """Test realistic workflow scenarios."""

    @pytest.mark.asyncio
    async def test_node_output_storage(self, state_manager):
        """Test storing node outputs as they would be in a workflow."""
        workflow_id = "workflow_123"

        # Simulate Node 1 (User Input) output
        await state_manager.set(
            key="node_output:user_input",
            value={"message": "Hello World", "user_id": "user_456"},
            scope=StateScope.WORKFLOW,
            scope_id=workflow_id,
            metadata={"node_type": "input", "execution_time": 10}
        )

        # Simulate Node 2 (LLM) output
        await state_manager.set(
            key="node_output:llm_processor",
            value={
                "content": "Processed: Hello World",
                "model": "gpt-4",
                "tokens": 150
            },
            scope=StateScope.WORKFLOW,
            scope_id=workflow_id,
            metadata={"node_type": "llm", "execution_time": 1500}
        )

        # Simulate Node 3 accessing previous node outputs
        user_input = await state_manager.get(
            key="node_output:user_input",
            scope=StateScope.WORKFLOW,
            scope_id=workflow_id
        )
        llm_output = await state_manager.get(
            key="node_output:llm_processor",
            scope=StateScope.WORKFLOW,
            scope_id=workflow_id
        )

        assert user_input["message"] == "Hello World"
        assert llm_output["content"] == "Processed: Hello World"

        # Cleanup workflow state when done
        cleared = await state_manager.clear(StateScope.WORKFLOW, workflow_id)
        assert cleared == 2


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_string_value(self, state_manager):
        """Test storing empty string."""
        await state_manager.set("empty", "", StateScope.WORKFLOW, "workflow_123")
        value = await state_manager.get("empty", StateScope.WORKFLOW, "workflow_123")
        assert value == ""

    @pytest.mark.asyncio
    async def test_none_value(self, state_manager):
        """Test storing None."""
        await state_manager.set("none_val", None, StateScope.WORKFLOW, "workflow_123")
        value = await state_manager.get("none_val", StateScope.WORKFLOW, "workflow_123")
        assert value is None

    @pytest.mark.asyncio
    async def test_large_data(self, state_manager):
        """Test storing large data."""
        large_data = {f"key_{i}": f"value_{i}" for i in range(1000)}

        await state_manager.set("large", large_data, StateScope.WORKFLOW, "workflow_123")
        retrieved = await state_manager.get("large", StateScope.WORKFLOW, "workflow_123")

        assert len(retrieved) == 1000
        assert retrieved["key_500"] == "value_500"


if __name__ == "__main__":
    # Run tests with: python -m pytest backend/tests/test_shared_state_manager.py -v
    pytest.main([__file__, "-v", "-s"])
