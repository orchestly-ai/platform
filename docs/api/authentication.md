# Authentication

The Agent Orchestration Platform uses API keys for authentication. All API requests must include a valid API key in the `X-API-Key` header.

## Obtaining an API Key

### Option 1: Register an Agent

When you register a new agent, an API key is automatically generated:

```bash
curl -X POST "https://api.agent-orchestrator.dev/api/v1/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-agent",
    "capabilities": ["code_generation"]
  }'
```

Response:
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "api_key": "ak_7f3d8a2b1c4e5f6g7h8i9j0k...",
  "status": "registered"
}
```

### Option 2: Dashboard

1. Log in to the [Dashboard](https://dashboard.agent-orchestrator.dev)
2. Navigate to **Settings** > **API Keys**
3. Click **Create New Key**
4. Copy and securely store your key

## Using API Keys

### Header Authentication

Include the API key in the `X-API-Key` header:

```bash
curl -X GET "https://api.agent-orchestrator.dev/api/v1/agents" \
  -H "X-API-Key: ak_your_api_key_here"
```

### Python SDK

```python
from agent_orchestrator import Client

client = Client(api_key="ak_your_api_key_here")
agents = client.agents.list()
```

### TypeScript SDK

```typescript
import { AgentOrchestrator } from '@agent-orchestrator/sdk';

const client = new AgentOrchestrator({
  apiKey: 'ak_your_api_key_here'
});

const agents = await client.agents.list();
```

## API Key Types

| Type | Prefix | Permissions | Use Case |
|------|--------|-------------|----------|
| Agent Key | `ak_` | Agent-specific operations | Individual agents |
| Organization Key | `ok_` | Full organization access | Admin operations |
| Read-Only Key | `rk_` | Read-only access | Dashboards, monitoring |

## Permissions

API keys are associated with RBAC (Role-Based Access Control) permissions:

### Permission Categories

| Category | Permissions |
|----------|-------------|
| **Agents** | `AGENT_VIEW`, `AGENT_MANAGE`, `AGENT_APPROVE` |
| **Workflows** | `WORKFLOW_VIEW`, `WORKFLOW_CREATE`, `WORKFLOW_EXECUTE`, `WORKFLOW_DELETE` |
| **Cost** | `COST_READ`, `COST_UPDATE`, `COST_LIMIT_SET` |
| **Policies** | `POLICY_VIEW`, `POLICY_MANAGE` |
| **Analytics** | `ANALYTICS_VIEW` |
| **Audit** | `AUDIT_VIEW` |

### Example: Check Permissions

```bash
curl -X GET "https://api.agent-orchestrator.dev/api/v1/auth/permissions" \
  -H "X-API-Key: ak_your_api_key_here"
```

Response:
```json
{
  "permissions": [
    "AGENT_VIEW",
    "AGENT_MANAGE",
    "WORKFLOW_VIEW",
    "WORKFLOW_CREATE",
    "WORKFLOW_EXECUTE"
  ]
}
```

## Key Management

### List API Keys

```bash
curl -X GET "https://api.agent-orchestrator.dev/api/v1/auth/keys" \
  -H "X-API-Key: ok_admin_key_here"
```

### Rotate API Key

```bash
curl -X POST "https://api.agent-orchestrator.dev/api/v1/auth/keys/{key_id}/rotate" \
  -H "X-API-Key: ok_admin_key_here"
```

### Revoke API Key

```bash
curl -X DELETE "https://api.agent-orchestrator.dev/api/v1/auth/keys/{key_id}" \
  -H "X-API-Key: ok_admin_key_here"
```

## Security Best Practices

### 1. Never Expose Keys in Client-Side Code

```javascript
// BAD - Never do this
const apiKey = "ak_secret_key_here";

// GOOD - Use environment variables
const apiKey = process.env.AGENT_ORCHESTRATOR_API_KEY;
```

### 2. Use Environment Variables

```bash
# .env file
AGENT_ORCHESTRATOR_API_KEY=ak_your_api_key_here
```

```python
import os
from agent_orchestrator import Client

client = Client(api_key=os.environ["AGENT_ORCHESTRATOR_API_KEY"])
```

### 3. Rotate Keys Regularly

- Rotate production keys every 90 days
- Rotate immediately if a key is compromised
- Use separate keys for development and production

### 4. Limit Key Scope

Create keys with minimal required permissions:

```bash
curl -X POST "https://api.agent-orchestrator.dev/api/v1/auth/keys" \
  -H "X-API-Key: ok_admin_key_here" \
  -d '{
    "name": "monitoring-key",
    "permissions": ["ANALYTICS_VIEW", "COST_READ"],
    "expires_at": "2026-01-01T00:00:00Z"
  }'
```

### 5. Monitor Key Usage

Track API key usage in the dashboard:

- Request count by key
- Endpoints accessed
- Error rates
- Geographic distribution

## SSO Integration

For enterprise customers, we support SSO integration:

### Supported Providers

- **SAML 2.0**: Okta, OneLogin, Azure AD
- **OAuth 2.0**: Google Workspace, GitHub
- **OpenID Connect**: Auth0, Keycloak

### Configuration

```bash
curl -X POST "https://api.agent-orchestrator.dev/api/v1/sso/configure" \
  -H "X-API-Key: ok_admin_key_here" \
  -d '{
    "provider": "okta",
    "metadata_url": "https://your-org.okta.com/app/.../sso/saml/metadata",
    "auto_create_users": true,
    "default_role": "developer"
  }'
```

## Development Mode

In development mode (`DEBUG=true`), you can use `debug` as an API key:

```bash
curl -X GET "http://localhost:8000/api/v1/agents" \
  -H "X-API-Key: debug"
```

**Warning**: Never enable debug mode in production.

## Troubleshooting

### Error: 401 Unauthorized

```json
{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "Invalid API key"
  }
}
```

**Solutions:**
- Verify the API key is correct
- Check if the key has been revoked
- Ensure the key hasn't expired

### Error: 403 Forbidden

```json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "You don't have permission to perform this action"
  }
}
```

**Solutions:**
- Check required permissions for the endpoint
- Request additional permissions from admin
- Use a key with appropriate scope

---

**See Also:**
- [API Overview](./README.md)
- [Rate Limits](./README.md#rate-limits)
