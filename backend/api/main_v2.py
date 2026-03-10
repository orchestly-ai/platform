"""
FastAPI Main Application V2

REST API for Agent Orchestration Platform using core modules.
"""
import sys
import os

# Add core to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from uuid import UUID
import time

from backend.shared.models import (
    AgentConfig,
    AgentState,
    Task,
    TaskInput,
    TaskOutput,
    LLMRequest,
    LLMResponse,
    TaskStatus,
    TaskPriority,
)
from backend.shared.config import get_settings
from backend.orchestrator import get_registry, get_router, get_queue
from backend.gateway.llm_proxy import get_gateway
from backend.observer.metrics_collector import get_collector
from backend.observer.alert_manager import get_alert_manager
from backend.shared.auth_v2 import verify_api_key, verify_agent_access, create_agent_api_key, has_permission
from backend.shared.metrics_v2 import track_http_request, router as metrics_router

# Import core modules
from core.monitoring import get_metrics_manager, get_tracer, track_request
from core.auth import get_auth_manager


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    print("🚀 Starting Agent Orchestration Platform V2...")

    # Initialize services
    settings = get_settings()
    registry = get_registry()
    router = get_router()
    queue = get_queue()
    gateway = get_gateway()
    collector = get_collector()
    alert_manager = get_alert_manager()

    # Initialize core modules
    metrics = get_metrics_manager()
    auth = get_auth_manager()
    tracer = get_tracer("agent-orchestration")

    print(f"   API: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"   Environment: {settings.ENVIRONMENT}")
    print(f"   Debug: {settings.DEBUG}")
    print(f"   Core Modules: ✅ Monitoring, Auth, LLM")
    print("✅ Platform ready\n")

    yield

    # Cleanup
    print("\n🛑 Shutting down...")
    await queue.close()
    print("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Agent Orchestration Platform API V2",
    description="""
    **Production-grade orchestration for multi-agent AI systems**

    The Agent Orchestration Platform provides enterprise-ready infrastructure for deploying
    and managing autonomous agent teams at scale.

    ## Features

    * 🛡️ **Agent Gateway** - Proxy all LLM API calls with cost controls and rate limiting
    * 📊 **Unified Observability** - Real-time monitoring with core/monitoring module
    * 🧠 **Intelligent Routing** - Smart task routing based on agent capabilities
    * 🔄 **Multi-Agent Coordination** - Manage complex multi-agent workflows
    * 💰 **Cost Tracking** - Per-agent cost tracking with core/llm integration
    * 🚨 **Alert Management** - Automated alerts for failures and anomalies
    * 🔐 **Enterprise Auth** - API key authentication with core/auth module

    ## What's New in V2

    * ✨ **Core Module Integration** - Uses shared core modules (monitoring, auth, llm)
    * 📈 **Better Metrics** - Prometheus metrics via core/monitoring
    * 🎯 **Distributed Tracing** - OpenTelemetry tracing for debugging
    * 🔑 **Enhanced Auth** - API key management via core/auth
    * 💸 **Unified LLM Routing** - All LLM providers via core/llm

    ## Authentication

    All API endpoints require an API key passed via the `X-API-Key` header.
    Obtain an API key by registering an agent.

    ## Getting Started

    1. Register your agent using `POST /api/v2/agents`
    2. Poll for tasks using `GET /api/v2/agents/{agent_id}/tasks/next`
    3. Submit results using `POST /api/v2/tasks/{task_id}/result`
    4. Monitor metrics in the dashboard at http://localhost:3000

    ## Documentation

    * [Full Documentation](https://docs.agent-orchestrator.dev)
    * [GitHub Repository](https://github.com/orchestly-ai/platform)
    * [SDK Documentation](https://docs.agent-orchestrator.dev/sdk)
    """,
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "agents",
            "description": "Agent registration and management operations",
        },
        {
            "name": "tasks",
            "description": "Task submission, polling, and result management",
        },
        {
            "name": "workflows",
            "description": "Visual workflow designer and execution management",
        },
        {
            "name": "metrics",
            "description": "System metrics and observability (core/monitoring)",
        },
        {
            "name": "alerts",
            "description": "Alert management and notifications",
        },
        {
            "name": "gateway",
            "description": "LLM gateway and proxy operations (core/llm)",
        },
        {
            "name": "health",
            "description": "Health check and system status",
        },
    ],
    contact={
        "name": "Agent Orchestration Platform Team",
        "url": "https://github.com/orchestly-ai/platform",
        "email": "support@agent-orchestrator.dev",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Get settings
settings = get_settings()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include metrics router
app.include_router(metrics_router)

# Include workflow router
from backend.api.workflows import router as workflow_router
app.include_router(workflow_router)


# ============================================================================
# Middleware for Request Tracking
# ============================================================================

@app.middleware("http")
async def track_requests(request, call_next):
    """Track all HTTP requests using core/monitoring."""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    track_http_request(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
        duration=duration
    )

    return response


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
@track_request(service="agent-orchestration", endpoint="/health")
async def health_check():
    """Health check endpoint."""
    registry = get_registry()
    queue = get_queue()

    # Get system stats
    agents = await registry.list_agents()
    queue_depths = await queue.get_all_queue_depths()

    return {
        "status": "healthy",
        "version": "0.2.0",
        "core_modules": ["monitoring", "auth", "llm"],
        "agents": {
            "total": len(agents),
            "active": len(await registry.list_agents(status="active")),
        },
        "queues": {
            "total_depth": sum(queue_depths.values()),
            "capabilities": list(queue_depths.keys()),
        }
    }


# ============================================================================
# Agent Management Endpoints (V2)
# ============================================================================

@app.post("/api/v2/agents", status_code=201, tags=["agents"])
@track_request(service="agent-orchestration", endpoint="/api/v2/agents")
async def register_agent(
    config: AgentConfig,
    api_key: dict = Depends(verify_api_key)
):
    """
    Register a new agent.

    Returns agent ID and API key for authentication (using core/auth).
    """
    registry = get_registry()

    try:
        agent_id = await registry.register_agent(config)

        # Generate API key using core/auth
        new_api_key = await create_agent_api_key(
            agent_id=agent_id,
            agent_name=config.name,
            permissions=["agent:*"]
        )

        return {
            "agent_id": str(agent_id),
            "api_key": new_api_key,
            "status": "registered",
            "note": "API key managed by core/auth module"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v2/agents", tags=["agents"])
@track_request(service="agent-orchestration", endpoint="/api/v2/agents")
async def list_agents(
    status: Optional[str] = None,
    user: dict = Depends(verify_api_key)
):
    """List all registered agents."""
    registry = get_registry()

    agents = await registry.list_agents(status=status)

    return {
        "agents": [
            {
                "agent_id": str(agent.agent_id),
                "name": agent.name,
                "capabilities": [c.name for c in agent.capabilities],
                "framework": agent.framework,
                "version": agent.version,
            }
            for agent in agents
        ],
        "total": len(agents)
    }


@app.get("/api/v2/agents/{agent_id}", tags=["agents"])
@track_request(service="agent-orchestration", endpoint="/api/v2/agents/{agent_id}")
async def get_agent(
    agent_id: UUID,
    user: dict = Depends(verify_agent_access)
):
    """Get agent details and metrics."""
    registry = get_registry()

    metrics = await registry.get_agent_metrics(agent_id)

    if not metrics:
        raise HTTPException(status_code=404, detail="Agent not found")

    return metrics


@app.post("/api/v2/agents/{agent_id}/heartbeat", tags=["agents"])
async def agent_heartbeat(
    agent_id: UUID,
    user: dict = Depends(verify_agent_access)
):
    """Update agent heartbeat."""
    registry = get_registry()

    await registry.update_heartbeat(agent_id)

    return {"status": "ok", "timestamp": "updated"}


@app.delete("/api/v2/agents/{agent_id}", tags=["agents"])
async def deregister_agent(
    agent_id: UUID,
    user: dict = Depends(verify_agent_access)
):
    """Deregister an agent."""
    registry = get_registry()

    await registry.deregister_agent(agent_id)

    return {"status": "deregistered", "agent_id": str(agent_id)}


# ============================================================================
# Task Management Endpoints (V2)
# ============================================================================

@app.post("/api/v2/tasks", status_code=201, tags=["tasks"])
@track_request(service="agent-orchestration", endpoint="/api/v2/tasks")
async def submit_task(
    capability: str,
    input_data: dict,
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout_seconds: int = 300,
    max_retries: int = 3,
    user: dict = Depends(verify_api_key)
):
    """Submit a new task."""
    queue = get_queue()

    # Create task
    task = Task(
        capability=capability,
        input=TaskInput(data=input_data),
        priority=priority,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )

    # Enqueue
    task_id = await queue.enqueue_task(task)

    return {
        "task_id": str(task_id),
        "status": "queued",
        "capability": capability
    }


@app.get("/api/v2/tasks/{task_id}", tags=["tasks"])
@track_request(service="agent-orchestration", endpoint="/api/v2/tasks/{task_id}")
async def get_task(
    task_id: UUID,
    user: dict = Depends(verify_api_key)
):
    """Get task status and details."""
    queue = get_queue()

    task = await queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": str(task.task_id),
        "capability": task.capability,
        "status": task.status.value,
        "assigned_agent_id": str(task.assigned_agent_id) if task.assigned_agent_id else None,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "retry_count": task.retry_count,
        "cost": task.actual_cost,
        "output": task.output.data if task.output else None,
        "error": task.error_message,
    }


@app.get("/api/v2/agents/{agent_id}/tasks/next", tags=["tasks"])
async def get_next_task(
    agent_id: UUID,
    capabilities: str,  # Comma-separated list
    user: dict = Depends(verify_agent_access)
):
    """
    Poll for next task matching agent capabilities.

    Used by SDK for task polling.
    """
    queue = get_queue()

    # Split capabilities
    capability_list = [c.strip() for c in capabilities.split(",")]

    # Try each capability
    for capability in capability_list:
        task = await queue.get_next_task(capability)

        if task:
            return {
                "task_id": str(task.task_id),
                "capability": task.capability,
                "input": task.input.data,
                "timeout_seconds": task.timeout_seconds,
                "assigned_agent_id": str(task.assigned_agent_id),
            }

    # No tasks available
    return Response(status_code=204)


@app.post("/api/v2/tasks/{task_id}/result", tags=["tasks"])
async def submit_task_result(
    task_id: UUID,
    status: str,
    output: Optional[dict] = None,
    error: Optional[str] = None,
    cost: Optional[float] = None,
    user: dict = Depends(verify_api_key)
):
    """Submit task result (completion or failure)."""
    queue = get_queue()

    if status == "completed":
        if not output:
            raise HTTPException(status_code=400, detail="Output required for completed task")

        await queue.complete_task(task_id, output, cost)

        return {"status": "completed", "task_id": str(task_id)}

    elif status == "failed":
        if not error:
            raise HTTPException(status_code=400, detail="Error message required for failed task")

        await queue.fail_task(task_id, error)

        return {"status": "failed", "task_id": str(task_id)}

    else:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")


# ============================================================================
# LLM Proxy Endpoint (V2 - Using core/llm)
# ============================================================================

@app.post("/api/v2/llm/completions", tags=["gateway"])
@track_request(service="agent-orchestration", endpoint="/api/v2/llm/completions")
async def llm_completion(
    agent_id: UUID,
    provider: str,
    model: str,
    messages: List[dict],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    task_id: Optional[UUID] = None,
    user: dict = Depends(verify_agent_access)
):
    """
    Proxy LLM request through gateway with cost tracking.

    Uses core/llm module for unified LLM routing.
    """
    gateway = get_gateway()

    try:
        response = await gateway.proxy_request(
            agent_id=agent_id,
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            task_id=task_id,
        )

        return {
            "content": response.content,
            "finish_reason": response.finish_reason,
            "usage": {
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens,
            },
            "cost": response.estimated_cost,
            "latency_ms": response.latency_ms,
            "note": "LLM routing handled by core/llm module"
        }

    except ValueError as e:
        # Cost limit exceeded
        raise HTTPException(status_code=429, detail=str(e))
    except RuntimeError as e:
        # LLM request failed
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Metrics Endpoints (V2 - Using core/monitoring)
# ============================================================================

@app.get("/api/v2/metrics/system", tags=["metrics"])
async def get_system_metrics(user: dict = Depends(verify_api_key)):
    """Get comprehensive system metrics."""
    collector = get_collector()
    return await collector.collect_metrics()


@app.get("/api/v2/metrics/capabilities/{capability}", tags=["metrics"])
async def get_capability_metrics(
    capability: str,
    user: dict = Depends(verify_api_key)
):
    """Get detailed metrics for a specific capability."""
    collector = get_collector()
    return await collector.get_capability_metrics(capability)


@app.get("/api/v2/metrics/agents/{agent_id}", tags=["metrics"])
async def get_agent_performance_metrics(
    agent_id: UUID,
    user: dict = Depends(verify_agent_access)
):
    """Get detailed performance metrics for an agent."""
    collector = get_collector()
    metrics = await collector.get_agent_performance(agent_id)

    if not metrics:
        raise HTTPException(status_code=404, detail="Agent not found")

    return metrics


# ============================================================================
# Alert Endpoints (V2)
# ============================================================================

@app.get("/api/v2/alerts", tags=["alerts"])
async def get_alerts(
    severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    user: dict = Depends(verify_api_key)
):
    """Get active alerts with optional filtering."""
    alert_manager = get_alert_manager()

    alerts = alert_manager.get_active_alerts(
        severity=severity,
        alert_type=alert_type
    )

    return {
        "alerts": [alert.to_dict() for alert in alerts],
        "total": len(alerts)
    }


@app.get("/api/v2/alerts/history", tags=["alerts"])
async def get_alert_history(
    hours: int = 24,
    severity: Optional[str] = None,
    user: dict = Depends(verify_api_key)
):
    """Get alert history."""
    alert_manager = get_alert_manager()

    alerts = alert_manager.get_alert_history(hours=hours, severity=severity)

    return {
        "alerts": [alert.to_dict() for alert in alerts],
        "total": len(alerts)
    }


@app.post("/api/v2/alerts/{alert_id}/acknowledge", tags=["alerts"])
async def acknowledge_alert(
    alert_id: UUID,
    user: dict = Depends(verify_api_key)
):
    """Acknowledge an alert."""
    alert_manager = get_alert_manager()

    success = await alert_manager.acknowledge_alert(alert_id)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "acknowledged", "alert_id": str(alert_id)}


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main_v2:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
