# Database Optimization Guide

## Index Strategy

### Core Indexes (Already Implemented)

The following indexes are defined in model files:

#### Workflow Tables
```sql
-- workflows table
CREATE INDEX idx_workflow_org ON workflows(organization_id);
CREATE INDEX idx_workflow_status ON workflows(status);
CREATE INDEX idx_workflow_created ON workflows(created_at);
CREATE INDEX idx_workflow_tags ON workflows USING gin(tags);

-- workflow_executions table
CREATE INDEX idx_exec_workflow ON workflow_executions(workflow_id);
CREATE INDEX idx_exec_org ON workflow_executions(organization_id);
CREATE INDEX idx_exec_status ON workflow_executions(status);
CREATE INDEX idx_exec_created ON workflow_executions(created_at);
```

#### Agent Tables
```sql
-- agents table
CREATE INDEX idx_agent_org ON agents(organization_id);
CREATE INDEX idx_agent_status ON agents(status);
CREATE INDEX idx_agent_type ON agents(agent_type);

-- agent_executions table
CREATE INDEX idx_agent_exec_agent ON agent_executions(agent_id);
CREATE INDEX idx_agent_exec_status ON agent_executions(status);
CREATE INDEX idx_agent_exec_created ON agent_executions(created_at);
```

### Recommended Additional Indexes

Add these indexes for production workloads:

```sql
-- Composite index for common query pattern
CREATE INDEX idx_workflow_org_status ON workflows(organization_id, status);

-- Partial index for active workflows only
CREATE INDEX idx_workflow_active ON workflows(organization_id)
WHERE status NOT IN ('archived', 'deleted');

-- Index for time-range queries
CREATE INDEX idx_exec_org_created ON workflow_executions(organization_id, created_at DESC);

-- Full-text search on workflow names
CREATE INDEX idx_workflow_name_search ON workflows
USING gin(to_tsvector('english', name));

-- JSONB indexes for workflow nodes
CREATE INDEX idx_workflow_nodes ON workflows USING gin(nodes jsonb_path_ops);
```

## Query Optimization

### Slow Query Patterns to Avoid

```python
# BAD: N+1 query pattern
workflows = await db.execute(select(Workflow).limit(100))
for w in workflows.scalars():
    executions = await db.execute(
        select(Execution).where(Execution.workflow_id == w.id)
    )  # 100 additional queries!

# GOOD: Eager loading
workflows = await db.execute(
    select(Workflow)
    .options(selectinload(Workflow.executions))
    .limit(100)
)  # Single query with JOIN
```

### Use EXPLAIN ANALYZE

```sql
EXPLAIN ANALYZE
SELECT * FROM workflows
WHERE organization_id = 'org_123'
  AND status = 'active'
ORDER BY created_at DESC
LIMIT 20;
```

Look for:
- Sequential scans on large tables (add index)
- High row estimates (statistics may be stale)
- Sort operations (add index for ORDER BY)

### Pagination Best Practices

```python
# BAD: OFFSET pagination (slow for large offsets)
query = select(Workflow).offset(10000).limit(20)

# GOOD: Cursor-based pagination
query = (
    select(Workflow)
    .where(Workflow.created_at < cursor_timestamp)
    .order_by(Workflow.created_at.desc())
    .limit(20)
)
```

## Connection Pooling

### SQLAlchemy Async Configuration

```python
# backend/database/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=20,           # Base connections
    max_overflow=10,        # Additional connections under load
    pool_timeout=30,        # Wait time for connection
    pool_recycle=1800,      # Recycle connections every 30 min
    pool_pre_ping=True,     # Verify connection before use
)
```

### Connection Pool Monitoring

```python
# Check pool status
from sqlalchemy import event

@event.listens_for(engine.sync_engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug(f"Connection checked out: {connection_record}")

@event.listens_for(engine.sync_engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    logger.debug(f"Connection returned: {connection_record}")
```

## PostgreSQL Configuration

### Recommended Settings for Production

```ini
# postgresql.conf

# Memory
shared_buffers = 256MB              # 25% of RAM for dedicated DB server
effective_cache_size = 768MB        # 75% of RAM
work_mem = 16MB                     # Per-query memory
maintenance_work_mem = 128MB        # For VACUUM, CREATE INDEX

# Connections
max_connections = 200               # Match pool size + overhead
superuser_reserved_connections = 3

# Write-Ahead Log
wal_level = replica
max_wal_size = 1GB
min_wal_size = 80MB

# Query Planning
random_page_cost = 1.1              # For SSDs
effective_io_concurrency = 200      # For SSDs
default_statistics_target = 100

# Logging (for debugging slow queries)
log_min_duration_statement = 500    # Log queries > 500ms
log_statement = 'ddl'               # Log schema changes
```

### Maintenance Tasks

```sql
-- Update statistics (run regularly)
ANALYZE workflows;
ANALYZE workflow_executions;
ANALYZE agents;

-- Reclaim space and update visibility map
VACUUM ANALYZE workflows;

-- Rebuild indexes (run during maintenance window)
REINDEX TABLE workflows;
```

## Monitoring Queries

### Slow Queries
```sql
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;
```

### Index Usage
```sql
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### Table Statistics
```sql
SELECT
    relname,
    n_live_tup,
    n_dead_tup,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables;
```
