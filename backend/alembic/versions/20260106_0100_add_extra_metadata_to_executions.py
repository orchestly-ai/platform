"""Add extra_metadata to workflow_executions

Revision ID: 20260106_0100
Revises: 20260105_1700
Create Date: 2026-01-06 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260106_0100'
down_revision: Union[str, None] = '20260105_1700'
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
    Add extra_metadata column to workflow_executions table.
    """
    # Get database-specific types
    if is_sqlite():
        json_type = sa.Text()
    else:
        from sqlalchemy.dialects import postgresql
        json_type = postgresql.JSON()

    # Add extra_metadata column if it doesn't exist
    if not column_exists('workflow_executions', 'extra_metadata'):
        op.add_column('workflow_executions', sa.Column('extra_metadata', json_type, nullable=True))


def downgrade() -> None:
    """
    Remove extra_metadata column from workflow_executions table.
    """
    if column_exists('workflow_executions', 'extra_metadata'):
        op.drop_column('workflow_executions', 'extra_metadata')
