# Prompt Registry API - Testing Guide

## Overview

The Prompt Registry provides a centralized system for managing AI prompts with versioning, similar to Docker Hub for container images.

## Features

- **Template Management**: Create and organize prompt templates
- **Semantic Versioning**: Version control for prompts (1.0.0, 1.1.0, etc.)
- **Variable Substitution**: Dynamic variables using `{{variable_name}}` syntax
- **Publishing**: Publish versions and set default versions
- **Usage Analytics**: Track invocations, latency, tokens, and success rates

## API Endpoints

Base URL: `http://localhost:8000/api/prompts`

### 1. Create Prompt Template

Creates a new prompt template with auto-generated slug.

```bash
curl -X POST http://localhost:8000/api/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Agent",
    "description": "Prompt for customer support interactions",
    "category": "customer_support"
  }'
```

**Response:**
```json
{
  "id": "uuid",
  "organization_id": "uuid",
  "name": "Customer Support Agent",
  "slug": "customer-support-agent",
  "description": "Prompt for customer support interactions",
  "category": "customer_support",
  "default_version_id": null,
  "is_active": true,
  "created_at": "2026-01-14T...",
  "updated_at": "2026-01-14T...",
  "created_by": "uuid"
}
```

### 2. List All Prompt Templates

```bash
curl -X GET "http://localhost:8000/api/prompts?category=customer_support&limit=10"
```

### 3. Get Specific Template

```bash
curl -X GET http://localhost:8000/api/prompts/customer-support-agent
```

### 4. Create Version 1.0.0

Creates a new version with automatic variable extraction from content.

```bash
curl -X POST http://localhost:8000/api/prompts/customer-support-agent/versions \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0.0",
    "content": "You are a helpful customer support agent.\n\nCustomer: {{customer_name}}\nIssue: {{issue_type}}\nPriority: {{priority}}\n\nPlease provide a professional and empathetic response to help resolve the customer'\''s issue.",
    "model_hint": "gpt-4o",
    "metadata": {
      "tested": true,
      "author": "team"
    }
  }'
```

**Response:**
```json
{
  "id": "uuid",
  "template_id": "uuid",
  "version": "1.0.0",
  "content": "You are a helpful customer support agent...",
  "variables": ["customer_name", "issue_type", "priority"],
  "model_hint": "gpt-4o",
  "metadata": {"tested": true, "author": "team"},
  "is_published": false,
  "published_at": null,
  "created_at": "2026-01-14T...",
  "created_by": "uuid"
}
```

### 5. Create Version 1.1.0

```bash
curl -X POST http://localhost:8000/api/prompts/customer-support-agent/versions \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.1.0",
    "content": "You are a helpful customer support agent specialized in {{product_category}}.\n\nCustomer: {{customer_name}}\nIssue: {{issue_type}}\nPriority: {{priority}}\nOrder ID: {{order_id}}\n\nPlease provide a professional and empathetic response to help resolve the customer'\''s issue.\nUse your knowledge of {{product_category}} to provide specific guidance.",
    "model_hint": "gpt-4o",
    "metadata": {
      "tested": true,
      "author": "team",
      "changelog": "Added product_category and order_id support"
    }
  }'
```

### 6. List All Versions

```bash
curl -X GET http://localhost:8000/api/prompts/customer-support-agent/versions
```

### 7. Get Specific Version

```bash
curl -X GET http://localhost:8000/api/prompts/customer-support-agent/versions/1.0.0
```

### 8. Publish Version 1.1.0

Marks version as published and sets it as the template's default version.

```bash
curl -X PUT http://localhost:8000/api/prompts/customer-support-agent/versions/1.1.0/publish
```

**Response:**
```json
{
  "id": "uuid",
  "template_id": "uuid",
  "version": "1.1.0",
  "content": "You are a helpful customer support agent...",
  "variables": ["customer_name", "issue_type", "priority", "order_id", "product_category"],
  "model_hint": "gpt-4o",
  "metadata": {...},
  "is_published": true,
  "published_at": "2026-01-14T...",
  "created_at": "2026-01-14T...",
  "created_by": "uuid"
}
```

### 9. Render Prompt with Variables

Substitutes variables and returns rendered content.

```bash
curl -X POST http://localhost:8000/api/prompts/customer-support-agent/render \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.1.0",
    "variables": {
      "customer_name": "John Doe",
      "issue_type": "Product not received",
      "priority": "High",
      "order_id": "ORD-12345",
      "product_category": "Electronics"
    }
  }'
```

**Response:**
```json
{
  "template_id": "uuid",
  "version_id": "uuid",
  "version": "1.1.0",
  "content": "You are a helpful customer support agent specialized in {{product_category}}...",
  "rendered_content": "You are a helpful customer support agent specialized in Electronics.\n\nCustomer: John Doe\nIssue: Product not received\nPriority: High\nOrder ID: ORD-12345\n\nPlease provide a professional and empathetic response...",
  "variables": {
    "customer_name": "John Doe",
    "issue_type": "Product not received",
    "priority": "High",
    "order_id": "ORD-12345",
    "product_category": "Electronics"
  },
  "model_hint": "gpt-4o"
}
```

### 10. Get Usage Statistics

Returns daily usage metrics for a specific version.

```bash
curl -X GET "http://localhost:8000/api/prompts/customer-support-agent/versions/1.1.0/stats?days=7"
```

**Response:**
```json
[
  {
    "id": "uuid",
    "version_id": "uuid",
    "date": "2026-01-14",
    "invocations": 150,
    "avg_latency_ms": 125.5,
    "avg_tokens": 450,
    "success_rate": 0.98
  }
]
```

## Testing Workflow

Follow these steps to test the complete workflow:

```bash
# 1. Create a prompt template
TEMPLATE=$(curl -X POST http://localhost:8000/api/prompts \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Prompt", "category": "test"}')

# 2. Create version 1.0.0
curl -X POST http://localhost:8000/api/prompts/test-prompt/versions \
  -H "Content-Type: application/json" \
  -d '{"version": "1.0.0", "content": "Hello {{name}}, welcome to {{product}}!"}'

# 3. Create version 1.1.0
curl -X POST http://localhost:8000/api/prompts/test-prompt/versions \
  -H "Content-Type: application/json" \
  -d '{"version": "1.1.0", "content": "Hello {{name}}, welcome to {{product}}! Your role: {{role}}"}'

# 4. Publish version 1.1.0
curl -X PUT http://localhost:8000/api/prompts/test-prompt/versions/1.1.0/publish

# 5. Render prompt with variables
curl -X POST http://localhost:8000/api/prompts/test-prompt/render \
  -H "Content-Type: application/json" \
  -d '{"variables": {"name": "Alice", "product": "AI Assistant", "role": "developer"}}'

# 6. Get usage stats
curl -X GET "http://localhost:8000/api/prompts/test-prompt/versions/1.1.0/stats?days=30"
```

## Architecture

### Models

- **PromptTemplateModel**: Stores prompt metadata and references
- **PromptVersionModel**: Stores versioned prompt content
- **PromptUsageStatsModel**: Tracks daily usage metrics

### Service Layer

**PromptService** provides:
- Template CRUD operations
- Version management
- Variable extraction and rendering
- Usage tracking
- Statistics aggregation

### Database Schema

```sql
-- prompt_templates: Template metadata
-- prompt_versions: Versioned content
-- prompt_usage_stats: Daily metrics
```

## Variable Syntax

Variables use double curly braces: `{{variable_name}}`

Example:
```
Hello {{customer_name}},

Your order {{order_id}} is {{status}}.

Best regards,
{{agent_name}}
```

Variables are automatically extracted and tracked in the `variables` field.

## Running the Test Suite

```bash
cd backend
python test_prompt_registry.py
```

This will test all functionality including:
- Template creation
- Version management
- Publishing
- Rendering with variables
- Usage statistics
