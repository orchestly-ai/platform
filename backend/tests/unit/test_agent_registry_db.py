"""
Unit Tests for Agent Registry Database Persistence

Tests for agent registration, retrieval, and capability indexing with database storage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from backend.orchestrator.registry import AgentRegistry, get_registry
from backend.shared.models import AgentConfig, AgentState, AgentStatus, AgentCapability


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    def test_registry_initialization(self):
        """Test registry initializes with empty capability index."""
        registry = AgentRegistry()

        assert registry._capability_index == {}
        assert registry._cache_initialized is False

    def test_get_registry_singleton(self):
        """Test get_registry returns same instance."""
        # Reset global registry
        import backend.orchestrator.registry as reg_module
        reg_module._registry = None

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_capability_index_update_add(self):
        """Test updating capability index when adding agent."""
        registry = AgentRegistry()
        agent_id = uuid4()

        capabilities = [
            AgentCapability(name="code_review", description="Review code"),
            AgentCapability(name="testing", description="Run tests"),
        ]

        registry._update_capability_index(agent_id, capabilities, organization_id="default", add=True)

        assert agent_id in registry._capability_index.get(("default", "code_review"), [])
        assert agent_id in registry._capability_index.get(("default", "testing"), [])

    def test_capability_index_update_remove(self):
        """Test updating capability index when removing agent."""
        registry = AgentRegistry()
        agent_id = uuid4()

        # First add
        capabilities = [AgentCapability(name="code_review", description="Review code")]
        registry._update_capability_index(agent_id, capabilities, organization_id="default", add=True)

        assert agent_id in registry._capability_index[("default", "code_review")]

        # Then remove
        registry._update_capability_index(agent_id, capabilities, organization_id="default", add=False)

        assert agent_id not in registry._capability_index.get(("default", "code_review"), [])

    def test_capability_index_handles_dict_format(self):
        """Test capability index handles dict-formatted capabilities (from DB JSON)."""
        registry = AgentRegistry()
        agent_id = uuid4()

        # Dict format as stored in database JSON column
        capabilities = [
            {"name": "code_review", "description": "Review code", "parameters": {}},
            {"name": "testing", "description": "Run tests", "parameters": {}},
        ]

        registry._update_capability_index(agent_id, capabilities, organization_id="default", add=True)

        assert agent_id in registry._capability_index.get(("default", "code_review"), [])
        assert agent_id in registry._capability_index.get(("default", "testing"), [])

    def test_capability_index_no_duplicate_agents(self):
        """Test capability index doesn't add duplicate agent IDs."""
        registry = AgentRegistry()
        agent_id = uuid4()

        capabilities = [AgentCapability(name="code_review", description="Review code")]

        # Add twice
        registry._update_capability_index(agent_id, capabilities, organization_id="default", add=True)
        registry._update_capability_index(agent_id, capabilities, organization_id="default", add=True)

        # Should only appear once (set guarantees uniqueness)
        assert len(registry._capability_index[("default", "code_review")]) == 1
        assert agent_id in registry._capability_index[("default", "code_review")]


class TestAgentRegistryModelConversion:
    """Tests for model conversion methods."""

    def test_model_to_config_with_dict_capabilities(self):
        """Test converting database model to AgentConfig."""
        registry = AgentRegistry()

        # Mock database model
        agent_model = MagicMock()
        agent_model.agent_id = uuid4()
        agent_model.organization_id = "org_1"
        agent_model.name = "test-agent"
        agent_model.framework = "langchain"
        agent_model.version = "1.0.0"
        agent_model.capabilities = [
            {"name": "code_review", "description": "Review code", "input_schema": {"lang": "python"}},
        ]
        agent_model.max_concurrent_tasks = 5
        agent_model.cost_limit_daily = 100.0
        agent_model.cost_limit_monthly = 3000.0
        agent_model.llm_provider = "openai"
        agent_model.llm_model = "gpt-4"
        agent_model.extra_metadata = {"team": "platform"}

        config = registry._model_to_config(agent_model)

        assert config.agent_id == agent_model.agent_id
        assert config.name == "test-agent"
        assert config.framework == "langchain"
        assert len(config.capabilities) == 1
        assert config.capabilities[0].name == "code_review"
        assert config.capabilities[0].input_schema == {"lang": "python"}
        assert config.metadata == {"team": "platform"}

    def test_model_to_config_with_string_capabilities(self):
        """Test converting model with string-only capabilities."""
        registry = AgentRegistry()

        agent_model = MagicMock()
        agent_model.agent_id = uuid4()
        agent_model.organization_id = "org_1"
        agent_model.name = "test-agent"
        agent_model.framework = "autogen"
        agent_model.version = "1.0.0"
        agent_model.capabilities = ["capability1", "capability2"]  # String format
        agent_model.max_concurrent_tasks = 5
        agent_model.cost_limit_daily = 100.0
        agent_model.cost_limit_monthly = 3000.0
        agent_model.llm_provider = "anthropic"
        agent_model.llm_model = "claude-3"
        agent_model.extra_metadata = None

        config = registry._model_to_config(agent_model)

        assert len(config.capabilities) == 2
        assert config.capabilities[0].name == "capability1"
        assert config.capabilities[1].name == "capability2"
        assert config.metadata == {}

    def test_model_to_config_empty_metadata(self):
        """Test model conversion with None extra_metadata."""
        registry = AgentRegistry()

        agent_model = MagicMock()
        agent_model.agent_id = uuid4()
        agent_model.organization_id = "org_1"
        agent_model.name = "agent"
        agent_model.framework = "crewai"
        agent_model.version = "1.0"
        agent_model.capabilities = []
        agent_model.max_concurrent_tasks = 1
        agent_model.cost_limit_daily = 10.0
        agent_model.cost_limit_monthly = 100.0
        agent_model.llm_provider = "openai"
        agent_model.llm_model = None
        agent_model.extra_metadata = None

        config = registry._model_to_config(agent_model)

        assert config.metadata == {}


class TestAgentRegistryAsync:
    """Tests for async registry methods (mocked database)."""

    @pytest.mark.asyncio
    async def test_register_agent_creates_capability_index(self):
        """Test that registering agent updates capability index."""
        registry = AgentRegistry()
        registry._cache_initialized = True  # Skip DB cache init

        # Mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        agent_id = uuid4()
        config = AgentConfig(
            agent_id=agent_id,
            organization_id="org_1",
            name="test-agent",
            framework="langchain",
            version="1.0.0",
            capabilities=[
                AgentCapability(name="code_gen", description="Generate code"),
            ],
            max_concurrent_tasks=5,
            cost_limit_daily=100.0,
            cost_limit_monthly=3000.0,
        )

        result_id = await registry.register_agent(config, db=mock_db)

        assert result_id == agent_id
        assert agent_id in registry._capability_index.get(("org_1", "code_gen"), [])

    @pytest.mark.asyncio
    async def test_deregister_agent_removes_from_capability_index(self):
        """Test that deregistering agent removes from capability index."""
        registry = AgentRegistry()
        agent_id = uuid4()

        # Pre-populate capability index with org-scoped key
        registry._capability_index[("org_1", "code_gen")] = {agent_id}

        # Mock database with agent that has code_gen capability
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.organization_id = "org_1"
        mock_agent.capabilities = [{"name": "code_gen", "description": "Generate code"}]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_agent)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        await registry.deregister_agent(agent_id, db=mock_db)

        assert agent_id not in registry._capability_index.get(("org_1", "code_gen"), [])

    @pytest.mark.asyncio
    async def test_find_agents_by_capability_uses_index(self):
        """Test that find_agents_by_capability uses in-memory index."""
        registry = AgentRegistry()
        registry._cache_initialized = True

        agent1 = uuid4()
        agent2 = uuid4()
        agent3 = uuid4()

        # Pre-populate capability index with org-scoped keys
        registry._capability_index[("org_1", "code_review")] = {agent1, agent2}
        registry._capability_index[("org_1", "testing")] = {agent2, agent3}

        # Mock database for status filtering
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[(agent1,), (agent2,)])

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await registry.find_agents_by_capability(
            "code_review",
            organization_id="org_1",
            status=AgentStatus.ACTIVE,
            db=mock_db
        )

        assert len(result) == 2
        assert agent1 in result
        assert agent2 in result
