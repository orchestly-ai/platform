# Production Deployment Guide

This guide covers deploying the Agent Orchestration Platform to production with full observability, security, and scalability.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Helm Installation](#helm-installation)
5. [Security](#security)
6. [Monitoring & Observability](#monitoring--observability)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Infrastructure

- **Kubernetes Cluster**: v1.24+ (EKS, GKE, AKS, or self-hosted)
- **PostgreSQL**: 14+ with TimescaleDB extension
- **Redis**: 7.0+
- **Storage**: Persistent volumes for database and cache
- **TLS Certificates**: Valid SSL certificates (Let's Encrypt recommended)

### Required Tools

```bash
# Kubernetes CLI
kubectl version --client

# Helm package manager
helm version

# Docker (for local testing)
docker --version

# Optional: k9s for cluster management
k9s version
```

### Environment Variables

Create a `.env.production` file:

```env
# Application
ENVIRONMENT=production
DEBUG=false

# Database
POSTGRES_HOST=postgres.production.svc.cluster.local
POSTGRES_PORT=5432
POSTGRES_DB=agent_orchestrator
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<SECURE_PASSWORD>

# Redis
REDIS_HOST=redis.production.svc.cluster.local
REDIS_PORT=6379

# Authentication
JWT_SECRET_KEY=<GENERATE_32_CHAR_SECRET>

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Monitoring (Optional)
SENTRY_DSN=https://...@sentry.io/...
DATADOG_API_KEY=...
```

---

## Quick Start

### 1. Local Development

```bash
# Clone repository
git clone https://github.com/orchestly-ai/platform.git
cd platform

# Start all services with Docker Compose
docker-compose up -d

# With monitoring
docker-compose --profile observability up -d

# Verify services
curl http://localhost:8000/health
curl http://localhost:3000
```

### 2. Run Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run unit tests
pytest tests/unit/ -v --cov

# Run integration tests
pytest tests/integration/ -v -m integration

# Run load tests
pytest tests/load/ -v -m slow
```

---

## Kubernetes Deployment

### Step 1: Create Namespace

```bash
kubectl create namespace production
kubectl label namespace production environment=production
```

### Step 2: Create Secrets

```bash
# From .env file
kubectl create secret generic agent-orchestrator-secrets \
  --from-env-file=.env.production \
  --namespace production

# Or manually
kubectl create secret generic agent-orchestrator-secrets \
  --from-literal=postgres_password='<PASSWORD>' \
  --from-literal=jwt_secret_key='<SECRET>' \
  --from-literal=openai_api_key='sk-...' \
  --namespace production
```

### Step 3: Apply Manifests

```bash
# Apply all base manifests
kubectl apply -f k8s/base/ --namespace production

# Or apply individually
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/postgres-statefulset.yaml
kubectl apply -f k8s/base/redis-statefulset.yaml
kubectl apply -f k8s/base/deployment.yaml
kubectl apply -f k8s/base/service.yaml
kubectl apply -f k8s/base/ingress.yaml
```

### Step 4: Verify Deployment

```bash
# Check all resources
kubectl get all -n production

# Check pod status
kubectl get pods -n production -w

# Check logs
kubectl logs -f deployment/agent-orchestrator-api -n production

# Check health
kubectl exec -it deployment/agent-orchestrator-api -n production -- \
  curl http://localhost:8000/health/ready
```

---

## Helm Installation

### Step 1: Add Repository (if published)

```bash
helm repo add agent-orchestrator https://charts.agent-orchestrator.dev
helm repo update
```

### Step 2: Install Chart

```bash
# Install with default values
helm install agent-orchestrator agent-orchestrator/agent-orchestrator \
  --namespace production \
  --create-namespace

# Install with custom values
helm install agent-orchestrator ./helm/agent-orchestrator \
  --namespace production \
  --values k8s/overlays/prod/values.yaml \
  --set secrets.jwtSecretKey='<SECRET>' \
  --set secrets.openaiApiKey='sk-...'
```

### Step 3: Upgrade Deployment

```bash
# Upgrade to new version
helm upgrade agent-orchestrator ./helm/agent-orchestrator \
  --namespace production \
  --values k8s/overlays/prod/values.yaml \
  --set image.api.tag=v0.2.0

# Rollback if needed
helm rollback agent-orchestrator 1 --namespace production
```

---

## Security

### 1. API Key Authentication

All agent API calls require authentication:

```python
import requests

headers = {
    "X-API-Key": "sk-your-api-key",
    "Content-Type": "application/json"
}

response = requests.post(
    "https://api.agent-orchestrator.example.com/api/v1/tasks",
    headers=headers,
    json={"capability": "test", "input": {"data": {}}}
)
```

### 2. JWT Authentication (Dashboard)

Dashboard users authenticate via JWT:

```bash
# Login
curl -X POST https://api.agent-orchestrator.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Use token
curl https://api.agent-orchestrator.example.com/api/v1/metrics \
  -H "Authorization: Bearer <token>"
```

### 3. Rate Limiting

Rate limits are enforced per organization:

- **Startup Tier**: 100 requests/minute
- **Growth Tier**: 500 requests/minute
- **Enterprise Tier**: 2000 requests/minute

### 4. Network Policies

Apply network policies for pod-to-pod communication:

```bash
kubectl apply -f k8s/base/network-policy.yaml -n production
```

### 5. TLS/SSL

Ensure all traffic is encrypted:

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer for Let's Encrypt
kubectl apply -f k8s/base/cert-issuer.yaml
```

---

## Monitoring & Observability

### 1. Prometheus Metrics

Metrics are exposed at `/metrics` endpoint:

```bash
curl https://api.agent-orchestrator.example.com/metrics
```

**Key Metrics:**
- `agents_registered_total` - Total registered agents
- `agents_active_total` - Currently active agents
- `tasks_completed_total` - Completed tasks by capability
- `task_duration_seconds` - Task execution latency
- `llm_cost_total` - LLM API costs
- `queue_depth` - Current queue depth by capability

### 2. Grafana Dashboards

Import the pre-built dashboard:

1. Open Grafana: `http://grafana.agent-orchestrator.example.com`
2. Go to Dashboards → Import
3. Upload `deployment/docker/grafana/dashboards/agent-orchestrator-dashboard.json`

### 3. Sentry Error Tracking

Configure Sentry DSN in secrets:

```bash
kubectl create secret generic agent-orchestrator-secrets \
  --from-literal=sentry_dsn='https://...@sentry.io/...' \
  --namespace production \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 4. Health Checks

Multiple health check endpoints:

```bash
# Basic health
curl https://api.agent-orchestrator.example.com/health

# Readiness (Kubernetes)
curl https://api.agent-orchestrator.example.com/health/ready

# Liveness (Kubernetes)
curl https://api.agent-orchestrator.example.com/health/live

# Detailed metrics
curl https://api.agent-orchestrator.example.com/health/detailed
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

The CI/CD pipeline automatically:

1. **On PR**: Run tests, linting, security scans
2. **On merge to main**: Build and push Docker images
3. **On tag (v*)**: Deploy to production

### Manual Deployment

```bash
# Tag release
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0

# GitHub Actions will automatically deploy
```

### Secrets Configuration

Add these secrets to GitHub repository:

- `KUBECONFIG_PRODUCTION` - Base64-encoded kubeconfig
- `DOCKER_USERNAME` - Container registry username
- `DOCKER_PASSWORD` - Container registry password

---

## Troubleshooting

### Common Issues

#### 1. Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n production

# Check logs
kubectl logs <pod-name> -n production

# Check events
kubectl get events -n production --sort-by='.lastTimestamp'
```

#### 2. Database Connection Failed

```bash
# Test database connectivity
kubectl exec -it deployment/agent-orchestrator-api -n production -- \
  psql -h postgres -U postgres -d agent_orchestrator

# Check secrets
kubectl get secret agent-orchestrator-secrets -n production -o yaml
```

#### 3. High Memory Usage

```bash
# Check resource usage
kubectl top pods -n production

# Scale up if needed
kubectl scale deployment agent-orchestrator-api --replicas=5 -n production
```

#### 4. Queue Backlog

```bash
# Check queue depths
curl https://api.agent-orchestrator.example.com/api/v1/metrics/queues

# Scale up workers
kubectl scale deployment agent-orchestrator-worker --replicas=10 -n production
```

### Performance Tuning

**Database:**
```sql
-- Create indexes
CREATE INDEX idx_tasks_capability ON tasks(capability);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_agents_status ON agents(status);
```

**Redis:**
```bash
# Increase max memory
kubectl exec -it redis-0 -n production -- redis-cli CONFIG SET maxmemory 4gb
```

**API:**
```bash
# Increase worker count
helm upgrade agent-orchestrator ./helm/agent-orchestrator \
  --set config.apiWorkers=8 \
  --namespace production
```

---

## Production Checklist

Before going live:

- [ ] All tests passing (unit, integration, load)
- [ ] Security scan completed (no critical vulnerabilities)
- [ ] TLS certificates configured
- [ ] Secrets properly managed (not in git)
- [ ] Database backups configured
- [ ] Monitoring and alerting set up
- [ ] Rate limiting configured
- [ ] CORS origins whitelisted
- [ ] Load testing completed (1000+ concurrent tasks)
- [ ] Disaster recovery plan documented
- [ ] On-call rotation established

---

## Support

- **Documentation**: https://docs.agent-orchestrator.dev
- **Issues**: https://github.com/orchestly-ai/platform/issues
- **Community**: Discord server (link in README)
- **Enterprise Support**: support@agent-orchestrator.dev

---

**Last Updated**: November 2025
**Version**: 0.1.0
