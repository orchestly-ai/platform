# Database Layer

Production-grade PostgreSQL persistence for the Agent Orchestration Platform.

## Overview

The database layer provides persistent storage for:
- **Agents**: Configuration, capabilities, and registration
- **Agent States**: Runtime metrics and cost tracking
- **Tasks**: Full task lifecycle and results
- **Task Executions**: Detailed execution history
- **Metrics**: Time-series data (ready for TimescaleDB)
- **Alerts**: Alert history and audit trail

## Architecture

```
backend/database/
├── __init__.py           # Module initialization
├── session.py            # SQLAlchemy async session management
├── models.py             # ORM models (6 tables)
├── repositories.py       # Data access layer
└── README.md            # This file

backend/alembic/
├── env.py               # Alembic environment configuration
├── script.py.mako       # Migration template
└── versions/            # Migration scripts
    └── 20241114_1400_initial_schema.py

backend/
├── alembic.ini          # Alembic configuration
└── migrate.py           # Migration CLI tool
```

## Database Schema

### Tables

**agents**
- Primary table for agent registration
- Stores configuration, capabilities, and metadata
- Indexed by: status, capabilities (GIN index)

**agent_states**
- One-to-one with agents
- Tracks runtime state (active tasks, costs)
- Updated frequently during task execution

**tasks**
- Stores all tasks with full lifecycle
- Input/output data stored as JSON
- Indexed by: capability, status, agent, timestamps
- Composite indexes for efficient queries

**task_executions**
- Detailed execution logs for debugging
- Tracks retries, duration, costs
- LLM usage statistics

**metrics**
- Time-series metrics storage
- Ready for TimescaleDB hypertable conversion
- Indexed for fast time-range queries

**alerts**
- Alert history and state tracking
- Links to agents/tasks for context
- Indexed by type, severity, state

### Relationships

```
agents (1) ──< (N) tasks
   │
   │ (1:1)
   │
agent_states

tasks (1) ──< (N) task_executions

agents (1) ──< (N) alerts
tasks (1) ──< (N) alerts
```

## Setup

### 1. Configure Database URL

In `.env`:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/agent_orchestration
```

Or use the default from docker-compose:
```bash
DATABASE_URL=postgresql://postgres:postgres@db:5432/agent_orchestration
```

### 2. Run Migrations

Using the migration CLI:

```bash
cd backend

# Check current status
python migrate.py check

# Initialize database (first time only)
python migrate.py init

# Or use Alembic migrations
python migrate.py upgrade head

# Create new migration (after model changes)
python migrate.py create "add_new_column"
```

### 3. Using Docker Compose

Database is automatically initialized when using docker-compose:

```bash
docker-compose up -d

# Check migration status
docker-compose exec api python migrate.py check

# Run migrations
docker-compose exec api python migrate.py upgrade head
```

## Usage

### Repository Pattern

Use repositories for all database operations:

```python
from backend.database.session import get_db
from backend.database.repositories import AgentRepository, TaskRepository

async def example(db: AsyncSession = Depends(get_db)):
    # Agent operations
    agent_repo = AgentRepository(db)

    # Create agent
    agent_id = await agent_repo.create(agent_config)

    # Get agent
    agent = await agent_repo.get(agent_id)

    # Find by capability
    agent_ids = await agent_repo.find_by_capability("ticket_triage")

    # Update state
    await agent_repo.update_state(
        agent_id,
        active_tasks=5,
        cost_delta=0.25
    )

    # Task operations
    task_repo = TaskRepository(db)

    # Create task
    task_id = await task_repo.create(task)

    # Complete task
    await task_repo.complete(
        task_id,
        output_data={"result": "..."},
        actual_cost=0.15
    )
```

### FastAPI Integration

Use dependency injection for database sessions:

```python
from fastapi import Depends
from backend.database.session import get_db

@app.post("/api/v1/agents")
async def register_agent(
    config: AgentConfig,
    db: AsyncSession = Depends(get_db)
):
    repo = AgentRepository(db)
    agent_id = await repo.create(config)
    return {"agent_id": str(agent_id)}
```

### Session Management

Sessions are managed automatically:
- Created on request start
- Committed on success
- Rolled back on error
- Closed after response

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Auto-commit
        except Exception:
            await session.rollback()  # Auto-rollback
            raise
        finally:
            await session.close()  # Auto-close
```

## Migration Guide

### Creating Migrations

1. **Modify models** in `backend/database/models.py`

2. **Generate migration**:
   ```bash
   python migrate.py create "description_of_change"
   ```

3. **Review migration** in `alembic/versions/`

4. **Apply migration**:
   ```bash
   python migrate.py upgrade head
   ```

### Common Migration Commands

```bash
# Upgrade to latest
python migrate.py upgrade head

# Downgrade one version
python migrate.py downgrade -1

# Show current version
python migrate.py current

# Show migration history
python migrate.py history

# Stamp database (for existing database)
python migrate.py stamp head

# Reset database (DESTROYS ALL DATA)
python migrate.py reset
```

## Performance Optimization

### Indexes

All tables have appropriate indexes:
- **Primary keys**: UUID with index
- **Foreign keys**: Indexed for joins
- **Query patterns**: Composite indexes for common queries
- **JSON columns**: GIN indexes for capability search

### Connection Pooling

Configured in `session.py`:
```python
engine = create_async_engine(
    database_url,
    pool_size=10,        # Normal connections
    max_overflow=20,     # Burst capacity
    pool_pre_ping=True,  # Verify before use
)
```

### Query Optimization

Use repositories for optimized queries:
- Proper use of indexes
- Eager loading with `selectinload()`
- Pagination with `limit()` and `offset()`
- Query result caching where appropriate

## TimescaleDB Migration (Future)

The `metrics` table is designed for TimescaleDB:

```sql
-- Convert to hypertable (after installing TimescaleDB)
SELECT create_hypertable('metrics', 'timestamp');

-- Create continuous aggregates
CREATE MATERIALIZED VIEW metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS hour,
    metric_name,
    agent_id,
    AVG(value) as avg_value,
    MAX(value) as max_value,
    MIN(value) as min_value,
    COUNT(*) as count
FROM metrics
GROUP BY hour, metric_name, agent_id;

-- Auto-refresh policy
SELECT add_continuous_aggregate_policy('metrics_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

## Monitoring

### Database Health Check

```python
from backend.database.session import engine

async def check_db_health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False
```

### Query Performance

Enable query logging in development:
```python
engine = create_async_engine(
    database_url,
    echo=True,  # Log all SQL queries
)
```

### Connection Pool Stats

Monitor pool usage:
```python
pool = engine.pool
print(f"Size: {pool.size()}")
print(f"Checked in: {pool.checkedin()}")
print(f"Checked out: {pool.checkedout()}")
print(f"Overflow: {pool.overflow()}")
```

## Backup & Recovery

### Backup

```bash
# Full database backup
pg_dump -h localhost -U postgres agent_orchestration > backup.sql

# Schema only
pg_dump -h localhost -U postgres -s agent_orchestration > schema.sql

# Data only
pg_dump -h localhost -U postgres -a agent_orchestration > data.sql
```

### Restore

```bash
# Restore full backup
psql -h localhost -U postgres agent_orchestration < backup.sql

# Restore to new database
createdb -h localhost -U postgres agent_orchestration_new
psql -h localhost -U postgres agent_orchestration_new < backup.sql
```

### Point-in-Time Recovery

Enable WAL archiving in PostgreSQL:
```
wal_level = replica
archive_mode = on
archive_command = 'cp %p /path/to/archive/%f'
```

## Troubleshooting

### Connection Errors

```python
# Check connection
async with engine.connect() as conn:
    result = await conn.execute(text("SELECT version()"))
    print(result.scalar())
```

### Migration Conflicts

```bash
# Show current revision
python migrate.py current

# Show expected revision
python migrate.py history | head -n 5

# Manually stamp if needed
python migrate.py stamp head
```

### Deadlocks

If you encounter deadlocks:
1. Use shorter transactions
2. Access tables in consistent order
3. Use `FOR UPDATE SKIP LOCKED` for queue operations
4. Monitor with `pg_stat_activity`

### Performance Issues

```sql
-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Find missing indexes
SELECT schemaname, tablename, attname, null_frac, avg_width, n_distinct
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY null_frac DESC;

-- Check table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
```

## Testing

### Test Database Setup

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from backend.database.session import Base

@pytest.fixture
async def test_db():
    # Create test database
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost/test_db"
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
```

### Repository Tests

```python
@pytest.mark.asyncio
async def test_agent_create(test_db):
    async with AsyncSession(test_db) as session:
        repo = AgentRepository(session)

        config = AgentConfig(name="test_agent", ...)
        agent_id = await repo.create(config)

        assert agent_id is not None

        # Verify
        agent = await repo.get(agent_id)
        assert agent.name == "test_agent"
```

## Best Practices

1. **Always use repositories** - Don't write raw SQL
2. **Use transactions** - Let `get_db()` handle commits/rollbacks
3. **Avoid N+1 queries** - Use `selectinload()` for relationships
4. **Index appropriately** - Add indexes for all query patterns
5. **Monitor performance** - Use `pg_stat_statements`
6. **Regular backups** - Automate with cron/systemd
7. **Test migrations** - Always test on staging first
8. **Version control** - Commit all migrations to git

## Resources

- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [TimescaleDB Documentation](https://docs.timescale.com/)
