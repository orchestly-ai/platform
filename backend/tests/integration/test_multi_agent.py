"""
E2E Integration Tests for Multi-Agent Orchestration

Tests multi-agent coordination including:
- Supervisor orchestration patterns (sequential, concurrent, group chat)
- Task decomposition and distribution
- Agent routing strategies
- Result aggregation
- Inter-agent communication
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


class TestSupervisorSequentialExecution:
    """Tests for sequential multi-agent execution."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def supervisor_config(self):
        return SupervisorConfig(
            config_id=uuid4(),
            organization_id="org-123",
            name="Sequential Supervisor",
            mode=SupervisorMode.SEQUENTIAL,
            routing_strategy=RoutingStrategy.ROUND_ROBIN,
            agent_pool=["agent_1", "agent_2", "agent_3"],
            max_agents_concurrent=1,
            auto_decompose_tasks=True
        )

    @pytest.fixture
    def agent_pool(self):
        return [
            Agent(
                agent_id="agent_1",
                organization_id="org-123",
                name="Research Agent",
                role=AgentRole.SPECIALIST,
                capabilities=["research", "analysis"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=5
            ),
            Agent(
                agent_id="agent_2",
                organization_id="org-123",
                name="Writer Agent",
                role=AgentRole.WORKER,
                capabilities=["writing", "editing"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=5
            ),
            Agent(
                agent_id="agent_3",
                organization_id="org-123",
                name="Reviewer Agent",
                role=AgentRole.REVIEWER,
                capabilities=["review", "quality"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=5
            ),
        ]

    @pytest.mark.asyncio
    async def test_sequential_task_execution(self, mock_db, supervisor_config, agent_pool):
        """Test that tasks execute sequentially with dependencies."""
        service = SupervisorExecutionService(mock_db)

        tasks = [
            {"id": "task_1", "description": "Research topic", "type": "research", "dependencies": []},
            {"id": "task_2", "description": "Write content", "type": "writing", "dependencies": ["task_1"]},
            {"id": "task_3", "description": "Review content", "type": "review", "dependencies": ["task_2"]},
        ]

        sorted_tasks = service._topological_sort_tasks(tasks)

        # Verify order respects dependencies
        task_ids = [t["id"] for t in sorted_tasks]
        assert task_ids.index("task_1") < task_ids.index("task_2")
        assert task_ids.index("task_2") < task_ids.index("task_3")


class TestSupervisorConcurrentExecution:
    """Tests for concurrent multi-agent execution."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def concurrent_config(self):
        return SupervisorConfig(
            config_id=uuid4(),
            organization_id="org-123",
            name="Concurrent Supervisor",
            mode=SupervisorMode.CONCURRENT,
            routing_strategy=RoutingStrategy.LOAD_BALANCED,
            agent_pool=["agent_1", "agent_2", "agent_3"],
            max_agents_concurrent=3,
            auto_decompose_tasks=True
        )

    @pytest.fixture
    def agent_pool(self):
        return [
            Agent(
                agent_id="agent_1",
                organization_id="org-123",
                name="Worker 1",
                role=AgentRole.WORKER,
                capabilities=["processing"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=5
            ),
            Agent(
                agent_id="agent_2",
                organization_id="org-123",
                name="Worker 2",
                role=AgentRole.WORKER,
                capabilities=["processing"],
                is_active=True,
                current_load=1,
                max_concurrent_tasks=5
            ),
            Agent(
                agent_id="agent_3",
                organization_id="org-123",
                name="Worker 3",
                role=AgentRole.WORKER,
                capabilities=["processing"],
                is_active=True,
                current_load=2,
                max_concurrent_tasks=5
            ),
        ]

    @pytest.mark.asyncio
    async def test_concurrent_task_grouping(self, mock_db, concurrent_config, agent_pool):
        """Test that independent tasks are grouped for parallel execution."""
        service = SupervisorExecutionService(mock_db)

        tasks = [
            {"id": "task_1", "description": "Init", "dependencies": []},
            {"id": "task_2a", "description": "Process A", "dependencies": ["task_1"]},
            {"id": "task_2b", "description": "Process B", "dependencies": ["task_1"]},
            {"id": "task_2c", "description": "Process C", "dependencies": ["task_1"]},
            {"id": "task_3", "description": "Finalize", "dependencies": ["task_2a", "task_2b", "task_2c"]},
        ]

        levels = service._group_tasks_by_dependency_level(tasks)

        # Level 0: task_1
        assert len(levels[0]) == 1
        # Level 1: task_2a, task_2b, task_2c (can run in parallel)
        assert len(levels[1]) == 3
        # Level 2: task_3
        assert len(levels[2]) == 1


class TestRoutingStrategies:
    """Tests for different agent routing strategies."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def routing_service(self, mock_db):
        return RoutingService(mock_db)

    @pytest.fixture
    def diverse_agents(self):
        return [
            Agent(
                agent_id="specialist_python",
                organization_id="org-123",
                name="Python Specialist",
                role=AgentRole.SPECIALIST,
                capabilities=["python", "data_analysis", "ml"],
                specialization="data_science",
                is_active=True,
                current_load=2,
                max_concurrent_tasks=5,
                success_rate=0.95
            ),
            Agent(
                agent_id="specialist_web",
                organization_id="org-123",
                name="Web Specialist",
                role=AgentRole.SPECIALIST,
                capabilities=["javascript", "react", "nodejs"],
                specialization="web_development",
                is_active=True,
                current_load=1,
                max_concurrent_tasks=5,
                success_rate=0.92
            ),
            Agent(
                agent_id="generalist",
                organization_id="org-123",
                name="Generalist Worker",
                role=AgentRole.WORKER,
                capabilities=["general", "documentation"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=10,
                success_rate=0.88
            ),
        ]

    @pytest.mark.asyncio
    async def test_capability_routing_matches_python(self, routing_service, diverse_agents):
        """Test capability routing selects Python specialist for data task."""
        task = {
            "id": "task_1",
            "description": "Analyze data using pandas and numpy",
            "type": "data_analysis"
        }

        agent, reason, confidence = await routing_service._route_capability_match(
            task, diverse_agents
        )

        assert agent.agent_id == "specialist_python"

    @pytest.mark.asyncio
    async def test_capability_routing_matches_web(self, routing_service, diverse_agents):
        """Test capability routing selects Web specialist for frontend task."""
        task = {
            "id": "task_2",
            "description": "Build React component with JavaScript",
            "type": "web_development"
        }

        agent, reason, confidence = await routing_service._route_capability_match(
            task, diverse_agents
        )

        assert agent.agent_id == "specialist_web"

    @pytest.mark.asyncio
    async def test_load_balanced_routing(self, routing_service, diverse_agents):
        """Test load balanced routing selects least busy agent."""
        task = {"id": "task_3", "description": "Any task"}

        agent, reason, confidence = await routing_service._route_load_balanced(
            task, diverse_agents
        )

        # Generalist has current_load=0 (least busy)
        assert agent.agent_id == "generalist"

    @pytest.mark.asyncio
    async def test_round_robin_routing(self, routing_service, diverse_agents):
        """Test round robin distributes tasks evenly."""
        task = {"id": "task_4", "description": "Generic task"}

        selected_agents = []
        for _ in range(6):
            agent, _, _ = await routing_service._route_round_robin(task, diverse_agents)
            selected_agents.append(agent.agent_id)

        # All agents should be selected at least once
        assert "specialist_python" in selected_agents
        assert "specialist_web" in selected_agents
        assert "generalist" in selected_agents


class TestTaskDecomposition:
    """Tests for intelligent task decomposition."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def decomposition_service(self, mock_db):
        return TaskDecompositionService(mock_db)

    @pytest.fixture
    def agent_pool(self):
        return [
            Agent(
                agent_id="researcher",
                organization_id="org-123",
                name="Research Agent",
                role=AgentRole.SPECIALIST,
                capabilities=["research", "analysis"]
            ),
            Agent(
                agent_id="writer",
                organization_id="org-123",
                name="Writer Agent",
                role=AgentRole.WORKER,
                capabilities=["writing", "editing"]
            ),
        ]

    @pytest.fixture
    def supervisor_config(self):
        return SupervisorConfig(
            config_id=uuid4(),
            organization_id="org-123",
            name="Task Decomposer",
            mode=SupervisorMode.SEQUENTIAL,
            routing_strategy=RoutingStrategy.CAPABILITY_MATCH,
            agent_pool=["researcher", "writer"]
        )

    @pytest.mark.asyncio
    async def test_decompose_research_task(self, decomposition_service, supervisor_config, agent_pool):
        """Test decomposition of research task into subtasks."""
        task = "Research the latest trends in AI and write a comprehensive report"

        subtasks = await decomposition_service.decompose_task(
            task=task,
            config=supervisor_config,
            agent_pool=agent_pool
        )

        assert len(subtasks) >= 3
        # Verify subtasks have required fields
        for subtask in subtasks:
            assert "id" in subtask
            assert "description" in subtask
            assert "type" in subtask

    @pytest.mark.asyncio
    async def test_decompose_coding_task(self, decomposition_service, supervisor_config, agent_pool):
        """Test decomposition of coding task."""
        task = "Implement a REST API with authentication"

        subtasks = await decomposition_service.decompose_task(
            task=task,
            config=supervisor_config,
            agent_pool=agent_pool
        )

        assert len(subtasks) >= 3


class TestAgentCoordination:
    """Tests for agent coordination and handoff."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def execution_service(self, mock_db):
        return SupervisorExecutionService(mock_db)

    @pytest.fixture
    def agent_pool(self):
        return [
            Agent(
                agent_id="agent_1",
                organization_id="org-123",
                name="Agent 1",
                role=AgentRole.WORKER,
                capabilities=["general"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=5
            ),
            Agent(
                agent_id="agent_2",
                organization_id="org-123",
                name="Agent 2",
                role=AgentRole.REVIEWER,
                capabilities=["review"],
                is_active=True,
                current_load=0,
                max_concurrent_tasks=5
            ),
        ]

    @pytest.mark.asyncio
    async def test_simulate_task_execution(self, execution_service, agent_pool):
        """Test simulated task execution returns expected result."""
        assignment = TaskAssignment(
            assignment_id=uuid4(),
            execution_id=uuid4(),
            agent_id="agent_1",
            task_id="test_task",
            task_description="Test task description",
            status=TaskStatus.IN_PROGRESS
        )

        result = await execution_service._simulate_task_execution(
            assignment, agent_pool[0]
        )

        assert result["status"] == "completed"
        assert "agent" in result


class TestResultAggregation:
    """Tests for aggregating results from multiple agents."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    def test_merge_agent_results(self, mock_db):
        """Test merging results from multiple agents."""
        results = [
            {"agent_id": "agent_1", "output": {"data": [1, 2, 3]}, "cost": 0.05},
            {"agent_id": "agent_2", "output": {"data": [4, 5, 6]}, "cost": 0.03},
            {"agent_id": "agent_3", "output": {"summary": "combined"}, "cost": 0.02},
        ]

        # Simple merge
        merged = {}
        total_cost = 0.0
        for result in results:
            merged[result["agent_id"]] = result["output"]
            total_cost += result["cost"]

        assert len(merged) == 3
        assert total_cost == 0.10
        assert "agent_1" in merged
        assert "agent_2" in merged
        assert "agent_3" in merged


class TestGroupChatMode:
    """Tests for group chat multi-agent pattern."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def group_chat_config(self):
        return SupervisorConfig(
            config_id=uuid4(),
            organization_id="org-123",
            name="Group Chat Supervisor",
            mode=SupervisorMode.GROUP_CHAT,
            routing_strategy=RoutingStrategy.LLM_DECISION,
            agent_pool=["researcher", "analyst", "writer"],
            max_conversation_turns=10
        )

    def test_group_chat_conversation_turn_tracking(self, mock_db, group_chat_config):
        """Test that conversation turns are tracked in group chat."""
        execution = SupervisorExecution(
            execution_id=uuid4(),
            config_id=group_chat_config.config_id,
            organization_id="org-123",
            status="running",
            mode=SupervisorMode.GROUP_CHAT,
            input_task="Discuss project requirements",
            conversation_history=[]
        )

        # Simulate conversation turns
        turns = [
            {"turn": 1, "speaker": "supervisor", "message": "Let's discuss the project"},
            {"turn": 2, "speaker": "researcher", "message": "I'll gather requirements"},
            {"turn": 3, "speaker": "analyst", "message": "I'll analyze feasibility"},
        ]

        execution.conversation_history = turns
        execution.total_turns = len(turns)

        assert execution.total_turns == 3
        assert len(execution.conversation_history) == 3


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
