"""Enhance API keys table with rate limiting, quotas, and rotation

Revision ID: 20260114_1000
Revises: c3d4e5f6a7b8
Create Date: 2026-01-14 10:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260114_1000'
down_revision = 'c3d4e5f6a7b8'  # Depends on RAG BYOD migration
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    """Add rate limiting, quotas, IP whitelisting, and key rotation fields."""

    # Add new columns to api_keys table (idempotent)
    if not column_exists('api_keys', 'rate_limit_per_second'):
        op.add_column('api_keys', sa.Column('rate_limit_per_second', sa.Integer(), nullable=True, server_default='100'))
    if not column_exists('api_keys', 'monthly_quota'):
        op.add_column('api_keys', sa.Column('monthly_quota', sa.Integer(), nullable=True))
    if not column_exists('api_keys', 'ip_whitelist'):
        op.add_column('api_keys', sa.Column('ip_whitelist', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'))
    if not column_exists('api_keys', 'created_by'):
        op.add_column('api_keys', sa.Column('created_by', sa.String(length=100), nullable=True))
    if not column_exists('api_keys', 'revoked_by'):
        op.add_column('api_keys', sa.Column('revoked_by', sa.String(length=100), nullable=True))
    if not column_exists('api_keys', 'previous_key_hash'):
        op.add_column('api_keys', sa.Column('previous_key_hash', sa.String(length=64), nullable=True))
    if not column_exists('api_keys', 'previous_key_expires_at'):
        op.add_column('api_keys', sa.Column('previous_key_expires_at', sa.DateTime(), nullable=True))

    # Create indexes (idempotent)
    if not index_exists('api_keys', 'idx_api_keys_hash'):
        op.create_index('idx_api_keys_hash', 'api_keys', ['key_hash'])
    if not index_exists('api_keys', 'idx_api_keys_org'):
        op.create_index('idx_api_keys_org', 'api_keys', ['organization_id'])


def downgrade():
    """Remove enhanced API key fields."""

    # Drop indexes (idempotent)
    if index_exists('api_keys', 'idx_api_keys_org'):
        op.drop_index('idx_api_keys_org', table_name='api_keys')
    if index_exists('api_keys', 'idx_api_keys_hash'):
        op.drop_index('idx_api_keys_hash', table_name='api_keys')

    # Drop columns (idempotent)
    if column_exists('api_keys', 'previous_key_expires_at'):
        op.drop_column('api_keys', 'previous_key_expires_at')
    if column_exists('api_keys', 'previous_key_hash'):
        op.drop_column('api_keys', 'previous_key_hash')
    if column_exists('api_keys', 'revoked_by'):
        op.drop_column('api_keys', 'revoked_by')
    if column_exists('api_keys', 'created_by'):
        op.drop_column('api_keys', 'created_by')
    if column_exists('api_keys', 'ip_whitelist'):
        op.drop_column('api_keys', 'ip_whitelist')
    if column_exists('api_keys', 'monthly_quota'):
        op.drop_column('api_keys', 'monthly_quota')
    if column_exists('api_keys', 'rate_limit_per_second'):
        op.drop_column('api_keys', 'rate_limit_per_second')
