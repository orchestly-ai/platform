# Azure Deployment

Deploy the Agent Orchestration Platform on Microsoft Azure using AKS, Azure Database for PostgreSQL, and Azure Cache for Redis.

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │            Azure Cloud                  │
                         │                                         │
    ┌──────────┐         │  ┌─────────────────────────────────┐   │
    │  Users   │─────────┼──│     Azure Application Gateway   │   │
    └──────────┘         │  └───────────────┬─────────────────┘   │
                         │                  │                      │
                         │  ┌───────────────┴───────────────┐     │
                         │  │         AKS Cluster            │     │
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
                         │  │ Azure DB    │  │ Azure Cache │     │
                         │  │ PostgreSQL  │  │   Redis     │     │
                         │  └─────────────┘  └─────────────┘     │
                         │                                         │
                         │  ┌─────────────┐  ┌─────────────┐      │
                         │  │ Blob Storage│  │  Key Vault  │      │
                         │  └─────────────┘  └─────────────┘      │
                         └─────────────────────────────────────────┘
```

## Prerequisites

- Azure CLI installed and configured
- kubectl installed
- Helm 3.0+
- Azure subscription with required permissions

## Quick Start

### 1. Create Resource Group

```bash
az group create \
  --name agent-orchestrator-rg \
  --location eastus
```

### 2. Create AKS Cluster

```bash
az aks create \
  --resource-group agent-orchestrator-rg \
  --name agent-orchestrator-aks \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-managed-identity \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials \
  --resource-group agent-orchestrator-rg \
  --name agent-orchestrator-aks
```

### 3. Create Azure Database for PostgreSQL

```bash
az postgres flexible-server create \
  --resource-group agent-orchestrator-rg \
  --name agent-orchestrator-db \
  --location eastus \
  --admin-user adminuser \
  --admin-password "$(openssl rand -base64 24)" \
  --sku-name Standard_D2s_v3 \
  --tier GeneralPurpose \
  --storage-size 128 \
  --version 14 \
  --high-availability ZoneRedundant

# Create database
az postgres flexible-server db create \
  --resource-group agent-orchestrator-rg \
  --server-name agent-orchestrator-db \
  --database-name agent_orchestrator
```

### 4. Create Azure Cache for Redis

```bash
az redis create \
  --resource-group agent-orchestrator-rg \
  --name agent-orchestrator-redis \
  --location eastus \
  --sku Premium \
  --vm-size P1 \
  --enable-non-ssl-port false \
  --minimum-tls-version 1.2
```

### 5. Create Key Vault and Secrets

```bash
# Create Key Vault
az keyvault create \
  --resource-group agent-orchestrator-rg \
  --name agent-orchestrator-kv \
  --location eastus

# Store secrets
az keyvault secret set \
  --vault-name agent-orchestrator-kv \
  --name SECRET-KEY \
  --value "$(openssl rand -hex 32)"

az keyvault secret set \
  --vault-name agent-orchestrator-kv \
  --name DATABASE-URL \
  --value "postgresql+asyncpg://adminuser:password@agent-orchestrator-db.postgres.database.azure.com:5432/agent_orchestrator"

az keyvault secret set \
  --vault-name agent-orchestrator-kv \
  --name REDIS-URL \
  --value "rediss://:password@agent-orchestrator-redis.redis.cache.windows.net:6380/0"
```

### 6. Deploy Application

```bash
helm install agent-orchestrator ./charts/agent-orchestrator \
  --namespace agent-orchestrator \
  --create-namespace \
  --values values-azure.yaml
```

## Terraform Infrastructure

### main.tf

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "terraform-state-rg"
    storage_account_name = "tfstateaccount"
    container_name       = "tfstate"
    key                  = "agent-orchestrator.tfstate"
  }
}

provider "azurerm" {
  features {}
}

# =============================================================================
# Resource Group
# =============================================================================
resource "azurerm_resource_group" "main" {
  name     = "agent-orchestrator-rg"
  location = var.location
}

# =============================================================================
# Virtual Network
# =============================================================================
resource "azurerm_virtual_network" "main" {
  name                = "agent-orchestrator-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_subnet" "aks" {
  name                 = "aks-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_subnet" "database" {
  name                 = "database-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.2.0/24"]

  delegation {
    name = "postgres-delegation"
    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
    }
  }
}

# =============================================================================
# AKS Cluster
# =============================================================================
resource "azurerm_kubernetes_cluster" "main" {
  name                = "agent-orchestrator-aks"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = "agent-orchestrator"

  default_node_pool {
    name                = "default"
    node_count          = 3
    vm_size             = "Standard_D4s_v3"
    vnet_subnet_id      = azurerm_subnet.aks.id
    enable_auto_scaling = true
    min_count           = 2
    max_count           = 10
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
  }

  key_vault_secrets_provider {
    secret_rotation_enabled = true
  }

  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  }
}

# =============================================================================
# Azure Database for PostgreSQL
# =============================================================================
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "agent-orchestrator-db"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "14"
  delegated_subnet_id    = azurerm_subnet.database.id
  private_dns_zone_id    = azurerm_private_dns_zone.postgres.id
  administrator_login    = "adminuser"
  administrator_password = random_password.db_password.result
  zone                   = "1"

  storage_mb = 131072
  sku_name   = "GP_Standard_D2s_v3"

  high_availability {
    mode                      = "ZoneRedundant"
    standby_availability_zone = "2"
  }

  backup_retention_days        = 7
  geo_redundant_backup_enabled = true
}

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "agent_orchestrator"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

# =============================================================================
# Azure Cache for Redis
# =============================================================================
resource "azurerm_redis_cache" "main" {
  name                = "agent-orchestrator-redis"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  capacity            = 1
  family              = "P"
  sku_name            = "Premium"
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"

  redis_configuration {
    maxmemory_policy = "allkeys-lru"
  }
}

# =============================================================================
# Key Vault
# =============================================================================
resource "azurerm_key_vault" "main" {
  name                = "agent-orchestrator-kv"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  purge_protection_enabled = true
}

resource "azurerm_key_vault_secret" "db_password" {
  name         = "DATABASE-PASSWORD"
  value        = random_password.db_password.result
  key_vault_id = azurerm_key_vault.main.id
}

# =============================================================================
# Storage Account
# =============================================================================
resource "azurerm_storage_account" "artifacts" {
  name                     = "agentorchartifacts"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "GRS"

  blob_properties {
    versioning_enabled = true
  }
}

# =============================================================================
# Log Analytics
# =============================================================================
resource "azurerm_log_analytics_workspace" "main" {
  name                = "agent-orchestrator-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# =============================================================================
# Application Gateway (optional)
# =============================================================================
resource "azurerm_application_gateway" "main" {
  name                = "agent-orchestrator-appgw"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  sku {
    name     = "WAF_v2"
    tier     = "WAF_v2"
    capacity = 2
  }

  gateway_ip_configuration {
    name      = "gateway-ip-config"
    subnet_id = azurerm_subnet.appgw.id
  }

  frontend_port {
    name = "https"
    port = 443
  }

  frontend_ip_configuration {
    name                 = "frontend-ip"
    public_ip_address_id = azurerm_public_ip.appgw.id
  }

  # Additional configuration...
}
```

## Helm Values for Azure

### values-azure.yaml

```yaml
global:
  cloud: azure
  region: eastus

api:
  replicaCount: 3

  podLabels:
    aadpodidbinding: agent-orchestrator

  env:
    - name: AZURE_KEYVAULT_NAME
      value: agent-orchestrator-kv
    - name: SECRET_KEY
      valueFrom:
        secretKeyRef:
          name: api-secrets
          key: SECRET_KEY

# Use external Azure Database
postgresql:
  enabled: false

externalDatabase:
  host: agent-orchestrator-db.postgres.database.azure.com
  port: 5432
  database: agent_orchestrator
  sslMode: require

# Use external Azure Cache for Redis
redis:
  enabled: false

externalRedis:
  host: agent-orchestrator-redis.redis.cache.windows.net
  port: 6380
  tls: true

# Azure Application Gateway Ingress
ingress:
  enabled: true
  className: azure-application-gateway
  annotations:
    appgw.ingress.kubernetes.io/ssl-redirect: "true"
    appgw.ingress.kubernetes.io/backend-protocol: "http"
  hosts:
    - host: api.agent-orchestrator.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: api-tls
      hosts:
        - api.agent-orchestrator.example.com

# Azure Storage for artifacts
storage:
  type: azure
  azure:
    storageAccountName: agentorchartifacts
    containerName: artifacts
```

## Azure-Specific Features

### Managed Identity Integration

```yaml
# aad-pod-identity binding
apiVersion: aadpodidentity.k8s.io/v1
kind: AzureIdentity
metadata:
  name: agent-orchestrator-identity
spec:
  type: 0
  resourceID: /subscriptions/.../resourcegroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/agent-orchestrator
  clientID: <client-id>
---
apiVersion: aadpodidentity.k8s.io/v1
kind: AzureIdentityBinding
metadata:
  name: agent-orchestrator-binding
spec:
  azureIdentity: agent-orchestrator-identity
  selector: agent-orchestrator
```

### Key Vault CSI Driver

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: azure-keyvault-secrets
spec:
  provider: azure
  parameters:
    usePodIdentity: "true"
    keyvaultName: "agent-orchestrator-kv"
    objects: |
      array:
        - |
          objectName: SECRET-KEY
          objectType: secret
        - |
          objectName: DATABASE-URL
          objectType: secret
    tenantId: "<tenant-id>"
```

### Azure Monitor Integration

```bash
# Enable Container Insights
az aks enable-addons \
  --resource-group agent-orchestrator-rg \
  --name agent-orchestrator-aks \
  --addons monitoring \
  --workspace-resource-id /subscriptions/.../resourceGroups/.../providers/Microsoft.OperationalInsights/workspaces/agent-orchestrator-logs
```

## Cost Optimization

### Azure Reserved Instances

- Reserve AKS nodes
- Reserve PostgreSQL compute
- Reserve Redis capacity

### Spot Instances

```hcl
resource "azurerm_kubernetes_cluster_node_pool" "spot" {
  name                  = "spot"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = "Standard_D4s_v3"
  priority              = "Spot"
  eviction_policy       = "Delete"
  spot_max_price        = -1

  enable_auto_scaling = true
  min_count           = 0
  max_count           = 20
}
```

## Disaster Recovery

### Geo-Replication

```hcl
# PostgreSQL read replica
resource "azurerm_postgresql_flexible_server" "replica" {
  name                   = "agent-orchestrator-db-replica"
  resource_group_name    = azurerm_resource_group.dr.name
  location               = "westus"
  source_server_id       = azurerm_postgresql_flexible_server.main.id
  create_mode           = "Replica"
}
```

---

**Next Steps:**
- [GCP Deployment](./gcp.md)
- [Kubernetes Guide](./kubernetes.md)
