# Alert Rules

## Overview

Alert rules for monitoring the Agent Orchestration Platform health, performance, and cost.

## Alert Categories

### 1. API Health Alerts

```yaml
# alert_rules.yml
groups:
  - name: api_health
    rules:
      - alert: APIHighErrorRate
        expr: |
          (sum(rate(api_requests_total{status=~"5.."}[5m]))
          / sum(rate(api_requests_total[5m]))) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate (> 5%)"
          description: "API error rate is {{ $value | printf \"%.2f\" }}%"

      - alert: APIHighLatency
        expr: |
          histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency (P95 > 2s)"
          description: "P95 latency is {{ $value | printf \"%.2f\" }}s"

      - alert: APIDown
        expr: up{job="agent-orchestration-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API is down"
          description: "API instance {{ $labels.instance }} is not responding"
```

### 2. LLM Provider Alerts

```yaml
  - name: llm_health
    rules:
      - alert: LLMHighErrorRate
        expr: |
          (sum(rate(llm_requests_total{status="error"}[5m]))
          / sum(rate(llm_requests_total[5m]))) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High LLM error rate (> 10%)"
          description: "LLM provider {{ $labels.provider }} error rate is {{ $value | printf \"%.2f\" }}%"

      - alert: LLMHighLatency
        expr: |
          histogram_quantile(0.95, rate(llm_request_duration_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High LLM latency (P95 > 10s)"
          description: "P95 latency for {{ $labels.provider }}/{{ $labels.model }} is {{ $value | printf \"%.2f\" }}s"

      - alert: LLMProviderDown
        expr: |
          sum(rate(llm_requests_total{status="error"}[5m])) by (provider)
          / sum(rate(llm_requests_total[5m])) by (provider) > 0.9
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "LLM provider appears down"
          description: "Provider {{ $labels.provider }} has > 90% error rate"
```

### 3. Cost Alerts

```yaml
  - name: cost_alerts
    rules:
      - alert: HighHourlyCost
        expr: llm:cost_per_hour > 100
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "High hourly LLM cost (> $100/hr)"
          description: "Current cost rate is ${{ $value | printf \"%.2f\" }}/hour"

      - alert: CostBudgetExceeded
        expr: |
          sum(llm_cost_dollars_total) > 10000
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Monthly cost budget exceeded"
          description: "Total spend is ${{ $value | printf \"%.2f\" }}"

      - alert: UnusualCostSpike
        expr: |
          rate(llm_cost_dollars_total[1h]) > 2 * avg_over_time(rate(llm_cost_dollars_total[1h])[24h:1h])
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Unusual cost spike detected"
          description: "Cost rate is 2x higher than 24h average"
```

### 4. Workflow Alerts

```yaml
  - name: workflow_health
    rules:
      - alert: WorkflowHighFailureRate
        expr: |
          (sum(rate(workflow_executions_total{status="failed"}[1h]))
          / sum(rate(workflow_executions_total[1h]))) > 0.1
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "High workflow failure rate (> 10%)"
          description: "Workflow failure rate is {{ $value | printf \"%.2f\" }}%"

      - alert: WorkflowStuck
        expr: |
          (time() - workflow_last_completed_timestamp) > 3600
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "No workflows completed in 1 hour"
          description: "Check for stuck workflows"

      - alert: TooManyActiveWorkflows
        expr: workflows_active_total > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Too many active workflows"
          description: "{{ $value }} workflows are currently active"
```

### 5. Database Alerts

```yaml
  - name: database_health
    rules:
      - alert: DatabaseHighLatency
        expr: |
          histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m])) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database query latency"
          description: "P95 query latency is {{ $value | printf \"%.2f\" }}s"

      - alert: DatabaseConnectionPoolExhausted
        expr: |
          db_connections_active / db_connections_max > 0.9
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool near exhaustion"
          description: "{{ $value | printf \"%.0f\" }}% of connections in use"

      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database is down"
          description: "PostgreSQL is not responding"
```

### 6. Cache Alerts

```yaml
  - name: cache_health
    rules:
      - alert: CacheHitRatioLow
        expr: cache:hit_ratio:5m < 0.5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit ratio (< 50%)"
          description: "Cache hit ratio is {{ $value | printf \"%.2f\" }}%"

      - alert: CacheDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis cache is down"
          description: "Redis is not responding"

      - alert: CacheMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis memory usage high"
          description: "Redis is using {{ $value | printf \"%.0f\" }}% of available memory"
```

### 7. Rate Limiting Alerts

```yaml
  - name: rate_limiting
    rules:
      - alert: HighRateLimitHits
        expr: rate(rate_limit_hits_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High rate of rate limit hits"
          description: "Organization {{ $labels.org_id }} is hitting rate limits frequently"
```

## Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/xxx/yyy/zzz'

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'

  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true

    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#alerts'
        send_resolved: true

  - name: 'critical-alerts'
    slack_configs:
      - channel: '#critical-alerts'
        send_resolved: true
    pagerduty_configs:
      - service_key: 'your-pagerduty-key'

  - name: 'warning-alerts'
    slack_configs:
      - channel: '#warnings'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname']
```

## Alert Severity Levels

| Severity | Response Time | Action Required |
|----------|--------------|-----------------|
| Critical | < 15 minutes | Immediate page, all-hands |
| Warning | < 1 hour | Investigate during business hours |
| Info | Next business day | Review in daily standup |

## Runbook Links

Each alert should link to a runbook:
- [API Down Runbook](runbooks/api-down.md)
- [LLM Provider Issues](runbooks/llm-issues.md)
- [Cost Spikes](runbooks/cost-spikes.md)
- [Database Issues](runbooks/database-issues.md)
