"""Add organization_id to core tables for multi-tenancy

Revision ID: 20260127_0001
Revises: 20260117_0001
Create Date: 2026-01-27 10:00:00.000000

This migration adds organization_id to agents, tasks, task_executions, metrics,
and alerts tables to support multi-tenancy isolation. Each record will be
scoped to an organization for proper customer data isolation.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260127_0001'
down_revision = '20260117_0001'
branch_labels = None
depends_on = None

# Default organization for existing data
DEFAULT_ORG_ID = '00000000-0000-0000-0000-000000000001'


def upgrade() -> None:
    """Add organization_id columns to core tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Tables to add organization_id to
    tables_to_update = ['agents', 'tasks', 'task_executions', 'metrics', 'alerts']

    for table_name in tables_to_update:
        if table_name not in existing_tables:
            continue

        existing_columns = [col['name'] for col in inspector.get_columns(table_name)]

        if 'organization_id' not in existing_columns:
            # Add column as nullable first
            op.add_column(
                table_name,
                sa.Column('organization_id', sa.String(255), nullable=True)
            )

            # Set default value for existing rows
            op.execute(
                f"UPDATE {table_name} SET organization_id = '{DEFAULT_ORG_ID}' WHERE organization_id IS NULL"
            )

            # Make column non-nullable
            op.alter_column(
                table_name,
                'organization_id',
                existing_type=sa.String(255),
                nullable=False
            )

            # Add index for organization_id
            op.create_index(
                f'idx_{table_name}_organization',
                table_name,
                ['organization_id']
            )

    # Add composite indexes for common queries
    # Agents: org + status
    if 'agents' in existing_tables:
        try:
            op.create_index(
                'idx_agent_org_status',
                'agents',
                ['organization_id', 'status']
            )
        except Exception:
            pass  # Index might already exist

    # Tasks: org + status
    if 'tasks' in existing_tables:
        try:
            op.create_index(
                'idx_task_org_status',
                'tasks',
                ['organization_id', 'status']
            )
        except Exception:
            pass  # Index might already exist

    # Metrics: org + timestamp
    if 'metrics' in existing_tables:
        try:
            op.create_index(
                'idx_metric_org_time',
                'metrics',
                ['organization_id', 'timestamp']
            )
        except Exception:
            pass  # Index might already exist

    # Alerts: org + state
    if 'alerts' in existing_tables:
        try:
            op.create_index(
                'idx_alert_org_state',
                'alerts',
                ['organization_id', 'state']
            )
        except Exception:
            pass  # Index might already exist

    # Add foreign key constraints if organizations table exists
    if 'organizations' in existing_tables:
        for table_name in tables_to_update:
            if table_name not in existing_tables:
                continue
            try:
                op.create_foreign_key(
                    f'fk_{table_name}_organization',
                    table_name,
                    'organizations',
                    ['organization_id'],
                    ['organization_id']
                )
            except Exception:
                pass  # FK might already exist or fail in SQLite


def downgrade() -> None:
    """Remove organization_id columns from core tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    tables_to_update = ['agents', 'tasks', 'task_executions', 'metrics', 'alerts']

    for table_name in tables_to_update:
        if table_name not in existing_tables:
            continue

        existing_columns = [col['name'] for col in inspector.get_columns(table_name)]

        if 'organization_id' in existing_columns:
            # Drop foreign key if exists
            try:
                op.drop_constraint(f'fk_{table_name}_organization', table_name, type_='foreignkey')
            except Exception:
                pass

            # Drop indexes
            try:
                op.drop_index(f'idx_{table_name}_organization', table_name)
            except Exception:
                pass

            # Drop column
            op.drop_column(table_name, 'organization_id')

    # Drop composite indexes
    composite_indexes = [
        ('agents', 'idx_agent_org_status'),
        ('tasks', 'idx_task_org_status'),
        ('metrics', 'idx_metric_org_time'),
        ('alerts', 'idx_alert_org_state'),
    ]

    for table_name, index_name in composite_indexes:
        if table_name in existing_tables:
            try:
                op.drop_index(index_name, table_name)
            except Exception:
                pass
