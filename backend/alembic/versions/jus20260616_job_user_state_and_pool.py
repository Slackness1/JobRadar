"""resume_job_user_state table + recommendation_runs.pool_json

Revision ID: jus20260616
Revises: cc0faccfa288
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "jus20260616"
down_revision: Union[str, Sequence[str], None] = "cc0faccfa288"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if "resume_job_user_state" not in insp.get_table_names():
        op.create_table(
            "resume_job_user_state",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_key", sa.Text(), nullable=False),
            sa.Column("job_id", sa.Text(), nullable=False),
            sa.Column("state", sa.Text(), nullable=False, server_default="seen"),
            sa.Column("first_seen_at", sa.DateTime(), nullable=True),
            sa.Column("state_updated_at", sa.DateTime(), nullable=True),
            sa.Column("source_session_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_key", "job_id", name="uq_job_user_state_user_job"),
        )
        op.create_index("ix_job_user_state_user_key", "resume_job_user_state", ["user_key"])
        op.create_index("ix_job_user_state_job_id", "resume_job_user_state", ["job_id"])
    cols = [c["name"] for c in insp.get_columns("resume_recommendation_runs")]
    if "pool_json" not in cols:
        op.add_column("resume_recommendation_runs", sa.Column("pool_json", sa.Text(), nullable=True))


def downgrade() -> None:
    pass
