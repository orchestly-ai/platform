"""
Routing Integration for Workflow Execution

Provides utilities to integrate SmartRouter with workflow execution.
Handles config hierarchy resolution (agent → workflow → org).
Includes task-type-to-model mappings for intelligent routing.
"""

from typing import Optional, Dict, Any, Union, List
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dataclasses import dataclass, field

from backend.shared.smart_router_service import (
    get_smart_router,
    SmartRouter,
    RoutingStrategy,
    OrgRoutingConfig,
    UniversalRequest,
    UniversalResponse,
    RoutingDecision,
    ProviderError,
    ExecutionState,
)
from backend.shared.ml_routing_models import RoutingPolicy
from backend.shared.llm_clients import LLMResponse

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# TASK TYPE MODEL MAPPINGS
# =============================================================================
# Maps task types to preferred models based on quality/cost tradeoffs.
# Cheap models for classification/triage, quality models for generation.
# =============================================================================

@dataclass
class TaskTypeConfig:
    """Configuration for a task type's model preferences"""
    primary_model: str
    primary_provider: str
    fallback_model: str
    fallback_provider: str
    optimization: str  # 'cost', 'quality', 'latency'
    description: str


# Static task-type-to-model mappings
# These can be overridden by database entries via CostOptimizationRule
TASK_TYPE_MODEL_MAPPINGS: Dict[str, TaskTypeConfig] = {
    # Classification/Triage tasks - use cheap, fast models
    "ticket_classification": TaskTypeConfig(
        primary_model="gpt-4o-mini",
        primary_provider="openai",
        fallback_model="claude-3-haiku-20240307",
        fallback_provider="anthropic",
        optimization="cost",
        description="Classify support tickets by category, priority, sentiment"
    ),
    "ticket_triage": TaskTypeConfig(
        primary_model="gpt-4o-mini",
        primary_provider="openai",
        fallback_model="claude-3-haiku-20240307",
        fallback_provider="anthropic",
        optimization="cost",
        description="Triage incoming tickets to appropriate queue"
    ),
    "sentiment_analysis": TaskTypeConfig(
        primary_model="gpt-4o-mini",
        primary_provider="openai",
        fallback_model="claude-3-haiku-20240307",
        fallback_provider="anthropic",
        optimization="cost",
        description="Analyze customer sentiment from text"
    ),
    "intent_detection": TaskTypeConfig(
        primary_model="gpt-4o-mini",
        primary_provider="openai",
        fallback_model="claude-3-haiku-20240307",
        fallback_provider="anthropic",
        optimization="cost",
        description="Detect customer intent from message"
    ),
    "entity_extraction": TaskTypeConfig(
        primary_model="gpt-4o-mini",
        primary_provider="openai",
        fallback_model="claude-3-haiku-20240307",
        fallback_provider="anthropic",
        optimization="cost",
        description="Extract named entities from text"
    ),
    "summarization": TaskTypeConfig(
        primary_model="gpt-4o-mini",
        primary_provider="openai",
        fallback_model="claude-3-haiku-20240307",
        fallback_provider="anthropic",
        optimization="cost",
        description="Summarize conversations or documents"
    ),

    # Generation tasks - use quality models
    "response_generation": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Generate customer-facing responses"
    ),
    "customer_response": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Generate empathetic customer responses"
    ),
    "email_generation": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Generate professional email responses"
    ),
    "content_creation": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Create marketing or documentation content"
    ),

    # Reasoning tasks - use best available models
    "complex_reasoning": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Complex multi-step reasoning tasks"
    ),
    "decision_support": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Support human decision-making"
    ),
    "refund_recommendation": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Recommend refund amounts and actions"
    ),

    # Code tasks - use capable models
    "code_generation": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Generate code snippets"
    ),
    "code_review": TaskTypeConfig(
        primary_model="gpt-4o",
        primary_provider="openai",
        fallback_model="claude-3-5-sonnet-20241022",
        fallback_provider="anthropic",
        optimization="quality",
        description="Review code for issues"
    ),

    # Fast/latency-critical tasks - use fast providers
    "autocomplete": TaskTypeConfig(
        primary_model="llama-3.3-70b-versatile",
        primary_provider="groq",
        fallback_model="gpt-4o-mini",
        fallback_provider="openai",
        optimization="latency",
        description="Real-time autocomplete suggestions"
    ),
    "quick_response": TaskTypeConfig(
        primary_model="llama-3.3-70b-versatile",
        primary_provider="groq",
        fallback_model="gpt-4o-mini",
        fallback_provider="openai",
        optimization="latency",
        description="Fast response for interactive chat"
    ),
}


def get_task_type_config(task_type: str) -> Optional[TaskTypeConfig]:
    """
    Get model configuration for a task type.

    Args:
        task_type: The task type identifier (e.g., 'ticket_classification')

    Returns:
        TaskTypeConfig if found, None otherwise
    """
    return TASK_TYPE_MODEL_MAPPINGS.get(task_type)


def list_task_types() -> Dict[str, str]:
    """
    List all available task types with descriptions.

    Returns:
        Dict mapping task_type to description
    """
    return {
        task_type: config.description
        for task_type, config in TASK_TYPE_MODEL_MAPPINGS.items()
    }


@dataclass
class ModelConfig:
    """Configuration for model selection"""
    routing_decision: RoutingDecision
    config_source: str  # 'agent', 'workflow', 'organization', or 'override'


class RoutingResolver:
    """Resolves routing configuration based on hierarchy"""

    def __init__(self, db: Session):
        self.db = db
        self.smart_router = get_smart_router(db=db)
        self._failover_executor: Optional['FailoverExecutor'] = None

    def get_failover_executor(self) -> 'FailoverExecutor':
        """Get or create the FailoverExecutor for this resolver."""
        if self._failover_executor is None:
            self._failover_executor = FailoverExecutor(self)
        return self._failover_executor

    async def resolve_model_selection(
        self,
        node_data: Dict,
        workflow_id: str,
        agent_id: str,
        org_id: str = "default",
        task_type: Optional[str] = None
    ) -> ModelConfig:
        """
        Resolve which model to use based on hierarchy:
        1. Agent-level model selection (highest priority - explicit model override)
        2. Task-type-based model mapping (if task_type specified)
        3. Workflow-level routing strategy
        4. Organization-level default strategy

        Args:
            node_data: Node configuration from workflow
            workflow_id: ID of the workflow being executed
            agent_id: ID of the agent node
            org_id: Organization ID
            task_type: Optional task type for intelligent routing (e.g., 'ticket_classification')

        Returns:
            ModelConfig with routing decision and source
        """
        model_selection = node_data.get('modelSelection', 'auto')
        data = node_data.get('data', {})

        # Extract task_type from multiple sources:
        # 1. Explicit parameter (highest priority)
        # 2. node_data.task_type
        # 3. node_data.data.task_type
        effective_task_type = (
            task_type or
            node_data.get('task_type') or
            data.get('task_type')
        )

        # Handle llm: prefix (e.g., 'llm:gpt-4o' -> 'gpt-4o')
        specific_model = None
        if model_selection and model_selection.startswith('llm:'):
            specific_model = model_selection.replace('llm:', '')
        # Backward compatibility: check old llmModel field
        elif node_data.get('llmModel'):
            specific_model = node_data.get('llmModel')

        # Priority 1: Check if specific model override
        if specific_model:
            provider = self._get_provider_for_model(specific_model)
            logger.debug(f"Using explicit model override: {provider}/{specific_model}")
            return ModelConfig(
                routing_decision=RoutingDecision(
                    provider=provider,
                    model=specific_model,
                    reason="agent_model_override",
                    strategy_used=None
                ),
                config_source="override"
            )

        # Priority 2: Check task-type-based routing
        if effective_task_type:
            task_routing = self._get_routing_for_task_type(effective_task_type)
            if task_routing:
                logger.info(
                    f"Task-type routing: {effective_task_type} -> "
                    f"{task_routing.provider}/{task_routing.model} "
                    f"(optimization: {TASK_TYPE_MODEL_MAPPINGS[effective_task_type].optimization})"
                )
                return ModelConfig(
                    routing_decision=task_routing,
                    config_source="task_type"
                )

        # If not auto and not specific model, it must be a strategy override
        if model_selection not in ['auto', 'cost_optimized', 'latency_optimized', 'quality_first', 'weighted_roundrobin']:
            # Unknown value - default to auto
            model_selection = 'auto'

        # Priority 3-4: Get routing configuration from hierarchy
        router_config = await self._get_routing_config_hierarchy(
            agent_id=agent_id,
            workflow_id=workflow_id,
            org_id=org_id,
            agent_strategy=model_selection if model_selection != 'auto' else None
        )

        # Route the request
        routing_decision = await self.smart_router.route_request(
            request=UniversalRequest(messages=[{"role": "user", "content": "test"}]),
            org_config=router_config.org_config
        )

        return ModelConfig(
            routing_decision=routing_decision,
            config_source=router_config.source
        )

    def _get_routing_for_task_type(self, task_type: str) -> Optional[RoutingDecision]:
        """
        Get routing decision based on task type configuration.

        Args:
            task_type: The task type identifier (e.g., 'ticket_classification')

        Returns:
            RoutingDecision if task type mapping exists, None otherwise
        """
        config = get_task_type_config(task_type)
        if not config:
            logger.debug(f"No task-type mapping found for: {task_type}")
            return None

        return RoutingDecision(
            provider=config.primary_provider,
            model=config.primary_model,
            reason=f"task_type_routing:{task_type}",
            strategy_used=config.optimization,
            fallback_provider=config.fallback_provider,
            fallback_model=config.fallback_model,
        )

    async def _get_routing_config_hierarchy(
        self,
        agent_id: str,
        workflow_id: str,
        org_id: str,
        agent_strategy: Optional[str] = None
    ) -> 'ConfigHierarchyResult':
        """
        Get routing config using hierarchy:
        agent → workflow → organization

        Supports both sync and async database sessions.
        """
        # 1. Check agent-level override
        if agent_strategy:
            # Agent specified a strategy override
            org_config = self._build_org_config(
                org_id=org_id,
                strategy=agent_strategy
            )
            return ConfigHierarchyResult(org_config=org_config, source="agent")

        # Query database for agent-specific policy
        # Support both async and sync sessions
        agent_policy = await self._query_policy(
            RoutingPolicy.name.like(f"%{agent_id}%")
        )

        if agent_policy:
            org_config = self._policy_to_org_config(agent_policy, org_id)
            return ConfigHierarchyResult(org_config=org_config, source="agent")

        # 2. Check workflow-level config
        workflow_policy = await self._query_policy(
            RoutingPolicy.name.like(f"%{workflow_id}%")
        )

        if workflow_policy:
            org_config = self._policy_to_org_config(workflow_policy, org_id)
            return ConfigHierarchyResult(org_config=org_config, source="workflow")

        # 3. Fall back to organization default
        org_policy = await self._query_policy(
            (RoutingPolicy.name.like("%organization%")) | (RoutingPolicy.name.like("%default%"))
        )

        if org_policy:
            org_config = self._policy_to_org_config(org_policy, org_id)
            return ConfigHierarchyResult(org_config=org_config, source="organization")

        # 4. Final fallback - use default cost optimized
        org_config = self._build_org_config(org_id=org_id, strategy="cost_optimized")
        return ConfigHierarchyResult(org_config=org_config, source="default")

    async def _query_policy(self, name_filter) -> Optional[RoutingPolicy]:
        """
        Query RoutingPolicy with support for both sync and async sessions.
        """
        if self.db is None:
            return None

        try:
            # Check if this is an async session
            if isinstance(self.db, AsyncSession):
                stmt = select(RoutingPolicy).where(
                    name_filter,
                    RoutingPolicy.is_active == True
                )
                result = await self.db.execute(stmt)
                return result.scalars().first()
            else:
                # Sync session fallback
                return self.db.query(RoutingPolicy).filter(
                    name_filter,
                    RoutingPolicy.is_active == True
                ).first()
        except Exception as e:
            # Log but don't fail - return None to use fallback
            import logging
            logging.getLogger(__name__).warning(f"Failed to query routing policy: {e}")
            return None

    def _policy_to_org_config(self, policy: RoutingPolicy, org_id: str) -> OrgRoutingConfig:
        """Convert database RoutingPolicy to OrgRoutingConfig"""
        # Map database strategy to SmartRouter strategy
        strategy_map = {
            "cost_optimized": RoutingStrategy.COST_OPTIMIZED,
            "latency_optimized": RoutingStrategy.LATENCY_OPTIMIZED,
            "quality_optimized": RoutingStrategy.BEST_AVAILABLE,
            "balanced": RoutingStrategy.PRIMARY_WITH_BACKUP,
        }

        strategy = strategy_map.get(policy.strategy, RoutingStrategy.COST_OPTIMIZED)

        return OrgRoutingConfig(
            org_id=org_id,
            routing_strategy=strategy,
            primary_provider="openai",
            primary_model="gpt-4o-mini",
            backup_provider="anthropic",
            backup_model="claude-3-haiku",
            fallback_chain=[]
        )

    def _build_org_config(self, org_id: str, strategy: str) -> OrgRoutingConfig:
        """Build OrgRoutingConfig from strategy name"""
        strategy_map = {
            "cost_optimized": RoutingStrategy.COST_OPTIMIZED,
            "latency_optimized": RoutingStrategy.LATENCY_OPTIMIZED,
            "quality_first": RoutingStrategy.BEST_AVAILABLE,
            "weighted_roundrobin": RoutingStrategy.PRIMARY_WITH_BACKUP,
            "auto": RoutingStrategy.COST_OPTIMIZED,
        }

        routing_strategy = strategy_map.get(strategy, RoutingStrategy.COST_OPTIMIZED)

        return OrgRoutingConfig(
            org_id=org_id,
            routing_strategy=routing_strategy,
            primary_provider="openai",
            primary_model="gpt-4o-mini",
            backup_provider="anthropic",
            backup_model="claude-3-haiku",
            fallback_chain=[]
        )

    def _get_provider_for_model(self, model: str) -> str:
        """Get provider name for a specific model"""
        model_lower = model.lower()
        if 'gpt' in model_lower:
            return 'openai'
        elif 'claude' in model_lower:
            return 'anthropic'
        elif 'gemini' in model_lower:
            return 'google'
        elif 'deepseek' in model_lower:
            return 'deepseek'
        elif 'llama' in model_lower or 'mixtral' in model_lower or 'gemma' in model_lower:
            # Groq hosts Llama, Mixtral, and Gemma models
            return 'groq'
        else:
            return 'openai'  # default


@dataclass
class ConfigHierarchyResult:
    """Result from config hierarchy resolution"""
    org_config: OrgRoutingConfig
    source: str  # 'agent', 'workflow', 'organization', 'default'


@dataclass
class FailoverResult:
    """Result from execute_with_failover_wrapper"""
    content: str
    model: str
    provider: str
    latency_ms: float
    tokens_used: int
    cost: float
    finish_reason: str
    failover_used: bool = False
    original_provider: Optional[str] = None
    failover_reason: Optional[str] = None

    def to_llm_response(self) -> LLMResponse:
        """Convert to LLMResponse for backward compatibility"""
        return LLMResponse(
            content=self.content,
            model=self.model,
            provider=self.provider,
            latency_ms=self.latency_ms,
            tokens_used=self.tokens_used,
            cost=self.cost,
            finish_reason=self.finish_reason
        )


class FailoverExecutor:
    """
    Executes LLM calls with automatic failover using SmartRouter.

    This is the primary interface for workflow execution to make LLM calls
    with proper failover handling.
    """

    def __init__(self, routing_resolver: 'RoutingResolver'):
        self.resolver = routing_resolver
        self.smart_router = routing_resolver.smart_router

    async def execute(
        self,
        messages: list,
        routing_decision: RoutingDecision,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        api_key: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
    ) -> FailoverResult:
        """
        Execute an LLM call with automatic failover.

        Args:
            messages: List of message dicts (role, content)
            routing_decision: Routing decision with provider, model, and fallback
            max_tokens: Maximum tokens for response
            temperature: Temperature setting
            api_key: Optional API key for primary provider
            fallback_api_key: Optional API key for fallback provider

        Returns:
            FailoverResult with response and failover metadata

        Raises:
            ProviderError: If all providers fail
        """
        # Build universal request
        request = UniversalRequest(
            messages=messages,
            model=routing_decision.model,
            max_tokens=max_tokens,
            temperature=temperature,
            metadata={"api_key": api_key}
        )

        try:
            # Try primary provider
            logger.info(
                f"Executing LLM call: {routing_decision.provider}/{routing_decision.model}"
            )
            response = await self.smart_router.execute_with_failover(
                request=request,
                routing=routing_decision,
            )

            # Check if failover was used
            failover_used = response.metadata.get("failover", False)
            original_provider = response.metadata.get("original_provider")
            failover_reason = response.metadata.get("failover_reason")

            if failover_used:
                logger.info(
                    f"Failover executed: {original_provider} -> {response.provider} "
                    f"(reason: {failover_reason})"
                )

            return FailoverResult(
                content=response.content,
                model=response.model,
                provider=response.provider,
                latency_ms=response.latency_ms,
                tokens_used=response.usage.get("total_tokens", 0),
                cost=response.cost,
                finish_reason="stop",
                failover_used=failover_used,
                original_provider=original_provider,
                failover_reason=failover_reason
            )

        except ProviderError as e:
            # All providers failed - log and re-raise
            logger.error(
                f"All providers failed for LLM call: {e}"
            )
            raise
