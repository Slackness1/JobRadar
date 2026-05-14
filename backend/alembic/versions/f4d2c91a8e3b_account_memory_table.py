"""account_memory — unified account-scoped memory layer

Revision ID: f4d2c91a8e3b
Revises: 0003_session_plan_json
Create Date: 2026-05-13 16:30:00.000000

Idempotent on table + indexes (same pattern as c3f87a1e9b42). JobRadar's
lifespan runs `Base.metadata.create_all` before `alembic upgrade head`, so by
the time this migration executes, the table and its indexes may already exist
(created from the SQLAlchemy model definition). Skipping when present keeps
`alembic upgrade head` re-runnable and lets fresh in-memory test DBs come up
cleanly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4d2c91a8e3b'
down_revision: Union[str, Sequence[str], None] = '0003_session_plan_json'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'account_memory'
INDEXES = [
    ('ix_account_memory_user_key', ['user_key']),
    ('ix_account_memory_category', ['category']),
    ('ix_account_memory_summary_hash', ['summary_hash']),
    ('ix_account_memory_user_confirmed', ['user_confirmed']),
    ('ix_account_memory_captured_at', ['captured_at']),
    ('ix_account_memory_is_archived', ['is_archived']),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE_NAME not in inspector.get_table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column('id', sa.Integer(), nullable=False),

            # identity + discriminator
            sa.Column('user_key', sa.Text(), nullable=False),
            sa.Column('category', sa.Text(), nullable=False),

            # content
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('payload_json', sa.Text(), nullable=True),
            sa.Column('summary_hash', sa.Text(), nullable=True),

            # provenance
            sa.Column('source_module', sa.Text(), nullable=True),
            sa.Column('source_session_id', sa.Integer(), nullable=True),
            sa.Column('source_message_id', sa.Integer(), nullable=True),
            sa.Column('raw_excerpt', sa.Text(), nullable=True),

            # confidence + user confirmation
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('user_confirmed', sa.Boolean(), nullable=True),

            # lifecycle
            sa.Column('captured_at', sa.DateTime(), nullable=True),
            sa.Column('last_verified_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('use_count', sa.Integer(), nullable=True),

            # evolution
            sa.Column('superseded_by_id', sa.Integer(), nullable=True),
            sa.Column('is_archived', sa.Boolean(), nullable=True),

            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'user_key', 'summary_hash',
                name='uq_account_memory_user_summary',
            ),
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
