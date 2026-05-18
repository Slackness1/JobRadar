"""invite_codes — 邀请码 gated 注册基础

Revision ID: b8e2c4f91a3d
Revises: a7b3e9c2f1d4
Create Date: 2026-05-16 14:00:00.000000

Idempotent on table + indexes (跟现有 migration 模式一致)。先建表,users 表等账号
系统设计敲定再加; `consumed_by_user_key` 用 TEXT 不上 FK 让两边解耦。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e2c4f91a3d'
down_revision: Union[str, Sequence[str], None] = 'a7b3e9c2f1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'invite_codes'
INDEXES = [
    ('ix_invite_codes_code', ['code']),
    ('ix_invite_codes_consumed_at', ['consumed_at']),
    ('ix_invite_codes_expires_at', ['expires_at']),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE_NAME not in inspector.get_table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.Text(), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),      # 用途备注 (给谁)
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('consumed_at', sa.DateTime(), nullable=True),
            sa.Column('consumed_by_user_key', sa.Text(), nullable=True),  # user_key, 不上 FK
            sa.Column('expires_at', sa.DateTime(), nullable=True),         # 可空 = 永不过期
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code', name='uq_invite_codes_code'),
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
