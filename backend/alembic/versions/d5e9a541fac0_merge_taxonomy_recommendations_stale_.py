"""merge taxonomy + recommendations_stale heads

Revision ID: d5e9a541fac0
Revises: 0004_recommendations_stale, 0005_job_canonical_track
Create Date: 2026-05-19 16:02:11.180794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e9a541fac0'
down_revision: Union[str, Sequence[str], None] = ('0004_recommendations_stale', '0005_job_canonical_track')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
