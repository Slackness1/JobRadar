"""drop job_intel_snapshots — Phase 0 of main-workspace-redesign-2026-05-20 (D-4)

Revision ID: e7a9c4d2b5f8
Revises: d5e9a541fac0
Create Date: 2026-05-20 12:00:00.000000

Snapshot system is removed entirely per main-workspace-redesign-2026-05-20 §2 D-4:
recommendation flow collapses to two layers (rule_score + LLM rerank) and the
admin job_intel summary stops returning snapshots. The table and all dependent
code paths are deleted in the same commit.

Idempotent via inspector.get_table_names() — safe to re-run, and skips cleanly
if the table never existed (fresh test DBs).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7a9c4d2b5f8'
down_revision: Union[str, Sequence[str], None] = 'd5e9a541fac0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'job_intel_snapshots'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE_NAME in inspector.get_table_names():
        existing_indexes = {idx['name'] for idx in inspector.get_indexes(TABLE_NAME)}
        for idx_name in existing_indexes:
            # don't try to drop SQLite-internal/auto-created indexes
            if idx_name and not idx_name.startswith('sqlite_'):
                op.drop_index(idx_name, table_name=TABLE_NAME)
        op.drop_table(TABLE_NAME)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE_NAME not in inspector.get_table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('job_id', sa.Integer(), nullable=False),
            sa.Column('snapshot_type', sa.Text(), nullable=True),
            sa.Column('summary_text', sa.Text(), nullable=True),
            sa.Column('evidence_count', sa.Integer(), nullable=True),
            sa.Column('source_platforms_json', sa.Text(), nullable=True),
            sa.Column('confidence_score', sa.Float(), nullable=True),
            sa.Column('generated_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_job_intel_snapshots_job_id', TABLE_NAME, ['job_id'])
