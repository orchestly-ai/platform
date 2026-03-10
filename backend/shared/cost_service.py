"""
Cost Forecasting and Budget Management Service

AI-powered cost prediction to prevent surprise bills.
Addresses #2 production pain point: cost runaway.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, date
from uuid import UUID
import numpy as np
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from backend.shared.cost_models import (
    CostEvent, CostEventModel, CostAggregateModel, BudgetModel,
    CostForecastModel, CostSummary, CostForecast, BudgetStatus,
    CostAnomaly, CostCategory, BudgetPeriod, AlertSeverity, CostPeriod,
    ForecastAnomaly
)
from backend.shared.audit_logger import get_audit_logger
from backend.shared.audit_models import AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class CostService:
    """
    Cost tracking, forecasting, and budget management service.

    Features:
    - Real-time cost tracking
    - AI-powered forecasting (7-day, 30-day)
    - Anomaly detection
    - Budget alerts
    - Cost attribution
    - Automatic rollup aggregation
    """

    def __init__(self):
        self._forecast_cache: Dict[str, Tuple[CostForecast, datetime]] = {}
        self._cache_ttl = timedelta(hours=1)

    async def track_cost(
        self,
        event: CostEvent,
        db: AsyncSession
    ) -> UUID:
        """
        Track a cost event.

        Args:
            event: Cost event to track
            db: Database session

        Returns:
            Event ID
        """
        # Create cost event
        cost_event = CostEventModel(
            event_id=event.event_id,
            timestamp=event.timestamp,
            organization_id=event.organization_id,
            user_id=event.user_id,
            agent_id=event.agent_id,
            task_id=event.task_id,
            workflow_id=event.workflow_id,
            category=event.category.value,
            amount=event.amount,
            currency=event.currency,
            provider=event.provider,
            model=event.model,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            total_tokens=event.total_tokens,
            extra_metadata=event.metadata  # Note: column is extra_metadata, not metadata
        )

        db.add(cost_event)
        await db.flush()

        # Check budget alerts
        await self._check_budget_alerts(event.organization_id, event.amount, db)

        logger.debug(f"Cost tracked: ${event.amount} for {event.category.value}")
        return event.event_id

    async def get_cost_summary(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime,
        agent_id: Optional[UUID] = None,
        db: AsyncSession = None
    ) -> CostSummary:
        """
        Get cost summary for a time period.
        """
        # Build query
        filters = [
            CostEventModel.organization_id == organization_id,
            CostEventModel.timestamp >= start_time,
            CostEventModel.timestamp <= end_time
        ]

        if agent_id:
            filters.append(CostEventModel.agent_id == agent_id)

        # Total cost and count
        stmt = select(
            func.sum(CostEventModel.amount),
            func.count(CostEventModel.event_id)
        ).where(and_(*filters))

        result = await db.execute(stmt)
        total_cost, event_count = result.one()

        total_cost = total_cost or 0.0
        event_count = event_count or 0
        avg_cost = (total_cost / event_count) if event_count > 0 else 0.0

        # Category breakdown
        category_stmt = select(
            CostEventModel.category,
            func.sum(CostEventModel.amount)
        ).where(and_(*filters)).group_by(CostEventModel.category)

        result = await db.execute(category_stmt)
        category_breakdown = {cat: float(amt) for cat, amt in result.all()}

        # Provider breakdown
        provider_stmt = select(
            CostEventModel.provider,
            func.sum(CostEventModel.amount)
        ).where(
            and_(*filters),
            CostEventModel.provider.isnot(None)
        ).group_by(CostEventModel.provider)

        result = await db.execute(provider_stmt)
        provider_breakdown = {prov: float(amt) for prov, amt in result.all()}

        # Top agents
        top_agents_stmt = select(
            CostEventModel.agent_id,
            func.sum(CostEventModel.amount)
        ).where(
            and_(*filters),
            CostEventModel.agent_id.isnot(None)
        ).group_by(CostEventModel.agent_id).order_by(desc(func.sum(CostEventModel.amount))).limit(5)

        result = await db.execute(top_agents_stmt)
        top_agents = [(str(agent_id), float(amt)) for agent_id, amt in result.all()]

        # Top workflows
        top_workflows_stmt = select(
            CostEventModel.workflow_id,
            func.sum(CostEventModel.amount)
        ).where(
            and_(*filters),
            CostEventModel.workflow_id.isnot(None)
        ).group_by(CostEventModel.workflow_id).order_by(desc(func.sum(CostEventModel.amount))).limit(5)

        result = await db.execute(top_workflows_stmt)
        top_workflows = [(str(wf_id), float(amt)) for wf_id, amt in result.all()]

        # Model breakdown
        model_stmt = select(
            CostEventModel.model,
            func.sum(CostEventModel.amount)
        ).where(
            and_(*filters),
            CostEventModel.model.isnot(None)
        ).group_by(CostEventModel.model)

        result = await db.execute(model_stmt)
        model_breakdown = {model: float(amt) for model, amt in result.all()}

        # Top users
        top_users_stmt = select(
            CostEventModel.user_id,
            func.sum(CostEventModel.amount)
        ).where(
            and_(*filters),
            CostEventModel.user_id.isnot(None)
        ).group_by(CostEventModel.user_id).order_by(desc(func.sum(CostEventModel.amount))).limit(5)

        result = await db.execute(top_users_stmt)
        top_users = [(str(user_id), float(amt)) for user_id, amt in result.all()]

        # Previous period comparison
        period_duration = end_time - start_time
        prev_start = start_time - period_duration
        prev_end = start_time

        prev_filters = [
            CostEventModel.organization_id == organization_id,
            CostEventModel.timestamp >= prev_start,
            CostEventModel.timestamp < prev_end
        ]

        prev_stmt = select(func.sum(CostEventModel.amount)).where(and_(*prev_filters))
        result = await db.execute(prev_stmt)
        prev_total = result.scalar_one() or 0.0

        vs_previous = None
        if prev_total > 0:
            vs_previous = ((total_cost - prev_total) / prev_total) * 100

        return CostSummary(
            period_start=start_time,
            period_end=end_time,
            total_cost=total_cost,
            event_count=event_count,
            avg_cost_per_event=avg_cost,
            category_breakdown=category_breakdown,
            provider_breakdown=provider_breakdown,
            model_breakdown=model_breakdown,
            top_agents=top_agents,
            top_workflows=top_workflows,
            top_users=top_users,
            vs_previous_period_percent=vs_previous
        )

    async def forecast_cost(
        self,
        organization_id: str,
        forecast_days: int = 7,
        db: AsyncSession = None
    ) -> CostForecast:
        """
        Generate AI-powered cost forecast.

        Uses simple linear regression for now. Can be upgraded to Prophet/ARIMA.
        """
        # Check cache
        cache_key = f"{organization_id}_{forecast_days}"
        if cache_key in self._forecast_cache:
            forecast, cached_at = self._forecast_cache[cache_key]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                return forecast

        # Get historical data (last 30 days)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=30)

        # Fetch daily costs
        stmt = select(
            func.date(CostEventModel.timestamp).label('date'),
            func.sum(CostEventModel.amount).label('total')
        ).where(
            and_(
                CostEventModel.organization_id == organization_id,
                CostEventModel.timestamp >= start_time,
                CostEventModel.timestamp <= end_time
            )
        ).group_by(func.date(CostEventModel.timestamp)).order_by(func.date(CostEventModel.timestamp))

        result = await db.execute(stmt)
        daily_costs = [(row.date, float(row.total)) for row in result.all()]

        if len(daily_costs) < 7:
            # Not enough data for forecast
            return CostForecast(
                forecast_period_start=date.today(),
                forecast_period_end=date.today() + timedelta(days=forecast_days),
                predicted_cost=0.0,
                confidence_lower=0.0,
                confidence_upper=0.0,
                trend="insufficient_data"
            )

        # Simple linear regression
        X = np.arange(len(daily_costs))
        y = np.array([cost for _, cost in daily_costs])

        # Fit line
        coeffs = np.polyfit(X, y, 1)
        slope, intercept = coeffs

        # Predict future
        future_days = np.arange(len(daily_costs), len(daily_costs) + forecast_days)
        predictions = slope * future_days + intercept
        predicted_cost = float(np.sum(predictions))

        # Calculate confidence interval (using std dev of residuals)
        fitted = slope * X + intercept
        residuals = y - fitted
        std_dev = np.std(residuals)

        # Calculate R² (coefficient of determination)
        ss_res = np.sum(residuals ** 2)  # Sum of squared residuals
        ss_tot = np.sum((y - np.mean(y)) ** 2)  # Total sum of squares
        r_squared = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

        # 95% confidence interval (±1.96 * std_dev * sqrt(n))
        margin = 1.96 * std_dev * np.sqrt(forecast_days)
        confidence_lower = max(0, predicted_cost - margin)
        confidence_upper = predicted_cost + margin

        # Determine trend
        recent_avg = np.mean(y[-7:]) if len(y) >= 7 else np.mean(y)
        if slope > recent_avg * 0.1:
            trend = "increasing"
        elif slope < -recent_avg * 0.1:
            trend = "decreasing"
        else:
            trend = "stable"

        # Detect anomalies (costs > 2 std devs from fitted line)
        anomalies = []
        for i, (date_val, actual_cost) in enumerate(daily_costs):
            expected = float(fitted[i])
            deviation = actual_cost - expected
            if abs(deviation) > 2 * std_dev:
                # Convert date to datetime
                anomaly_dt = datetime.combine(date_val, datetime.min.time())
                # Calculate deviation percentage
                deviation_percent = (deviation / expected * 100) if expected > 0 else 0.0
                # Determine severity based on deviation
                if abs(deviation) > 3 * std_dev:
                    severity = "high"
                elif abs(deviation) > 2.5 * std_dev:
                    severity = "medium"
                else:
                    severity = "low"
                anomalies.append(ForecastAnomaly(
                    timestamp=anomaly_dt,
                    expected_cost=expected,
                    actual_cost=actual_cost,
                    deviation_percent=deviation_percent,
                    severity=severity
                ))

        forecast = CostForecast(
            forecast_period_start=date.today(),
            forecast_period_end=date.today() + timedelta(days=forecast_days),
            predicted_cost=predicted_cost,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            trend=trend,
            anomalies_detected=anomalies,
            model_type="linear_regression",
            accuracy_score=r_squared
        )

        # Cache
        self._forecast_cache[cache_key] = (forecast, datetime.utcnow())

        return forecast

    async def detect_anomalies(
        self,
        organization_id: str,
        lookback_days: int = 7,
        db: AsyncSession = None
    ) -> List[CostAnomaly]:
        """
        Detect cost anomalies using statistical methods.
        """
        # Get historical hourly costs
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=lookback_days)

        hour_col = func.date_trunc('hour', CostEventModel.timestamp)
        stmt = select(
            hour_col.label('hour'),
            func.sum(CostEventModel.amount).label('total')
        ).where(
            and_(
                CostEventModel.organization_id == organization_id,
                CostEventModel.timestamp >= start_time,
                CostEventModel.timestamp <= end_time
            )
        ).group_by(hour_col).order_by(hour_col)

        result = await db.execute(stmt)
        hourly_costs = [(row.hour, float(row.total)) for row in result.all()]

        if len(hourly_costs) < 24:
            return []

        # Calculate statistics
        costs = np.array([cost for _, cost in hourly_costs])
        mean = np.mean(costs)
        std_dev = np.std(costs)

        # Detect anomalies (> 2 std devs from mean)
        anomalies = []
        for timestamp, actual_cost in hourly_costs:
            deviation = abs(actual_cost - mean)
            if deviation > 2 * std_dev:
                deviation_percent = (deviation / mean) * 100

                # Determine severity
                if deviation > 3 * std_dev:
                    severity = "high"
                elif deviation > 2.5 * std_dev:
                    severity = "medium"
                else:
                    severity = "low"

                anomaly = CostAnomaly(
                    timestamp=timestamp,
                    expected_cost=mean,
                    actual_cost=actual_cost,
                    deviation_percent=deviation_percent,
                    severity=severity,
                    description=f"Cost spike detected: ${actual_cost:.2f} (expected ${mean:.2f})",
                    potential_causes=[
                        "Sudden increase in agent activity",
                        "Large batch job",
                        "Model API rate limit exhaustion",
                        "Workflow loop or retry storm"
                    ]
                )
                anomalies.append(anomaly)

        return anomalies

    async def create_budget(
        self,
        budget: 'Budget',
        db: AsyncSession
    ) -> UUID:
        """
        Create a new budget.

        Args:
            budget: Budget definition
            db: Database session

        Returns:
            Created budget ID
        """
        # Create budget model
        # Convert period enum to string if needed
        period_value = budget.period.value if hasattr(budget.period, 'value') else budget.period
        budget_model = BudgetModel(
            budget_id=budget.budget_id,
            organization_id=budget.organization_id,
            name=budget.name,
            period=period_value,
            amount=budget.amount,
            currency=budget.currency,
            scope_type=budget.scope_type,
            scope_id=budget.scope_id,
            alert_threshold_info=budget.alert_threshold_info,
            alert_threshold_warning=budget.alert_threshold_warning,
            alert_threshold_critical=budget.alert_threshold_critical,
            auto_disable_on_exceeded=budget.auto_disable_on_exceeded,
            is_active=budget.is_active
        )

        db.add(budget_model)
        await db.commit()
        await db.refresh(budget_model)

        return budget_model.budget_id

    async def check_budget_status(
        self,
        budget_id: UUID,
        db: AsyncSession
    ) -> BudgetStatus:
        """
        Check current budget status and generate alerts.
        """
        # Get budget
        stmt = select(BudgetModel).where(BudgetModel.budget_id == budget_id)
        result = await db.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            raise ValueError(f"Budget not found: {budget_id}")

        # Calculate period start/end
        now = datetime.utcnow()
        period_start, period_end = self._get_period_bounds(now, budget.period)

        # Get current spending
        filters = [
            CostEventModel.organization_id == budget.organization_id,
            CostEventModel.timestamp >= period_start,
            CostEventModel.timestamp <= period_end
        ]

        if budget.scope_type == "agent":
            filters.append(CostEventModel.agent_id == UUID(budget.scope_id))
        elif budget.scope_type == "category":
            filters.append(CostEventModel.category == budget.scope_id)

        stmt = select(func.sum(CostEventModel.amount)).where(and_(*filters))
        result = await db.execute(stmt)
        spent = result.scalar_one() or 0.0

        # Calculate metrics
        remaining = budget.amount - spent
        percent_used = (spent / budget.amount * 100) if budget.amount > 0 else 0

        # Determine alert level
        alert_level = None
        if percent_used >= 100:
            alert_level = AlertSeverity.EXCEEDED
        elif percent_used >= budget.alert_threshold_critical:
            alert_level = AlertSeverity.CRITICAL
        elif percent_used >= budget.alert_threshold_warning:
            alert_level = AlertSeverity.WARNING
        elif percent_used >= budget.alert_threshold_info:
            alert_level = AlertSeverity.INFO

        # Days until period end
        days_until_end = (period_end - now).days

        # Project spending
        days_elapsed = (now - period_start).days + 1
        days_in_period = (period_end - period_start).days + 1
        daily_rate = spent / days_elapsed if days_elapsed > 0 else 0
        projected_spend = daily_rate * days_in_period
        projected_overage = max(0, projected_spend - budget.amount)

        # Recommendations
        recommendations = []
        if alert_level == AlertSeverity.EXCEEDED:
            recommendations.append("Budget exceeded - consider disabling expensive agents")
            recommendations.append("Review cost anomalies and optimize workflows")
        elif alert_level == AlertSeverity.CRITICAL:
            recommendations.append(f"Only ${remaining:.2f} remaining - monitor closely")
            recommendations.append("Consider temporary cost limits on agents")
        elif projected_overage > 0:
            recommendations.append(f"Projected to exceed budget by ${projected_overage:.2f}")
            recommendations.append("Reduce agent concurrency or optimize LLM calls")

        return BudgetStatus(
            budget_id=budget_id,
            budget_name=budget.name,
            period=BudgetPeriod(budget.period),
            limit=budget.amount,
            spent=spent,
            remaining=remaining,
            percent_used=percent_used,
            alert_level=alert_level,
            days_until_period_end=days_until_end,
            projected_spend=projected_spend,
            projected_overage=projected_overage,
            recommended_actions=recommendations
        )

    async def _check_budget_alerts(
        self,
        organization_id: str,
        cost_amount: float,
        db: AsyncSession
    ):
        """Check if any budgets are exceeded and send alerts"""
        # Get active budgets for org
        stmt = select(BudgetModel).where(
            and_(
                BudgetModel.organization_id == organization_id,
                BudgetModel.is_active == True
            )
        )
        result = await db.execute(stmt)
        budgets = result.scalars().all()

        for budget in budgets:
            status = await self.check_budget_status(budget.budget_id, db)

            # Log alert if threshold crossed
            if status.alert_level:
                audit_logger = get_audit_logger()

                severity_map = {
                    AlertSeverity.INFO: AuditSeverity.INFO,
                    AlertSeverity.WARNING: AuditSeverity.WARNING,
                    AlertSeverity.CRITICAL: AuditSeverity.CRITICAL,
                    AlertSeverity.EXCEEDED: AuditSeverity.CRITICAL
                }

                await audit_logger.log_cost_event(
                    event_type=AuditEventType.COST_LIMIT_WARNING if status.alert_level != AlertSeverity.EXCEEDED else AuditEventType.COST_LIMIT_EXCEEDED,
                    description=f"Budget '{budget.name}': {status.percent_used:.1f}% used (${status.spent:.2f}/${status.limit:.2f})",
                    cost_impact=cost_amount,
                    resource_type="budget",
                    resource_id=str(budget.budget_id),
                    severity=severity_map[status.alert_level],
                    db=db
                )

    def _get_period_bounds(self, now: datetime, period: str) -> Tuple[datetime, datetime]:
        """Calculate period start and end times"""
        if period == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == "weekly":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif period == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Next month
            if now.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        else:
            # Default to daily
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)

        return start, end


# Global cost service instance
_cost_service: Optional[CostService] = None


def get_cost_service() -> CostService:
    """Get the global cost service instance"""
    global _cost_service
    if _cost_service is None:
        _cost_service = CostService()
    return _cost_service
