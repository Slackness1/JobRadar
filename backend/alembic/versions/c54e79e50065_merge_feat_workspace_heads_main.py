"""merge feat workspace heads → main

Revision ID: c54e79e50065
Revises: 4d1aff7cec7b, c3e8a5b9d6f1
Create Date: 2026-05-22 11:33:05.386059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c54e79e50065'
down_revision: Union[str, Sequence[str], None] = ('4d1aff7cec7b', 'c3e8a5b9d6f1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
