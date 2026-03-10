"""Add routing_strategies table

Revision ID: 20260104_0001
Revises: 20251223_0200
Create Date: 2026-01-04 00:01:00.000000

This migration adds the routing_strategies table for persisting LLM routing
strategy configuration per organization (TODO-004).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260104_0001'
down_revision = '20251223_0200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create routing_strategies table."""
    # Check if table already exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'routing_strategies' not in existing_tables:
        op.create_table(
            'routing_strategies',
            sa.Column('id', sa.String(length=100), nullable=False, primary_key=True),
            sa.Column('organization_id', sa.String(length=100), nullable=False),
            sa.Column('strategy', sa.String(length=50), nullable=False),
            sa.Column('config', sa.Text(), nullable=True),  # JSON as TEXT for SQLite compatibility
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )

        # Create index on organization_id
        op.create_index('idx_routing_strategy_org', 'routing_strategies', ['organization_id'])


def downgrade() -> None:
    """Drop routing_strategies table."""
    op.drop_index('idx_routing_strategy_org', table_name='routing_strategies')
    op.drop_table('routing_strategies')
