"""
Health Monitor

Tracks model performance, latency, and availability for intelligent routing.
"""

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
import statistics

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import RouterHealthMetricModel, RouterModelModel
from backend.database.session import get_db


class HealthMetrics:
    """Health metrics for a model."""

    def __init__(
        self,
        model_id: str,
        latency_p50_ms: Optional[int] = None,
        latency_p95_ms: Optional[int] = None,
        latency_p99_ms: Optional[int] = None,
        success_rate: Optional[float] = None,
        error_count: int = 0,
        request_count: int = 0,
        is_healthy: bool = True,
    ):
        self.model_id = model_id
        self.latency_p50_ms = latency_p50_ms
        self.latency_p95_ms = latency_p95_ms
        self.latency_p99_ms = latency_p99_ms
        self.success_rate = success_rate
        self.error_count = error_count
        self.request_count = request_count
        self.is_healthy = is_healthy

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "latency_p99_ms": self.latency_p99_ms,
            "success_rate": self.success_rate,
            "error_count": self.error_count,
            "request_count": self.request_count,
            "is_healthy": self.is_healthy,
        }


class HealthMonitor:
    """
    Monitor for tracking model health and performance.

    Tracks latency, success rate, and availability for intelligent routing decisions.
    """

    # Health check thresholds
    MAX_ERROR_RATE = 0.10  # 10% error rate threshold
    MAX_P95_LATENCY_MS = 10000  # 10 second P95 latency threshold
    RECOVERY_SUCCESS_THRESHOLD = 3  # Consecutive successes needed for recovery
    WINDOW_SIZE_MINUTES = 5  # Rolling window for metrics

    def __init__(self, db: AsyncSession):
        """Initialize health monitor."""
        self.db = db

        # In-memory tracking for real-time metrics (rolling window)
        # model_id -> deque of (timestamp, latency_ms, success)
        self._request_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )

        # Recovery tracking: model_id -> consecutive_successes
        self._recovery_count: Dict[str, int] = defaultdict(int)

    async def track_request(
        self,
        model_id: str,
        latency_ms: int,
        success: bool,
        error: Optional[str] = None,
    ):
        """
        Track a request for health monitoring.

        This is called asynchronously after each LLM request to avoid blocking.

        Args:
            model_id: Model ID
            latency_ms: Request latency in milliseconds
            success: Whether request succeeded
            error: Optional error message
        """
        timestamp = datetime.utcnow()

        # Add to in-memory history
        self._request_history[model_id].append((timestamp, latency_ms, success))

        # Update recovery tracking
        if success:
            self._recovery_count[model_id] += 1
        else:
            self._recovery_count[model_id] = 0

        # Asynchronously update database (non-blocking)
        asyncio.create_task(self._update_metrics_async(model_id))

    async def _update_metrics_async(self, model_id: str):
        """Update metrics in database asynchronously."""
        try:
            # Calculate metrics from in-memory history
            metrics = self._calculate_metrics(model_id)

            # Check if model should be marked healthy/unhealthy
            is_healthy = self._check_health(metrics)

            # Save to database
            metric_record = RouterHealthMetricModel(
                id=str(uuid4()),
                model_id=model_id,
                timestamp=datetime.utcnow(),
                latency_p50_ms=metrics["latency_p50_ms"],
                latency_p95_ms=metrics["latency_p95_ms"],
                latency_p99_ms=metrics["latency_p99_ms"],
                success_rate=metrics["success_rate"],
                error_count=metrics["error_count"],
                request_count=metrics["request_count"],
                is_healthy=is_healthy,
            )

            self.db.add(metric_record)
            self.db.commit()

        except Exception as e:
            # Don't let health tracking errors break the main flow
            print(f"Error updating health metrics for model {model_id}: {e}")
            self.db.rollback()

    def _calculate_metrics(self, model_id: str) -> Dict:
        """
        Calculate metrics from in-memory history.

        Uses a rolling window of recent requests.
        """
        history = self._request_history[model_id]

        if not history:
            return {
                "latency_p50_ms": None,
                "latency_p95_ms": None,
                "latency_p99_ms": None,
                "success_rate": None,
                "error_count": 0,
                "request_count": 0,
            }

        # Filter to requests within the window
        cutoff = datetime.utcnow() - timedelta(minutes=self.WINDOW_SIZE_MINUTES)
        recent_requests = [
            (ts, latency, success)
            for ts, latency, success in history
            if ts >= cutoff
        ]

        if not recent_requests:
            return {
                "latency_p50_ms": None,
                "latency_p95_ms": None,
                "latency_p99_ms": None,
                "success_rate": None,
                "error_count": 0,
                "request_count": 0,
            }

        # Calculate latency percentiles
        latencies = [latency for _, latency, _ in recent_requests]
        latencies.sort()

        request_count = len(recent_requests)
        success_count = sum(1 for _, _, success in recent_requests if success)
        error_count = request_count - success_count

        return {
            "latency_p50_ms": self._percentile(latencies, 50),
            "latency_p95_ms": self._percentile(latencies, 95),
            "latency_p99_ms": self._percentile(latencies, 99),
            "success_rate": success_count / request_count if request_count > 0 else None,
            "error_count": error_count,
            "request_count": request_count,
        }

    def _percentile(self, values: List[int], p: int) -> int:
        """Calculate percentile from sorted values."""
        if not values:
            return 0

        if len(values) == 1:
            return values[0]

        index = (len(values) - 1) * p / 100
        lower = int(index)
        upper = lower + 1

        if upper >= len(values):
            return values[-1]

        weight = index - lower
        return int(values[lower] * (1 - weight) + values[upper] * weight)

    def _check_health(self, metrics: Dict) -> bool:
        """
        Determine if model is healthy based on metrics.

        A model is considered unhealthy if:
        - Error rate > 10%
        - P95 latency > 10 seconds

        A model can recover after 3 consecutive successful requests.
        """
        if metrics["request_count"] == 0:
            return True  # No data, assume healthy

        # Check error rate
        if metrics["success_rate"] is not None:
            error_rate = 1 - metrics["success_rate"]
            if error_rate > self.MAX_ERROR_RATE:
                return False

        # Check latency
        if metrics["latency_p95_ms"] is not None:
            if metrics["latency_p95_ms"] > self.MAX_P95_LATENCY_MS:
                return False

        return True

    def get_health(self, model_id: str) -> HealthMetrics:
        """
        Get current health metrics for a model.

        Args:
            model_id: Model ID

        Returns:
            HealthMetrics object
        """
        metrics = self._calculate_metrics(model_id)
        is_healthy = self._check_health(metrics)

        return HealthMetrics(
            model_id=model_id,
            latency_p50_ms=metrics["latency_p50_ms"],
            latency_p95_ms=metrics["latency_p95_ms"],
            latency_p99_ms=metrics["latency_p99_ms"],
            success_rate=metrics["success_rate"],
            error_count=metrics["error_count"],
            request_count=metrics["request_count"],
            is_healthy=is_healthy,
        )

    def get_all_health(self, model_ids: List[str]) -> Dict[str, HealthMetrics]:
        """
        Get health metrics for multiple models.

        Args:
            model_ids: List of model IDs

        Returns:
            Dictionary mapping model_id to HealthMetrics
        """
        return {
            model_id: self.get_health(model_id)
            for model_id in model_ids
        }

    def get_historical_metrics(
        self,
        model_id: str,
        hours: int = 24
    ) -> List[HealthMetrics]:
        """
        Get historical health metrics from database.

        Args:
            model_id: Model ID
            hours: Number of hours to look back

        Returns:
            List of HealthMetrics ordered by timestamp
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        records = self.db.query(RouterHealthMetricModel).filter(
            RouterHealthMetricModel.model_id == model_id,
            RouterHealthMetricModel.timestamp >= cutoff,
        ).order_by(RouterHealthMetricModel.timestamp.asc()).all()

        return [
            HealthMetrics(
                model_id=record.model_id,
                latency_p50_ms=record.latency_p50_ms,
                latency_p95_ms=record.latency_p95_ms,
                latency_p99_ms=record.latency_p99_ms,
                success_rate=record.success_rate,
                error_count=record.error_count,
                request_count=record.request_count,
                is_healthy=record.is_healthy,
            )
            for record in records
        ]

    def is_healthy(self, model_id: str) -> bool:
        """Check if a model is currently healthy."""
        metrics = self.get_health(model_id)
        return metrics.is_healthy

    def get_dashboard_data(self, organization_id: str) -> Dict:
        """
        Get health dashboard data for all models in an organization.

        Args:
            organization_id: Organization ID

        Returns:
            Dashboard data with model health summary
        """
        # Get all models for organization
        models = self.db.query(RouterModelModel).filter(
            RouterModelModel.organization_id == organization_id,
            RouterModelModel.is_enabled == True,
        ).all()

        model_health = []
        for model in models:
            health = self.get_health(model.id)
            model_health.append({
                "model_id": model.id,
                "model_name": model.model_name,
                "provider": model.provider,
                "display_name": model.display_name,
                "health": health.to_dict(),
            })

        # Calculate summary stats
        healthy_count = sum(1 for m in model_health if m["health"]["is_healthy"])
        total_requests = sum(m["health"]["request_count"] for m in model_health)

        return {
            "total_models": len(model_health),
            "healthy_models": healthy_count,
            "unhealthy_models": len(model_health) - healthy_count,
            "total_requests": total_requests,
            "models": model_health,
        }


# Singleton instance
_monitor: Optional[HealthMonitor] = None


def get_health_monitor(db: Optional[Session] = None) -> HealthMonitor:
    """Get or create the health monitor singleton."""
    if db is None:
        db = next(get_db())

    global _monitor
    if _monitor is None:
        _monitor = HealthMonitor(db)
    return _monitor
