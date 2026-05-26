"""xhs_taxonomy_extracts: taxonomy 字段独立表, 不污染 xhs_insights (KB 用)。

Revision ID: a26052601
Revises: f1a8e3c7b2d5
Create Date: 2026-05-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers
revision = "a26052601"
down_revision = "f1a8e3c7b2d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "xhs_taxonomy_extracts" in insp.get_table_names():
        return  # idempotent
    op.create_table(
        "xhs_taxonomy_extracts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.Text, nullable=False, index=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("post_time", sa.Text, nullable=True),
        sa.Column("author_uid", sa.Text, nullable=True, index=True),
        sa.Column("relevance_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("strategy_signals_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("industry_signals_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("institution_signals_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("discovered_sub_categories_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("company_role_pairs_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("dimension_distinctions_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("extraction_confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("strategy_bucket", sa.Text, nullable=True, index=True),  # 给 6 subagent 各自查
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
    )


def downgrade() -> None:
    op.drop_table("xhs_taxonomy_extracts")
