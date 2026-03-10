"""SQLite compatible schema for all features

Revision ID: 20260102_0001
Revises: 20260104_0001
Create Date: 2026-01-02 00:01:00.000000

This migration creates SQLite-compatible tables for all features that were
previously PostgreSQL-only. Uses TEXT for JSON columns and VARCHAR for ENUMs.
"""
from alembic import op
import sqlalchemy as sa
import os

# revision identifiers, used by Alembic.
revision = '20260102_0001'
down_revision = '20260104_0001'
branch_labels = None
depends_on = None

# Detect if we're using SQLite
def is_sqlite():
    bind = op.get_bind()
    return bind.dialect.name == 'sqlite'


def upgrade() -> None:
    # Skip if tables already exist (for PostgreSQL which may have them from earlier migrations)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # =============================================
    # APPROVAL / HITL TABLES
    # =============================================

    if 'approval_requests' not in existing_tables:
        op.create_table(
            'approval_requests',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('workflow_execution_id', sa.Integer(), nullable=True),
            sa.Column('task_id', sa.Integer(), nullable=True),
            sa.Column('node_id', sa.String(length=255), nullable=True),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('context', sa.Text(), nullable=True),  # JSON as TEXT for SQLite
            sa.Column('requested_by_user_id', sa.String(length=255), nullable=False),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('required_approvers', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('required_approval_count', sa.Integer(), default=1),
            sa.Column('priority', sa.String(length=50), default='medium'),  # ENUM as VARCHAR
            sa.Column('timeout_seconds', sa.Integer(), nullable=True),
            sa.Column('timeout_action', sa.String(length=50), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(length=50), default='pending', nullable=False),  # ENUM as VARCHAR
            sa.Column('approved_by_user_id', sa.String(length=255), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('response_time_seconds', sa.Float(), nullable=True),
            sa.Column('escalation_level', sa.Integer(), default=0),
            sa.Column('escalated_to_user_id', sa.String(length=255), nullable=True),
            sa.Column('escalated_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_approval_requests_status', 'approval_requests', ['status'])
        op.create_index('ix_approval_requests_priority', 'approval_requests', ['priority'])

    if 'approval_responses' not in existing_tables:
        op.create_table(
            'approval_responses',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('request_id', sa.Integer(), nullable=False),
            sa.Column('approver_user_id', sa.String(length=255), nullable=False),
            sa.Column('approver_email', sa.String(length=500), nullable=True),
            sa.Column('decision', sa.String(length=50), nullable=False),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('response_time_seconds', sa.Float(), nullable=True),
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.Column('user_agent', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['request_id'], ['approval_requests.id'], ondelete='CASCADE'),
        )

    # =============================================
    # A/B TESTING TABLES
    # =============================================

    if 'ab_experiments' not in existing_tables:
        op.create_table(
            'ab_experiments',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=255), nullable=False, unique=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('hypothesis', sa.Text(), nullable=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('created_by_user_id', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=50), default='draft'),  # draft, running, paused, completed
            sa.Column('traffic_percentage', sa.Integer(), default=100),
            sa.Column('allocation_strategy', sa.String(length=50), default='random'),
            sa.Column('start_date', sa.DateTime(), nullable=True),
            sa.Column('end_date', sa.DateTime(), nullable=True),
            sa.Column('target_sample_size', sa.Integer(), nullable=True),
            sa.Column('confidence_level', sa.Float(), default=0.95),
            sa.Column('primary_metric', sa.String(length=255), nullable=True),
            sa.Column('secondary_metrics', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('winner_variant_id', sa.Integer(), nullable=True),
            sa.Column('statistical_significance', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_ab_experiments_status', 'ab_experiments', ['status'])
        op.create_index('ix_ab_experiments_slug', 'ab_experiments', ['slug'], unique=True)

    if 'ab_variants' not in existing_tables:
        op.create_table(
            'ab_variants',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('experiment_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_control', sa.Boolean(), default=False),
            sa.Column('traffic_weight', sa.Integer(), default=50),
            sa.Column('configuration', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('assignments_count', sa.Integer(), default=0),
            sa.Column('conversions_count', sa.Integer(), default=0),
            sa.Column('conversion_rate', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_ab_variants_experiment_id', 'ab_variants', ['experiment_id'])

    if 'ab_assignments' not in existing_tables:
        op.create_table(
            'ab_assignments',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('experiment_id', sa.Integer(), nullable=False),
            sa.Column('variant_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.String(length=255), nullable=True),
            sa.Column('session_id', sa.String(length=255), nullable=True),
            sa.Column('context', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('converted', sa.Boolean(), default=False),
            sa.Column('conversion_value', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('converted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['variant_id'], ['ab_variants.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_ab_assignments_experiment_id', 'ab_assignments', ['experiment_id'])
        op.create_index('ix_ab_assignments_user_id', 'ab_assignments', ['user_id'])

    if 'ab_metrics' not in existing_tables:
        op.create_table(
            'ab_metrics',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('experiment_id', sa.Integer(), nullable=False),
            sa.Column('variant_id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=True),
            sa.Column('metric_name', sa.String(length=255), nullable=False),
            sa.Column('metric_value', sa.Float(), nullable=False),
            sa.Column('metadata', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['variant_id'], ['ab_variants.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_ab_metrics_experiment_id', 'ab_metrics', ['experiment_id'])

    # =============================================
    # TEAM / SETTINGS TABLES
    # =============================================

    if 'organizations' not in existing_tables:
        op.create_table(
            'organizations',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=255), nullable=False, unique=True),
            sa.Column('logo_url', sa.String(length=500), nullable=True),
            sa.Column('settings', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('plan', sa.String(length=50), default='free'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    if 'team_members' not in existing_tables:
        op.create_table(
            'team_members',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.String(length=255), nullable=False),
            sa.Column('email', sa.String(length=500), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=True),
            sa.Column('avatar_url', sa.String(length=500), nullable=True),
            sa.Column('role', sa.String(length=50), default='member'),  # admin, member, viewer
            sa.Column('permissions', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('status', sa.String(length=50), default='active'),  # active, invited, suspended
            sa.Column('invited_by_user_id', sa.String(length=255), nullable=True),
            sa.Column('invited_at', sa.DateTime(), nullable=True),
            sa.Column('joined_at', sa.DateTime(), nullable=True),
            sa.Column('last_seen_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_team_members_organization_id', 'team_members', ['organization_id'])
        op.create_index('ix_team_members_email', 'team_members', ['email'])
        op.create_index('ix_team_members_user_id', 'team_members', ['user_id'])

    if 'api_keys' not in existing_tables:
        op.create_table(
            'api_keys',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('organization_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('key_prefix', sa.String(length=20), nullable=False),  # First 8 chars for display
            sa.Column('key_hash', sa.String(length=255), nullable=False),  # SHA256 hash
            sa.Column('created_by_user_id', sa.String(length=255), nullable=False),
            sa.Column('permissions', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('rate_limit', sa.Integer(), default=1000),  # requests per minute
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('usage_count', sa.Integer(), default=0),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_by_user_id', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_api_keys_organization_id', 'api_keys', ['organization_id'])
        op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
        op.create_index('ix_api_keys_is_active', 'api_keys', ['is_active'])

    # =============================================
    # COST TRACKING TABLE (if not exists)
    # =============================================

    if 'cost_records' not in existing_tables:
        op.create_table(
            'cost_records',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('agent_id', sa.String(length=255), nullable=True),
            sa.Column('task_id', sa.Integer(), nullable=True),
            sa.Column('workflow_id', sa.Integer(), nullable=True),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('model', sa.String(length=100), nullable=False),
            sa.Column('input_tokens', sa.Integer(), default=0),
            sa.Column('output_tokens', sa.Integer(), default=0),
            sa.Column('total_tokens', sa.Integer(), default=0),
            sa.Column('cost_usd', sa.Float(), default=0.0),
            sa.Column('metadata', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        op.create_index('ix_cost_records_organization_id', 'cost_records', ['organization_id'])
        op.create_index('ix_cost_records_agent_id', 'cost_records', ['agent_id'])
        op.create_index('ix_cost_records_created_at', 'cost_records', ['created_at'])

    # =============================================
    # AUDIT EVENTS TABLE (if not exists)
    # =============================================

    if 'audit_events' not in existing_tables:
        op.create_table(
            'audit_events',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('organization_id', sa.Integer(), nullable=True),
            sa.Column('user_id', sa.String(length=255), nullable=True),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('resource_type', sa.String(length=100), nullable=False),
            sa.Column('resource_id', sa.String(length=255), nullable=True),
            sa.Column('details', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.Column('user_agent', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        op.create_index('ix_audit_events_organization_id', 'audit_events', ['organization_id'])
        op.create_index('ix_audit_events_user_id', 'audit_events', ['user_id'])
        op.create_index('ix_audit_events_action', 'audit_events', ['action'])
        op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'])

    # =============================================
    # INTEGRATION MARKETPLACE TABLES
    # =============================================

    if 'integrations' not in existing_tables:
        op.create_table(
            'integrations',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('integration_id', sa.String(length=36), nullable=False, unique=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=255), nullable=False, unique=True),
            sa.Column('display_name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('long_description', sa.Text(), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('tags', sa.Text(), nullable=True),  # JSON array as TEXT
            sa.Column('integration_type', sa.String(length=50), nullable=False),
            sa.Column('auth_type', sa.String(length=50), nullable=False),
            sa.Column('configuration_schema', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('auth_config_schema', sa.Text(), nullable=True),
            sa.Column('supported_actions', sa.Text(), nullable=True),
            sa.Column('supported_triggers', sa.Text(), nullable=True),
            sa.Column('version', sa.String(length=50), server_default='1.0.0'),
            sa.Column('homepage_url', sa.String(length=500), nullable=True),
            sa.Column('documentation_url', sa.String(length=500), nullable=True),
            sa.Column('icon_url', sa.String(length=500), nullable=True),
            sa.Column('provider_name', sa.String(length=255), nullable=True),
            sa.Column('provider_url', sa.String(length=500), nullable=True),
            sa.Column('is_verified', sa.Boolean(), server_default='0'),
            sa.Column('is_community', sa.Boolean(), server_default='0'),
            sa.Column('is_featured', sa.Boolean(), server_default='0'),
            sa.Column('is_free', sa.Boolean(), server_default='1'),
            sa.Column('pricing_info', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=50), server_default='approved'),
            sa.Column('total_installations', sa.Integer(), server_default='0'),
            sa.Column('total_active_installations', sa.Integer(), server_default='0'),
            sa.Column('average_rating', sa.Float(), nullable=True),
            sa.Column('total_ratings', sa.Integer(), server_default='0'),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_integrations_slug', 'integrations', ['slug'], unique=True)
        op.create_index('ix_integrations_category', 'integrations', ['category'])

    if 'integration_installations' not in existing_tables:
        op.create_table(
            'integration_installations',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('installation_id', sa.String(length=36), nullable=False, unique=True),
            sa.Column('integration_id', sa.String(length=36), nullable=False),
            sa.Column('organization_id', sa.String(length=255), nullable=False),
            sa.Column('installed_version', sa.String(length=50), server_default='1.0.0'),
            sa.Column('status', sa.String(length=50), server_default='not_installed'),
            sa.Column('configuration', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('auth_credentials', sa.Text(), nullable=True),  # JSON as TEXT - encrypted credentials
            sa.Column('total_executions', sa.Integer(), server_default='0'),
            sa.Column('successful_executions', sa.Integer(), server_default='0'),
            sa.Column('failed_executions', sa.Integer(), server_default='0'),
            sa.Column('last_execution_at', sa.DateTime(), nullable=True),
            sa.Column('is_healthy', sa.Boolean(), server_default='1'),
            sa.Column('last_health_check_at', sa.DateTime(), nullable=True),
            sa.Column('health_check_message', sa.Text(), nullable=True),
            sa.Column('installed_by', sa.String(length=255), nullable=True),
            sa.Column('installed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['integration_id'], ['integrations.integration_id'], ondelete='CASCADE'),
        )
        op.create_index('ix_integration_installations_organization_id', 'integration_installations', ['organization_id'])
        op.create_index('ix_integration_installations_integration_id', 'integration_installations', ['integration_id'])

    if 'integration_ratings' not in existing_tables:
        op.create_table(
            'integration_ratings',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('rating_id', sa.String(length=36), nullable=False, unique=True),
            sa.Column('integration_id', sa.String(length=36), nullable=False),
            sa.Column('organization_id', sa.String(length=255), nullable=False),
            sa.Column('user_id', sa.String(length=255), nullable=False),
            sa.Column('rating', sa.Integer(), nullable=False),
            sa.Column('review', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['integration_id'], ['integrations.integration_id'], ondelete='CASCADE'),
        )
        op.create_index('ix_integration_ratings_integration_id', 'integration_ratings', ['integration_id'])

    if 'integration_execution_logs' not in existing_tables:
        op.create_table(
            'integration_execution_logs',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('log_id', sa.String(length=36), nullable=False, unique=True),
            sa.Column('installation_id', sa.String(length=36), nullable=True),
            sa.Column('action_id', sa.String(length=36), nullable=True),
            sa.Column('organization_id', sa.String(length=255), nullable=True),
            sa.Column('action_name', sa.String(length=255), nullable=True),
            sa.Column('input_parameters', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('output_result', sa.Text(), nullable=True),  # JSON as TEXT
            sa.Column('status', sa.String(length=50), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('error_code', sa.String(length=100), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('duration_ms', sa.Float(), nullable=True),
            sa.Column('workflow_execution_id', sa.String(length=36), nullable=True),
            sa.Column('task_id', sa.String(length=36), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['installation_id'], ['integration_installations.installation_id'], ondelete='CASCADE'),
        )
        op.create_index('ix_integration_execution_logs_installation_id', 'integration_execution_logs', ['installation_id'])

    # =============================================
    # INSERT DEFAULT ORGANIZATION
    # =============================================

    if 'organizations' not in existing_tables or is_sqlite():
        # Insert default org only if table was just created
        conn = op.get_bind()
        result = conn.execute(sa.text("SELECT COUNT(*) FROM organizations"))
        count = result.scalar()
        if count == 0:
            conn.execute(sa.text("""
                INSERT INTO organizations (name, slug, plan, settings)
                VALUES ('Default Organization', 'default', 'enterprise', '{}')
            """))


def downgrade() -> None:
    # Integration tables (drop in reverse dependency order)
    op.drop_table('integration_execution_logs')
    op.drop_table('integration_ratings')
    op.drop_table('integration_installations')
    op.drop_table('integrations')
    # Other tables
    op.drop_table('audit_events')
    op.drop_table('cost_records')
    op.drop_table('api_keys')
    op.drop_table('team_members')
    op.drop_table('organizations')
    op.drop_table('ab_metrics')
    op.drop_table('ab_assignments')
    op.drop_table('ab_variants')
    op.drop_table('ab_experiments')
    op.drop_table('approval_responses')
    op.drop_table('approval_requests')
