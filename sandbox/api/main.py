"""
Sandbox API - Demo Environment for AgentOrch

A fully functional sandbox API that provides:
- Rate-limited demo API keys
- Mock LLM responses (no actual API costs)
- Pre-built demo workflows
- Full API compatibility with production

This powers:
- Interactive website demos
- SDK playground
- Investor demonstrations
- Documentation examples
"""

import sys
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import sandbox components
from .rate_limiter import get_rate_limiter, RateLimiter
from .demo_keys import get_demo_key_manager, DemoKeyManager, KeyTier
from ..mock.llm_mock import get_mock_provider, MockLLMProvider
from ..mock.integration_mock import get_mock_integration_provider, MockIntegrationProvider
from ..workflows import get_demo_workflows, DemoWorkflow


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateKeyRequest(BaseModel):
    """Request to create a demo API key."""
    tier: str = "demo"
    ttl_hours: int = 24
    metadata: Optional[Dict[str, Any]] = None


class CreateKeyResponse(BaseModel):
    """Response with new demo API key."""
    api_key: str
    key_id: str
    tier: str
    expires_at: str
    limits: Dict[str, Any]


class LLMChatRequest(BaseModel):
    """Request for LLM chat completion."""
    messages: List[Dict[str, str]]
    model: str = "gpt-4"
    provider: str = "openai"
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class LLMChatResponse(BaseModel):
    """Response from LLM chat completion."""
    content: str
    model: str
    provider: str
    usage: Dict[str, int]
    cost: float
    latency_ms: int
    sandbox: bool = True


class WorkflowExecuteRequest(BaseModel):
    """Request to execute a workflow."""
    inputs: Dict[str, Any]
    workflow_id: Optional[str] = None


class WorkflowExecuteResponse(BaseModel):
    """Response from workflow execution."""
    execution_id: str
    workflow_id: str
    status: str
    outputs: Dict[str, Any]
    steps: List[Dict[str, Any]]
    cost: float
    duration_ms: int
    sandbox: bool = True


class IntegrationRequest(BaseModel):
    """Request to execute an integration action."""
    integration: str
    action: str
    params: Optional[Dict[str, Any]] = None


class IntegrationResponse(BaseModel):
    """Response from integration execution."""
    integration: str
    action: str
    success: bool
    data: Dict[str, Any]
    latency_ms: int
    sandbox: bool = True


# ============================================================================
# Dependencies
# ============================================================================

async def verify_demo_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Verify demo API key and check rate limits."""
    # Extract key from header
    api_key = x_api_key
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Use X-API-Key header or Bearer token.",
        )

    # Validate key
    key_manager = get_demo_key_manager()
    demo_key = key_manager.validate_key(api_key)

    if not demo_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key.",
        )

    # Check rate limit
    rate_limiter = get_rate_limiter()
    allowed, error, retry_after = rate_limiter.check_rate_limit(
        api_key,
        tier=demo_key.tier.value,
    )

    if not allowed:
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=429,
            detail=error,
            headers=headers,
        )

    return {
        "api_key": api_key,
        "key_id": demo_key.key_id,
        "tier": demo_key.tier.value,
    }


# ============================================================================
# Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize sandbox services."""
    print("🎮 Starting AgentOrch Sandbox API...")

    # Initialize services
    key_manager = get_demo_key_manager()
    rate_limiter = get_rate_limiter()
    llm_provider = get_mock_provider()
    integration_provider = get_mock_integration_provider()

    print(f"   Demo keys initialized: {len(key_manager.list_keys())}")
    print("   Mock LLM provider: ready")
    print("   Mock integrations: ready")
    print("✅ Sandbox ready\n")

    yield

    print("\n🛑 Shutting down sandbox...")


# ============================================================================
# Create App
# ============================================================================

app = FastAPI(
    title="AgentOrch Sandbox API",
    description="""
    **Interactive Sandbox for AgentOrch Platform**

    This is a fully functional sandbox environment that mirrors the production API.
    Use it to:

    - Test the SDK without incurring costs
    - Explore platform features interactively
    - Run demos for customers or investors
    - Develop integrations before going to production

    ## Features

    All features work identically to production, with these sandbox-specific behaviors:

    - **LLM Responses**: Realistic mock responses (no actual API calls)
    - **Integrations**: Simulated external services (Slack, Salesforce, etc.)
    - **Cost Tracking**: Accurate cost simulation
    - **Rate Limiting**: Demo-appropriate limits

    ## Demo API Keys

    Use these predefined keys for testing:

    - `demo-key-xxx` - Standard demo tier
    - `playground-key-xxx` - Playground tier (more limited)
    - `investor-demo-key` - Investor demo tier (higher limits)

    Or generate a temporary key via `POST /sandbox/keys`.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for sandbox
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router for modular inclusion
from fastapi import APIRouter
router = APIRouter(prefix="/sandbox", tags=["sandbox"])


# ============================================================================
# API Key Management
# ============================================================================

@router.post("/keys", response_model=CreateKeyResponse)
async def create_demo_key(request: CreateKeyRequest):
    """
    Create a new demo API key.

    Keys expire after the specified TTL (default: 24 hours).
    """
    key_manager = get_demo_key_manager()
    rate_limiter = get_rate_limiter()

    try:
        tier = KeyTier(request.tier)
    except ValueError:
        tier = KeyTier.DEMO

    raw_key, demo_key = key_manager.create_key(
        tier=tier,
        ttl_hours=request.ttl_hours,
        metadata=request.metadata,
    )

    return CreateKeyResponse(
        api_key=raw_key,
        key_id=demo_key.key_id,
        tier=demo_key.tier.value,
        expires_at=demo_key.expires_at.isoformat(),
        limits=rate_limiter.get_limits(demo_key.tier.value),
    )


@router.get("/keys/info")
async def get_key_info(auth: Dict = Depends(verify_demo_key)):
    """Get information about the current API key."""
    key_manager = get_demo_key_manager()
    rate_limiter = get_rate_limiter()

    return {
        "key_id": auth["key_id"],
        "tier": auth["tier"],
        "limits": rate_limiter.get_limits(auth["tier"]),
        "usage": rate_limiter.get_usage(auth["api_key"]),
    }


# ============================================================================
# LLM Endpoints
# ============================================================================

@router.post("/v1/llm/chat", response_model=LLMChatResponse)
async def llm_chat(
    request: LLMChatRequest,
    auth: Dict = Depends(verify_demo_key),
):
    """
    Send a chat completion request.

    Returns realistic mock responses without actual LLM API calls.
    Simulates costs and latency accurately.
    """
    llm_provider = get_mock_provider()
    rate_limiter = get_rate_limiter()

    # Execute mock LLM call
    response = await llm_provider.complete(
        messages=request.messages,
        model=request.model,
        provider=request.provider,
    )

    # Record usage
    rate_limiter.record_usage(
        auth["api_key"],
        tokens=response.total_tokens,
        cost=response.cost,
    )

    return LLMChatResponse(
        content=response.content,
        model=response.model,
        provider=response.provider,
        usage={
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
        },
        cost=response.cost,
        latency_ms=response.latency_ms,
        sandbox=True,
    )


# ============================================================================
# Workflow Endpoints
# ============================================================================

@router.get("/v1/workflows")
async def list_workflows(auth: Dict = Depends(verify_demo_key)):
    """List available demo workflows."""
    workflows = get_demo_workflows()
    return {
        "workflows": [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "category": w.category,
                "steps": len(w.steps),
                "estimated_cost": w.estimated_cost,
            }
            for w in workflows
        ],
        "total": len(workflows),
    }


@router.get("/v1/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    auth: Dict = Depends(verify_demo_key),
):
    """Get workflow details."""
    workflows = get_demo_workflows()

    for w in workflows:
        if w.id == workflow_id:
            return w.to_dict()

    raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/v1/workflows/{workflow_id}/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    auth: Dict = Depends(verify_demo_key),
):
    """
    Execute a demo workflow.

    Runs through all workflow steps using mock services.
    Returns full execution trace with costs.
    """
    workflows = get_demo_workflows()
    llm_provider = get_mock_provider()
    integration_provider = get_mock_integration_provider()
    rate_limiter = get_rate_limiter()

    # Find workflow
    workflow = None
    for w in workflows:
        if w.id == workflow_id:
            workflow = w
            break

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Execute workflow
    execution_id = str(uuid4())
    start_time = datetime.utcnow()
    total_cost = 0.0
    steps_result = []
    current_state = dict(request.inputs)

    for i, step in enumerate(workflow.steps):
        step_start = datetime.utcnow()

        if step["type"] == "llm":
            # Execute LLM step
            messages = [
                {"role": "system", "content": step.get("system_prompt", "You are a helpful assistant.")},
                {"role": "user", "content": step.get("prompt", "").format(**current_state)},
            ]
            llm_response = await llm_provider.complete(
                messages=messages,
                model=step.get("model", "gpt-4"),
                provider=step.get("provider", "openai"),
                scenario=step.get("scenario"),
                variant=step.get("variant"),
            )
            current_state[step["name"]] = llm_response.content
            total_cost += llm_response.cost

            steps_result.append({
                "index": i,
                "name": step["name"],
                "type": "llm",
                "status": "completed",
                "input": messages,
                "output": llm_response.content,
                "cost": llm_response.cost,
                "duration_ms": llm_response.latency_ms,
                "model": llm_response.model,
            })

        elif step["type"] == "integration":
            # Execute integration step
            int_response = await integration_provider.execute(
                integration=step.get("connector", step.get("integration")),
                action=step.get("action"),
                params=step.get("params", {}),
            )

            current_state[step["name"]] = int_response.data

            steps_result.append({
                "index": i,
                "name": step["name"],
                "type": "integration",
                "status": "completed" if int_response.success else "failed",
                "integration": int_response.integration,
                "action": int_response.action,
                "output": int_response.data,
                "duration_ms": int_response.latency_ms,
            })

        elif step["type"] == "conditional":
            # Evaluate condition (simplified)
            condition = step.get("condition", "true")
            result = True  # Simplified for demo

            steps_result.append({
                "index": i,
                "name": step["name"],
                "type": "conditional",
                "status": "completed",
                "condition": condition,
                "result": result,
            })

        else:
            # Generic step
            steps_result.append({
                "index": i,
                "name": step.get("name", f"step_{i}"),
                "type": step["type"],
                "status": "completed",
            })

    end_time = datetime.utcnow()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    # Record usage
    rate_limiter.record_usage(
        auth["api_key"],
        tokens=0,
        cost=total_cost,
    )

    return WorkflowExecuteResponse(
        execution_id=execution_id,
        workflow_id=workflow_id,
        status="completed",
        outputs=current_state,
        steps=steps_result,
        cost=total_cost,
        duration_ms=duration_ms,
        sandbox=True,
    )


# ============================================================================
# Time-Travel Debugging
# ============================================================================

@router.get("/v1/executions/{execution_id}/time-travel/{step_index}")
async def time_travel(
    execution_id: str,
    step_index: int,
    auth: Dict = Depends(verify_demo_key),
):
    """
    Get state snapshot at a specific step.

    Demonstrates time-travel debugging capability.
    """
    # For sandbox, return mock time-travel data
    return {
        "execution_id": execution_id,
        "step_index": step_index,
        "step": {
            "name": f"Step {step_index}",
            "type": "llm" if step_index % 2 == 0 else "integration",
            "status": "completed",
        },
        "state_at_step": {
            "input": {"ticket": "Sample input data"},
            "accumulated_outputs": {f"step_{i}": f"Output from step {i}" for i in range(step_index)},
        },
        "cost_so_far": 0.003 * step_index,
        "tokens_so_far": 150 * step_index,
        "duration_so_far_ms": 200 * step_index,
        "sandbox": True,
    }


# ============================================================================
# Integration Endpoints
# ============================================================================

@router.get("/v1/integrations")
async def list_integrations(auth: Dict = Depends(verify_demo_key)):
    """List available mock integrations."""
    integration_provider = get_mock_integration_provider()
    return {
        "integrations": integration_provider.get_supported_integrations(),
        "note": "All integrations are simulated in sandbox mode",
    }


@router.post("/v1/integrations/execute", response_model=IntegrationResponse)
async def execute_integration(
    request: IntegrationRequest,
    auth: Dict = Depends(verify_demo_key),
):
    """Execute a mock integration action."""
    integration_provider = get_mock_integration_provider()

    result = await integration_provider.execute(
        integration=request.integration,
        action=request.action,
        params=request.params,
    )

    return IntegrationResponse(
        integration=result.integration,
        action=result.action,
        success=result.success,
        data=result.data,
        latency_ms=result.latency_ms,
        sandbox=True,
    )


# ============================================================================
# Cost Endpoints
# ============================================================================

@router.get("/v1/costs")
async def get_costs(auth: Dict = Depends(verify_demo_key)):
    """Get mock cost data."""
    llm_provider = get_mock_provider()
    rate_limiter = get_rate_limiter()

    llm_stats = llm_provider.get_usage_stats()
    usage = rate_limiter.get_usage(auth["api_key"])

    return {
        "session": {
            "total_cost": llm_stats["total_cost"],
            "total_tokens": llm_stats["total_tokens"],
            "total_calls": llm_stats["total_calls"],
            "by_provider": llm_stats.get("by_provider", {}),
            "by_model": llm_stats.get("by_model", {}),
        },
        "today": {
            "requests": usage["requests_today"],
            "tokens": usage["tokens_today"],
            "cost": usage["cost_today"],
        },
        "limits": rate_limiter.get_limits(auth["tier"]),
        "sandbox": True,
    }


# ============================================================================
# Health & Info
# ============================================================================

@router.get("/health")
async def health():
    """Health check for sandbox API."""
    return {
        "status": "healthy",
        "service": "sandbox",
        "version": "1.0.0",
        "features": [
            "mock_llm",
            "mock_integrations",
            "demo_workflows",
            "time_travel",
            "cost_tracking",
        ],
    }


@router.get("/info")
async def info():
    """Get sandbox information."""
    key_manager = get_demo_key_manager()
    return {
        "name": "AgentOrch Sandbox",
        "version": "1.0.0",
        "description": "Interactive sandbox environment for AgentOrch platform",
        "demo_keys": {
            "playground": "playground-key-xxx",
            "demo": "demo-key-xxx",
            "investor": "investor-demo-key",
        },
        "capabilities": [
            "LLM chat completions (mock)",
            "Workflow execution",
            "Time-travel debugging",
            "Integration simulation",
            "Cost tracking",
        ],
        "stats": key_manager.get_stats(),
    }


# Include router in app
app.include_router(router)


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,  # Different port from main API
        log_level="info",
    )
