# Multi-LLM Intelligent Routing System

> **CONFIDENTIAL - INTERNAL USE ONLY**
>
> This document describes our proprietary LLM routing algorithms.

## Overview

The Multi-LLM Routing System is one of our primary competitive advantages. It enables:
- Automatic model selection based on task requirements
- Cost optimization across 7+ providers
- Latency-aware routing with geographic considerations
- Seamless failover without customer code changes

## Routing Algorithm

### Decision Tree

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Request Incoming                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Check Organization Routing Config                            │
│    - Custom model preferences?                                  │
│    - Budget constraints?                                        │
│    - Latency requirements?                                      │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Analyze Request Requirements                                 │
│    - Token limit needed (context window)                        │
│    - Capability requirements (vision, function calling, etc.)   │
│    - Response format (JSON mode, streaming)                     │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Filter Eligible Models                                       │
│    - Meets capability requirements                              │
│    - Within cost threshold                                      │
│    - Provider is healthy (circuit breaker open)                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Score & Rank Models                                          │
│    score = w1*cost_score + w2*latency_score + w3*quality_score  │
│    + w4*reliability_score                                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Execute with Fallback Chain                                  │
│    Primary → Secondary → Tertiary                               │
└─────────────────────────────────────────────────────────────────┘
```

### Scoring Weights (Configurable per Organization)

```python
DEFAULT_ROUTING_WEIGHTS = {
    "cost": 0.30,        # Lower cost = higher score
    "latency": 0.25,     # Lower latency = higher score
    "quality": 0.30,     # Based on benchmark scores
    "reliability": 0.15  # Based on uptime history
}
```

### Capability Matrix

We maintain a capability matrix for all models:

```python
MODEL_CAPABILITIES = {
    "gpt-4o": {
        "vision": True,
        "function_calling": True,
        "json_mode": True,
        "streaming": True,
        "max_tokens": 128000,
        "output_max": 16384,
    },
    "claude-4.5-sonnet": {
        "vision": True,
        "function_calling": True,
        "json_mode": True,
        "streaming": True,
        "max_tokens": 200000,
        "output_max": 8192,
    },
    # ... etc
}
```

## Fallback Strategy

### Circuit Breaker Pattern

Each provider has a circuit breaker:

```python
class ProviderCircuitBreaker:
    """
    States: CLOSED (healthy) → OPEN (unhealthy) → HALF_OPEN (testing)

    Transitions:
    - CLOSED → OPEN: After 5 failures in 60 seconds
    - OPEN → HALF_OPEN: After 30 second cooldown
    - HALF_OPEN → CLOSED: After 3 successful requests
    - HALF_OPEN → OPEN: After 1 failure
    """

    FAILURE_THRESHOLD = 5
    FAILURE_WINDOW_SECONDS = 60
    COOLDOWN_SECONDS = 30
    SUCCESS_THRESHOLD = 3
```

### Fallback Chain Construction

```python
def build_fallback_chain(request: LLMRequest) -> List[ModelConfig]:
    """
    Build ordered list of models to try.

    Strategy:
    1. Primary: Best scoring model that meets requirements
    2. Secondary: Different provider, similar capability
    3. Tertiary: Fallback to most reliable model
    """
    eligible = filter_eligible_models(request)
    ranked = score_and_rank(eligible, request.org_config)

    # Ensure provider diversity in chain
    chain = []
    seen_providers = set()

    for model in ranked:
        if model.provider not in seen_providers:
            chain.append(model)
            seen_providers.add(model.provider)
        if len(chain) >= 3:
            break

    return chain
```

## Cost Optimization Strategies

### Strategy 1: Model Downsizing

For simple tasks, automatically route to cheaper models:

```python
def should_downsize(request: LLMRequest) -> bool:
    """
    Heuristics for downsizing:
    - Short prompt (<1000 tokens)
    - No vision/function calling needed
    - Classification or extraction task
    """
    if request.estimated_input_tokens < 1000:
        if not request.requires_vision:
            if request.task_type in ["classification", "extraction"]:
                return True
    return False
```

### Strategy 2: Batch Routing

Accumulate similar requests and route to batch-optimized endpoints:

```python
BATCH_PROVIDERS = {
    "anthropic": {"endpoint": "/v1/messages/batches", "discount": 0.50},
    "openai": {"endpoint": "/v1/batches", "discount": 0.50},
}
```

### Strategy 3: Caching Layer

Semantic cache for repeated queries:

```python
class SemanticCache:
    """
    Cache LLM responses based on semantic similarity.

    - Embedding-based lookup
    - TTL: 24 hours default
    - Organization-scoped
    """
    SIMILARITY_THRESHOLD = 0.95
```

## Implementation Files

| Component | Location |
|-----------|----------|
| Router Core | `backend/llm/router.py` |
| Model Registry | `backend/llm/models.py` |
| Circuit Breaker | `backend/llm/circuit_breaker.py` |
| Cost Calculator | `backend/shared/llm_pricing.py` |
| Capability Matrix | `backend/llm/capabilities.py` |

## Metrics & Monitoring

Track these metrics per organization:

```python
ROUTING_METRICS = [
    "routing_decision_latency_ms",
    "model_selection_distribution",
    "fallback_trigger_rate",
    "cost_savings_vs_default",
    "circuit_breaker_open_count",
]
```

## Configuration API (Internal Only)

```http
# Update routing weights for organization
PUT /internal/api/v1/routing/config/{org_id}
{
    "weights": {"cost": 0.5, "latency": 0.2, "quality": 0.2, "reliability": 0.1},
    "preferred_providers": ["anthropic", "openai"],
    "blocked_models": ["gpt-3.5-turbo"],
    "max_cost_per_request": 0.10
}

# Get routing analytics
GET /internal/api/v1/routing/analytics/{org_id}?period=7d
```
