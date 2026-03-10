"""Add settings tables (organizations, team_members, api_keys)

Revision ID: 20260105_1700
Revises: 20251219_0400
Create Date: 2026-01-05 17:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260105_1700'
down_revision = '20251219_0400'
branch_labels = None
depends_on = None


def upgrade():
    """Create team_members and api_keys tables."""

    # NOTE: organizations table already exists from RBAC migration (20251217_0900_add_rbac.py)
    # We're just adding team_members and api_keys tables

    # Create team_members table
    op.create_table(
        'team_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='member'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='invited'),
        sa.Column('invited_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_team_members_email', 'team_members', ['email'], unique=True)
    op.create_index('ix_team_members_organization_id', 'team_members', ['organization_id'])
    op.create_index('ix_team_members_user_id', 'team_members', ['user_id'])
    op.create_index('idx_team_member_org_email', 'team_members', ['organization_id', 'email'])
    op.create_index('idx_team_member_status', 'team_members', ['status'])

    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.organization_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
    op.create_index('ix_api_keys_is_active', 'api_keys', ['is_active'])
    op.create_index('ix_api_keys_organization_id', 'api_keys', ['organization_id'])
    op.create_index('idx_api_key_org_active', 'api_keys', ['organization_id', 'is_active'])
    op.create_index('idx_api_key_prefix', 'api_keys', ['key_prefix'])

    # Insert default organization if it doesn't exist (for fresh installations)
    op.execute("""
        INSERT INTO organizations (organization_id, name, slug, plan, max_users, max_agents, enabled_features, is_active, created_at, updated_at)
        VALUES ('default-org', 'Default Organization', 'default-org', 'enterprise', 100, 100, '[]'::jsonb, true, now(), now())
        ON CONFLICT (organization_id) DO NOTHING
    """)

    # Insert default admin team member
    op.execute("""
        INSERT INTO team_members (organization_id, user_id, email, name, role, status, joined_at)
        VALUES ('default-org', 'user_1', 'admin@example.com', 'Admin User', 'admin', 'active', now())
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    """Drop settings tables."""
    op.drop_table('api_keys')
    op.drop_table('team_members')
    # Note: organizations table is managed by RBAC migration, don't drop it here
