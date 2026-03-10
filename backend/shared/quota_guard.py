#!/usr/bin/env python3
"""
Quota Guard - Advanced Rate Limiting and Usage Prediction

Implements ROADMAP.md Section: Customer-Managed Key Gateway (BYOK)

Features:
- Sliding window rate limiting
- Token burst detection
- Usage prediction and preemptive throttling
- Budget alerts and enforcement
- Multi-tier quota management

Key Design Decisions:
- Sliding window for accurate rate limiting
- Exponential backoff recommendations
- Budget soft/hard limits with alerts
- Cross-key organization-level limits
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4
import logging
import math

logger = logging.getLogger(__name__)


class ThrottleAction(str, Enum):
    """Actions to take when limits are approached."""
    ALLOW = "allow"
    THROTTLE = "throttle"
    QUEUE = "queue"
    REJECT = "reject"


class AlertSeverity(str, Enum):
    """Severity of quota alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class QuotaLimit:
    """Configuration for a quota limit."""
    name: str
    limit_value: int
    window_seconds: int  # Time window for the limit
    soft_limit_percent: float = 0.8  # Alert at 80%
    hard_limit_percent: float = 1.0  # Block at 100%
    burst_multiplier: float = 1.5  # Allow temporary burst

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "limit_value": self.limit_value,
            "window_seconds": self.window_seconds,
            "soft_limit_percent": self.soft_limit_percent,
            "hard_limit_percent": self.hard_limit_percent,
            "burst_multiplier": self.burst_multiplier,
        }


@dataclass
class BudgetConfig:
    """Budget configuration for an organization."""
    org_id: UUID
    daily_budget: Optional[float] = None
    monthly_budget: Optional[float] = None
    alert_thresholds: List[float] = field(default_factory=lambda: [0.5, 0.8, 0.9, 1.0])
    hard_stop_at: float = 1.0  # Stop at 100% of budget
    currency: str = "USD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "org_id": str(self.org_id),
            "daily_budget": self.daily_budget,
            "monthly_budget": self.monthly_budget,
            "alert_thresholds": self.alert_thresholds,
            "hard_stop_at": self.hard_stop_at,
            "currency": self.currency,
        }


@dataclass
class UsageWindow:
    """Sliding window for usage tracking."""
    window_id: str
    entity_id: UUID  # Key or org ID
    limit_name: str
    window_start: datetime
    window_end: datetime
    current_value: int = 0
    requests: List[Tuple[datetime, int]] = field(default_factory=list)  # (timestamp, value)

    def add_request(self, value: int):
        """Add a request to the window."""
        now = datetime.utcnow()
        self.requests.append((now, value))
        self.current_value += value
        self._cleanup_old_requests()

    def _cleanup_old_requests(self):
        """Remove requests outside the window."""
        cutoff = datetime.utcnow() - (self.window_end - self.window_start)
        new_requests = [(t, v) for t, v in self.requests if t >= cutoff]
        self.requests = new_requests
        self.current_value = sum(v for _, v in self.requests)

    def get_current_usage(self) -> int:
        """Get current usage within the window."""
        self._cleanup_old_requests()
        return self.current_value


@dataclass
class QuotaAlert:
    """An alert generated when quota thresholds are reached."""
    alert_id: UUID
    entity_id: UUID
    entity_type: str  # "key" or "org"
    alert_type: str  # "rate_limit", "budget", "burst"
    severity: AlertSeverity
    message: str
    threshold_percent: float
    current_value: float
    limit_value: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": str(self.alert_id),
            "entity_id": str(self.entity_id),
            "entity_type": self.entity_type,
            "alert_type": self.alert_type,
            "severity": self.severity.value,
            "message": self.message,
            "threshold_percent": self.threshold_percent,
            "current_value": self.current_value,
            "limit_value": self.limit_value,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
        }


@dataclass
class ThrottleDecision:
    """Decision from the quota guard."""
    action: ThrottleAction
    allowed: bool
    reason: Optional[str] = None
    delay_ms: int = 0  # Recommended delay before retry
    backoff_factor: float = 1.0
    alerts: List[QuotaAlert] = field(default_factory=list)
    usage_percent: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "allowed": self.allowed,
            "reason": self.reason,
            "delay_ms": self.delay_ms,
            "backoff_factor": self.backoff_factor,
            "usage_percent": self.usage_percent,
            "recommendations": self.recommendations,
            "alerts": [a.to_dict() for a in self.alerts],
        }


@dataclass
class UsagePrediction:
    """Predicted usage for budget planning."""
    org_id: UUID
    prediction_time: datetime
    predicted_hourly_cost: float
    predicted_daily_cost: float
    predicted_monthly_cost: float
    confidence: float  # 0-1
    trend: str  # "increasing", "stable", "decreasing"
    will_exceed_daily_budget: bool = False
    will_exceed_monthly_budget: bool = False
    hours_until_daily_limit: Optional[float] = None
    days_until_monthly_limit: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "org_id": str(self.org_id),
            "prediction_time": self.prediction_time.isoformat(),
            "predicted_hourly_cost": self.predicted_hourly_cost,
            "predicted_daily_cost": self.predicted_daily_cost,
            "predicted_monthly_cost": self.predicted_monthly_cost,
            "confidence": self.confidence,
            "trend": self.trend,
            "will_exceed_daily_budget": self.will_exceed_daily_budget,
            "will_exceed_monthly_budget": self.will_exceed_monthly_budget,
            "hours_until_daily_limit": self.hours_until_daily_limit,
            "days_until_monthly_limit": self.days_until_monthly_limit,
        }


class QuotaGuard:
    """
    Advanced quota management with sliding windows and predictions.
    """

    # Default limits
    DEFAULT_RPM_LIMIT = QuotaLimit("rpm", 1000, 60)
    DEFAULT_TPM_LIMIT = QuotaLimit("tpm", 100000, 60)
    DEFAULT_RPH_LIMIT = QuotaLimit("rph", 10000, 3600)
    DEFAULT_RPD_LIMIT = QuotaLimit("rpd", 100000, 86400)

    def __init__(
        self,
        alert_callback: Optional[Callable] = None,
    ):
        """Initialize the quota guard."""
        self.alert_callback = alert_callback

        # Storage
        self._limits: Dict[UUID, List[QuotaLimit]] = {}  # entity_id -> limits
        self._windows: Dict[str, UsageWindow] = {}  # window_id -> window
        self._budgets: Dict[UUID, BudgetConfig] = {}  # org_id -> budget
        self._spend_tracking: Dict[str, float] = {}  # "{org_id}:{period}" -> spend
        self._alerts: List[QuotaAlert] = []

    def set_limits(self, entity_id: UUID, limits: List[QuotaLimit]):
        """Set quota limits for an entity (key or org)."""
        self._limits[entity_id] = limits

    def set_budget(self, budget: BudgetConfig):
        """Set budget configuration for an organization."""
        self._budgets[budget.org_id] = budget

    def get_budget(self, org_id: UUID) -> Optional[BudgetConfig]:
        """Get budget configuration for an organization."""
        return self._budgets.get(org_id)

    async def check_quota(
        self,
        entity_id: UUID,
        request_value: int = 1,
        request_tokens: int = 0,
        estimated_cost: float = 0.0,
        org_id: Optional[UUID] = None,
    ) -> ThrottleDecision:
        """
        Check if a request should be allowed based on quotas.

        Args:
            entity_id: Key or entity ID
            request_value: Number of requests (usually 1)
            request_tokens: Estimated tokens for this request
            estimated_cost: Estimated cost for this request
            org_id: Organization ID for budget checks

        Returns:
            ThrottleDecision with action and recommendations
        """
        limits = self._limits.get(entity_id, [self.DEFAULT_RPM_LIMIT, self.DEFAULT_TPM_LIMIT])
        alerts: List[QuotaAlert] = []
        recommendations: List[str] = []
        max_usage_percent = 0.0

        # Check each limit
        for limit in limits:
            window = self._get_or_create_window(entity_id, limit)
            current_usage = window.get_current_usage()

            # Determine value to check based on limit type
            check_value = request_value
            if "tp" in limit.name.lower():  # Token limits
                check_value = request_tokens

            # Calculate usage percentages
            projected_usage = current_usage + check_value
            usage_percent = projected_usage / limit.limit_value if limit.limit_value > 0 else 0
            max_usage_percent = max(max_usage_percent, usage_percent)

            # Check soft limit (warning)
            if usage_percent >= limit.soft_limit_percent and usage_percent < limit.hard_limit_percent:
                alert = QuotaAlert(
                    alert_id=uuid4(),
                    entity_id=entity_id,
                    entity_type="key",
                    alert_type="rate_limit",
                    severity=AlertSeverity.WARNING,
                    message=f"{limit.name} approaching limit ({usage_percent*100:.1f}%)",
                    threshold_percent=limit.soft_limit_percent,
                    current_value=projected_usage,
                    limit_value=limit.limit_value,
                )
                alerts.append(alert)
                recommendations.append(f"Consider throttling to stay under {limit.name} limit")

            # Check hard limit (reject)
            if usage_percent >= limit.hard_limit_percent:
                # Check burst allowance
                burst_limit = limit.limit_value * limit.burst_multiplier
                if projected_usage <= burst_limit:
                    # Allow burst but recommend throttling
                    recommendations.append(f"Using burst capacity for {limit.name}")
                else:
                    # Hard reject
                    delay_ms = self._calculate_backoff(limit, current_usage)
                    return ThrottleDecision(
                        action=ThrottleAction.REJECT,
                        allowed=False,
                        reason=f"{limit.name} limit exceeded",
                        delay_ms=delay_ms,
                        backoff_factor=2.0,
                        usage_percent=usage_percent,
                        alerts=alerts,
                        recommendations=["Wait for rate limit window to reset"],
                    )

        # Check budget if org_id provided
        if org_id and estimated_cost > 0:
            budget_decision = await self._check_budget(org_id, estimated_cost)
            if budget_decision:
                alerts.extend(budget_decision.alerts)
                if not budget_decision.allowed:
                    return budget_decision

        # Determine action based on usage
        if max_usage_percent >= 0.9:
            action = ThrottleAction.THROTTLE
            delay_ms = int((max_usage_percent - 0.8) * 1000)  # Gradual delay
        elif max_usage_percent >= 0.8:
            action = ThrottleAction.THROTTLE
            delay_ms = 100
        else:
            action = ThrottleAction.ALLOW
            delay_ms = 0

        # Send alerts
        for alert in alerts:
            self._alerts.append(alert)
            if self.alert_callback:
                await self.alert_callback(alert)

        return ThrottleDecision(
            action=action,
            allowed=True,
            delay_ms=delay_ms,
            usage_percent=max_usage_percent,
            alerts=alerts,
            recommendations=recommendations,
        )

    async def record_usage(
        self,
        entity_id: UUID,
        request_value: int = 1,
        request_tokens: int = 0,
        cost: float = 0.0,
        org_id: Optional[UUID] = None,
    ):
        """Record actual usage after a request completes."""
        limits = self._limits.get(entity_id, [self.DEFAULT_RPM_LIMIT, self.DEFAULT_TPM_LIMIT])

        for limit in limits:
            window = self._get_or_create_window(entity_id, limit)

            if "tp" in limit.name.lower():
                window.add_request(request_tokens)
            else:
                window.add_request(request_value)

        # Record spend
        if org_id and cost > 0:
            now = datetime.utcnow()
            daily_key = f"{org_id}:{now.strftime('%Y%m%d')}"
            monthly_key = f"{org_id}:{now.strftime('%Y%m')}"

            self._spend_tracking[daily_key] = self._spend_tracking.get(daily_key, 0) + cost
            self._spend_tracking[monthly_key] = self._spend_tracking.get(monthly_key, 0) + cost

    async def _check_budget(
        self,
        org_id: UUID,
        estimated_cost: float,
    ) -> Optional[ThrottleDecision]:
        """Check if request fits within budget."""
        budget = self._budgets.get(org_id)
        if not budget:
            return None

        now = datetime.utcnow()
        alerts = []

        # Check daily budget
        if budget.daily_budget:
            daily_key = f"{org_id}:{now.strftime('%Y%m%d')}"
            current_daily = self._spend_tracking.get(daily_key, 0)
            projected_daily = current_daily + estimated_cost
            daily_percent = projected_daily / budget.daily_budget

            for threshold in budget.alert_thresholds:
                if daily_percent >= threshold:
                    severity = AlertSeverity.CRITICAL if threshold >= 0.9 else AlertSeverity.WARNING
                    alerts.append(QuotaAlert(
                        alert_id=uuid4(),
                        entity_id=org_id,
                        entity_type="org",
                        alert_type="budget",
                        severity=severity,
                        message=f"Daily budget at {daily_percent*100:.1f}%",
                        threshold_percent=threshold,
                        current_value=projected_daily,
                        limit_value=budget.daily_budget,
                    ))
                    break

            if daily_percent >= budget.hard_stop_at:
                return ThrottleDecision(
                    action=ThrottleAction.REJECT,
                    allowed=False,
                    reason="Daily budget exceeded",
                    alerts=alerts,
                    usage_percent=daily_percent,
                )

        # Check monthly budget
        if budget.monthly_budget:
            monthly_key = f"{org_id}:{now.strftime('%Y%m')}"
            current_monthly = self._spend_tracking.get(monthly_key, 0)
            projected_monthly = current_monthly + estimated_cost
            monthly_percent = projected_monthly / budget.monthly_budget

            for threshold in budget.alert_thresholds:
                if monthly_percent >= threshold:
                    severity = AlertSeverity.CRITICAL if threshold >= 0.9 else AlertSeverity.WARNING
                    alerts.append(QuotaAlert(
                        alert_id=uuid4(),
                        entity_id=org_id,
                        entity_type="org",
                        alert_type="budget",
                        severity=severity,
                        message=f"Monthly budget at {monthly_percent*100:.1f}%",
                        threshold_percent=threshold,
                        current_value=projected_monthly,
                        limit_value=budget.monthly_budget,
                    ))
                    break

            if monthly_percent >= budget.hard_stop_at:
                return ThrottleDecision(
                    action=ThrottleAction.REJECT,
                    allowed=False,
                    reason="Monthly budget exceeded",
                    alerts=alerts,
                    usage_percent=monthly_percent,
                )

        if alerts:
            return ThrottleDecision(
                action=ThrottleAction.ALLOW,
                allowed=True,
                alerts=alerts,
                recommendations=["Consider increasing budget or reducing usage"],
            )

        return None

    async def predict_usage(
        self,
        org_id: UUID,
    ) -> UsagePrediction:
        """Predict future usage based on recent patterns."""
        now = datetime.utcnow()

        # Get recent hourly data (last 24 hours)
        hourly_costs = []
        for h in range(24):
            hour_time = now - timedelta(hours=h)
            hour_key = f"{org_id}:{hour_time.strftime('%Y%m%d%H')}"
            cost = self._spend_tracking.get(hour_key, 0)
            hourly_costs.append(cost)

        # Calculate averages
        if not any(hourly_costs):
            return UsagePrediction(
                org_id=org_id,
                prediction_time=now,
                predicted_hourly_cost=0,
                predicted_daily_cost=0,
                predicted_monthly_cost=0,
                confidence=0.0,
                trend="stable",
            )

        avg_hourly = sum(hourly_costs) / len([c for c in hourly_costs if c > 0]) if any(hourly_costs) else 0
        predicted_daily = avg_hourly * 24
        predicted_monthly = predicted_daily * 30

        # Determine trend
        recent = sum(hourly_costs[:6])  # Last 6 hours
        older = sum(hourly_costs[6:12])  # 6-12 hours ago

        if recent > older * 1.2:
            trend = "increasing"
        elif recent < older * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"

        # Check budget exceedance
        budget = self._budgets.get(org_id)
        will_exceed_daily = False
        will_exceed_monthly = False
        hours_until_daily = None
        days_until_monthly = None

        if budget:
            if budget.daily_budget and predicted_daily > 0:
                daily_key = f"{org_id}:{now.strftime('%Y%m%d')}"
                current_daily = self._spend_tracking.get(daily_key, 0)
                remaining_daily = budget.daily_budget - current_daily
                if remaining_daily > 0 and avg_hourly > 0:
                    hours_until_daily = remaining_daily / avg_hourly
                    will_exceed_daily = hours_until_daily < 24

            if budget.monthly_budget and predicted_monthly > 0:
                monthly_key = f"{org_id}:{now.strftime('%Y%m')}"
                current_monthly = self._spend_tracking.get(monthly_key, 0)
                remaining_monthly = budget.monthly_budget - current_monthly
                if remaining_monthly > 0 and predicted_daily > 0:
                    days_until_monthly = remaining_monthly / predicted_daily
                    will_exceed_monthly = days_until_monthly < 30

        return UsagePrediction(
            org_id=org_id,
            prediction_time=now,
            predicted_hourly_cost=avg_hourly,
            predicted_daily_cost=predicted_daily,
            predicted_monthly_cost=predicted_monthly,
            confidence=0.7 if len([c for c in hourly_costs if c > 0]) >= 12 else 0.4,
            trend=trend,
            will_exceed_daily_budget=will_exceed_daily,
            will_exceed_monthly_budget=will_exceed_monthly,
            hours_until_daily_limit=hours_until_daily,
            days_until_monthly_limit=days_until_monthly,
        )

    def _get_or_create_window(
        self,
        entity_id: UUID,
        limit: QuotaLimit,
    ) -> UsageWindow:
        """Get or create a usage window for tracking."""
        window_id = f"{entity_id}:{limit.name}"

        if window_id not in self._windows:
            now = datetime.utcnow()
            self._windows[window_id] = UsageWindow(
                window_id=window_id,
                entity_id=entity_id,
                limit_name=limit.name,
                window_start=now,
                window_end=now + timedelta(seconds=limit.window_seconds),
            )

        return self._windows[window_id]

    def _calculate_backoff(
        self,
        limit: QuotaLimit,
        current_usage: int,
    ) -> int:
        """Calculate recommended backoff delay in milliseconds."""
        overage_percent = current_usage / limit.limit_value if limit.limit_value > 0 else 1
        base_delay = 1000  # 1 second

        # Exponential backoff based on overage
        delay = int(base_delay * (2 ** (overage_percent - 1)))
        return min(delay, 60000)  # Cap at 60 seconds

    def get_alerts(
        self,
        entity_id: Optional[UUID] = None,
        unacknowledged_only: bool = False,
    ) -> List[QuotaAlert]:
        """Get alerts, optionally filtered."""
        alerts = self._alerts

        if entity_id:
            alerts = [a for a in alerts if a.entity_id == entity_id]

        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]

        return alerts

    async def acknowledge_alert(self, alert_id: UUID) -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_current_usage(
        self,
        entity_id: UUID,
    ) -> Dict[str, int]:
        """Get current usage for all limits."""
        result = {}
        limits = self._limits.get(entity_id, [self.DEFAULT_RPM_LIMIT, self.DEFAULT_TPM_LIMIT])

        for limit in limits:
            window = self._get_or_create_window(entity_id, limit)
            result[limit.name] = window.get_current_usage()

        return result

    def get_spend(
        self,
        org_id: UUID,
        period: str = "daily",
    ) -> float:
        """Get current spend for a period."""
        now = datetime.utcnow()

        if period == "daily":
            key = f"{org_id}:{now.strftime('%Y%m%d')}"
        elif period == "monthly":
            key = f"{org_id}:{now.strftime('%Y%m')}"
        else:
            return 0

        return self._spend_tracking.get(key, 0)


# Singleton instance
_guard_instance: Optional[QuotaGuard] = None


def get_quota_guard(
    alert_callback: Optional[Callable] = None,
) -> QuotaGuard:
    """Get or create the singleton quota guard instance."""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = QuotaGuard(alert_callback=alert_callback)
    return _guard_instance


def reset_quota_guard() -> None:
    """Reset the singleton instance (for testing)."""
    global _guard_instance
    _guard_instance = None
