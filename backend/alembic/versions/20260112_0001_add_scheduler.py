"""Add scheduler tables

Revision ID: a1b2c3d4e5f6
Revises: 578e738ebe65
Create Date: 2026-01-12 07:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '578e738ebe65'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Detect database type
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Use appropriate UUID type
    if is_sqlite:
        uuid_type = sa.String(36)
        json_type = sa.JSON()
    else:
        uuid_type = postgresql.UUID(as_uuid=True)
        json_type = postgresql.JSONB()

    # Create scheduled_workflows table
    op.create_table(
        'scheduled_workflows',
        sa.Column('schedule_id', uuid_type, primary_key=True),
        sa.Column('workflow_id', uuid_type, nullable=False),
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('schedule_type', sa.String(50), nullable=False, server_default='cron'),
        sa.Column('cron_expression', sa.String(100), nullable=True),
        sa.Column('interval_seconds', sa.Integer(), nullable=True),
        sa.Column('run_at', sa.DateTime(), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='UTC'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_status', sa.String(50), nullable=True),
        sa.Column('last_run_execution_id', uuid_type, nullable=True),
        sa.Column('last_run_error', sa.Text(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('total_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('retry_delay_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('allow_concurrent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_running', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('external_scheduler', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('external_trigger_token', sa.String(255), nullable=True),
        sa.Column('tags', json_type, nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('updated_by', sa.String(255), nullable=True),
    )

    # Create indexes for scheduled_workflows
    op.create_index('idx_schedule_org', 'scheduled_workflows', ['organization_id'])
    op.create_index('idx_schedule_workflow', 'scheduled_workflows', ['workflow_id'])
    op.create_index('idx_schedule_status', 'scheduled_workflows', ['status'])
    op.create_index('idx_schedule_next_run', 'scheduled_workflows', ['next_run_at'])
    op.create_index('idx_schedule_external', 'scheduled_workflows', ['external_scheduler'])

    # Create schedule_execution_history table
    op.create_table(
        'schedule_execution_history',
        sa.Column('history_id', uuid_type, primary_key=True),
        sa.Column('schedule_id', uuid_type, nullable=False),
        sa.Column('workflow_id', uuid_type, nullable=False),
        sa.Column('execution_id', uuid_type, nullable=True),
        sa.Column('organization_id', sa.String(255), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('trigger_source', sa.String(50), nullable=False, server_default='scheduler'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('output_summary', sa.JSON(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for schedule_execution_history
    op.create_index('idx_history_schedule', 'schedule_execution_history', ['schedule_id'])
    op.create_index('idx_history_org', 'schedule_execution_history', ['organization_id'])
    op.create_index('idx_history_scheduled_for', 'schedule_execution_history', ['scheduled_for'])
    op.create_index('idx_history_status', 'schedule_execution_history', ['status'])

    # Create organization_schedule_limits table
    op.create_table(
        'organization_schedule_limits',
        sa.Column('organization_id', sa.String(255), primary_key=True),
        sa.Column('tier', sa.String(50), nullable=False, server_default='free'),
        sa.Column('max_schedules', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('min_interval_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('max_concurrent_executions', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('current_schedule_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('executions_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_this_month', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('per_execution_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('billing_cycle_start', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_history_status', table_name='schedule_execution_history')
    op.drop_index('idx_history_scheduled_for', table_name='schedule_execution_history')
    op.drop_index('idx_history_org', table_name='schedule_execution_history')
    op.drop_index('idx_history_schedule', table_name='schedule_execution_history')

    op.drop_index('idx_schedule_external', table_name='scheduled_workflows')
    op.drop_index('idx_schedule_next_run', table_name='scheduled_workflows')
    op.drop_index('idx_schedule_status', table_name='scheduled_workflows')
    op.drop_index('idx_schedule_workflow', table_name='scheduled_workflows')
    op.drop_index('idx_schedule_org', table_name='scheduled_workflows')

    # Drop tables
    op.drop_table('organization_schedule_limits')
    op.drop_table('schedule_execution_history')
    op.drop_table('scheduled_workflows')
