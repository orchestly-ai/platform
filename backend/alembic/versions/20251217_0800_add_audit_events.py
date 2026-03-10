"""add audit events table

Revision ID: 20251217_0800
Revises: 002
Create Date: 2025-12-17 08:00:00.000000

Comprehensive audit logging for compliance (SOC 2, HIPAA, GDPR).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251217_0800'
down_revision = '002'
branch_labels = None
depends_on = None


def is_sqlite():
    """Check if running on SQLite"""
    bind = op.get_bind()
    return bind.dialect.name == 'sqlite'


def upgrade():
    """Create audit_events table"""

    # Check if table already exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'audit_events' in inspector.get_table_names():
        return

    # Use compatible types for SQLite vs PostgreSQL
    if is_sqlite():
        uuid_type = sa.String(36)
        inet_type = sa.String(50)
        json_type = sa.Text()
    else:
        from sqlalchemy.dialects import postgresql
        uuid_type = postgresql.UUID(as_uuid=True)
        inet_type = postgresql.INET()
        json_type = postgresql.JSON(astext_type=sa.Text())

    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('event_id', uuid_type, primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),

        # Actor
        sa.Column('user_id', sa.String(255), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('user_role', sa.String(100), nullable=True),

        # Session
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('request_id', sa.String(255), nullable=True),

        # Network
        sa.Column('ip_address', inet_type, nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),

        # Resource
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('resource_name', sa.String(255), nullable=True),

        # Action
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),

        # Data
        sa.Column('changes', json_type, nullable=True),
        sa.Column('request_data', json_type, nullable=True),
        sa.Column('response_data', json_type, nullable=True),

        # Outcome
        sa.Column('success', sa.Boolean(), nullable=False, default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(100), nullable=True),

        # Cost
        sa.Column('cost_impact', sa.Float(), nullable=True),

        # Additional context
        sa.Column('tags', json_type, nullable=True),
        sa.Column('metadata', json_type, nullable=True),

        # Compliance
        sa.Column('pii_accessed', sa.Boolean(), nullable=False, default=False),
        sa.Column('sensitive_action', sa.Boolean(), nullable=False, default=False),

        # Retention
        sa.Column('retention_days', sa.Integer(), nullable=False, default=2555),

        # Correlation
        sa.Column('parent_event_id', uuid_type, nullable=True),
        sa.Column('correlation_id', sa.String(255), nullable=True)
    )

    # Create indexes for common query patterns

    # Time-series queries
    op.create_index('idx_audit_timestamp', 'audit_events', ['timestamp'])
    op.create_index('idx_audit_timestamp_type', 'audit_events', ['timestamp', 'event_type'])

    # Event type
    op.create_index('idx_audit_event_type', 'audit_events', ['event_type'])
    op.create_index('idx_audit_severity', 'audit_events', ['severity'])

    # User activity
    op.create_index('idx_audit_user_time', 'audit_events', ['user_id', 'timestamp'])
    op.create_index('idx_audit_user_action', 'audit_events', ['user_id', 'action'])
    op.create_index('idx_audit_user_id', 'audit_events', ['user_id'])

    # Resource tracking
    op.create_index('idx_audit_resource', 'audit_events', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_resource_time', 'audit_events', ['resource_type', 'resource_id', 'timestamp'])
    op.create_index('idx_audit_resource_type', 'audit_events', ['resource_type'])
    op.create_index('idx_audit_resource_id', 'audit_events', ['resource_id'])
    op.create_index('idx_audit_action', 'audit_events', ['action'])

    # Security queries
    op.create_index('idx_audit_security', 'audit_events', ['severity', 'success', 'timestamp'])
    op.create_index('idx_audit_failed_auth', 'audit_events', ['event_type', 'success', 'ip_address'])
    op.create_index('idx_audit_success', 'audit_events', ['success'])
    op.create_index('idx_audit_ip_address', 'audit_events', ['ip_address'])

    # Compliance queries
    op.create_index('idx_audit_pii', 'audit_events', ['pii_accessed', 'timestamp'])
    op.create_index('idx_audit_sensitive', 'audit_events', ['sensitive_action', 'timestamp'])

    # Correlation
    op.create_index('idx_audit_correlation', 'audit_events', ['correlation_id', 'timestamp'])
    op.create_index('idx_audit_parent', 'audit_events', ['parent_event_id'])
    op.create_index('idx_audit_correlation_id', 'audit_events', ['correlation_id'])

    # Session tracking
    op.create_index('idx_audit_session', 'audit_events', ['session_id', 'timestamp'])
    op.create_index('idx_audit_session_id', 'audit_events', ['session_id'])
    op.create_index('idx_audit_request_id', 'audit_events', ['request_id'])

    # Tags (GIN index for JSON)
    # op.create_index('idx_audit_tags', 'audit_events', ['tags'], postgresql_using='gin'  # GIN index disabled - requires JSONB type)


def downgrade():
    """Drop audit_events table"""
    op.drop_table('audit_events')
