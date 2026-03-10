"""
Circuit Breaker Service for Runaway Agent Protection

Implements ROADMAP.md Section: Recursive Loop & Cost Runaway Circuit Breaker

Features:
- Token velocity monitoring (default: 50K tokens/min)
- Cost velocity monitoring (default: $5/min)
- Consecutive same-tool detection (loop detection)
- Total tool call limits
- Batch operation bypass (ADMIN only)

This catches runaway agents BEFORE the 30-second heartbeat detects them,
preventing $100+ runaways in 5 minutes.
"""

import logging
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Set
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

logger = logging.getLogger(__name__)


class CircuitBreakerAction(Enum):
    """Action to take when circuit breaker trips."""
    PROCEED = "proceed"
    SUSPEND_FOR_APPROVAL = "suspend_for_approval"
    KILL = "kill"
    ALERT = "alert"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker limits."""
    token_velocity_per_minute: int = 50_000
    cost_velocity_per_minute: float = 5.0
    same_tool_consecutive_limit: int = 5
    total_tool_calls_per_execution: int = 100
    total_llm_calls_per_execution: int = 50
    max_recursion_depth: int = 10


@dataclass
class BatchOperationConfig:
    """Configuration for high-volume batch operations that bypass normal limits."""
    bypass_circuit_breaker: bool = False
    elevated_token_limit: int = 500_000  # 10x normal
    elevated_cost_limit: float = 50.0    # 10x normal
    elevated_tool_limit: int = 1000      # 10x normal
    require_cost_estimate_approval: bool = True
    audit_reason: str = ""


@dataclass
class CircuitBreakerResult:
    """Result from circuit breaker check."""
    proceed: bool
    action: CircuitBreakerAction = CircuitBreakerAction.PROCEED
    reason: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proceed": self.proceed,
            "action": self.action.value,
            "reason": self.reason,
            "metrics": self.metrics
        }


@dataclass
class ExecutionMetrics:
    """Metrics for a workflow execution."""
    execution_id: UUID
    started_at: datetime
    total_tokens: int = 0
    total_cost: float = 0.0
    llm_call_count: int = 0
    tool_call_count: int = 0
    current_recursion_depth: int = 0


@dataclass
class ToolCallRecord:
    """Record of a tool call for loop detection."""
    tool_name: str
    params_hash: str
    timestamp: datetime
    execution_id: UUID


class CircuitBreaker:
    """
    Fast-acting circuit breaker for runaway agents.

    Monitors:
    - Token velocity (tokens per minute)
    - Cost velocity ($ per minute)
    - Tool call patterns (loop detection)
    - Recursion depth

    Actions:
    - PROCEED: Continue execution
    - SUSPEND_FOR_APPROVAL: Pause and request human approval
    - KILL: Terminate execution immediately
    - ALERT: Log warning but continue
    """

    def __init__(
        self,
        db: AsyncSession,
        config: Optional[CircuitBreakerConfig] = None,
        redis_client: Optional[Any] = None
    ):
        self.db = db
        self.config = config or CircuitBreakerConfig()
        self.redis = redis_client

        # In-memory cache for fast lookups (per-session)
        self._metrics_cache: Dict[UUID, ExecutionMetrics] = {}
        self._tool_history_cache: Dict[UUID, List[ToolCallRecord]] = {}

    async def check_before_llm_call(
        self,
        execution_id: UUID,
        estimated_tokens: int = 0,
        batch_config: Optional[BatchOperationConfig] = None
    ) -> CircuitBreakerResult:
        """
        Check circuit breaker before making an LLM call.

        Args:
            execution_id: Workflow execution ID
            estimated_tokens: Estimated tokens for this call
            batch_config: Optional batch operation configuration

        Returns:
            CircuitBreakerResult indicating whether to proceed
        """
        metrics = await self._get_execution_metrics(execution_id)
        limits = self._get_limits(batch_config)

        # Calculate elapsed time
        elapsed_seconds = (datetime.utcnow() - metrics.started_at).total_seconds()
        elapsed_minutes = max(elapsed_seconds / 60, 0.1)  # Min 6 seconds to avoid division issues

        # Check 1: LLM call count
        if metrics.llm_call_count >= limits.total_llm_calls_per_execution:
            return CircuitBreakerResult(
                proceed=False,
                action=CircuitBreakerAction.SUSPEND_FOR_APPROVAL,
                reason=f"LLM call limit reached: {metrics.llm_call_count}/{limits.total_llm_calls_per_execution}",
                metrics={"llm_calls": metrics.llm_call_count, "limit": limits.total_llm_calls_per_execution}
            )

        # Check 2: Token velocity
        token_velocity = metrics.total_tokens / elapsed_minutes
        if token_velocity > limits.token_velocity_per_minute:
            if batch_config and batch_config.bypass_circuit_breaker:
                logger.warning(
                    f"Batch operation exceeding normal token limits: {token_velocity:.0f}/min "
                    f"(approved via bypass, reason: {batch_config.audit_reason})"
                )
            else:
                return CircuitBreakerResult(
                    proceed=False,
                    action=CircuitBreakerAction.SUSPEND_FOR_APPROVAL,
                    reason=f"Token velocity too high: {token_velocity:.0f} tokens/min (limit: {limits.token_velocity_per_minute})",
                    metrics={"token_velocity": token_velocity, "limit": limits.token_velocity_per_minute}
                )

        # Check 3: Cost velocity (most critical - KILL action)
        cost_velocity = metrics.total_cost / elapsed_minutes
        if cost_velocity > limits.cost_velocity_per_minute:
            if batch_config and batch_config.bypass_circuit_breaker:
                logger.warning(
                    f"Batch operation exceeding cost limits: ${cost_velocity:.2f}/min "
                    f"(approved via bypass, reason: {batch_config.audit_reason})"
                )
            else:
                return CircuitBreakerResult(
                    proceed=False,
                    action=CircuitBreakerAction.KILL,
                    reason=f"Cost runaway detected: ${cost_velocity:.2f}/min (limit: ${limits.cost_velocity_per_minute})",
                    metrics={"cost_velocity": cost_velocity, "limit": limits.cost_velocity_per_minute}
                )

        # Check 4: Recursion depth
        if metrics.current_recursion_depth > limits.max_recursion_depth:
            return CircuitBreakerResult(
                proceed=False,
                action=CircuitBreakerAction.SUSPEND_FOR_APPROVAL,
                reason=f"Recursion depth exceeded: {metrics.current_recursion_depth}/{limits.max_recursion_depth}",
                metrics={"depth": metrics.current_recursion_depth, "limit": limits.max_recursion_depth}
            )

        # All checks passed
        return CircuitBreakerResult(
            proceed=True,
            action=CircuitBreakerAction.PROCEED,
            metrics={
                "token_velocity": round(token_velocity, 2),
                "cost_velocity": round(cost_velocity, 4),
                "llm_calls": metrics.llm_call_count,
                "elapsed_seconds": round(elapsed_seconds, 2)
            }
        )

    async def check_before_tool_call(
        self,
        execution_id: UUID,
        tool_name: str,
        params: Dict[str, Any],
        batch_config: Optional[BatchOperationConfig] = None
    ) -> CircuitBreakerResult:
        """
        Check circuit breaker before executing a tool.
        Detects feedback loops where the same tool is called repeatedly.

        Args:
            execution_id: Workflow execution ID
            tool_name: Name of the tool being called
            params: Tool parameters
            batch_config: Optional batch operation configuration

        Returns:
            CircuitBreakerResult indicating whether to proceed
        """
        metrics = await self._get_execution_metrics(execution_id)
        limits = self._get_limits(batch_config)

        # Check 1: Total tool call count
        if metrics.tool_call_count >= limits.total_tool_calls_per_execution:
            return CircuitBreakerResult(
                proceed=False,
                action=CircuitBreakerAction.SUSPEND_FOR_APPROVAL,
                reason=f"Tool call limit reached: {metrics.tool_call_count}/{limits.total_tool_calls_per_execution}",
                metrics={"tool_calls": metrics.tool_call_count, "limit": limits.total_tool_calls_per_execution}
            )

        # Check 2: Loop detection (same tool with same/similar params)
        params_hash = self._hash_params(params)
        history = await self._get_recent_tool_calls(execution_id, limit=10)

        consecutive_same_tool = 0
        identical_calls = 0

        for call in history:
            if call.tool_name == tool_name:
                consecutive_same_tool += 1
                if call.params_hash == params_hash:
                    identical_calls += 1
            else:
                break  # Different tool, reset counter

        # Identical calls (exact same tool + params) - likely infinite loop
        if identical_calls >= 3:
            return CircuitBreakerResult(
                proceed=False,
                action=CircuitBreakerAction.KILL,
                reason=f"Infinite loop detected: {tool_name} called {identical_calls}x with identical params",
                metrics={"tool": tool_name, "identical_calls": identical_calls}
            )

        # Same tool called many times consecutively
        if consecutive_same_tool >= limits.same_tool_consecutive_limit:
            return CircuitBreakerResult(
                proceed=False,
                action=CircuitBreakerAction.SUSPEND_FOR_APPROVAL,
                reason=f"Possible loop: {tool_name} called {consecutive_same_tool}x consecutively",
                metrics={"tool": tool_name, "consecutive_calls": consecutive_same_tool}
            )

        # Record this tool call for future loop detection
        await self._record_tool_call(execution_id, tool_name, params_hash)

        # All checks passed
        return CircuitBreakerResult(
            proceed=True,
            action=CircuitBreakerAction.PROCEED,
            metrics={
                "tool_calls": metrics.tool_call_count,
                "consecutive_same": consecutive_same_tool
            }
        )

    async def record_llm_call(
        self,
        execution_id: UUID,
        tokens_used: int,
        cost: float
    ) -> None:
        """
        Record an LLM call's metrics for velocity tracking.

        Args:
            execution_id: Workflow execution ID
            tokens_used: Tokens consumed
            cost: Cost in USD
        """
        metrics = await self._get_execution_metrics(execution_id)
        metrics.total_tokens += tokens_used
        metrics.total_cost += cost
        metrics.llm_call_count += 1

        # Update cache
        self._metrics_cache[execution_id] = metrics

        # Persist to database periodically (every 5 calls)
        if metrics.llm_call_count % 5 == 0:
            await self._persist_metrics(execution_id, metrics)

        logger.debug(
            f"Recorded LLM call for {execution_id}: "
            f"+{tokens_used} tokens, +${cost:.4f}, "
            f"total: {metrics.total_tokens} tokens, ${metrics.total_cost:.4f}"
        )

    async def record_recursion_depth(
        self,
        execution_id: UUID,
        depth: int
    ) -> None:
        """Update the current recursion depth for an execution."""
        metrics = await self._get_execution_metrics(execution_id)
        metrics.current_recursion_depth = depth
        self._metrics_cache[execution_id] = metrics

    def _get_limits(self, batch_config: Optional[BatchOperationConfig]) -> CircuitBreakerConfig:
        """Get limits, elevated for batch operations."""
        if batch_config and batch_config.bypass_circuit_breaker:
            return CircuitBreakerConfig(
                token_velocity_per_minute=batch_config.elevated_token_limit,
                cost_velocity_per_minute=batch_config.elevated_cost_limit,
                same_tool_consecutive_limit=50,  # Allow more repetition
                total_tool_calls_per_execution=batch_config.elevated_tool_limit,
                total_llm_calls_per_execution=500,  # 10x for batches
                max_recursion_depth=20  # 2x for batches
            )
        return self.config

    async def _get_execution_metrics(self, execution_id: UUID) -> ExecutionMetrics:
        """Get or create metrics for an execution."""
        # Check cache first
        if execution_id in self._metrics_cache:
            return self._metrics_cache[execution_id]

        # Try to load from database (only if db is available)
        if self.db:
            try:
                from backend.shared.workflow_models import WorkflowExecutionModel

                result = await self.db.execute(
                    select(WorkflowExecutionModel).where(
                        WorkflowExecutionModel.execution_id == execution_id
                    )
                )
                execution = result.scalar_one_or_none()

                if execution:
                    metrics = ExecutionMetrics(
                        execution_id=execution_id,
                        started_at=execution.started_at or datetime.utcnow(),
                        total_tokens=execution.total_tokens or 0,
                        total_cost=execution.total_cost or 0.0,
                        llm_call_count=execution.extra_metadata.get("llm_call_count", 0) if execution.extra_metadata else 0,
                        tool_call_count=execution.extra_metadata.get("tool_call_count", 0) if execution.extra_metadata else 0,
                        current_recursion_depth=execution.extra_metadata.get("recursion_depth", 0) if execution.extra_metadata else 0
                    )
                    self._metrics_cache[execution_id] = metrics
                    return metrics
            except Exception as e:
                logger.warning(f"Failed to load metrics from DB: {e}")

        # Create new metrics (fallback for no DB or DB load failure)
        metrics = ExecutionMetrics(
            execution_id=execution_id,
            started_at=datetime.utcnow()
        )
        self._metrics_cache[execution_id] = metrics
        return metrics

    async def _get_recent_tool_calls(
        self,
        execution_id: UUID,
        limit: int = 10
    ) -> List[ToolCallRecord]:
        """Get recent tool calls for loop detection."""
        # Check in-memory cache first
        if execution_id in self._tool_history_cache:
            history = self._tool_history_cache[execution_id]
            return history[-limit:][::-1]  # Most recent first

        return []

    async def _record_tool_call(
        self,
        execution_id: UUID,
        tool_name: str,
        params_hash: str
    ) -> None:
        """Record a tool call for loop detection."""
        record = ToolCallRecord(
            tool_name=tool_name,
            params_hash=params_hash,
            timestamp=datetime.utcnow(),
            execution_id=execution_id
        )

        if execution_id not in self._tool_history_cache:
            self._tool_history_cache[execution_id] = []

        self._tool_history_cache[execution_id].append(record)

        # Keep only last 100 calls per execution
        if len(self._tool_history_cache[execution_id]) > 100:
            self._tool_history_cache[execution_id] = self._tool_history_cache[execution_id][-100:]

        # Update metrics
        metrics = await self._get_execution_metrics(execution_id)
        metrics.tool_call_count += 1
        self._metrics_cache[execution_id] = metrics

    async def _persist_metrics(
        self,
        execution_id: UUID,
        metrics: ExecutionMetrics
    ) -> None:
        """Persist metrics to database."""
        # Skip if no database connection
        if not self.db:
            return

        try:
            from backend.shared.workflow_models import WorkflowExecutionModel

            result = await self.db.execute(
                select(WorkflowExecutionModel).where(
                    WorkflowExecutionModel.execution_id == execution_id
                )
            )
            execution = result.scalar_one_or_none()

            if execution:
                execution.total_tokens = metrics.total_tokens
                execution.total_cost = metrics.total_cost

                # Store additional metrics in extra_metadata
                metadata = execution.extra_metadata or {}
                metadata.update({
                    "llm_call_count": metrics.llm_call_count,
                    "tool_call_count": metrics.tool_call_count,
                    "recursion_depth": metrics.current_recursion_depth,
                    "circuit_breaker_last_check": datetime.utcnow().isoformat()
                })
                execution.extra_metadata = metadata

                await self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to persist metrics: {e}")

    def _hash_params(self, params: Dict[str, Any]) -> str:
        """Create a hash of parameters for comparison."""
        # Sort keys for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(sorted_params.encode()).hexdigest()[:16]

    def clear_execution_cache(self, execution_id: UUID) -> None:
        """Clear cached data for a completed execution."""
        self._metrics_cache.pop(execution_id, None)
        self._tool_history_cache.pop(execution_id, None)


# Singleton instance for easy access
_circuit_breaker_instance: Optional[CircuitBreaker] = None


def get_circuit_breaker(
    db: AsyncSession,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """Get or create a circuit breaker instance."""
    global _circuit_breaker_instance
    if _circuit_breaker_instance is None or _circuit_breaker_instance.db != db:
        _circuit_breaker_instance = CircuitBreaker(db, config)
    return _circuit_breaker_instance


def validate_batch_config(
    batch_config: BatchOperationConfig,
    user_permissions: Set[str]
) -> None:
    """
    Validate that user has permission to use batch bypass.

    Raises:
        PermissionError: If user lacks required permission
    """
    if batch_config.bypass_circuit_breaker:
        required_permissions = {"ADMIN", "CIRCUIT_BREAKER_BYPASS"}
        if not user_permissions & required_permissions:
            raise PermissionError(
                "bypass_circuit_breaker requires ADMIN or CIRCUIT_BREAKER_BYPASS permission"
            )

        if not batch_config.audit_reason:
            raise ValueError(
                "audit_reason is required when bypass_circuit_breaker is enabled"
            )
