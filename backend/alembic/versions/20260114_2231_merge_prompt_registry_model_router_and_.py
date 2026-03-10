"""merge prompt_registry, model_router, and other migration heads

Revision ID: f115080920ca
Revises: d1e2f3a4b5c6, d4e5f6a7b8c9, 20260114_1000
Create Date: 2026-01-14 22:31:34.881892+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f115080920ca'
down_revision: Union[str, Sequence[str], None] = ('d1e2f3a4b5c6', 'd4e5f6a7b8c9', '20260114_1000')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
