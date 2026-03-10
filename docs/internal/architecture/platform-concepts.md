# Agent Orchestration Platform - Architecture & Concepts Guide

> **Internal Document** - Comprehensive explanation for engineering/product team

## Table of Contents
1. [Documentation Access](#1-documentation-access)
2. [Integration Architecture (How We Connect to External Apps)](#2-integration-architecture)
3. [Customer Journey (How Customers Use Our Platform)](#3-customer-journey)
4. [Authentication & Authorization Explained](#4-authentication--authorization-explained)
5. [Dashboard Views](#5-dashboard-views)
6. [Webhooks vs Integrations](#6-webhooks-vs-integrations)
7. [Webhook Components Deep Dive](#7-webhook-components-deep-dive)

---

## 1. Documentation Access

### Internal Docs (CONFIDENTIAL)
**Location:** `platform/agent-orchestration/docs/internal/`

**NOT served via web** - These are markdown files for internal team only. Access via:
- Git repository
- Internal wiki (if deployed)
- IDE/code editor

**Contains:** Implementation details, algorithms, database schemas, internal APIs

### External Docs (PUBLIC)
**URL:** http://localhost:3001/docs/api-reference/overview

**Served via Docusaurus** at port 3001. Start with:
```bash
cd docs/public
./start-all.sh
```

**Contains:** How to USE our APIs (not how they work internally)

---

## 2. Integration Architecture

### The Problem We Solved
Customers want their AI workflows to connect to Slack, GitHub, Google Drive, Salesforce, etc.
We needed to support 50+ integrations without building each one from scratch.

### Our Approach: Hybrid Integration System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INTEGRATION ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OPTION A: Nango (Third-Party Integration Platform)                         │
│  ────────────────────────────────────────────────────────────────────────   │
│  Pros: 150+ pre-built integrations, handles OAuth complexity                │
│  Cons: Dependency, cost at scale, less control                              │
│                                                                              │
│  OPTION B: Custom Built                                                      │
│  ────────────────────────────────────────────────────────────────────────   │
│  Pros: Full control, no dependency, custom logic                            │
│  Cons: Time to build, maintain OAuth for each provider                      │
│                                                                              │
│  OPTION C: HYBRID (What We Chose)                                           │
│  ────────────────────────────────────────────────────────────────────────   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Integration Manager                               │   │
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────┐  │   │
│  │  │  Custom OAuth     │  │  Nango Connector  │  │  Direct API     │  │   │
│  │  │  (Core partners)  │  │  (Long tail)      │  │  (Simple APIs)  │  │   │
│  │  │                   │  │                   │  │                 │  │   │
│  │  │  - Google         │  │  - 100+ others    │  │  - REST calls   │  │   │
│  │  │  - GitHub         │  │  - Managed by     │  │  - API key      │  │   │
│  │  │  - Slack          │  │    Nango          │  │    based        │  │   │
│  │  │  - Microsoft      │  │                   │  │                 │  │   │
│  │  │  - Salesforce     │  │                   │  │                 │  │   │
│  │  └───────────────────┘  └───────────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Why Hybrid?                                                                 │
│  - Core integrations (Google, Slack, GitHub): We build custom for control   │
│  - Long tail (100+ others): Use Nango to get coverage fast                 │
│  - Simple APIs: Direct API calls with customer's API keys                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Integration Types We Support

| Type | How It Works | Example |
|------|--------------|---------|
| **OAuth Integrations** | User authorizes via OAuth flow | Google, Slack, GitHub |
| **API Key Integrations** | User provides their API key | OpenAI, SendGrid, Twilio |
| **Webhook Integrations** | External service pushes data to us | Stripe payments, GitHub events |

### Code Location
- `backend/integrations/` - Integration manager
- `backend/integrations/oauth/` - OAuth handling
- `backend/integrations/oauth/configs/` - Provider YAML configs

---

## 3. Customer Journey

### How Customers Use Our Platform

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CUSTOMER JOURNEY                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: SIGN UP & GET API KEY                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Customer signs up → Gets Organization ID → Creates API Key                 │
│                                                                              │
│  Dashboard: Settings → API Keys → Create New Key                            │
│  Result: sk-org-xxxxxxxxxxxx (Bearer token for all API calls)               │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│  STEP 2: CHOOSE HOW TO BUILD WORKFLOWS                                      │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  ┌─────────────────────────┐     ┌─────────────────────────┐               │
│  │   OPTION A: Visual      │     │   OPTION B: SDK/API     │               │
│  │   Builder (Dashboard)   │     │   (Programmatic)        │               │
│  │                         │     │                         │               │
│  │   - Drag & drop steps   │     │   - TypeScript SDK      │               │
│  │   - No code required    │     │   - Python SDK          │               │
│  │   - Best for: Simple    │     │   - REST API direct     │               │
│  │     workflows, non-devs │     │   - Best for: Complex   │               │
│  │                         │     │     logic, CI/CD        │               │
│  └─────────────────────────┘     └─────────────────────────┘               │
│                                                                              │
│  Both methods create the same workflow - just different interfaces          │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│  STEP 3: CONNECT EXTERNAL APPS                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Dashboard: Integrations → Connect                                          │
│                                                                              │
│  For OAuth apps (Google, Slack, GitHub):                                    │
│    1. Click "Connect Google"                                                │
│    2. Redirected to Google login                                            │
│    3. Authorize permissions                                                 │
│    4. Redirected back - tokens stored securely                              │
│                                                                              │
│  For API key apps (SendGrid, Twilio):                                       │
│    1. Click "Connect SendGrid"                                              │
│    2. Enter your SendGrid API key                                           │
│    3. Key encrypted and stored                                              │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│  STEP 4: BUILD & DEPLOY WORKFLOWS                                           │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  Workflow example: "When Stripe payment received, update Salesforce,        │
│                     notify Slack, send email"                               │
│                                                                              │
│  Visual Builder:                                                             │
│    [Webhook Trigger] → [LLM Step] → [Salesforce Step] → [Slack Step]       │
│                                                                              │
│  SDK (TypeScript):                                                           │
│    const workflow = client.workflows.create({                               │
│      name: "Payment Handler",                                               │
│      trigger: { type: "webhook", provider: "stripe" },                      │
│      steps: [                                                                │
│        { type: "llm", model: "gpt-4o", prompt: "..." },                     │
│        { type: "integration", app: "salesforce", action: "update" },        │
│        { type: "integration", app: "slack", action: "send_message" }        │
│      ]                                                                       │
│    });                                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Programmatic Workflow Creation

Yes, workflows CAN be created programmatically:

```typescript
// Using TypeScript SDK
import { AgentOrch } from '@agentorch/sdk';

const client = new AgentOrch({ apiKey: 'sk-org-xxx' });

// Create workflow via API
const workflow = await client.workflows.create({
  name: "Customer Support Agent",
  steps: [
    {
      id: "classify",
      type: "llm",
      config: {
        model: "gpt-4o",
        prompt: "Classify this support ticket: {{input.message}}"
      }
    },
    {
      id: "respond",
      type: "llm",
      config: {
        model: "claude-3-sonnet",
        prompt: "Generate response for {{steps.classify.output}}"
      }
    }
  ]
});

// Execute workflow
const execution = await client.workflows.execute(workflow.id, {
  input: { message: "I can't login to my account" }
});
```

---

## 4. Authentication & Authorization Explained

### The Confusion Cleared Up

There are THREE different auth contexts in our system:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              THREE TYPES OF AUTHENTICATION IN OUR SYSTEM                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. API KEYS (Customer → Our Platform)                                      │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  What: Customer authenticates to OUR API                                    │
│  Where: Settings → API Keys                                                 │
│  Format: sk-org-xxxxxxxxxxxxxxxxxxxx                                        │
│  Used for: All API calls to our platform                                    │
│                                                                              │
│  Example:                                                                    │
│    curl -H "Authorization: Bearer sk-org-xxx" \                             │
│         https://api.agentorch.com/v1/workflows                              │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  2. OAUTH APPS (Customer's Users → External Services)                       │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  What: Customer's integration credentials for OAuth providers               │
│  Where: Settings → OAuth Apps                                               │
│  Purpose: Let customer use THEIR OWN OAuth app instead of ours              │
│                                                                              │
│  Default flow (Platform OAuth):                                             │
│    User clicks "Connect Google" → Uses OUR Google OAuth app                 │
│    Consent screen shows "AgentOrch wants to access..."                      │
│                                                                              │
│  Custom flow (Customer's OAuth):                                            │
│    User clicks "Connect Google" → Uses CUSTOMER'S Google OAuth app          │
│    Consent screen shows "Acme Corp wants to access..."                      │
│                                                                              │
│  Why would customer want this?                                               │
│    - White-label: Their branding on consent screen                          │
│    - Control: Their own rate limits                                          │
│    - Compliance: Some enterprises require it                                │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  3. INTEGRATION CREDENTIALS (Our Platform → External Services)              │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  What: Tokens we store after OAuth flow completes                           │
│  Where: Integrations page (stored encrypted)                                │
│  Format: Access tokens, refresh tokens from providers                       │
│  Used for: Making API calls to Google, Slack, etc. on behalf of user        │
│                                                                              │
│  Flow:                                                                       │
│    1. User connects Google                                                  │
│    2. OAuth flow happens (using our or their OAuth app)                     │
│    3. We receive access_token + refresh_token                               │
│    4. Stored encrypted in our database                                      │
│    5. Used when workflow step needs to call Google API                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Visual Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│   CUSTOMER                    OUR PLATFORM                        │
│   ────────                    ────────────                        │
│                                                                   │
│   ┌─────────┐   API Key      ┌─────────────────────────────────┐ │
│   │ Their   │ ─────────────► │                                 │ │
│   │ Backend │   (sk-org-xx)  │      Agent Orchestration        │ │
│   │ or SDK  │                │           Platform               │ │
│   └─────────┘                │                                 │ │
│                              │  ┌─────────────────────────────┐│ │
│                              │  │ Integration Credentials     ││ │
│   ┌─────────┐   OAuth Flow   │  │ (access tokens for          ││ │
│   │ Their   │ ◄────────────► │  │  Google, Slack, etc.)       ││ │
│   │ Users   │                │  └──────────────┬──────────────┘│ │
│   └─────────┘                │                 │               │ │
│                              └─────────────────┼───────────────┘ │
│                                                │                  │
│                                                ▼                  │
│                              ┌─────────────────────────────────┐ │
│                              │  External Services              │ │
│                              │  (Google, Slack, GitHub, etc.)  │ │
│                              └─────────────────────────────────┘ │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Dashboard Views

### Yes, These Are Customer Views

| URL | What It Is | Who Uses It |
|-----|------------|-------------|
| `localhost:3000/dashboard` | Main dashboard - workflows, executions | Customer |
| `localhost:3000/workflows` | Workflow list and builder | Customer |
| `localhost:3000/integrations` | Connect external apps | Customer |
| `localhost:3000/webhooks` | View incoming webhooks, configure handlers | Customer |
| `localhost:3000/settings` | Organization settings | Customer (admin) |
| `localhost:3000/costs` | Usage & cost tracking | Customer |

### Settings Page Breakdown

**Settings → API Keys**
- Creates keys for customer to call OUR API
- Format: `sk-org-xxxxxxxxx`
- Used in: `Authorization: Bearer sk-org-xxx`

**Settings → OAuth Apps**
- OPTIONAL: Customer configures THEIR OWN OAuth credentials
- If not configured: We use our platform's OAuth apps
- If configured: Their branding appears on consent screens

**Settings → Team**
- Invite team members
- Set roles/permissions

**Settings → Billing**
- Payment methods
- Usage history

---

## 6. Webhooks vs Integrations

### Key Difference

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WEBHOOKS vs INTEGRATIONS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INTEGRATIONS (We PULL data)                                                │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Direction: Our Platform → External Service                                 │
│  Trigger: Our code initiates the request                                    │
│  Use case: "Get Google Calendar events", "Send Slack message"               │
│                                                                              │
│  Example flow:                                                               │
│    1. Workflow step: "Get events from Google Calendar"                      │
│    2. Our platform calls Google Calendar API                                │
│    3. Google returns data                                                   │
│    4. Workflow continues with that data                                     │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  WEBHOOKS (External service PUSHES data)                                    │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  Direction: External Service → Our Platform                                 │
│  Trigger: External event happens                                            │
│  Use case: "When Stripe payment received", "When GitHub PR opened"          │
│                                                                              │
│  Example flow:                                                               │
│    1. Customer pays on Stripe                                               │
│    2. Stripe sends webhook to our URL                                       │
│    3. Our platform receives the event                                       │
│    4. Handler triggers workflow                                             │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  COMPARISON TABLE                                                            │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  │ Aspect        │ Integrations          │ Webhooks                 │       │
│  │───────────────│───────────────────────│──────────────────────────│       │
│  │ Direction     │ Outbound (we call)    │ Inbound (they call)      │       │
│  │ Trigger       │ Our workflow step     │ External event           │       │
│  │ Auth method   │ OAuth / API Key       │ Signature verification   │       │
│  │ Data flow     │ Request → Response    │ Push notification        │       │
│  │ Use case      │ "Do something"        │ "React to something"     │       │
│  │ Example       │ Send Slack message    │ Stripe payment received  │       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Webhook Components Deep Dive

### The Three Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WEBHOOK SYSTEM COMPONENTS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         PROVIDERS                                    │   │
│  │  ────────────────────────────────────────────────────────────────   │   │
│  │                                                                      │   │
│  │  What: External services that can send webhooks to us                │   │
│  │  Examples: Stripe, GitHub, Slack, Discord, HubSpot                   │   │
│  │                                                                      │   │
│  │  Configuration per provider:                                         │   │
│  │    - Webhook URL: https://api.agentorch.com/api/webhooks/stripe     │   │
│  │    - Secret key: For signature verification (whsec_xxx)              │   │
│  │    - Enabled/Disabled: Toggle processing on/off                      │   │
│  │                                                                      │   │
│  │  Customer action:                                                    │   │
│  │    1. Go to Webhooks → Providers                                     │   │
│  │    2. Click "Configure" for Stripe                                   │   │
│  │    3. Copy webhook URL to Stripe Dashboard                           │   │
│  │    4. Enter webhook secret from Stripe                               │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          EVENTS                                      │   │
│  │  ────────────────────────────────────────────────────────────────   │   │
│  │                                                                      │   │
│  │  What: Individual webhook payloads we receive                        │   │
│  │  Examples: payment.succeeded, push, message.created                  │   │
│  │                                                                      │   │
│  │  Event record contains:                                              │   │
│  │    - event_id: Unique identifier                                     │   │
│  │    - provider: "stripe"                                              │   │
│  │    - event_type: "payment.succeeded"                                 │   │
│  │    - payload: The actual data from Stripe                            │   │
│  │    - status: received, completed, failed                             │   │
│  │    - received_at: Timestamp                                          │   │
│  │                                                                      │   │
│  │  Customer action:                                                    │   │
│  │    1. Go to Webhooks → Events                                        │   │
│  │    2. See all received webhooks                                      │   │
│  │    3. Click to see payload details                                   │   │
│  │    4. Retry failed events                                            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         HANDLERS                                     │   │
│  │  ────────────────────────────────────────────────────────────────   │   │
│  │                                                                      │   │
│  │  What: Rules that define what to DO when an event is received        │   │
│  │                                                                      │   │
│  │  Handler types:                                                      │   │
│  │    - workflow: Trigger a workflow with event data as input           │   │
│  │    - http: Forward to another URL                                    │   │
│  │    - log: Just log for debugging                                     │   │
│  │                                                                      │   │
│  │  Pattern matching:                                                   │   │
│  │    - "stripe.payment.succeeded" → Exact match                        │   │
│  │    - "stripe.*" → All Stripe events                                  │   │
│  │    - "github.push" → Only push events                                │   │
│  │                                                                      │   │
│  │  Customer action:                                                    │   │
│  │    1. Go to Webhooks → Handlers                                      │   │
│  │    2. Click "Add Handler"                                            │   │
│  │    3. Set event pattern: "stripe.payment.succeeded"                  │   │
│  │    4. Choose action: Trigger workflow "process-payment"              │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Complete Webhook Flow Example

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE WEBHOOK FLOW                                     │
│                                                                              │
│  Scenario: Customer receives Stripe payment, wants to update CRM            │
│                                                                              │
│  SETUP (One-time):                                                           │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  1. Provider Config:                                                        │
│     Dashboard → Webhooks → Providers → Configure Stripe                     │
│     - Copy webhook URL to Stripe Dashboard                                  │
│     - Enter Stripe webhook secret                                           │
│                                                                              │
│  2. Handler Config:                                                         │
│     Dashboard → Webhooks → Handlers → Add Handler                           │
│     - Event pattern: "stripe.payment.succeeded"                             │
│     - Handler type: workflow                                                │
│     - Workflow: "update-salesforce-deal"                                    │
│                                                                              │
│  RUNTIME (Every payment):                                                    │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐ │
│  │ Customer │     │    Stripe    │     │ Our Platform │     │ Salesforce │ │
│  │   Pays   │────►│   Payment    │────►│   Webhook    │────►│   Update   │ │
│  │          │     │   Success    │     │   Handler    │     │   Deal     │ │
│  └──────────┘     └──────────────┘     └──────────────┘     └────────────┘ │
│                                                                              │
│  Detailed flow:                                                              │
│                                                                              │
│  1. Customer completes payment on your checkout                             │
│  2. Stripe processes payment                                                │
│  3. Stripe sends webhook to: agentorch.com/api/webhooks/stripe             │
│  4. We verify signature using configured secret                             │
│  5. Event stored with type "stripe.payment.succeeded"                       │
│  6. Handler matches pattern "stripe.payment.succeeded"                      │
│  7. Workflow "update-salesforce-deal" triggered                             │
│  8. Workflow uses Salesforce integration to update deal                     │
│  9. Event marked as "completed"                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

### External Docs (for customers)
- API Overview: http://localhost:3001/docs/api-reference/overview
- Webhooks Guide: http://localhost:3001/docs/api-reference/webhooks
- OAuth Settings: http://localhost:3001/docs/api-reference/oauth-settings
- Cost Tracking: http://localhost:3001/docs/api-reference/cost

### Internal Docs (for team)
- `docs/internal/architecture/overview.md` - System architecture
- `docs/internal/architecture/hybrid-oauth.md` - OAuth implementation
- `docs/internal/architecture/multi-llm-routing.md` - LLM routing
- `docs/internal/api/internal-endpoints.md` - Internal APIs

### Code Locations
- OAuth handling: `backend/integrations/oauth/`
- Webhook processing: `backend/webhooks/`
- Integration manager: `backend/integrations/`
- Dashboard: `dashboard/src/pages/`
