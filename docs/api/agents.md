# Agents API

The Agents API provides enterprise-grade agent registration, governance, and management for organizations with 50+ AI agents.

## Base URLs

```
/api/v1/agents           # Basic agent operations
/api/v1/agent-registry   # Enterprise governance & policies
```

## Endpoints Overview

### Agent Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/agents` | Register a new agent |
| `GET` | `/agents` | List all agents |
| `GET` | `/agents/{id}` | Get agent details |
| `PUT` | `/agents/{id}` | Update agent |
| `DELETE` | `/agents/{id}` | Deregister agent |
| `POST` | `/agents/{id}/heartbeat` | Update heartbeat |

### Agent Registry & Governance

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/agent-registry/agents` | Register with governance |
| `POST` | `/agent-registry/agents/search` | Search with filters |
| `GET` | `/agent-registry/agents/duplicates` | Find duplicate capabilities |
| `GET` | `/agent-registry/stats` | Registry statistics |

### Approvals

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/agent-registry/approvals` | Request approval |
| `POST` | `/agent-registry/approvals/{id}/decide` | Approve/reject |
| `GET` | `/agent-registry/approvals/pending` | Pending approvals |

### Policies

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/agent-registry/policies` | Create policy |
| `GET` | `/agent-registry/policies` | List policies |
| `POST` | `/agent-registry/agents/{id}/check-compliance` | Check compliance |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/agent-registry/analytics/cost-by-team` | Cost breakdown by team |
| `GET` | `/agent-registry/analytics/top-expensive` | Top expensive agents |
| `GET` | `/agent-registry/analytics/pii-access-audit` | PII access audit |

---

## Register Agent

Register a new AI agent in the platform.

```
POST /api/v1/agents
```

### Request Body

```json
{
  "name": "code-review-agent",
  "capabilities": [
    {"name": "code_review", "confidence": 0.95},
    {"name": "bug_detection", "confidence": 0.88}
  ],
  "framework": "langchain",
  "version": "1.0.0",
  "description": "Automated code review agent",
  "cost_per_hour": 0.50,
  "metadata": {
    "team": "engineering",
    "environment": "production"
  }
}
```

### Capabilities

| Capability | Description |
|------------|-------------|
| `code_generation` | Generate code from descriptions |
| `code_review` | Review and improve code |
| `bug_detection` | Identify bugs and issues |
| `documentation` | Generate documentation |
| `testing` | Write and run tests |
| `data_analysis` | Analyze datasets |
| `customer_support` | Handle support tickets |
| `content_writing` | Generate content |

### Response

```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "api_key": "ak_abc123def456...",
  "status": "registered"
}
```

---

## List Agents

Get all registered agents.

```
GET /api/v1/agents
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter: `active`, `inactive`, `suspended` |

### Response

```json
{
  "agents": [
    {
      "agent_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "code-review-agent",
      "capabilities": ["code_review", "bug_detection"],
      "framework": "langchain",
      "version": "1.0.0"
    }
  ],
  "total": 25
}
```

---

## Search Agents (Enterprise)

Advanced search with governance filters.

```
POST /api/v1/agent-registry/agents/search?organization_id=org_123
```

### Request Body

```json
{
  "query": "code review",
  "owner_user_id": null,
  "owner_team": "engineering",
  "category": "development",
  "tags": ["python", "code-review"],
  "status": "approved",
  "sensitivity_level": "internal",
  "min_cost": 0,
  "max_cost": 1.0
}
```

### Response

```json
[
  {
    "agent_id": "agent_code_review_001",
    "name": "Python Code Reviewer",
    "description": "Reviews Python code for bugs and style",
    "owner_user_id": "user_001",
    "owner_team": "engineering",
    "category": "development",
    "tags": ["python", "code-review", "linting"],
    "status": "approved",
    "sensitivity_level": "internal",
    "monthly_cost": 45.50,
    "total_invocations": 12500,
    "avg_latency_ms": 1250,
    "created_at": "2025-01-15T10:00:00Z"
  }
]
```

---

## Agent Approval Workflow

For enterprise environments requiring approval before agents go live.

### Request Approval

```
POST /api/v1/agent-registry/approvals?approver_user_id=user_002
```

```json
{
  "agent_id": "agent_new_001",
  "approval_type": "deployment",
  "justification": "Need this agent for Q1 initiatives",
  "requested_permissions": ["pii_access", "external_api"]
}
```

### Approve or Reject

```
POST /api/v1/agent-registry/approvals/{approval_id}/decide
```

```json
{
  "approved": true,
  "comments": "Approved for production use",
  "conditions": ["Monitor cost for first 30 days"]
}
```

### Multi-Stage Approval

For high-sensitivity agents requiring multiple approvals:

```
POST /api/v1/agent-registry/agents/{agent_id}/multi-stage-approval
```

```json
[
  {"stage": "manager", "approver_user_id": "user_003", "reason": "Manager approval"},
  {"stage": "security", "approver_user_id": "user_004", "reason": "Security review"},
  {"stage": "compliance", "approver_user_id": "user_005", "reason": "Compliance review"}
]
```

---

## Policy Management

Create and enforce governance policies.

### Create Policy

```
POST /api/v1/agent-registry/policies?organization_id=org_123
```

```json
{
  "name": "Monthly Cost Cap",
  "policy_type": "cost_cap",
  "enforcement_level": "blocking",
  "rules": {
    "max_monthly_cost": 1000.00,
    "currency": "USD"
  },
  "applies_to": {
    "all_agents": true
  }
}
```

### Policy Types

| Type | Description |
|------|-------------|
| `cost_cap` | Maximum cost per period |
| `data_access` | Restrict data source access |
| `approval_required` | Require approvals for actions |
| `retention` | Data retention rules |
| `compliance` | HIPAA, SOC 2, GDPR rules |

### Enforcement Levels

| Level | Behavior |
|-------|----------|
| `warn` | Log warning, allow action |
| `blocking` | Block action, return error |
| `notify` | Allow action, notify admins |

### Check Compliance

```
POST /api/v1/agent-registry/agents/{agent_id}/check-compliance
```

Returns list of violated policies (empty if compliant).

---

## Analytics

### Cost by Team

```
GET /api/v1/agent-registry/analytics/cost-by-team?organization_id=org_123
```

```json
[
  {"team": "engineering", "total_cost": 450.25, "agent_count": 12},
  {"team": "support", "total_cost": 280.50, "agent_count": 8},
  {"team": "sales", "total_cost": 125.00, "agent_count": 5}
]
```

### Top Expensive Agents

```
GET /api/v1/agent-registry/analytics/top-expensive?organization_id=org_123&limit=10
```

```json
[
  {
    "agent_id": "agent_001",
    "name": "Research Agent",
    "monthly_cost": 125.50,
    "daily_cost": 4.18,
    "trend": "increasing"
  }
]
```

### PII Access Audit

For HIPAA/SOC 2 compliance:

```
GET /api/v1/agent-registry/analytics/pii-access-audit?organization_id=org_123
```

```json
[
  {
    "agent_id": "agent_support_001",
    "timestamp": "2025-12-26T10:15:00Z",
    "data_type": "customer_email",
    "action": "read",
    "justification": "Support ticket #12345"
  }
]
```

---

## Agent Heartbeat

Agents should send heartbeats to indicate they're active:

```
POST /api/v1/agents/{agent_id}/heartbeat
```

```json
{
  "status": "ok",
  "timestamp": "updated"
}
```

**Recommended**: Send heartbeat every 30 seconds.

---

## Task Polling

Agents poll for tasks matching their capabilities:

```
GET /api/v1/agents/{agent_id}/tasks/next?capabilities=code_review,bug_detection
```

### Response (Task Available)

```json
{
  "task_id": "task_abc123",
  "capability": "code_review",
  "input": {
    "code": "def hello(): print('world')",
    "language": "python"
  },
  "timeout_seconds": 300,
  "assigned_agent_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Response (No Tasks)

```
HTTP 204 No Content
```

---

## Submit Task Result

After completing a task:

```
POST /api/v1/tasks/{task_id}/result
```

### Success

```json
{
  "status": "completed",
  "output": {
    "issues_found": 2,
    "suggestions": ["Add type hints", "Use f-strings"]
  },
  "cost": 0.0025
}
```

### Failure

```json
{
  "status": "failed",
  "error": "Unable to parse code: syntax error on line 5"
}
```

---

## Registry Statistics

Get high-level stats for your organization:

```
GET /api/v1/agent-registry/stats?organization_id=org_123
```

```json
{
  "total_agents": 52,
  "active_agents": 45,
  "pending_approvals": 3,
  "total_monthly_cost": 1250.75,
  "avg_latency_ms": 850,
  "policy_violations_this_month": 7,
  "by_category": {
    "development": 18,
    "support": 15,
    "sales": 12,
    "research": 7
  }
}
```

---

## Find Duplicate Capabilities

Identify agents with overlapping capabilities to avoid redundancy:

```
GET /api/v1/agent-registry/agents/duplicates?organization_id=org_123
```

```json
{
  "code_review": [
    {"agent_id": "agent_001", "name": "Python Reviewer"},
    {"agent_id": "agent_002", "name": "Code Quality Bot"}
  ],
  "customer_support": [
    {"agent_id": "agent_003", "name": "Support Agent v1"},
    {"agent_id": "agent_004", "name": "Support Agent v2"}
  ]
}
```

---

## Permissions Required

| Endpoint | Permission |
|----------|------------|
| View agents | `AGENT_VIEW` |
| Create/update agents | `AGENT_MANAGE` |
| Approve agents | `AGENT_APPROVE` |
| View policies | `POLICY_VIEW` |
| Manage policies | `POLICY_MANAGE` |
| View analytics | `ANALYTICS_VIEW` |
| View audit logs | `AUDIT_VIEW` |

---

**See Also:**
- [Authentication](./authentication.md)
- [Workflows API](./workflows.md)
- [Cost Management API](./cost.md)
