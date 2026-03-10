# Prometheus Metrics

## Overview

The Agent Orchestration Platform exposes Prometheus metrics for monitoring performance, resource usage, and business KPIs.

## Metrics Categories

### 1. API Metrics

```prometheus
# Total API requests
api_requests_total{method="GET", endpoint="/api/v1/workflows", status="200"} 1234

# Request duration histogram
api_request_duration_seconds_bucket{method="GET", endpoint="/api/v1/workflows", le="0.1"} 900
api_request_duration_seconds_bucket{method="GET", endpoint="/api/v1/workflows", le="0.5"} 1100
api_request_duration_seconds_bucket{method="GET", endpoint="/api/v1/workflows", le="1.0"} 1200
api_request_duration_seconds_sum{method="GET", endpoint="/api/v1/workflows"} 123.45
api_request_duration_seconds_count{method="GET", endpoint="/api/v1/workflows"} 1234

# Active requests
api_requests_active{endpoint="/api/v1/workflows/execute"} 5
```

### 2. LLM Provider Metrics

```prometheus
# LLM request count
llm_requests_total{provider="openai", model="gpt-4", status="success"} 5000
llm_requests_total{provider="anthropic", model="claude-3-5-sonnet", status="success"} 3000

# LLM latency
llm_request_duration_seconds_bucket{provider="openai", model="gpt-4", le="1.0"} 4000
llm_request_duration_seconds_bucket{provider="openai", model="gpt-4", le="5.0"} 4900
llm_request_duration_seconds_sum{provider="openai", model="gpt-4"} 12345.67

# Token usage
llm_tokens_total{provider="openai", type="input"} 1000000
llm_tokens_total{provider="openai", type="output"} 500000

# Cost tracking
llm_cost_dollars_total{provider="openai", org_id="org_123"} 450.50
```

### 3. Workflow Metrics

```prometheus
# Workflow executions
workflow_executions_total{status="completed"} 1000
workflow_executions_total{status="failed"} 50
workflow_executions_total{status="cancelled"} 10

# Workflow duration
workflow_duration_seconds_bucket{workflow_id="wf_123", le="60"} 800
workflow_duration_seconds_sum{workflow_id="wf_123"} 45678.90

# Active workflows
workflows_active_total 15

# Workflow by type
workflow_by_type_total{type="data_pipeline"} 500
workflow_by_type_total{type="content_generation"} 300
```

### 4. Agent Metrics

```prometheus
# Agent tasks
agent_tasks_total{agent_id="agent_1", status="completed"} 2500
agent_tasks_total{agent_id="agent_1", status="failed"} 25

# Active agent tasks
agent_tasks_active{agent_id="agent_1"} 3

# Agent load
agent_load_ratio{agent_id="agent_1"} 0.6

# Task duration
agent_task_duration_seconds_bucket{agent_type="research", le="30"} 2000
```

### 5. Database Metrics

```prometheus
# Query duration
db_query_duration_seconds_bucket{operation="select", table="workflows", le="0.01"} 9000
db_query_duration_seconds_bucket{operation="select", table="workflows", le="0.1"} 9900

# Connection pool
db_connections_active 15
db_connections_idle 5
db_connections_max 20

# Query count
db_queries_total{operation="select"} 50000
db_queries_total{operation="insert"} 5000
db_queries_total{operation="update"} 3000
```

### 6. Cache Metrics

```prometheus
# Cache hit/miss
cache_hits_total{cache="entity"} 80000
cache_misses_total{cache="entity"} 20000

# Cache operations
cache_operations_total{operation="get"} 100000
cache_operations_total{operation="set"} 25000
cache_operations_total{operation="delete"} 5000

# Cache latency
cache_operation_duration_seconds_bucket{operation="get", le="0.001"} 98000
```

### 7. Rate Limiting Metrics

```prometheus
# Rate limit hits
rate_limit_hits_total{org_id="org_123"} 50
rate_limit_remaining{org_id="org_123"} 450
```

## Prometheus Configuration

### prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: 'agent-orchestration-api'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['api:9090']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'api'

  - job_name: 'agent-orchestration-workers'
    static_configs:
      - targets: ['worker-1:9090', 'worker-2:9090']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

## Recording Rules

For efficient dashboard queries, use recording rules:

```yaml
# prometheus_rules.yml
groups:
  - name: agent_orchestration
    interval: 30s
    rules:
      # API success rate
      - record: api:success_rate:5m
        expr: |
          sum(rate(api_requests_total{status=~"2.."}[5m]))
          / sum(rate(api_requests_total[5m]))

      # LLM cost per hour
      - record: llm:cost_per_hour
        expr: |
          sum(rate(llm_cost_dollars_total[1h])) * 3600

      # Workflow success rate
      - record: workflow:success_rate:1h
        expr: |
          sum(rate(workflow_executions_total{status="completed"}[1h]))
          / sum(rate(workflow_executions_total[1h]))

      # Cache hit ratio
      - record: cache:hit_ratio:5m
        expr: |
          sum(rate(cache_hits_total[5m]))
          / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

      # Average request latency
      - record: api:latency_p95:5m
        expr: |
          histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[5m])) by (le))
```

## PromQL Examples

### API Performance
```promql
# Request rate per second
rate(api_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# Error rate
rate(api_requests_total{status=~"5.."}[5m]) / rate(api_requests_total[5m])
```

### LLM Usage
```promql
# Tokens per minute
rate(llm_tokens_total[5m]) * 60

# Cost per hour by provider
sum by (provider) (rate(llm_cost_dollars_total[1h])) * 3600

# Average latency by model
rate(llm_request_duration_seconds_sum[5m]) / rate(llm_request_duration_seconds_count[5m])
```

### Workflow Monitoring
```promql
# Active workflows
sum(workflows_active_total)

# Completion rate
sum(rate(workflow_executions_total{status="completed"}[1h]))
  / sum(rate(workflow_executions_total[1h]))

# Average duration by workflow
sum by (workflow_id) (rate(workflow_duration_seconds_sum[1h]))
  / sum by (workflow_id) (rate(workflow_duration_seconds_count[1h]))
```
