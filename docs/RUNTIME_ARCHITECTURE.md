# Runtime Architecture & Deployment Models

> **Purpose**: Define where and how workflows execute, data flows, and deployment options for different customer needs.

---

## Table of Contents
1. [Current Runtime Model](#1-current-runtime-model)
2. [Data Flow & Sovereignty](#2-data-flow--sovereignty)
3. [Deployment Modes](#3-deployment-modes)
4. [Scaling Architecture](#4-scaling-architecture)
5. [Implementation Roadmap](#5-implementation-roadmap)

---

## 1. Current Runtime Model

### Execution Location: **OUR CLOUD INFRASTRUCTURE**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CUSTOMER APPLICATION                              │
│  from agent_orchestrator import Client                               │
│  client = Client(api_key="ao_live_xxx")                             │
│  result = client.workflows.execute(workflow_id, input)              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS REST API
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  OUR SAAS PLATFORM (Multi-Region)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │             API Gateway (FastAPI + Kong)                   │     │
│  │  • API key authentication                                  │     │
│  │  • Rate limiting (per org/key)                             │     │
│  │  • Request validation                                      │     │
│  │  • Geo-routing (latency-based)                             │     │
│  └────────────────────────┬───────────────────────────────────┘     │
│                           │                                          │
│  ┌────────────────────────▼───────────────────────────────────┐     │
│  │         Workflow Executor Service (Python/K8s)             │     │
│  │                                                             │     │
│  │  1. Parse workflow DAG from JSON                           │     │
│  │  2. Validate node dependencies                             │     │
│  │  3. Execute nodes (sequential/parallel)                    │     │
│  │  4. Manage state transitions                               │     │
│  │  5. Handle errors & retries                                │     │
│  │  6. Emit execution events (WebSocket)                      │     │
│  │                                                             │     │
│  │  Located: backend/services/workflow_executor.py            │     │
│  └────────────────────────┬───────────────────────────────────┘     │
│                           │                                          │
│         ┌─────────────────┼─────────────────┐                       │
│         │                 │                 │                       │
│  ┌──────▼──────┐   ┌──────▼──────┐   ┌─────▼─────┐                 │
│  │ LLM Gateway │   │ Task Queue  │   │   Cache   │                 │
│  │  (Router)   │   │   (Redis)   │   │  (Redis)  │                 │
│  └──────┬──────┘   └─────────────┘   └───────────┘                 │
│         │                                                           │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          ├──────► OpenAI API (gpt-4o, gpt-4o-mini)
          ├──────► Anthropic API (claude-3.5-sonnet, claude-3-haiku)
          ├──────► Google API (gemini-1.5-pro, gemini-1.5-flash)
          └──────► DeepSeek API (deepseek-chat)
```

### Key Characteristics

| Aspect | Details |
|--------|---------|
| **Workflow Execution** | Runs entirely on our K8s clusters |
| **Compute Ownership** | We manage and pay for compute |
| **Customer Responsibility** | API integration only |
| **Data Residency** | Workflow definitions in our DB, execution state ephemeral |
| **Scaling** | We handle auto-scaling, load balancing |
| **Monitoring** | Built-in observability (Prometheus/Grafana) |

---

## 2. Data Flow & Sovereignty

### What Stays Where

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA CLASSIFICATION                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  OUR INFRASTRUCTURE (US-East-1, EU-West-1, AP-South-1)              │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ PERSISTENT DATA                                            │     │
│  │ • Workflow definitions (JSON, encrypted)                   │     │
│  │ • Organization configs                                      │     │
│  │ • API keys (hashed)                                        │     │
│  │ • Usage metrics (aggregated)                               │     │
│  │ • Audit logs (90 days)                                     │     │
│  │                                                             │     │
│  │ Storage: PostgreSQL (encrypted at rest)                    │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ EPHEMERAL DATA (Auto-deleted)                              │     │
│  │ • Workflow execution state (TTL: 24 hours)                 │     │
│  │ • Task queue entries (TTL: 1 hour)                         │     │
│  │ • LLM response cache (TTL: 15 minutes)                     │     │
│  │                                                             │     │
│  │ Storage: Redis (in-memory, no disk persistence)            │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                  CUSTOMER INFRASTRUCTURE (BYOS/BYOD)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ SENSITIVE DATA (Never touches our servers)                 │     │
│  │ • Vector embeddings (BYOS - Bring Your Own Storage)        │     │
│  │   - Pinecone, Qdrant, Weaviate, pgvector                   │     │
│  │ • Source documents (BYOD - Bring Your Own Data)            │     │
│  │   - S3, Google Drive, Notion, Confluence                   │     │
│  │ • Customer databases                                        │     │
│  │   - Production databases queried via Tool nodes            │     │
│  │ • API responses                                             │     │
│  │   - Results from customer's internal APIs                  │     │
│  │                                                             │     │
│  │ Connection: Encrypted credentials, API keys stored in our DB│     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow Example: Memory Node Execution

```
Step 1: Customer triggers workflow
  client.workflows.execute("wf_123", {"query": "What is our refund policy?"})

Step 2: Our workflow executor processes Memory node
  ┌─────────────────────────────────────────────────┐
  │ OUR CLOUD (Workflow Executor)                   │
  │ 1. Parse Memory node config                     │
  │    - operation: "query"                         │
  │    - providerId: "customer-pinecone-main"       │
  │    - namespace: "policies"                      │
  │    - query: "{{input.query}}"                   │
  │ 2. Lookup provider credentials (encrypted)      │
  │ 3. Generate embedding (OpenAI)                  │
  └──────────────────┬──────────────────────────────┘
                     │ HTTPS (TLS 1.3)
                     ▼
  ┌─────────────────────────────────────────────────┐
  │ CUSTOMER'S VECTOR DB (Pinecone)                 │
  │ 1. Receive query embedding                      │
  │ 2. Search namespace "policies"                  │
  │ 3. Return top 5 results                         │
  └──────────────────┬──────────────────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────────────────┐
  │ OUR CLOUD (Workflow Executor)                   │
  │ 4. Receive search results                       │
  │ 5. Pass to next node in workflow                │
  │ 6. Return final result to customer              │
  └─────────────────────────────────────────────────┘

KEY: Customer's policy data NEVER leaves their Pinecone instance
```

### Compliance & Security

| Requirement | Implementation |
|-------------|----------------|
| **GDPR** | EU data stored in EU-West-1 only, right to deletion |
| **HIPAA** | PHI stays in customer's infrastructure (BYOS/BYOD) |
| **SOC2** | Encrypted at rest/transit, audit logs, access controls |
| **Data Encryption** | TLS 1.3 in transit, AES-256 at rest |
| **Credential Storage** | Encrypted with customer-specific keys (AWS KMS) |

---

## 3. Deployment Modes

### Mode 1: Managed SaaS (Default)

**Target:** SMBs, startups, fast iteration

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FULLY MANAGED MODEL                              │
└─────────────────────────────────────────────────────────────────────┘

Customer Responsibilities:
  ✓ Integrate SDK (5 lines of code)
  ✓ Configure workflows (visual builder)
  ✓ Provide API keys for BYOS/BYOD

Our Responsibilities:
  ✓ Infrastructure provisioning
  ✓ Kubernetes cluster management
  ✓ Auto-scaling (horizontal + vertical)
  ✓ Multi-region deployment
  ✓ 99.9% uptime SLA
  ✓ Security patches & updates
  ✓ Monitoring & alerting
  ✓ Cost optimization

Cost Model:
  - Platform fee: $49-$299/month
  - LLM pass-through: Cost + 5-10% markup
  - Overage: $1.50-$2.00 per 1K tasks

Limitations:
  ✗ No VPC peering
  ✗ No custom networking
  ✗ No air-gapped deployments
```

### Mode 2: Hybrid Cloud (Enterprise)

**Target:** Mid-market, regulated industries, data sovereignty needs

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HYBRID ARCHITECTURE                             │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐              ┌──────────────────────┐
│   CUSTOMER'S VPC     │              │      OUR CLOUD       │
│   (us-east-1)        │              │    (us-east-1)       │
├──────────────────────┤              ├──────────────────────┤
│                      │              │                      │
│  ┌────────────────┐  │              │  ┌────────────────┐  │
│  │ Agent Runtime  │  │              │  │ Control Plane  │  │
│  │   (K8s pods)   │  │◄────────────►│  │   (FastAPI)    │  │
│  └────────────────┘  │  VPC Peering │  └────────────────┘  │
│                      │  PrivateLink │                      │
│  ┌────────────────┐  │              │  ┌────────────────┐  │
│  │ Workflow Exec  │  │              │  │  LLM Gateway   │  │
│  │    Engine      │  │              │  │   (Router)     │  │
│  └────────────────┘  │              │  └────────────────┘  │
│                      │              │                      │
│  ┌────────────────┐  │              │  ┌────────────────┐  │
│  │ Customer DBs   │  │              │  │ Monitoring     │  │
│  │  (PostgreSQL)  │  │              │  │  (Grafana)     │  │
│  └────────────────┘  │              │  └────────────────┘  │
│                      │              │                      │
└──────────────────────┘              └──────────────────────┘

Data Flow:
1. Customer deploys our agent runtime in their VPC
2. Agent polls our control plane for tasks (HTTPS/gRPC)
3. Execution happens in CUSTOMER'S infrastructure
4. Results sent back to our API
5. LLM calls routed through our gateway (cost optimization)

Customer Responsibilities:
  ✓ Provision K8s cluster in their VPC
  ✓ Deploy our Helm chart
  ✓ Configure network policies
  ✓ Manage compute scaling

Our Responsibilities:
  ✓ Control plane (workflow orchestration)
  ✓ LLM routing & cost tracking
  ✓ Monitoring dashboards
  ✓ Software updates (Helm chart)

Cost Model:
  - Platform fee: $999/month minimum
  - Compute: Customer pays AWS directly
  - LLM pass-through: Cost + 2% markup

Benefits:
  ✓ Data never leaves customer VPC
  ✓ Compliance (HIPAA, SOC2, FedRAMP)
  ✓ Custom networking/security
  ✓ Lower latency (co-located with apps)
```

### Mode 3: Self-Hosted / On-Premise (Regulated)

**Target:** Government, healthcare, finance, air-gapped environments

```
┌─────────────────────────────────────────────────────────────────────┐
│                  SELF-HOSTED DEPLOYMENT                              │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│       CUSTOMER'S INFRASTRUCTURE (On-Prem or Private Cloud)   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │        Full Agent Orchestration Platform               │  │
│  │         (Deployed via Helm Chart)                      │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │                                                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │  │
│  │  │   API GW    │  │  Workflow   │  │ LLM Gateway │    │  │
│  │  │  (FastAPI)  │  │  Executor   │  │  (Local)    │    │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘    │  │
│  │                                                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │  │
│  │  │ PostgreSQL  │  │    Redis    │  │  Monitoring │    │  │
│  │  │  (OLTP)     │  │   (Cache)   │  │  (Grafana)  │    │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘    │  │
│  │                                                         │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │           Customer's Local LLMs (Optional)             │  │
│  │  • Azure OpenAI Service (private endpoint)             │  │
│  │  • Self-hosted models (vLLM, Ollama)                   │  │
│  │  • On-prem GPU clusters                                │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘

Customer Responsibilities:
  ✓ ALL infrastructure (K8s, DBs, storage)
  ✓ Security & compliance
  ✓ Backups & disaster recovery
  ✓ Scaling & performance tuning
  ✓ Software updates (via Helm)

Our Responsibilities:
  ✓ Provide Helm chart
  ✓ Documentation & setup guides
  ✓ Support (SLA-based)
  ✓ Security patches (monthly releases)

Cost Model:
  - Annual license: $50K - $500K (based on usage tier)
  - Support contract: 20% of license annually
  - Custom development: Time & materials

Benefits:
  ✓ Complete control & isolation
  ✓ Air-gapped deployments
  ✓ Zero data exfiltration risk
  ✓ Custom modifications allowed
  ✓ Use local/private LLMs
```

---

## 4. Scaling Architecture

### Horizontal Scaling (More Pods)

```yaml
# Auto-scaling configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: workflow-executor
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: workflow-executor
  minReplicas: 3
  maxReplicas: 50
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
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Percent
        value: 100  # Double pods every 30s if needed
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50  # Scale down slowly
        periodSeconds: 60
```

### Load Distribution

```
Load Tier        | Pods | CPU/Pod | Memory/Pod | Monthly Cost
─────────────────┼──────┼─────────┼────────────┼─────────────
Free (< 1K/mo)   |   1  |  0.5    |   512MB    |    $15
Starter (50K/mo) |   3  |  1.0    |   1GB      |    $120
Pro (500K/mo)    |  10  |  2.0    |   2GB      |    $600
Enterprise       |  50+ |  4.0    |   4GB      |   $3,000+
```

### Geographic Distribution

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MULTI-REGION ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │   CloudFlare    │
                         │ api.agentorch.io│
                         └────────┬────────┘
                                  │
                    Geo-Routing (Latency-Based)
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
┌───────▼────────┐       ┌────────▼────────┐       ┌───────▼────────┐
│   US-EAST-1    │       │   EU-WEST-1     │       │  AP-SOUTH-1    │
│   (Virginia)   │       │   (Ireland)     │       │   (Mumbai)     │
├────────────────┤       ├─────────────────┤       ├────────────────┤
│ Primary        │       │ GDPR Compliant  │       │ Low Latency    │
│ 10 pods        │◄─────►│ 6 pods          │◄─────►│ 4 pods         │
│ ~40% traffic   │ Sync  │ ~35% traffic    │ Sync  │ ~25% traffic   │
└────────────────┘       └─────────────────┘       └────────────────┘
         │                        │                         │
         ▼                        ▼                         ▼
  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
  │ RDS Primary │          │ RDS Replica │          │ RDS Replica │
  │ Multi-AZ    │          │ Read-only   │          │ Read-only   │
  └─────────────┘          └─────────────┘          └─────────────┘

Failover Strategy:
1. Health check every 10s
2. Automatic DNS failover (< 60s)
3. Cross-region read replicas for disaster recovery
4. RPO: 5 minutes, RTO: 15 minutes
```

---

## 5. Implementation Roadmap

### Phase 1: Foundation (Months 1-2) ✅ CURRENT

**Status:** Implemented

- [x] Single-region deployment (us-east-1)
- [x] K8s cluster with 3 nodes
- [x] Workflow executor service
- [x] LLM gateway with routing
- [x] BYOS Memory integration
- [x] BYOD RAG integration
- [x] Basic monitoring (Prometheus)

**Deployment:** Managed SaaS only

### Phase 2: Scale & Reliability (Months 3-4)

**Goal:** Multi-region, production-grade

```yaml
Deliverables:
  Infrastructure:
    - Add EU-West-1 region (GDPR)
    - Configure cross-region replication
    - Implement geo-routing
    - Add data residency controls

  Scaling:
    - Horizontal auto-scaling (HPA)
    - Load balancing improvements
    - Redis cluster (HA)
    - PostgreSQL read replicas

  Observability:
    - Distributed tracing (Jaeger)
    - Advanced alerting
    - Cost dashboards per customer
    - SLA monitoring (99.9% uptime)

Estimated Cost: $25K (infra) + $60K (dev)
```

### Phase 3: Hybrid Cloud (Months 5-6)

**Goal:** Enterprise VPC deployment

```yaml
Deliverables:
  Customer VPC Agent:
    - Create agent SDK with polling model
    - Build Helm chart for customer K8s
    - VPC peering setup automation
    - PrivateLink integration

  Control Plane Updates:
    - Task queue API for remote agents
    - Agent health monitoring
    - Network policy templates
    - Customer-managed secrets

  Documentation:
    - Deployment guides (AWS/Azure/GCP)
    - Network architecture examples
    - Security best practices
    - Terraform modules

Estimated Cost: $40K (dev) + $15K (docs)
```

### Phase 4: Self-Hosted (Months 7-9)

**Goal:** On-premise / air-gapped deployments

```yaml
Deliverables:
  Packaging:
    - Complete Helm chart with all services
    - Local LLM integration (vLLM, Ollama)
    - Air-gap installation support
    - Database migration tools

  Licensing:
    - License key system
    - Usage telemetry (opt-in)
    - Update notification service
    - Support ticketing portal

  Enterprise Features:
    - SSO/SAML integration
    - SCIM provisioning
    - Custom SLAs
    - Dedicated support channel

Estimated Cost: $80K (dev) + $30K (enterprise features)
```

---

## Current Status

| Deployment Mode | Status | Availability |
|----------------|--------|--------------|
| **Managed SaaS** | ✅ Production | Now |
| **Hybrid Cloud** | 🟡 Planned | Q2 2026 |
| **Self-Hosted** | 🔴 Roadmap | Q3 2026 |

---

## FAQs

**Q: Where do my workflows execute?**
A: Currently on our cloud infrastructure (AWS multi-region). Enterprise customers can opt for hybrid deployment where execution happens in their VPC.

**Q: Does my data leave our infrastructure?**
A: Only workflow definitions and metadata. Your actual data (memories, documents, databases) stays in your infrastructure via BYOS/BYOD.

**Q: Can we deploy on-premise?**
A: Yes, planned for Q3 2026 with self-hosted Helm chart. Contact us for early access.

**Q: What about air-gapped deployments?**
A: Supported in self-hosted mode with local LLM integration.

**Q: How do you handle GDPR/HIPAA?**
A: EU data in EU-West-1, PHI stays in customer's infrastructure, full audit logs.

---

*Document Version: 1.0*
*Last Updated: January 2026*
*Owner: Platform Architecture Team*
