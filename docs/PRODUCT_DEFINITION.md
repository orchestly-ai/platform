# Agent Orchestration - Product Definition

## What We Are

**Agent Orchestration** is a **Control Plane Platform** for building, deploying, and operating AI agent systems at scale.

### Tagline
> "The Control Plane for AI Agents"

### Core Value Proposition
> "Bring your own LLMs, your own data, your own compute. We provide the intelligence layer that makes them work together."

---

## Product Classification

| Category | Are We This? | Explanation |
|----------|--------------|-------------|
| Library/SDK | Partially | We have SDKs, but also hosted services |
| API | Partially | We expose APIs, but also have UI |
| Infrastructure | **No** | We don't provide compute/storage |
| Platform | **Yes** | We tie everything together |
| Control Plane | **Yes** | We orchestrate, don't execute |

---

## The Kubernetes Analogy

```
┌───────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│   Kubernetes:                      Agent Orchestration:                   │
│   ────────────                     ────────────────────                   │
│   • Schedules containers           • Schedules workflows                  │
│   • Manages state                  • Manages agent state                  │
│   • Routes traffic                 • Routes LLM requests                  │
│   • Monitors health                • Monitors executions                  │
│   • Doesn't run your code          • Doesn't run your LLMs               │
│   • Control plane + workers        • Control plane + workers              │
│                                                                            │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Platform Philosophy: BYOX (Bring Your Own X)

We follow a "control plane" philosophy where we provide the orchestration intelligence, and customers bring their own infrastructure:

| Component | Provider | Rationale |
|-----------|----------|-----------|
| **Control Plane** | Us (always) | This IS our product |
| **LLM APIs** | Customer (BYOK) | We're model-agnostic |
| **Compute Workers** | Customer (BYOC) or Us | Flexibility by tier |
| **Memory/Vector DB** | Customer (BYOS) | We don't store their data |
| **RAG Documents** | Customer (BYOD) | We don't store their data |
| **Workflow Definitions** | Us | Orchestration metadata |
| **Execution History** | Us | Observability data |
| **Audit Logs** | Us (short-term) + Customer (long-term) | Compliance flexibility |

### BYOX Acronyms
- **BYOK** - Bring Your Own Keys (LLM API keys)
- **BYOS** - Bring Your Own Storage (Vector DBs for memory)
- **BYOD** - Bring Your Own Data (Document stores for RAG)
- **BYOC** - Bring Your Own Compute (Workflow execution workers)

---

## What We Provide vs. What Customers Provide

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RESPONSIBILITY SPLIT                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  AGENT ORCHESTRATION (Us)                CUSTOMER INFRASTRUCTURE            │
│  ────────────────────────                ───────────────────────            │
│                                                                              │
│  ┌─────────────────────────┐            ┌─────────────────────────┐        │
│  │  DESIGN                 │            │  LLM PROVIDERS          │        │
│  │  • Visual workflow      │            │  • OpenAI API           │        │
│  │  • Templates            │            │  • Anthropic API        │        │
│  │  • SDK/CLI              │            │  • Google AI            │        │
│  └─────────────────────────┘            │  • Self-hosted LLMs     │        │
│                                         └─────────────────────────┘        │
│  ┌─────────────────────────┐                                               │
│  │  ORCHESTRATE            │            ┌─────────────────────────┐        │
│  │  • Multi-agent coord    │            │  STORAGE                │        │
│  │  • State management     │            │  • Pinecone             │        │
│  │  • Scheduling           │            │  • Weaviate             │        │
│  │  • Webhooks/triggers    │            │  • S3/GCS               │        │
│  └─────────────────────────┘            │  • PostgreSQL           │        │
│                                         └─────────────────────────┘        │
│  ┌─────────────────────────┐                                               │
│  │  OPTIMIZE               │            ┌─────────────────────────┐        │
│  │  • Smart LLM routing    │            │  COMPUTE (Optional)     │        │
│  │  • A/B testing          │            │  • AWS EC2/Lambda       │        │
│  │  • Cost optimization    │            │  • GCP Cloud Run        │        │
│  │  • Caching              │            │  • Kubernetes           │        │
│  └─────────────────────────┘            │  • On-premise           │        │
│                                         └─────────────────────────┘        │
│  ┌─────────────────────────┐                                               │
│  │  OBSERVE                │                                               │
│  │  • Debugging            │                                               │
│  │  • Audit logs           │                                               │
│  │  • Metrics              │                                               │
│  │  • Cost tracking        │                                               │
│  └─────────────────────────┘                                               │
│                                                                              │
│  ┌─────────────────────────┐                                               │
│  │  GOVERN                 │                                               │
│  │  • HITL approvals       │                                               │
│  │  • Budgets              │                                               │
│  │  • Rate limits          │                                               │
│  │  • Access control       │                                               │
│  └─────────────────────────┘                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Models

### 1. SaaS (Recommended for most)
- We host the control plane
- Customer connects their LLM keys, storage, and optionally compute
- Fastest time to value

### 2. Hybrid
- Our control plane (cloud-hosted)
- Their data plane (customer infrastructure)
- Good for data-sensitive workloads

### 3. Self-Hosted (Enterprise)
- Customer runs everything
- We provide the software
- Maximum control and isolation

---

## Tiered Pricing Model

| Tier | Control Plane | Workflow Execution | Storage | Best For |
|------|--------------|-------------------|---------|----------|
| **Free** | Hosted | Platform (limited) | Platform (limited) | Evaluation |
| **Pro** | Hosted | Platform (metered) | BYOS | Startups |
| **Enterprise** | Hosted or Self | BYOC | BYOS | Large orgs |

---

## Competitive Positioning

```
                              MORE OPINIONATED
                                    ▲
                                    │
          LangChain ────────────────┼───────────────► Agent Frameworks
          (Library)                 │                 (Full stack)
                                    │
                        ┌───────────┴───────────┐
                        │                       │
                        │  AGENT ORCHESTRATION  │
                        │                       │
                        │  Control Plane for    │
                        │  AI Agents            │
                        │                       │
                        └───────────────────────┘
                                    │
          Temporal ─────────────────┼───────────────► Airflow
          (Generic workflows)       │                 (Data pipelines)
                                    │
                                    ▼
                              LESS OPINIONATED

  ◄─────────────────────────────────┼─────────────────────────────────────►
  INFRASTRUCTURE                    │                         APPLICATION
  (Run anything)                    │                         (Pre-built)
```

### Comparable Products

| Product | What They Are | How We Compare |
|---------|---------------|----------------|
| **Temporal** | Workflow orchestration | Similar, but AI-agent focused |
| **Prefect** | Data pipeline orchestration | Similar, but AI-agent focused |
| **LangSmith** | LLM observability | We have this + orchestration |
| **Weights & Biases** | ML experiment tracking | We have this + workflow execution |
| **Kubernetes** | Container orchestration | Architectural inspiration |

---

## Feature Categories

| Category | Features | Value |
|----------|----------|-------|
| **Design** | Visual Builder, Templates, SDK | Create workflows fast |
| **Orchestrate** | Scheduling, Webhooks, Multi-agent | Coordinate complex systems |
| **Optimize** | LLM Routing, A/B Testing, Caching | Reduce costs, improve quality |
| **Observe** | Debugger, Audit Logs, Metrics | Understand what's happening |
| **Govern** | HITL, Budgets, Rate Limits | Control and compliance |

---

## Key Differentiators

1. **Model Agnostic** - Works with any LLM provider
2. **BYOX Philosophy** - No vendor lock-in on infrastructure
3. **Visual + Code** - Both no-code and SDK approaches
4. **AI-Native Observability** - Time-travel debugging, A/B testing for AI
5. **Enterprise Ready** - HITL, audit logs, SSO, RBAC
6. **Cost Optimization** - Smart routing, token tracking, budgets

---

## Summary

**Agent Orchestration is the control plane that makes AI agents production-ready.**

We don't compete with LLM providers, cloud providers, or database vendors. We complement them by providing the orchestration layer that ties everything together.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                         YOUR AI AGENT STACK                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    AGENT ORCHESTRATION                               │   │
│  │                    (Control Plane)                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│           ┌────────────────────────┼────────────────────────┐              │
│           ▼                        ▼                        ▼              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │  LLM Providers  │    │  Your Storage   │    │  Your Compute   │        │
│  │  (BYOK)         │    │  (BYOS/BYOD)    │    │  (BYOC)         │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```
