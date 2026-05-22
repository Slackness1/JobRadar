"""account_memory: linked_field_paths + needs_resync (Plan 1, 2026-05-20)

Revision ID: a1c8d4e6f2b9
Revises: b3f1c8d5a2e9
Create Date: 2026-05-20

Adds two columns to support memory ↔ resume-edit synchronisation:

  - linked_field_paths (TEXT, JSON list[str]): which resume bullets this
    memory row was extracted FROM (e.g. ["internships.0.bullets.2"]).
    Empty list = orphaned / general memory not tied to a specific bullet.
  - needs_resync (BOOLEAN, default 0): set TRUE when the linked bullet text
    is modified after this memory was captured. UI shows a 🔄 badge and
    routes the student to plan-mode to re-confirm what changed.

Idempotent — both columns are no-ops if already present (lifespan also runs
`Base.metadata.create_all` which creates columns from the SQLAlchemy model).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c8d4e6f2b9'
down_revision: Union[str, Sequence[str], None] = 'b3f1c8d5a2e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'account_memory'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        # Table doesn't exist yet — earlier migration must run first. Skip;
        # the table-creation migration will include these columns via the
        # model definition.
        return

    existing_cols = {col['name'] for col in inspector.get_columns(TABLE_NAME)}

    if 'linked_field_paths' not in existing_cols:
        op.add_column(
            TABLE_NAME,
            sa.Column('linked_field_paths', sa.Text, nullable=False, server_default='[]'),
        )

    if 'needs_resync' not in existing_cols:
        op.add_column(
            TABLE_NAME,
            sa.Column('needs_resync', sa.Boolean, nullable=False, server_default=sa.text('0')),
        )


def downgrade() -> None:
    # SQLite ALTER TABLE DROP COLUMN requires copy+rebuild; leave as-is
    # — these columns have safe defaults and don't break older code reading
    # them as unknown.
    pass
