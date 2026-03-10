# Integration Patterns & Node Types Roadmap

> **Purpose**: Define all integration patterns for connecting customer systems to agent workflows, prioritized by enterprise demand.

---

## Table of Contents
1. [Current Integration Capabilities](#1-current-integration-capabilities)
2. [Planned Integration Nodes](#2-planned-integration-nodes)
3. [Implementation Phases](#3-implementation-phases)
4. [Technical Specifications](#4-technical-specifications)

---

## 1. Current Integration Capabilities

### ✅ Implemented (As of Jan 2026)

#### Tool/API Node (HTTP CRUD)
```typescript
interface ToolConfig {
  url: string                    // https://api.example.com/endpoint
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  headers?: Record<string, string>
  body?: string                  // JSON template with {{variables}}
  auth?: {
    type: 'none' | 'api_key' | 'bearer' | 'basic' | 'oauth2'
    apiKey?: string
    headerName?: string
    bearerToken?: string
    username?: string
    password?: string
  }
  timeout?: number               // milliseconds
  responseMapping?: string       // JSONPath to extract data
}
```

**Use Cases:**
- Call customer REST APIs
- Fetch data from third-party services
- Trigger webhooks
- Post to Slack/Discord
- Update CRM records

**Example:**
```json
{
  "url": "https://api.stripe.com/v1/charges",
  "method": "POST",
  "auth": {
    "type": "bearer",
    "bearerToken": "sk_live_xxx"
  },
  "body": "{\"amount\": {{amount}}, \"currency\": \"usd\"}"
}
```

#### Memory Node (BYOS - Vector Databases)
```typescript
interface MemoryConfig {
  operation: 'store' | 'query' | 'delete'
  providerId: string             // Reference to configured vector DB
  namespace?: string             // Logical partition
  content?: string               // For store operation
  query?: string                 // For query operation
  limit?: number                 // Top-K results
  filters?: Record<string, any>
  metadata?: Record<string, any>
}
```

**Supported Providers:**
- Pinecone
- Qdrant
- Weaviate
- Redis (vector search)
- Chroma
- PostgreSQL + pgvector

**Use Cases:**
- Store conversation history
- Semantic search over past interactions
- Long-term agent memory
- User preference storage

#### Knowledge Node (BYOD - Document Stores)
```typescript
interface KnowledgeConfig {
  connectorId: string            // Reference to RAG connector
  query: string                  // Search query
  limit?: number                 // Number of chunks
  minScore?: number              // Relevance threshold
  rerank?: boolean               // Use cross-encoder
  filters?: Record<string, any>
}
```

**Supported Connectors:**
- S3, GCS, Azure Blob
- Elasticsearch, OpenSearch
- Notion, Confluence
- Google Drive, SharePoint
- MongoDB, PostgreSQL

**Use Cases:**
- RAG over company docs
- Policy/compliance lookup
- Product documentation search
- Knowledge base queries

#### Integration Node (Pre-built SaaS)
```typescript
interface IntegrationConfig {
  integrationType: 'slack' | 'discord' | 'gmail' | 'stripe' | 'github' | ...
  action: string                 // Provider-specific action
  parameters: Record<string, any>
}
```

**Pre-built Integrations:** 15+ (Slack, Stripe, GitHub, etc.)

---

## 2. Planned Integration Nodes

### Phase 1 (Months 1-2): Event-Driven Workflows

#### 🎯 Priority 1: Webhook/Event Listener Node

**Problem:** Workflows currently require manual triggering. Enterprises need event-driven automation.

```typescript
interface WebhookConfig {
  // AUTO-GENERATED webhook URL by our platform
  webhookUrl: string             // https://api.agentorch.io/webhooks/{workflow_id}/{unique_id}

  // Security
  authentication: {
    type: 'none' | 'secret' | 'hmac' | 'oauth2'
    secret?: string              // Shared secret in header
    hmacHeader?: string          // X-Hub-Signature
    algorithm?: 'sha256' | 'sha1'
  }

  // Payload handling
  method: 'POST' | 'GET'
  contentType: 'application/json' | 'application/x-www-form-urlencoded'
  payloadMapping: {
    [key: string]: string        // Extract fields from webhook payload
  }

  // Filtering
  conditions?: {
    field: string
    operator: 'equals' | 'contains' | 'regex'
    value: string
  }[]

  // Response
  responseStatus: number         // 200, 202, etc.
  responseBody?: string
}
```

**Use Cases:**
- GitHub push → code review workflow
- Stripe payment → fulfillment workflow
- Form submission → lead processing
- Alert trigger → incident response

**Implementation:**
```python
# Backend: Create webhook endpoint
@router.post("/webhooks/{workflow_id}/{webhook_id}")
async def receive_webhook(
    workflow_id: str,
    webhook_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 1. Validate webhook signature
    # 2. Extract payload
    # 3. Check conditions
    # 4. Trigger workflow execution
    # 5. Return response
```

**Estimated Effort:** 2 weeks

#### 🎯 Priority 2: HITL (Human-in-the-Loop) Approval Node

**Problem:** Sensitive operations need human approval before proceeding.

```typescript
interface HITLConfig {
  approvers: string[]            // Email addresses or user IDs
  approvalType: 'any' | 'all' | 'majority'
  timeout?: number               // Auto-reject after N minutes
  timeoutAction: 'reject' | 'approve' | 'retry'

  // Notification
  notifyVia: ('email' | 'slack' | 'sms')[]
  emailTemplate?: string
  slackChannel?: string

  // Context for approver
  title: string
  description: string
  contextData: Record<string, any>  // Data to show approver

  // Actions
  approveLabel?: string          // "Approve Refund"
  rejectLabel?: string           // "Deny Refund"
  customActions?: {
    label: string
    value: string
  }[]
}
```

**Use Cases:**
- Refund requests > $1000
- Content publishing approval
- Contract generation review
- Data deletion requests
- High-value transactions

**Implementation:**
- Backend: `/api/hitl/approvals` (already exists!)
- Just need workflow node UI + executor integration

**Estimated Effort:** 1 week

---

### Phase 2 (Months 3-4): Data Infrastructure

#### 🎯 Priority 3: Message Queue Node

**Problem:** Modern apps use event streaming (Kafka, SQS). Need async integration.

```typescript
interface MessageQueueConfig {
  provider: 'kafka' | 'rabbitmq' | 'sqs' | 'pubsub' | 'servicebus' | 'redis_streams'
  operation: 'publish' | 'consume' | 'subscribe'

  // Connection
  connectionId: string           // Reference to configured connection

  // For Kafka/Pulsar
  topic?: string
  partition?: number
  consumerGroup?: string

  // For SQS/PubSub
  queueUrl?: string
  subscriptionName?: string

  // Message
  messageFormat: 'json' | 'avro' | 'protobuf' | 'raw'
  schema?: string                // Avro/Protobuf schema
  message?: string               // Template for publish

  // Behavior
  maxMessages?: number           // For consume operation
  waitTimeSeconds?: number       // Long polling
  acknowledgement: 'auto' | 'manual'
}
```

**Use Cases:**
- Workflow triggered by Kafka events
- Publish results to SQS queue
- Subscribe to user activity stream
- Process event batches

**Estimated Effort:** 3 weeks

#### 🎯 Priority 4: Database Node

**Problem:** Agents need direct database access without building APIs.

```typescript
interface DatabaseConfig {
  provider: 'postgres' | 'mysql' | 'mongodb' | 'dynamodb' | 'bigquery' | 'snowflake'
  operation: 'query' | 'insert' | 'update' | 'delete' | 'execute'

  // Connection
  connectionId: string           // Encrypted credentials reference
  database?: string
  schema?: string

  // For SQL databases
  query?: string                 // SQL query with {{parameters}}
  parameters?: Record<string, any>

  // For NoSQL
  collection?: string
  filter?: object                // MongoDB query
  document?: object              // For insert/update

  // Results
  limit?: number
  resultMapping?: string         // Extract specific fields

  // Safety
  readOnly?: boolean             // Prevent writes
  timeout?: number
}
```

**Use Cases:**
- Query production database for context
- Update user records
- Insert analytics events
- Bulk data processing

**Security Features:**
- Read-only mode by default
- Query timeout limits
- Connection pooling
- Audit logging

**Estimated Effort:** 3 weeks

---

### Phase 3 (Months 5-6): Advanced Data & Files

#### 🎯 Priority 5: File/Object Storage Node

```typescript
interface StorageConfig {
  provider: 's3' | 'gcs' | 'azure_blob' | 'dropbox' | 'box'
  operation: 'upload' | 'download' | 'list' | 'delete' | 'move'

  // Connection
  connectionId: string
  bucket: string
  path: string                   // Supports {{variables}}

  // For upload
  content?: string               // File content or reference
  contentType?: string
  metadata?: Record<string, string>

  // For download
  saveAs?: string                // Local path or variable name

  // For list
  prefix?: string
  recursive?: boolean
  maxResults?: number
}
```

**Use Cases:**
- Upload invoices to S3
- Download PDFs for processing
- Batch file operations
- Document archival

**Estimated Effort:** 2 weeks

#### 🎯 Priority 6: Streaming/Batch Processing Node

```typescript
interface DataPipelineConfig {
  provider: 'snowflake' | 'databricks' | 'bigquery' | 'redshift' | 'fivetran'
  operation: 'query' | 'load' | 'transform' | 'sync'

  // For batch processing
  source: {
    type: 'table' | 'query' | 'file'
    reference: string
  }

  destination?: {
    type: 'table' | 'file'
    reference: string
  }

  // Transformation
  transformSql?: string

  // Execution
  async: boolean                 // Run as background job
  jobId?: string                 // For status polling
}
```

**Use Cases:**
- Trigger Snowflake queries
- Sync data with Fivetran
- Run dbt transformations
- ML model inference on batch data

**Estimated Effort:** 4 weeks

---

### Phase 4 (Months 7-8): Specialized Integrations

#### Priority 7: Email Node (Advanced)

```typescript
interface EmailConfig {
  provider: 'sendgrid' | 'ses' | 'postmark' | 'gmail' | 'smtp'
  operation: 'send' | 'parse_incoming'

  // For sending
  from: string
  to: string[]
  cc?: string[]
  bcc?: string[]
  subject: string
  body: string                   // HTML or plain text
  template?: string              // Pre-defined template
  attachments?: {
    filename: string
    content: string              // Base64 or S3 URL
  }[]

  // For parsing
  webhookUrl?: string            // For incoming emails
  filters?: {
    from?: string
    subject?: string
    hasAttachment?: boolean
  }
}
```

**Use Cases:**
- Send personalized emails
- Process support tickets
- Extract invoice data from emails
- Automated follow-ups

**Estimated Effort:** 2 weeks

#### Priority 8: Custom Code Execution Node

```typescript
interface CodeExecutionConfig {
  runtime: 'python3.11' | 'node18' | 'go1.21' | 'rust'
  code: string                   // Sandboxed code execution

  // Input
  input: Record<string, any>

  // Environment
  packages?: string[]            // pip/npm packages to install
  envVars?: Record<string, string>

  // Limits
  timeout: number                // Max 300 seconds
  memory: number                 // Max 512MB

  // Security
  allowNetworkAccess: boolean
  allowFileSystem: boolean
}
```

**Use Cases:**
- Custom data transformations
- Complex business logic
- ML model inference
- Data validation

**Security:**
- Isolated containers (gVisor)
- Network restrictions
- Resource limits
- Audit logs

**Estimated Effort:** 4 weeks

---

## 3. Implementation Phases

### Phase 1: Event-Driven Foundations (Months 1-2)

**Goal:** Enable reactive workflows

```yaml
Deliverables:
  Nodes:
    - Webhook/Event Listener Node (2 weeks)
    - HITL Approval Node (1 week)

  Infrastructure:
    - Webhook ingestion service
    - Event filtering engine
    - Approval notification service

  Frontend:
    - Webhook config UI
    - Webhook testing tool
    - Approval dashboard

  Documentation:
    - Webhook setup guides
    - Example workflows
    - Security best practices

Estimated Cost: $30K (dev) + $5K (docs)
Success Metrics: 50% of workflows use webhooks
```

### Phase 2: Data Infrastructure (Months 3-4)

**Goal:** Direct data access

```yaml
Deliverables:
  Nodes:
    - Message Queue Node (3 weeks)
    - Database Node (3 weeks)

  Infrastructure:
    - Connection pooling service
    - Query timeout enforcement
    - Credential vault integration

  Frontend:
    - SQL query builder
    - Database connection manager
    - Query result viewer

  Security:
    - Read-only mode enforcement
    - Query approval workflow (optional)
    - Audit logging

Estimated Cost: $50K (dev) + $10K (security)
Success Metrics: 30% of workflows query databases
```

### Phase 3: Files & Batch Processing (Months 5-6)

**Goal:** Handle large-scale data

```yaml
Deliverables:
  Nodes:
    - File/Object Storage Node (2 weeks)
    - Streaming/Batch Node (4 weeks)

  Infrastructure:
    - Large file handling (chunked uploads)
    - Async job execution
    - Progress tracking

  Frontend:
    - File browser UI
    - Job status dashboard
    - Batch operation templates

Estimated Cost: $45K (dev)
Success Metrics: 20% of workflows process files
```

### Phase 4: Specialized Use Cases (Months 7-8)

**Goal:** Advanced integrations

```yaml
Deliverables:
  Nodes:
    - Email Node (2 weeks)
    - Custom Code Execution (4 weeks)

  Infrastructure:
    - Sandboxed execution environment
    - Email parsing service
    - Template management

  Security:
    - Code review system (optional)
    - Execution limits
    - Virus scanning (attachments)

Estimated Cost: $60K (dev) + $15K (security)
Success Metrics: 15% of workflows use custom code
```

---

## 4. Technical Specifications

### Node Execution Pattern

All integration nodes follow this pattern:

```python
async def _execute_integration_node(
    self,
    node_data: Dict,
    node_id: str
) -> Dict[str, Any]:
    """
    Generic integration executor pattern.

    Returns:
        {
            'latency_ms': float,
            'cost': float,
            'tokens_used': int,
            'response_data': Any,
            'success': bool,
            'error': Optional[str]
        }
    """
    import time

    config = node_data['data'].get('integrationConfig', {})
    start_time = time.time()

    try:
        # 1. Validate configuration
        self._validate_config(config)

        # 2. Resolve template variables
        config = self._resolve_variables(config, workflow_context)

        # 3. Execute operation (provider-specific)
        result = await self._execute_provider(config)

        # 4. Calculate metrics
        latency_ms = (time.time() - start_time) * 1000

        return {
            'latency_ms': latency_ms,
            'cost': self._calculate_cost(config),
            'tokens_used': 0,  # Or embedding tokens if applicable
            'response_data': result,
            'success': True
        }

    except Exception as e:
        logger.error(f"{node_id} failed: {e}")
        return {
            'latency_ms': (time.time() - start_time) * 1000,
            'cost': 0,
            'tokens_used': 0,
            'response_data': None,
            'success': False,
            'error': str(e)
        }
```

### Template Variable System

All nodes support template variables:

```typescript
// Input
{
  "url": "https://api.stripe.com/v1/customers/{{customer_id}}/charges",
  "body": {
    "amount": "{{workflow_input.amount}}",
    "metadata": {
      "workflow_id": "{{workflow.id}}",
      "execution_time": "{{execution.timestamp}}"
    }
  }
}

// Available variables
{{workflow.id}}              // Current workflow ID
{{workflow.name}}            // Workflow name
{{execution.id}}             // Execution ID
{{execution.timestamp}}      // ISO timestamp
{{workflow_input.field}}     // Workflow input data
{{node_id.output.field}}     // Previous node output
{{env.API_KEY}}              // Environment variable
```

### Error Handling Strategy

```typescript
interface NodeRetryConfig {
  maxRetries: number           // Default: 3
  backoffMs: number            // Default: 1000 (exponential)
  retryOn: ('timeout' | 'error' | 'rate_limit')[]
  fallback?: {
    nodeId: string             // Execute alternative node on failure
  }
}
```

### Cost Tracking

Each integration node tracks costs:

```python
def _calculate_cost(self, config: Dict) -> float:
    """
    Calculate cost for integration operation.

    Categories:
    - API calls: $0.0001 per request
    - Database queries: $0.0005 per query
    - File uploads: $0.01 per GB
    - Streaming: $0.10 per million events
    """
    costs = {
        'api_call': 0.0001,
        'database_query': 0.0005,
        'file_upload_gb': 0.01,
        'streaming_million': 0.10,
    }

    operation_type = self._get_operation_type(config)
    return costs.get(operation_type, 0)
```

---

## Summary: Integration Roadmap

| Phase | Timeline | Nodes | Effort | Cost |
|-------|----------|-------|--------|------|
| **Current** | Done | Tool/API, Memory, Knowledge, Integration | — | — |
| **Phase 1** | Months 1-2 | Webhook, HITL | 3 weeks | $35K |
| **Phase 2** | Months 3-4 | Message Queue, Database | 6 weeks | $60K |
| **Phase 3** | Months 5-6 | File Storage, Batch Processing | 6 weeks | $45K |
| **Phase 4** | Months 7-8 | Email, Custom Code | 6 weeks | $75K |
| **Total** | 8 months | 11 new nodes | 21 weeks | $215K |

---

## Next Steps

1. **Validate priorities** with 10 enterprise customers
2. **Start Phase 1** implementation (Webhook + HITL)
3. **Create node templates** for rapid development
4. **Build testing framework** for integration nodes
5. **Update pricing** to reflect new capabilities

---

*Document Version: 1.0*
*Last Updated: January 2026*
*Owner: Product & Engineering*
