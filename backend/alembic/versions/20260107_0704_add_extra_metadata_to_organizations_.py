"""Add extra_metadata to organizations table

Revision ID: 578e738ebe65
Revises: 6b8edcd9b4aa
Create Date: 2026-01-07 07:04:43.798714+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '578e738ebe65'
down_revision: Union[str, None] = '6b8edcd9b4aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def is_sqlite():
    """Check if running on SQLite"""
    bind = op.get_bind()
    return bind.dialect.name == 'sqlite'


def column_exists(table_name, column_name):
    """Check if column exists"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except:
        return False


def upgrade() -> None:
    """
    Add extra_metadata column to organizations table.
    """
    # Get database-specific types
    if is_sqlite():
        json_type = sa.Text()
    else:
        from sqlalchemy.dialects import postgresql
        json_type = postgresql.JSONB()

    # Add extra_metadata column if it doesn't exist
    if not column_exists('organizations', 'extra_metadata'):
        op.add_column('organizations', sa.Column('extra_metadata', json_type, nullable=True))


def downgrade() -> None:
    """
    Remove extra_metadata column from organizations table.
    """
    if column_exists('organizations', 'extra_metadata'):
        op.drop_column('organizations', 'extra_metadata')
