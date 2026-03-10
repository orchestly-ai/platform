# BYOC: Bring Your Own Compute - Deployment Guide

> **Purpose**: Enable customers to run agent workflows on their own infrastructure while leveraging our control plane and LLM gateway.

---

## Table of Contents
1. [Overview](#1-overview)
2. [Phase 1: Document Current Architecture](#2-phase-1-document-current-architecture)
3. [Phase 2: Hybrid Mode Implementation](#3-phase-2-hybrid-mode-implementation)
4. [Phase 3: Self-Hosted Package](#4-phase-3-self-hosted-package)
5. [Comparison Matrix](#5-comparison-matrix)

---

## 1. Overview

### Why BYOC?

**Customer Pain Points:**
- **Cost Control**: Workflows consume significant compute (especially long-running agents)
- **Data Sovereignty**: Regulatory requirements (HIPAA, FedRAMP, GDPR)
- **Network Latency**: Workflows need access to internal systems
- **Compliance**: Air-gapped environments (gov, healthcare, finance)
- **Custom Resources**: GPU access, specialized hardware

### BYOC Strategy

```
┌────────────────────────────────────────────────────────────────┐
│                    BYOC PROGRESSION                             │
└────────────────────────────────────────────────────────────────┘

Phase 1: MANAGED (Current)
  Customer → SDK call → OUR cloud executes → Return result
  ✓ Easy setup
  ✗ Vendor lock-in
  ✗ Higher costs

Phase 2: HYBRID (Q2 2026)
  Customer → SDK call → OUR control plane → Customer's K8s executes → Return result
  ✓ Cost control
  ✓ Data stays in VPC
  ✗ Complex setup

Phase 3: SELF-HOSTED (Q3 2026)
  Customer → Local API → Customer's infrastructure → Return result
  ✓ Complete control
  ✓ Air-gapped
  ✗ Customer manages everything
```

---

## 2. Phase 1: Document Current Architecture

**Status:** ✅ COMPLETED (This Document)

**Timeline:** Months 1-2

### 2.1 Current Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MANAGED SAAS ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────┘

Step 1: Customer Application
┌──────────────────────────────────────────────┐
│  from agent_orchestrator import Client       │
│                                              │
│  client = Client(api_key="ao_live_xxx")     │
│                                              │
│  # Execute workflow                          │
│  result = client.workflows.execute(          │
│      workflow_id="wf_customer_support",     │
│      input={"ticket_id": "T-12345"},        │
│      wait=True                               │
│  )                                           │
│                                              │
│  print(result.output)                        │
└──────────────────┬───────────────────────────┘
                   │
                   │ HTTPS POST
                   │ https://api.agentorch.io/v1/workflows/execute
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  OUR CLOUD (AWS us-east-1)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 2: API Gateway (Kong + FastAPI)                               │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ 1. Validate API key (Redis cache → PostgreSQL)            │     │
│  │ 2. Check rate limits (1000 req/s)                         │     │
│  │ 3. Check quota (500K tasks/month)                         │     │
│  │ 4. Log request (Kafka → ClickHouse)                       │     │
│  │ 5. Route to workflow executor                             │     │
│  └────────────────────┬───────────────────────────────────────┘     │
│                       │                                              │
│  Step 3: Workflow Executor (K8s Deployment)                          │
│  ┌────────────────────▼───────────────────────────────────────┐     │
│  │ Pod: workflow-executor-7d8f9c-xxxx                         │     │
│  │ Resources: 2 CPU, 4GB RAM                                  │     │
│  │                                                             │     │
│  │ Class: WorkflowExecutor                                    │     │
│  │ File: backend/services/workflow_executor.py                │     │
│  │                                                             │     │
│  │ def execute_workflow(workflow_id, input):                  │     │
│  │     # 1. Load workflow definition from PostgreSQL          │     │
│  │     workflow = await db.get_workflow(workflow_id)          │     │
│  │                                                             │     │
│  │     # 2. Parse DAG (nodes + edges)                         │     │
│  │     dag = WorkflowDAG(workflow.nodes, workflow.edges)      │     │
│  │                                                             │     │
│  │     # 3. Execute nodes in order                            │     │
│  │     for node in dag.topological_sort():                    │     │
│  │         result = await execute_node(node, context)         │     │
│  │         context[node.id] = result                          │     │
│  │                                                             │     │
│  │     # 4. Return final output                               │     │
│  │     return context[final_node_id]                          │     │
│  └────────────────────┬───────────────────────────────────────┘     │
│                       │                                              │
│  Step 4: Node Execution (per node type)                              │
│  ┌────────────────────▼───────────────────────────────────────┐     │
│  │                                                             │     │
│  │ if node.type == "supervisor":                              │     │
│  │     # Route to cheapest LLM                                │     │
│  │     decision = llm_gateway.route(                          │     │
│  │         strategy="cost_optimized",                         │     │
│  │         model_preference="gpt-4o"                          │     │
│  │     )                                                       │     │
│  │     result = await openai_client.complete(...)             │     │
│  │                                                             │     │
│  │ elif node.type == "memory":                                │     │
│  │     # Query customer's Pinecone                            │     │
│  │     config = await get_provider_config(providerId)         │     │
│  │     embedding = await openai.embeddings(query)             │     │
│  │     results = await pinecone.query(                        │     │
│  │         index=config.index_name,                           │     │
│  │         vector=embedding,                                  │     │
│  │         namespace=namespace                                │     │
│  │     )                                                       │     │
│  │                                                             │     │
│  │ elif node.type == "tool":                                  │     │
│  │     # Call customer's API                                  │     │
│  │     response = await httpx.request(                        │     │
│  │         method=toolConfig.method,                          │     │
│  │         url=toolConfig.url,                                │     │
│  │         headers=toolConfig.headers                         │     │
│  │     )                                                       │     │
│  └────────────────────┬───────────────────────────────────────┘     │
│                       │                                              │
└───────────────────────┼──────────────────────────────────────────────┘
                        │
                        ▼
              Result returned to customer
```

### 2.2 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW MAP                                │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│              1. WORKFLOW DEFINITION STORAGE                       │
├──────────────────────────────────────────────────────────────────┤
│ Location: OUR PostgreSQL (us-east-1)                             │
│ Data: JSON workflow specs, node configs                          │
│ Encryption: AES-256 at rest                                      │
│ Retention: Indefinite (user-controlled)                          │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              2. EXECUTION STATE (EPHEMERAL)                       │
├──────────────────────────────────────────────────────────────────┤
│ Location: OUR Redis (in-memory)                                  │
│ Data: Current execution context, intermediate results            │
│ TTL: 24 hours (auto-deleted)                                     │
│ Persistence: None (lost on pod restart)                          │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              3. EXTERNAL DATA ACCESS                              │
├──────────────────────────────────────────────────────────────────┤
│ Our executor → Customer's vector DB (BYOS)                       │
│ Our executor → Customer's document store (BYOD)                  │
│ Our executor → Customer's APIs (Tool nodes)                      │
│                                                                   │
│ CRITICAL: Customer data NEVER stored in our infrastructure       │
│ We only cache connection credentials (encrypted)                 │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              4. RESULT DELIVERY                                   │
├──────────────────────────────────────────────────────────────────┤
│ Method 1: Synchronous (client.execute(wait=True))                │
│   - Result in HTTP response                                      │
│   - No storage                                                    │
│                                                                   │
│ Method 2: Asynchronous (client.execute(wait=False))              │
│   - Result in PostgreSQL (7 days retention)                      │
│   - Webhook callback (optional)                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 Infrastructure Costs (Per Customer)

| Customer Tier | Workflows/Month | Compute Cost | Our Cost | Their Cost (Managed) |
|---------------|-----------------|--------------|----------|---------------------|
| Free          | 1,000           | $2           | $2       | $0 (included)       |
| Starter       | 50,000          | $80          | $80      | $49/mo (covers it)  |
| Pro           | 500,000         | $600         | $600     | $299/mo (profit)    |
| Enterprise    | 5,000,000       | $4,500       | $4,500   | $2,500/mo (loss!)   |

**Problem:** Enterprise customers are unprofitable on managed SaaS!

---

## 3. Phase 2: Hybrid Mode Implementation

**Status:** 🟡 PLANNED

**Timeline:** Months 3-4 (Q2 2026)

**Goal:** Let customers run workflows in their K8s while using our control plane

### 3.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HYBRID ARCHITECTURE                             │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐              ┌──────────────────────────┐
│   CUSTOMER'S VPC         │              │      OUR CLOUD           │
│   (us-east-1)            │              │    (us-east-1)           │
├──────────────────────────┤              ├──────────────────────────┤
│                          │              │                          │
│  ┌────────────────────┐  │              │  ┌────────────────────┐  │
│  │  Agent Worker      │  │              │  │  Control Plane     │  │
│  │  (Our K8s Chart)   │  │              │  │   API Gateway      │  │
│  │                    │  │              │  │                    │  │
│  │  - Polls for tasks │◄─┼──────────────┼──┤  - Workflow mgmt   │  │
│  │  - Executes nodes  │  │  HTTPS GET   │  │  - Task queue      │  │
│  │  - Reports results │──┼──────────────┼─►│  - Result storage  │  │
│  └────────────────────┘  │  HTTPS POST  │  │                    │  │
│                          │              │  └────────────────────┘  │
│  ┌────────────────────┐  │              │                          │
│  │  Workflow Executor │  │              │  ┌────────────────────┐  │
│  │   (Python worker)  │  │              │  │   LLM Gateway      │  │
│  │                    │  │              │  │   (Cost routing)   │  │
│  │  - Runs in their   │──┼──────────────┼─►│                    │  │
│  │    K8s cluster     │  │  HTTPS       │  │  - OpenAI          │  │
│  │  - Uses their      │  │              │  │  - Anthropic       │  │
│  │    compute         │  │              │  │  - Google          │  │
│  └────────────────────┘  │              │  └────────────────────┘  │
│           │              │              │                          │
│           ▼              │              │  ┌────────────────────┐  │
│  ┌────────────────────┐  │              │  │  Monitoring        │  │
│  │  Customer DBs      │  │              │  │  Dashboard         │  │
│  │  (Direct access)   │  │              │  │  (Shared UI)       │  │
│  └────────────────────┘  │              │  └────────────────────┘  │
│                          │              │                          │
└──────────────────────────┘              └──────────────────────────┘
         │                                           │
         └───────────────────────────────────────────┘
              Network: VPC Peering or PrivateLink
```

### 3.2 How It Works

#### Step 1: Customer Deploys Agent Worker

```bash
# Customer runs in their K8s cluster
helm repo add agentorch https://charts.agentorch.io
helm install agent-worker agentorch/agent-worker \
  --set apiKey=ao_live_customer_xxx \
  --set region=us-east-1 \
  --set replicas=3

# This creates:
# - Deployment: agent-worker (3 pods)
# - ConfigMap: Connection to our API
# - Secret: Customer's API key
```

#### Step 2: Worker Polls for Tasks

```python
# Running in customer's K8s
# File: agent_worker/main.py

import asyncio
import httpx

class AgentWorker:
    def __init__(self, api_key: str, control_plane_url: str):
        self.api_key = api_key
        self.control_plane_url = control_plane_url
        self.client = httpx.AsyncClient()

    async def poll_loop(self):
        """Long-polling for workflow tasks"""
        while True:
            try:
                # Poll our control plane for tasks
                response = await self.client.get(
                    f"{self.control_plane_url}/v1/tasks/poll",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params={
                        "capabilities": ["workflow_execution"],
                        "timeout": 30  # Long-poll for 30s
                    }
                )

                if response.status_code == 200:
                    task = response.json()
                    await self.execute_task(task)

            except Exception as e:
                logger.error(f"Poll failed: {e}")
                await asyncio.sleep(5)

    async def execute_task(self, task: dict):
        """Execute workflow in customer's infrastructure"""
        workflow_id = task['workflow_id']
        input_data = task['input']
        execution_id = task['execution_id']

        try:
            # Execute workflow locally
            executor = WorkflowExecutor(
                workflow_id=workflow_id,
                llm_gateway_url=self.control_plane_url  # Still use our LLM routing
            )

            result = await executor.execute(input_data)

            # Report result back to control plane
            await self.client.post(
                f"{self.control_plane_url}/v1/executions/{execution_id}/complete",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "status": "success",
                    "output": result,
                    "metrics": {
                        "duration_ms": executor.duration_ms,
                        "cost": executor.total_cost
                    }
                }
            )

        except Exception as e:
            # Report failure
            await self.client.post(
                f"{self.control_plane_url}/v1/executions/{execution_id}/fail",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"error": str(e)}
            )
```

#### Step 3: Customer Calls API (Same as Before)

```python
# No change from customer's perspective!
from agent_orchestrator import Client

client = Client(api_key="ao_live_customer_xxx")

# This goes to our API, but executes in their K8s
result = client.workflows.execute(
    workflow_id="wf_customer_support",
    input={"ticket_id": "T-12345"},
    wait=True
)
```

### 3.3 Benefits of Hybrid Mode

| Aspect | Managed SaaS | Hybrid Mode |
|--------|-------------|-------------|
| **Compute Cost** | We pay | Customer pays (AWS direct billing) |
| **Data Residency** | Our region | Customer's VPC |
| **Network Latency** | Higher (cross-region) | Lower (same VPC as customer DBs) |
| **Compliance** | Our SOC2 | Customer's compliance + ours |
| **Setup Complexity** | None | Helm install (30 mins) |
| **Scaling** | We manage | Customer manages (HPA) |

**Example Cost Savings:**
- Enterprise customer: 5M workflows/month
- Managed cost: $4,500/month (our AWS bill)
- Hybrid cost: $0 (customer pays AWS directly)
- Our margin: Same ($2,500/month platform fee)

### 3.4 Implementation Tasks

**Backend Changes:**

```yaml
# New endpoint: Task polling
GET /v1/tasks/poll
  - Long-polling (30s timeout)
  - Return next queued task for org
  - Track worker health

POST /v1/executions/{id}/complete
  - Receive result from worker
  - Update execution status
  - Trigger webhooks

POST /v1/executions/{id}/fail
  - Handle failures
  - Retry logic
  - Alerting

# New model: Worker registration
WorkerModel:
  - worker_id: UUID
  - organization_id: UUID
  - last_heartbeat: datetime
  - capabilities: List[str]
  - region: str
  - version: str
```

**Agent Worker Package:**

```yaml
Repository: agent-worker
Structure:
  - agent_worker/
    - main.py              # Poll loop
    - executor.py          # Workflow executor (copy from backend)
    - llm_client.py        # Call our LLM gateway
    - Dockerfile
  - charts/
    - agent-worker/
      - Chart.yaml
      - values.yaml
      - templates/
        - deployment.yaml
        - configmap.yaml
        - secret.yaml
  - docs/
    - deployment-guide.md
    - network-setup.md
    - troubleshooting.md
```

**Network Configuration:**

```yaml
# Option 1: VPC Peering (AWS)
aws ec2 create-vpc-peering-connection \
  --vpc-id vpc-customer \
  --peer-vpc-id vpc-agentorch \
  --peer-region us-east-1

# Option 2: PrivateLink (AWS)
aws ec2 create-vpc-endpoint-service-configuration \
  --network-load-balancer-arns arn:aws:elasticloadbalancing:...
  --acceptance-required

# Option 3: Public HTTPS (with IP whitelist)
# Worker → https://api.agentorch.io (TLS 1.3)
# No special networking needed
```

**Estimated Effort:** 6 weeks (2 backend devs)

**Cost:** $60,000

---

## 4. Phase 3: Self-Hosted Package

**Status:** 🔴 ROADMAP

**Timeline:** Months 5-6 (Q3 2026)

**Goal:** Full platform deployment in customer's infrastructure (air-gapped)

### 4.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│            CUSTOMER'S INFRASTRUCTURE (On-Prem or Private Cloud)      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │         Agent Orchestration Platform (Helm Chart)             │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │                                                                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │  │
│  │  │   API GW    │  │  Workflow   │  │ LLM Gateway │           │  │
│  │  │  (FastAPI)  │  │  Executor   │  │  (Router)   │           │  │
│  │  │             │  │             │  │             │           │  │
│  │  │ • Auth      │  │ • DAG exec  │  │ • Optional  │           │  │
│  │  │ • Rate Limit│  │ • Node exec │  │   (if using │           │  │
│  │  │ • Validation│  │ • State mgmt│  │    external │           │  │
│  │  └─────────────┘  └─────────────┘  │    LLMs)    │           │  │
│  │                                     └─────────────┘           │  │
│  │                                                                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │  │
│  │  │ PostgreSQL  │  │    Redis    │  │  Dashboard  │           │  │
│  │  │  (Primary)  │  │   (Cache)   │  │  (React)    │           │  │
│  │  │             │  │             │  │             │           │  │
│  │  │ • Workflows │  │ • Sessions  │  │ • Web UI    │           │  │
│  │  │ • Configs   │  │ • Queue     │  │ • Monitoring│           │  │
│  │  │ • Users     │  │ • Locks     │  │             │           │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │  │
│  │                                                                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │  │
│  │  │ Prometheus  │  │   Grafana   │  │  AlertMgr   │           │  │
│  │  │ (Metrics)   │  │ (Dashboards)│  │  (Alerts)   │           │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │  │
│  │                                                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │           LOCAL LLM INTEGRATION (Optional)                     │  │
│  ├───────────────────────────────────────────────────────────────┤  │
│  │                                                                │  │
│  │  Option 1: Azure OpenAI (Private Endpoint)                    │  │
│  │  https://customer.openai.azure.com                            │  │
│  │                                                                │  │
│  │  Option 2: Self-Hosted Models (vLLM/Ollama)                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │  │
│  │  │ vLLM Server │  │ vLLM Server │  │ vLLM Server │           │  │
│  │  │ Llama-3 70B │  │ Mixtral 8x7B│  │ CodeLlama   │           │  │
│  │  │ (A100 GPU)  │  │ (A100 GPU)  │  │ (A100 GPU)  │           │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘           │  │
│  │                                                                │  │
│  │  Option 3: Hybrid (Azure OpenAI + external for cost)          │  │
│  │                                                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

                    NO EXTERNAL DEPENDENCIES
                    ✓ Fully air-gapped capable
                    ✓ All data stays on-prem
                    ✓ No calls to our cloud
```

### 4.2 Helm Chart Structure

```yaml
# Chart.yaml
apiVersion: v2
name: agent-orchestration-platform
description: Enterprise AI Agent Orchestration
version: 1.0.0
appVersion: "2.0.0"

# values.yaml
global:
  domain: agentorch.company.local
  tlsEnabled: true
  imageRegistry: registry.company.local/agentorch

# API Gateway
apiGateway:
  replicas: 3
  resources:
    requests:
      cpu: 1000m
      memory: 2Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20

# Workflow Executor
workflowExecutor:
  replicas: 5
  resources:
    requests:
      cpu: 2000m
      memory: 4Gi
    limits:
      cpu: 4000m
      memory: 8Gi

# PostgreSQL
postgresql:
  enabled: true
  auth:
    postgresPassword: CHANGE_ME
  primary:
    persistence:
      size: 100Gi
  backup:
    enabled: true
    schedule: "0 2 * * *"

# Redis
redis:
  enabled: true
  architecture: standalone
  auth:
    password: CHANGE_ME

# Dashboard
dashboard:
  enabled: true
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: agentorch.company.local

# LLM Gateway (optional)
llmGateway:
  enabled: true
  providers:
    - name: azure-openai
      type: azure_openai
      endpoint: https://company.openai.azure.com
      deployment: gpt-4o
    - name: local-llama
      type: vllm
      endpoint: http://vllm-service:8000
      model: meta-llama/Llama-3-70B

# Monitoring
prometheus:
  enabled: true
grafana:
  enabled: true
  adminPassword: CHANGE_ME
```

### 4.3 Installation Process

```bash
# Step 1: Add Helm repository
helm repo add agentorch https://charts.agentorch.io
# OR for air-gapped: Provide tarball

# Step 2: Create namespace
kubectl create namespace agentorch

# Step 3: Create secrets
kubectl create secret generic agentorch-secrets \
  --from-literal=postgres-password='xxx' \
  --from-literal=redis-password='xxx' \
  --from-literal=jwt-secret='xxx' \
  -n agentorch

# Step 4: Install chart
helm install agentorch-platform agentorch/agent-orchestration-platform \
  --namespace agentorch \
  --set global.domain=agentorch.company.local \
  --set postgresql.auth.existingSecret=agentorch-secrets \
  --set redis.auth.existingSecret=agentorch-secrets \
  --values custom-values.yaml

# Step 5: Wait for deployment
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=agent-orchestration-platform \
  -n agentorch \
  --timeout=600s

# Step 6: Get admin credentials
kubectl get secret agentorch-admin \
  -n agentorch \
  -o jsonpath='{.data.password}' | base64 -d
```

### 4.4 Air-Gap Support

**Problem:** Regulated industries (DoD, healthcare, finance) cannot access internet

**Solution:**

```yaml
# 1. Pre-package all container images
images:
  - registry.company.local/agentorch/api-gateway:2.0.0
  - registry.company.local/agentorch/workflow-executor:2.0.0
  - registry.company.local/agentorch/dashboard:2.0.0
  - registry.company.local/postgres:15
  - registry.company.local/redis:7.2
  - registry.company.local/prometheus:2.45
  - registry.company.local/grafana:10.0

# 2. Bundle Helm chart as tarball
helm package agent-orchestration-platform
# → agent-orchestration-platform-1.0.0.tgz

# 3. Include all dependencies
dependencies:
  - bitnami/postgresql
  - bitnami/redis
  - prometheus-community/prometheus
  - grafana/grafana

# 4. Offline installation script
./install-offline.sh \
  --images-tarball agentorch-images.tar \
  --helm-chart agent-orchestration-platform-1.0.0.tgz \
  --registry registry.company.local
```

### 4.5 Local LLM Integration

```python
# backend/llm/providers/vllm_provider.py

class VLLMProvider:
    """
    Local LLM provider using vLLM server.

    Supports:
    - Llama 3 (8B, 70B, 405B)
    - Mixtral (8x7B, 8x22B)
    - CodeLlama
    - Mistral
    - Any HuggingFace model
    """

    def __init__(self, endpoint: str, model: str):
        self.endpoint = endpoint  # http://vllm-service:8000
        self.model = model        # meta-llama/Llama-3-70B
        self.client = httpx.AsyncClient()

    async def complete(
        self,
        messages: List[Dict],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> LLMResponse:
        """Call local vLLM server"""

        start_time = time.time()

        response = await self.client.post(
            f"{self.endpoint}/v1/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        )

        data = response.json()

        return LLMResponse(
            content=data['choices'][0]['message']['content'],
            model=self.model,
            provider="vllm",
            latency_ms=(time.time() - start_time) * 1000,
            tokens_used=data['usage']['total_tokens'],
            cost=0.0,  # No cost for local models!
            finish_reason=data['choices'][0]['finish_reason']
        )
```

### 4.6 Licensing System

```yaml
# License key format
{
  "license_key": "AO-ENTERPRISE-abc123...",
  "organization": "Acme Corp",
  "tier": "enterprise",
  "max_workflows_per_month": 10000000,
  "max_users": 500,
  "features": [
    "self_hosted",
    "air_gapped",
    "custom_llms",
    "priority_support"
  ],
  "issued_at": "2026-01-15T00:00:00Z",
  "expires_at": "2027-01-15T00:00:00Z",
  "signature": "..."  # RSA signature
}

# Validation (offline-capable)
def validate_license(license_key: str) -> bool:
    """Validate license using embedded public key"""
    try:
        # Decode license
        license_data = jwt.decode(
            license_key,
            PUBLIC_KEY,  # Embedded in binary
            algorithms=["RS256"]
        )

        # Check expiration
        if datetime.now() > license_data['expires_at']:
            return False

        # Check usage limits (from local DB)
        current_usage = get_monthly_usage()
        if current_usage > license_data['max_workflows_per_month']:
            logger.warning("License limit exceeded")
            # Don't block, just warn (customer already paid)

        return True

    except Exception as e:
        logger.error(f"License validation failed: {e}")
        return False
```

### 4.7 Update Mechanism

```bash
# Option 1: Online updates (if internet access)
helm repo update agentorch
helm upgrade agentorch-platform agentorch/agent-orchestration-platform \
  --namespace agentorch \
  --reuse-values

# Option 2: Offline updates (air-gapped)
# 1. Download new release
curl -O https://releases.agentorch.io/v2.1.0/offline-bundle.tar.gz

# 2. Transfer to air-gapped environment
scp offline-bundle.tar.gz customer-server:/tmp/

# 3. Extract and install
tar -xzf offline-bundle.tar.gz
cd agentorch-v2.1.0
./upgrade.sh --namespace agentorch

# 4. Runs database migrations automatically
# 5. Rolling update (zero downtime)
```

### 4.8 Support Model

| Support Tier | Response Time | Channels | Annual Cost |
|--------------|---------------|----------|-------------|
| **Community** | Best effort | GitHub Issues, Docs | Free |
| **Business** | 24 hours | Email, Slack | 20% of license |
| **Enterprise** | 4 hours | Email, Slack, Phone | 20% of license |
| **Mission Critical** | 1 hour (24/7) | Dedicated Slack, Phone, Zoom | 30% of license |

---

## 5. Comparison Matrix

| Feature | Managed SaaS | Hybrid Mode | Self-Hosted |
|---------|--------------|-------------|-------------|
| **Deployment** | None | Helm chart (worker) | Full Helm chart |
| **Compute Location** | Our cloud | Customer K8s | Customer K8s |
| **Data Location** | Our DB (encrypted) | Customer VPC | Customer infrastructure |
| **Network** | Public internet | VPC peering or public | Air-gapped capable |
| **LLM Gateway** | Our service | Our service | Optional (local LLMs) |
| **Control Plane** | Our service | Our service | Customer-managed |
| **Monitoring** | Our Grafana | Shared | Customer-managed |
| **Scaling** | We manage | Customer manages | Customer manages |
| **Updates** | Automatic | Helm upgrade | Manual or scheduled |
| **Cost (Platform)** | $49-$299/mo | $999+/mo | $50K-$500K/year |
| **Cost (Compute)** | Included | Customer pays | Customer pays |
| **Cost (LLM)** | Cost + 5-10% | Cost + 2-5% | Zero (if local) |
| **Setup Time** | 5 minutes | 2-4 hours | 1-2 days |
| **Best For** | SMBs, startups | Mid-market | Enterprise, regulated |
| **Compliance** | SOC2 | SOC2 + customer's | Full customer control |
| **Support** | Community + email | Priority | Dedicated |

---

## Implementation Timeline

```
Month 1-2: Phase 1 - Documentation ✅
  Week 1-2:   RUNTIME_ARCHITECTURE.md
  Week 3-4:   BYOC_DEPLOYMENT.md
  Week 5-6:   INTEGRATION_PATTERNS.md
  Week 7-8:   Update COMMERCIALIZATION_ROADMAP.md

Month 3-4: Phase 2 - Hybrid Mode 🟡
  Week 1-2:   Task polling API
  Week 3-4:   Agent worker package
  Week 5-6:   Helm chart for worker
  Week 7-8:   Testing + docs

Month 5-6: Phase 3 - Self-Hosted 🔴
  Week 1-2:   Full platform Helm chart
  Week 3-4:   Air-gap support
  Week 5-6:   Local LLM integration
  Week 7-8:   Licensing system
  Week 9-10:  Testing + security audit
  Week 11-12: Documentation + training

Total: 6 months, $195K budget
```

---

*Document Version: 1.0*
*Last Updated: January 2026*
*Owner: Platform Architecture Team*
