"""Unit tests for Triage Agent.

NOTE: These tests are for the example triage agent and are skipped as they're
part of the legacy test suite. See backend/tests/ for working tests.
"""
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip all tests in this module - legacy test suite
pytestmark = pytest.mark.skip(reason="Legacy tests - see backend/tests/ for working tests")

# Add examples to path
sys.path.insert(0, "examples/customer-support")
sys.path.insert(0, "sdk/python")

from agents.triage_agent import TriageAgent


@pytest.mark.unit
@pytest.mark.asyncio
class TestTriageAgent:
    """Test suite for TriageAgent."""

    @pytest.fixture
    def agent(self):
        """Create TriageAgent instance with mocked LLM."""
        with patch("agents.triage_agent.LLMClient") as mock_llm_class:
            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock()
            mock_llm_class.return_value = mock_llm

            agent = TriageAgent()
            agent.llm = mock_llm
            yield agent

    @pytest.fixture
    def sample_ticket(self):
        """Sample support ticket."""
        return {
            "ticket_id": "T-12345",
            "subject": "Cannot login to my account",
            "body": "I've been trying to login for the past hour but keep getting an error message.",
            "from": "customer@example.com",
            "channel": "email",
        }

    async def test_ticket_triage_faq_category(self, agent, sample_ticket):
        """Test triaging a FAQ ticket."""
        # Mock LLM response
        llm_response = {
            "category": "FAQ",
            "priority": "Normal",
            "summary": "Customer unable to login",
            "key_points": [
                "Login error",
                "Happening for past hour",
            ],
        }
        agent.llm.generate.return_value = json.dumps(llm_response)

        result = await agent.ticket_triage(sample_ticket)

        assert result["ticket_id"] == "T-12345"
        assert result["category"] == "FAQ"
        assert result["priority"] == "Normal"
        assert result["route_to"] == "faq_handling"
        assert result["summary"] == "Customer unable to login"
        assert len(result["key_points"]) == 2

    async def test_ticket_triage_technical_category(self, agent):
        """Test triaging a technical support ticket."""
        ticket = {
            "ticket_id": "T-67890",
            "subject": "API returning 500 errors",
            "body": "Our production API has been returning 500 errors for the past 30 minutes.",
            "from": "developer@company.com",
            "channel": "email",
        }

        llm_response = {
            "category": "Technical",
            "priority": "Critical",
            "summary": "Production API errors",
            "key_points": [
                "500 errors from API",
                "Started 30 minutes ago",
                "Affecting production",
            ],
        }
        agent.llm.generate.return_value = json.dumps(llm_response)

        result = await agent.ticket_triage(ticket)

        assert result["category"] == "Technical"
        assert result["priority"] == "Critical"
        assert result["route_to"] == "technical_support"

    async def test_ticket_triage_billing_category(self, agent):
        """Test triaging a billing ticket."""
        ticket = {
            "ticket_id": "T-11111",
            "subject": "Refund request",
            "body": "I was charged twice for my monthly subscription.",
            "from": "customer@example.com",
            "channel": "chat",
        }

        llm_response = {
            "category": "Billing",
            "priority": "High",
            "summary": "Double charge on subscription",
            "key_points": [
                "Charged twice",
                "Monthly subscription",
                "Requesting refund",
            ],
        }
        agent.llm.generate.return_value = json.dumps(llm_response)

        result = await agent.ticket_triage(ticket)

        assert result["category"] == "Billing"
        assert result["priority"] == "High"
        assert result["route_to"] == "billing_support"

    async def test_ticket_triage_other_category(self, agent):
        """Test triaging ticket with 'Other' category."""
        ticket = {
            "ticket_id": "T-22222",
            "subject": "Feature request",
            "body": "It would be great if you could add dark mode.",
            "from": "customer@example.com",
            "channel": "email",
        }

        llm_response = {
            "category": "Other",
            "priority": "Low",
            "summary": "Feature request for dark mode",
            "key_points": ["Dark mode feature request"],
        }
        agent.llm.generate.return_value = json.dumps(llm_response)

        result = await agent.ticket_triage(ticket)

        assert result["category"] == "Other"
        assert result["route_to"] == "human_escalation"

    async def test_ticket_triage_invalid_json_response(self, agent, sample_ticket):
        """Test handling of invalid JSON response from LLM."""
        # LLM returns invalid JSON
        agent.llm.generate.return_value = "This is not valid JSON"

        result = await agent.ticket_triage(sample_ticket)

        # Should fallback gracefully
        assert result["ticket_id"] == "T-12345"
        assert result["category"] == "Other"
        assert result["priority"] == "Normal"
        assert result["route_to"] == "human_escalation"
        assert result["summary"] == sample_ticket["subject"]

    async def test_ticket_triage_empty_ticket(self, agent):
        """Test triaging ticket with minimal data."""
        ticket = {
            "ticket_id": "T-99999",
        }

        llm_response = {
            "category": "Other",
            "priority": "Normal",
            "summary": "Empty ticket",
            "key_points": [],
        }
        agent.llm.generate.return_value = json.dumps(llm_response)

        result = await agent.ticket_triage(ticket)

        assert result["ticket_id"] == "T-99999"
        assert "category" in result
        assert "priority" in result

    async def test_ticket_triage_llm_called_with_correct_params(self, agent, sample_ticket):
        """Test that LLM is called with correct parameters."""
        llm_response = {"category": "FAQ", "priority": "Normal", "summary": "Test", "key_points": []}
        agent.llm.generate.return_value = json.dumps(llm_response)

        await agent.ticket_triage(sample_ticket)

        agent.llm.generate.assert_called_once()
        call_kwargs = agent.llm.generate.call_args[1]

        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 300
        assert "prompt" in call_kwargs
        assert sample_ticket["subject"] in call_kwargs["prompt"]
        assert sample_ticket["body"] in call_kwargs["prompt"]

    async def test_ticket_triage_route_mapping(self, agent):
        """Test all category to route mappings."""
        test_cases = [
            ("FAQ", "faq_handling"),
            ("Technical", "technical_support"),
            ("Billing", "billing_support"),
            ("Other", "human_escalation"),
            ("UnknownCategory", "human_escalation"),  # Default fallback
        ]

        for category, expected_route in test_cases:
            ticket = {
                "ticket_id": f"T-{category}",
                "subject": "Test",
                "body": "Test body",
            }

            llm_response = {
                "category": category,
                "priority": "Normal",
                "summary": "Test",
                "key_points": [],
            }
            agent.llm.generate.return_value = json.dumps(llm_response)

            result = await agent.ticket_triage(ticket)

            assert result["route_to"] == expected_route, f"Failed for category: {category}"

    async def test_ticket_triage_priority_levels(self, agent):
        """Test all priority levels are handled correctly."""
        priorities = ["Low", "Normal", "High", "Critical"]

        for priority in priorities:
            ticket = {
                "ticket_id": f"T-{priority}",
                "subject": "Test",
                "body": "Test body",
            }

            llm_response = {
                "category": "FAQ",
                "priority": priority,
                "summary": "Test",
                "key_points": [],
            }
            agent.llm.generate.return_value = json.dumps(llm_response)

            result = await agent.ticket_triage(ticket)

            assert result["priority"] == priority

    async def test_ticket_triage_missing_llm_fields(self, agent, sample_ticket):
        """Test handling when LLM response is missing expected fields."""
        # LLM returns incomplete response
        llm_response = {
            "category": "FAQ",
            # Missing priority, summary, key_points
        }
        agent.llm.generate.return_value = json.dumps(llm_response)

        result = await agent.ticket_triage(sample_ticket)

        # Should use defaults for missing fields
        assert result["category"] == "FAQ"
        assert result["priority"] == "Normal"  # Default
        assert result["summary"] == sample_ticket["subject"]  # Fallback
        assert result["key_points"] == []  # Default

    async def test_ticket_triage_preserves_ticket_id(self, agent):
        """Test that ticket_id is always preserved in output."""
        ticket_ids = ["T-12345", "TICKET-999", "ABC-123-XYZ"]

        llm_response = {"category": "FAQ", "priority": "Normal", "summary": "Test", "key_points": []}
        agent.llm.generate.return_value = json.dumps(llm_response)

        for ticket_id in ticket_ids:
            ticket = {
                "ticket_id": ticket_id,
                "subject": "Test",
                "body": "Test",
            }

            result = await agent.ticket_triage(ticket)

            assert result["ticket_id"] == ticket_id


@pytest.mark.unit
class TestTriageAgentConfiguration:
    """Test TriageAgent configuration and initialization."""

    def test_agent_initialization(self):
        """Test agent initializes correctly."""
        with patch("agents.triage_agent.LLMClient") as mock_llm_class:
            agent = TriageAgent()

            assert agent is not None
            mock_llm_class.assert_called_once_with(provider="openai", model="gpt-4o-mini")

    def test_agent_decorator_configuration(self):
        """Test that agent is configured with correct decorator parameters."""
        # This tests the @register_agent decorator configuration
        # The actual decorator application would be tested in integration tests
        assert hasattr(TriageAgent, "ticket_triage")
        assert callable(TriageAgent.ticket_triage)
