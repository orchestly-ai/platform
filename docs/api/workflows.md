# Workflows API

The Workflows API provides a visual DAG (Directed Acyclic Graph) builder for creating and executing multi-step agent workflows.

## Base URL

```
/api/v1/workflows
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/workflows` | Create a new workflow |
| `GET` | `/workflows` | List workflows |
| `GET` | `/workflows/{id}` | Get workflow details |
| `PUT` | `/workflows/{id}` | Update workflow |
| `DELETE` | `/workflows/{id}` | Delete workflow |
| `POST` | `/workflows/{id}/duplicate` | Duplicate workflow |
| `POST` | `/workflows/{id}/execute` | Execute workflow |
| `GET` | `/workflows/{id}/executions` | List executions |
| `GET` | `/workflows/executions/{id}` | Get execution details |
| `POST` | `/workflows/executions/{id}/cancel` | Cancel execution |
| `GET` | `/workflows/{id}/analytics` | Get workflow analytics |
| `GET` | `/workflows/templates` | List templates |
| `POST` | `/workflows/templates/{id}/use` | Create from template |

---

## Create Workflow

Create a new workflow with nodes and edges.

```
POST /api/v1/workflows
```

### Request Body

```json
{
  "name": "Customer Support Pipeline",
  "description": "Automated customer support with human escalation",
  "tags": ["support", "production"],
  "nodes": [
    {
      "id": "classify",
      "type": "llm_call",
      "position": {"x": 0, "y": 0},
      "data": {
        "model": "gpt-4",
        "prompt": "Classify this support ticket: {{input.ticket}}"
      }
    },
    {
      "id": "route",
      "type": "conditional",
      "position": {"x": 200, "y": 0},
      "data": {
        "conditions": [
          {"if": "{{classify.output}} == 'urgent'", "then": "escalate"},
          {"else": "auto_respond"}
        ]
      }
    },
    {
      "id": "escalate",
      "type": "human_approval",
      "position": {"x": 400, "y": -100},
      "data": {
        "approvers": ["support-team"],
        "timeout_hours": 4
      }
    },
    {
      "id": "auto_respond",
      "type": "llm_call",
      "position": {"x": 400, "y": 100},
      "data": {
        "model": "gpt-3.5-turbo",
        "prompt": "Generate a helpful response to: {{input.ticket}}"
      }
    }
  ],
  "edges": [
    {"id": "e1", "source": "classify", "target": "route"},
    {"id": "e2", "source": "route", "target": "escalate", "label": "urgent"},
    {"id": "e3", "source": "route", "target": "auto_respond", "label": "default"}
  ],
  "variables": {
    "model_temperature": 0.7
  },
  "environment": "production",
  "max_execution_time_seconds": 3600,
  "retry_on_failure": true,
  "max_retries": 3
}
```

### Node Types

| Type | Description | Data Fields |
|------|-------------|-------------|
| `llm_call` | Make an LLM API call | `model`, `prompt`, `temperature`, `max_tokens` |
| `tool_call` | Execute a tool/function | `tool_name`, `parameters` |
| `human_approval` | Pause for human approval | `approvers`, `timeout_hours`, `auto_approve` |
| `conditional` | Branch based on conditions | `conditions` |
| `parallel` | Execute branches in parallel | `branches` |
| `loop` | Iterate over items | `items`, `max_iterations` |
| `http` | Make HTTP request | `url`, `method`, `headers`, `body` |
| `code` | Execute Python code | `code`, `language` |
| `integration` | Call external integration | `integration_id`, `action`, `params` |

### Response

```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "organization_id": "org_demo_12345",
  "name": "Customer Support Pipeline",
  "description": "Automated customer support with human escalation",
  "tags": ["support", "production"],
  "status": "draft",
  "version": 1,
  "nodes": [...],
  "edges": [...],
  "variables": {"model_temperature": 0.7},
  "environment": "production",
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T10:00:00Z",
  "created_by": "user_67890"
}
```

---

## List Workflows

Get all workflows for your organization.

```
GET /api/v1/workflows
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `draft`, `active`, `archived` |
| `tags` | string | Comma-separated tags |
| `environment` | string | Filter by environment |
| `limit` | integer | Max results (default: 100, max: 1000) |
| `offset` | integer | Pagination offset |

### Example

```bash
curl -X GET "https://api.agent-orchestrator.dev/api/v1/workflows?status=active&tags=production" \
  -H "X-API-Key: ak_your_key"
```

---

## Execute Workflow

Start a workflow execution.

```
POST /api/v1/workflows/{workflow_id}/execute
```

### Request Body

```json
{
  "input_data": {
    "ticket": "My order hasn't arrived and it's been 2 weeks!",
    "customer_id": "cust_12345"
  },
  "variables": {
    "model_temperature": 0.5
  }
}
```

### Response

```json
{
  "execution_id": "exec_abc123",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_version": 1,
  "status": "pending",
  "triggered_by": "user_67890",
  "trigger_source": "manual",
  "started_at": null,
  "input_data": {...},
  "node_states": {},
  "created_at": "2025-12-26T10:30:00Z"
}
```

### Execution Status Values

| Status | Description |
|--------|-------------|
| `pending` | Execution queued |
| `running` | Currently executing |
| `suspended` | Paused for human approval |
| `completed` | Successfully finished |
| `failed` | Execution failed |
| `cancelled` | Manually cancelled |

---

## Get Execution Details

Check the status and results of an execution.

```
GET /api/v1/workflows/executions/{execution_id}
```

### Response

```json
{
  "execution_id": "exec_abc123",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_version": 1,
  "status": "completed",
  "triggered_by": "user_67890",
  "trigger_source": "manual",
  "started_at": "2025-12-26T10:30:01Z",
  "completed_at": "2025-12-26T10:30:15Z",
  "duration_seconds": 14.2,
  "input_data": {
    "ticket": "My order hasn't arrived..."
  },
  "output_data": {
    "classification": "shipping_issue",
    "response": "I apologize for the delay..."
  },
  "node_states": {
    "classify": {
      "status": "completed",
      "started_at": "2025-12-26T10:30:01Z",
      "completed_at": "2025-12-26T10:30:05Z",
      "output": {"classification": "shipping_issue"}
    },
    "route": {
      "status": "completed",
      "branch_taken": "auto_respond"
    },
    "auto_respond": {
      "status": "completed",
      "output": {"response": "I apologize..."}
    }
  },
  "total_cost": 0.0045,
  "total_tokens": 892
}
```

---

## Workflow Analytics

Get execution statistics and performance metrics.

```
GET /api/v1/workflows/{workflow_id}/analytics
```

### Response

```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_name": "Customer Support Pipeline",
  "statistics": {
    "total_executions": 1250,
    "successful_executions": 1180,
    "failed_executions": 70,
    "success_rate": 94.4,
    "avg_duration_seconds": 12.5,
    "total_cost": 125.50,
    "avg_cost": 0.10
  },
  "recent_executions": [
    {
      "execution_id": "exec_abc123",
      "status": "completed",
      "duration_seconds": 14.2,
      "total_cost": 0.0045,
      "created_at": "2025-12-26T10:30:00Z"
    }
  ]
}
```

---

## Templates

### List Templates

Browse pre-built workflow templates.

```
GET /api/v1/workflows/templates
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Template category |
| `tags` | string | Comma-separated tags |
| `is_featured` | boolean | Featured templates only |

### Response

```json
{
  "templates": [
    {
      "template_id": "tmpl_customer_support",
      "name": "Customer Support Automation",
      "description": "AI-powered customer support with escalation",
      "category": "support",
      "tags": ["support", "llm", "hitl"],
      "use_count": 532,
      "rating": 4.8,
      "is_featured": true
    }
  ]
}
```

### Create from Template

Instantiate a template as a new workflow.

```
POST /api/v1/workflows/templates/{template_id}/use?name=My%20Workflow
```

---

## Triggers

Workflows can be triggered by:

### Manual Trigger

```bash
POST /api/v1/workflows/{id}/execute
```

### Webhook Trigger

```bash
POST /api/v1/workflows/{id}/trigger/webhook
Authorization: Bearer {webhook_secret}
```

### Schedule Trigger

Configure in workflow settings:

```json
{
  "trigger_type": "schedule",
  "trigger_config": {
    "cron": "0 9 * * 1-5",
    "timezone": "America/New_York"
  }
}
```

### Event Trigger

Trigger from integration events:

```json
{
  "trigger_type": "event",
  "trigger_config": {
    "integration": "slack",
    "event": "message.received",
    "filter": {"channel": "#support"}
  }
}
```

---

## Variables and Templating

Workflows support variable interpolation using `{{}}` syntax:

### Input Variables

```
{{input.field_name}}
```

### Node Output Variables

```
{{node_id.output}}
{{node_id.output.nested.field}}
```

### Workflow Variables

```
{{variables.my_variable}}
```

### Built-in Variables

| Variable | Description |
|----------|-------------|
| `{{execution_id}}` | Current execution ID |
| `{{workflow_id}}` | Workflow ID |
| `{{timestamp}}` | Current UTC timestamp |
| `{{organization_id}}` | Organization ID |

---

## Error Handling

### Retry Configuration

```json
{
  "retry_on_failure": true,
  "max_retries": 3,
  "retry_delay_seconds": 5,
  "retry_backoff": "exponential"
}
```

### Error Node

Handle errors gracefully:

```json
{
  "id": "error_handler",
  "type": "code",
  "data": {
    "code": "notify_team(error_details)"
  }
}
```

---

## Best Practices

1. **Use meaningful node IDs**: `classify_ticket` instead of `node1`
2. **Set appropriate timeouts**: Prevent runaway executions
3. **Enable retries**: Handle transient failures gracefully
4. **Use templates**: Start with proven patterns
5. **Monitor analytics**: Track success rates and costs
6. **Version control**: Use git for workflow definitions

---

**See Also:**
- [Human-in-the-Loop API](./hitl.md)
- [LLM Routing API](./llm.md)
- [Integrations API](./integrations.md)
