# Integrations API

The Integrations API provides access to 26+ pre-built integrations with external services. Reduce integration time from weeks to minutes with one-click install.

## Base URL

```
/api/v1/integrations
```

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/browse` | Browse marketplace |
| `GET` | `/{id}` | Get integration details |
| `GET` | `/featured` | Featured integrations |
| `GET` | `/popular` | Popular integrations |
| `GET` | `/category/{category}` | By category |
| `POST` | `/{id}/install` | Install integration |
| `POST` | `/installations/{id}/configure` | Configure integration |
| `DELETE` | `/{id}/uninstall` | Uninstall |
| `GET` | `/installations/{org_id}` | List installations |
| `GET` | `/installations/{id}/health` | Health check |
| `POST` | `/{id}/execute` | Execute action |
| `POST` | `/{id}/rate` | Rate integration |

---

## Available Integrations

### Communication

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **Slack** | OAuth 2.0 | Send message, create channel, list members |
| **Microsoft Teams** | OAuth 2.0 | Send message, create channel, schedule meeting |
| **Discord** | Bot Token | Send message, manage channels |
| **Intercom** | Access Token | Create conversation, send message |

### CRM & Sales

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **Salesforce** | OAuth 2.0 | CRUD leads/opportunities/accounts |
| **HubSpot** | OAuth 2.0 | CRUD contacts/deals/companies |
| **Pipedrive** | API Key | CRUD deals/persons/organizations |

### Project Management

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **Jira** | API Token | Create issue, update status, add comment |
| **Asana** | OAuth 2.0 | Create task, update task, list projects |
| **Linear** | API Key | Create issue, update status |

### Productivity

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **Notion** | Integration Token | Create page, update database, search |
| **Airtable** | API Key | CRUD records, list bases |
| **Google Sheets** | OAuth 2.0 | Read/write cells, create sheets |

### Developer Tools

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **GitHub** | OAuth 2.0 / PAT | CRUD issues/PRs, manage repos |
| **GitLab** | OAuth 2.0 | CRUD issues/MRs, manage projects |
| **Bitbucket** | OAuth 2.0 | CRUD PRs, manage repos |

### Data & Analytics

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **Snowflake** | Key Pair | Run query, list tables |
| **BigQuery** | Service Account | Run query, list datasets |
| **MongoDB** | Connection String | CRUD documents |
| **PostgreSQL** | Connection String | Run query |

### Monitoring & Observability

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **Datadog** | API Key | Create metric, list monitors |
| **PagerDuty** | API Key | Create incident, acknowledge |

### E-Commerce

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **Shopify** | API Key | List orders, update inventory |
| **WooCommerce** | API Key | List products, create order |
| **Stripe** | API Key | Create charge, list customers |

### Marketing

| Integration | Auth Type | Actions |
|-------------|-----------|---------|
| **SendGrid** | API Key | Send email, manage contacts |
| **Mailchimp** | API Key | Manage lists, send campaigns |

---

## Browse Marketplace

Search and filter available integrations.

```
POST /api/v1/integrations/browse
```

### Request Body

```json
{
  "category": "communication",
  "search_query": "slack",
  "tags": ["messaging", "notifications"],
  "is_verified": true,
  "is_featured": null,
  "is_free": true,
  "min_rating": 4.0,
  "sort_by": "popularity",
  "limit": 20,
  "offset": 0
}
```

### Categories

- `communication` - Slack, Teams, Discord
- `crm` - Salesforce, HubSpot
- `project_management` - Jira, Asana
- `productivity` - Notion, Airtable
- `developer_tools` - GitHub, GitLab
- `data` - Snowflake, BigQuery
- `monitoring` - Datadog, PagerDuty
- `ecommerce` - Shopify, Stripe
- `marketing` - SendGrid, Mailchimp

### Sort Options

- `popularity` - By install count
- `rating` - By user rating
- `newest` - Most recently added
- `name` - Alphabetical

### Response

```json
{
  "integrations": [
    {
      "integration_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Slack",
      "description": "Send messages and manage channels in Slack",
      "category": "communication",
      "icon_url": "https://cdn.example.com/slack.png",
      "tags": ["messaging", "notifications", "chat"],
      "auth_type": "oauth2",
      "is_verified": true,
      "is_featured": true,
      "is_free": true,
      "rating": 4.8,
      "install_count": 12500,
      "version": "2.1.0"
    }
  ],
  "total_count": 1,
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

---

## Install Integration

One-click install for your organization.

```
POST /api/v1/integrations/{integration_id}/install?user_id=user_123
```

### Request Body

```json
{
  "organization_id": "org_123",
  "configuration": {
    "default_channel": "#general"
  },
  "auth_credentials": null
}
```

### Response

```json
{
  "installation_id": "inst_abc123",
  "integration_id": "550e8400-e29b-41d4-a716-446655440000",
  "organization_id": "org_123",
  "status": "configuration_required",
  "message": "Integration installed successfully. Please configure authentication to activate."
}
```

### Installation Status Values

| Status | Description |
|--------|-------------|
| `active` | Ready to use |
| `configuration_required` | Needs auth credentials |
| `error` | Installation failed |
| `suspended` | Temporarily disabled |

---

## Configure Integration

Set up authentication credentials after installation.

```
POST /api/v1/integrations/installations/{installation_id}/configure
```

### Request Body (OAuth)

```json
{
  "configuration": {
    "workspace": "my-company",
    "default_channel": "#alerts"
  },
  "auth_credentials": {
    "oauth_token": "xoxb-...",
    "refresh_token": "xoxr-..."
  }
}
```

### Request Body (API Key)

```json
{
  "configuration": {
    "base_url": "https://api.example.com"
  },
  "auth_credentials": {
    "api_key": "sk_live_..."
  }
}
```

### Response

```json
{
  "installation_id": "inst_abc123",
  "status": "active",
  "message": "Integration configured and activated successfully."
}
```

---

## Execute Integration Action

Call an integration action from your workflow.

```
POST /api/v1/integrations/{integration_id}/execute
```

### Request Body

```json
{
  "installation_id": "inst_abc123",
  "action_name": "send_message",
  "input_parameters": {
    "channel": "#general",
    "text": "Hello from Agent Orchestrator!",
    "attachments": [
      {
        "title": "Workflow Complete",
        "color": "#36a64f"
      }
    ]
  },
  "workflow_execution_id": "exec_xyz789",
  "task_id": "task_456"
}
```

### Response

```json
{
  "success": true,
  "output_result": {
    "message_id": "1234567890.123456",
    "channel": "C0123456789",
    "ts": "1703583600.123456"
  },
  "error_message": null,
  "duration_ms": 245.5
}
```

---

## Available Actions by Integration

### Slack

| Action | Parameters |
|--------|------------|
| `send_message` | `channel`, `text`, `attachments` |
| `create_channel` | `name`, `is_private` |
| `list_channels` | `limit`, `types` |
| `upload_file` | `channel`, `file`, `filename` |

### GitHub

| Action | Parameters |
|--------|------------|
| `create_issue` | `repo`, `title`, `body`, `labels` |
| `create_pr` | `repo`, `title`, `head`, `base` |
| `add_comment` | `repo`, `issue_number`, `body` |
| `list_repos` | `org`, `type` |

### Salesforce

| Action | Parameters |
|--------|------------|
| `create_lead` | `FirstName`, `LastName`, `Email`, `Company` |
| `update_opportunity` | `Id`, `Stage`, `Amount` |
| `query` | `soql` |

### Jira

| Action | Parameters |
|--------|------------|
| `create_issue` | `project`, `summary`, `description`, `issuetype` |
| `update_status` | `issue_key`, `transition_id` |
| `add_comment` | `issue_key`, `body` |

---

## Installation Health

Check the health status of an installation.

```
GET /api/v1/integrations/installations/{installation_id}/health
```

### Response

```json
{
  "healthy": true,
  "status": "active",
  "total_executions": 1250,
  "successful_executions": 1230,
  "failed_executions": 20,
  "success_rate": 98.4,
  "last_execution_at": "2025-12-26T10:30:00Z",
  "last_health_check_at": "2025-12-26T10:00:00Z",
  "health_check_message": "All systems operational"
}
```

---

## List Installations

Get all installed integrations for an organization.

```
GET /api/v1/integrations/installations/{organization_id}
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status |

### Response

```json
[
  {
    "installation_id": "inst_abc123",
    "integration_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "active",
    "installed_version": "2.1.0",
    "total_executions": 1250,
    "successful_executions": 1230,
    "failed_executions": 20,
    "last_execution_at": "2025-12-26T10:30:00Z",
    "installed_at": "2025-01-15T09:00:00Z"
  }
]
```

---

## Rate Integration

Submit a rating and review.

```
POST /api/v1/integrations/{integration_id}/rate
```

### Request Body

```json
{
  "organization_id": "org_123",
  "user_id": "user_456",
  "rating": 5,
  "review": "Great integration! Works perfectly with our workflows."
}
```

### Response

```json
{
  "rating_id": "rating_xyz",
  "integration_id": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 5,
  "message": "Rating submitted successfully."
}
```

---

## Using Integrations in Workflows

### Integration Node

```json
{
  "id": "slack_notify",
  "type": "integration",
  "data": {
    "integration": "slack",
    "installation_id": "inst_abc123",
    "action": "send_message",
    "parameters": {
      "channel": "{{variables.alert_channel}}",
      "text": "Workflow {{workflow_id}} completed: {{previous_node.output}}"
    }
  }
}
```

### Chaining Integrations

```json
{
  "nodes": [
    {
      "id": "create_jira",
      "type": "integration",
      "data": {
        "integration": "jira",
        "action": "create_issue",
        "parameters": {
          "summary": "{{input.title}}",
          "description": "{{llm_node.output}}"
        }
      }
    },
    {
      "id": "notify_slack",
      "type": "integration",
      "data": {
        "integration": "slack",
        "action": "send_message",
        "parameters": {
          "text": "Created Jira: {{create_jira.output.key}}"
        }
      }
    }
  ],
  "edges": [
    {"source": "create_jira", "target": "notify_slack"}
  ]
}
```

---

## OAuth Flow

For OAuth-based integrations:

### 1. Get Authorization URL

```
GET /api/v1/integrations/{id}/oauth/authorize?redirect_uri=https://your-app.com/callback
```

### 2. Handle Callback

```
GET /api/v1/integrations/{id}/oauth/callback?code=abc123&state=xyz
```

### 3. Tokens Auto-Refresh

OAuth tokens are automatically refreshed before expiration.

---

## Webhooks from Integrations

Receive events from integrations:

### Configure Webhook

```json
{
  "trigger_type": "event",
  "trigger_config": {
    "integration": "github",
    "event": "pull_request.opened",
    "filter": {
      "repository": "my-org/my-repo"
    }
  }
}
```

### Supported Events

| Integration | Events |
|-------------|--------|
| GitHub | `push`, `pull_request.*`, `issue.*` |
| Slack | `message.*`, `reaction_added` |
| Stripe | `charge.*`, `customer.*`, `invoice.*` |
| Jira | `issue_created`, `issue_updated` |

---

## Error Handling

### Common Errors

| Code | Description |
|------|-------------|
| `INTEGRATION_NOT_FOUND` | Integration doesn't exist |
| `INSTALLATION_NOT_FOUND` | Installation not found |
| `NOT_CONFIGURED` | Auth credentials missing |
| `ACTION_NOT_FOUND` | Invalid action name |
| `AUTH_FAILED` | Credentials expired/invalid |
| `RATE_LIMITED` | External API rate limit |

### Retry Logic

Failed executions are automatically retried with exponential backoff:

- Attempt 1: Immediate
- Attempt 2: 1 second
- Attempt 3: 5 seconds
- Attempt 4: 30 seconds

---

## Building Custom Integrations

Contact us for the Integration SDK to build custom integrations:

```python
from agent_orchestrator.integrations import BaseIntegration

class MyIntegration(BaseIntegration):
    name = "my-service"
    auth_type = "api_key"

    async def execute_action(self, action: str, params: dict) -> dict:
        if action == "my_action":
            return await self._my_action(params)
        raise ValueError(f"Unknown action: {action}")

    async def health_check(self) -> bool:
        response = await self._request("GET", "/health")
        return response.status == 200
```

---

**See Also:**
- [Workflows API](./workflows.md)
- [Authentication](./authentication.md)
