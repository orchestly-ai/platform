"""
Auto-Optimization Engine for Agent Orchestration

Continuously analyzes execution patterns and automatically suggests/applies optimizations:
- Cost optimization: Recommend cheaper models for workflows that don't need premium
- Latency optimization: Identify slow paths and suggest routing changes
- A/B test graduation: Auto-promote winning variants with statistical significance
- Resource recommendations: Suggest scaling based on usage patterns

This engine makes the platform self-improving over time.
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of optimizations the engine can suggest."""
    COST_REDUCTION = "cost_reduction"
    LATENCY_IMPROVEMENT = "latency_improvement"
    AB_TEST_GRADUATION = "ab_test_graduation"
    MODEL_UPGRADE = "model_upgrade"
    MODEL_DOWNGRADE = "model_downgrade"
    ROUTING_CHANGE = "routing_change"
    CACHE_ENABLEMENT = "cache_enablement"
    BATCH_CONSOLIDATION = "batch_consolidation"


class OptimizationStatus(Enum):
    """Status of an optimization recommendation."""
    SUGGESTED = "suggested"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ConfidenceLevel(Enum):
    """Confidence level for recommendations."""
    LOW = "low"        # 60-75% confidence
    MEDIUM = "medium"  # 75-90% confidence
    HIGH = "high"      # 90%+ confidence


@dataclass
class OptimizationRecommendation:
    """A single optimization recommendation."""
    recommendation_id: UUID
    organization_id: str
    optimization_type: OptimizationType
    title: str
    description: str
    confidence: ConfidenceLevel
    estimated_savings: Optional[float] = None  # $ per month
    estimated_latency_improvement_ms: Optional[float] = None
    affected_workflows: List[UUID] = field(default_factory=list)
    current_config: Dict[str, Any] = field(default_factory=dict)
    recommended_config: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    auto_apply_eligible: bool = False
    status: OptimizationStatus = OptimizationStatus.SUGGESTED
    created_at: datetime = field(default_factory=datetime.utcnow)
    applied_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": str(self.recommendation_id),
            "organization_id": self.organization_id,
            "type": self.optimization_type.value,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence.value,
            "estimated_savings": self.estimated_savings,
            "estimated_latency_improvement_ms": self.estimated_latency_improvement_ms,
            "affected_workflows": [str(w) for w in self.affected_workflows],
            "current_config": self.current_config,
            "recommended_config": self.recommended_config,
            "evidence": self.evidence,
            "auto_apply_eligible": self.auto_apply_eligible,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None
        }


@dataclass
class WorkflowAnalysis:
    """Analysis results for a single workflow."""
    workflow_id: UUID
    execution_count: int
    avg_cost: float
    avg_latency_ms: float
    p95_latency_ms: float
    success_rate: float
    primary_model: str
    token_usage_pattern: str  # "consistent", "variable", "bursty"
    complexity_level: str  # "simple", "moderate", "complex"


@dataclass
class ModelCostProfile:
    """Cost and capability profile for a model."""
    model_id: str
    provider: str
    cost_per_1k_tokens: float
    avg_latency_ms: float
    capability_tier: int  # 1=basic, 2=standard, 3=advanced, 4=premium


class AutoOptimizationEngine:
    """
    Engine that continuously analyzes and optimizes agent orchestration.

    Analysis runs:
    - Real-time: After each execution completion
    - Batch: Daily analysis for pattern detection
    - Triggered: When anomalies are detected
    """

    # Model profiles for cost/capability analysis
    MODEL_PROFILES: Dict[str, ModelCostProfile] = {
        "gpt-4o": ModelCostProfile("gpt-4o", "openai", 0.005, 800, 4),
        "gpt-4o-mini": ModelCostProfile("gpt-4o-mini", "openai", 0.00015, 400, 2),
        "gpt-4-turbo": ModelCostProfile("gpt-4-turbo", "openai", 0.01, 1000, 4),
        "gpt-3.5-turbo": ModelCostProfile("gpt-3.5-turbo", "openai", 0.0005, 300, 1),
        "claude-3-5-sonnet": ModelCostProfile("claude-3-5-sonnet", "anthropic", 0.003, 700, 3),
        "claude-3-haiku": ModelCostProfile("claude-3-haiku", "anthropic", 0.00025, 250, 1),
        "claude-3-opus": ModelCostProfile("claude-3-opus", "anthropic", 0.015, 1200, 4),
        "gemini-1.5-pro": ModelCostProfile("gemini-1.5-pro", "google", 0.00125, 600, 3),
        "gemini-1.5-flash": ModelCostProfile("gemini-1.5-flash", "google", 0.000075, 200, 1),
    }

    def __init__(
        self,
        db: AsyncSession,
        lookback_days: int = 14,
        min_executions_for_analysis: int = 20,
        auto_apply_threshold: float = 0.95  # 95% confidence for auto-apply
    ):
        self.db = db
        self.lookback_days = lookback_days
        self.min_executions = min_executions_for_analysis
        self.auto_apply_threshold = auto_apply_threshold
        self._recommendations_cache: Dict[str, List[OptimizationRecommendation]] = {}

    async def analyze_organization(
        self,
        organization_id: str
    ) -> List[OptimizationRecommendation]:
        """
        Run full optimization analysis for an organization.

        Returns list of recommendations sorted by estimated impact.
        """
        recommendations = []

        # Get workflow analysis data
        workflows = await self._analyze_workflows(organization_id)

        if not workflows:
            logger.info(f"No workflows with sufficient data for org {organization_id}")
            return []

        # Run different optimization analyzers
        recommendations.extend(
            await self._analyze_cost_optimization(organization_id, workflows)
        )
        recommendations.extend(
            await self._analyze_model_downgrades(organization_id, workflows)
        )
        recommendations.extend(
            await self._analyze_latency_optimization(organization_id, workflows)
        )
        recommendations.extend(
            await self._analyze_ab_test_graduation(organization_id)
        )
        recommendations.extend(
            await self._analyze_cache_opportunities(organization_id, workflows)
        )

        # Sort by estimated impact (savings + latency improvement value)
        recommendations.sort(
            key=lambda r: (r.estimated_savings or 0) + (r.estimated_latency_improvement_ms or 0) * 0.01,
            reverse=True
        )

        # Cache recommendations
        self._recommendations_cache[organization_id] = recommendations

        return recommendations

    async def _analyze_workflows(
        self,
        organization_id: str
    ) -> List[WorkflowAnalysis]:
        """Analyze workflow execution patterns."""
        from backend.shared.workflow_models import WorkflowExecutionModel, WorkflowModel

        cutoff = datetime.utcnow() - timedelta(days=self.lookback_days)

        # Get execution statistics per workflow
        result = await self.db.execute(
            select(
                WorkflowExecutionModel.workflow_id,
                func.count(WorkflowExecutionModel.execution_id).label('count'),
                func.avg(WorkflowExecutionModel.total_cost).label('avg_cost'),
                func.avg(WorkflowExecutionModel.total_tokens).label('avg_tokens'),
                func.sum(
                    func.case(
                        (WorkflowExecutionModel.status == 'completed', 1),
                        else_=0
                    )
                ).label('successful')
            )
            .where(
                and_(
                    WorkflowExecutionModel.organization_id == organization_id,
                    WorkflowExecutionModel.started_at >= cutoff
                )
            )
            .group_by(WorkflowExecutionModel.workflow_id)
            .having(func.count(WorkflowExecutionModel.execution_id) >= self.min_executions)
        )

        workflows = []
        for row in result.all():
            # Get workflow details
            workflow_result = await self.db.execute(
                select(WorkflowModel).where(WorkflowModel.workflow_id == row.workflow_id)
            )
            workflow = workflow_result.scalar_one_or_none()

            if not workflow:
                continue

            # Determine primary model from workflow config
            config = workflow.config or {}
            primary_model = config.get("model", "gpt-4o-mini")

            # Calculate success rate
            success_rate = (row.successful / row.count * 100) if row.count > 0 else 0

            # Estimate latency from token count (rough approximation)
            avg_tokens = row.avg_tokens or 0
            avg_latency = avg_tokens * 0.5  # Rough: 0.5ms per token

            # Determine complexity based on average tokens
            if avg_tokens < 1000:
                complexity = "simple"
            elif avg_tokens < 5000:
                complexity = "moderate"
            else:
                complexity = "complex"

            workflows.append(WorkflowAnalysis(
                workflow_id=row.workflow_id,
                execution_count=row.count,
                avg_cost=float(row.avg_cost or 0),
                avg_latency_ms=avg_latency,
                p95_latency_ms=avg_latency * 1.5,  # Estimate
                success_rate=success_rate,
                primary_model=primary_model,
                token_usage_pattern="consistent",  # Would need more analysis
                complexity_level=complexity
            ))

        return workflows

    async def _analyze_cost_optimization(
        self,
        organization_id: str,
        workflows: List[WorkflowAnalysis]
    ) -> List[OptimizationRecommendation]:
        """Identify workflows that could use cheaper models."""
        from uuid import uuid4

        recommendations = []

        for wf in workflows:
            current_profile = self.MODEL_PROFILES.get(wf.primary_model)
            if not current_profile:
                continue

            # Check if workflow is simple enough for a cheaper model
            if wf.complexity_level == "simple" and current_profile.capability_tier >= 3:
                # Suggest downgrade to tier 1-2 model
                cheaper_models = [
                    m for m in self.MODEL_PROFILES.values()
                    if m.capability_tier <= 2 and m.cost_per_1k_tokens < current_profile.cost_per_1k_tokens
                ]

                if cheaper_models:
                    best_cheaper = min(cheaper_models, key=lambda m: m.cost_per_1k_tokens)

                    # Calculate estimated savings
                    cost_reduction_ratio = 1 - (best_cheaper.cost_per_1k_tokens / current_profile.cost_per_1k_tokens)
                    monthly_savings = wf.avg_cost * wf.execution_count * 2 * cost_reduction_ratio  # Extrapolate to month

                    if monthly_savings > 5:  # Only recommend if >$5/month savings
                        recommendations.append(OptimizationRecommendation(
                            recommendation_id=uuid4(),
                            organization_id=organization_id,
                            optimization_type=OptimizationType.MODEL_DOWNGRADE,
                            title=f"Switch {wf.primary_model} to {best_cheaper.model_id}",
                            description=(
                                f"Workflow complexity is 'simple' but using premium model. "
                                f"Based on {wf.execution_count} executions, switching to "
                                f"{best_cheaper.model_id} could save ~${monthly_savings:.2f}/month "
                                f"with similar quality for this use case."
                            ),
                            confidence=ConfidenceLevel.MEDIUM if wf.success_rate > 95 else ConfidenceLevel.LOW,
                            estimated_savings=monthly_savings,
                            affected_workflows=[wf.workflow_id],
                            current_config={"model": wf.primary_model},
                            recommended_config={"model": best_cheaper.model_id},
                            evidence={
                                "execution_count": wf.execution_count,
                                "complexity_level": wf.complexity_level,
                                "success_rate": wf.success_rate,
                                "cost_reduction_percent": cost_reduction_ratio * 100
                            },
                            auto_apply_eligible=False  # Model changes need human review
                        ))

        return recommendations

    async def _analyze_model_downgrades(
        self,
        organization_id: str,
        workflows: List[WorkflowAnalysis]
    ) -> List[OptimizationRecommendation]:
        """Identify workflows using overpowered models for their task."""
        from uuid import uuid4

        recommendations = []

        for wf in workflows:
            current_profile = self.MODEL_PROFILES.get(wf.primary_model)
            if not current_profile:
                continue

            # High success rate + simple tasks with premium model = downgrade opportunity
            if (wf.success_rate > 98 and
                wf.complexity_level in ["simple", "moderate"] and
                current_profile.capability_tier >= 4):

                # Find tier 3 alternatives
                alternatives = [
                    m for m in self.MODEL_PROFILES.values()
                    if m.capability_tier == 3 and m.cost_per_1k_tokens < current_profile.cost_per_1k_tokens
                ]

                if alternatives:
                    best_alt = min(alternatives, key=lambda m: m.cost_per_1k_tokens)

                    savings = wf.avg_cost * wf.execution_count * 2 * 0.5  # Estimate 50% savings

                    if savings > 10:
                        recommendations.append(OptimizationRecommendation(
                            recommendation_id=uuid4(),
                            organization_id=organization_id,
                            optimization_type=OptimizationType.MODEL_DOWNGRADE,
                            title=f"Downgrade from {wf.primary_model} to {best_alt.model_id}",
                            description=(
                                f"This workflow has {wf.success_rate:.1f}% success rate with "
                                f"'{wf.complexity_level}' complexity. A tier-3 model like "
                                f"{best_alt.model_id} is likely sufficient and ~50% cheaper."
                            ),
                            confidence=ConfidenceLevel.HIGH,
                            estimated_savings=savings,
                            affected_workflows=[wf.workflow_id],
                            current_config={"model": wf.primary_model, "tier": current_profile.capability_tier},
                            recommended_config={"model": best_alt.model_id, "tier": best_alt.capability_tier},
                            evidence={
                                "success_rate": wf.success_rate,
                                "execution_count": wf.execution_count,
                                "complexity": wf.complexity_level
                            },
                            auto_apply_eligible=False
                        ))

        return recommendations

    async def _analyze_latency_optimization(
        self,
        organization_id: str,
        workflows: List[WorkflowAnalysis]
    ) -> List[OptimizationRecommendation]:
        """Identify workflows that could benefit from faster models."""
        from uuid import uuid4

        recommendations = []

        for wf in workflows:
            current_profile = self.MODEL_PROFILES.get(wf.primary_model)
            if not current_profile:
                continue

            # If P95 latency is high and there's a faster alternative at same tier
            if wf.p95_latency_ms > 2000:  # >2s P95
                faster_models = [
                    m for m in self.MODEL_PROFILES.values()
                    if (m.capability_tier >= current_profile.capability_tier - 1 and
                        m.avg_latency_ms < current_profile.avg_latency_ms * 0.7)
                ]

                if faster_models:
                    fastest = min(faster_models, key=lambda m: m.avg_latency_ms)
                    latency_improvement = current_profile.avg_latency_ms - fastest.avg_latency_ms

                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=uuid4(),
                        organization_id=organization_id,
                        optimization_type=OptimizationType.LATENCY_IMPROVEMENT,
                        title=f"Reduce latency with {fastest.model_id}",
                        description=(
                            f"Workflow has P95 latency of {wf.p95_latency_ms:.0f}ms. "
                            f"Switching to {fastest.model_id} could reduce this by ~{latency_improvement:.0f}ms."
                        ),
                        confidence=ConfidenceLevel.MEDIUM,
                        estimated_latency_improvement_ms=latency_improvement,
                        affected_workflows=[wf.workflow_id],
                        current_config={"model": wf.primary_model, "avg_latency_ms": current_profile.avg_latency_ms},
                        recommended_config={"model": fastest.model_id, "avg_latency_ms": fastest.avg_latency_ms},
                        evidence={
                            "current_p95_latency_ms": wf.p95_latency_ms,
                            "execution_count": wf.execution_count
                        },
                        auto_apply_eligible=False
                    ))

        return recommendations

    async def _analyze_ab_test_graduation(
        self,
        organization_id: str
    ) -> List[OptimizationRecommendation]:
        """Check for A/B tests ready to graduate."""
        from uuid import uuid4

        recommendations = []

        try:
            from backend.shared.ab_testing_models import ABTestModel, ABTestVariantModel

            # Get active A/B tests with sufficient data
            result = await self.db.execute(
                select(ABTestModel)
                .where(
                    and_(
                        ABTestModel.organization_id == organization_id,
                        ABTestModel.status == "running"
                    )
                )
            )

            for test in result.scalars().all():
                # Get variants and their metrics
                variants_result = await self.db.execute(
                    select(ABTestVariantModel)
                    .where(ABTestVariantModel.test_id == test.test_id)
                )
                variants = list(variants_result.scalars().all())

                if len(variants) < 2:
                    continue

                # Calculate which variant is winning
                variant_scores = []
                for v in variants:
                    score = v.success_count / max(v.total_count, 1)
                    variant_scores.append((v, score, v.total_count))

                # Sort by score
                variant_scores.sort(key=lambda x: x[1], reverse=True)
                winner, win_score, win_count = variant_scores[0]
                runner_up, ru_score, ru_count = variant_scores[1]

                # Check for statistical significance (simplified)
                if win_count >= 100 and ru_count >= 100:
                    # Calculate effect size
                    effect_size = (win_score - ru_score) / max(ru_score, 0.01)

                    if effect_size > 0.1:  # 10% improvement
                        confidence = ConfidenceLevel.HIGH if effect_size > 0.2 else ConfidenceLevel.MEDIUM

                        recommendations.append(OptimizationRecommendation(
                            recommendation_id=uuid4(),
                            organization_id=organization_id,
                            optimization_type=OptimizationType.AB_TEST_GRADUATION,
                            title=f"Graduate A/B test: {test.name}",
                            description=(
                                f"Variant '{winner.name}' is winning with {win_score*100:.1f}% success rate "
                                f"vs {ru_score*100:.1f}% for '{runner_up.name}'. "
                                f"Effect size: {effect_size*100:.1f}%. Ready to graduate."
                            ),
                            confidence=confidence,
                            estimated_savings=None,
                            affected_workflows=[],
                            current_config={"test_id": str(test.test_id), "status": "running"},
                            recommended_config={
                                "action": "graduate",
                                "winning_variant": winner.name,
                                "winning_variant_id": str(winner.variant_id)
                            },
                            evidence={
                                "winner_success_rate": win_score,
                                "runner_up_success_rate": ru_score,
                                "winner_sample_size": win_count,
                                "effect_size": effect_size
                            },
                            auto_apply_eligible=confidence == ConfidenceLevel.HIGH
                        ))
        except Exception as e:
            logger.warning(f"Failed to analyze A/B tests: {e}")

        return recommendations

    async def _analyze_cache_opportunities(
        self,
        organization_id: str,
        workflows: List[WorkflowAnalysis]
    ) -> List[OptimizationRecommendation]:
        """Identify workflows that could benefit from response caching."""
        from uuid import uuid4

        recommendations = []

        for wf in workflows:
            # Workflows with consistent token patterns and high volume are good cache candidates
            if (wf.token_usage_pattern == "consistent" and
                wf.execution_count > 50 and
                wf.complexity_level == "simple"):

                # Estimate 30% cache hit rate for simple consistent workflows
                estimated_cache_savings = wf.avg_cost * wf.execution_count * 0.3 * 2

                if estimated_cache_savings > 5:
                    recommendations.append(OptimizationRecommendation(
                        recommendation_id=uuid4(),
                        organization_id=organization_id,
                        optimization_type=OptimizationType.CACHE_ENABLEMENT,
                        title=f"Enable response caching for workflow",
                        description=(
                            f"This workflow has consistent patterns across {wf.execution_count} "
                            f"executions. Enabling semantic caching could save ~${estimated_cache_savings:.2f}/month."
                        ),
                        confidence=ConfidenceLevel.LOW,  # Caching needs testing
                        estimated_savings=estimated_cache_savings,
                        affected_workflows=[wf.workflow_id],
                        current_config={"caching_enabled": False},
                        recommended_config={"caching_enabled": True, "cache_ttl_seconds": 3600},
                        evidence={
                            "execution_count": wf.execution_count,
                            "pattern": wf.token_usage_pattern,
                            "estimated_hit_rate": 0.3
                        },
                        auto_apply_eligible=False
                    ))

        return recommendations

    async def apply_recommendation(
        self,
        recommendation_id: UUID,
        approved_by: str
    ) -> bool:
        """
        Apply an approved optimization recommendation.

        Returns True if successfully applied.
        """
        # Find recommendation in cache
        recommendation = None
        for org_recs in self._recommendations_cache.values():
            for rec in org_recs:
                if rec.recommendation_id == recommendation_id:
                    recommendation = rec
                    break

        if not recommendation:
            logger.error(f"Recommendation {recommendation_id} not found")
            return False

        if recommendation.status != OptimizationStatus.APPROVED:
            logger.error(f"Recommendation {recommendation_id} not approved (status: {recommendation.status})")
            return False

        try:
            if recommendation.optimization_type == OptimizationType.MODEL_DOWNGRADE:
                await self._apply_model_change(recommendation)
            elif recommendation.optimization_type == OptimizationType.AB_TEST_GRADUATION:
                await self._apply_ab_test_graduation(recommendation)
            elif recommendation.optimization_type == OptimizationType.CACHE_ENABLEMENT:
                await self._apply_cache_enablement(recommendation)
            else:
                logger.warning(f"Optimization type {recommendation.optimization_type} not yet implemented for auto-apply")
                return False

            recommendation.status = OptimizationStatus.APPLIED
            recommendation.applied_at = datetime.utcnow()

            logger.info(f"Applied optimization {recommendation_id} by {approved_by}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply optimization {recommendation_id}: {e}")
            return False

    async def _apply_model_change(self, recommendation: OptimizationRecommendation) -> None:
        """Apply a model change to affected workflows."""
        from backend.shared.workflow_models import WorkflowModel

        new_model = recommendation.recommended_config.get("model")

        for workflow_id in recommendation.affected_workflows:
            result = await self.db.execute(
                select(WorkflowModel).where(WorkflowModel.workflow_id == workflow_id)
            )
            workflow = result.scalar_one_or_none()

            if workflow:
                config = workflow.config or {}
                config["model"] = new_model
                config["_optimization_applied"] = str(recommendation.recommendation_id)
                config["_previous_model"] = recommendation.current_config.get("model")
                workflow.config = config

        await self.db.commit()

    async def _apply_ab_test_graduation(self, recommendation: OptimizationRecommendation) -> None:
        """Graduate an A/B test to the winning variant."""
        from backend.shared.ab_testing_models import ABTestModel

        test_id = UUID(recommendation.current_config.get("test_id"))

        result = await self.db.execute(
            select(ABTestModel).where(ABTestModel.test_id == test_id)
        )
        test = result.scalar_one_or_none()

        if test:
            test.status = "completed"
            test.winning_variant_id = UUID(recommendation.recommended_config.get("winning_variant_id"))
            test.completed_at = datetime.utcnow()

        await self.db.commit()

    async def _apply_cache_enablement(self, recommendation: OptimizationRecommendation) -> None:
        """Enable caching for affected workflows."""
        from backend.shared.workflow_models import WorkflowModel

        for workflow_id in recommendation.affected_workflows:
            result = await self.db.execute(
                select(WorkflowModel).where(WorkflowModel.workflow_id == workflow_id)
            )
            workflow = result.scalar_one_or_none()

            if workflow:
                config = workflow.config or {}
                config["caching_enabled"] = True
                config["cache_ttl_seconds"] = recommendation.recommended_config.get("cache_ttl_seconds", 3600)
                workflow.config = config

        await self.db.commit()

    def get_cached_recommendations(
        self,
        organization_id: str
    ) -> List[OptimizationRecommendation]:
        """Get cached recommendations for an organization."""
        return self._recommendations_cache.get(organization_id, [])

    async def get_optimization_summary(
        self,
        organization_id: str
    ) -> Dict[str, Any]:
        """Get summary of optimization opportunities."""
        recommendations = await self.analyze_organization(organization_id)

        total_savings = sum(r.estimated_savings or 0 for r in recommendations)
        total_latency_improvement = sum(r.estimated_latency_improvement_ms or 0 for r in recommendations)

        by_type = {}
        for r in recommendations:
            type_name = r.optimization_type.value
            if type_name not in by_type:
                by_type[type_name] = {"count": 0, "savings": 0}
            by_type[type_name]["count"] += 1
            by_type[type_name]["savings"] += r.estimated_savings or 0

        return {
            "organization_id": organization_id,
            "total_recommendations": len(recommendations),
            "total_estimated_monthly_savings": total_savings,
            "total_latency_improvement_ms": total_latency_improvement,
            "by_type": by_type,
            "high_confidence_count": len([r for r in recommendations if r.confidence == ConfidenceLevel.HIGH]),
            "auto_apply_eligible_count": len([r for r in recommendations if r.auto_apply_eligible]),
            "recommendations": [r.to_dict() for r in recommendations[:10]]  # Top 10
        }


# Singleton instance
_optimization_engine: Optional[AutoOptimizationEngine] = None


def get_optimization_engine(db: AsyncSession) -> AutoOptimizationEngine:
    """Get or create optimization engine instance."""
    global _optimization_engine
    if _optimization_engine is None or _optimization_engine.db != db:
        _optimization_engine = AutoOptimizationEngine(db)
    return _optimization_engine
