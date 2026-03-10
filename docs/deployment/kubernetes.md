# Kubernetes Deployment

Deploy the Agent Orchestration Platform on Kubernetes for production-grade high availability and scalability.

## Prerequisites

- Kubernetes 1.25+
- kubectl configured
- Helm 3.0+
- Ingress controller (nginx-ingress recommended)
- cert-manager (for TLS)

## Quick Start with Helm

### 1. Add Helm Repository

```bash
helm repo add agent-orchestrator https://charts.agent-orchestrator.dev
helm repo update
```

### 2. Create Namespace

```bash
kubectl create namespace agent-orchestrator
```

### 3. Create Secrets

```bash
kubectl create secret generic api-secrets \
  --namespace agent-orchestrator \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=DATABASE_URL="postgresql+asyncpg://user:pass@postgres:5432/agent_orchestrator" \
  --from-literal=REDIS_URL="redis://redis:6379/0"

kubectl create secret generic llm-credentials \
  --namespace agent-orchestrator \
  --from-literal=OPENAI_API_KEY="sk-..." \
  --from-literal=ANTHROPIC_API_KEY="sk-ant-..."
```

### 4. Install Chart

```bash
helm install agent-orchestrator agent-orchestrator/agent-orchestrator \
  --namespace agent-orchestrator \
  --values values.yaml
```

### 5. Verify Installation

```bash
kubectl get pods -n agent-orchestrator
kubectl get svc -n agent-orchestrator
```

## Helm Values

### values.yaml

```yaml
# =============================================================================
# Global Settings
# =============================================================================
global:
  environment: production
  imageRegistry: ghcr.io/orchestly-ai
  imagePullSecrets:
    - name: regcred

# =============================================================================
# API Server
# =============================================================================
api:
  replicaCount: 3

  image:
    repository: agent-orchestrator/api
    tag: latest
    pullPolicy: IfNotPresent

  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi

  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80

  env:
    - name: DEBUG
      value: "false"
    - name: SECRET_KEY
      valueFrom:
        secretKeyRef:
          name: api-secrets
          key: SECRET_KEY
    - name: DATABASE_URL
      valueFrom:
        secretKeyRef:
          name: api-secrets
          key: DATABASE_URL
    - name: REDIS_URL
      valueFrom:
        secretKeyRef:
          name: api-secrets
          key: REDIS_URL

  livenessProbe:
    httpGet:
      path: /health
      port: 8000
    initialDelaySeconds: 30
    periodSeconds: 10

  readinessProbe:
    httpGet:
      path: /health/ready
      port: 8000
    initialDelaySeconds: 5
    periodSeconds: 5

  service:
    type: ClusterIP
    port: 8000

# =============================================================================
# Workers
# =============================================================================
worker:
  replicaCount: 5

  image:
    repository: agent-orchestrator/worker
    tag: latest

  resources:
    requests:
      cpu: 250m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi

  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70

# =============================================================================
# Scheduler
# =============================================================================
scheduler:
  enabled: true
  replicaCount: 1

  image:
    repository: agent-orchestrator/scheduler
    tag: latest

# =============================================================================
# PostgreSQL
# =============================================================================
postgresql:
  enabled: true
  auth:
    postgresPassword: "change-me"
    database: agent_orchestrator

  primary:
    resources:
      requests:
        cpu: 1000m
        memory: 2Gi
      limits:
        cpu: 4000m
        memory: 8Gi

    persistence:
      enabled: true
      size: 100Gi
      storageClass: gp3

  readReplicas:
    replicaCount: 2
    resources:
      requests:
        cpu: 500m
        memory: 1Gi

# =============================================================================
# Redis
# =============================================================================
redis:
  enabled: true
  architecture: replication

  auth:
    enabled: true
    password: "change-me"

  master:
    resources:
      requests:
        cpu: 250m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 2Gi

    persistence:
      enabled: true
      size: 10Gi

  replica:
    replicaCount: 2

# =============================================================================
# Ingress
# =============================================================================
ingress:
  enabled: true
  className: nginx

  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"

  hosts:
    - host: api.agent-orchestrator.example.com
      paths:
        - path: /
          pathType: Prefix

  tls:
    - secretName: api-tls
      hosts:
        - api.agent-orchestrator.example.com

# =============================================================================
# Dashboard
# =============================================================================
dashboard:
  enabled: true
  replicaCount: 2

  image:
    repository: agent-orchestrator/dashboard
    tag: latest

  ingress:
    enabled: true
    hosts:
      - host: dashboard.agent-orchestrator.example.com
        paths:
          - path: /
            pathType: Prefix

# =============================================================================
# Monitoring
# =============================================================================
monitoring:
  enabled: true

  prometheus:
    enabled: true
    serviceMonitor:
      enabled: true

  grafana:
    enabled: true
    dashboards:
      enabled: true

# =============================================================================
# Pod Disruption Budget
# =============================================================================
podDisruptionBudget:
  enabled: true
  minAvailable: 2
```

## Manual Kubernetes Manifests

### Namespace and Secrets

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: agent-orchestrator
  labels:
    name: agent-orchestrator
---
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-secrets
  namespace: agent-orchestrator
type: Opaque
stringData:
  SECRET_KEY: "your-secret-key"
  DATABASE_URL: "postgresql+asyncpg://user:pass@postgres:5432/agent_orchestrator"
  REDIS_URL: "redis://:password@redis:6379/0"
  OPENAI_API_KEY: "sk-..."
  ANTHROPIC_API_KEY: "sk-ant-..."
```

### API Deployment

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: agent-orchestrator
  labels:
    app: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: api
          image: ghcr.io/orchestly-ai/agent-orchestrator/api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: api-secrets
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2000m
              memory: 4Gi
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app: api
                topologyKey: kubernetes.io/hostname
---
# api-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: agent-orchestrator
spec:
  selector:
    app: api
  ports:
    - port: 8000
      targetPort: 8000
  type: ClusterIP
---
# api-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
  namespace: agent-orchestrator
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Worker Deployment

```yaml
# worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker
  namespace: agent-orchestrator
spec:
  replicas: 5
  selector:
    matchLabels:
      app: worker
  template:
    metadata:
      labels:
        app: worker
    spec:
      containers:
        - name: worker
          image: ghcr.io/orchestly-ai/agent-orchestrator/worker:latest
          command: ["celery", "-A", "backend.worker", "worker", "--loglevel=info"]
          envFrom:
            - secretRef:
                name: api-secrets
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 2Gi
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: agent-orchestrator
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.agent-orchestrator.example.com
      secretName: api-tls
  rules:
    - host: api.agent-orchestrator.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8000
```

## Database Migration Job

```yaml
# migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  namespace: agent-orchestrator
spec:
  template:
    spec:
      containers:
        - name: migration
          image: ghcr.io/orchestly-ai/agent-orchestrator/api:latest
          command: ["alembic", "upgrade", "head"]
          envFrom:
            - secretRef:
                name: api-secrets
      restartPolicy: Never
  backoffLimit: 3
```

## Operations

### Deploy

```bash
# Apply all manifests
kubectl apply -f k8s/

# Or with Helm
helm upgrade --install agent-orchestrator ./charts/agent-orchestrator \
  --namespace agent-orchestrator \
  --values values-production.yaml
```

### Scale

```bash
# Manual scaling
kubectl scale deployment api --replicas=5 -n agent-orchestrator

# Check HPA status
kubectl get hpa -n agent-orchestrator
```

### Rolling Update

```bash
# Update image
kubectl set image deployment/api api=ghcr.io/orchestly-ai/agent-orchestrator/api:v1.2.0 \
  -n agent-orchestrator

# Check rollout status
kubectl rollout status deployment/api -n agent-orchestrator

# Rollback if needed
kubectl rollout undo deployment/api -n agent-orchestrator
```

### Logs

```bash
# View logs
kubectl logs -f deployment/api -n agent-orchestrator

# View logs from all pods
kubectl logs -f -l app=api -n agent-orchestrator
```

### Debugging

```bash
# Exec into pod
kubectl exec -it deployment/api -n agent-orchestrator -- /bin/bash

# Port forward for local access
kubectl port-forward svc/api 8000:8000 -n agent-orchestrator

# Describe pod for events
kubectl describe pod -l app=api -n agent-orchestrator
```

## Monitoring

### ServiceMonitor for Prometheus

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-monitor
  namespace: agent-orchestrator
spec:
  selector:
    matchLabels:
      app: api
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### Grafana Dashboard ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards
  namespace: monitoring
  labels:
    grafana_dashboard: "1"
data:
  agent-orchestrator.json: |
    {
      "dashboard": { ... }
    }
```

## Backup CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-backup
  namespace: agent-orchestrator
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:14
              command:
                - /bin/sh
                - -c
                - |
                  pg_dump -h $PGHOST -U $PGUSER $PGDATABASE | \
                  aws s3 cp - s3://backups/agent-orchestrator/$(date +%Y%m%d).sql
              envFrom:
                - secretRef:
                    name: db-credentials
          restartPolicy: OnFailure
```

---

**Next Steps:**
- [AWS Deployment](./aws.md) for EKS setup
- [Azure Deployment](./azure.md) for AKS setup
- [GCP Deployment](./gcp.md) for GKE setup
