"""
Alembic Environment Configuration

Manages database migrations for the agent orchestration platform.
Uses synchronous driver (psycopg2) for migrations to support multi-statement executes.
"""

from logging.config import fileConfig
from sqlalchemy import pool, create_engine

from alembic import context

# Import models and settings
import sys
from pathlib import Path

# Add agent-orchestration directory to path for imports
# env.py is at: agent-orchestration/backend/alembic/env.py
# We need: agent-orchestration/ in the path
agent_orchestration_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(agent_orchestration_dir))

from backend.database.session import Base
from backend.database.models import (
    AgentModel, AgentStateModel, TaskModel, TaskExecutionModel,
    MetricModel, AlertModel
)
# Import workflow models from shared (canonical location)
from backend.shared.workflow_models import WorkflowModel, WorkflowExecutionModel
# Import scheduler models
from backend.shared.scheduler_models import (
    ScheduledWorkflowModel, ScheduleExecutionHistoryModel, OrganizationScheduleLimits
)
# Import memory models (BYOS)
from backend.shared.memory_models import (
    MemoryProviderConfigModel, AgentMemoryNamespaceModel
)
# Import RAG models (BYOD)
from backend.shared.rag_models import (
    RAGConnectorConfigModel, RAGDocumentIndexModel, RAGQueryHistoryModel
)
from backend.shared.config import get_settings

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata

# Get database URL - detect SQLite vs PostgreSQL
import os
settings = get_settings()

USE_SQLITE = os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes")

if USE_SQLITE:
    # Use SQLite for local development
    database_url = "sqlite:///./test_workflow.db"
else:
    # Use synchronous postgresql driver for migrations (supports multi-statement)
    database_url = settings.DATABASE_URL

config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode with sync engine.

    Uses psycopg2 (sync driver) to support multi-statement SQL.
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
