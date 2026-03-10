# Deployment Guide

Deploy the Agent Orchestration Platform to production environments.

## Deployment Options

| Option | Best For | Complexity |
|--------|----------|------------|
| [Docker Compose](./docker-compose.md) | Development, small deployments | Low |
| [Kubernetes](./kubernetes.md) | Production, high availability | Medium |
| [AWS](./aws.md) | AWS-native infrastructure | Medium |
| [Azure](./azure.md) | Azure-native infrastructure | Medium |
| [GCP](./gcp.md) | Google Cloud infrastructure | Medium |

## Prerequisites

### Minimum Requirements

| Component | Development | Production |
|-----------|-------------|------------|
| CPU | 2 cores | 4+ cores |
| Memory | 4 GB | 16+ GB |
| Storage | 20 GB | 100+ GB SSD |
| Database | SQLite | PostgreSQL 14+ |
| Cache | In-memory | Redis 7+ |

### Required Services

- **PostgreSQL 14+**: Primary database
- **Redis 7+**: Caching and task queues
- **Object Storage**: S3/GCS/Azure Blob for artifacts

### Optional Services

- **Elasticsearch**: Log aggregation
- **Prometheus + Grafana**: Monitoring
- **Vault**: Secrets management

## Quick Start

### Docker Compose (Development)

```bash
git clone https://github.com/orchestly-ai/platform.git
cd platform

# Copy environment template
cp .env.example .env

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

Access the platform:
- API: http://localhost:8000
- Dashboard: http://localhost:3000
- API Docs: http://localhost:8000/docs

### Kubernetes (Production)

```bash
# Add Helm repository
helm repo add agent-orchestrator https://charts.agent-orchestrator.dev

# Install with default values
helm install agent-orchestrator agent-orchestrator/agent-orchestrator \
  --namespace agent-orchestrator \
  --create-namespace

# Install with custom values
helm install agent-orchestrator agent-orchestrator/agent-orchestrator \
  --namespace agent-orchestrator \
  --create-namespace \
  -f values-production.yaml
```

## Architecture Overview

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (nginx/ALB)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │  API Pod  │  │  API Pod  │  │  API Pod  │
        │  (FastAPI)│  │  (FastAPI)│  │  (FastAPI)│
        └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐        ┌─────▼─────┐       ┌─────▼─────┐
    │ Postgres│        │   Redis   │       │  Workers  │
    │ Primary │        │  Cluster  │       │  (Celery) │
    └────┬────┘        └───────────┘       └───────────┘
         │
    ┌────▼────┐
    │ Postgres│
    │ Replica │
    └─────────┘
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `SECRET_KEY` | Application secret key | Yes |
| `API_HOST` | API bind address | No (0.0.0.0) |
| `API_PORT` | API port | No (8000) |
| `DEBUG` | Enable debug mode | No (false) |
| `CORS_ORIGINS` | Allowed CORS origins | No |

### LLM Provider Configuration

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |

### Integration Credentials

Store securely using secrets management:

```yaml
# Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: integration-credentials
type: Opaque
stringData:
  SLACK_BOT_TOKEN: "xoxb-..."
  GITHUB_TOKEN: "ghp_..."
  SALESFORCE_CLIENT_ID: "..."
```

## Health Checks

### Liveness Probe

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### Readiness Probe

```bash
curl http://localhost:8000/health/ready
```

Checks:
- Database connectivity
- Redis connectivity
- Required services available

## Scaling

### Horizontal Scaling

```bash
# Kubernetes
kubectl scale deployment api --replicas=5

# Docker Compose
docker-compose up -d --scale api=5
```

### Scaling Guidelines

| Component | Scaling Strategy |
|-----------|------------------|
| API | Horizontal (stateless) |
| Workers | Horizontal (stateless) |
| PostgreSQL | Vertical + Read Replicas |
| Redis | Cluster mode |

## Monitoring

### Prometheus Metrics

Exposed at `/metrics`:

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `workflow_executions_total` - Workflow executions
- `llm_requests_total` - LLM API calls
- `llm_cost_total` - Total LLM costs

### Grafana Dashboards

Import from `monitoring/grafana/`:

- `platform-overview.json` - System overview
- `workflow-metrics.json` - Workflow analytics
- `cost-tracking.json` - Cost dashboards

## Backup & Recovery

### Database Backup

```bash
# PostgreSQL backup
pg_dump -h $DB_HOST -U $DB_USER agent_orchestrator > backup.sql

# Restore
psql -h $DB_HOST -U $DB_USER agent_orchestrator < backup.sql
```

### Automated Backups

Configure in Kubernetes:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:14
            command: ["/scripts/backup.sh"]
```

## Security

### Network Security

- Use private subnets for databases
- Configure security groups/firewall rules
- Enable TLS for all connections

### Secrets Management

- Use Kubernetes Secrets or cloud-native solutions
- Rotate credentials regularly
- Never commit secrets to version control

### Authentication

- Configure SSO for production
- Use strong API key policies
- Enable audit logging

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Database connection failed | Check `DATABASE_URL` and network |
| Redis connection refused | Verify Redis is running and accessible |
| API returns 500 | Check logs with `docker-compose logs api` |
| Slow performance | Scale horizontally, check database indexes |

### Logs

```bash
# Docker Compose
docker-compose logs -f api

# Kubernetes
kubectl logs -f deployment/api -n agent-orchestrator
```

### Debug Mode

Enable temporarily for troubleshooting:

```bash
DEBUG=true docker-compose up
```

**Warning**: Never enable in production.

---

**Next Steps:**
- [Docker Compose Guide](./docker-compose.md)
- [Kubernetes Guide](./kubernetes.md)
- [AWS Deployment](./aws.md)
