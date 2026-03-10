"""Merge migration heads

Revision ID: 6b8edcd9b4aa
Revises: 20260102_0001, 20260106_0100
Create Date: 2026-01-07 06:59:10.262765+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b8edcd9b4aa'
down_revision: Union[str, None] = ('20260102_0001', '20260106_0100')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
