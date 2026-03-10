# GCP Deployment

Deploy the Agent Orchestration Platform on Google Cloud Platform using GKE, Cloud SQL, and Memorystore.

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │         Google Cloud Platform           │
                         │                                         │
    ┌──────────┐         │  ┌─────────────────────────────────┐   │
    │  Users   │─────────┼──│      Cloud Load Balancer        │   │
    └──────────┘         │  └───────────────┬─────────────────┘   │
                         │                  │                      │
                         │  ┌───────────────┴───────────────┐     │
                         │  │          GKE Cluster           │     │
                         │  │  ┌─────┐ ┌─────┐ ┌─────┐      │     │
                         │  │  │ API │ │ API │ │ API │      │     │
                         │  │  └──┬──┘ └──┬──┘ └──┬──┘      │     │
                         │  │     │       │       │          │     │
                         │  │  ┌──┴───────┴───────┴──┐      │     │
                         │  │  │      Workers        │      │     │
                         │  │  └─────────────────────┘      │     │
                         │  └───────────────────────────────┘     │
                         │                  │                      │
                         │    ┌─────────────┴─────────────┐       │
                         │    │                           │       │
                         │  ┌─▼───────────┐  ┌───────────▼─┐     │
                         │  │  Cloud SQL  │  │ Memorystore │     │
                         │  │  PostgreSQL │  │    Redis    │     │
                         │  └─────────────┘  └─────────────┘     │
                         │                                         │
                         │  ┌─────────────┐  ┌─────────────┐      │
                         │  │    GCS      │  │   Secret    │      │
                         │  │   Bucket    │  │   Manager   │      │
                         │  └─────────────┘  └─────────────┘      │
                         └─────────────────────────────────────────┘
```

## Prerequisites

- gcloud CLI installed and configured
- kubectl installed
- Helm 3.0+
- GCP project with billing enabled

## Quick Start

### 1. Set Project

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1
export ZONE=us-central1-a

gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION
```

### 2. Enable APIs

```bash
gcloud services enable \
  container.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com \
  servicenetworking.googleapis.com
```

### 3. Create GKE Cluster

```bash
gcloud container clusters create agent-orchestrator \
  --region $REGION \
  --num-nodes 3 \
  --machine-type e2-standard-4 \
  --enable-autoscaling \
  --min-nodes 2 \
  --max-nodes 10 \
  --enable-ip-alias \
  --workload-pool=$PROJECT_ID.svc.id.goog

# Get credentials
gcloud container clusters get-credentials agent-orchestrator --region $REGION
```

### 4. Create Cloud SQL PostgreSQL

```bash
# Create instance
gcloud sql instances create agent-orchestrator-db \
  --database-version=POSTGRES_14 \
  --tier=db-custom-2-4096 \
  --region=$REGION \
  --availability-type=REGIONAL \
  --storage-size=100GB \
  --storage-auto-increase

# Set root password
gcloud sql users set-password postgres \
  --instance=agent-orchestrator-db \
  --password="$(openssl rand -base64 24)"

# Create database
gcloud sql databases create agent_orchestrator \
  --instance=agent-orchestrator-db
```

### 5. Create Memorystore Redis

```bash
gcloud redis instances create agent-orchestrator-redis \
  --size=5 \
  --region=$REGION \
  --redis-version=redis_7_0 \
  --tier=standard
```

### 6. Store Secrets

```bash
# Create secrets
echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create SECRET_KEY --data-file=-

echo -n "postgresql+asyncpg://postgres:password@/agent_orchestrator?host=/cloudsql/$PROJECT_ID:$REGION:agent-orchestrator-db" | \
  gcloud secrets create DATABASE_URL --data-file=-

REDIS_HOST=$(gcloud redis instances describe agent-orchestrator-redis --region=$REGION --format='value(host)')
echo -n "redis://$REDIS_HOST:6379/0" | \
  gcloud secrets create REDIS_URL --data-file=-
```

### 7. Deploy Application

```bash
helm install agent-orchestrator ./charts/agent-orchestrator \
  --namespace agent-orchestrator \
  --create-namespace \
  --values values-gcp.yaml
```

## Terraform Infrastructure

### main.tf

```hcl
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "terraform-state-bucket"
    prefix = "agent-orchestrator"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# VPC Network
# =============================================================================
resource "google_compute_network" "main" {
  name                    = "agent-orchestrator-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "gke" {
  name          = "gke-subnet"
  ip_cidr_range = "10.0.0.0/20"
  region        = var.region
  network       = google_compute_network.main.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

# Private service connection for Cloud SQL
resource "google_compute_global_address" "private_ip" {
  name          = "private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

# =============================================================================
# GKE Cluster
# =============================================================================
resource "google_container_cluster" "main" {
  name     = "agent-orchestrator"
  location = var.region

  network    = google_compute_network.main.name
  subnetwork = google_compute_subnetwork.gke.name

  # Enable Autopilot for easier management
  # Or use standard mode with node pools
  enable_autopilot = false

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
  }

  # Remove default node pool
  remove_default_node_pool = true
  initial_node_count       = 1
}

resource "google_container_node_pool" "primary" {
  name       = "primary-pool"
  location   = var.region
  cluster    = google_container_cluster.main.name
  node_count = 3

  autoscaling {
    min_node_count = 2
    max_node_count = 10
  }

  node_config {
    machine_type = "e2-standard-4"
    disk_size_gb = 100
    disk_type    = "pd-ssd"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}

# =============================================================================
# Cloud SQL PostgreSQL
# =============================================================================
resource "google_sql_database_instance" "main" {
  name             = "agent-orchestrator-db"
  database_version = "POSTGRES_14"
  region           = var.region

  depends_on = [google_service_networking_connection.private_vpc]

  settings {
    tier              = "db-custom-2-4096"
    availability_type = "REGIONAL"
    disk_size         = 100
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "02:00"
      location                       = var.region
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "main" {
  name     = "agent_orchestrator"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "main" {
  name     = "app"
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}

# =============================================================================
# Memorystore Redis
# =============================================================================
resource "google_redis_instance" "main" {
  name           = "agent-orchestrator-redis"
  tier           = "STANDARD_HA"
  memory_size_gb = 5
  region         = var.region

  authorized_network = google_compute_network.main.id

  redis_version = "REDIS_7_0"

  display_name = "Agent Orchestrator Redis"
}

# =============================================================================
# Cloud Storage
# =============================================================================
resource "google_storage_bucket" "artifacts" {
  name     = "${var.project_id}-agent-orchestrator-artifacts"
  location = var.region

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# =============================================================================
# Secret Manager
# =============================================================================
resource "google_secret_manager_secret" "api_secrets" {
  secret_id = "agent-orchestrator-secrets"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "api_secrets" {
  secret = google_secret_manager_secret.api_secrets.id

  secret_data = jsonencode({
    SECRET_KEY   = random_password.secret_key.result
    DATABASE_URL = "postgresql+asyncpg://${google_sql_user.main.name}:${google_sql_user.main.password}@/${google_sql_database.main.name}?host=/cloudsql/${google_sql_database_instance.main.connection_name}"
    REDIS_URL    = "redis://${google_redis_instance.main.host}:${google_redis_instance.main.port}/0"
  })
}

# =============================================================================
# Service Account for Workload Identity
# =============================================================================
resource "google_service_account" "api" {
  account_id   = "agent-orchestrator-api"
  display_name = "Agent Orchestrator API"
}

resource "google_service_account_iam_binding" "api_workload_identity" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[agent-orchestrator/api]"
  ]
}

# Grant access to secrets
resource "google_secret_manager_secret_iam_member" "api_secrets" {
  secret_id = google_secret_manager_secret.api_secrets.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

# Grant access to Cloud SQL
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}
```

## Helm Values for GCP

### values-gcp.yaml

```yaml
global:
  cloud: gcp
  region: us-central1
  projectId: your-project-id

api:
  replicaCount: 3

  serviceAccount:
    annotations:
      iam.gke.io/gcp-service-account: agent-orchestrator-api@your-project-id.iam.gserviceaccount.com

  # Cloud SQL Proxy sidecar
  extraContainers:
    - name: cloud-sql-proxy
      image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.1.0
      args:
        - "--structured-logs"
        - "--port=5432"
        - "your-project-id:us-central1:agent-orchestrator-db"
      securityContext:
        runAsNonRoot: true
      resources:
        requests:
          cpu: 100m
          memory: 128Mi

  env:
    - name: DATABASE_URL
      value: "postgresql+asyncpg://app:password@localhost:5432/agent_orchestrator"
    - name: REDIS_URL
      valueFrom:
        secretKeyRef:
          name: redis-url
          key: url

# Use external Cloud SQL
postgresql:
  enabled: false

# Use external Memorystore
redis:
  enabled: false

externalRedis:
  host: 10.0.0.3  # Memorystore IP
  port: 6379

# GKE Ingress
ingress:
  enabled: true
  className: gce
  annotations:
    kubernetes.io/ingress.global-static-ip-name: agent-orchestrator-ip
    networking.gke.io/managed-certificates: api-cert
    kubernetes.io/ingress.class: "gce"
  hosts:
    - host: api.agent-orchestrator.example.com
      paths:
        - path: /
          pathType: Prefix

# Managed Certificate
managedCertificate:
  enabled: true
  domains:
    - api.agent-orchestrator.example.com
```

## GCP-Specific Features

### Workload Identity

```yaml
# kubernetes service account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api
  namespace: agent-orchestrator
  annotations:
    iam.gke.io/gcp-service-account: agent-orchestrator-api@PROJECT_ID.iam.gserviceaccount.com
```

### Secret Manager Integration

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: gcp-secrets
spec:
  provider: gcp
  parameters:
    secrets: |
      - resourceName: "projects/PROJECT_ID/secrets/agent-orchestrator-secrets/versions/latest"
        path: "secrets.json"
```

### Cloud SQL Auth Proxy

```yaml
# Sidecar configuration
containers:
  - name: cloud-sql-proxy
    image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.1.0
    args:
      - "--structured-logs"
      - "--auto-iam-authn"
      - "PROJECT_ID:REGION:INSTANCE_NAME"
    securityContext:
      runAsNonRoot: true
```

### GKE Managed Certificate

```yaml
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: api-cert
spec:
  domains:
    - api.agent-orchestrator.example.com
```

## Cost Optimization

### Preemptible/Spot VMs

```hcl
resource "google_container_node_pool" "spot" {
  name       = "spot-pool"
  cluster    = google_container_cluster.main.name

  autoscaling {
    min_node_count = 0
    max_node_count = 20
  }

  node_config {
    spot         = true
    machine_type = "e2-standard-4"
  }
}
```

### Committed Use Discounts

- Commit to 1 or 3 years for significant discounts
- Apply to GKE nodes, Cloud SQL, and Memorystore

## Monitoring

### Cloud Monitoring

```bash
# Enable GKE monitoring
gcloud container clusters update agent-orchestrator \
  --region $REGION \
  --enable-managed-prometheus
```

### Custom Dashboards

```yaml
# monitoring configmap
apiVersion: v1
kind: ConfigMap
metadata:
  name: dashboard-config
data:
  dashboard.json: |
    {
      "displayName": "Agent Orchestrator",
      "mosaicLayout": {...}
    }
```

## Disaster Recovery

### Cross-Region Replication

```hcl
# Cloud SQL replica
resource "google_sql_database_instance" "replica" {
  name                 = "agent-orchestrator-db-replica"
  master_instance_name = google_sql_database_instance.main.name
  region               = "us-east1"

  replica_configuration {
    failover_target = true
  }
}
```

---

**Next Steps:**
- [Kubernetes Guide](./kubernetes.md)
- [Docker Compose Guide](./docker-compose.md)
