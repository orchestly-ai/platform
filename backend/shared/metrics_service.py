"""
Metrics Service for Agent Orchestration Platform

Provides Prometheus metrics collection for:
- API requests
- LLM usage
- Workflow execution
- Database operations
- Cache performance
"""

import time
from typing import Optional, Callable
from functools import wraps
from contextlib import contextmanager

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary,
        generate_latest, CONTENT_TYPE_LATEST,
        CollectorRegistry, multiprocess, REGISTRY
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

from backend.shared.config import settings


# ============================================================================
# Metric Definitions
# ============================================================================

if HAS_PROMETHEUS and settings.ENABLE_METRICS:
    # API Metrics
    API_REQUESTS_TOTAL = Counter(
        'api_requests_total',
        'Total API requests',
        ['method', 'endpoint', 'status']
    )

    API_REQUEST_DURATION = Histogram(
        'api_request_duration_seconds',
        'API request duration',
        ['method', 'endpoint'],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )

    API_REQUESTS_ACTIVE = Gauge(
        'api_requests_active',
        'Currently active API requests',
        ['endpoint']
    )

    # LLM Metrics
    LLM_REQUESTS_TOTAL = Counter(
        'llm_requests_total',
        'Total LLM requests',
        ['provider', 'model', 'status']
    )

    LLM_REQUEST_DURATION = Histogram(
        'llm_request_duration_seconds',
        'LLM request duration',
        ['provider', 'model'],
        buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
    )

    LLM_TOKENS_TOTAL = Counter(
        'llm_tokens_total',
        'Total LLM tokens',
        ['provider', 'type']  # type: input/output
    )

    LLM_COST_TOTAL = Counter(
        'llm_cost_dollars_total',
        'Total LLM cost in dollars',
        ['provider', 'org_id']
    )

    # Workflow Metrics
    WORKFLOW_EXECUTIONS_TOTAL = Counter(
        'workflow_executions_total',
        'Total workflow executions',
        ['status']
    )

    WORKFLOW_DURATION = Histogram(
        'workflow_duration_seconds',
        'Workflow execution duration',
        ['workflow_id'],
        buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800]
    )

    WORKFLOWS_ACTIVE = Gauge(
        'workflows_active_total',
        'Currently active workflows'
    )

    # Agent Metrics
    AGENT_TASKS_TOTAL = Counter(
        'agent_tasks_total',
        'Total agent tasks',
        ['agent_id', 'status']
    )

    AGENT_TASKS_ACTIVE = Gauge(
        'agent_tasks_active',
        'Currently active agent tasks',
        ['agent_id']
    )

    AGENT_TASK_DURATION = Histogram(
        'agent_task_duration_seconds',
        'Agent task duration',
        ['agent_type'],
        buckets=[1, 5, 10, 30, 60, 120, 300]
    )

    # Database Metrics
    DB_QUERY_DURATION = Histogram(
        'db_query_duration_seconds',
        'Database query duration',
        ['operation', 'table'],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
    )

    DB_QUERIES_TOTAL = Counter(
        'db_queries_total',
        'Total database queries',
        ['operation']
    )

    DB_CONNECTIONS_ACTIVE = Gauge(
        'db_connections_active',
        'Active database connections'
    )

    DB_CONNECTIONS_IDLE = Gauge(
        'db_connections_idle',
        'Idle database connections'
    )

    # Cache Metrics
    CACHE_HITS = Counter(
        'cache_hits_total',
        'Cache hits',
        ['cache']
    )

    CACHE_MISSES = Counter(
        'cache_misses_total',
        'Cache misses',
        ['cache']
    )

    CACHE_OPERATIONS = Counter(
        'cache_operations_total',
        'Cache operations',
        ['operation']
    )

    CACHE_OPERATION_DURATION = Histogram(
        'cache_operation_duration_seconds',
        'Cache operation duration',
        ['operation'],
        buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05]
    )

    # Rate Limiting Metrics
    RATE_LIMIT_HITS = Counter(
        'rate_limit_hits_total',
        'Rate limit hits',
        ['org_id']
    )

    RATE_LIMIT_REMAINING = Gauge(
        'rate_limit_remaining',
        'Remaining rate limit',
        ['org_id']
    )


# ============================================================================
# Metrics Service Class
# ============================================================================

class MetricsService:
    """Service for collecting and exposing Prometheus metrics."""

    def __init__(self):
        self.enabled = HAS_PROMETHEUS and settings.ENABLE_METRICS

    # =========================================================================
    # API Metrics
    # =========================================================================

    def record_api_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float
    ):
        """Record an API request."""
        if not self.enabled:
            return

        API_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status=str(status)
        ).inc()

        API_REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

    @contextmanager
    def track_api_request(self, method: str, endpoint: str):
        """Context manager to track API request duration."""
        if not self.enabled:
            yield
            return

        API_REQUESTS_ACTIVE.labels(endpoint=endpoint).inc()
        start_time = time.time()
        status = 200

        try:
            yield
        except Exception as e:
            status = 500
            raise
        finally:
            duration = time.time() - start_time
            API_REQUESTS_ACTIVE.labels(endpoint=endpoint).dec()
            self.record_api_request(method, endpoint, status, duration)

    # =========================================================================
    # LLM Metrics
    # =========================================================================

    def record_llm_request(
        self,
        provider: str,
        model: str,
        status: str,
        duration: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        org_id: Optional[str] = None
    ):
        """Record an LLM request."""
        if not self.enabled:
            return

        LLM_REQUESTS_TOTAL.labels(
            provider=provider,
            model=model,
            status=status
        ).inc()

        LLM_REQUEST_DURATION.labels(
            provider=provider,
            model=model
        ).observe(duration)

        if input_tokens > 0:
            LLM_TOKENS_TOTAL.labels(
                provider=provider,
                type='input'
            ).inc(input_tokens)

        if output_tokens > 0:
            LLM_TOKENS_TOTAL.labels(
                provider=provider,
                type='output'
            ).inc(output_tokens)

        if cost > 0 and org_id:
            LLM_COST_TOTAL.labels(
                provider=provider,
                org_id=org_id
            ).inc(cost)

    # =========================================================================
    # Workflow Metrics
    # =========================================================================

    def record_workflow_execution(
        self,
        workflow_id: str,
        status: str,
        duration: float
    ):
        """Record a workflow execution."""
        if not self.enabled:
            return

        WORKFLOW_EXECUTIONS_TOTAL.labels(status=status).inc()
        WORKFLOW_DURATION.labels(workflow_id=workflow_id).observe(duration)

    def set_active_workflows(self, count: int):
        """Set the number of active workflows."""
        if not self.enabled:
            return

        WORKFLOWS_ACTIVE.set(count)

    # =========================================================================
    # Agent Metrics
    # =========================================================================

    def record_agent_task(
        self,
        agent_id: str,
        agent_type: str,
        status: str,
        duration: float
    ):
        """Record an agent task."""
        if not self.enabled:
            return

        AGENT_TASKS_TOTAL.labels(
            agent_id=agent_id,
            status=status
        ).inc()

        AGENT_TASK_DURATION.labels(
            agent_type=agent_type
        ).observe(duration)

    def set_agent_active_tasks(self, agent_id: str, count: int):
        """Set the number of active tasks for an agent."""
        if not self.enabled:
            return

        AGENT_TASKS_ACTIVE.labels(agent_id=agent_id).set(count)

    # =========================================================================
    # Database Metrics
    # =========================================================================

    def record_db_query(
        self,
        operation: str,
        table: str,
        duration: float
    ):
        """Record a database query."""
        if not self.enabled:
            return

        DB_QUERIES_TOTAL.labels(operation=operation).inc()
        DB_QUERY_DURATION.labels(
            operation=operation,
            table=table
        ).observe(duration)

    @contextmanager
    def track_db_query(self, operation: str, table: str):
        """Context manager to track database query duration."""
        if not self.enabled:
            yield
            return

        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_db_query(operation, table, duration)

    def set_db_connections(self, active: int, idle: int):
        """Set database connection pool stats."""
        if not self.enabled:
            return

        DB_CONNECTIONS_ACTIVE.set(active)
        DB_CONNECTIONS_IDLE.set(idle)

    # =========================================================================
    # Cache Metrics
    # =========================================================================

    def record_cache_hit(self, cache_name: str = "default"):
        """Record a cache hit."""
        if not self.enabled:
            return

        CACHE_HITS.labels(cache=cache_name).inc()

    def record_cache_miss(self, cache_name: str = "default"):
        """Record a cache miss."""
        if not self.enabled:
            return

        CACHE_MISSES.labels(cache=cache_name).inc()

    def record_cache_operation(
        self,
        operation: str,
        duration: float
    ):
        """Record a cache operation."""
        if not self.enabled:
            return

        CACHE_OPERATIONS.labels(operation=operation).inc()
        CACHE_OPERATION_DURATION.labels(operation=operation).observe(duration)

    # =========================================================================
    # Rate Limiting Metrics
    # =========================================================================

    def record_rate_limit_hit(self, org_id: str):
        """Record a rate limit hit."""
        if not self.enabled:
            return

        RATE_LIMIT_HITS.labels(org_id=org_id).inc()

    def set_rate_limit_remaining(self, org_id: str, remaining: int):
        """Set remaining rate limit."""
        if not self.enabled:
            return

        RATE_LIMIT_REMAINING.labels(org_id=org_id).set(remaining)

    # =========================================================================
    # Export
    # =========================================================================

    def get_metrics(self) -> bytes:
        """Generate Prometheus metrics output."""
        if not self.enabled:
            return b"# Metrics disabled\n"

        return generate_latest(REGISTRY)

    def get_content_type(self) -> str:
        """Get Prometheus content type."""
        if not self.enabled:
            return "text/plain"

        return CONTENT_TYPE_LATEST


# Global metrics instance
metrics_service = MetricsService()


def get_metrics() -> MetricsService:
    """Get metrics service instance."""
    return metrics_service


# ============================================================================
# Decorators
# ============================================================================

def track_api_request(endpoint: str):
    """Decorator to track API request metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            metrics = get_metrics()
            method = "GET"  # Default, should be overridden

            with metrics.track_api_request(method, endpoint):
                return await func(*args, **kwargs)

        return wrapper
    return decorator


def track_llm_request(provider: str, model: str):
    """Decorator to track LLM request metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            metrics = get_metrics()
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                metrics.record_llm_request(
                    provider=provider,
                    model=model,
                    status=status,
                    duration=duration
                )

        return wrapper
    return decorator


def track_db_query(operation: str, table: str):
    """Decorator to track database query metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            metrics = get_metrics()

            with metrics.track_db_query(operation, table):
                return await func(*args, **kwargs)

        return wrapper
    return decorator
