"""
Prometheus Metrics Export (V2 - Using Core Monitoring)

Exports metrics for Prometheus scraping using core/monitoring module.
"""
import sys
import os

# Add core to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from fastapi import APIRouter, Response
from core.monitoring import get_metrics_manager

# Get metrics manager
metrics = get_metrics_manager()

# ============================================================================
# Platform-Specific Metrics
# ============================================================================

# Agent metrics
agents_registered_total = metrics.create_gauge(
    name='agents_registered_total',
    description='Total number of registered agents',
    labels=[]
)

agents_active_total = metrics.create_gauge(
    name='agents_active_total',
    description='Number of active agents',
    labels=[]
)

agents_error_total = metrics.create_gauge(
    name='agents_error_total',
    description='Number of agents in error state',
    labels=[]
)

# Task metrics
tasks_queued_total = metrics.create_gauge(
    name='tasks_queued_total',
    description='Total tasks currently in queue',
    labels=['capability']
)

tasks_completed_total = metrics.create_counter(
    name='tasks_completed_total',
    description='Total completed tasks',
    labels=['capability']
)

tasks_failed_total = metrics.create_counter(
    name='tasks_failed_total',
    description='Total failed tasks',
    labels=['capability']
)

task_duration_seconds = metrics.create_histogram(
    name='task_duration_seconds',
    description='Task execution duration in seconds',
    labels=['capability'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0]
)

# Agent cost metrics
agent_cost_today = metrics.create_gauge(
    name='agent_cost_today',
    description='Agent cost today in USD',
    labels=['agent_id']
)

# Queue metrics
queue_depth = metrics.create_gauge(
    name='queue_depth',
    description='Current queue depth',
    labels=['capability']
)

dead_letter_queue_depth = metrics.create_gauge(
    name='dead_letter_queue_depth',
    description='Dead letter queue depth',
    labels=[]
)


# ============================================================================
# Metrics Updater
# ============================================================================

async def update_metrics():
    """Update all Prometheus metrics from current state."""
    from backend.orchestrator import get_registry, get_queue

    try:
        registry_instance = get_registry()
        queue_instance = get_queue()

        # Agent metrics
        agents = await registry_instance.list_agents()
        active_agents = await registry_instance.list_agents(status="active")
        error_agents = await registry_instance.list_agents(status="error")

        agents_registered_total.set(len(agents))
        agents_active_total.set(len(active_agents))
        agents_error_total.set(len(error_agents))

        # Queue metrics
        queue_depths = await queue_instance.get_all_queue_depths()
        for capability, depth in queue_depths.items():
            queue_depth.labels(capability=capability).set(depth)

        dlq_depth = await queue_instance.get_dead_letter_queue_depth()
        dead_letter_queue_depth.set(dlq_depth)

        # Agent cost metrics
        for agent in agents:
            state = await registry_instance.get_agent_state(agent.agent_id)
            if state:
                agent_cost_today.labels(agent_id=str(agent.agent_id)).set(
                    state.total_cost_today
                )

    except Exception as e:
        print(f"Error updating metrics: {e}")


# ============================================================================
# FastAPI Router
# ============================================================================

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus exposition format.
    Uses core/monitoring module for unified platform metrics.
    """
    # Update metrics before scraping
    await update_metrics()

    # Generate and return metrics using core/monitoring
    return Response(
        content=metrics.export_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


# ============================================================================
# Helper Functions (for backward compatibility)
# ============================================================================

def track_http_request(method: str, endpoint: str, status: int, duration: float):
    """Track HTTP request (uses core/monitoring)"""
    metrics.track_http_request(
        service="agent-orchestration",
        method=method,
        endpoint=endpoint,
        status_code=status,
        duration=duration
    )


def track_task_completion(capability: str):
    """Track task completion"""
    tasks_completed_total.labels(capability=capability).inc()


def track_task_failure(capability: str):
    """Track task failure"""
    tasks_failed_total.labels(capability=capability).inc()


def track_task_duration(capability: str, duration: float):
    """Track task duration"""
    task_duration_seconds.labels(capability=capability).observe(duration)


def track_agent_cost(agent_id: str, cost: float):
    """Track agent cost"""
    agent_cost_today.labels(agent_id=agent_id).set(cost)
