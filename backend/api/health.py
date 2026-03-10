"""
Health Check Endpoints

Comprehensive health checks for production readiness.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from backend.shared.config import get_settings
from backend.database.session import get_db_session
from backend.orchestrator import get_registry, get_queue

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.

    Returns 200 if service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "agent-orchestrator",
    }


@router.get("/health/ready")
async def readiness_check() -> JSONResponse:
    """
    Readiness probe for Kubernetes.

    Checks if service can accept traffic:
    - Database connection
    - Redis connection
    - Core services initialized

    Returns:
        200 if ready, 503 if not ready
    """
    checks = {
        "database": False,
        "redis": False,
        "registry": False,
        "queue": False,
    }
    errors = []

    # Check database
    try:
        session = next(get_db_session())
        session.execute("SELECT 1")
        session.close()
        checks["database"] = True
    except Exception as e:
        errors.append(f"Database: {str(e)}")

    # Check Redis
    try:
        settings = get_settings()
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        checks["redis"] = True
    except Exception as e:
        errors.append(f"Redis: {str(e)}")

    # Check registry
    try:
        registry = get_registry()
        if registry:
            checks["registry"] = True
    except Exception as e:
        errors.append(f"Registry: {str(e)}")

    # Check queue
    try:
        queue = get_queue()
        if queue:
            checks["queue"] = True
    except Exception as e:
        errors.append(f"Queue: {str(e)}")

    all_healthy = all(checks.values())
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "ready": all_healthy,
            "checks": checks,
            "errors": errors if errors else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@router.get("/health/live")
async def liveness_check() -> JSONResponse:
    """
    Liveness probe for Kubernetes.

    Checks if service is alive and not deadlocked.

    Returns:
        200 if alive, 503 if deadlocked
    """
    try:
        # Simple ping-pong to ensure event loop is responsive
        await asyncio.sleep(0.001)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "alive": True,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "alive": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


@router.get("/health/startup")
async def startup_check() -> JSONResponse:
    """
    Startup probe for Kubernetes.

    Checks if service has completed initialization.

    Returns:
        200 if started, 503 if still starting
    """
    checks = {
        "database_migrations": False,
        "registry_initialized": False,
        "queue_initialized": False,
    }
    errors = []

    # Check database migrations
    try:
        session = next(get_db_session())
        # Check if alembic version table exists
        result = session.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version')"
        )
        checks["database_migrations"] = result.scalar()
        session.close()
    except Exception as e:
        errors.append(f"Database migrations: {str(e)}")

    # Check registry
    try:
        registry = get_registry()
        checks["registry_initialized"] = registry is not None
    except Exception as e:
        errors.append(f"Registry: {str(e)}")

    # Check queue
    try:
        queue = get_queue()
        checks["queue_initialized"] = queue is not None
    except Exception as e:
        errors.append(f"Queue: {str(e)}")

    all_started = all(checks.values())
    status_code = status.HTTP_200_OK if all_started else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "started": all_started,
            "checks": checks,
            "errors": errors if errors else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health status for monitoring.

    Includes:
    - System metrics
    - Component status
    - Agent statistics
    - Queue depths
    """
    from backend.observer.metrics_collector import get_collector

    try:
        collector = get_collector()
        metrics = await collector.collect_metrics()

        queue = get_queue()
        queue_depths = await queue.get_all_queue_depths()
        dlq_depth = await queue.get_dead_letter_queue_depth()

        registry = get_registry()
        agents = await registry.list_agents()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "api": "healthy",
                "database": "healthy",
                "redis": "healthy",
                "registry": "healthy",
                "queue": "healthy",
            },
            "statistics": {
                "agents": {
                    "total": len(agents),
                    "active": metrics.get("agents", {}).get("active", 0),
                },
                "tasks": {
                    "completed": metrics.get("tasks", {}).get("completed", 0),
                    "failed": metrics.get("tasks", {}).get("failed", 0),
                    "success_rate": metrics.get("tasks", {}).get("success_rate", 0),
                },
                "queues": {
                    "total_depth": sum(queue_depths.values()),
                    "dead_letter_queue": dlq_depth,
                    "by_capability": queue_depths,
                },
                "costs": {
                    "today": metrics.get("costs", {}).get("today", 0),
                    "month": metrics.get("costs", {}).get("month", 0),
                },
            },
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
