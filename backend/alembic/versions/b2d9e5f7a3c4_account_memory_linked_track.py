"""account_memory: linked_track (Plan ②, 2026-05-20)

Revision ID: b2d9e5f7a3c4
Revises: a1c8d4e6f2b9
Create Date: 2026-05-20

Adds the ``linked_track`` column to ``account_memory`` so the unified-memory
layer can tag each row with the student's active 赛道 at write time:

  - linked_track (TEXT, default ''): canonical track name (e.g.
    '二级买方·基本面') the student was working on when this memory was
    captured. Used by ArchivePanel to show the track tag on each card and
    by the recall path to optionally filter memory by track.

Idempotent — no-op if column already present.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d9e5f7a3c4'
down_revision: Union[str, Sequence[str], None] = 'a1c8d4e6f2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'account_memory'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return
    existing_cols = {col['name'] for col in inspector.get_columns(TABLE_NAME)}
    if 'linked_track' not in existing_cols:
        op.add_column(
            TABLE_NAME,
            sa.Column('linked_track', sa.Text, nullable=False, server_default=''),
        )


def downgrade() -> None:
    # SQLite ALTER TABLE DROP COLUMN requires copy+rebuild; leave column in
    # place — safe default ('') keeps older readers compatible.
    pass
