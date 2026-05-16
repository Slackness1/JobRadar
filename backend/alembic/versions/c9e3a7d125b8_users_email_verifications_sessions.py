"""users + email_verifications + user_sessions — 账号系统第二批

Revision ID: c9e3a7d125b8
Revises: b8e2c4f91a3d
Create Date: 2026-05-16 14:20:00.000000

invite_codes 在上一个 migration 已经建过。这次建另外 3 张。idempotent。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9e3a7d125b8'
down_revision: Union[str, Sequence[str], None] = 'b8e2c4f91a3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = [
    (
        'users',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.Text(), nullable=False),
            sa.Column('password_hash', sa.Text(), nullable=False),
            sa.Column('invite_code_id', sa.Integer(), sa.ForeignKey('invite_codes.id'), nullable=True),
            sa.Column('email_verified_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_login_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email', name='uq_users_email'),
        ],
        [('ix_users_email', ['email'])],
    ),
    (
        'email_verifications',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('code', sa.Text(), nullable=False),
            sa.Column('purpose', sa.Text(), nullable=True),
            sa.Column('sent_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('attempts', sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        ],
        [
            ('ix_email_verifications_user_id', ['user_id']),
            ('ix_email_verifications_purpose', ['purpose']),
            ('ix_email_verifications_expires_at', ['expires_at']),
        ],
    ),
    (
        'user_sessions',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('token', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('ua', sa.Text(), nullable=True),
            sa.Column('ip', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token', name='uq_user_sessions_token'),
        ],
        [
            ('ix_user_sessions_user_id', ['user_id']),
            ('ix_user_sessions_token', ['token']),
            ('ix_user_sessions_expires_at', ['expires_at']),
        ],
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table_name, cols, idxs in TABLES:
        if table_name not in existing_tables:
            op.create_table(table_name, *cols)
            existing_tables.add(table_name)
        existing_idx = {ix['name'] for ix in inspector.get_indexes(table_name)}
        for idx_name, idx_cols in idxs:
            if idx_name not in existing_idx:
                op.create_index(idx_name, table_name, idx_cols, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name, _, idxs in reversed(TABLES):
        if table_name in inspector.get_table_names():
            existing_idx = {ix['name'] for ix in inspector.get_indexes(table_name)}
            for idx_name, _ in reversed(idxs):
                if idx_name in existing_idx:
                    op.drop_index(idx_name, table_name=table_name)
            op.drop_table(table_name)
