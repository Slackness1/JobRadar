"""record per-turn analysis parts that failed to persist

Score, reference answer and voice metrics are written in parallel onto the same
interview_turns row. A lost write used to disappear into a WARNING log, leaving
the student with a silently empty analysis. This column records which part was
lost so the report can say so out loud.

Revision ID: c1f7a2d93b64
Revises: 9d4a6c2e7b10
Create Date: 2026-08-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1f7a2d93b64"
down_revision: Union[str, Sequence[str], None] = "9d4a6c2e7b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "interview_turns" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("interview_turns")}
    if "analysis_failures" not in columns:
        op.add_column(
            "interview_turns",
            sa.Column("analysis_failures", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "interview_turns" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("interview_turns")}
    if "analysis_failures" in columns:
        op.drop_column("interview_turns", "analysis_failures")
