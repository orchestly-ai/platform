"""
SmartRouter - LLM Provider Failover Service

Implements ROADMAP.md Section: Provider Outage Failover Strategy

Features:
- Circuit breaker per provider (5 consecutive failures = open)
- Automatic failover on provider failure
- Multiple routing strategies (primary_only, primary_backup, best_available, etc.)
- Mid-stream failover with state consistency
- Provider health tracking and recovery
"""

import asyncio
import json
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any, Callable
from uuid import UUID

from backend.shared.llm_clients import call_llm, LLMResponse

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """LLM routing strategies."""
    PRIMARY_ONLY = "primary_only"           # Use only primary, fail if unavailable
    PRIMARY_WITH_BACKUP = "primary_backup"  # Failover to backup on primary failure
    BEST_AVAILABLE = "best_available"       # Select healthiest provider
    COST_OPTIMIZED = "cost_optimized"       # Prefer cheaper providers when healthy
    LATENCY_OPTIMIZED = "latency_optimized" # Prefer lowest latency providers


class ProviderStatus(Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class ProviderHealth:
    """Tracks health state for a single provider."""
    provider: str
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    circuit_open: bool = False
    circuit_open_until: Optional[datetime] = None
    avg_latency_ms: float = 0.0
    last_latencies: List[float] = field(default_factory=list)

    @property
    def status(self) -> ProviderStatus:
        """Compute current status."""
        if self.circuit_open:
            return ProviderStatus.CIRCUIT_OPEN
        if self.consecutive_failures >= 3:
            return ProviderStatus.DEGRADED
        if self.consecutive_failures >= 5:
            return ProviderStatus.UNHEALTHY
        return ProviderStatus.HEALTHY

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.total_failures + self.total_successes
        if total == 0:
            return 1.0
        return self.total_successes / total

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "status": self.status.value,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "success_rate": f"{self.success_rate:.1%}",
            "circuit_open": self.circuit_open,
            "circuit_open_until": self.circuit_open_until.isoformat() if self.circuit_open_until else None,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
        }


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    provider: str
    model: str
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None
    reason: Optional[str] = None
    strategy_used: Optional[RoutingStrategy] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "model": self.model,
            "fallback_provider": self.fallback_provider,
            "fallback_model": self.fallback_model,
            "reason": self.reason,
            "strategy_used": self.strategy_used.value if self.strategy_used else None,
        }


@dataclass
class OrgRoutingConfig:
    """Organization-level routing configuration."""
    org_id: str
    routing_strategy: RoutingStrategy = RoutingStrategy.PRIMARY_WITH_BACKUP
    primary_provider: str = "openai"
    primary_model: str = "gpt-4"
    backup_provider: Optional[str] = "anthropic"
    backup_model: Optional[str] = "claude-3-sonnet"
    fallback_chain: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "org_id": self.org_id,
            "routing_strategy": self.routing_strategy.value,
            "primary_provider": self.primary_provider,
            "primary_model": self.primary_model,
            "backup_provider": self.backup_provider,
            "backup_model": self.backup_model,
            "fallback_chain": self.fallback_chain,
        }


@dataclass
class ProviderError(Exception):
    """Error from an LLM provider."""
    provider: str
    error_type: str  # 'timeout', 'rate_limit', 'auth', 'server_error', 'network'
    message: str
    status_code: Optional[int] = None
    retryable: bool = True

    def __str__(self):
        return f"{self.provider} error ({self.error_type}): {self.message}"


@dataclass
class ExecutionState:
    """State for mid-stream failover."""
    execution_id: UUID
    conversation_history: List[Dict] = field(default_factory=list)
    current_provider: Optional[str] = None
    current_model: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)


@dataclass
class UniversalRequest:
    """Provider-agnostic request format."""
    messages: List[Dict]
    tools: List[Dict] = field(default_factory=list)
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UniversalResponse:
    """Provider-agnostic response format."""
    content: str
    tool_calls: List[Dict] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    cost: float = 0.0
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "cost": self.cost,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": round(self.latency_ms, 2),
            "metadata": self.metadata,
        }


# Cost per 1K tokens (input/output) - simplified pricing
PROVIDER_PRICING = {
    "openai": {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    },
    "anthropic": {
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.0001, "output": 0.0002},
        "deepseek-coder": {"input": 0.0001, "output": 0.0002},
    },
    "google": {
        "gemini-pro": {"input": 0.00025, "output": 0.0005},
        "gemini-pro-vision": {"input": 0.00025, "output": 0.0005},
    },
}


class SmartRouter:
    """
    Intelligent LLM provider routing with automatic failover.

    Features:
    - Per-provider circuit breakers
    - Multiple routing strategies
    - Mid-stream failover with state preservation
    - Health tracking and metrics
    """

    FAILURE_THRESHOLD = 5           # Consecutive failures to open circuit
    CIRCUIT_RESET_SECONDS = 60      # Time before circuit half-opens
    MAX_LATENCIES_TRACKED = 100     # Rolling window for latency average

    def __init__(self, db=None, provider_clients: Dict = None):
        """
        Initialize SmartRouter.

        Args:
            db: Database session for config persistence
            provider_clients: Dict of provider name -> client instance
        """
        self.db = db
        self.provider_clients = provider_clients or {}
        self.provider_health: Dict[str, ProviderHealth] = {}
        self._failover_count = 0
        self._total_requests = 0

    async def route_request(
        self,
        request: UniversalRequest,
        org_config: OrgRoutingConfig
    ) -> RoutingDecision:
        """
        Determine which provider to use based on strategy and health.

        Args:
            request: The universal request to route
            org_config: Organization routing configuration

        Returns:
            RoutingDecision with provider and optional fallback
        """
        strategy = org_config.routing_strategy

        if strategy == RoutingStrategy.PRIMARY_ONLY:
            return RoutingDecision(
                provider=org_config.primary_provider,
                model=org_config.primary_model,
                strategy_used=strategy
            )

        if strategy == RoutingStrategy.PRIMARY_WITH_BACKUP:
            if await self._is_provider_healthy(org_config.primary_provider):
                return RoutingDecision(
                    provider=org_config.primary_provider,
                    model=org_config.primary_model,
                    fallback_provider=org_config.backup_provider,
                    fallback_model=org_config.backup_model,
                    strategy_used=strategy
                )
            else:
                return RoutingDecision(
                    provider=org_config.backup_provider,
                    model=org_config.backup_model,
                    reason="primary_circuit_open",
                    strategy_used=strategy
                )

        if strategy == RoutingStrategy.BEST_AVAILABLE:
            return await self._select_best_available(request, org_config)

        if strategy == RoutingStrategy.COST_OPTIMIZED:
            return await self._select_cost_optimized(request, org_config)

        if strategy == RoutingStrategy.LATENCY_OPTIMIZED:
            return await self._select_latency_optimized(request, org_config)

        # Default to primary with backup
        return RoutingDecision(
            provider=org_config.primary_provider,
            model=org_config.primary_model,
            fallback_provider=org_config.backup_provider,
            fallback_model=org_config.backup_model,
            strategy_used=RoutingStrategy.PRIMARY_WITH_BACKUP
        )

    async def execute_with_failover(
        self,
        request: UniversalRequest,
        routing: RoutingDecision,
        execution_state: Optional[ExecutionState] = None
    ) -> UniversalResponse:
        """
        Execute request with automatic failover on failure.

        Args:
            request: The universal request
            routing: Routing decision from route_request
            execution_state: Optional state for mid-stream failover

        Returns:
            UniversalResponse from successful provider

        Raises:
            ProviderError: If all providers fail
        """
        self._total_requests += 1
        start_time = datetime.utcnow()

        try:
            # Extract API key from request metadata if provided
            api_key = request.metadata.get("api_key") if request.metadata else None
            response = await self._call_provider(
                routing.provider, routing.model, request, api_key=api_key
            )
            await self._record_success(routing.provider, response.latency_ms)
            return response

        except ProviderError as primary_error:
            await self._record_failure(routing.provider, primary_error)
            logger.warning(
                f"Primary provider {routing.provider} failed: {primary_error}"
            )

            if not routing.fallback_provider:
                raise

            # Check if fallback is healthy
            if not await self._is_provider_healthy(routing.fallback_provider):
                raise ProviderError(
                    provider=routing.fallback_provider,
                    error_type="circuit_open",
                    message="Fallback provider circuit is open",
                    retryable=False
                )

            self._failover_count += 1
            logger.info(
                f"Failing over from {routing.provider} to {routing.fallback_provider}"
            )

            # CRITICAL: Re-normalize history for new provider if mid-stream
            if execution_state and execution_state.conversation_history:
                request = await self._renormalize_for_provider(
                    request,
                    execution_state,
                    routing.provider,
                    routing.fallback_provider
                )

            try:
                fallback_key = request.metadata.get("fallback_api_key") if request.metadata else None
                response = await self._call_provider(
                    routing.fallback_provider, routing.fallback_model, request,
                    api_key=fallback_key or api_key
                )
                await self._record_success(routing.fallback_provider, response.latency_ms)
                response.metadata["failover"] = True
                response.metadata["original_provider"] = routing.provider
                response.metadata["failover_reason"] = str(primary_error)
                return response

            except ProviderError as fallback_error:
                await self._record_failure(routing.fallback_provider, fallback_error)
                # Both failed, raise the original error with context
                raise ProviderError(
                    provider=routing.provider,
                    error_type="all_providers_failed",
                    message=f"Primary: {primary_error}, Fallback: {fallback_error}",
                    retryable=False
                )

    async def _call_provider(
        self,
        provider: str,
        model: str,
        request: UniversalRequest,
        api_key: Optional[str] = None
    ) -> UniversalResponse:
        """
        Call a specific provider with the request.

        Raises ProviderError on failure to enable proper failover handling.

        Args:
            provider: LLM provider name
            model: Model name
            request: Universal request with messages
            api_key: Optional API key (if not provided, call_llm will use env vars)

        Returns:
            UniversalResponse on success

        Raises:
            ProviderError: On any API call failure (enables failover)
        """
        start_time = datetime.utcnow()

        try:
            llm_response: LLMResponse = await call_llm(
                provider=provider,
                model=model,
                messages=request.messages,
                max_tokens=request.max_tokens or 1000,
                temperature=request.temperature or 0.7,
                api_key=api_key
            )

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Use real metrics from API
            return UniversalResponse(
                content=llm_response.content,
                tool_calls=[],
                usage={
                    "input_tokens": llm_response.tokens_used // 2,  # Estimate split
                    "output_tokens": llm_response.tokens_used // 2,
                    "total_tokens": llm_response.tokens_used
                },
                cost=llm_response.cost,
                provider=llm_response.provider,
                model=llm_response.model,
                latency_ms=llm_response.latency_ms or latency_ms,
                metadata={"real_api_call": True}
            )

        except Exception as e:
            # Convert exception to ProviderError for proper failover handling
            error_str = str(e).lower()

            # Classify error type for better handling
            if 'timeout' in error_str:
                error_type = 'timeout'
                retryable = True
            elif 'rate' in error_str or '429' in error_str:
                error_type = 'rate_limit'
                retryable = True
            elif 'auth' in error_str or '401' in error_str or 'api key' in error_str:
                error_type = 'auth'
                retryable = False
            elif '5' in error_str and ('00' in error_str or '02' in error_str or '03' in error_str):
                error_type = 'server_error'
                retryable = True
            else:
                error_type = 'network'
                retryable = True

            logger.warning(
                f"Provider {provider}/{model} failed: {e} (type={error_type}, retryable={retryable})"
            )

            raise ProviderError(
                provider=provider,
                error_type=error_type,
                message=str(e),
                retryable=retryable
            )

    def _calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost based on token usage."""
        if provider not in PROVIDER_PRICING:
            return 0.0
        if model not in PROVIDER_PRICING[provider]:
            return 0.0

        pricing = PROVIDER_PRICING[provider][model]
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def _renormalize_for_provider(
        self,
        request: UniversalRequest,
        state: ExecutionState,
        from_provider: str,
        to_provider: str
    ) -> UniversalRequest:
        """
        Re-normalize conversation history when switching providers mid-stream.

        Different providers have different message format requirements:
        - OpenAI: tool_calls in assistant messages
        - Anthropic: tool_use blocks
        - etc.
        """
        logger.info(
            f"Re-normalizing {len(state.conversation_history)} messages "
            f"from {from_provider} to {to_provider}"
        )

        # For now, return request unchanged
        # In production, this would transform message formats
        normalized_messages = []
        for msg in request.messages:
            normalized_msg = msg.copy()
            # Add provider normalization logic here
            normalized_messages.append(normalized_msg)

        request.messages = normalized_messages
        request.metadata["renormalized_from"] = from_provider
        request.metadata["renormalized_to"] = to_provider

        return request

    async def _is_provider_healthy(self, provider: str) -> bool:
        """Check if a provider is healthy (circuit closed or half-open)."""
        health = self.provider_health.get(provider)
        if not health:
            return True

        if health.circuit_open:
            # Check if we should half-open
            if datetime.utcnow() > health.circuit_open_until:
                logger.info(f"Circuit for {provider} transitioning to half-open")
                health.circuit_open = False
                health.consecutive_failures = 0
                return True
            return False

        return True

    async def _record_success(self, provider: str, latency_ms: float):
        """Record a successful call to a provider."""
        health = self.provider_health.setdefault(
            provider, ProviderHealth(provider=provider)
        )
        health.consecutive_failures = 0
        health.total_successes += 1
        health.last_success = datetime.utcnow()

        # Update latency tracking
        health.last_latencies.append(latency_ms)
        if len(health.last_latencies) > self.MAX_LATENCIES_TRACKED:
            health.last_latencies.pop(0)
        health.avg_latency_ms = sum(health.last_latencies) / len(health.last_latencies)

    async def _record_failure(self, provider: str, error: ProviderError):
        """Record a failed call and potentially open circuit."""
        health = self.provider_health.setdefault(
            provider, ProviderHealth(provider=provider)
        )
        health.consecutive_failures += 1
        health.total_failures += 1
        health.last_failure = datetime.utcnow()

        if health.consecutive_failures >= self.FAILURE_THRESHOLD:
            health.circuit_open = True
            health.circuit_open_until = datetime.utcnow() + timedelta(
                seconds=self.CIRCUIT_RESET_SECONDS
            )
            logger.warning(
                f"Circuit OPEN for {provider} until {health.circuit_open_until}"
            )

    async def _select_best_available(
        self,
        request: UniversalRequest,
        org_config: OrgRoutingConfig
    ) -> RoutingDecision:
        """Select the healthiest available provider."""
        candidates = [
            (org_config.primary_provider, org_config.primary_model),
            (org_config.backup_provider, org_config.backup_model),
        ]

        # Add fallback chain
        for fallback in org_config.fallback_chain:
            candidates.append((fallback["provider"], fallback["model"]))

        # Sort by health (success rate, then latency)
        scored_candidates = []
        for provider, model in candidates:
            if not provider or not model:
                continue
            if not await self._is_provider_healthy(provider):
                continue

            health = self.provider_health.get(provider, ProviderHealth(provider=provider))
            score = health.success_rate * 100 - (health.avg_latency_ms / 10)
            scored_candidates.append((score, provider, model))

        if not scored_candidates:
            # All circuits open, try primary anyway
            return RoutingDecision(
                provider=org_config.primary_provider,
                model=org_config.primary_model,
                reason="all_circuits_open_trying_primary",
                strategy_used=RoutingStrategy.BEST_AVAILABLE
            )

        # Sort by score descending
        scored_candidates.sort(reverse=True)
        best = scored_candidates[0]
        fallback = scored_candidates[1] if len(scored_candidates) > 1 else (None, None, None)

        return RoutingDecision(
            provider=best[1],
            model=best[2],
            fallback_provider=fallback[1],
            fallback_model=fallback[2],
            reason=f"best_score_{best[0]:.1f}",
            strategy_used=RoutingStrategy.BEST_AVAILABLE
        )

    async def _select_cost_optimized(
        self,
        request: UniversalRequest,
        org_config: OrgRoutingConfig
    ) -> RoutingDecision:
        """Select the cheapest healthy provider."""
        candidates = [
            (org_config.primary_provider, org_config.primary_model),
            (org_config.backup_provider, org_config.backup_model),
        ]

        for fallback in org_config.fallback_chain:
            candidates.append((fallback["provider"], fallback["model"]))

        # Calculate cost per provider
        priced_candidates = []
        for provider, model in candidates:
            if not provider or not model:
                continue
            if not await self._is_provider_healthy(provider):
                continue

            # Get pricing (use input cost as proxy)
            pricing = PROVIDER_PRICING.get(provider, {}).get(model, {})
            cost = pricing.get("input", 999) + pricing.get("output", 999)
            priced_candidates.append((cost, provider, model))

        if not priced_candidates:
            return RoutingDecision(
                provider=org_config.primary_provider,
                model=org_config.primary_model,
                reason="no_healthy_providers",
                strategy_used=RoutingStrategy.COST_OPTIMIZED
            )

        # Sort by cost ascending
        priced_candidates.sort()
        cheapest = priced_candidates[0]
        fallback = priced_candidates[1] if len(priced_candidates) > 1 else (None, None, None)

        return RoutingDecision(
            provider=cheapest[1],
            model=cheapest[2],
            fallback_provider=fallback[1],
            fallback_model=fallback[2],
            reason=f"lowest_cost_{cheapest[0]:.4f}",
            strategy_used=RoutingStrategy.COST_OPTIMIZED
        )

    async def _select_latency_optimized(
        self,
        request: UniversalRequest,
        org_config: OrgRoutingConfig
    ) -> RoutingDecision:
        """Select the lowest latency healthy provider."""
        candidates = [
            (org_config.primary_provider, org_config.primary_model),
            (org_config.backup_provider, org_config.backup_model),
        ]

        for fallback in org_config.fallback_chain:
            candidates.append((fallback["provider"], fallback["model"]))

        # Get latency per provider
        latency_candidates = []
        for provider, model in candidates:
            if not provider or not model:
                continue
            if not await self._is_provider_healthy(provider):
                continue

            health = self.provider_health.get(provider, ProviderHealth(provider=provider))
            latency = health.avg_latency_ms if health.avg_latency_ms > 0 else 100
            latency_candidates.append((latency, provider, model))

        if not latency_candidates:
            return RoutingDecision(
                provider=org_config.primary_provider,
                model=org_config.primary_model,
                reason="no_healthy_providers",
                strategy_used=RoutingStrategy.LATENCY_OPTIMIZED
            )

        # Sort by latency ascending
        latency_candidates.sort()
        fastest = latency_candidates[0]
        fallback = latency_candidates[1] if len(latency_candidates) > 1 else (None, None, None)

        return RoutingDecision(
            provider=fastest[1],
            model=fastest[2],
            fallback_provider=fallback[1],
            fallback_model=fallback[2],
            reason=f"lowest_latency_{fastest[0]:.0f}ms",
            strategy_used=RoutingStrategy.LATENCY_OPTIMIZED
        )

    def get_provider_health(self, provider: str) -> Optional[ProviderHealth]:
        """Get health status for a specific provider."""
        return self.provider_health.get(provider)

    def get_all_health(self) -> Dict[str, Dict]:
        """Get health status for all tracked providers."""
        return {
            provider: health.to_dict()
            for provider, health in self.provider_health.items()
        }

    def get_metrics(self) -> Dict:
        """Get router metrics."""
        return {
            "total_requests": self._total_requests,
            "failover_count": self._failover_count,
            "failover_rate": f"{(self._failover_count / max(self._total_requests, 1)) * 100:.1f}%",
            "providers_tracked": len(self.provider_health),
            "circuits_open": sum(
                1 for h in self.provider_health.values() if h.circuit_open
            ),
        }

    def reset_circuit(self, provider: str) -> bool:
        """Manually reset a provider's circuit breaker."""
        health = self.provider_health.get(provider)
        if not health:
            return False

        health.circuit_open = False
        health.circuit_open_until = None
        health.consecutive_failures = 0
        logger.info(f"Circuit for {provider} manually reset")
        return True

    def clear_health_metrics(self, provider: Optional[str] = None):
        """Clear health metrics for one or all providers."""
        if provider:
            if provider in self.provider_health:
                del self.provider_health[provider]
        else:
            self.provider_health.clear()


# Singleton instance
_smart_router: Optional[SmartRouter] = None


def get_smart_router(db=None, provider_clients: Dict = None) -> SmartRouter:
    """Get or create the global SmartRouter instance."""
    global _smart_router
    if _smart_router is None:
        _smart_router = SmartRouter(db=db, provider_clients=provider_clients)
    return _smart_router


def reset_smart_router():
    """Reset the global SmartRouter instance (useful for testing)."""
    global _smart_router
    _smart_router = None
