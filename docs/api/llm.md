# LLM Routing API

The LLM Routing API provides intelligent multi-provider LLM routing with automatic failover, cost optimization, and A/B testing.

## Base URL

```
/api/v1/llm
```

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/providers` | Register LLM provider |
| `GET` | `/providers` | List providers |
| `GET` | `/providers/{id}` | Get provider details |
| `GET` | `/providers/available` | Supported providers |
| `POST` | `/models` | Register model |
| `GET` | `/models` | List models |
| `GET` | `/models/{id}` | Get model details |
| `POST` | `/route` | Get routing recommendation |
| `POST` | `/requests` | Log LLM request |
| `GET` | `/analytics` | Cost analytics |
| `POST` | `/compare` | Create A/B test |
| `POST` | `/compare/{id}/execute` | Run comparison |
| `GET` | `/recommendations` | Model recommendations |

---

## Supported Providers

| Provider | Models | Capabilities |
|----------|--------|--------------|
| **OpenAI** | GPT-4, GPT-4 Turbo, GPT-3.5 Turbo | Chat, Code, Vision, JSON |
| **Anthropic** | Claude 3 Opus, Sonnet, Haiku | Chat, Code, Analysis |
| **DeepSeek** | DeepSeek V3, DeepSeek R1 | Chat, Code, Reasoning |
| **Google** | Gemini Pro, Gemini Ultra | Chat, Vision, Code |
| **Mistral** | Mistral Large, Medium, Small | Chat, Code |
| **Cohere** | Command, Command Light | Chat, Embeddings |

---

## Register Provider

Add a new LLM provider configuration.

```
POST /api/v1/llm/providers
```

### Request Body

```json
{
  "provider": "openai",
  "api_key": "sk-...",
  "api_base_url": "https://api.openai.com/v1",
  "is_default": false,
  "rate_limit_rpm": 10000,
  "rate_limit_tpm": 1000000,
  "priority": 1,
  "tags": ["production", "primary"]
}
```

### Response

```json
{
  "id": 1,
  "provider": "openai",
  "is_active": true,
  "is_default": false,
  "rate_limit_rpm": 10000,
  "rate_limit_tpm": 1000000,
  "priority": 1,
  "created_at": "2025-12-26T10:00:00Z"
}
```

---

## Register Model

Add a model configuration with pricing.

```
POST /api/v1/llm/models
```

### Request Body

```json
{
  "provider_id": 1,
  "model_id": "gpt-4-turbo",
  "display_name": "GPT-4 Turbo",
  "input_price_per_1k": 0.01,
  "output_price_per_1k": 0.03,
  "context_window": 128000,
  "max_output_tokens": 4096,
  "supports_vision": true,
  "supports_function_calling": true,
  "supports_json_mode": true,
  "capabilities": ["code", "reasoning", "vision"]
}
```

### Response

```json
{
  "id": 1,
  "model_id": "gpt-4-turbo",
  "display_name": "GPT-4 Turbo",
  "provider": "openai",
  "input_price_per_1k": 0.01,
  "output_price_per_1k": 0.03,
  "context_window": 128000,
  "is_active": true,
  "avg_latency_ms": null,
  "total_requests": 0
}
```

---

## Intelligent Routing

Get the best model for your request based on strategy and constraints.

```
POST /api/v1/llm/route
```

### Request Body

```json
{
  "task_type": "code_generation",
  "prompt_tokens_estimate": 500,
  "max_output_tokens": 2000,
  "routing_strategy": "cost_optimized",
  "constraints": {
    "max_latency_ms": 5000,
    "max_cost": 0.10,
    "required_capabilities": ["code", "function_calling"],
    "excluded_providers": ["anthropic"]
  },
  "fallback_enabled": true
}
```

### Routing Strategies

| Strategy | Description |
|----------|-------------|
| `cost_optimized` | Cheapest model meeting requirements |
| `quality_optimized` | Best quality model |
| `latency_optimized` | Fastest response time |
| `balanced` | Balance of cost and quality |
| `round_robin` | Distribute across providers |
| `weighted` | Weighted distribution |

### Response

```json
{
  "recommended_model_id": 1,
  "model_name": "gpt-4-turbo",
  "provider": "openai",
  "estimated_cost": 0.065,
  "estimated_latency_ms": 2500,
  "confidence_score": 0.92,
  "reasoning": "Best cost/quality ratio for code generation",
  "fallback_model_id": 3,
  "fallback_model_name": "claude-3-sonnet"
}
```

---

## Log LLM Request

Record usage for cost tracking and analytics.

```
POST /api/v1/llm/requests
```

### Request Body

```json
{
  "model_id": 1,
  "input_tokens": 450,
  "output_tokens": 1200,
  "latency_ms": 2340,
  "success": true,
  "task_type": "code_generation",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_id": "wf_abc123",
  "metadata": {
    "prompt_version": "v2.1"
  }
}
```

### Response

```json
{
  "request_id": 12345,
  "total_cost": 0.0495,
  "total_tokens": 1650
}
```

---

## Proxy Endpoint

Route LLM requests through the gateway with automatic cost tracking.

```
POST /api/v1/llm/completions
```

### Request Body

```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "provider": "openai",
  "model": "gpt-4-turbo",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Write a Python function to sort a list."}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "task_id": "task_xyz"
}
```

### Response

```json
{
  "content": "Here's a Python function to sort a list:\n\n```python\ndef sort_list(items):\n    return sorted(items)\n```",
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 120,
    "total_tokens": 165
  },
  "cost": 0.0051,
  "latency_ms": 1850
}
```

---

## Cost Analytics

Get aggregated cost and usage analytics.

```
GET /api/v1/llm/analytics
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | datetime | Start of period |
| `end_date` | datetime | End of period |

### Response

```json
{
  "period": {
    "start": "2025-12-01T00:00:00Z",
    "end": "2025-12-26T23:59:59Z"
  },
  "total_cost": 1250.45,
  "total_requests": 45000,
  "total_tokens": {
    "input": 12500000,
    "output": 8750000
  },
  "by_provider": {
    "openai": {"cost": 800.25, "requests": 25000},
    "anthropic": {"cost": 350.20, "requests": 15000},
    "deepseek": {"cost": 100.00, "requests": 5000}
  },
  "by_model": {
    "gpt-4-turbo": {"cost": 650.00, "requests": 18000},
    "gpt-3.5-turbo": {"cost": 150.25, "requests": 7000},
    "claude-3-sonnet": {"cost": 350.20, "requests": 15000}
  },
  "avg_latency_ms": 1850,
  "avg_cost_per_request": 0.028,
  "success_rate": 99.2
}
```

---

## A/B Testing

Compare two models head-to-head.

### Create Comparison

```
POST /api/v1/llm/compare
```

```json
{
  "name": "GPT-4 vs Claude Comparison",
  "model_a_id": 1,
  "model_b_id": 3,
  "test_cases": [
    {
      "prompt": "Write a function to calculate fibonacci numbers",
      "expected_capabilities": ["code"]
    },
    {
      "prompt": "Explain quantum computing to a 10-year-old",
      "expected_capabilities": ["explanation"]
    }
  ],
  "evaluation_criteria": ["quality", "latency", "cost"]
}
```

### Execute Comparison

```
POST /api/v1/llm/compare/{comparison_id}/execute
```

### Response

```json
{
  "id": 1,
  "name": "GPT-4 vs Claude Comparison",
  "status": "completed",
  "model_a": {"name": "gpt-4-turbo", "score": 8.5},
  "model_b": {"name": "claude-3-sonnet", "score": 8.2},
  "winner": "gpt-4-turbo",
  "results": {
    "quality": {"model_a": 9.0, "model_b": 8.5},
    "latency_ms": {"model_a": 2100, "model_b": 1800},
    "cost": {"model_a": 0.045, "model_b": 0.032}
  },
  "recommendation": "GPT-4 Turbo provides slightly better quality at ~40% higher cost. Choose based on budget constraints."
}
```

---

## Model Recommendations

Get recommended models for a task type.

```
GET /api/v1/llm/recommendations?task_type=code
```

### Task Types

| Type | Description |
|------|-------------|
| `code` | Code generation and review |
| `vision` | Image analysis |
| `reasoning` | Complex reasoning tasks |
| `json` | Structured output |
| `chat` | General conversation |
| `embedding` | Text embeddings |

### Response

```json
[
  {
    "id": 1,
    "model_id": "gpt-4-turbo",
    "display_name": "GPT-4 Turbo",
    "provider": "openai",
    "recommendation_score": 0.95,
    "avg_latency_ms": 2100,
    "cost_per_1k_tokens": 0.02
  },
  {
    "id": 3,
    "model_id": "claude-3-sonnet",
    "display_name": "Claude 3 Sonnet",
    "provider": "anthropic",
    "recommendation_score": 0.88
  }
]
```

---

## Provider Failover

The SmartRouter automatically handles provider failures:

### Failover Configuration

```json
{
  "routing_strategy": "primary_with_backup",
  "primary_provider": "openai",
  "backup_provider": "anthropic",
  "failover_triggers": [
    "rate_limit",
    "timeout",
    "server_error"
  ],
  "circuit_breaker": {
    "failure_threshold": 5,
    "reset_timeout_seconds": 60
  }
}
```

### Circuit Breaker States

| State | Description |
|-------|-------------|
| `closed` | Normal operation |
| `open` | Provider temporarily disabled |
| `half_open` | Testing if provider recovered |

---

## Using in Workflows

### LLM Node Configuration

```json
{
  "id": "generate_code",
  "type": "llm_call",
  "data": {
    "routing_strategy": "cost_optimized",
    "model": "auto",
    "prompt": "{{variables.system_prompt}}\n\n{{input.user_request}}",
    "temperature": 0.7,
    "max_tokens": 2000,
    "fallback_enabled": true,
    "constraints": {
      "max_cost": 0.10
    }
  }
}
```

### Response Access

```
{{generate_code.output.content}}
{{generate_code.output.usage.total_tokens}}
{{generate_code.output.cost}}
```

---

## Rate Limiting

### Per-Provider Limits

Configure limits when registering providers:

```json
{
  "rate_limit_rpm": 10000,
  "rate_limit_tpm": 1000000
}
```

### Response Headers

```
X-RateLimit-Provider: openai
X-RateLimit-Remaining-RPM: 9500
X-RateLimit-Remaining-TPM: 950000
X-RateLimit-Reset: 1703583660
```

---

## Error Handling

### Common Errors

| Code | Description |
|------|-------------|
| `PROVIDER_UNAVAILABLE` | Provider is down |
| `RATE_LIMIT_EXCEEDED` | Hit rate limits |
| `COST_LIMIT_EXCEEDED` | Budget exceeded |
| `MODEL_NOT_FOUND` | Invalid model ID |
| `CONTEXT_LENGTH_EXCEEDED` | Prompt too long |

### Example Error

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "OpenAI rate limit exceeded",
    "details": {
      "provider": "openai",
      "limit": 10000,
      "reset_at": "2025-12-26T10:31:00Z"
    }
  }
}
```

---

## Best Practices

1. **Use routing strategies**: Let the system choose the best model
2. **Enable failover**: Prevent outages from affecting users
3. **Set cost constraints**: Prevent runaway spending
4. **Monitor analytics**: Track usage patterns
5. **A/B test models**: Find the best fit for your use case
6. **Cache responses**: Reduce costs for repeated queries

---

**See Also:**
- [Cost Management API](./cost.md)
- [Workflows API](./workflows.md)
