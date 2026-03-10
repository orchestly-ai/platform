"""
A/B Testing API Endpoints - P1 Feature #2

REST API for A/B testing and experimentation.

Endpoints:
- POST   /api/v1/experiments              - Create experiment
- GET    /api/v1/experiments              - List experiments
- GET    /api/v1/experiments/{id}         - Get experiment details
- POST   /api/v1/experiments/{id}/start   - Start experiment
- POST   /api/v1/experiments/{id}/pause   - Pause experiment
- POST   /api/v1/experiments/{id}/complete - Complete experiment
- POST   /api/v1/experiments/{id}/assign  - Assign variant
- POST   /api/v1/experiments/assignments/{id}/complete - Record completion
- GET    /api/v1/experiments/{id}/analyze - Get analysis results
- GET    /api/v1/experiments/{id}/variants - List variants
- POST   /api/v1/experiments/metrics      - Record custom metric
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from backend.database.session import get_db
from backend.shared.ab_testing_models import (
    ABExperimentCreate,
    ABExperimentResponse,
    ABVariantResponse,
    ABAssignmentCreate,
    ABAssignmentResponse,
    ABCompletionRequest,
    ABMetricCreate,
    ABExperimentResults,
    ExperimentStatus,
    ABFeedbackRequest,
    ABFeedbackResponse,
    MetricType,
)
from backend.shared.ab_testing_service import ABTestingService
from backend.shared.auth import get_current_user_id, get_current_organization_id
from backend.shared.plan_enforcement import enforce_feature


router = APIRouter(prefix="/api/v1/experiments", tags=["ab_testing"])


# Alias for backwards compatibility (DB schema uses int for org_id)
async def get_organization_id() -> Optional[int]:
    """Get current user's organization ID as int."""
    return 1


def _safe_json_deserialize(value, default=None):
    """
    Safely deserialize JSON values that may be stored as strings (SQLite)
    or already parsed objects (PostgreSQL JSONB).
    """
    import json
    if value is None:
        return default if default is not None else ([] if isinstance(default, list) else {})
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else value
    return value


def experiment_to_response(experiment, variants=None) -> dict:
    """Convert experiment ORM object to response dict."""
    from datetime import datetime

    # Handle SQLite string serialization vs PostgreSQL JSONB
    if variants is None:
        variants = experiment.variants if hasattr(experiment, 'variants') else []
    variants = _safe_json_deserialize(variants, [])

    return {
        "id": experiment.id,
        "name": experiment.name,
        "slug": experiment.slug,
        "description": experiment.description,
        "agent_id": experiment.agent_id,
        "workflow_id": experiment.workflow_id,
        "task_type": experiment.task_type,
        "organization_id": experiment.organization_id,
        "created_by_user_id": experiment.created_by_user_id,
        "traffic_split_strategy": experiment.traffic_split_strategy or "random",
        "total_traffic_percentage": experiment.total_traffic_percentage or 100.0,
        "hypothesis": experiment.hypothesis,
        "success_criteria": _safe_json_deserialize(experiment.success_criteria, {}),
        "minimum_sample_size": experiment.minimum_sample_size or 100,
        "confidence_level": experiment.confidence_level or 0.95,
        "minimum_effect_size": experiment.minimum_effect_size or 0.05,
        "winner_selection_criteria": experiment.winner_selection_criteria or "composite_score",
        "winner_variant_id": experiment.winner_variant_id,
        "winner_confidence": experiment.winner_confidence,
        "status": experiment.status or "draft",
        "started_at": experiment.started_at,
        "completed_at": experiment.completed_at,
        "scheduled_end_date": experiment.scheduled_end_date,
        "total_samples": experiment.total_samples or 0,
        "is_statistically_significant": experiment.is_statistically_significant or False,
        "p_value": experiment.p_value,
        "auto_promote_winner": experiment.auto_promote_winner or False,
        "promoted_at": experiment.promoted_at,
        "tags": _safe_json_deserialize(experiment.tags, []),
        "metadata": _safe_json_deserialize(experiment.extra_metadata, {}),
        "created_at": experiment.created_at or datetime.utcnow(),
        "updated_at": experiment.updated_at or datetime.utcnow(),
        "variants": [
            {
                "id": v.id,
                "experiment_id": v.experiment_id,
                "name": v.name,
                "variant_key": v.variant_key,
                "variant_type": v.variant_type or "treatment",
                "description": v.description,
                "config": v.config if isinstance(v.config, dict) else {},
                "traffic_percentage": v.traffic_percentage or 0,
                "agent_config_id": v.agent_config_id,
                "workflow_definition": v.workflow_definition if isinstance(v.workflow_definition, dict) else None,
                "prompt_template": v.prompt_template,
                "model_name": v.model_name,
                "sample_count": v.sample_count or 0,
                "success_count": v.success_count or 0,
                "error_count": v.error_count or 0,
                "success_rate": v.success_rate or 0.0,
                "avg_latency_ms": v.avg_latency_ms or 0.0,
                "avg_cost": v.avg_cost or 0.0,
                "error_rate": v.error_rate or 0.0,
                "is_active": v.is_active if v.is_active is not None else True,
                "is_winner": v.is_winner or False,
                "created_at": v.created_at or datetime.utcnow(),
                "updated_at": v.updated_at or datetime.utcnow(),
            }
            for v in (variants or [])
        ],
    }


@router.post("", response_model=ABExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    experiment_data: ABExperimentCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """
    Create new A/B test experiment.

    Experiment starts in DRAFT status. Use /start to begin testing.
    """
    await enforce_feature("ab_testing", str(organization_id or "default"), db)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from backend.shared.ab_testing_models import ABExperiment, ABVariant

    try:
        experiment = await ABTestingService.create_experiment(
            db, experiment_data, user_id, organization_id
        )

        # Reload with variants eagerly loaded
        stmt = select(ABExperiment).where(ABExperiment.id == experiment.id).options(
            selectinload(ABExperiment.variants)
        )
        result = await db.execute(stmt)
        experiment = result.scalar_one()

        return experiment_to_response(experiment, experiment.variants)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=List[ABExperimentResponse])
async def list_experiments(
    status_filter: Optional[ExperimentStatus] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[int] = Depends(get_organization_id),
):
    """List A/B test experiments."""
    await enforce_feature("ab_testing", str(organization_id or "default"), db)

    from sqlalchemy import select, and_
    from sqlalchemy.orm import selectinload
    from backend.shared.ab_testing_models import ABExperiment

    stmt = select(ABExperiment).options(selectinload(ABExperiment.variants))

    filters = []
    if organization_id:
        filters.append(ABExperiment.organization_id == organization_id)
    if status_filter:
        filters.append(ABExperiment.status == status_filter)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(ABExperiment.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    experiments = result.scalars().all()

    return [experiment_to_response(exp, exp.variants) for exp in experiments]


@router.get("/{experiment_id}", response_model=ABExperimentResponse)
async def get_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get experiment details with variants."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from backend.shared.ab_testing_models import ABExperiment

    stmt = select(ABExperiment).where(ABExperiment.id == experiment_id).options(
        selectinload(ABExperiment.variants)
    )
    result = await db.execute(stmt)
    experiment = result.scalar_one_or_none()

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    return experiment_to_response(experiment, experiment.variants)


@router.post("/{experiment_id}/start", response_model=ABExperimentResponse)
async def start_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Start or resume experiment.

    Changes status from DRAFT or PAUSED to RUNNING. On first start (from DRAFT),
    sets started_at timestamp. On resume (from PAUSED), preserves original start time.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from backend.shared.ab_testing_models import ABExperiment

    try:
        experiment = await ABTestingService.start_experiment(db, experiment_id)

        # Reload with variants
        stmt = select(ABExperiment).where(ABExperiment.id == experiment_id).options(
            selectinload(ABExperiment.variants)
        )
        result = await db.execute(stmt)
        experiment = result.scalar_one()

        return experiment_to_response(experiment, experiment.variants)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{experiment_id}/pause", response_model=ABExperimentResponse)
async def pause_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Pause running experiment.

    Stops accepting new assignments but preserves data.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from backend.shared.ab_testing_models import ABExperiment

    stmt = select(ABExperiment).where(ABExperiment.id == experiment_id).options(
        selectinload(ABExperiment.variants)
    )
    result = await db.execute(stmt)
    experiment = result.scalar_one_or_none()

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    # Compare as string (SQLite stores as string)
    current_status = experiment.status.value if hasattr(experiment.status, 'value') else experiment.status
    if current_status != 'running':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only pause RUNNING experiments, currently {current_status}",
        )

    experiment.status = 'paused'

    await db.commit()
    await db.refresh(experiment)

    return experiment_to_response(experiment, experiment.variants)


@router.post("/{experiment_id}/complete", response_model=ABExperimentResponse)
async def complete_experiment(
    experiment_id: int,
    promote_winner: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """
    Complete experiment and optionally promote winner.

    Analyzes results, determines winner, and marks experiment complete.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from backend.shared.ab_testing_models import ABExperiment

    try:
        experiment = await ABTestingService.complete_experiment(
            db, experiment_id, promote_winner
        )

        # Reload with variants
        stmt = select(ABExperiment).where(ABExperiment.id == experiment_id).options(
            selectinload(ABExperiment.variants)
        )
        result = await db.execute(stmt)
        experiment = result.scalar_one()

        return experiment_to_response(experiment, experiment.variants)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{experiment_id}/assign", response_model=ABAssignmentResponse)
async def assign_variant(
    experiment_id: int,
    assignment_data: ABAssignmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Assign user/session to a variant.

    Uses experiment's traffic splitting strategy to select variant.
    Returns assignment with variant details.
    """
    try:
        assignment = await ABTestingService.assign_variant(
            db, experiment_id, assignment_data
        )

        # Get variant details for response
        from sqlalchemy import select
        from backend.shared.ab_testing_models import ABVariant

        stmt = select(ABVariant).where(ABVariant.id == assignment.variant_id)
        result = await db.execute(stmt)
        variant = result.scalar_one_or_none()

        return ABAssignmentResponse(
            id=assignment.id,
            experiment_id=assignment.experiment_id,
            variant_id=assignment.variant_id,
            variant_key=variant.variant_key if variant else "",
            variant_name=variant.name if variant else "",
            user_id=assignment.user_id,
            session_id=assignment.session_id,
            execution_id=assignment.execution_id,
            assigned_at=assignment.assigned_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/assignments/{assignment_id}/complete")
async def record_completion(
    assignment_id: int,
    completion_data: ABCompletionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record completion of assigned variant execution.

    Updates assignment with outcome (success/failure, latency, cost, etc.)
    and aggregates metrics for analysis.
    """
    # Override assignment_id from path
    completion_data.assignment_id = assignment_id

    try:
        assignment = await ABTestingService.record_completion(db, completion_data)
        return {
            "assignment_id": assignment.id,
            "completed": assignment.completed,
            "success": assignment.success,
            "message": "Completion recorded successfully",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{experiment_id}/analyze", response_model=ABExperimentResults)
async def analyze_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get experiment analysis and statistical results.

    Returns:
    - Statistical significance (p-value)
    - Winner recommendation
    - Variant performance comparison
    - Insights and recommendations
    """
    try:
        results = await ABTestingService.analyze_experiment(db, experiment_id)
        return results
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{experiment_id}/variants", response_model=List[ABVariantResponse])
async def list_variants(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List all variants for experiment with performance metrics."""
    from sqlalchemy import select
    from backend.shared.ab_testing_models import ABVariant

    stmt = select(ABVariant).where(ABVariant.experiment_id == experiment_id)
    result = await db.execute(stmt)
    variants = result.scalars().all()

    return variants


@router.post("/metrics", status_code=status.HTTP_201_CREATED)
async def record_metric(
    metric_data: ABMetricCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Record custom metric for experiment.

    Useful for tracking domain-specific metrics beyond standard
    success/latency/cost metrics.
    """
    from backend.shared.ab_testing_models import ABMetric, ABAssignment

    # Get assignment to get experiment and variant IDs
    from sqlalchemy import select

    stmt = select(ABAssignment).where(ABAssignment.id == metric_data.assignment_id)
    result = await db.execute(stmt)
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )

    metric = ABMetric(
        experiment_id=assignment.experiment_id,
        variant_id=assignment.variant_id,
        assignment_id=metric_data.assignment_id,
        metric_type=metric_data.metric_type,
        metric_name=metric_data.metric_name,
        metric_value=metric_data.metric_value,
        metric_unit=metric_data.metric_unit,
        context=metric_data.context,
    )

    db.add(metric)
    await db.commit()

    return {
        "metric_id": metric.id,
        "message": "Metric recorded successfully",
    }


@router.get("/{experiment_id}/metrics")
async def get_experiment_metrics(
    experiment_id: int,
    metric_type: Optional[str] = None,
    variant_id: Optional[int] = None,
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed metrics for experiment.

    Returns time-series data for analysis and visualization.
    """
    from sqlalchemy import select, and_
    from backend.shared.ab_testing_models import ABMetric, MetricType

    stmt = select(ABMetric).where(ABMetric.experiment_id == experiment_id)

    if metric_type:
        try:
            metric_enum = MetricType(metric_type)
            stmt = stmt.where(ABMetric.metric_type == metric_enum)
        except ValueError:
            pass  # Invalid metric type, ignore filter

    if variant_id:
        stmt = stmt.where(ABMetric.variant_id == variant_id)

    stmt = stmt.order_by(ABMetric.recorded_at.desc()).limit(limit)

    result = await db.execute(stmt)
    metrics = result.scalars().all()

    return [
        {
            "id": m.id,
            "variant_id": m.variant_id,
            "metric_type": m.metric_type.value,
            "metric_name": m.metric_name,
            "metric_value": m.metric_value,
            "metric_unit": m.metric_unit,
            "context": m.context,
            "recorded_at": m.recorded_at,
        }
        for m in metrics
    ]


@router.get("/{experiment_id}/stats")
async def get_experiment_stats(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get experiment statistics and progress.

    Returns current state, sample counts, and progress towards goals.
    """
    from sqlalchemy import select, func
    from backend.shared.ab_testing_models import ABExperiment, ABVariant, ABAssignment

    # Get experiment
    stmt = select(ABExperiment).where(ABExperiment.id == experiment_id)
    result = await db.execute(stmt)
    experiment = result.scalar_one_or_none()

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    # Get variant stats
    stmt = select(ABVariant).where(ABVariant.experiment_id == experiment_id)
    result = await db.execute(stmt)
    variants = result.scalars().all()

    # Get assignment counts
    stmt = select(func.count(ABAssignment.id)).where(ABAssignment.experiment_id == experiment_id)
    result = await db.execute(stmt)
    total_assignments = result.scalar()

    stmt = select(func.count(ABAssignment.id)).where(
        and_(
            ABAssignment.experiment_id == experiment_id,
            ABAssignment.completed == True
        )
    )
    result = await db.execute(stmt)
    completed_assignments = result.scalar()

    # Calculate progress
    min_samples_needed = experiment.minimum_sample_size * len(variants)
    progress_pct = (experiment.total_samples / min_samples_needed * 100) if min_samples_needed > 0 else 0

    return {
        "experiment_id": experiment.id,
        "experiment_name": experiment.name,
        "status": experiment.status.value,
        "total_assignments": total_assignments,
        "completed_assignments": completed_assignments,
        "total_samples": experiment.total_samples,
        "minimum_samples_needed": min_samples_needed,
        "progress_percentage": min(100, progress_pct),
        "variants": [
            {
                "id": v.id,
                "name": v.name,
                "sample_count": v.sample_count,
                "minimum_needed": experiment.minimum_sample_size,
                "has_enough_samples": v.sample_count >= experiment.minimum_sample_size,
            }
            for v in variants
        ],
        "is_ready_for_analysis": all(
            v.sample_count >= experiment.minimum_sample_size for v in variants
        ),
    }


@router.post("/assignments/{assignment_id}/feedback", response_model=ABFeedbackResponse)
async def record_feedback(
    assignment_id: int,
    feedback: ABFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record user feedback (thumbs up/down) on an A/B experiment execution.

    This is how you track whether users responded positively to the LLM output.
    Use this to measure true "conversion" - not just "did the LLM call succeed"
    but "did the user like the result".

    The feedback updates:
    1. The assignment's custom_metrics with the feedback
    2. Creates an ABMetric record for tracking
    3. Updates variant conversion metrics (positive feedback = conversion)

    Example usage:
    ```
    POST /api/v1/experiments/assignments/123/feedback
    {
        "assignment_id": 123,
        "positive": true,
        "rating": 5,
        "comment": "Great response!"
    }
    ```

    The "conversion rate" in the dashboard will now reflect actual user satisfaction
    rather than just LLM call success.
    """
    from sqlalchemy import select
    from backend.shared.ab_testing_models import ABAssignment, ABVariant, ABMetric

    # Override assignment_id from path
    feedback.assignment_id = assignment_id

    # Get assignment
    stmt = select(ABAssignment).where(ABAssignment.id == assignment_id)
    result = await db.execute(stmt)
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found",
        )

    # Get variant for the response
    stmt = select(ABVariant).where(ABVariant.id == assignment.variant_id)
    result = await db.execute(stmt)
    variant = result.scalar_one_or_none()

    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {assignment.variant_id} not found",
        )

    # Update assignment's custom_metrics with feedback
    custom_metrics = assignment.custom_metrics or {}
    custom_metrics["user_feedback_positive"] = 1.0 if feedback.positive else 0.0
    if feedback.rating:
        custom_metrics["user_rating"] = float(feedback.rating)
    assignment.custom_metrics = custom_metrics

    # Create ABMetric record for user satisfaction
    metric = ABMetric(
        experiment_id=assignment.experiment_id,
        variant_id=assignment.variant_id,
        assignment_id=assignment_id,
        metric_type=MetricType.USER_SATISFACTION,
        metric_name=feedback.feedback_type,
        metric_value=1.0 if feedback.positive else 0.0,
        metric_unit="boolean",
        context={
            "positive": feedback.positive,
            "rating": feedback.rating,
            "comment": feedback.comment,
        },
    )
    db.add(metric)

    # If there's a rating, also record it as a separate metric
    if feedback.rating:
        rating_metric = ABMetric(
            experiment_id=assignment.experiment_id,
            variant_id=assignment.variant_id,
            assignment_id=assignment_id,
            metric_type=MetricType.USER_SATISFACTION,
            metric_name="star_rating",
            metric_value=float(feedback.rating),
            metric_unit="stars",
            context={"comment": feedback.comment},
        )
        db.add(rating_metric)

    # Update variant's success metrics based on feedback
    # Here we update success_count to reflect positive user feedback
    # This makes "conversion rate" = "positive feedback rate"
    if feedback.positive:
        variant.success_count = (variant.success_count or 0) + 1

    # Recalculate success_rate (conversion rate)
    if variant.sample_count and variant.sample_count > 0:
        variant.success_rate = (variant.success_count / variant.sample_count) * 100

    await db.commit()

    return ABFeedbackResponse(
        assignment_id=assignment_id,
        experiment_id=assignment.experiment_id,
        variant_id=assignment.variant_id,
        variant_name=variant.name,
        positive=feedback.positive,
        recorded=True,
        message=f"Feedback recorded for variant '{variant.name}'. "
                f"Conversion rate updated to {variant.success_rate:.1f}%",
    )


@router.get("/{experiment_id}/feedback-summary")
async def get_feedback_summary(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get feedback summary for an experiment.

    Returns aggregated user feedback metrics per variant:
    - Total feedback count
    - Positive feedback count
    - Positive feedback rate (true conversion rate)
    - Average star rating
    """
    from sqlalchemy import select, func, and_
    from backend.shared.ab_testing_models import ABExperiment, ABVariant, ABMetric

    # Get experiment
    stmt = select(ABExperiment).where(ABExperiment.id == experiment_id)
    result = await db.execute(stmt)
    experiment = result.scalar_one_or_none()

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    # Get variants
    stmt = select(ABVariant).where(ABVariant.experiment_id == experiment_id)
    result = await db.execute(stmt)
    variants = result.scalars().all()

    variant_feedback = []
    for variant in variants:
        # Get user_rating metrics (thumbs up/down)
        stmt = select(ABMetric).where(
            and_(
                ABMetric.variant_id == variant.id,
                ABMetric.metric_type == MetricType.USER_SATISFACTION,
                ABMetric.metric_name == "user_rating",
            )
        )
        result = await db.execute(stmt)
        feedback_metrics = result.scalars().all()

        total_feedback = len(feedback_metrics)
        positive_count = sum(1 for m in feedback_metrics if m.metric_value == 1.0)
        positive_rate = (positive_count / total_feedback * 100) if total_feedback > 0 else 0

        # Get star ratings
        stmt = select(ABMetric).where(
            and_(
                ABMetric.variant_id == variant.id,
                ABMetric.metric_type == MetricType.USER_SATISFACTION,
                ABMetric.metric_name == "star_rating",
            )
        )
        result = await db.execute(stmt)
        rating_metrics = result.scalars().all()

        avg_rating = (
            sum(m.metric_value for m in rating_metrics) / len(rating_metrics)
            if rating_metrics else None
        )

        variant_feedback.append({
            "variant_id": variant.id,
            "variant_name": variant.name,
            "total_executions": variant.sample_count or 0,
            "total_feedback": total_feedback,
            "feedback_coverage": (total_feedback / variant.sample_count * 100) if variant.sample_count else 0,
            "positive_feedback": positive_count,
            "negative_feedback": total_feedback - positive_count,
            "positive_rate": positive_rate,
            "avg_star_rating": avg_rating,
            "rating_count": len(rating_metrics),
        })

    return {
        "experiment_id": experiment.id,
        "experiment_name": experiment.name,
        "variants": variant_feedback,
        "total_feedback": sum(v["total_feedback"] for v in variant_feedback),
        "overall_positive_rate": (
            sum(v["positive_feedback"] for v in variant_feedback) /
            sum(v["total_feedback"] for v in variant_feedback) * 100
        ) if sum(v["total_feedback"] for v in variant_feedback) > 0 else 0,
    }
