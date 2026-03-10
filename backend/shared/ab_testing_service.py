"""
A/B Testing Service - P1 Feature #2

Business logic for running A/B tests and experiments.

Key Features:
- Create and manage experiments
- Traffic splitting and variant assignment
- Statistical significance testing
- Performance metrics comparison
- Automatic winner selection
- Gradual rollout support
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import hashlib
import random
import math

try:
    from scipy.stats import chi2
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from backend.shared.ab_testing_models import (
    ABExperiment,
    ABVariant,
    ABAssignment,
    ABMetric,
    ABExperimentCreate,
    ABVariantCreate,
    ABAssignmentCreate,
    ABMetricCreate,
    ABCompletionRequest,
    ABExperimentResults,
    ExperimentStatus,
    VariantType,
    TrafficSplitStrategy,
    MetricType,
    WinnerSelectionCriteria,
)


class ABTestingService:
    """Service for A/B testing and experimentation."""

    @staticmethod
    async def create_experiment(
        db: AsyncSession,
        experiment_data: ABExperimentCreate,
        user_id: str,
        organization_id: Optional[int] = None,
    ) -> ABExperiment:
        """
        Create new A/B test experiment.

        Args:
            db: Database session
            experiment_data: Experiment configuration
            user_id: User creating experiment
            organization_id: Organization ID

        Returns:
            Created experiment with variants

        Raises:
            ValueError: If validation fails
        """
        # Convert enum objects to their string values
        traffic_split_strategy_val = experiment_data.traffic_split_strategy if isinstance(experiment_data.traffic_split_strategy, str) else experiment_data.traffic_split_strategy.value
        winner_selection_criteria_val = experiment_data.winner_selection_criteria if isinstance(experiment_data.winner_selection_criteria, str) else experiment_data.winner_selection_criteria.value

        # Create experiment
        experiment = ABExperiment(
            name=experiment_data.name,
            slug=experiment_data.slug,
            description=experiment_data.description,
            agent_id=experiment_data.agent_id,
            workflow_id=experiment_data.workflow_id,
            task_type=experiment_data.task_type,
            organization_id=organization_id,
            created_by_user_id=user_id,
            traffic_split_strategy=traffic_split_strategy_val,
            total_traffic_percentage=experiment_data.total_traffic_percentage,
            hypothesis=experiment_data.hypothesis,
            success_criteria=experiment_data.success_criteria,
            minimum_sample_size=experiment_data.minimum_sample_size,
            confidence_level=experiment_data.confidence_level,
            minimum_effect_size=experiment_data.minimum_effect_size,
            winner_selection_criteria=winner_selection_criteria_val,
            auto_promote_winner=experiment_data.auto_promote_winner,
            scheduled_end_date=experiment_data.scheduled_end_date,
            tags=experiment_data.tags,
            status='draft',
        )

        db.add(experiment)
        await db.flush()  # Get experiment ID

        # Create variants
        for variant_data in experiment_data.variants:
            # Convert variant_type enum to string
            variant_type_val = variant_data.variant_type if isinstance(variant_data.variant_type, str) else variant_data.variant_type.value

            variant = ABVariant(
                experiment_id=experiment.id,
                name=variant_data.name,
                variant_key=variant_data.variant_key,
                variant_type=variant_type_val,
                description=variant_data.description,
                config=variant_data.config,
                traffic_percentage=variant_data.traffic_percentage,
                agent_config_id=variant_data.agent_config_id,
                workflow_definition=variant_data.workflow_definition,
                prompt_template=variant_data.prompt_template,
                model_name=variant_data.model_name,
            )
            db.add(variant)

        await db.commit()
        await db.refresh(experiment)

        return experiment

    @staticmethod
    async def start_experiment(
        db: AsyncSession,
        experiment_id: int,
    ) -> ABExperiment:
        """
        Start running experiment.

        Args:
            db: Database session
            experiment_id: Experiment ID

        Returns:
            Started experiment
        """
        stmt = select(ABExperiment).where(ABExperiment.id == experiment_id)
        result = await db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        current_status = experiment.status.value if hasattr(experiment.status, 'value') else experiment.status
        if current_status not in ('draft', 'paused'):
            raise ValueError(f"Experiment must be in DRAFT or PAUSED status to start/resume, currently {current_status}")

        experiment.status = 'running'
        # Only set started_at on first start (draft → running), not on resume
        if current_status == 'draft':
            experiment.started_at = datetime.utcnow()

        await db.commit()
        await db.refresh(experiment)

        return experiment

    @staticmethod
    async def assign_variant(
        db: AsyncSession,
        experiment_id: int,
        assignment_data: ABAssignmentCreate,
    ) -> ABAssignment:
        """
        Assign user/session to a variant.

        Uses traffic splitting strategy to determine which variant.

        Args:
            db: Database session
            experiment_id: Experiment ID
            assignment_data: Assignment details (user_id, session_id, etc.)

        Returns:
            Created assignment

        Raises:
            ValueError: If experiment not found or not running
        """
        # Get experiment with variants
        stmt = select(ABExperiment).where(ABExperiment.id == experiment_id)
        result = await db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        if experiment.status != 'running':
            raise ValueError(f"Experiment not running, status: {experiment.status}")

        # Get active variants
        stmt = select(ABVariant).where(
            and_(
                ABVariant.experiment_id == experiment_id,
                ABVariant.is_active == True
            )
        ).order_by(ABVariant.id)
        result = await db.execute(stmt)
        variants = result.scalars().all()

        if not variants:
            raise ValueError("No active variants found")

        # Select variant based on strategy
        selected_variant = await ABTestingService._select_variant(
            db,
            experiment,
            variants,
            assignment_data,
        )

        # Create assignment hash for consistent assignment (if using user_hash strategy)
        assignment_hash = None
        if experiment.traffic_split_strategy == 'user_hash' and assignment_data.user_id:
            assignment_hash = ABTestingService._generate_hash(
                f"{experiment_id}:{assignment_data.user_id}"
            )

        # Create assignment
        assignment = ABAssignment(
            experiment_id=experiment_id,
            variant_id=selected_variant.id,
            user_id=assignment_data.user_id,
            session_id=assignment_data.session_id,
            execution_id=assignment_data.execution_id,
            assignment_hash=assignment_hash,
            assignment_reason=experiment.traffic_split_strategy,
        )

        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)

        return assignment

    @staticmethod
    async def record_completion(
        db: AsyncSession,
        completion_data: ABCompletionRequest,
        count_as_conversion: bool = False,
    ) -> ABAssignment:
        """
        Record completion of assigned variant execution.

        Updates assignment with outcome and metrics.

        IMPORTANT: The `success` field in completion_data has two meanings:
        - success=True: LLM call completed without errors
        - success=False: LLM call failed with an error

        The `count_as_conversion` parameter controls whether success=True
        should increment the variant's success_count (conversion metric):
        - count_as_conversion=False (default): Only tracks completion + error status
          Success_count is NOT incremented. Use this for automatic LLM call tracking.
        - count_as_conversion=True: Increments success_count when success=True.
          Use this when recording user feedback or explicit quality signals.

        This allows separating "LLM call completed" (tracked via sample_count)
        from "user liked the output" (tracked via success_count/conversion rate).

        Args:
            db: Database session
            completion_data: Completion details (success, latency, cost, etc.)
            count_as_conversion: If True, success=True increments success_count

        Returns:
            Updated assignment
        """
        # Get assignment
        stmt = select(ABAssignment).where(ABAssignment.id == completion_data.assignment_id)
        result = await db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            raise ValueError(f"Assignment {completion_data.assignment_id} not found")

        # Update assignment
        assignment.completed = True
        assignment.success = completion_data.success
        assignment.latency_ms = completion_data.latency_ms
        assignment.cost = completion_data.cost
        assignment.error_message = completion_data.error_message
        assignment.custom_metrics = completion_data.custom_metrics
        assignment.completed_at = datetime.utcnow()

        # Update variant aggregates
        stmt = select(ABVariant).where(ABVariant.id == assignment.variant_id)
        result = await db.execute(stmt)
        variant = result.scalar_one_or_none()

        if variant:
            variant.sample_count += 1

            # Only count as conversion (increment success_count) if explicitly requested
            # This separates "LLM call completed" from "user gave positive feedback"
            if completion_data.success and count_as_conversion:
                variant.success_count += 1
            elif not completion_data.success:
                # Always track errors
                variant.error_count += 1

            if completion_data.latency_ms:
                variant.total_latency_ms += completion_data.latency_ms

            if completion_data.cost:
                variant.total_cost += completion_data.cost

            # Recalculate metrics
            # Note: success_rate now represents conversion rate (positive feedback / total samples)
            variant.success_rate = (variant.success_count / variant.sample_count) * 100 if variant.sample_count > 0 else 0
            variant.error_rate = (variant.error_count / variant.sample_count) * 100 if variant.sample_count > 0 else 0
            variant.avg_latency_ms = variant.total_latency_ms / variant.sample_count if variant.sample_count > 0 else 0
            variant.avg_cost = variant.total_cost / variant.sample_count if variant.sample_count > 0 else 0

        # Update experiment total samples
        stmt = select(ABExperiment).where(ABExperiment.id == assignment.experiment_id)
        result = await db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if experiment:
            experiment.total_samples += 1

        # Record metrics
        if completion_data.latency_ms:
            metric = ABMetric(
                experiment_id=assignment.experiment_id,
                variant_id=assignment.variant_id,
                assignment_id=assignment.id,
                metric_type='latency',
                metric_name="execution_latency",
                metric_value=completion_data.latency_ms,
                metric_unit="ms",
            )
            db.add(metric)

        if completion_data.cost:
            metric = ABMetric(
                experiment_id=assignment.experiment_id,
                variant_id=assignment.variant_id,
                assignment_id=assignment.id,
                metric_type='cost',
                metric_name="execution_cost",
                metric_value=completion_data.cost,
                metric_unit="$",
            )
            db.add(metric)

        # Success/error metric
        metric = ABMetric(
            experiment_id=assignment.experiment_id,
            variant_id=assignment.variant_id,
            assignment_id=assignment.id,
            metric_type='success_rate' if completion_data.success else 'error_rate',
            metric_name="execution_outcome",
            metric_value=1.0 if completion_data.success else 0.0,
            metric_unit="boolean",
        )
        db.add(metric)

        # Custom metrics
        for metric_name, metric_value in completion_data.custom_metrics.items():
            metric = ABMetric(
                experiment_id=assignment.experiment_id,
                variant_id=assignment.variant_id,
                assignment_id=assignment.id,
                metric_type='custom',
                metric_name=metric_name,
                metric_value=metric_value,
            )
            db.add(metric)

        await db.commit()
        await db.refresh(assignment)

        return assignment

    @staticmethod
    async def analyze_experiment(
        db: AsyncSession,
        experiment_id: int,
    ) -> ABExperimentResults:
        """
        Analyze experiment results and determine statistical significance.

        Args:
            db: Database session
            experiment_id: Experiment ID

        Returns:
            Experiment results with statistical analysis
        """
        # Get experiment with variants
        stmt = select(ABExperiment).where(ABExperiment.id == experiment_id)
        result = await db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Get variants with metrics
        stmt = select(ABVariant).where(ABVariant.experiment_id == experiment_id)
        result = await db.execute(stmt)
        variants = result.scalars().all()

        if len(variants) < 2:
            raise ValueError("Need at least 2 variants for analysis")

        # Check if we have enough samples
        min_samples_met = all(v.sample_count >= experiment.minimum_sample_size for v in variants)

        if not min_samples_met:
            return ABExperimentResults(
                experiment_id=experiment.id,
                experiment_name=experiment.name,
                status=experiment.status,
                total_samples=experiment.total_samples,
                is_statistically_significant=False,
                p_value=None,
                confidence_level=experiment.confidence_level,
                winner_variant_id=None,
                winner_confidence=None,
                variants=[ABTestingService._variant_to_dict(v) for v in variants],
                recommendation="Continue test - need more samples",
                insights=[
                    f"Minimum {experiment.minimum_sample_size} samples per variant required",
                    f"Current samples: " + ", ".join([f"{v.name}: {v.sample_count}" for v in variants]),
                ],
            )

        # Statistical significance testing (chi-square test for success rates)
        is_significant, p_value = ABTestingService._calculate_significance(variants, experiment.confidence_level)

        # Select winner
        winner_variant = ABTestingService._select_winner(variants, experiment.winner_selection_criteria)

        # Calculate confidence in winner
        winner_confidence = ABTestingService._calculate_winner_confidence(variants, winner_variant)

        # Generate insights
        insights = ABTestingService._generate_insights(variants, winner_variant, experiment)

        # Determine recommendation
        recommendation = ABTestingService._generate_recommendation(
            is_significant,
            winner_variant,
            winner_confidence,
            experiment,
        )

        return ABExperimentResults(
            experiment_id=experiment.id,
            experiment_name=experiment.name,
            status=experiment.status,
            total_samples=experiment.total_samples,
            is_statistically_significant=is_significant,
            p_value=p_value,
            confidence_level=experiment.confidence_level,
            winner_variant_id=winner_variant.id if winner_variant else None,
            winner_confidence=winner_confidence,
            variants=[ABTestingService._variant_to_dict(v) for v in variants],
            recommendation=recommendation,
            insights=insights,
        )

    @staticmethod
    async def complete_experiment(
        db: AsyncSession,
        experiment_id: int,
        promote_winner: bool = False,
    ) -> ABExperiment:
        """
        Complete experiment and optionally promote winner.

        Args:
            db: Database session
            experiment_id: Experiment ID
            promote_winner: Whether to promote winner to production

        Returns:
            Completed experiment
        """
        # Analyze first
        results = await ABTestingService.analyze_experiment(db, experiment_id)

        # Get experiment
        stmt = select(ABExperiment).where(ABExperiment.id == experiment_id)
        result = await db.execute(stmt)
        experiment = result.scalar_one_or_none()

        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Update experiment
        experiment.status = 'completed'
        experiment.completed_at = datetime.utcnow()
        experiment.is_statistically_significant = results.is_statistically_significant
        experiment.p_value = results.p_value
        experiment.winner_variant_id = results.winner_variant_id
        experiment.winner_confidence = results.winner_confidence

        # Promote winner if requested and winner exists
        if promote_winner and results.winner_variant_id:
            experiment.promoted_at = datetime.utcnow()

            # Mark winner variant
            stmt = select(ABVariant).where(ABVariant.id == results.winner_variant_id)
            result = await db.execute(stmt)
            winner_variant = result.scalar_one_or_none()
            if winner_variant:
                winner_variant.is_winner = True

        await db.commit()
        await db.refresh(experiment)

        return experiment

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    @staticmethod
    async def _select_variant(
        db: AsyncSession,
        experiment: ABExperiment,
        variants: List[ABVariant],
        assignment_data: ABAssignmentCreate,
    ) -> ABVariant:
        """Select variant based on traffic splitting strategy."""
        strategy = experiment.traffic_split_strategy

        if strategy == 'random':
            # Random selection weighted by traffic percentage
            weights = [v.traffic_percentage for v in variants]
            selected = random.choices(variants, weights=weights, k=1)[0]
            return selected

        elif strategy == 'weighted':
            # Same as random
            weights = [v.traffic_percentage for v in variants]
            selected = random.choices(variants, weights=weights, k=1)[0]
            return selected

        elif strategy == 'user_hash':
            # Consistent per user
            if not assignment_data.user_id:
                # Fall back to random
                weights = [v.traffic_percentage for v in variants]
                selected = random.choices(variants, weights=weights, k=1)[0]
                return selected

            # Hash user ID and select variant
            hash_value = ABTestingService._generate_hash(f"{experiment.id}:{assignment_data.user_id}")
            hash_int = int(hash_value[:8], 16)
            percentage = (hash_int % 100) + 1  # 1-100

            cumulative = 0
            for variant in variants:
                cumulative += variant.traffic_percentage
                if percentage <= cumulative:
                    return variant

            return variants[-1]  # Fallback

        elif strategy == 'round_robin':
            # Rotate through variants
            stmt = select(func.count(ABAssignment.id)).where(
                ABAssignment.experiment_id == experiment.id
            )
            result = await db.execute(stmt)
            assignment_count = result.scalar()

            index = assignment_count % len(variants)
            return variants[index]

        else:
            # Default to random
            weights = [v.traffic_percentage for v in variants]
            selected = random.choices(variants, weights=weights, k=1)[0]
            return selected

    @staticmethod
    def _generate_hash(value: str) -> str:
        """Generate consistent hash for user assignment."""
        return hashlib.md5(value.encode()).hexdigest()

    @staticmethod
    def _calculate_significance(variants: List[ABVariant], confidence_level: float) -> Tuple[bool, float]:
        """
        Calculate statistical significance using chi-square test.

        Returns (is_significant, p_value)
        """
        if len(variants) < 2:
            return False, 1.0

        # Simple chi-square test for success rates
        total_successes = sum(v.success_count for v in variants)
        total_samples = sum(v.sample_count for v in variants)

        if total_samples == 0:
            return False, 1.0

        expected_rate = total_successes / total_samples

        chi_square = 0
        for variant in variants:
            if variant.sample_count == 0:
                continue

            expected_successes = variant.sample_count * expected_rate
            if expected_successes > 0:
                chi_square += ((variant.success_count - expected_successes) ** 2) / expected_successes

        # Degrees of freedom = n_variants - 1
        df = len(variants) - 1

        # Calculate p-value using chi-square survival function
        if HAS_SCIPY:
            p_value = float(chi2.sf(chi_square, df)) if chi_square > 0 else 1.0
        else:
            # Fallback approximation when scipy is not installed
            # Less accurate but directionally correct for large chi_square values
            if chi_square <= 0:
                p_value = 1.0
            elif df == 1:
                # For df=1, use the normal approximation: p ≈ 2 * Φ(-√χ²)
                z = math.sqrt(chi_square)
                # Abramowitz and Stegun approximation for erfc
                t = 1.0 / (1.0 + 0.3275911 * z / math.sqrt(2))
                coeffs = [0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429]
                poly = sum(c * t**(i+1) for i, c in enumerate(coeffs))
                p_value = poly * math.exp(-z * z / 2)
            else:
                # For df>1 without scipy, use Wilson-Hilferty approximation
                z = ((chi_square / df) ** (1/3) - (1 - 2/(9*df))) / math.sqrt(2/(9*df))
                # Standard normal CDF approximation
                if z > 6:
                    p_value = 0.0
                elif z < -6:
                    p_value = 1.0
                else:
                    t = 1.0 / (1.0 + 0.2316419 * abs(z))
                    coeffs = [0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429]
                    poly = sum(c * t**(i+1) for i, c in enumerate(coeffs))
                    cdf = 1.0 - poly * math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
                    p_value = 1.0 - cdf if z > 0 else cdf

        is_significant = p_value < (1 - confidence_level)

        return is_significant, p_value

    @staticmethod
    def _select_winner(variants: List[ABVariant], criteria: str) -> Optional[ABVariant]:
        """Select winner based on criteria."""
        if not variants:
            return None

        if criteria == 'highest_success_rate':
            return max(variants, key=lambda v: v.success_rate)

        elif criteria == 'lowest_latency':
            return min(variants, key=lambda v: v.avg_latency_ms if v.avg_latency_ms > 0 else float('inf'))

        elif criteria == 'lowest_cost':
            return min(variants, key=lambda v: v.avg_cost if v.avg_cost > 0 else float('inf'))

        elif criteria == 'composite_score':
            # Composite score: weighted combination
            # Normalize metrics and combine (higher is better)
            scores = []
            for variant in variants:
                score = 0
                # Success rate (40% weight)
                score += variant.success_rate * 0.4
                # Inverse latency (30% weight) - lower is better
                if variant.avg_latency_ms > 0:
                    score += (1 / variant.avg_latency_ms) * 30000 * 0.3
                # Inverse cost (30% weight) - lower is better
                if variant.avg_cost > 0:
                    score += (1 / variant.avg_cost) * 100 * 0.3

                scores.append((variant, score))

            return max(scores, key=lambda x: x[1])[0]

        else:
            return max(variants, key=lambda v: v.success_rate)

    @staticmethod
    def _calculate_winner_confidence(variants: List[ABVariant], winner: Optional[ABVariant]) -> float:
        """Calculate confidence in winner selection."""
        if not winner or len(variants) < 2:
            return 0.0

        # Simple confidence: difference between winner and second place
        sorted_variants = sorted(variants, key=lambda v: v.success_rate, reverse=True)
        if sorted_variants[0] != winner:
            return 0.0

        if len(sorted_variants) < 2:
            return 1.0

        winner_rate = sorted_variants[0].success_rate
        second_rate = sorted_variants[1].success_rate

        if winner_rate == 0:
            return 0.0

        difference = (winner_rate - second_rate) / winner_rate
        confidence = min(1.0, max(0.0, difference))

        return confidence

    @staticmethod
    def _generate_insights(
        variants: List[ABVariant],
        winner: Optional[ABVariant],
        experiment: ABExperiment,
    ) -> List[str]:
        """Generate insights from experiment results."""
        insights = []

        if not variants:
            return insights

        # Sample size insights
        total_samples = sum(v.sample_count for v in variants)
        insights.append(f"Collected {total_samples:,} total samples across {len(variants)} variants")

        # Performance insights
        best_success = max(variants, key=lambda v: v.success_rate)
        worst_success = min(variants, key=lambda v: v.success_rate)

        if best_success.success_rate > worst_success.success_rate:
            improvement = best_success.success_rate - worst_success.success_rate
            insights.append(
                f"Best variant ({best_success.name}) has {improvement:.1f}% higher success rate than worst ({worst_success.name})"
            )

        # Cost insights
        costs = [v.avg_cost for v in variants if v.avg_cost > 0]
        if costs:
            best_cost = min(variants, key=lambda v: v.avg_cost if v.avg_cost > 0 else float('inf'))
            worst_cost = max(variants, key=lambda v: v.avg_cost)

            if worst_cost.avg_cost > 0:
                savings = ((worst_cost.avg_cost - best_cost.avg_cost) / worst_cost.avg_cost) * 100
                insights.append(
                    f"Cost difference: {best_cost.name} is {savings:.1f}% cheaper than {worst_cost.name}"
                )

        # Latency insights
        latencies = [v.avg_latency_ms for v in variants if v.avg_latency_ms > 0]
        if latencies:
            fastest = min(variants, key=lambda v: v.avg_latency_ms if v.avg_latency_ms > 0 else float('inf'))
            slowest = max(variants, key=lambda v: v.avg_latency_ms)

            if slowest.avg_latency_ms > 0:
                speedup = ((slowest.avg_latency_ms - fastest.avg_latency_ms) / slowest.avg_latency_ms) * 100
                insights.append(
                    f"Latency difference: {fastest.name} is {speedup:.1f}% faster than {slowest.name}"
                )

        return insights

    @staticmethod
    def _generate_recommendation(
        is_significant: bool,
        winner: Optional[ABVariant],
        winner_confidence: float,
        experiment: ABExperiment,
    ) -> str:
        """Generate action recommendation."""
        if not is_significant:
            return "Continue test - results not statistically significant yet"

        if not winner:
            return "No clear winner - variants performing similarly"

        if winner_confidence >= 0.8:
            return f"Deploy {winner.name} - clear winner with {winner_confidence:.0%} confidence"
        elif winner_confidence >= 0.5:
            return f"Consider deploying {winner.name} - moderate confidence ({winner_confidence:.0%})"
        else:
            return f"Inconclusive - {winner.name} slightly ahead but low confidence ({winner_confidence:.0%})"

    @staticmethod
    def _variant_to_dict(variant: ABVariant) -> Dict[str, Any]:
        """Convert variant to dictionary for results."""
        return {
            "id": variant.id,
            "name": variant.name,
            "variant_key": variant.variant_key,
            "variant_type": variant.variant_type,
            "traffic_percentage": variant.traffic_percentage,
            "sample_count": variant.sample_count,
            "success_count": variant.success_count,
            "error_count": variant.error_count,
            "success_rate": variant.success_rate,
            "error_rate": variant.error_rate,
            "avg_latency_ms": variant.avg_latency_ms,
            "avg_cost": variant.avg_cost,
            "is_winner": variant.is_winner,
        }
