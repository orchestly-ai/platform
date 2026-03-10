"""add workflows tables

Revision ID: 002
Revises: 001
Create Date: 2024-12-03 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add workflows and workflow_executions tables.
    """
    # Create workflows table
    op.create_table(
        'workflows',
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSON(), nullable=True),
        sa.Column('nodes', postgresql.JSON(), nullable=False),
        sa.Column('edges', postgresql.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('is_template', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('execution_count', sa.Integer(), nullable=False, default=0),
        sa.Column('total_cost', sa.Float(), nullable=False, default=0.0),
        sa.Column('average_execution_time', sa.Float(), nullable=True),
        sa.Column('last_executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Create indexes for workflows
    op.create_index('idx_workflow_name', 'workflows', ['name'])
    op.create_index('idx_workflow_template', 'workflows', ['is_template'])
    # op.create_index('idx_workflow_tags', 'workflows', ['tags'], postgresql_using='gin'  # GIN index disabled - requires JSONB type)
    op.create_index('idx_workflow_created', 'workflows', ['created_at'])

    # Create workflow_executions table
    op.create_table(
        'workflow_executions',
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workflows.workflow_id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow_version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('input_data', postgresql.JSON(), nullable=True),
        sa.Column('output_data', postgresql.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=False, default=0.0),
        sa.Column('node_executions', postgresql.JSON(), nullable=False, default='[]'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
    )

    # Create indexes for workflow_executions
    op.create_index('idx_exec_workflow_status', 'workflow_executions', ['workflow_id', 'status'])
    op.create_index('idx_exec_started', 'workflow_executions', ['started_at'])
    op.create_index('idx_exec_workflow', 'workflow_executions', ['workflow_id'])


def downgrade() -> None:
    """
    Drop workflows and workflow_executions tables.
    """
    # Drop indexes
    op.drop_index('idx_exec_workflow', table_name='workflow_executions')
    op.drop_index('idx_exec_started', table_name='workflow_executions')
    op.drop_index('idx_exec_workflow_status', table_name='workflow_executions')

    op.drop_index('idx_workflow_created', table_name='workflows')
    op.drop_index('idx_workflow_tags', table_name='workflows')
    op.drop_index('idx_workflow_template', table_name='workflows')
    op.drop_index('idx_workflow_name', table_name='workflows')

    # Drop tables
    op.drop_table('workflow_executions')
    op.drop_table('workflows')
