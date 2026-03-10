"""Unit tests for Agent Registry.

NOTE: These tests are outdated and have asyncio event loop issues.
The backend/tests/unit/test_agent_registry_db.py contains the up-to-date tests.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

pytestmark = pytest.mark.skip(reason="Tests outdated - asyncio loop issues. See backend/tests/unit/test_agent_registry_db.py")

from backend.shared.models import (
    AgentConfig,
    AgentStatus,
    AgentCapability,
)
from backend.orchestrator.registry import AgentRegistry


@pytest.mark.unit
@pytest.mark.asyncio
class TestAgentRegistry:
    """Test suite for AgentRegistry."""

    @pytest.fixture
    def registry(self):
        """Create fresh AgentRegistry instance."""
        return AgentRegistry()

    @pytest.fixture
    def sample_agent_config(self):
        """Sample agent configuration."""
        return AgentConfig(
            agent_id=uuid4(),
            name="Test Agent",
            capabilities=[
                AgentCapability(
                    name="test_capability",
                    description="Test capability",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )

    async def test_register_agent_success(self, registry, sample_agent_config):
        """Test successful agent registration."""
        agent_id = await registry.register_agent(sample_agent_config)

        assert agent_id == sample_agent_config.agent_id
        assert agent_id in registry._agents
        assert agent_id in registry._agent_states

        # Check state initialized correctly
        state = await registry.get_agent_state(agent_id)
        assert state is not None
        assert state.status == AgentStatus.ACTIVE
        assert state.tasks_completed == 0
        assert state.tasks_failed == 0
        assert state.total_cost_today == 0.0

    async def test_register_agent_duplicate_name(self, registry, sample_agent_config):
        """Test registering agent with duplicate name fails."""
        await registry.register_agent(sample_agent_config)

        # Try to register another agent with same name
        duplicate_config = AgentConfig(
            agent_id=uuid4(),
            name="Test Agent",  # Same name
            capabilities=sample_agent_config.capabilities,
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )

        with pytest.raises(ValueError, match="already exists"):
            await registry.register_agent(duplicate_config)

    async def test_register_agent_capability_index(self, registry, sample_agent_config):
        """Test capability index is updated on registration."""
        agent_id = await registry.register_agent(sample_agent_config)

        capability_name = "test_capability"
        assert capability_name in registry._capability_index
        assert agent_id in registry._capability_index[capability_name]

    async def test_deregister_agent_success(self, registry, sample_agent_config):
        """Test agent deregistration."""
        agent_id = await registry.register_agent(sample_agent_config)

        await registry.deregister_agent(agent_id)

        assert agent_id not in registry._agents
        assert agent_id not in registry._agent_states

        # Check removed from capability index
        capability_name = "test_capability"
        if capability_name in registry._capability_index:
            assert agent_id not in registry._capability_index[capability_name]

    async def test_deregister_nonexistent_agent(self, registry):
        """Test deregistering non-existent agent doesn't error."""
        fake_id = uuid4()
        await registry.deregister_agent(fake_id)  # Should not raise

    async def test_get_agent(self, registry, sample_agent_config):
        """Test retrieving agent configuration."""
        agent_id = await registry.register_agent(sample_agent_config)

        config = await registry.get_agent(agent_id)

        assert config is not None
        assert config.agent_id == agent_id
        assert config.name == "Test Agent"

    async def test_get_nonexistent_agent(self, registry):
        """Test getting non-existent agent returns None."""
        fake_id = uuid4()
        config = await registry.get_agent(fake_id)
        assert config is None

    async def test_list_agents_all(self, registry):
        """Test listing all agents."""
        # Register multiple agents
        configs = []
        for i in range(3):
            config = AgentConfig(
                agent_id=uuid4(),
                name=f"Agent {i}",
                capabilities=[
                    AgentCapability(
                        name=f"capability_{i}",
                        description=f"Capability {i}",
                        estimated_cost_per_call=0.01,
                    )
                ],
                cost_limit_daily=10.0,
                cost_limit_monthly=100.0,
            )
            await registry.register_agent(config)
            configs.append(config)

        agents = await registry.list_agents()

        assert len(agents) == 3
        assert all(isinstance(agent, AgentConfig) for agent in agents)

    async def test_list_agents_by_status(self, registry, sample_agent_config):
        """Test listing agents filtered by status."""
        agent_id = await registry.register_agent(sample_agent_config)

        # Mark agent as error
        await registry.update_agent_status(agent_id, AgentStatus.ERROR)

        # List only active agents (should be empty)
        active_agents = await registry.list_agents(status=AgentStatus.ACTIVE)
        assert len(active_agents) == 0

        # List error agents (should have our agent)
        error_agents = await registry.list_agents(status=AgentStatus.ERROR)
        assert len(error_agents) == 1
        assert error_agents[0].agent_id == agent_id

    async def test_find_agents_by_capability(self, registry):
        """Test finding agents by capability."""
        # Register agents with different capabilities
        agent1_config = AgentConfig(
            agent_id=uuid4(),
            name="Agent 1",
            capabilities=[
                AgentCapability(
                    name="capability_a",
                    description="Capability A",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )
        agent1_id = await registry.register_agent(agent1_config)

        agent2_config = AgentConfig(
            agent_id=uuid4(),
            name="Agent 2",
            capabilities=[
                AgentCapability(
                    name="capability_a",
                    description="Capability A",
                    estimated_cost_per_call=0.01,
                ),
                AgentCapability(
                    name="capability_b",
                    description="Capability B",
                    estimated_cost_per_call=0.02,
                ),
            ],
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )
        agent2_id = await registry.register_agent(agent2_config)

        # Find agents with capability_a
        agents_a = await registry.find_agents_by_capability("capability_a")
        assert len(agents_a) == 2
        assert agent1_id in agents_a
        assert agent2_id in agents_a

        # Find agents with capability_b
        agents_b = await registry.find_agents_by_capability("capability_b")
        assert len(agents_b) == 1
        assert agent2_id in agents_b

        # Find agents with non-existent capability
        agents_c = await registry.find_agents_by_capability("capability_c")
        assert len(agents_c) == 0

    async def test_find_agents_by_capability_with_status_filter(self, registry):
        """Test finding agents by capability with status filter."""
        agent_id = uuid4()
        config = AgentConfig(
            agent_id=agent_id,
            name="Test Agent",
            capabilities=[
                AgentCapability(
                    name="test_cap",
                    description="Test",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )
        await registry.register_agent(config)

        # Agent should be found when active
        agents = await registry.find_agents_by_capability("test_cap", AgentStatus.ACTIVE)
        assert len(agents) == 1

        # Mark as inactive
        await registry.update_agent_status(agent_id, AgentStatus.INACTIVE)

        # Should not be found when filtering for active
        agents = await registry.find_agents_by_capability("test_cap", AgentStatus.ACTIVE)
        assert len(agents) == 0

        # Should be found when filtering for inactive
        agents = await registry.find_agents_by_capability("test_cap", AgentStatus.INACTIVE)
        assert len(agents) == 1

    async def test_update_agent_status(self, registry, sample_agent_config):
        """Test updating agent status."""
        agent_id = await registry.register_agent(sample_agent_config)

        await registry.update_agent_status(agent_id, AgentStatus.ERROR, "Test error")

        state = await registry.get_agent_state(agent_id)
        assert state.status == AgentStatus.ERROR
        assert state.error_message == "Test error"

    async def test_update_heartbeat(self, registry, sample_agent_config):
        """Test updating agent heartbeat."""
        agent_id = await registry.register_agent(sample_agent_config)

        initial_state = await registry.get_agent_state(agent_id)
        initial_heartbeat = initial_state.last_heartbeat

        # Wait a tiny bit and update heartbeat
        import asyncio
        await asyncio.sleep(0.01)
        await registry.update_heartbeat(agent_id)

        new_state = await registry.get_agent_state(agent_id)
        assert new_state.last_heartbeat > initial_heartbeat

    async def test_update_heartbeat_recovers_from_error(self, registry, sample_agent_config):
        """Test heartbeat updates recover agent from error status."""
        agent_id = await registry.register_agent(sample_agent_config)

        # Mark as error
        await registry.update_agent_status(agent_id, AgentStatus.ERROR, "Test error")

        # Update heartbeat should recover
        await registry.update_heartbeat(agent_id)

        state = await registry.get_agent_state(agent_id)
        assert state.status == AgentStatus.ACTIVE
        assert state.error_message is None

    async def test_increment_task_count_completed(self, registry, sample_agent_config):
        """Test incrementing completed task count."""
        agent_id = await registry.register_agent(sample_agent_config)

        await registry.increment_task_count(agent_id, completed=True)
        await registry.increment_task_count(agent_id, completed=True)

        state = await registry.get_agent_state(agent_id)
        assert state.tasks_completed == 2
        assert state.tasks_failed == 0

    async def test_increment_task_count_failed(self, registry, sample_agent_config):
        """Test incrementing failed task count."""
        agent_id = await registry.register_agent(sample_agent_config)

        await registry.increment_task_count(agent_id, completed=False)

        state = await registry.get_agent_state(agent_id)
        assert state.tasks_completed == 0
        assert state.tasks_failed == 1

    async def test_update_cost(self, registry, sample_agent_config):
        """Test updating agent cost."""
        agent_id = await registry.register_agent(sample_agent_config)

        await registry.update_cost(agent_id, 1.50)
        await registry.update_cost(agent_id, 2.25)

        state = await registry.get_agent_state(agent_id)
        assert state.total_cost_today == 3.75
        assert state.total_cost_month == 3.75

    async def test_check_cost_limit_within_limits(self, registry, sample_agent_config):
        """Test cost limit check when within limits."""
        agent_id = await registry.register_agent(sample_agent_config)

        await registry.update_cost(agent_id, 5.0)

        within_limit = await registry.check_cost_limit(agent_id)
        assert within_limit is True

    async def test_check_cost_limit_daily_exceeded(self, registry, sample_agent_config):
        """Test cost limit check when daily limit exceeded."""
        agent_id = await registry.register_agent(sample_agent_config)

        # Exceed daily limit (10.0)
        await registry.update_cost(agent_id, 15.0)

        within_limit = await registry.check_cost_limit(agent_id)
        assert within_limit is False

    async def test_check_cost_limit_monthly_exceeded(self, registry):
        """Test cost limit check when monthly limit exceeded."""
        config = AgentConfig(
            agent_id=uuid4(),
            name="Test Agent",
            capabilities=[
                AgentCapability(
                    name="test",
                    description="Test",
                    estimated_cost_per_call=0.01,
                )
            ],
            cost_limit_daily=1000.0,  # High daily limit
            cost_limit_monthly=50.0,   # Low monthly limit
        )
        agent_id = await registry.register_agent(config)

        # Exceed monthly limit
        await registry.update_cost(agent_id, 60.0)

        within_limit = await registry.check_cost_limit(agent_id)
        assert within_limit is False

    async def test_get_agent_metrics(self, registry, sample_agent_config):
        """Test getting agent metrics summary."""
        agent_id = await registry.register_agent(sample_agent_config)

        # Add some activity
        await registry.increment_task_count(agent_id, completed=True)
        await registry.increment_task_count(agent_id, completed=True)
        await registry.increment_task_count(agent_id, completed=False)
        await registry.update_cost(agent_id, 5.25)

        metrics = await registry.get_agent_metrics(agent_id)

        assert metrics is not None
        assert metrics["agent_id"] == str(agent_id)
        assert metrics["name"] == "Test Agent"
        assert metrics["tasks_completed"] == 2
        assert metrics["tasks_failed"] == 1
        assert metrics["success_rate"] == 2 / 3  # 66.67%
        assert metrics["cost_today"] == 5.25
        assert metrics["cost_month"] == 5.25

    async def test_get_agent_metrics_nonexistent(self, registry):
        """Test getting metrics for non-existent agent."""
        fake_id = uuid4()
        metrics = await registry.get_agent_metrics(fake_id)
        assert metrics is None

    async def test_cleanup_stale_agents(self, registry, sample_agent_config):
        """Test cleanup of stale agents."""
        agent_id = await registry.register_agent(sample_agent_config)

        # Manually set old heartbeat
        state = registry._agent_states[agent_id]
        state.last_heartbeat = datetime.utcnow() - timedelta(seconds=600)

        # Run cleanup with 300s timeout
        stale_count = await registry.cleanup_stale_agents(timeout_seconds=300)

        assert stale_count == 1

        # Check agent marked as error
        updated_state = await registry.get_agent_state(agent_id)
        assert updated_state.status == AgentStatus.ERROR
        assert "No heartbeat" in updated_state.error_message

    async def test_cleanup_stale_agents_no_stale(self, registry, sample_agent_config):
        """Test cleanup when no stale agents."""
        await registry.register_agent(sample_agent_config)

        stale_count = await registry.cleanup_stale_agents(timeout_seconds=300)

        assert stale_count == 0

    async def test_agent_metrics_success_rate_edge_cases(self, registry, sample_agent_config):
        """Test success rate calculation edge cases."""
        agent_id = await registry.register_agent(sample_agent_config)

        # No tasks completed - should be 0.0
        metrics = await registry.get_agent_metrics(agent_id)
        assert metrics["success_rate"] == 0.0

        # Only successful tasks - should be 1.0
        await registry.increment_task_count(agent_id, completed=True)
        metrics = await registry.get_agent_metrics(agent_id)
        assert metrics["success_rate"] == 1.0

        # Only failed tasks - should be 0.0
        agent2_config = AgentConfig(
            agent_id=uuid4(),
            name="Agent 2",
            capabilities=sample_agent_config.capabilities,
            cost_limit_daily=10.0,
            cost_limit_monthly=100.0,
        )
        agent2_id = await registry.register_agent(agent2_config)
        await registry.increment_task_count(agent2_id, completed=False)
        metrics2 = await registry.get_agent_metrics(agent2_id)
        assert metrics2["success_rate"] == 0.0


@pytest.mark.unit
class TestAgentRegistryGlobalInstance:
    """Test global registry instance management."""

    def test_get_registry_singleton(self):
        """Test that get_registry returns singleton instance."""
        from backend.orchestrator.registry import get_registry, _registry

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2
