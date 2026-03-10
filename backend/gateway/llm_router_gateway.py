"""
LLM Router Gateway

Enhanced LLM Gateway with intelligent model routing.
Integrates the routing engine to automatically select optimal models.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from backend.gateway.llm_proxy import LLMGateway
from backend.router import get_routing_engine, get_health_monitor
from backend.router.strategies import RoutingRequest
from backend.shared.models import LLMResponse
from backend.database.session import get_db


class LLMRouterGateway(LLMGateway):
    """
    Enhanced LLM Gateway with intelligent routing.

    Extends the base LLM Gateway to automatically route requests to optimal models
    based on configured strategies.
    """

    def __init__(self):
        """Initialize LLM router gateway."""
        super().__init__()

        # Get routing components
        self.db = next(get_db())
        self.routing_engine = get_routing_engine(self.db)
        self.health_monitor = get_health_monitor(self.db)

    async def proxy_request_with_routing(
        self,
        agent_id: UUID,
        organization_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        task_id: Optional[UUID] = None,
        # Routing constraints
        min_quality: Optional[float] = None,
        max_cost: Optional[float] = None,
        require_vision: bool = False,
        require_tools: bool = False,
        max_latency_ms: Optional[int] = None,
        # Scope for strategy selection
        scope_type: str = "organization",
        scope_id: Optional[str] = None,
        # Optional manual override
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Proxy an LLM request with intelligent routing.

        If provider and model are not specified, the routing engine will select
        the optimal model based on the configured strategy and constraints.

        Args:
            agent_id: Agent making the request
            organization_id: Organization ID
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Max completion tokens
            task_id: Optional task ID for tracking
            min_quality: Minimum quality score (0-1)
            max_cost: Maximum cost per 1K tokens
            require_vision: Require vision support
            require_tools: Require function calling support
            max_latency_ms: Maximum acceptable latency
            scope_type: Scope for strategy selection
            scope_id: Scope ID (workflow or agent)
            provider: Optional manual provider override
            model: Optional manual model override

        Returns:
            LLMResponse with completion and metadata

        Raises:
            ValueError: If cost limit exceeded or no suitable model
            RuntimeError: If request fails
        """
        start_time = time.time()

        # If provider and model are not specified, use routing engine
        if not provider or not model:
            # Create routing request
            routing_request = RoutingRequest(
                min_quality=min_quality,
                max_cost=max_cost,
                require_vision=require_vision,
                require_tools=require_tools,
                max_latency_ms=max_latency_ms,
            )

            # Get routing decision
            decision = self.routing_engine.route(
                organization_id=organization_id,
                request=routing_request,
                scope_type=scope_type,
                scope_id=scope_id,
            )

            if not decision:
                raise ValueError(
                    "No suitable model found for the given constraints. "
                    "Please adjust your requirements or add more models."
                )

            provider = decision.provider
            model = decision.model_name

            print(f"🎯 Router selected: {provider}/{model} (strategy: {decision.strategy_used})")

        # Make the actual LLM request
        try:
            response = await self.proxy_request(
                agent_id=agent_id,
                provider=provider,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                task_id=task_id,
            )

            # Track success in health monitor
            latency_ms = int((time.time() - start_time) * 1000)

            # Get model ID for health tracking
            # Note: In production, you'd want to map provider/model to model_id
            # For now, we'll use a composite key
            model_key = f"{provider}:{model}"

            await self.health_monitor.track_request(
                model_id=model_key,
                latency_ms=latency_ms,
                success=True,
            )

            return response

        except Exception as e:
            # Track failure in health monitor
            latency_ms = int((time.time() - start_time) * 1000)
            model_key = f"{provider}:{model}"

            await self.health_monitor.track_request(
                model_id=model_key,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )

            raise


# Singleton instance
_router_gateway: Optional[LLMRouterGateway] = None


def get_router_gateway() -> LLMRouterGateway:
    """Get or create the LLM router gateway singleton."""
    global _router_gateway
    if _router_gateway is None:
        _router_gateway = LLMRouterGateway()
    return _router_gateway
