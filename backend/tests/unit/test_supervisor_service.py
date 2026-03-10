"""
Unit Tests for Supervisor Orchestration Service

Tests for task decomposition, routing strategies, and multi-agent execution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from backend.shared.supervisor_service import (
    TaskDecompositionService, RoutingService, SupervisorExecutionService
)
from backend.shared.supervisor_models import (
    SupervisorConfig, SupervisorExecution, Agent, TaskAssignment,
    SupervisorMode, RoutingStrategy, AgentRole, TaskStatus
)


class TestTaskDecomposition:
    """Tests for TaskDecompositionService."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return TaskDecompositionService(mock_db)

    @pytest.fixture
    def sample_agents(self):
        return [
            Agent(
                agent_id="agent_1",
                organization_id="org_1",
                name="Research Agent",
                role=AgentRole.SPECIALIST,
                capabilities=["research", "analysis"]
            ),
            Agent(
                agent_id="agent_2",
                organization_id="org_1",
                name="Writer Agent",
                role=AgentRole.WORKER,
                capabilities=["writing", "editing"]
            ),
            Agent(
                agent_id="agent_3",
                organization_id="org_1",
                name="Review Agent",
                role=AgentRole.REVIEWER,
                capabilities=["review", "quality"]
            ),
        ]

    @pytest.fixture
    def sample_config(self):
        return SupervisorConfig(
            config_id=uuid4(),
            organization_id="org_1",
            name="Test Supervisor",
            mode=SupervisorMode.SEQUENTIAL,
            routing_strategy=RoutingStrategy.CAPABILITY_MATCH,
            agent_pool=["agent_1", "agent_2", "agent_3"]
        )

    def test_build_agent_summary(self, service, sample_agents):
        """Test building agent summary for LLM prompt."""
        summary = service._build_agent_summary(sample_agents)

        assert "Research Agent" in summary
        assert "specialist" in summary
        assert "research" in summary or "analysis" in summary

    def test_default_decomposition_prompt(self, service):
        """Test default decomposition prompt contains required elements."""
        prompt = service._default_decomposition_prompt()

        assert "task decomposition" in prompt.lower()
        assert "{task}" in prompt
        assert "{agent_summary}" in prompt

    @pytest.mark.asyncio
    async def test_decompose_research_task(self, service, sample_config, sample_agents):
        """Test decomposition of research task."""
        task = "Research the latest trends in AI and analyze their impact on business"

        subtasks = await service.decompose_task(
            task=task,
            config=sample_config,
            agent_pool=sample_agents
        )

        assert len(subtasks) >= 3
        assert any("research" in st.get("type", "").lower() for st in subtasks)
        assert any("analysis" in st.get("type", "").lower() for st in subtasks)

    @pytest.mark.asyncio
    async def test_decompose_writing_task(self, service, sample_config, sample_agents):
        """Test decomposition of writing task."""
        task = "Write a blog post about machine learning"

        subtasks = await service.decompose_task(
            task=task,
            config=sample_config,
            agent_pool=sample_agents
        )

        assert len(subtasks) >= 3
        types = [st.get("type", "") for st in subtasks]
        assert "planning" in types or "writing" in types

    @pytest.mark.asyncio
    async def test_decompose_coding_task(self, service, sample_config, sample_agents):
        """Test decomposition of coding task."""
        task = "Implement a REST API endpoint for user authentication"

        subtasks = await service.decompose_task(
            task=task,
            config=sample_config,
            agent_pool=sample_agents
        )

        assert len(subtasks) >= 3
        types = [st.get("type", "") for st in subtasks]
        assert "design" in types or "coding" in types

    @pytest.mark.asyncio
    async def test_decompose_generic_task(self, service, sample_config, sample_agents):
        """Test decomposition of generic task."""
        task = "Complete this project milestone"

        subtasks = await service.decompose_task(
            task=task,
            config=sample_config,
            agent_pool=sample_agents
        )

        # Should get default 3-step decomposition
        assert len(subtasks) == 3

    @pytest.mark.asyncio
    async def test_subtasks_have_dependencies(self, service, sample_config, sample_agents):
        """Test that decomposed tasks have proper dependency chains."""
        task = "Research market trends and create a report"

        subtasks = await service.decompose_task(
            task=task,
            config=sample_config,
            agent_pool=sample_agents
        )

        # Check that later tasks depend on earlier ones
        first_task = subtasks[0]
        later_tasks = subtasks[1:]

        for task in later_tasks:
            deps = task.get("dependencies", [])
            # At least some tasks should have dependencies
            if deps:
                assert first_task["id"] in deps or any(t["id"] in deps for t in subtasks)


class TestRoutingService:
    """Tests for RoutingService."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return RoutingService(mock_db)

    @pytest.fixture
    def sample_agents(self):
        return [
            Agent(
                agent_id="agent_1",
                organization_id="org_1",
                name="Python Expert",
                role=AgentRole.SPECIALIST,
                capabilities=["python", "data_analysis"],
                specialization="data_science",
                is_active=True,
                current_load=2,
                max_concurrent_tasks=5,
                success_rate=0.95
            ),
            Agent(
                agent_id="agent_2",
                organization_id="org_1",
                name="Writer",
                role=AgentRole.WORKER,
                capabilities=["writing", "research"],
                specialization="content",
                is_active=True,
                current_load=1,
                max_concurrent_tasks=5,
                success_rate=0.88
            ),
            Agent(
                agent_id="agent_3",
                organization_id="org_1",
                name="Reviewer",
                role=AgentRole.REVIEWER,
                capabilities=["review", "editing"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=3,
                success_rate=0.92
            ),
        ]

    @pytest.mark.asyncio
    async def test_route_round_robin(self, service, sample_agents):
        """Test round robin routing distributes evenly."""
        task = {"id": "task_1", "description": "Any task", "type": "general"}

        agents_selected = []
        for _ in range(6):
            agent, reason, confidence = await service._route_round_robin(task, sample_agents)
            agents_selected.append(agent.agent_id)

        # Should cycle through all agents
        assert "agent_1" in agents_selected
        assert "agent_2" in agents_selected
        assert "agent_3" in agents_selected

    @pytest.mark.asyncio
    async def test_route_round_robin_no_agents(self, service):
        """Test round robin with no agents raises error."""
        task = {"id": "task_1", "description": "Any task"}

        with pytest.raises(ValueError, match="No agents available"):
            await service._route_round_robin(task, [])

    @pytest.mark.asyncio
    async def test_route_capability_match(self, service, sample_agents):
        """Test capability-based routing."""
        task = {
            "id": "task_1",
            "description": "Analyze data using python",
            "type": "data_analysis",
            "suggested_agent_role": "specialist"
        }

        agent, reason, confidence = await service._route_capability_match(task, sample_agents)

        # Should pick the Python Expert agent
        assert agent.agent_id == "agent_1"
        assert "capability" in reason.lower()

    @pytest.mark.asyncio
    async def test_route_capability_match_writing(self, service, sample_agents):
        """Test capability matching for writing task."""
        task = {
            "id": "task_2",
            "description": "Write a blog post about AI",
            "type": "writing",
            "suggested_agent_role": "worker"
        }

        agent, reason, confidence = await service._route_capability_match(task, sample_agents)

        # Should pick the Writer agent
        assert agent.agent_id == "agent_2"

    @pytest.mark.asyncio
    async def test_route_load_balanced(self, service, sample_agents):
        """Test load-balanced routing picks least busy agent."""
        task = {"id": "task_1", "description": "Any task"}

        agent, reason, confidence = await service._route_load_balanced(task, sample_agents)

        # agent_3 has load 0, should be picked
        assert agent.agent_id == "agent_3"
        assert "least busy" in reason.lower()

    @pytest.mark.asyncio
    async def test_route_priority_based_high(self, service, sample_agents):
        """Test priority-based routing for high priority task."""
        task = {"id": "task_1", "description": "Urgent task", "priority": 9}

        agent, reason, confidence = await service._route_priority_based(task, sample_agents)

        # High priority should go to specialist
        assert agent.role == AgentRole.SPECIALIST
        assert "high priority" in reason.lower()

    @pytest.mark.asyncio
    async def test_route_priority_based_medium(self, service, sample_agents):
        """Test priority-based routing for medium priority task."""
        task = {"id": "task_1", "description": "Regular task", "priority": 5}

        agent, reason, confidence = await service._route_priority_based(task, sample_agents)

        # Medium priority should go to worker
        assert agent.role == AgentRole.WORKER

    @pytest.mark.asyncio
    async def test_route_custom_rules(self, service, sample_agents):
        """Test custom rule-based routing."""
        task = {"id": "task_1", "description": "Write content for marketing", "type": "content"}

        routing_rules = [
            {"if": "content", "route_to": "agent_2"},
            {"if": "python", "route_to": "agent_1"}
        ]

        agent, reason, confidence = await service._route_custom_rules(
            task, sample_agents, routing_rules
        )

        assert agent.agent_id == "agent_2"
        assert "custom rule" in reason.lower()

    @pytest.mark.asyncio
    async def test_route_custom_rules_no_match(self, service, sample_agents):
        """Test custom rules fallback when no match."""
        task = {"id": "task_1", "description": "Random task", "type": "unknown"}

        routing_rules = [
            {"if": "python", "route_to": "agent_1"}
        ]

        # Should fallback to capability match
        agent, reason, confidence = await service._route_custom_rules(
            task, sample_agents, routing_rules
        )

        assert agent is not None

    @pytest.mark.asyncio
    async def test_route_task_dispatcher(self, service, sample_agents):
        """Test main route_task dispatcher method."""
        task = {"id": "task_1", "description": "Test task"}

        # Test each strategy
        for strategy in RoutingStrategy:
            agent, reason, confidence = await service.route_task(
                task=task,
                agent_pool=sample_agents,
                strategy=strategy
            )

            assert agent is not None
            assert isinstance(reason, str)
            assert 0 <= confidence <= 1


class TestSupervisorExecution:
    """Tests for SupervisorExecutionService."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return SupervisorExecutionService(mock_db)

    @pytest.fixture
    def sample_config(self):
        return SupervisorConfig(
            config_id=uuid4(),
            organization_id="org_1",
            name="Test Supervisor",
            mode=SupervisorMode.SEQUENTIAL,
            routing_strategy=RoutingStrategy.CAPABILITY_MATCH,
            agent_pool=["agent_1", "agent_2"],
            auto_decompose_tasks=True,
            max_agents_concurrent=3
        )

    @pytest.fixture
    def sample_agents(self):
        return [
            Agent(
                agent_id="agent_1",
                organization_id="org_1",
                name="Agent 1",
                role=AgentRole.WORKER,
                capabilities=["general"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=5
            ),
            Agent(
                agent_id="agent_2",
                organization_id="org_1",
                name="Agent 2",
                role=AgentRole.WORKER,
                capabilities=["general"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=5
            ),
        ]

    def test_topological_sort_tasks(self, service):
        """Test topological sorting of tasks with dependencies."""
        tasks = [
            {"id": "task_3", "description": "Third", "dependencies": ["task_2"]},
            {"id": "task_1", "description": "First", "dependencies": []},
            {"id": "task_2", "description": "Second", "dependencies": ["task_1"]},
        ]

        sorted_tasks = service._topological_sort_tasks(tasks)

        task_ids = [t["id"] for t in sorted_tasks]
        assert task_ids.index("task_1") < task_ids.index("task_2")
        assert task_ids.index("task_2") < task_ids.index("task_3")

    def test_topological_sort_parallel_tasks(self, service):
        """Test topological sort with parallel tasks."""
        tasks = [
            {"id": "task_1", "description": "First", "dependencies": []},
            {"id": "task_2a", "description": "Parallel A", "dependencies": ["task_1"]},
            {"id": "task_2b", "description": "Parallel B", "dependencies": ["task_1"]},
            {"id": "task_3", "description": "Third", "dependencies": ["task_2a", "task_2b"]},
        ]

        sorted_tasks = service._topological_sort_tasks(tasks)

        task_ids = [t["id"] for t in sorted_tasks]
        assert task_ids.index("task_1") < task_ids.index("task_2a")
        assert task_ids.index("task_1") < task_ids.index("task_2b")
        assert task_ids.index("task_2a") < task_ids.index("task_3")
        assert task_ids.index("task_2b") < task_ids.index("task_3")

    def test_group_tasks_by_dependency_level(self, service):
        """Test grouping tasks by dependency level for parallel execution."""
        tasks = [
            {"id": "task_1", "dependencies": []},
            {"id": "task_2a", "dependencies": ["task_1"]},
            {"id": "task_2b", "dependencies": ["task_1"]},
            {"id": "task_3", "dependencies": ["task_2a", "task_2b"]},
        ]

        levels = service._group_tasks_by_dependency_level(tasks)

        # Level 0: task_1
        assert len(levels[0]) == 1
        assert levels[0][0]["id"] == "task_1"

        # Level 1: task_2a and task_2b
        assert len(levels[1]) == 2
        level1_ids = [t["id"] for t in levels[1]]
        assert "task_2a" in level1_ids
        assert "task_2b" in level1_ids

        # Level 2: task_3
        assert len(levels[2]) == 1
        assert levels[2][0]["id"] == "task_3"

    @pytest.mark.asyncio
    async def test_simulate_task_execution(self, service, sample_agents):
        """Test simulated task execution."""
        assignment = TaskAssignment(
            assignment_id=uuid4(),
            execution_id=uuid4(),
            agent_id="agent_1",
            task_id="task_1",
            task_description="Test task",
            status=TaskStatus.PENDING
        )

        result = await service._simulate_task_execution(assignment, sample_agents[0])

        assert result["status"] == "completed"
        assert "agent_1" in result["agent"]


class TestAgentDataclass:
    """Tests for Agent dataclass."""

    def test_agent_creation(self):
        """Test creating an Agent."""
        agent = Agent(
            agent_id="test_agent",
            organization_id="org_1",
            name="Test Agent",
            role=AgentRole.WORKER,
            capabilities=["python", "testing"],
            is_active=True
        )

        assert agent.agent_id == "test_agent"
        assert agent.role == AgentRole.WORKER
        assert "python" in agent.capabilities

    def test_agent_default_values(self):
        """Test Agent default values."""
        agent = Agent(
            agent_id="minimal_agent",
            organization_id="org_1",
            name="Minimal",
            role=AgentRole.WORKER
        )

        assert agent.max_concurrent_tasks == 5
        assert agent.is_active == True
        assert agent.current_load == 0
        assert agent.capabilities == []


class TestSupervisorConfig:
    """Tests for SupervisorConfig dataclass."""

    def test_config_creation(self):
        """Test creating a SupervisorConfig."""
        config = SupervisorConfig(
            config_id=uuid4(),
            organization_id="org_1",
            name="Test Supervisor",
            mode=SupervisorMode.CONCURRENT,
            routing_strategy=RoutingStrategy.LOAD_BALANCED,
            agent_pool=["agent_1", "agent_2", "agent_3"]
        )

        assert config.mode == SupervisorMode.CONCURRENT
        assert config.routing_strategy == RoutingStrategy.LOAD_BALANCED
        assert len(config.agent_pool) == 3

    def test_config_default_values(self):
        """Test SupervisorConfig default values."""
        config = SupervisorConfig(
            config_id=uuid4(),
            organization_id="org_1",
            name="Default Config",
            mode=SupervisorMode.SEQUENTIAL,
            routing_strategy=RoutingStrategy.ROUND_ROBIN,
            agent_pool=[]
        )

        assert config.max_agents_concurrent == 3
        assert config.timeout_seconds == 300
        assert config.auto_decompose_tasks == True
        assert config.llm_temperature == 0.7


class TestTaskAssignment:
    """Tests for TaskAssignment dataclass."""

    def test_assignment_creation(self):
        """Test creating a TaskAssignment."""
        assignment = TaskAssignment(
            assignment_id=uuid4(),
            execution_id=uuid4(),
            agent_id="agent_1",
            task_id="task_1",
            task_description="Complete this task",
            status=TaskStatus.PENDING,
            priority=5
        )

        assert assignment.status == TaskStatus.PENDING
        assert assignment.priority == 5
        assert assignment.retry_count == 0

    def test_assignment_with_dependencies(self):
        """Test TaskAssignment with dependencies."""
        assignment = TaskAssignment(
            assignment_id=uuid4(),
            execution_id=uuid4(),
            agent_id="agent_1",
            task_id="task_3",
            task_description="Final task",
            status=TaskStatus.BLOCKED,
            depends_on=["task_1", "task_2"],
            blocks=["task_4"]
        )

        assert "task_1" in assignment.depends_on
        assert "task_4" in assignment.blocks


class TestSupervisorModeConfigs:
    """Tests for supervisor mode configurations."""

    def test_all_modes_have_config(self):
        """Test that all SupervisorMode enums have configuration."""
        from backend.shared.supervisor_models import SUPERVISOR_MODE_CONFIGS

        for mode in SupervisorMode:
            assert mode.value in SUPERVISOR_MODE_CONFIGS

    def test_mode_config_structure(self):
        """Test mode config has required fields."""
        from backend.shared.supervisor_models import SUPERVISOR_MODE_CONFIGS

        for mode_key, config in SUPERVISOR_MODE_CONFIGS.items():
            assert "name" in config
            assert "description" in config
            assert "use_cases" in config
            assert "supports_parallel" in config


class TestRoutingStrategyConfigs:
    """Tests for routing strategy configurations."""

    def test_all_strategies_have_config(self):
        """Test that all RoutingStrategy enums have configuration."""
        from backend.shared.supervisor_models import ROUTING_STRATEGY_CONFIGS

        for strategy in RoutingStrategy:
            assert strategy.value in ROUTING_STRATEGY_CONFIGS

    def test_strategy_config_structure(self):
        """Test strategy config has required fields."""
        from backend.shared.supervisor_models import ROUTING_STRATEGY_CONFIGS

        for strategy_key, config in ROUTING_STRATEGY_CONFIGS.items():
            assert "name" in config
            assert "description" in config
            assert "complexity" in config


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
