# Integration Architecture

## Overview

This document describes the architecture for:
1. **Declarative Integration System** - Add integrations via config files
2. **Hybrid Customer Auth** - Direct API keys + Nango OAuth
3. **Webhooks** - Receive events from external apps

---

## Understanding Data Flow Direction

A key architectural concept is the **direction of data flow** between Agent Orchestration and external apps:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA FLOW DIRECTIONS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────┐                      ┌─────────────────────┐       │
│  │                     │     INTEGRATIONS     │                     │       │
│  │                     │     (Outbound)       │                     │       │
│  │  Agent              │  ─────────────────►  │  External App       │       │
│  │  Orchestration      │  You call their API  │  (Slack, Stripe,    │       │
│  │                     │                      │   GitHub, etc.)     │       │
│  │                     │     WEBHOOKS         │                     │       │
│  │                     │     (Inbound)        │                     │       │
│  │                     │  ◄─────────────────  │                     │       │
│  │                     │  They call your URL  │                     │       │
│  └─────────────────────┘                      └─────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Integrations (Outbound - You → Them)

**Purpose:** Send data or commands TO external applications

| Aspect | Description |
|--------|-------------|
| **Direction** | Agent Orchestration → External App |
| **Initiator** | Your workflow/agent triggers the action |
| **Timing** | Synchronous (usually) - you wait for response |
| **Examples** | Send Slack message, create GitHub issue, charge Stripe customer |
| **Authentication** | You store API keys/OAuth tokens to access their API |

```python
# Example: Integration (outbound)
result = await integrations.execute(
    provider="slack",
    action="send_message",
    parameters={"channel": "#alerts", "text": "Hello!"}
)
# You initiated this, you wait for response
```

### Webhooks (Inbound - Them → You)

**Purpose:** Receive events or notifications FROM external applications

| Aspect | Description |
|--------|-------------|
| **Direction** | External App → Agent Orchestration |
| **Initiator** | External app triggers based on their events |
| **Timing** | Asynchronous - events arrive when they happen |
| **Examples** | Stripe payment completed, GitHub PR merged, Slack message received |
| **Authentication** | They provide a secret; you verify incoming requests |

```python
# Example: Webhook (inbound)
@webhook_handler("stripe", "payment_intent.succeeded")
async def handle_payment(event: StripeEvent):
    # Stripe initiated this, you process asynchronously
    await process_successful_payment(event.data)
```

### Real-World Example: Slack

Most apps need **BOTH** integrations and webhooks:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE SLACK FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INTEGRATION (Outbound)                                                     │
│  ─────────────────────                                                      │
│  Your agent decides to post an update:                                      │
│  Agent Orchestration ──► Slack API ──► Message appears in #channel          │
│                                                                              │
│  WEBHOOK (Inbound)                                                          │
│  ────────────────────                                                       │
│  User reacts with 👍 to the message:                                        │
│  Slack ──► Your Webhook URL ──► Agent Orchestration processes reaction      │
│                                                                              │
│  User types /approve command:                                               │
│  Slack ──► Your Webhook URL ──► Agent triggers approval workflow            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sync vs Async Messaging

| Pattern | Type | Who Waits? | Example |
|---------|------|------------|---------|
| **Sync Integration** | Outbound | You wait for response | POST message, get message_id back |
| **Async Webhook** | Inbound | No one waits | Receive "user reacted" event |
| **Sync-ish Webhook** | Inbound | They wait briefly | Slack slash command expects quick reply |

### Scoping: Per-Organization Isolation

**Important:** Both integrations and webhooks are scoped per-organization:

- **Your Stripe webhooks** only receive events for YOUR Stripe account
- **Your Slack integration** only accesses YOUR Slack workspace
- Other organizations on the platform cannot see your events or access your apps

```
Organization A                      Organization B
─────────────                       ─────────────
Stripe Account: acct_A              Stripe Account: acct_B
Webhook Secret: whsec_A             Webhook Secret: whsec_B
     │                                    │
     ▼                                    ▼
Receives events for                 Receives events for
their customers only                their customers only
```

## Goals

- **For Platform Team**: Add new integrations in 10-30 minutes via YAML config
- **For Customers**: Connect integrations with one click (OAuth) or paste (API key)
- **Maintainability**: Minimal code per integration, centralized logic
- **Flexibility**: Support both simple HTTP APIs and complex SDK-based integrations

---

## Part 1: Declarative Integration System

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Integration Manager                           │
├─────────────────────────────────────────────────────────────────┤
│  load_integrations()  →  IntegrationRegistry                    │
│  execute_action()     →  Routes to HTTP or SDK executor         │
│  get_integration()    →  Returns integration config             │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
      │   discord   │ │    slack    │ │   openai    │
      │   .yaml     │ │    .yaml    │ │   .yaml     │
      └─────────────┘ └─────────────┘ └─────────────┘
              │               │               │
              ▼               ▼               ▼
      ┌─────────────────────────────────────────────┐
      │           Action Executor Router            │
      ├─────────────────────────────────────────────┤
      │  action.type == "http"  →  HTTPExecutor     │
      │  action.type == "sdk"   →  SDKExecutor      │
      └─────────────────────────────────────────────┘
```

### Integration Config Schema (YAML)

```yaml
# integrations/discord.yaml
id: discord
name: Discord
display_name: Discord
description: Send messages to Discord channels
category: communication
icon_url: /icons/discord.svg

# Authentication configuration
auth:
  type: bot_token  # Options: api_key, bot_token, oauth2, basic
  fields:
    - name: bot_token
      label: Bot Token
      type: password
      required: true
      help: "Get from Discord Developer Portal > Bot > Token"

# Available actions
actions:
  send_message:
    name: Send Message
    description: Send a message to a Discord channel
    type: http  # Simple HTTP call

    # HTTP configuration
    method: POST
    url: "https://discord.com/api/v10/channels/{{parameters.channel_id}}/messages"
    headers:
      Authorization: "Bot {{auth.bot_token}}"
      Content-Type: "application/json"
    body:
      content: "{{parameters.content}}"

    # Parameter schema
    parameters:
      - name: channel_id
        label: Channel ID
        type: string
        required: true
      - name: content
        label: Message Content
        type: string
        required: true
        supports_templates: true  # Allow {{variable}} syntax

    # Response mapping
    response:
      message_id: "$.id"
      channel_id: "$.channel_id"

  create_thread:
    name: Create Thread
    description: Create a new thread in a channel
    type: sdk  # Complex - needs SDK
    handler: integrations.discord.create_thread
    parameters:
      - name: channel_id
        type: string
        required: true
      - name: name
        type: string
        required: true

# Triggers (optional)
triggers:
  message_received:
    name: Message Received
    description: Triggered when a message is received
    type: webhook
    webhook_path: /webhooks/discord/message
```

### Directory Structure

```
backend/
├── integrations/
│   ├── __init__.py
│   ├── registry.py          # Integration registry & loader
│   ├── executor.py          # Action execution logic
│   ├── http_executor.py     # HTTP-based action executor
│   ├── sdk_executor.py      # SDK-based action executor
│   ├── schema.py            # Pydantic models for config
│   └── configs/             # YAML config files
│       ├── discord.yaml
│       ├── slack.yaml
│       ├── openai.yaml
│       ├── anthropic.yaml
│       ├── groq.yaml
│       ├── github.yaml
│       └── gmail.yaml
└── shared/
    └── integrations/        # SDK implementations (for complex actions)
        ├── discord.py
        ├── slack.py
        └── ...
```

---

## Part 2: Hybrid Customer Auth

### Auth Flow by Type

```
┌─────────────────────────────────────────────────────────────────┐
│                    Customer clicks "Connect"                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  Check auth.type from │
                  │  integration config   │
                  └───────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌───────────┐      ┌───────────┐      ┌───────────┐
    │  api_key  │      │  oauth2   │      │ bot_token │
    │ bot_token │      │           │      │           │
    └───────────┘      └───────────┘      └───────────┘
          │                   │                   │
          ▼                   ▼                   ▼
    ┌───────────┐      ┌───────────┐      ┌───────────┐
    │  Show     │      │  Redirect │      │  Show     │
    │  Input    │      │  to Nango │      │  Input    │
    │  Modal    │      │  OAuth    │      │  Modal    │
    └───────────┘      └───────────┘      └───────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                  ┌───────────────────────┐
                  │   ConnectionProvider  │
                  │   stores credentials  │
                  └───────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  integration_         │
                  │  installations table  │
                  └───────────────────────┘
```

### Connect UI Component

```tsx
// ConnectIntegration component
<ConnectIntegration
  integrationId="discord"
  onConnected={(credentials) => { ... }}
/>

// Internally:
// 1. Fetches integration config
// 2. Based on auth.type:
//    - api_key/bot_token: Shows <CredentialInputModal />
//    - oauth2: Calls Nango.auth() or redirects
// 3. On success: Stores via ConnectionProvider
// 4. Shows "Connected" status
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (This Session)

1. **Integration Schema** (`schema.py`)
   - Pydantic models for integration config
   - Validation logic

2. **Integration Registry** (`registry.py`)
   - Load YAML configs from directory
   - Provide lookup by ID

3. **HTTP Executor** (`http_executor.py`)
   - Template variable substitution
   - Make HTTP requests
   - Response mapping

4. **Example Configs**
   - discord.yaml
   - openai.yaml
   - slack.yaml

### Phase 2: Customer Auth (Next Session)

5. **Connect UI Component**
   - CredentialInputModal for API keys
   - Nango integration for OAuth

6. **Backend Auth Endpoints**
   - POST /integrations/{id}/connect
   - GET /integrations/{id}/status

### Phase 3: Polish (Future)

7. **More integrations**
8. **SDK fallback for complex actions**
9. **Webhook triggers**

---

## API Changes

### New Endpoints

```
GET  /api/integrations                    # List available integrations
GET  /api/integrations/{id}               # Get integration details
GET  /api/integrations/{id}/auth-config   # Get auth requirements
POST /api/integrations/{id}/connect       # Connect (API key or OAuth callback)
GET  /api/integrations/{id}/status        # Check connection status
DELETE /api/integrations/{id}/disconnect  # Revoke connection

POST /api/integrations/{id}/execute       # Execute an action
```

### Database Changes

None required - uses existing `integration_installations` table.

---

## Security Considerations

1. **Credential Storage**: Encrypted at rest (existing CredentialManager)
2. **OAuth Tokens**: Stored in Nango (when using OAuth)
3. **API Keys**: Validated before storage
4. **Template Injection**: Sanitize user inputs in templates
5. **Rate Limiting**: Per-integration rate limits

---

## Success Metrics

- Time to add new integration: < 30 minutes
- Customer connection success rate: > 95%
- Integration execution reliability: > 99%
