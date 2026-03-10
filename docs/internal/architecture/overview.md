# System Architecture Overview

> **CONFIDENTIAL - INTERNAL USE ONLY**

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Agent Orchestration Platform                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Dashboard  │  │   SDK/CLI    │  │  Webhooks    │  │  External    │    │
│  │   (React)    │  │  (TypeScript)│  │  Receiver    │  │    APIs      │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│  ═══════╧═════════════════╧═════════════════╧═════════════════╧═══════════  │
│                              API Gateway (FastAPI)                          │
│  ═══════════════════════════════════════════════════════════════════════    │
│         │                 │                 │                 │             │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐    │
│  │   Workflow   │  │   LLM        │  │   OAuth      │  │   Cost       │    │
│  │   Engine     │  │   Gateway    │  │   Manager    │  │   Tracker    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐    │
│  │  Execution   │  │  Multi-LLM   │  │   Hybrid     │  │   Token      │    │
│  │   Store      │  │   Router     │  │  OAuth Store │  │   Ledger     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                         PostgreSQL / SQLite Database                        │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. LLM Gateway (Our Primary Moat)

The LLM Gateway provides a unified interface to 7+ LLM providers with intelligent routing.

**Key Differentiators:**
- **Intelligent Routing**: Cost, latency, and capability-based model selection
- **Automatic Fallback**: Seamless failover across providers
- **Token Normalization**: Consistent token counting across providers
- **Rate Limit Management**: Per-organization rate limiting with burst handling

**Implementation:** `backend/llm/gateway.py`, `backend/llm/router.py`

### 2. Hybrid OAuth System (Competitive Advantage)

Unique approach combining platform-managed and customer-managed credentials.

**How it works:**
```
┌─────────────────────────────────────────────────────────────┐
│                    OAuth Request Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Request comes in for OAuth provider (e.g., Google)      │
│                          │                                   │
│                          ▼                                   │
│  2. Check OrganizationOAuthConfig table                     │
│     ├── Has custom config? → Use customer's credentials     │
│     └── No custom config? → Use platform defaults           │
│                          │                                   │
│                          ▼                                   │
│  3. Build OAuth URL with appropriate credentials            │
│                          │                                   │
│                          ▼                                   │
│  4. Customer can switch to their own app anytime            │
│     (No code changes, just config update)                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Implementation:** `backend/integrations/oauth/`

### 3. Webhook Processing Engine

Unified webhook receiver with provider-specific signature verification.

**Supported Verification Methods:**
- HMAC-SHA256 (Stripe, GitHub)
- Stripe-specific (timestamp + signature)
- Slack signing secrets
- Custom header-based

**Implementation:** `backend/webhooks/`

### 4. Workflow Execution Engine

DAG-based workflow execution with advanced features.

**Capabilities:**
- Parallel step execution
- Conditional branching
- Human-in-the-loop approvals
- Time-travel debugging (replay any step)
- A/B testing of workflow variants

**Implementation:** `backend/orchestrator/`

## Database Schema (Core Tables)

```sql
-- Workflow definitions
CREATE TABLE workflows (
    workflow_id VARCHAR(255) PRIMARY KEY,
    organization_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    dag_definition JSONB NOT NULL,
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Execution tracking with full state
CREATE TABLE workflow_executions (
    execution_id VARCHAR(255) PRIMARY KEY,
    workflow_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    step_states JSONB,  -- Full state for time-travel
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Token ledger for precise cost tracking
CREATE TABLE token_usage_ledger (
    id SERIAL PRIMARY KEY,
    organization_id VARCHAR(255) NOT NULL,
    execution_id VARCHAR(255),
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Organization-specific pricing
CREATE TABLE organization_pricing_config (
    config_id VARCHAR(255) PRIMARY KEY,
    organization_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    input_cost_per_million DECIMAL(10,4) NOT NULL,
    output_cost_per_million DECIMAL(10,4) NOT NULL,
    effective_date TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);
```

## Service Communication

All internal services communicate via:
1. **Direct function calls** (within same process)
2. **Async task queues** (for background processing)
3. **Event sourcing** (for execution state)

No microservices boundary for core components - keeps latency minimal.

## Security Model

1. **API Authentication**: Bearer tokens with org-scoped permissions
2. **OAuth Secrets**: Encrypted at rest, never logged
3. **Webhook Secrets**: Per-provider, per-organization isolation
4. **Audit Logging**: All admin actions logged

## Performance Characteristics

| Operation | Target Latency | Notes |
|-----------|---------------|-------|
| LLM Request (cached routing) | <10ms overhead | Routing decision cached |
| Workflow Step Execution | <50ms overhead | Plus LLM latency |
| Webhook Processing | <100ms | Including signature verification |
| Cost Calculation | <5ms | In-memory pricing lookup |
