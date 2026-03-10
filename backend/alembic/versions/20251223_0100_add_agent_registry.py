"""add agent registry and governance

Revision ID: 20251223_0100
Revises: 20251219_0900
Create Date: 2025-12-23 01:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251223_0100'
down_revision = '20251219_0900'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create agent registry and governance tables"""

    # Create agents_registry table
    op.create_table(
        'agents_registry',
        sa.Column('agent_id', sa.String(255), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text),
        sa.Column('version', sa.String(50)),

        # Ownership
        sa.Column('owner_user_id', sa.String(255), nullable=False, index=True),
        sa.Column('owner_team_id', sa.String(255), index=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Classification
        sa.Column('category', sa.String(100), index=True),
        sa.Column('tags', postgresql.ARRAY(sa.String)),
        sa.Column('sensitivity', sa.String(50), server_default='internal'),

        # Lifecycle
        sa.Column('status', sa.String(50), server_default='draft', index=True),
        sa.Column('deployment_status', sa.String(50), server_default='not_deployed'),

        # Access Control
        sa.Column('data_sources_allowed', postgresql.ARRAY(sa.String)),
        sa.Column('permissions', postgresql.JSONB),

        # Metrics
        sa.Column('total_executions', sa.Integer, server_default='0'),
        sa.Column('total_cost_usd', sa.DECIMAL(10, 2), server_default='0.00'),
        sa.Column('avg_response_time_ms', sa.Integer),
        sa.Column('success_rate', sa.DECIMAL(5, 2)),

        # Governance
        sa.Column('requires_approval', sa.Boolean, server_default='true'),
        sa.Column('approved_by', sa.String(255)),
        sa.Column('approved_at', sa.TIMESTAMP),
        sa.Column('sunset_date', sa.TIMESTAMP),

        # Metadata
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_active_at', sa.TIMESTAMP),

        # Foreign Keys
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'])
    )

    # Create agent_approvals table
    op.create_table(
        'agent_approvals',
        sa.Column('approval_id', sa.String(255), primary_key=True),
        sa.Column('agent_id', sa.String(255), nullable=False, index=True),

        # Approval Workflow
        sa.Column('approval_stage', sa.String(50), index=True),
        sa.Column('approver_user_id', sa.String(255), index=True),
        sa.Column('status', sa.String(50), server_default='pending', index=True),

        # Justification
        sa.Column('requested_by', sa.String(255), nullable=False),
        sa.Column('request_reason', sa.Text),
        sa.Column('decision_reason', sa.Text),

        # Audit
        sa.Column('requested_at', sa.TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column('decided_at', sa.TIMESTAMP),

        # Foreign Keys
        sa.ForeignKeyConstraint(['agent_id'], ['agents_registry.agent_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approver_user_id'], ['users.user_id']),
        sa.ForeignKeyConstraint(['requested_by'], ['users.user_id'])
    )

    # Create agent_policies table
    op.create_table(
        'agent_policies',
        sa.Column('policy_id', sa.String(255), primary_key=True),
        sa.Column('organization_id', sa.String(255), nullable=False, index=True),

        # Policy Details
        sa.Column('policy_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('policy_type', sa.String(50), index=True),

        # Scope
        sa.Column('applies_to', sa.String(50), index=True),
        sa.Column('scope_value', sa.String(255)),

        # Policy Rules
        sa.Column('rules', postgresql.JSONB, nullable=False),

        # Enforcement
        sa.Column('enforcement_level', sa.String(50), server_default='warning'),
        sa.Column('violations_count', sa.Integer, server_default='0'),

        # Metadata
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('is_active', sa.Boolean, server_default='true'),

        # Foreign Keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.user_id'])
    )

    # Create agent_usage_log table
    op.create_table(
        'agent_usage_log',
        sa.Column('log_id', sa.String(255), primary_key=True),
        sa.Column('agent_id', sa.String(255), nullable=False, index=True),

        # Usage Details
        sa.Column('execution_id', sa.String(255), index=True),
        sa.Column('user_id', sa.String(255), index=True),
        sa.Column('team_id', sa.String(255), index=True),

        # Metrics
        sa.Column('execution_time_ms', sa.Integer),
        sa.Column('tokens_used', sa.Integer),
        sa.Column('cost_usd', sa.DECIMAL(10, 4)),
        sa.Column('success', sa.Boolean, index=True),

        # Data Access
        sa.Column('data_sources_accessed', postgresql.ARRAY(sa.String)),
        sa.Column('pii_accessed', sa.Boolean, server_default='false', index=True),

        # Timestamp
        sa.Column('executed_at', sa.TIMESTAMP, server_default=sa.func.now(), nullable=False, index=True),

        # Foreign Keys
        sa.ForeignKeyConstraint(['agent_id'], ['agents_registry.agent_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'])
    )

    # Create indexes for better query performance
    op.create_index('idx_agents_status_org', 'agents_registry', ['status', 'organization_id'])
    op.create_index('idx_agents_owner_status', 'agents_registry', ['owner_user_id', 'status'])
    op.create_index('idx_agents_team_status', 'agents_registry', ['owner_team_id', 'status'])
    op.create_index('idx_agents_category_status', 'agents_registry', ['category', 'status'])
    op.create_index('idx_agents_cost', 'agents_registry', ['total_cost_usd'])

    op.create_index('idx_approvals_agent_status', 'agent_approvals', ['agent_id', 'status'])
    op.create_index('idx_approvals_approver_status', 'agent_approvals', ['approver_user_id', 'status'])

    op.create_index('idx_policies_org_active', 'agent_policies', ['organization_id', 'is_active'])
    op.create_index('idx_policies_type_active', 'agent_policies', ['policy_type', 'is_active'])

    op.create_index('idx_usage_agent_time', 'agent_usage_log', ['agent_id', 'executed_at'])
    op.create_index('idx_usage_user_time', 'agent_usage_log', ['user_id', 'executed_at'])
    op.create_index('idx_usage_team_time', 'agent_usage_log', ['team_id', 'executed_at'])
    op.create_index('idx_usage_pii', 'agent_usage_log', ['pii_accessed', 'executed_at'])


def downgrade() -> None:
    """Drop agent registry and governance tables"""

    # Drop indexes first
    op.drop_index('idx_usage_pii', 'agent_usage_log')
    op.drop_index('idx_usage_team_time', 'agent_usage_log')
    op.drop_index('idx_usage_user_time', 'agent_usage_log')
    op.drop_index('idx_usage_agent_time', 'agent_usage_log')

    op.drop_index('idx_policies_type_active', 'agent_policies')
    op.drop_index('idx_policies_org_active', 'agent_policies')

    op.drop_index('idx_approvals_approver_status', 'agent_approvals')
    op.drop_index('idx_approvals_agent_status', 'agent_approvals')

    op.drop_index('idx_agents_cost', 'agents_registry')
    op.drop_index('idx_agents_category_status', 'agents_registry')
    op.drop_index('idx_agents_team_status', 'agents_registry')
    op.drop_index('idx_agents_owner_status', 'agents_registry')
    op.drop_index('idx_agents_status_org', 'agents_registry')

    # Drop tables (in reverse order of dependencies)
    op.drop_table('agent_usage_log')
    op.drop_table('agent_policies')
    op.drop_table('agent_approvals')
    op.drop_table('agents_registry')
