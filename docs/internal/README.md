# Internal API Documentation

> **CONFIDENTIAL - INTERNAL USE ONLY**
>
> This documentation contains proprietary implementation details and is not for external distribution.
> For public-facing documentation, see `/public/docs/`.

## Overview

This documentation covers the internal architecture, implementation details, and APIs that power the Agent Orchestration Platform. These details represent our core competitive advantages and should never be exposed externally.

## Documentation Structure

```
internal/
├── README.md                    # This file
├── architecture/
│   ├── overview.md              # System architecture
│   ├── multi-llm-routing.md     # Intelligent LLM routing system
│   ├── hybrid-oauth.md          # Hybrid OAuth implementation
│   ├── webhook-processing.md    # Webhook receiver architecture
│   └── cost-tracking.md         # Token & cost tracking system
├── api/
│   ├── internal-endpoints.md    # Internal-only API endpoints
│   ├── admin-apis.md            # Admin/management APIs
│   └── system-apis.md           # System-level APIs
└── implementation/
    ├── llm-gateway.md           # LLM gateway implementation
    ├── workflow-engine.md       # Workflow execution engine
    ├── time-travel-debug.md     # Time-travel debugging
    └── ab-testing.md            # A/B testing framework
```

## Quick Links

- [Architecture Overview](./architecture/overview.md)
- [Multi-LLM Routing](./architecture/multi-llm-routing.md)
- [Internal APIs](./api/internal-endpoints.md)

## Security Notice

These documents should:
- Never be committed to public repositories
- Never be shared with customers or partners
- Be accessed only by authorized engineering team members
- Be stored separately from public documentation

## Access Control

In production, this documentation should be:
1. Hosted on internal-only infrastructure
2. Protected by SSO/authentication
3. Audited for access logs
