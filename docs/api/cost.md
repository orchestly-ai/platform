# Cost Management API

The Cost Management API provides AI-powered cost tracking, forecasting, and budget management. Prevent $10K+ surprise bills with proactive alerts and anomaly detection.

## Base URL

```
/api/v1/cost
```

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/events` | Log cost event |
| `GET` | `/events` | Query cost events |
| `GET` | `/summary` | Cost summary with breakdowns |
| `GET` | `/forecast` | AI-powered cost forecast |
| `GET` | `/anomalies` | Detect cost anomalies |
| `POST` | `/budgets` | Create budget |
| `GET` | `/budgets` | List budgets |
| `GET` | `/budgets/{id}/status` | Budget status |
| `GET` | `/categories` | List cost categories |
| `GET` | `/providers` | List LLM providers |

---

## Cost Categories

| Category | Description |
|----------|-------------|
| `llm_inference` | Language model API calls |
| `llm_embedding` | Text embedding generation |
| `storage` | Data storage costs |
| `compute` | Compute resources |
| `data_transfer` | Network bandwidth |
| `external_api` | Third-party API calls |

---

## Log Cost Event

Track a cost event for billing and analytics.

```
POST /api/v1/cost/events
```

### Request Body

```json
{
  "organization_id": "org_123",
  "category": "llm_inference",
  "amount": 0.045,
  "currency": "USD",
  "user_id": "user_456",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task_789",
  "workflow_id": "wf_abc",
  "provider": "openai",
  "model": "gpt-4-turbo",
  "input_tokens": 450,
  "output_tokens": 1200,
  "metadata": {
    "task_type": "code_generation"
  }
}
```

### Response

```json
{
  "event_id": "evt_xyz123",
  "timestamp": "2025-12-26T10:30:00Z",
  "organization_id": "org_123",
  "category": "llm_inference",
  "amount": 0.045,
  "currency": "USD",
  "provider": "openai",
  "model": "gpt-4-turbo",
  "input_tokens": 450,
  "output_tokens": 1200
}
```

---

## Cost Summary

Get aggregated cost data with breakdowns.

```
GET /api/v1/cost/summary
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `organization_id` | string | Required. Organization ID |
| `start_time` | datetime | Start of period (default: 30 days ago) |
| `end_time` | datetime | End of period (default: now) |

### Response

```json
{
  "organization_id": "org_123",
  "start_time": "2025-11-26T00:00:00Z",
  "end_time": "2025-12-26T23:59:59Z",
  "total_cost": 1250.45,
  "event_count": 45000,
  "avg_cost_per_event": 0.028,
  "category_breakdown": {
    "llm_inference": 1100.25,
    "llm_embedding": 85.50,
    "storage": 45.00,
    "external_api": 19.70
  },
  "provider_breakdown": {
    "openai": 800.25,
    "anthropic": 350.20,
    "deepseek": 100.00
  },
  "model_breakdown": {
    "gpt-4-turbo": 650.00,
    "gpt-3.5-turbo": 150.25,
    "claude-3-sonnet": 350.20,
    "deepseek-v3": 100.00
  },
  "top_agents": [
    ["agent_research_001", 250.50],
    ["agent_support_002", 180.25],
    ["agent_code_003", 120.00]
  ],
  "top_workflows": [
    ["wf_customer_support", 450.00],
    ["wf_code_review", 280.50],
    ["wf_research", 200.00]
  ],
  "top_users": [
    ["user_001", 300.00],
    ["user_002", 250.00]
  ],
  "vs_previous_period_percent": 15.5
}
```

---

## Cost Forecasting

AI-powered cost prediction using linear regression.

```
GET /api/v1/cost/forecast
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `organization_id` | string | Required |
| `forecast_days` | integer | Days to forecast (1-90, default: 7) |

### Response

```json
{
  "forecast_id": "fcst_abc123",
  "organization_id": "org_123",
  "forecast_date": "2025-12-26T10:30:00Z",
  "forecast_period_start": "2025-12-26T00:00:00Z",
  "forecast_period_end": "2026-01-02T00:00:00Z",
  "predicted_cost": 312.50,
  "confidence_lower": 280.00,
  "confidence_upper": 345.00,
  "confidence_interval": 95,
  "trend": "increasing",
  "anomalies_detected": [
    {
      "timestamp": "2025-12-25T14:00:00Z",
      "expected_cost": 40.00,
      "actual_cost": 85.00,
      "severity": "medium"
    }
  ]
}
```

### Trend Values

| Trend | Description |
|-------|-------------|
| `increasing` | Costs trending upward |
| `decreasing` | Costs trending downward |
| `stable` | Costs relatively flat |

---

## Anomaly Detection

Detect unusual cost patterns using 2-sigma threshold.

```
GET /api/v1/cost/anomalies
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `organization_id` | string | Required |
| `start_time` | datetime | Start of analysis period |
| `end_time` | datetime | End of analysis period |

### Response

```json
[
  {
    "timestamp": "2025-12-25T14:00:00Z",
    "expected_cost": 40.00,
    "actual_cost": 125.00,
    "deviation_percent": 212.5,
    "severity": "high",
    "potential_causes": [
      "Batch processing job 'quarterly_report'",
      "Agent 'research_agent' high activity",
      "Model upgrade to GPT-4 Turbo"
    ]
  },
  {
    "timestamp": "2025-12-24T09:00:00Z",
    "expected_cost": 35.00,
    "actual_cost": 62.00,
    "deviation_percent": 77.1,
    "severity": "medium",
    "potential_causes": [
      "Traffic spike from marketing campaign"
    ]
  }
]
```

### Severity Levels

| Severity | Deviation |
|----------|-----------|
| `low` | 50-100% above expected |
| `medium` | 100-200% above expected |
| `high` | >200% above expected |

---

## Budget Management

### Create Budget

Set up a budget with 4-tier alerting.

```
POST /api/v1/cost/budgets
```

### Request Body

```json
{
  "organization_id": "org_123",
  "name": "Monthly AI Budget",
  "period": "monthly",
  "amount": 5000.00,
  "currency": "USD",
  "scope_type": "organization",
  "scope_id": null,
  "alert_threshold_info": 50.0,
  "alert_threshold_warning": 75.0,
  "alert_threshold_critical": 90.0,
  "auto_disable_on_exceeded": false
}
```

### Budget Periods

| Period | Description |
|--------|-------------|
| `daily` | Resets daily at midnight UTC |
| `weekly` | Resets Monday at midnight UTC |
| `monthly` | Resets 1st of month |
| `quarterly` | Resets Jan/Apr/Jul/Oct 1st |
| `yearly` | Resets January 1st |

### Scope Types

| Type | Description |
|------|-------------|
| `organization` | Entire organization |
| `team` | Specific team |
| `agent` | Single agent |
| `workflow` | Single workflow |
| `user` | Individual user |

### Response

```json
{
  "budget_id": "bdgt_xyz123",
  "organization_id": "org_123",
  "name": "Monthly AI Budget",
  "period": "monthly",
  "amount": 5000.00,
  "currency": "USD",
  "alert_threshold_info": 50.0,
  "alert_threshold_warning": 75.0,
  "alert_threshold_critical": 90.0,
  "auto_disable_on_exceeded": false,
  "is_active": true,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T10:00:00Z"
}
```

---

## Budget Status

Check current spending against budget.

```
GET /api/v1/cost/budgets/{budget_id}/status
```

### Response

```json
{
  "budget_id": "bdgt_xyz123",
  "name": "Monthly AI Budget",
  "amount": 5000.00,
  "current_period_start": "2025-12-01T00:00:00Z",
  "current_period_end": "2025-12-31T23:59:59Z",
  "spent": 3750.25,
  "remaining": 1249.75,
  "percent_used": 75.01,
  "status": "warning",
  "alerts": [
    {
      "level": "info",
      "threshold": 50.0,
      "message": "50% of budget used ($2,500.00)",
      "created_at": "2025-12-15T08:00:00Z"
    },
    {
      "level": "warning",
      "threshold": 75.0,
      "message": "75% of budget used ($3,750.00)",
      "created_at": "2025-12-26T10:30:00Z"
    }
  ]
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `ok` | Under 50% used |
| `info` | 50-75% used |
| `warning` | 75-90% used |
| `critical` | 90-100% used |
| `exceeded` | Over 100% used |

---

## Alert Thresholds

Configure alerts at multiple levels:

| Level | Default Threshold | Action |
|-------|-------------------|--------|
| `info` | 50% | Dashboard notification |
| `warning` | 75% | Email + Slack notification |
| `critical` | 90% | Urgent notification + escalation |
| `exceeded` | 100% | All channels + optional auto-disable |

### Notification Channels

```json
{
  "notifications": {
    "email": ["team@company.com"],
    "slack": "#cost-alerts",
    "pagerduty": "service_id_123"
  }
}
```

---

## Permissions Required

| Endpoint | Permission |
|----------|------------|
| View costs | `COST_READ` |
| Log events | `COST_UPDATE` |
| Manage budgets | `COST_LIMIT_SET` |

---

## Using in Workflows

### Cost-Aware Routing

```json
{
  "id": "llm_call",
  "type": "llm_call",
  "data": {
    "routing_strategy": "cost_optimized",
    "constraints": {
      "max_cost": 0.10
    }
  }
}
```

### Budget Check Node

```json
{
  "id": "check_budget",
  "type": "conditional",
  "data": {
    "conditions": [
      {
        "if": "{{cost.budget_remaining}} < 100",
        "then": "low_cost_path"
      },
      {
        "else": "normal_path"
      }
    ]
  }
}
```

---

## Webhooks

Receive real-time cost alerts:

```json
{
  "event": "cost.threshold_exceeded",
  "data": {
    "budget_id": "bdgt_xyz123",
    "threshold": 75,
    "current_percent": 75.01,
    "spent": 3750.25,
    "remaining": 1249.75
  },
  "timestamp": "2025-12-26T10:30:00Z"
}
```

### Webhook Events

| Event | Description |
|-------|-------------|
| `cost.threshold_exceeded` | Budget threshold crossed |
| `cost.anomaly_detected` | Unusual spending pattern |
| `cost.budget_exceeded` | Budget fully consumed |

---

## Best Practices

1. **Set realistic budgets**: Base on historical usage + growth
2. **Enable all alert levels**: Catch issues early
3. **Use scope-based budgets**: Track costs by team/workflow
4. **Monitor anomalies daily**: Catch runaway costs fast
5. **Review forecasts weekly**: Adjust budgets proactively
6. **Use cost-optimized routing**: Reduce LLM costs 30-50%

---

## Example: Complete Cost Setup

```bash
# 1. Create organization budget
curl -X POST "/api/v1/cost/budgets" \
  -d '{"organization_id": "org_123", "name": "Monthly Budget", "period": "monthly", "amount": 5000}'

# 2. Create team-level budget
curl -X POST "/api/v1/cost/budgets" \
  -d '{"organization_id": "org_123", "name": "Engineering Team", "period": "monthly", "amount": 2000, "scope_type": "team", "scope_id": "team_eng"}'

# 3. Monitor status
curl -X GET "/api/v1/cost/budgets/bdgt_xyz/status"

# 4. Check for anomalies
curl -X GET "/api/v1/cost/anomalies?organization_id=org_123"

# 5. Get 7-day forecast
curl -X GET "/api/v1/cost/forecast?organization_id=org_123&forecast_days=7"
```

---

**See Also:**
- [LLM Routing API](./llm.md)
- [Analytics](./agents.md#analytics)
