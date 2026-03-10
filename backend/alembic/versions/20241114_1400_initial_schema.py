"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2024-11-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema."""

    # Create agents table
    op.create_table(
        'agents',
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('framework', sa.String(length=50), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('capabilities', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('max_concurrent_tasks', sa.Integer(), nullable=False),
        sa.Column('cost_limit_daily', sa.Float(), nullable=False),
        sa.Column('cost_limit_monthly', sa.Float(), nullable=False),
        sa.Column('llm_provider', sa.String(length=50), nullable=False),
        sa.Column('llm_model', sa.String(length=100), nullable=True),
        sa.Column('extra_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('agent_id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_agent_status', 'agents', ['status'])
    # Note: GIN index on capabilities removed - JSON type doesn't support it efficiently
    # If needed, convert capabilities column to JSONB type in a future migration

    # Create agent_states table
    op.create_table(
        'agent_states',
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('active_tasks', sa.Integer(), nullable=False),
        sa.Column('tasks_completed', sa.Integer(), nullable=False),
        sa.Column('tasks_failed', sa.Integer(), nullable=False),
        sa.Column('total_cost_today', sa.Float(), nullable=False),
        sa.Column('total_cost_month', sa.Float(), nullable=False),
        sa.Column('cost_last_reset_day', sa.DateTime(), nullable=True),
        sa.Column('cost_last_reset_month', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('agent_id')
    )

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('capability', sa.String(length=100), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('input_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('output_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('assigned_agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('actual_cost', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_agent_id'], ['agents.agent_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('task_id')
    )
    op.create_index('idx_task_capability', 'tasks', ['capability'])
    op.create_index('idx_task_status', 'tasks', ['status'])
    op.create_index('idx_task_agent', 'tasks', ['assigned_agent_id'])
    op.create_index('idx_task_created', 'tasks', ['created_at'])
    op.create_index('idx_task_capability_status', 'tasks', ['capability', 'status'])
    op.create_index('idx_task_agent_status', 'tasks', ['assigned_agent_id', 'status'])

    # Create task_executions table
    op.create_table(
        'task_executions',
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('llm_calls', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('logs', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('extra_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.task_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('execution_id')
    )
    op.create_index('idx_execution_task', 'task_executions', ['task_id'])
    op.create_index('idx_execution_agent', 'task_executions', ['agent_id'])
    op.create_index('idx_execution_started', 'task_executions', ['started_at'])

    # Create metrics table
    op.create_table(
        'metrics',
        sa.Column('metric_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_type', sa.String(length=50), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('capability', sa.String(length=100), nullable=True),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('metric_id')
    )
    op.create_index('idx_metric_timestamp', 'metrics', ['timestamp'])
    op.create_index('idx_metric_name', 'metrics', ['metric_name'])
    op.create_index('idx_metric_agent', 'metrics', ['agent_id'])
    op.create_index('idx_metric_capability', 'metrics', ['capability'])
    op.create_index('idx_metric_name_time', 'metrics', ['metric_name', 'timestamp'])
    op.create_index('idx_metric_agent_time', 'metrics', ['agent_id', 'timestamp'])
    op.create_index('idx_metric_capability_time', 'metrics', ['capability', 'timestamp'])

    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_type', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('extra_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.task_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('alert_id')
    )
    op.create_index('idx_alert_type', 'alerts', ['alert_type'])
    op.create_index('idx_alert_severity', 'alerts', ['severity'])
    op.create_index('idx_alert_state', 'alerts', ['state'])
    op.create_index('idx_alert_created', 'alerts', ['created_at'])
    op.create_index('idx_alert_type_state', 'alerts', ['alert_type', 'state'])
    op.create_index('idx_alert_severity_created', 'alerts', ['severity', 'created_at'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('alerts')
    op.drop_table('metrics')
    op.drop_table('task_executions')
    op.drop_table('tasks')
    op.drop_table('agent_states')
    op.drop_table('agents')
