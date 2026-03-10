# Human-in-the-Loop (HITL) API

The HITL API provides approval workflows and human review capabilities for AI agent operations. Pause workflows for human oversight on critical decisions.

## Base URL

```
/api/v1/hitl
```

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/approvals` | Create approval request |
| `GET` | `/approvals` | List approval requests |
| `GET` | `/approvals/{id}` | Get approval details |
| `POST` | `/approvals/{id}/decide` | Submit decision |
| `POST` | `/approvals/{id}/escalate` | Escalate approval |
| `POST` | `/approvals/{id}/cancel` | Cancel approval |
| `GET` | `/approvals/pending/me` | My pending approvals |
| `GET` | `/approvals/stats` | Approval statistics |
| `GET` | `/approvals/{id}/history` | Approval history |
| `POST` | `/templates` | Create template |
| `GET` | `/templates` | List templates |
| `GET` | `/templates/{slug}` | Get template |
| `POST` | `/process-timeouts` | Process timeouts |

---

## Create Approval Request

Pause a workflow and request human approval.

```
POST /api/v1/hitl/approvals
```

### Request Body

```json
{
  "workflow_execution_id": 12345,
  "node_id": "approval_node_1",
  "title": "Approve Customer Refund",
  "description": "Customer #12345 is requesting a refund of $500 for order #67890",
  "priority": "high",
  "required_approvers": ["user_manager_001", "user_finance_002"],
  "min_approvals_required": 1,
  "timeout_hours": 4,
  "auto_approve_on_timeout": false,
  "context": {
    "customer_id": "cust_12345",
    "order_id": "order_67890",
    "refund_amount": 500.00,
    "reason": "Product damaged during shipping"
  },
  "actions": [
    {"label": "Approve Full Refund", "value": "approve_full"},
    {"label": "Approve Partial (50%)", "value": "approve_partial"},
    {"label": "Reject", "value": "reject"}
  ]
}
```

### Priority Levels

| Priority | SLA Target | Escalation |
|----------|------------|------------|
| `low` | 24 hours | After 48h |
| `normal` | 8 hours | After 24h |
| `high` | 2 hours | After 4h |
| `critical` | 30 minutes | After 1h |

### Response

```json
{
  "id": 1,
  "workflow_execution_id": 12345,
  "node_id": "approval_node_1",
  "title": "Approve Customer Refund",
  "status": "pending",
  "priority": "high",
  "required_approvers": ["user_manager_001", "user_finance_002"],
  "min_approvals_required": 1,
  "current_approvals": 0,
  "timeout_at": "2025-12-26T14:30:00Z",
  "created_at": "2025-12-26T10:30:00Z",
  "resume_token": "rt_abc123def456"
}
```

---

## Submit Decision

Approve or reject an approval request.

```
POST /api/v1/hitl/approvals/{approval_id}/decide
```

### Request Body

```json
{
  "approved": true,
  "action_taken": "approve_full",
  "comments": "Verified shipping damage. Full refund approved.",
  "modifications": null
}
```

### With Modifications

```json
{
  "approved": true,
  "action_taken": "approve_partial",
  "comments": "Approving 75% refund due to wear evidence",
  "modifications": {
    "refund_amount": 375.00,
    "refund_reason": "Partial damage"
  }
}
```

### Response

```json
{
  "id": 1,
  "status": "approved",
  "decided_by": "user_manager_001",
  "decided_at": "2025-12-26T11:15:00Z",
  "action_taken": "approve_full",
  "comments": "Verified shipping damage. Full refund approved.",
  "current_approvals": 1,
  "workflow_resumed": true
}
```

---

## Escalation

Escalate an approval to another user or level.

```
POST /api/v1/hitl/approvals/{approval_id}/escalate
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `escalated_to_user_id` | string | Required. User to escalate to |
| `trigger` | string | Escalation reason |
| `notes` | string | Additional notes |

### Escalation Triggers

| Trigger | Description |
|---------|-------------|
| `manual` | User-initiated escalation |
| `timeout` | Auto-escalation on timeout |
| `rejection` | Escalation after rejection |
| `high_value` | Amount exceeds threshold |
| `policy` | Policy-triggered escalation |

### Response

```json
{
  "escalation_id": 1,
  "level": 2,
  "escalated_to": "user_director_001",
  "trigger": "manual",
  "previous_approver": "user_manager_001",
  "notes": "Requires director approval due to customer history"
}
```

---

## Get Pending Approvals

Get approvals waiting for current user.

```
GET /api/v1/hitl/approvals/pending/me
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `priority` | string | Filter by priority |
| `limit` | integer | Max results (default: 50) |

### Response

```json
[
  {
    "id": 1,
    "title": "Approve Customer Refund",
    "priority": "high",
    "status": "pending",
    "timeout_at": "2025-12-26T14:30:00Z",
    "created_at": "2025-12-26T10:30:00Z",
    "context": {...}
  },
  {
    "id": 2,
    "title": "Deploy to Production",
    "priority": "critical",
    "status": "pending",
    "timeout_at": "2025-12-26T11:00:00Z",
    "created_at": "2025-12-26T10:30:00Z"
  }
]
```

---

## Approval Statistics

Get approval metrics for your organization.

```
GET /api/v1/hitl/approvals/stats
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | datetime | Start of period |
| `end_date` | datetime | End of period |

### Response

```json
{
  "total_requests": 1250,
  "approved": 980,
  "rejected": 150,
  "cancelled": 45,
  "timed_out": 75,
  "approval_rate": 78.4,
  "avg_response_time_hours": 2.3,
  "escalation_rate": 12.5,
  "by_priority": {
    "critical": {"total": 50, "avg_response_minutes": 18},
    "high": {"total": 200, "avg_response_minutes": 45},
    "normal": {"total": 600, "avg_response_hours": 3.2},
    "low": {"total": 400, "avg_response_hours": 12.5}
  },
  "by_approver": [
    {"user_id": "user_001", "handled": 150, "avg_response_minutes": 35},
    {"user_id": "user_002", "handled": 120, "avg_response_minutes": 52}
  ]
}
```

---

## Approval Templates

Create reusable approval configurations.

### Create Template

```
POST /api/v1/hitl/templates
```

```json
{
  "name": "Large Refund Approval",
  "slug": "large-refund",
  "description": "Approval workflow for refunds over $500",
  "category": "finance",
  "default_approvers": ["role:finance_manager"],
  "min_approvals_required": 2,
  "timeout_hours": 4,
  "auto_approve_on_timeout": false,
  "escalation_chain": [
    {"level": 1, "role": "finance_manager", "timeout_hours": 2},
    {"level": 2, "role": "finance_director", "timeout_hours": 2},
    {"level": 3, "role": "cfo", "timeout_hours": 4}
  ],
  "notification_channels": ["email", "slack"],
  "required_fields": ["refund_amount", "customer_id", "reason"]
}
```

### Use Template in Workflow

```json
{
  "id": "refund_approval",
  "type": "human_approval",
  "data": {
    "template": "large-refund",
    "context": {
      "refund_amount": "{{calculate_refund.output.amount}}",
      "customer_id": "{{input.customer_id}}",
      "reason": "{{input.reason}}"
    }
  }
}
```

---

## Approval History

Get complete history of an approval.

```
GET /api/v1/hitl/approvals/{approval_id}/history
```

### Response

```json
{
  "request": {
    "id": 1,
    "title": "Approve Customer Refund",
    "status": "approved",
    "created_at": "2025-12-26T10:30:00Z",
    "completed_at": "2025-12-26T11:15:00Z"
  },
  "responses": [
    {
      "id": 1,
      "user_id": "user_manager_001",
      "decision": "approved",
      "action_taken": "approve_full",
      "comments": "Verified shipping damage",
      "responded_at": "2025-12-26T11:15:00Z",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0..."
    }
  ],
  "escalations": [],
  "notifications": [
    {
      "id": 1,
      "channel": "email",
      "recipient": "manager@company.com",
      "sent_at": "2025-12-26T10:30:05Z",
      "status": "delivered"
    },
    {
      "id": 2,
      "channel": "slack",
      "recipient": "#approvals",
      "sent_at": "2025-12-26T10:30:06Z",
      "status": "delivered"
    }
  ]
}
```

---

## Timeout Processing

Process timed-out approval requests.

```
POST /api/v1/hitl/process-timeouts
```

This endpoint should be called by a background worker (cron job) every minute.

### Response

```json
{
  "processed_count": 5,
  "message": "Processed 5 timed-out approval requests"
}
```

### Timeout Actions

| Configuration | Behavior |
|---------------|----------|
| `auto_approve_on_timeout: true` | Auto-approve and resume workflow |
| `auto_approve_on_timeout: false` | Auto-reject and fail workflow |
| Escalation chain configured | Escalate to next level |

---

## Using HITL in Workflows

### Basic Approval Node

```json
{
  "id": "manager_approval",
  "type": "human_approval",
  "position": {"x": 400, "y": 0},
  "data": {
    "title": "Manager Approval Required",
    "description": "Please review and approve this action",
    "approvers": ["{{input.manager_id}}"],
    "timeout_hours": 8,
    "actions": [
      {"label": "Approve", "value": "approve"},
      {"label": "Reject", "value": "reject"}
    ]
  }
}
```

### Conditional Approval

```json
{
  "nodes": [
    {
      "id": "check_amount",
      "type": "conditional",
      "data": {
        "conditions": [
          {"if": "{{input.amount}} > 1000", "then": "director_approval"},
          {"else": "auto_approve"}
        ]
      }
    },
    {
      "id": "director_approval",
      "type": "human_approval",
      "data": {
        "title": "Large Transaction Approval",
        "approvers": ["role:director"]
      }
    }
  ]
}
```

### Accessing Approval Result

```
{{manager_approval.output.approved}}        // true/false
{{manager_approval.output.action_taken}}    // "approve", "reject", etc.
{{manager_approval.output.comments}}        // Approver's comments
{{manager_approval.output.decided_by}}      // User who decided
{{manager_approval.output.modifications}}   // Any modifications made
```

---

## Notification Channels

### Email

```json
{
  "notifications": {
    "email": {
      "recipients": ["manager@company.com"],
      "template": "approval_request",
      "include_context": true
    }
  }
}
```

### Slack

```json
{
  "notifications": {
    "slack": {
      "channel": "#approvals",
      "mention_users": ["@manager"],
      "include_actions": true
    }
  }
}
```

### Mobile Push

```json
{
  "notifications": {
    "push": {
      "title": "Approval Required",
      "body": "{{title}}",
      "priority": "high"
    }
  }
}
```

---

## Multi-Level Approval

Configure multi-stage approval chains:

```json
{
  "approval_chain": [
    {
      "stage": 1,
      "name": "Manager Approval",
      "approvers": ["role:manager"],
      "required_approvals": 1
    },
    {
      "stage": 2,
      "name": "Security Review",
      "approvers": ["role:security_team"],
      "required_approvals": 1,
      "parallel": false
    },
    {
      "stage": 3,
      "name": "Compliance Sign-off",
      "approvers": ["role:compliance"],
      "required_approvals": 1
    }
  ]
}
```

---

## Status Values

| Status | Description |
|--------|-------------|
| `pending` | Waiting for approval |
| `approved` | Approved by required approvers |
| `rejected` | Rejected by an approver |
| `cancelled` | Cancelled by requester |
| `timed_out` | Exceeded timeout without decision |
| `escalated` | Escalated to next level |

---

## Best Practices

1. **Set appropriate timeouts**: Match business urgency
2. **Use escalation chains**: Prevent bottlenecks
3. **Provide context**: Include all relevant information
4. **Use templates**: Standardize common approvals
5. **Monitor statistics**: Track approval efficiency
6. **Configure notifications**: Ensure timely responses
7. **Audit history**: Maintain compliance records

---

## Webhooks

Receive real-time approval events:

```json
{
  "event": "approval.required",
  "data": {
    "approval_id": 1,
    "title": "Approve Customer Refund",
    "priority": "high",
    "approvers": ["user_manager_001"]
  }
}
```

### Events

| Event | Description |
|-------|-------------|
| `approval.required` | New approval created |
| `approval.decided` | Approval approved/rejected |
| `approval.escalated` | Escalated to next level |
| `approval.timeout` | Approval timed out |

---

**See Also:**
- [Workflows API](./workflows.md)
- [Agents API](./agents.md)
