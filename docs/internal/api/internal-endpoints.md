# Internal API Endpoints

> **CONFIDENTIAL - INTERNAL USE ONLY**
>
> These endpoints are not exposed publicly and should never be documented externally.

## Overview

Internal APIs are prefixed with `/internal/api/v1/` and require admin authentication.

## Authentication

```http
Authorization: Bearer <internal_admin_token>
X-Internal-Service: <service_name>
```

Internal tokens are issued only to:
- Platform admin users
- Internal microservices
- Background job workers

---

## Routing Management

### Get Routing Config for Organization

```http
GET /internal/api/v1/routing/config/{org_id}
```

Response:
```json
{
    "org_id": "org-123",
    "weights": {
        "cost": 0.3,
        "latency": 0.25,
        "quality": 0.3,
        "reliability": 0.15
    },
    "preferred_providers": ["anthropic", "openai"],
    "blocked_models": [],
    "max_cost_per_request": null,
    "fallback_chain_length": 3
}
```

### Update Routing Config

```http
PUT /internal/api/v1/routing/config/{org_id}
Content-Type: application/json

{
    "weights": {
        "cost": 0.5,
        "latency": 0.2,
        "quality": 0.2,
        "reliability": 0.1
    },
    "preferred_providers": ["anthropic"],
    "max_cost_per_request": 0.50
}
```

### Get Routing Analytics

```http
GET /internal/api/v1/routing/analytics/{org_id}?period=7d
```

Response:
```json
{
    "period": "7d",
    "total_requests": 15234,
    "model_distribution": {
        "claude-4.5-sonnet": 8234,
        "gpt-4o": 5123,
        "gemini-2.0-flash": 1877
    },
    "provider_distribution": {
        "anthropic": 8234,
        "openai": 5123,
        "google": 1877
    },
    "fallback_rate": 0.023,
    "avg_routing_latency_ms": 3.2,
    "estimated_cost_savings": 234.56
}
```

---

## Circuit Breaker Management

### Get Provider Health Status

```http
GET /internal/api/v1/providers/health
```

Response:
```json
{
    "providers": {
        "openai": {
            "status": "healthy",
            "circuit_state": "CLOSED",
            "last_failure": null,
            "success_rate_1h": 0.998
        },
        "anthropic": {
            "status": "healthy",
            "circuit_state": "CLOSED",
            "last_failure": "2026-01-12T10:23:45Z",
            "success_rate_1h": 0.995
        },
        "google": {
            "status": "degraded",
            "circuit_state": "HALF_OPEN",
            "last_failure": "2026-01-12T14:02:33Z",
            "success_rate_1h": 0.892
        }
    }
}
```

### Force Circuit Breaker State

```http
POST /internal/api/v1/providers/{provider}/circuit-breaker
Content-Type: application/json

{
    "action": "reset",  // or "open", "close"
    "reason": "Manual intervention after provider recovery"
}
```

---

## Token Ledger (Raw Access)

### Query Token Usage (Detailed)

```http
GET /internal/api/v1/tokens/ledger
Query Parameters:
  - org_id: required
  - start_date: ISO 8601
  - end_date: ISO 8601
  - provider: optional filter
  - model: optional filter
  - execution_id: optional filter
```

Response:
```json
{
    "entries": [
        {
            "id": 12345,
            "org_id": "org-123",
            "execution_id": "exec-456",
            "provider": "anthropic",
            "model": "claude-4.5-sonnet",
            "input_tokens": 1523,
            "output_tokens": 892,
            "timestamp": "2026-01-12T14:30:00Z",
            "request_id": "req-789",
            "cached": false
        }
    ],
    "total": 1,
    "aggregates": {
        "total_input_tokens": 1523,
        "total_output_tokens": 892
    }
}
```

### Reconciliation Export

```http
GET /internal/api/v1/tokens/export/{org_id}
Query Parameters:
  - format: csv | json
  - start_date: required
  - end_date: required
```

Returns downloadable file with all token entries for billing reconciliation.

---

## Organization Management

### Get Full Organization Details

```http
GET /internal/api/v1/organizations/{org_id}/full
```

Response includes:
- All settings
- All OAuth configs
- All webhook configs
- Usage quotas
- Billing status

### Override Organization Limits

```http
PUT /internal/api/v1/organizations/{org_id}/limits
Content-Type: application/json

{
    "max_tokens_per_day": 10000000,
    "max_executions_per_day": 50000,
    "max_concurrent_executions": 100,
    "rate_limit_rpm": 1000
}
```

---

## Execution Debugging (Time Travel)

### Get Full Execution State

```http
GET /internal/api/v1/executions/{execution_id}/state
```

Response:
```json
{
    "execution_id": "exec-123",
    "workflow_id": "wf-456",
    "full_state": {
        "steps": {
            "step-1": {
                "input": {...},
                "output": {...},
                "llm_requests": [...],
                "duration_ms": 1234,
                "token_usage": {...}
            }
        },
        "variables": {...},
        "context": {...}
    },
    "replayable": true
}
```

### Replay From Step

```http
POST /internal/api/v1/executions/{execution_id}/replay
Content-Type: application/json

{
    "from_step": "step-3",
    "modified_input": {...},
    "dry_run": true
}
```

---

## A/B Testing (Internal Management)

### Create Experiment

```http
POST /internal/api/v1/experiments
Content-Type: application/json

{
    "name": "Claude vs GPT for summarization",
    "workflow_id": "wf-123",
    "variants": [
        {
            "name": "control",
            "weight": 50,
            "config": {"model": "gpt-4o"}
        },
        {
            "name": "treatment",
            "weight": 50,
            "config": {"model": "claude-4.5-sonnet"}
        }
    ],
    "metrics": ["latency", "cost", "user_rating"],
    "traffic_percentage": 10
}
```

### Get Experiment Results

```http
GET /internal/api/v1/experiments/{experiment_id}/results
```

Response:
```json
{
    "experiment_id": "exp-123",
    "status": "running",
    "sample_size": 5234,
    "results": {
        "control": {
            "avg_latency_ms": 1234,
            "avg_cost": 0.023,
            "avg_user_rating": 4.2
        },
        "treatment": {
            "avg_latency_ms": 987,
            "avg_cost": 0.019,
            "avg_user_rating": 4.5
        }
    },
    "statistical_significance": {
        "latency": 0.95,
        "cost": 0.87,
        "user_rating": 0.92
    }
}
```

---

## System Health

### Get System Metrics

```http
GET /internal/api/v1/system/metrics
```

### Force Cache Invalidation

```http
POST /internal/api/v1/system/cache/invalidate
Content-Type: application/json

{
    "cache_type": "routing_decisions",  // or "model_capabilities", "pricing"
    "org_id": null  // null for global
}
```

### Get Background Job Status

```http
GET /internal/api/v1/system/jobs
```
