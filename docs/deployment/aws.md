# AWS Deployment

Deploy the Agent Orchestration Platform on Amazon Web Services using EKS, RDS, and ElastiCache.

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │              AWS Cloud                  │
                         │                                         │
    ┌──────────┐         │  ┌─────────────────────────────────┐   │
    │  Users   │─────────┼──│      Application Load Balancer  │   │
    └──────────┘         │  └───────────────┬─────────────────┘   │
                         │                  │                      │
                         │  ┌───────────────┴───────────────┐     │
                         │  │           EKS Cluster          │     │
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
                         │  │  RDS Aurora │  │ ElastiCache │     │
                         │  │  PostgreSQL │  │    Redis    │     │
                         │  └─────────────┘  └─────────────┘     │
                         │                                         │
                         │  ┌─────────────┐  ┌─────────────┐      │
                         │  │     S3      │  │  Secrets    │      │
                         │  │   Bucket    │  │   Manager   │      │
                         │  └─────────────┘  └─────────────┘      │
                         └─────────────────────────────────────────┘
```

## Prerequisites

- AWS CLI configured
- eksctl installed
- kubectl installed
- Helm 3.0+
- Terraform (optional)

## Quick Start

### 1. Create EKS Cluster

```bash
eksctl create cluster \
  --name agent-orchestrator \
  --region us-west-2 \
  --version 1.28 \
  --nodegroup-name workers \
  --node-type m5.large \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 10 \
  --managed
```

### 2. Create RDS Aurora

```bash
aws rds create-db-cluster \
  --db-cluster-identifier agent-orchestrator-db \
  --engine aurora-postgresql \
  --engine-version 14.6 \
  --master-username admin \
  --master-user-password "$(openssl rand -base64 24)" \
  --vpc-security-group-ids sg-xxx \
  --db-subnet-group-name my-subnet-group \
  --backup-retention-period 7

aws rds create-db-instance \
  --db-instance-identifier agent-orchestrator-db-1 \
  --db-cluster-identifier agent-orchestrator-db \
  --db-instance-class db.r5.large \
  --engine aurora-postgresql
```

### 3. Create ElastiCache Redis

```bash
aws elasticache create-replication-group \
  --replication-group-id agent-orchestrator-redis \
  --replication-group-description "Agent Orchestrator Redis" \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.r5.large \
  --num-cache-clusters 2 \
  --automatic-failover-enabled \
  --security-group-ids sg-xxx \
  --cache-subnet-group-name my-subnet-group
```

### 4. Store Secrets

```bash
aws secretsmanager create-secret \
  --name agent-orchestrator/api-secrets \
  --secret-string '{
    "SECRET_KEY": "'"$(openssl rand -hex 32)"'",
    "DATABASE_URL": "postgresql+asyncpg://admin:password@agent-orchestrator-db.xxx.us-west-2.rds.amazonaws.com:5432/agent_orchestrator",
    "REDIS_URL": "redis://agent-orchestrator-redis.xxx.cache.amazonaws.com:6379/0",
    "OPENAI_API_KEY": "sk-...",
    "ANTHROPIC_API_KEY": "sk-ant-..."
  }'
```

### 5. Deploy Application

```bash
helm install agent-orchestrator ./charts/agent-orchestrator \
  --namespace agent-orchestrator \
  --create-namespace \
  --values values-aws.yaml
```

## Terraform Infrastructure

### main.tf

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "terraform-state-bucket"
    key    = "agent-orchestrator/terraform.tfstate"
    region = "us-west-2"
  }
}

provider "aws" {
  region = var.region
}

# =============================================================================
# VPC
# =============================================================================
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"

  name = "agent-orchestrator-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = false
  enable_dns_hostnames = true

  tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }

  public_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"           = "1"
  }
}

# =============================================================================
# EKS Cluster
# =============================================================================
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "19.0.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.28"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    workers = {
      name           = "workers"
      instance_types = ["m5.large"]
      min_size       = 2
      max_size       = 10
      desired_size   = 3

      labels = {
        role = "worker"
      }
    }
  }

  # Enable IRSA
  enable_irsa = true
}

# =============================================================================
# RDS Aurora PostgreSQL
# =============================================================================
module "rds" {
  source  = "terraform-aws-modules/rds-aurora/aws"
  version = "8.0.0"

  name           = "agent-orchestrator-db"
  engine         = "aurora-postgresql"
  engine_version = "14.6"
  instance_class = "db.r5.large"
  instances = {
    1 = {}
    2 = {}
  }

  vpc_id               = module.vpc.vpc_id
  db_subnet_group_name = module.vpc.database_subnet_group_name
  security_group_rules = {
    vpc_ingress = {
      cidr_blocks = module.vpc.private_subnets_cidr_blocks
    }
  }

  master_username        = "admin"
  create_random_password = true
  database_name          = "agent_orchestrator"

  backup_retention_period = 7
  skip_final_snapshot     = false

  enabled_cloudwatch_logs_exports = ["postgresql"]
}

# =============================================================================
# ElastiCache Redis
# =============================================================================
module "elasticache" {
  source = "terraform-aws-modules/elasticache/aws"

  cluster_id           = "agent-orchestrator-redis"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.r5.large"
  num_cache_clusters   = 2
  parameter_group_name = "default.redis7"

  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.redis.id]

  automatic_failover_enabled = true
  multi_az_enabled          = true
}

# =============================================================================
# S3 Bucket for Artifacts
# =============================================================================
resource "aws_s3_bucket" "artifacts" {
  bucket = "agent-orchestrator-artifacts-${var.environment}"
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

# =============================================================================
# Secrets Manager
# =============================================================================
resource "aws_secretsmanager_secret" "api_secrets" {
  name = "agent-orchestrator/api-secrets"
}

resource "aws_secretsmanager_secret_version" "api_secrets" {
  secret_id = aws_secretsmanager_secret.api_secrets.id
  secret_string = jsonencode({
    SECRET_KEY   = random_password.secret_key.result
    DATABASE_URL = "postgresql+asyncpg://${module.rds.cluster_master_username}:${module.rds.cluster_master_password}@${module.rds.cluster_endpoint}:5432/agent_orchestrator"
    REDIS_URL    = "redis://${module.elasticache.primary_endpoint_address}:6379/0"
  })
}

# =============================================================================
# ALB Ingress Controller IAM
# =============================================================================
module "load_balancer_controller_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "5.0.0"

  role_name                              = "load-balancer-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}
```

### variables.tf

```hcl
variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "agent-orchestrator"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}
```

## Helm Values for AWS

### values-aws.yaml

```yaml
global:
  cloud: aws
  region: us-west-2

api:
  replicaCount: 3

  serviceAccount:
    annotations:
      eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/agent-orchestrator-api

  env:
    - name: AWS_REGION
      value: us-west-2
    - name: SECRET_KEY
      valueFrom:
        secretKeyRef:
          name: api-secrets
          key: SECRET_KEY

# Use external RDS
postgresql:
  enabled: false

externalDatabase:
  host: agent-orchestrator-db.xxx.us-west-2.rds.amazonaws.com
  port: 5432
  database: agent_orchestrator
  existingSecret: api-secrets
  existingSecretPasswordKey: DATABASE_PASSWORD

# Use external ElastiCache
redis:
  enabled: false

externalRedis:
  host: agent-orchestrator-redis.xxx.cache.amazonaws.com
  port: 6379

# AWS ALB Ingress
ingress:
  enabled: true
  className: alb
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-west-2:ACCOUNT_ID:certificate/xxx
    alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS-1-2-2017-01
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/ssl-redirect: "443"
```

## AWS-Specific Features

### Secrets Manager Integration

```yaml
# external-secrets.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: api-secrets
  namespace: agent-orchestrator
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: aws-secrets-manager
  target:
    name: api-secrets
    creationPolicy: Owner
  data:
    - secretKey: SECRET_KEY
      remoteRef:
        key: agent-orchestrator/api-secrets
        property: SECRET_KEY
    - secretKey: DATABASE_URL
      remoteRef:
        key: agent-orchestrator/api-secrets
        property: DATABASE_URL
```

### S3 for Artifacts

```yaml
# In deployment
env:
  - name: AWS_S3_BUCKET
    value: agent-orchestrator-artifacts
  - name: AWS_REGION
    value: us-west-2
```

### CloudWatch Logging

```yaml
# fluentbit configmap
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
data:
  fluent-bit.conf: |
    [OUTPUT]
        Name cloudwatch_logs
        Match *
        region us-west-2
        log_group_name /aws/eks/agent-orchestrator/logs
        log_stream_prefix api-
        auto_create_group true
```

## Cost Optimization

### Spot Instances

```hcl
eks_managed_node_groups = {
  spot_workers = {
    name           = "spot-workers"
    instance_types = ["m5.large", "m5a.large", "m4.large"]
    capacity_type  = "SPOT"
    min_size       = 2
    max_size       = 20
    desired_size   = 5
  }
}
```

### Reserved Instances

- Reserve RDS instances for production
- Reserve ElastiCache nodes for production
- Use Savings Plans for EKS compute

## Monitoring

### CloudWatch Alarms

```hcl
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "agent-orchestrator-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EKS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "High CPU utilization"

  dimensions = {
    ClusterName = var.cluster_name
  }
}
```

## Disaster Recovery

### Cross-Region Replication

```hcl
# S3 cross-region replication
resource "aws_s3_bucket_replication_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  role   = aws_iam_role.replication.arn

  rule {
    id     = "replicate-all"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.artifacts_dr.arn
      storage_class = "STANDARD"
    }
  }
}
```

---

**Next Steps:**
- [Azure Deployment](./azure.md)
- [GCP Deployment](./gcp.md)
