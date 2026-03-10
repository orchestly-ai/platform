"""
Mock Integration Provider for Sandbox Environment

Simulates external integrations (Slack, Salesforce, GitHub, etc.)
without actually connecting to external services.
"""

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class IntegrationType(Enum):
    """Supported mock integration types."""
    SLACK = "slack"
    SALESFORCE = "salesforce"
    GITHUB = "github"
    JIRA = "jira"
    ZENDESK = "zendesk"
    EMAIL = "email"
    HUBSPOT = "hubspot"
    NOTION = "notion"
    DATABASE = "database"
    WEBHOOK = "webhook"


@dataclass
class MockIntegrationResult:
    """Result from a mock integration call."""
    integration: str
    action: str
    success: bool
    data: Dict[str, Any]
    latency_ms: int
    error_message: Optional[str] = None


# Mock response templates for each integration
MOCK_INTEGRATION_RESPONSES = {
    "slack": {
        "send_message": {
            "data": {
                "ok": True,
                "channel": "C0123456789",
                "ts": "1234567890.123456",
                "message": {
                    "type": "message",
                    "subtype": "bot_message",
                    "text": "Message sent successfully",
                }
            }
        },
        "create_channel": {
            "data": {
                "ok": True,
                "channel": {
                    "id": "C0987654321",
                    "name": "new-channel",
                    "created": 1234567890,
                }
            }
        },
        "list_channels": {
            "data": {
                "ok": True,
                "channels": [
                    {"id": "C001", "name": "general", "is_private": False},
                    {"id": "C002", "name": "support", "is_private": False},
                    {"id": "C003", "name": "engineering", "is_private": False},
                ]
            }
        },
    },
    "salesforce": {
        "create_lead": {
            "data": {
                "id": "00Q5e000001234ABC",
                "success": True,
                "errors": [],
                "lead": {
                    "FirstName": "John",
                    "LastName": "Doe",
                    "Company": "Acme Corp",
                    "Status": "New",
                }
            }
        },
        "update_opportunity": {
            "data": {
                "id": "0065e000002345DEF",
                "success": True,
                "opportunity": {
                    "Name": "Acme Corp - Enterprise Deal",
                    "StageName": "Proposal",
                    "Amount": 250000,
                }
            }
        },
        "query": {
            "data": {
                "totalSize": 3,
                "done": True,
                "records": [
                    {"Id": "001", "Name": "Account 1", "Industry": "Technology"},
                    {"Id": "002", "Name": "Account 2", "Industry": "Finance"},
                    {"Id": "003", "Name": "Account 3", "Industry": "Healthcare"},
                ]
            }
        },
    },
    "github": {
        "create_issue": {
            "data": {
                "id": 12345,
                "number": 42,
                "title": "New Issue",
                "state": "open",
                "html_url": "https://github.com/org/repo/issues/42",
            }
        },
        "create_pull_request": {
            "data": {
                "id": 67890,
                "number": 100,
                "title": "New Pull Request",
                "state": "open",
                "html_url": "https://github.com/org/repo/pull/100",
            }
        },
        "add_comment": {
            "data": {
                "id": 11111,
                "body": "Comment added successfully",
                "created_at": "2025-01-15T10:00:00Z",
            }
        },
    },
    "jira": {
        "create_issue": {
            "data": {
                "id": "10001",
                "key": "PROJ-123",
                "self": "https://company.atlassian.net/rest/api/3/issue/10001",
            }
        },
        "update_issue": {
            "data": {
                "id": "10001",
                "key": "PROJ-123",
                "success": True,
                "transition": {
                    "from": "To Do",
                    "to": "In Progress",
                }
            }
        },
        "add_comment": {
            "data": {
                "id": "20001",
                "body": "Comment added via AgentOrch",
                "author": {"displayName": "AI Agent"},
            }
        },
    },
    "zendesk": {
        "create_ticket": {
            "data": {
                "ticket": {
                    "id": 35436,
                    "status": "new",
                    "subject": "Support Request",
                    "priority": "normal",
                    "created_at": "2025-01-15T10:00:00Z",
                }
            }
        },
        "update_ticket": {
            "data": {
                "ticket": {
                    "id": 35436,
                    "status": "pending",
                    "updated_at": "2025-01-15T10:30:00Z",
                }
            }
        },
        "add_internal_note": {
            "data": {
                "audit": {
                    "id": 99887,
                    "ticket_id": 35436,
                    "created_at": "2025-01-15T10:15:00Z",
                }
            }
        },
    },
    "email": {
        "send": {
            "data": {
                "message_id": "msg_abc123xyz789",
                "status": "sent",
                "to": ["recipient@example.com"],
                "subject": "Subject Line",
                "sent_at": "2025-01-15T10:00:00Z",
            }
        },
        "send_template": {
            "data": {
                "message_id": "msg_def456uvw012",
                "status": "sent",
                "template_id": "welcome_email",
                "variables_used": ["name", "company"],
            }
        },
    },
    "hubspot": {
        "create_contact": {
            "data": {
                "id": "123456",
                "properties": {
                    "email": "contact@example.com",
                    "firstname": "John",
                    "lastname": "Doe",
                    "company": "Acme Inc",
                }
            }
        },
        "update_deal": {
            "data": {
                "id": "789012",
                "properties": {
                    "dealname": "Enterprise Deal",
                    "amount": "100000",
                    "dealstage": "contractsent",
                }
            }
        },
    },
    "notion": {
        "create_page": {
            "data": {
                "id": "page_abc123",
                "url": "https://notion.so/page_abc123",
                "created_time": "2025-01-15T10:00:00Z",
            }
        },
        "update_database": {
            "data": {
                "id": "db_xyz789",
                "success": True,
                "updated_entries": 1,
            }
        },
    },
    "database": {
        "query": {
            "data": {
                "rows": [
                    {"id": 1, "name": "Record 1", "value": 100},
                    {"id": 2, "name": "Record 2", "value": 200},
                ],
                "count": 2,
                "execution_time_ms": 15,
            }
        },
        "insert": {
            "data": {
                "inserted_id": 123,
                "success": True,
                "affected_rows": 1,
            }
        },
        "update": {
            "data": {
                "success": True,
                "affected_rows": 1,
            }
        },
    },
    "webhook": {
        "post": {
            "data": {
                "status_code": 200,
                "response_time_ms": 150,
                "body": {"received": True, "processed": True},
            }
        },
        "get": {
            "data": {
                "status_code": 200,
                "response_time_ms": 100,
                "body": {"data": "sample response"},
            }
        },
    },
}


class MockIntegrationProvider:
    """
    Mock integration provider for sandbox environment.

    Simulates external integrations without actual connections.
    """

    def __init__(
        self,
        simulate_latency: bool = True,
        failure_rate: float = 0.0,
        latency_range: tuple = (50, 300),
    ):
        """
        Initialize mock integration provider.

        Args:
            simulate_latency: Whether to simulate network latency
            failure_rate: Probability of simulated failures
            latency_range: Min/max latency in milliseconds
        """
        self.simulate_latency = simulate_latency
        self.failure_rate = failure_rate
        self.latency_range = latency_range
        self.call_history: List[Dict[str, Any]] = []

    async def execute(
        self,
        integration: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> MockIntegrationResult:
        """
        Execute a mock integration action.

        Args:
            integration: Integration name (slack, salesforce, etc.)
            action: Action to perform (send_message, create_lead, etc.)
            params: Parameters for the action
            **kwargs: Additional parameters

        Returns:
            MockIntegrationResult with simulated response
        """
        start_time = datetime.utcnow()

        # Simulate latency
        if self.simulate_latency:
            latency_ms = random.randint(*self.latency_range)
            await asyncio.sleep(latency_ms / 1000)
        else:
            latency_ms = 10

        # Simulate failure
        if random.random() < self.failure_rate:
            error_msg = f"Simulated {integration} API failure"
            self._record_call(integration, action, False, latency_ms, error_msg)
            return MockIntegrationResult(
                integration=integration,
                action=action,
                success=False,
                data={},
                latency_ms=latency_ms,
                error_message=error_msg,
            )

        # Get mock response
        response_data = self._get_mock_response(integration, action, params)

        # Enrich response with dynamic data
        enriched_data = self._enrich_response(response_data, params)

        # Record call
        self._record_call(integration, action, True, latency_ms)

        return MockIntegrationResult(
            integration=integration,
            action=action,
            success=True,
            data=enriched_data,
            latency_ms=latency_ms,
        )

    def _get_mock_response(
        self,
        integration: str,
        action: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get mock response for integration action."""
        integration = integration.lower()
        action = action.lower()

        if integration in MOCK_INTEGRATION_RESPONSES:
            actions = MOCK_INTEGRATION_RESPONSES[integration]
            if action in actions:
                return actions[action].get("data", {})

        # Generic fallback
        return {
            "success": True,
            "integration": integration,
            "action": action,
            "message": "Operation completed successfully",
        }

    def _enrich_response(
        self,
        response: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enrich response with dynamic data from params."""
        if not params:
            return response

        # Deep copy to avoid modifying template
        result = dict(response)

        # Inject dynamic values
        if "channel" in params:
            if "channel" in result:
                result["channel"] = params["channel"]
        if "message" in params:
            if isinstance(result.get("message"), dict):
                result["message"]["text"] = params["message"]

        # Add timestamp
        result["_sandbox_timestamp"] = datetime.utcnow().isoformat()

        return result

    def _record_call(
        self,
        integration: str,
        action: str,
        success: bool,
        latency_ms: int,
        error: Optional[str] = None
    ):
        """Record call to history."""
        self.call_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "integration": integration,
            "action": action,
            "success": success,
            "latency_ms": latency_ms,
            "error": error,
        })

    def get_supported_integrations(self) -> List[Dict[str, Any]]:
        """Get list of supported mock integrations."""
        return [
            {
                "name": "Slack",
                "id": "slack",
                "actions": ["send_message", "create_channel", "list_channels"],
                "status": "connected",
            },
            {
                "name": "Salesforce",
                "id": "salesforce",
                "actions": ["create_lead", "update_opportunity", "query"],
                "status": "connected",
            },
            {
                "name": "GitHub",
                "id": "github",
                "actions": ["create_issue", "create_pull_request", "add_comment"],
                "status": "connected",
            },
            {
                "name": "Jira",
                "id": "jira",
                "actions": ["create_issue", "update_issue", "add_comment"],
                "status": "connected",
            },
            {
                "name": "Zendesk",
                "id": "zendesk",
                "actions": ["create_ticket", "update_ticket", "add_internal_note"],
                "status": "connected",
            },
            {
                "name": "Email",
                "id": "email",
                "actions": ["send", "send_template"],
                "status": "connected",
            },
            {
                "name": "HubSpot",
                "id": "hubspot",
                "actions": ["create_contact", "update_deal"],
                "status": "connected",
            },
            {
                "name": "Notion",
                "id": "notion",
                "actions": ["create_page", "update_database"],
                "status": "connected",
            },
        ]

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        if not self.call_history:
            return {
                "total_calls": 0,
                "successful": 0,
                "failed": 0,
                "by_integration": {},
            }

        successful = sum(1 for c in self.call_history if c["success"])
        return {
            "total_calls": len(self.call_history),
            "successful": successful,
            "failed": len(self.call_history) - successful,
            "by_integration": self._aggregate_by_integration(),
        }

    def _aggregate_by_integration(self) -> Dict[str, Any]:
        """Aggregate stats by integration."""
        result = {}
        for call in self.call_history:
            key = call["integration"]
            if key not in result:
                result[key] = {"calls": 0, "successful": 0, "failed": 0}
            result[key]["calls"] += 1
            if call["success"]:
                result[key]["successful"] += 1
            else:
                result[key]["failed"] += 1
        return result

    def reset_history(self):
        """Reset call history."""
        self.call_history = []


# Singleton for demo use
_mock_integration_provider: Optional[MockIntegrationProvider] = None


def get_mock_integration_provider() -> MockIntegrationProvider:
    """Get or create the mock integration provider singleton."""
    global _mock_integration_provider
    if _mock_integration_provider is None:
        _mock_integration_provider = MockIntegrationProvider()
    return _mock_integration_provider
