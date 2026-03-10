"""
Response Transformers for Frontend-Backend Integration

Transforms backend API responses to match frontend TypeScript expectations.
Addresses field name mismatches identified in TODO-001 of INTEGRATION_MASTER_PLAN.md
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime


class ResponseTransformer:
    """Utility class for transforming backend responses to frontend format."""

    @staticmethod
    def transform_cost_summary(backend_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform cost summary response from backend to frontend format.

        Backend fields:
        - total_cost, event_count, avg_cost_per_event
        - provider_breakdown, model_breakdown, category_breakdown
        - top_agents, top_workflows, top_users
        - vs_previous_period_percent

        Frontend expects:
        - today, thisWeek, thisMonth, lastMonth
        - byProvider, byModel, byCategory
        - trend, percentChange

        Args:
            backend_response: CostSummaryResponse from backend

        Returns:
            Transformed response matching frontend CostSummary interface
        """
        # For now, map total_cost to all time periods
        # In a real implementation, you'd query different time ranges
        total_cost = backend_response.get("total_cost", 0)

        # Calculate trend based on vs_previous_period_percent
        vs_previous = backend_response.get("vs_previous_period_percent", 0)
        if vs_previous is None:
            trend = "stable"
            percent_change = 0
        elif vs_previous > 5:
            trend = "up"
            percent_change = vs_previous
        elif vs_previous < -5:
            trend = "down"
            percent_change = vs_previous
        else:
            trend = "stable"
            percent_change = vs_previous

        return {
            "today": total_cost,
            "thisWeek": total_cost,
            "thisMonth": total_cost,
            "lastMonth": total_cost,  # Would need separate query for actual value
            "byProvider": backend_response.get("provider_breakdown", {}),
            "byModel": backend_response.get("model_breakdown", {}),
            "byCategory": backend_response.get("category_breakdown", {}),
            "trend": trend,
            "percentChange": percent_change,
            # Preserve additional backend fields for compatibility
            "organizationId": backend_response.get("organization_id"),
            "startTime": backend_response.get("start_time"),
            "endTime": backend_response.get("end_time"),
            "eventCount": backend_response.get("event_count", 0),
            "avgCostPerEvent": backend_response.get("avg_cost_per_event", 0),
            "topAgents": backend_response.get("top_agents", []),
            "topWorkflows": backend_response.get("top_workflows", []),
            "topUsers": backend_response.get("top_users", []),
        }

    @staticmethod
    def transform_llm_provider(backend_response: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
        """
        Transform LLM provider response from backend to frontend format.

        Backend fields:
        - provider (enum value like "openai", "anthropic")
        - name
        - is_active (boolean)
        - api_key_configured (boolean)
        - models (list of model names)
        - avg_latency_ms, success_rate, request_count

        Frontend expects:
        - id (string)
        - name
        - status ("active" | "inactive" | "error")
        - models (LLMModel[] or string[])
        - avgLatencyMs, successRate, requestsToday
        - circuitBreakerState

        Args:
            backend_response: LLMProviderResponse from backend (dict or ORM object)

        Returns:
            Transformed response matching frontend LLMProvider interface
        """
        # Handle both dict and ORM object
        if hasattr(backend_response, '__dict__'):
            # ORM object - convert to dict
            provider = backend_response.provider if hasattr(backend_response, 'provider') else None
            name = backend_response.name if hasattr(backend_response, 'name') else ""
            is_active = backend_response.is_active if hasattr(backend_response, 'is_active') else True
            api_key_configured = backend_response.api_key_configured if hasattr(backend_response, 'api_key_configured') else False
            avg_latency_ms = backend_response.avg_latency_ms if hasattr(backend_response, 'avg_latency_ms') else None
            success_rate = backend_response.success_rate if hasattr(backend_response, 'success_rate') else None
            request_count = backend_response.request_count if hasattr(backend_response, 'request_count') else None
            models = backend_response.models if hasattr(backend_response, 'models') else []
        else:
            # Dict object
            provider = backend_response.get("provider")
            name = backend_response.get("name", "")
            is_active = backend_response.get("is_active", True)
            api_key_configured = backend_response.get("api_key_configured", False)
            avg_latency_ms = backend_response.get("avg_latency_ms")
            success_rate = backend_response.get("success_rate")
            request_count = backend_response.get("request_count")
            models = backend_response.get("models", [])

        # Map is_active to status
        if not is_active:
            status = "inactive"
        elif not api_key_configured:
            status = "error"  # No API key configured
        else:
            status = "active"

        # Map provider enum to id (e.g., LLMProvider.OPENAI -> "openai")
        provider_id = str(provider.value) if hasattr(provider, 'value') else str(provider)

        # Default circuit breaker state
        circuit_breaker_state = "closed"
        if status == "error":
            circuit_breaker_state = "open"
        elif success_rate is not None and success_rate < 0.5:
            circuit_breaker_state = "half-open"

        return {
            "id": provider_id,
            "name": name,
            "status": status,
            "models": models,
            "avgLatencyMs": avg_latency_ms or 0,
            "successRate": success_rate or 0,
            "requestsToday": request_count or 0,
            "circuitBreakerState": circuit_breaker_state,
        }

    @staticmethod
    def transform_hitl_approval(backend_response: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
        """
        Transform HITL approval request from backend to frontend format.

        Backend fields:
        - id (or request_id)
        - title, description, priority, status
        - requested_by_user_id, created_at
        - required_approvers, required_approval_count
        - decision_made_by, decision_made_at, decision, decision_reason
        - expires_at, context

        Frontend expects:
        - id
        - type, title, description, priority, status
        - requestedBy, requestedAt
        - expiresAt, context
        - decidedBy, decidedAt, decision, decisionReason

        Args:
            backend_response: ApprovalRequestResponse from backend

        Returns:
            Transformed response matching frontend ApprovalRequest interface
        """
        # Handle both dict and ORM object
        if hasattr(backend_response, '__dict__'):
            request_id = backend_response.id if hasattr(backend_response, 'id') else None
            title = backend_response.title if hasattr(backend_response, 'title') else ""
            description = backend_response.description if hasattr(backend_response, 'description') else ""
            priority = backend_response.priority if hasattr(backend_response, 'priority') else "medium"
            status = backend_response.status if hasattr(backend_response, 'status') else "pending"
            requested_by = backend_response.requested_by_user_id if hasattr(backend_response, 'requested_by_user_id') else None
            created_at = backend_response.created_at if hasattr(backend_response, 'created_at') else None
            expires_at = backend_response.expires_at if hasattr(backend_response, 'expires_at') else None
            context = backend_response.context if hasattr(backend_response, 'context') else {}
            decision_made_by = backend_response.decision_made_by if hasattr(backend_response, 'decision_made_by') else None
            decision_made_at = backend_response.decision_made_at if hasattr(backend_response, 'decision_made_at') else None
            decision = backend_response.decision if hasattr(backend_response, 'decision') else None
            decision_reason = backend_response.decision_reason if hasattr(backend_response, 'decision_reason') else None
            request_type = backend_response.request_type if hasattr(backend_response, 'request_type') else "approval"
        else:
            request_id = backend_response.get("id") or backend_response.get("request_id")
            title = backend_response.get("title", "")
            description = backend_response.get("description", "")
            priority = backend_response.get("priority", "medium")
            status = backend_response.get("status", "pending")
            requested_by = backend_response.get("requested_by_user_id") or backend_response.get("requester_id")
            created_at = backend_response.get("created_at")
            expires_at = backend_response.get("expires_at")
            context = backend_response.get("context", {})
            decision_made_by = backend_response.get("decision_made_by")
            decision_made_at = backend_response.get("decision_made_at")
            decision = backend_response.get("decision")
            decision_reason = backend_response.get("decision_reason")
            request_type = backend_response.get("request_type", "approval")

        # Convert enum values to strings if needed
        if hasattr(priority, 'value'):
            priority = priority.value
        if hasattr(status, 'value'):
            status = status.value

        # Convert datetime to ISO string if needed
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        if isinstance(expires_at, datetime):
            expires_at = expires_at.isoformat()
        if isinstance(decision_made_at, datetime):
            decision_made_at = decision_made_at.isoformat()

        return {
            "id": str(request_id),
            "type": request_type,
            "title": title,
            "description": description,
            "priority": priority,
            "status": status,
            "requestedBy": requested_by,
            "requestedAt": created_at,
            "expiresAt": expires_at,
            "context": context,
            "decidedBy": decision_made_by,
            "decidedAt": decision_made_at,
            "decision": decision,
            "decisionReason": decision_reason,
        }

    @staticmethod
    def transform_audit_log_entry(backend_response: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
        """
        Transform audit log entry from backend to frontend format.

        Backend fields:
        - event_id
        - user_id, user_email, user_role
        - resource_type, resource_id, resource_name
        - ip_address, user_agent
        - action, description, timestamp
        - severity, success, error_message

        Frontend expects:
        - id
        - timestamp
        - action
        - actor (user_id)
        - resource (resource_type)
        - resourceId
        - details
        - severity
        - ipAddress
        - userAgent

        Args:
            backend_response: AuditEventResponse from backend

        Returns:
            Transformed response matching frontend AuditLogEntry interface
        """
        # Handle both dict and ORM object
        if hasattr(backend_response, '__dict__'):
            event_id = backend_response.event_id if hasattr(backend_response, 'event_id') else None
            timestamp = backend_response.timestamp if hasattr(backend_response, 'timestamp') else None
            action = backend_response.action if hasattr(backend_response, 'action') else ""
            user_id = backend_response.user_id if hasattr(backend_response, 'user_id') else None
            resource_type = backend_response.resource_type if hasattr(backend_response, 'resource_type') else None
            resource_id = backend_response.resource_id if hasattr(backend_response, 'resource_id') else None
            severity = backend_response.severity if hasattr(backend_response, 'severity') else "info"
            ip_address = backend_response.ip_address if hasattr(backend_response, 'ip_address') else None
            user_agent = backend_response.user_agent if hasattr(backend_response, 'user_agent') else None
            description = backend_response.description if hasattr(backend_response, 'description') else ""
            success = backend_response.success if hasattr(backend_response, 'success') else True
            error_message = backend_response.error_message if hasattr(backend_response, 'error_message') else None
            changes = backend_response.changes if hasattr(backend_response, 'changes') else None
        else:
            event_id = backend_response.get("event_id")
            timestamp = backend_response.get("timestamp")
            action = backend_response.get("action", "")
            user_id = backend_response.get("user_id")
            resource_type = backend_response.get("resource_type")
            resource_id = backend_response.get("resource_id")
            severity = backend_response.get("severity", "info")
            ip_address = backend_response.get("ip_address")
            user_agent = backend_response.get("user_agent")
            description = backend_response.get("description", "")
            success = backend_response.get("success", True)
            error_message = backend_response.get("error_message")
            changes = backend_response.get("changes")

        # Convert enum values to strings if needed
        if hasattr(severity, 'value'):
            severity = severity.value

        # Convert datetime to ISO string if needed
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()

        # Build details object
        details = {
            "description": description,
            "success": success,
        }
        if error_message:
            details["errorMessage"] = error_message
        if changes:
            details["changes"] = changes

        return {
            "id": str(event_id),
            "timestamp": timestamp,
            "action": action,
            "actor": user_id,
            "resource": resource_type,
            "resourceId": resource_id,
            "details": details,
            "severity": severity,
            "ipAddress": str(ip_address) if ip_address else None,
            "userAgent": user_agent,
        }

    @staticmethod
    def transform_list(
        backend_list: List[Any],
        transformer_func: callable
    ) -> List[Dict[str, Any]]:
        """
        Transform a list of backend responses using the specified transformer.

        Args:
            backend_list: List of backend responses
            transformer_func: Function to transform each item

        Returns:
            List of transformed responses
        """
        return [transformer_func(item) for item in backend_list]
