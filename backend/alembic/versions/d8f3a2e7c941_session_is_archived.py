"""resume_copilot_sessions — add is_archived flag for Sessions page

Revision ID: d8f3a2e7c941
Revises: a7c3e9b1f048
Create Date: 2026-05-26

P0a of resume-copilot-redesign-2026-05-26:

- ``is_archived`` (BOOLEAN, NOT NULL, default 0) — soft-archive flag so the
  Sessions page can split 使用中 / 归档 / 全部 filter tabs without DELETE'ing
  rows. Defaults to 0 (False); the value flips when (P0a+ work) wires the
  archive action in the SessionCard menu.

Idempotent via ``inspector.get_columns()`` — safe to re-run on a DB where the
column already exists (e.g. a fresh test DB built from current SQLAlchemy
models, or a DB that's been schema-patched by the legacy path).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8f3a2e7c941'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9b1f048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'resume_copilot_sessions'
INDEX_NAME = 'ix_resume_copilot_sessions_is_archived'


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {col['name'] for col in inspector.get_columns(table)}


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {idx['name'] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        # Table missing — first-boot create_all path will pick the column up
        # from the model definition; nothing for this migration to do.
        return

    existing_cols = _column_names(inspector, TABLE_NAME)
    if 'is_archived' not in existing_cols:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                'is_archived',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('0'),
            ),
        )

    existing_indexes = _index_names(inspector, TABLE_NAME)
    if INDEX_NAME not in existing_indexes:
        op.create_index(INDEX_NAME, TABLE_NAME, ['is_archived'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = _index_names(inspector, TABLE_NAME)
    if INDEX_NAME in existing_indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    existing_cols = _column_names(inspector, TABLE_NAME)
    if 'is_archived' in existing_cols:
        op.drop_column(TABLE_NAME, 'is_archived')
