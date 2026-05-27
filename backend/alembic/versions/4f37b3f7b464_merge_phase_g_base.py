"""merge_phase_g_base

Revision ID: 4f37b3f7b464
Revises: a26052601, d8f3a2e7c941
Create Date: 2026-05-27 21:31:21.004050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f37b3f7b464'
down_revision: Union[str, Sequence[str], None] = ('a26052601', 'd8f3a2e7c941')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
