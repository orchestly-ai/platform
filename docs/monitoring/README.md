# Monitoring & Alerting Guide

Comprehensive monitoring setup for the Agent Orchestration Platform using Prometheus and Grafana.

## Contents

- **PROMETHEUS_METRICS.md** - Metrics collection and configuration
- **GRAFANA_DASHBOARDS.md** - Dashboard configurations
- **ALERT_RULES.md** - Alerting rules and thresholds

## Quick Start

### 1. Enable Metrics
Set environment variable:
```bash
export ENABLE_METRICS=true
export METRICS_PORT=9090
```

### 2. Access Metrics Endpoint
```bash
curl http://localhost:9090/metrics
```

### 3. Configure Prometheus
Add to `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'agent-orchestration'
    static_configs:
      - targets: ['localhost:9090']
```

### 4. Import Grafana Dashboards
Import the JSON files from `grafana/` directory.

## Key Metrics

| Metric | Description | Type |
|--------|-------------|------|
| `api_requests_total` | Total API requests | Counter |
| `api_request_duration_seconds` | Request latency | Histogram |
| `llm_requests_total` | LLM API calls | Counter |
| `llm_tokens_total` | Tokens consumed | Counter |
| `workflow_executions_total` | Workflow runs | Counter |
| `agent_tasks_active` | Active agent tasks | Gauge |

## Health Endpoints

- `GET /health` - Basic health check
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe
