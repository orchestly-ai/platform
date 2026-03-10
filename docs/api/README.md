# Agent Orchestration Platform API

> **Production-grade orchestration for multi-agent AI systems**

## Overview

The Agent Orchestration Platform API provides enterprise-ready infrastructure for deploying and managing autonomous agent teams at scale. This RESTful API enables you to:

- **Register and manage AI agents** with capability-based routing
- **Design visual workflows** using a DAG-based execution engine
- **Track costs** with AI-powered forecasting and anomaly detection
- **Implement human-in-the-loop** approval workflows
- **Route LLM requests** intelligently across multiple providers
- **Connect 26+ integrations** to external services

## Base URL

```
Production: https://api.agent-orchestrator.dev/api/v1
Development: http://localhost:8000/api/v1
```

## Authentication

All API endpoints require authentication via API key:

```bash
curl -X GET "https://api.agent-orchestrator.dev/api/v1/agents" \
  -H "X-API-Key: ak_your_api_key_here"
```

See [Authentication Guide](./authentication.md) for details on obtaining and managing API keys.

## Quick Start

### 1. Register an Agent

```bash
curl -X POST "https://api.agent-orchestrator.dev/api/v1/agents" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: debug" \
  -d '{
    "name": "my-first-agent",
    "capabilities": ["code_generation", "code_review"],
    "framework": "langchain",
    "version": "1.0.0"
  }'
```

Response:
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "api_key": "ak_abc123...",
  "status": "registered"
}
```

### 2. Create a Workflow

```bash
curl -X POST "https://api.agent-orchestrator.dev/api/v1/workflows" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_abc123..." \
  -d '{
    "name": "Code Review Pipeline",
    "nodes": [
      {"id": "1", "type": "llm_call", "position": {"x": 0, "y": 0}, "data": {"model": "gpt-4"}},
      {"id": "2", "type": "human_approval", "position": {"x": 200, "y": 0}, "data": {}}
    ],
    "edges": [
      {"id": "e1", "source": "1", "target": "2"}
    ]
  }'
```

### 3. Execute the Workflow

```bash
curl -X POST "https://api.agent-orchestrator.dev/api/v1/workflows/{workflow_id}/execute" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ak_abc123..." \
  -d '{
    "input_data": {"code": "def hello(): print(\"world\")"}
  }'
```

## API Modules

| Module | Description | Documentation |
|--------|-------------|---------------|
| **Agents** | Agent registration, management, and governance | [agents.md](./agents.md) |
| **Workflows** | Visual DAG builder and execution engine | [workflows.md](./workflows.md) |
| **LLM Routing** | Multi-provider LLM routing and cost optimization | [llm.md](./llm.md) |
| **Cost Management** | AI-powered cost tracking and forecasting | [cost.md](./cost.md) |
| **Human-in-the-Loop** | Approval workflows and human review | [hitl.md](./hitl.md) |
| **Integrations** | 26+ pre-built service integrations | [integrations.md](./integrations.md) |

## Response Format

All API responses follow a consistent JSON format:

### Success Response

```json
{
  "data": { ... },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2025-12-26T10:30:00Z"
  }
}
```

### Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {"field": "name", "error": "Required field missing"}
    ]
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2025-12-26T10:30:00Z"
  }
}
```

## HTTP Status Codes

| Code | Description |
|------|-------------|
| `200` | Success |
| `201` | Resource created |
| `202` | Accepted (async operation started) |
| `204` | No content (successful deletion) |
| `400` | Bad request (validation error) |
| `401` | Unauthorized (invalid API key) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Resource not found |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

## Rate Limits

| Plan | Requests/minute | Requests/day |
|------|-----------------|--------------|
| Free | 60 | 1,000 |
| Pro | 600 | 50,000 |
| Enterprise | Custom | Custom |

Rate limit headers are included in all responses:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1703583600
```

## Pagination

List endpoints support pagination via `limit` and `offset` parameters:

```bash
GET /api/v1/workflows?limit=20&offset=40
```

Response includes pagination metadata:

```json
{
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 40,
    "has_more": true
  }
}
```

## Filtering and Sorting

Most list endpoints support filtering and sorting:

```bash
# Filter by status
GET /api/v1/workflows?status=active

# Filter by tags
GET /api/v1/workflows?tags=production,critical

# Sort by field
GET /api/v1/workflows?sort_by=created_at&sort_order=desc
```

## Webhooks

Configure webhooks to receive real-time notifications:

```bash
POST /api/v1/webhooks
{
  "url": "https://your-app.com/webhooks",
  "events": ["workflow.completed", "approval.required", "cost.threshold"]
}
```

## SDKs

Official SDKs are available for:

- **Python**: `pip install agent-orchestrator`
- **TypeScript/JavaScript**: `npm install @agent-orchestrator/sdk`

See [SDK Documentation](https://docs.agent-orchestrator.dev/sdk) for detailed usage.

## OpenAPI Specification

Interactive API documentation is available at:

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`

## Support

- **Documentation**: https://docs.agent-orchestrator.dev
- **GitHub Issues**: https://github.com/orchestly-ai/platform/issues
- **Email**: support@agent-orchestrator.dev

---

**API Version**: 1.0.0
**Last Updated**: December 2025
