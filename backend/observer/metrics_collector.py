"""
Metrics Collector - Collects and aggregates metrics from orchestration components.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from uuid import UUID
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


# Bounded cache limits to prevent OOM
MAX_CAPABILITIES_TRACKED = 500
MAX_CACHE_ENTRIES = 100

from backend.shared.models import TaskStatus, AgentStatus
from backend.shared.config import get_settings

# Use TYPE_CHECKING to avoid circular imports at runtime
# These are only used for type hints, not actual imports
if TYPE_CHECKING:
    from backend.orchestrator import AgentRegistry, TaskQueue


class MetricsCollector:
    """
    Collects and aggregates metrics from agents, tasks, and system components.

    Features:
    - Real-time metric aggregation
    - Time-series data collection
    - Performance analytics
    - Cost attribution
    - Alert condition detection
    """

    def __init__(self):
        """Initialize metrics collector."""
        self.settings = get_settings()
        # Lazy import to avoid circular dependency
        # registry and queue are set on first access via properties
        self._registry = None
        self._queue = None

        # Time-series storage (in-memory for MVP, move to TimescaleDB later)
        self.task_latencies = defaultdict(lambda: deque(maxlen=1000))  # Last 1000 tasks per capability
        self.task_costs = defaultdict(lambda: deque(maxlen=1000))
        self.agent_utilization = defaultdict(lambda: deque(maxlen=1000))
        self.queue_depths_history = deque(maxlen=1000)

        # Aggregated metrics — per-key expiry: Dict[str, Tuple[Dict, datetime]]
        self.metrics_cache: Dict[str, Tuple[Dict, datetime]] = {}

        # Alert thresholds
        self.alert_thresholds = {
            "high_queue_depth": 100,  # Alert if any queue exceeds 100 tasks
            "high_error_rate": 0.1,  # Alert if error rate > 10%
            "high_cost_burn": 1000.0,  # Alert if daily cost > $1000
            "agent_down": 300,  # Alert if agent hasn't sent heartbeat in 5 minutes
            "slow_task": 60.0,  # Alert if task latency > 60s
        }

    @property
    def registry(self):
        """Lazy-load registry to avoid circular import."""
        if self._registry is None:
            from backend.orchestrator import get_registry
            self._registry = get_registry()
        return self._registry

    @property
    def queue(self):
        """Lazy-load queue to avoid circular import."""
        if self._queue is None:
            from backend.orchestrator import get_queue
            self._queue = get_queue()
        return self._queue

    async def collect_metrics(self, organization_id: Optional[str] = None) -> Dict:
        """
        Collect current metrics snapshot, scoped to an organization.

        Args:
            organization_id: Organization ID for tenant isolation

        Returns:
            Dictionary of all metrics
        """
        # Check cache (per-key expiry, org-scoped)
        cache_key = organization_id or "_global"
        if cache_key in self.metrics_cache:
            cached_data, expiry = self.metrics_cache[cache_key]
            if _utcnow() < expiry:
                return cached_data

        # Collect fresh metrics
        agents = await self.registry.list_agents(organization_id=organization_id)
        active_agents = await self.registry.list_agents(status=AgentStatus.ACTIVE, organization_id=organization_id)
        queue_depths = await self.queue.get_all_queue_depths()
        dlq_depth = await self.queue.get_dead_letter_queue_depth()

        # Aggregate agent metrics
        total_cost_today = 0.0
        total_cost_month = 0.0
        total_tasks_completed = 0
        total_tasks_failed = 0
        total_active_tasks = 0
        idle_agent_count = 0
        agent_details = []

        for agent in agents:
            state = await self.registry.get_agent_state(agent.agent_id)
            if state:
                total_cost_today += state.total_cost_today
                total_cost_month += state.total_cost_month
                total_tasks_completed += state.tasks_completed
                total_tasks_failed += state.tasks_failed
                total_active_tasks += state.active_tasks

                if state.active_tasks == 0:
                    idle_agent_count += 1

                agent_details.append({
                    "agent_id": str(agent.agent_id),
                    "name": agent.name,
                    "status": state.status.value,
                    "active_tasks": state.active_tasks,
                    "tasks_completed": state.tasks_completed,
                    "tasks_failed": state.tasks_failed,
                    "cost_today": state.total_cost_today,
                    "cost_month": state.total_cost_month,
                    "last_heartbeat": state.last_heartbeat.isoformat() if state.last_heartbeat else None,
                })

        # Calculate rates and percentages
        total_tasks = total_tasks_completed + total_tasks_failed
        success_rate = total_tasks_completed / total_tasks if total_tasks > 0 else 0.0
        error_rate = total_tasks_failed / total_tasks if total_tasks > 0 else 0.0

        # Calculate agent utilization
        total_capacity = sum(agent.max_concurrent_tasks for agent in agents)
        utilization = total_active_tasks / total_capacity if total_capacity > 0 else 0.0

        metrics = {
            "timestamp": _utcnow().isoformat(),
            "agents": {
                "total": len(agents),
                "active": len(active_agents),
                "idle": idle_agent_count,
                "utilization": utilization,
                "details": agent_details,
            },
            "tasks": {
                "completed": total_tasks_completed,
                "failed": total_tasks_failed,
                "total": total_tasks,
                "success_rate": success_rate,
                "error_rate": error_rate,
            },
            "queues": {
                "total_depth": sum(queue_depths.values()),
                "by_capability": queue_depths,
                "dead_letter_queue": dlq_depth,
            },
            "costs": {
                "today": total_cost_today,
                "month": total_cost_month,
                "by_agent": {
                    agent["name"]: agent["cost_today"]
                    for agent in agent_details
                },
            },
            "system": {
                "environment": self.settings.ENVIRONMENT,
                "version": "0.1.0",
            }
        }

        # Cache for 5 seconds (per-key expiry, org-scoped)
        if len(self.metrics_cache) >= MAX_CACHE_ENTRIES:
            # Evict expired entries first, then oldest if still over limit
            now = _utcnow()
            self.metrics_cache = {k: v for k, v in self.metrics_cache.items() if v[1] > now}
        self.metrics_cache[cache_key] = (metrics, _utcnow() + timedelta(seconds=5))

        return metrics

    async def record_task_completion(
        self,
        task_id: UUID,
        capability: str,
        latency_seconds: float,
        cost: float,
        success: bool
    ) -> None:
        """
        Record task completion metrics.

        Args:
            task_id: Task ID
            capability: Task capability
            latency_seconds: Task execution time
            cost: Task cost in USD
            success: Whether task succeeded
        """
        timestamp = _utcnow()

        # Store in time-series
        self.task_latencies[capability].append({
            "timestamp": timestamp,
            "task_id": str(task_id),
            "latency": latency_seconds,
            "success": success,
        })

        self.task_costs[capability].append({
            "timestamp": timestamp,
            "task_id": str(task_id),
            "cost": cost,
            "success": success,
        })

        # Invalidate all cached metrics
        self.metrics_cache.clear()

        # Evict old capabilities if over limit
        if len(self.task_latencies) > MAX_CAPABILITIES_TRACKED:
            oldest_keys = list(self.task_latencies.keys())[:-MAX_CAPABILITIES_TRACKED]
            for key in oldest_keys:
                del self.task_latencies[key]
                self.task_costs.pop(key, None)

        logger.info(f"Recorded metrics for task {task_id}: capability={capability}, latency={latency_seconds:.2f}s, cost=${cost:.4f}, success={success}")

    async def get_capability_metrics(self, capability: str) -> Dict:
        """
        Get detailed metrics for a specific capability.

        Args:
            capability: Capability name

        Returns:
            Capability metrics
        """
        latencies = list(self.task_latencies.get(capability, []))
        costs = list(self.task_costs.get(capability, []))

        if not latencies:
            return {
                "capability": capability,
                "task_count": 0,
                "avg_latency": 0.0,
                "p95_latency": 0.0,
                "p99_latency": 0.0,
                "avg_cost": 0.0,
                "total_cost": 0.0,
                "success_rate": 0.0,
            }

        # Calculate statistics
        latency_values = [entry["latency"] for entry in latencies]
        cost_values = [entry["cost"] for entry in costs]
        successes = sum(1 for entry in latencies if entry["success"])

        latency_values.sort()
        p95_index = int(len(latency_values) * 0.95)
        p99_index = int(len(latency_values) * 0.99)

        return {
            "capability": capability,
            "task_count": len(latencies),
            "avg_latency": sum(latency_values) / len(latency_values),
            "p95_latency": latency_values[p95_index] if p95_index < len(latency_values) else 0.0,
            "p99_latency": latency_values[p99_index] if p99_index < len(latency_values) else 0.0,
            "avg_cost": sum(cost_values) / len(cost_values),
            "total_cost": sum(cost_values),
            "success_rate": successes / len(latencies),
        }

    async def get_agent_performance(self, agent_id: UUID) -> Dict:
        """
        Get detailed performance metrics for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Agent performance metrics
        """
        state = await self.registry.get_agent_state(agent_id)
        config = await self.registry.get_agent(agent_id)

        if not state or not config:
            return {}

        total_tasks = state.tasks_completed + state.tasks_failed
        success_rate = state.tasks_completed / total_tasks if total_tasks > 0 else 0.0

        # Calculate time since last heartbeat
        time_since_heartbeat = None
        if state.last_heartbeat:
            time_since_heartbeat = (_utcnow() - state.last_heartbeat).total_seconds()

        return {
            "agent_id": str(agent_id),
            "name": config.name,
            "status": state.status.value,
            "capabilities": [c.name for c in config.capabilities],
            "performance": {
                "tasks_completed": state.tasks_completed,
                "tasks_failed": state.tasks_failed,
                "success_rate": success_rate,
                "active_tasks": state.active_tasks,
                "max_concurrent": config.max_concurrent_tasks,
                "utilization": state.active_tasks / config.max_concurrent_tasks,
            },
            "costs": {
                "today": state.total_cost_today,
                "month": state.total_cost_month,
                "limit_daily": config.cost_limit_daily,
                "limit_monthly": config.cost_limit_monthly,
                "usage_pct_daily": (state.total_cost_today / config.cost_limit_daily) * 100,
                "usage_pct_monthly": (state.total_cost_month / config.cost_limit_monthly) * 100,
            },
            "health": {
                "last_heartbeat": state.last_heartbeat.isoformat() if state.last_heartbeat else None,
                "seconds_since_heartbeat": time_since_heartbeat,
                "is_healthy": time_since_heartbeat < 60 if time_since_heartbeat else False,
            }
        }

    async def check_alerts(self, organization_id: Optional[str] = None) -> List[Dict]:
        """
        Check for alert conditions, scoped to an organization.

        Args:
            organization_id: Organization ID for tenant isolation

        Returns:
            List of active alerts
        """
        alerts = []

        # Get current metrics
        metrics = await self.collect_metrics(organization_id=organization_id)

        # Check high queue depth
        for capability, depth in metrics["queues"]["by_capability"].items():
            if depth > self.alert_thresholds["high_queue_depth"]:
                alerts.append({
                    "severity": "warning",
                    "type": "high_queue_depth",
                    "capability": capability,
                    "current_value": depth,
                    "threshold": self.alert_thresholds["high_queue_depth"],
                    "message": f"Queue depth for {capability} is {depth} (threshold: {self.alert_thresholds['high_queue_depth']})",
                })

        # Check high error rate
        if metrics["tasks"]["error_rate"] > self.alert_thresholds["high_error_rate"]:
            alerts.append({
                "severity": "critical",
                "type": "high_error_rate",
                "current_value": metrics["tasks"]["error_rate"],
                "threshold": self.alert_thresholds["high_error_rate"],
                "message": f"Task error rate is {metrics['tasks']['error_rate']:.1%} (threshold: {self.alert_thresholds['high_error_rate']:.1%})",
            })

        # Check high cost burn
        if metrics["costs"]["today"] > self.alert_thresholds["high_cost_burn"]:
            alerts.append({
                "severity": "warning",
                "type": "high_cost_burn",
                "current_value": metrics["costs"]["today"],
                "threshold": self.alert_thresholds["high_cost_burn"],
                "message": f"Daily cost is ${metrics['costs']['today']:.2f} (threshold: ${self.alert_thresholds['high_cost_burn']:.2f})",
            })

        # Check agent health
        for agent in metrics["agents"]["details"]:
            if agent["status"] == "active" and agent["last_heartbeat"]:
                last_heartbeat = datetime.fromisoformat(agent["last_heartbeat"])
                seconds_since = (_utcnow() - last_heartbeat).total_seconds()

                if seconds_since > self.alert_thresholds["agent_down"]:
                    alerts.append({
                        "severity": "critical",
                        "type": "agent_down",
                        "agent_id": agent["agent_id"],
                        "agent_name": agent["name"],
                        "current_value": seconds_since,
                        "threshold": self.alert_thresholds["agent_down"],
                        "message": f"Agent {agent['name']} hasn't sent heartbeat in {seconds_since:.0f}s (threshold: {self.alert_thresholds['agent_down']}s)",
                    })

        # Check slow tasks (per capability)
        for capability in self.task_latencies.keys():
            recent_latencies = [
                entry["latency"]
                for entry in list(self.task_latencies[capability])[-10:]  # Last 10 tasks
            ]

            if recent_latencies:
                avg_latency = sum(recent_latencies) / len(recent_latencies)

                if avg_latency > self.alert_thresholds["slow_task"]:
                    alerts.append({
                        "severity": "warning",
                        "type": "slow_task",
                        "capability": capability,
                        "current_value": avg_latency,
                        "threshold": self.alert_thresholds["slow_task"],
                        "message": f"Average task latency for {capability} is {avg_latency:.1f}s (threshold: {self.alert_thresholds['slow_task']}s)",
                    })

        return alerts

    async def get_time_series(
        self,
        metric: str,
        capability: Optional[str] = None,
        window_minutes: int = 60
    ) -> List[Dict]:
        """
        Get time-series data for a metric.

        Args:
            metric: Metric name (latency, cost, queue_depth)
            capability: Capability to filter by (optional)
            window_minutes: Time window in minutes

        Returns:
            Time-series data points
        """
        cutoff_time = _utcnow() - timedelta(minutes=window_minutes)

        if metric == "latency":
            data = self.task_latencies.get(capability, []) if capability else []
            return [
                {"timestamp": entry["timestamp"].isoformat(), "value": entry["latency"]}
                for entry in data
                if entry["timestamp"] >= cutoff_time
            ]

        elif metric == "cost":
            data = self.task_costs.get(capability, []) if capability else []
            return [
                {"timestamp": entry["timestamp"].isoformat(), "value": entry["cost"]}
                for entry in data
                if entry["timestamp"] >= cutoff_time
            ]

        else:
            return []


# Global collector instance
_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get or create global metrics collector instance."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
