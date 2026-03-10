"""
Prometheus Metrics Export

Exports metrics for Prometheus scraping.
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, REGISTRY
from prometheus_client import CollectorRegistry
from fastapi import APIRouter, Response

# Create custom registry
registry = CollectorRegistry()

# ============================================================================
# Metrics
# ============================================================================

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=registry
)

# Agent metrics
agents_registered_total = Gauge(
    'agents_registered_total',
    'Total number of registered agents',
    registry=registry
)

agents_active_total = Gauge(
    'agents_active_total',
    'Number of active agents',
    registry=registry
)

agents_error_total = Gauge(
    'agents_error_total',
    'Number of agents in error state',
    registry=registry
)

# Task metrics
tasks_queued_total = Gauge(
    'tasks_queued_total',
    'Total tasks currently in queue',
    ['capability'],
    registry=registry
)

tasks_completed_total = Counter(
    'tasks_completed_total',
    'Total completed tasks',
    ['capability'],
    registry=registry
)

tasks_failed_total = Counter(
    'tasks_failed_total',
    'Total failed tasks',
    ['capability'],
    registry=registry
)

task_duration_seconds = Histogram(
    'task_duration_seconds',
    'Task execution duration in seconds',
    ['capability'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
    registry=registry
)

# Cost metrics
llm_cost_total = Counter(
    'llm_cost_total',
    'Total LLM cost in USD',
    ['agent_id', 'provider', 'model'],
    registry=registry
)

agent_cost_today = Gauge(
    'agent_cost_today',
    'Agent cost today in USD',
    ['agent_id'],
    registry=registry
)

# Queue metrics
queue_depth = Gauge(
    'queue_depth',
    'Current queue depth',
    ['capability'],
    registry=registry
)

dead_letter_queue_depth = Gauge(
    'dead_letter_queue_depth',
    'Dead letter queue depth',
    registry=registry
)

# System metrics
system_info = Info(
    'agent_orchestrator_system',
    'System information',
    registry=registry
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
    """
    # Update metrics before scraping
    await update_metrics()

    # Generate and return metrics
    return Response(
        content=generate_latest(registry),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )
