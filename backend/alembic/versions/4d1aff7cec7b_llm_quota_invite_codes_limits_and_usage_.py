"""llm_quota — 邀请码 token 配额 + 用量日志

Revision ID: 4d1aff7cec7b
Revises: 0006_xhs_notes_insights
Create Date: 2026-05-19 22:39:45.045990

invite_codes:
  - token_limit_total: 总配额 (NULL = 不限,默认给 SAIF-OB9TAP 已用码)
  - token_limit_daily: 每日上限 (NULL = 不限)

llm_usage:
  - 一行 = 一次 LLM 调用,记 user_key / feature / prompt+completion tokens / 当日日期
  - usage_date 单独存一列,方便每日聚合 (索引 user_key + usage_date)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4d1aff7cec7b'
# Prod head 是 d5e9a541fac0 (merge of taxonomy/recommendations/stale)。0006_xhs_notes_insights
# 是 dev 上未提交的并行 in-progress 工作,链不到 prod。锚到 d5e9a541fac0 让 prod 能跑;
# dev 这边 0006 自己再做个 merge 跟我合一下就行。
down_revision: Union[str, Sequence[str], None] = 'd5e9a541fac0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. invite_codes 加配额列
    existing_cols = {col['name'] for col in inspector.get_columns('invite_codes')}
    if 'token_limit_total' not in existing_cols:
        op.add_column('invite_codes', sa.Column('token_limit_total', sa.Integer(), nullable=True))
    if 'token_limit_daily' not in existing_cols:
        op.add_column('invite_codes', sa.Column('token_limit_daily', sa.Integer(), nullable=True))

    # 2. llm_usage 表
    if 'llm_usage' not in inspector.get_table_names():
        op.create_table(
            'llm_usage',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_key', sa.Text(), nullable=False),
            sa.Column('feature', sa.Text(), nullable=False),   # parse / recommend / chat / interview / etc.
            sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('usage_date', sa.Text(), nullable=False),  # 'YYYY-MM-DD' Asia/Shanghai
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_llm_usage_user_date', 'llm_usage', ['user_key', 'usage_date'])
        op.create_index('ix_llm_usage_user_key', 'llm_usage', ['user_key'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'llm_usage' in inspector.get_table_names():
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('llm_usage')}
        for idx_name in ('ix_llm_usage_user_key', 'ix_llm_usage_user_date'):
            if idx_name in existing_indexes:
                op.drop_index(idx_name, table_name='llm_usage')
        op.drop_table('llm_usage')

    existing_cols = {col['name'] for col in inspector.get_columns('invite_codes')}
    if 'token_limit_daily' in existing_cols:
        op.drop_column('invite_codes', 'token_limit_daily')
    if 'token_limit_total' in existing_cols:
        op.drop_column('invite_codes', 'token_limit_total')
