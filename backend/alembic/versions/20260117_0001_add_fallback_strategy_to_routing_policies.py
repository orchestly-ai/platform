"""Add fallback_strategy column to routing_policies table

Revision ID: 20260117_0001
Revises: f115080920ca
Create Date: 2026-01-17 19:00:00.000000

This migration adds the fallback_strategy column to the routing_policies table
to support configuring a fallback routing strategy when the primary strategy fails.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260117_0001'
down_revision = 'f115080920ca'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add fallback_strategy column to routing_policies."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Check if routing_policies table exists
    existing_tables = inspector.get_table_names()
    if 'routing_policies' not in existing_tables:
        return

    # Check if column already exists
    existing_columns = [col['name'] for col in inspector.get_columns('routing_policies')]

    if 'fallback_strategy' not in existing_columns:
        op.add_column(
            'routing_policies',
            sa.Column('fallback_strategy', sa.String(50), nullable=True)
        )


def downgrade() -> None:
    """Remove fallback_strategy column from routing_policies."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = inspector.get_table_names()
    if 'routing_policies' not in existing_tables:
        return

    existing_columns = [col['name'] for col in inspector.get_columns('routing_policies')]

    if 'fallback_strategy' in existing_columns:
        op.drop_column('routing_policies', 'fallback_strategy')
