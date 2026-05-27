"""phase_g_sub_cat_columns

Phase G (T0): jobs 表加 7 列 sub_category 体系字段。

Revision ID: ca243dc0b213
Revises: 4f37b3f7b464
Create Date: 2026-05-27 21:31:29.770933

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'ca243dc0b213'
down_revision: Union[str, Sequence[str], None] = '4f37b3f7b464'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = [c["name"] for c in inspector.get_columns("jobs")]

    if "sub_category" not in existing_columns:
        op.add_column("jobs", sa.Column("sub_category", sa.Text(), nullable=True))
    if "sub_category_secondary" not in existing_columns:
        op.add_column("jobs", sa.Column("sub_category_secondary", sa.Text(), nullable=True))
    if "industry_focus" not in existing_columns:
        op.add_column("jobs", sa.Column("industry_focus", sa.Text(), nullable=True))
    if "institution_tier" not in existing_columns:
        op.add_column("jobs", sa.Column("institution_tier", sa.Text(), nullable=True))
    if "sub_cat_confidence" not in existing_columns:
        op.add_column("jobs", sa.Column("sub_cat_confidence", sa.Float(), nullable=True))
    if "sub_cat_reasoning" not in existing_columns:
        op.add_column("jobs", sa.Column("sub_cat_reasoning", sa.Text(), nullable=True))
    if "sub_cat_enriched_at" not in existing_columns:
        op.add_column("jobs", sa.Column("sub_cat_enriched_at", sa.DateTime(), nullable=True))

    # Indexes — only create if not present
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("jobs")}
    if "ix_jobs_sub_category" not in existing_indexes:
        op.create_index("ix_jobs_sub_category", "jobs", ["sub_category"], unique=False)
    if "ix_jobs_institution_tier" not in existing_indexes:
        op.create_index("ix_jobs_institution_tier", "jobs", ["institution_tier"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = [c["name"] for c in inspector.get_columns("jobs")]

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("jobs")}
    if "ix_jobs_institution_tier" in existing_indexes:
        op.drop_index("ix_jobs_institution_tier", table_name="jobs")
    if "ix_jobs_sub_category" in existing_indexes:
        op.drop_index("ix_jobs_sub_category", table_name="jobs")

    for col in ("sub_cat_enriched_at", "sub_cat_reasoning", "sub_cat_confidence",
                "institution_tier", "industry_focus", "sub_category_secondary", "sub_category"):
        if col in existing_columns:
            op.drop_column("jobs", col)
