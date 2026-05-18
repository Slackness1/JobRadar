"""student_experiences — cross-session personal KB for resume-copilot

Revision ID: c3f87a1e9b42
Revises: 744a2a8b79fd
Create Date: 2026-05-13 04:10:00.000000

Idempotent on table + indexes. JobRadar's lifespan runs `Base.metadata.create_all`
before `alembic upgrade head`, so by the time this migration executes, the table
and its indexes may already exist (created from the SQLAlchemy model definition).
Skipping when present keeps `alembic upgrade head` re-runnable and lets fresh
in-memory test DBs (sites_router fixture etc.) come up cleanly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f87a1e9b42'
down_revision: Union[str, Sequence[str], None] = '744a2a8b79fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'student_experiences'
INDEXES = [
    ('ix_student_experiences_user_key', ['user_key']),
    ('ix_student_experiences_summary_hash', ['summary_hash']),
    ('ix_student_experiences_user_confirmed', ['user_confirmed']),
    ('ix_student_experiences_captured_at', ['captured_at']),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE_NAME not in inspector.get_table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_key', sa.Text(), nullable=False),
            sa.Column(
                'source_session_id',
                sa.Integer(),
                sa.ForeignKey('resume_copilot_sessions.id', ondelete='SET NULL'),
                nullable=True,
            ),
            sa.Column('name', sa.Text(), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('summary_hash', sa.Text(), nullable=True),
            sa.Column('category', sa.Text(), nullable=True),
            sa.Column('star_dimensions_json', sa.Text(), nullable=True),
            sa.Column('behavioral_hook', sa.Text(), nullable=True),
            sa.Column('quantified_json', sa.Text(), nullable=True),
            sa.Column('raw_excerpt', sa.Text(), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('user_confirmed', sa.Boolean(), nullable=True),
            sa.Column('has_temporal_anchor', sa.Boolean(), nullable=True),
            sa.Column('has_concrete_action', sa.Boolean(), nullable=True),
            sa.Column('has_outcome', sa.Boolean(), nullable=True),
            sa.Column('captured_at', sa.DateTime(), nullable=True),
            sa.Column('last_verified_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('use_count', sa.Integer(), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_key', 'summary_hash', name='uq_student_experience_user_summary'),
        )

    existing_indexes = {idx['name'] for idx in inspector.get_indexes(TABLE_NAME)}
    for idx_name, cols in INDEXES:
        if idx_name not in existing_indexes:
            op.create_index(idx_name, TABLE_NAME, cols, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME in inspector.get_table_names():
        existing_indexes = {idx['name'] for idx in inspector.get_indexes(TABLE_NAME)}
        for idx_name, _ in reversed(INDEXES):
            if idx_name in existing_indexes:
                op.drop_index(idx_name, table_name=TABLE_NAME)
        op.drop_table(TABLE_NAME)
