"""
A/B Testing Middleware for Workflow Executor Integration

Intercepts LLM node executions in the workflow executor to:
1. Check for running experiments matching the task type / workflow
2. Assign variants (different models, prompts, or configs)
3. Override the routing decision with the variant's config
4. Record completion metrics (success, latency, cost) per variant

This bridges the standalone ABTestingService with real workflow execution.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.ab_testing_models import (
    ABExperiment,
    ABVariant,
    ABAssignment,
    ABAssignmentCreate,
    ABCompletionRequest,
)
from backend.shared.ab_testing_service import ABTestingService

logger = logging.getLogger(__name__)


@dataclass
class ABOverride:
    """
    Override configuration from an A/B variant assignment.

    When an experiment is active for a node, this carries the variant's
    model/prompt/config overrides and the assignment ID for later recording.
    """
    assignment_id: int
    experiment_id: int
    variant_id: int
    variant_name: str
    variant_key: str
    # Overrides (any of these may be None, meaning "use default")
    model_name: Optional[str] = None
    prompt_template: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class ABTestingMiddleware:
    """
    Middleware that hooks A/B testing into workflow node execution.

    Usage in WorkflowExecutor:
        # Before LLM call:
        override = await ab_middleware.check_and_assign(db, node_data, workflow_id, user_id)
        if override:
            # Apply model/prompt overrides from variant
            ...

        # After LLM call:
        await ab_middleware.record_result(db, override, success, latency_ms, cost)
    """

    @staticmethod
    async def check_and_assign(
        db: AsyncSession,
        node_data: Dict[str, Any],
        workflow_id: Optional[str] = None,
        user_id: str = "system",
        node_id: Optional[str] = None,
    ) -> Optional[ABOverride]:
        """
        Check for a running A/B experiment matching this node and assign a variant.

        Matching logic (in order of specificity):
        1. Exact workflow_id match (experiment targets this specific workflow)
        2. task_type match (experiment targets a category like "summarization")
        3. No match -> return None (no experiment active)

        Args:
            db: Database session
            node_data: The node's full data dict (node_data['data'] has type, label, config)
            workflow_id: Current workflow ID
            user_id: Current user ID for consistent assignment
            node_id: Current node ID

        Returns:
            ABOverride if an experiment matched and a variant was assigned, else None
        """
        try:
            data = node_data.get("data") or {}
            node_type = data.get("type", "")
            node_label = data.get("label", "")

            logger.info(
                f"[A/B Middleware] check_and_assign called: "
                f"workflow_id={workflow_id}, node_type={node_type}, "
                f"node_label={node_label}, node_id={node_id}"
            )

            # Only intercept LLM nodes
            if node_type not in ("supervisor", "worker"):
                logger.debug(f"[A/B Middleware] Skipping non-LLM node type: {node_type}")
                return None

            # Look for running experiments that match this execution
            #
            # Matching rules (in priority order):
            # 1. Explicit workflow_id match - single workflow (task_type="workflow:{uuid}")
            # 2. Multiple workflows match (task_type="workflows:{uuid1},{uuid2},...")
            # 3. task_type match (if only one running experiment has this task_type)
            #
            # NOTE: We explicitly avoid "wildcard" experiments (no target) to prevent
            # accidental experiment application. Every experiment should be explicit.

            experiment = None
            match_reason = None

            if workflow_id:
                # Priority 1: Check for single workflow match (workflow:{uuid})
                stmt = select(ABExperiment).where(
                    and_(
                        ABExperiment.status == "running",
                        ABExperiment.task_type == f"workflow:{workflow_id}",
                    )
                )
                result = await db.execute(stmt)
                experiment = result.scalar_one_or_none()
                if experiment:
                    match_reason = f"workflow_id={workflow_id}"

                # Priority 2: Check for multi-workflow match (workflows:{uuid1},{uuid2},...)
                if not experiment:
                    # Find experiments with task_type starting with "workflows:"
                    stmt = select(ABExperiment).where(
                        and_(
                            ABExperiment.status == "running",
                            ABExperiment.task_type.like("workflows:%"),
                        )
                    )
                    result = await db.execute(stmt)
                    multi_workflow_experiments = result.scalars().all()

                    for exp in multi_workflow_experiments:
                        # Parse the workflow IDs from "workflows:{uuid1},{uuid2},..."
                        workflow_ids_str = exp.task_type[len("workflows:"):]
                        target_workflow_ids = [
                            wid.strip() for wid in workflow_ids_str.split(",")
                        ]
                        if workflow_id in target_workflow_ids:
                            experiment = exp
                            match_reason = f"multi_workflow_match (workflow_id={workflow_id})"
                            break

            # Priority 3: Match by task_type (must be exactly one match)
            if not experiment:
                task_type = data.get("task_type") or data.get("category") or node_label
                if task_type and not task_type.startswith("workflow"):
                    stmt = select(ABExperiment).where(
                        and_(
                            ABExperiment.status == "running",
                            ABExperiment.task_type == task_type,
                        )
                    )
                    result = await db.execute(stmt)
                    matching_experiments = result.scalars().all()

                    if len(matching_experiments) == 1:
                        experiment = matching_experiments[0]
                        match_reason = f"task_type={task_type}"
                    elif len(matching_experiments) > 1:
                        # Multiple experiments match - log warning and skip
                        # This prevents undefined behavior
                        logger.warning(
                            f"Multiple A/B experiments match task_type='{task_type}': "
                            f"{[e.name for e in matching_experiments]}. "
                            f"Skipping A/B testing to avoid undefined behavior. "
                            f"Please ensure only one experiment targets each task_type."
                        )
                        return None

            if not experiment:
                logger.info(
                    f"[A/B Middleware] No experiment matched for workflow_id={workflow_id}"
                )
                return None

            logger.info(
                f"[A/B Middleware] Experiment '{experiment.name}' (id={experiment.id}) "
                f"matched node '{node_label}' (type={node_type}) via {match_reason}"
            )

            # Assign variant via the service
            assignment_data = ABAssignmentCreate(
                user_id=user_id,
                session_id=node_id,
            )

            assignment = await ABTestingService.assign_variant(
                db, experiment.id, assignment_data
            )

            # Load the variant to get its overrides
            stmt = select(ABVariant).where(ABVariant.id == assignment.variant_id)
            result = await db.execute(stmt)
            variant = result.scalar_one_or_none()

            if not variant:
                logger.warning(f"Variant {assignment.variant_id} not found after assignment")
                return None

            override = ABOverride(
                assignment_id=assignment.id,
                experiment_id=experiment.id,
                variant_id=variant.id,
                variant_name=variant.name,
                variant_key=variant.variant_key,
                model_name=variant.model_name,
                prompt_template=variant.prompt_template,
                config=variant.config if isinstance(variant.config, dict) else None,
            )

            logger.info(
                f"A/B assigned variant '{variant.name}' (key={variant.variant_key}) "
                f"for experiment '{experiment.name}'. "
                f"Override model={variant.model_name}, "
                f"has_prompt={variant.prompt_template is not None}"
            )

            return override

        except Exception as e:
            # A/B testing should NEVER break workflow execution
            logger.warning(f"A/B testing middleware error (non-fatal): {e}", exc_info=True)
            return None

    @staticmethod
    async def record_result(
        db: AsyncSession,
        override: ABOverride,
        success: bool,
        latency_ms: float = 0.0,
        cost: float = 0.0,
        error_message: Optional[str] = None,
        custom_metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Record the outcome of an A/B variant execution.

        Called after the LLM node finishes to update variant metrics.

        Args:
            db: Database session
            override: The ABOverride from check_and_assign()
            success: Whether the LLM call succeeded
            latency_ms: Execution time in milliseconds
            cost: Cost in dollars
            error_message: Error message if failed
            custom_metrics: Additional metrics to track
        """
        try:
            completion = ABCompletionRequest(
                assignment_id=override.assignment_id,
                success=success,
                latency_ms=latency_ms,
                cost=cost,
                error_message=error_message,
                custom_metrics=custom_metrics or {},
            )

            await ABTestingService.record_completion(db, completion)

            logger.info(
                f"A/B recorded: experiment={override.experiment_id}, "
                f"variant='{override.variant_name}', "
                f"success={success}, latency={latency_ms:.0f}ms, cost=${cost:.4f}"
            )

        except Exception as e:
            # Recording failure should NEVER break workflow execution
            logger.warning(
                f"A/B testing record_result error (non-fatal): {e}",
                exc_info=True,
            )

    @staticmethod
    def apply_override(
        override: ABOverride,
        routing_decision: Any,
        node_data: Dict[str, Any],
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Apply variant overrides to routing decision and node data.

        Modifies the model/provider selection and prompt based on the
        assigned variant configuration.

        Args:
            override: The ABOverride from check_and_assign()
            routing_decision: The current routing decision (has .model, .provider)
            node_data: The node data dict (will modify data.prompt if variant has one)

        Returns:
            (modified_routing_decision, modified_node_data)
        """
        # Override model if variant specifies one
        if override.model_name and routing_decision:
            original_model = routing_decision.model
            # Parse "provider/model" format (e.g., "groq/llama-3.3-70b-versatile")
            if "/" in override.model_name:
                parts = override.model_name.split("/", 1)
                routing_decision.provider = parts[0]
                routing_decision.model = parts[1]
            else:
                routing_decision.model = override.model_name

            routing_decision.reason = (
                f"A/B test override: variant '{override.variant_name}' "
                f"(was {original_model})"
            )

            logger.info(
                f"A/B override model: {original_model} -> "
                f"{routing_decision.provider}/{routing_decision.model}"
            )

        # Override prompt if variant specifies one
        if override.prompt_template:
            data = node_data.get("data") or {}
            original_prompt = data.get("prompt", "")
            data["prompt"] = override.prompt_template
            node_data["data"] = data

            logger.info(
                f"A/B override prompt: '{original_prompt[:50]}...' -> "
                f"'{override.prompt_template[:50]}...'"
            )

        # Merge variant config into node config
        if override.config:
            data = node_data.get("data") or {}
            config = data.get("config") or {}
            config.update(override.config)
            data["config"] = config
            node_data["data"] = data

            logger.info(f"A/B override config keys: {list(override.config.keys())}")

        return routing_decision, node_data
