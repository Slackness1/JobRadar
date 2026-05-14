"""add recommendations_stale flag to resume_copilot_sessions

Revision ID: 0004_recommendations_stale
Revises: 0003_session_plan_json
Create Date: 2026-05-14 10:00:00.000000

When Plan-mode finalizes a bullet and writes back into the confirmed profile,
this flag flips to 1 so the workspace can show "你写完了 N 条新 bullet, 重新推荐?".
Cleared back to 0 when the user re-runs POST /generate.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_recommendations_stale'
down_revision: Union[str, Sequence[str], None] = '0003_session_plan_json'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'resume_copilot_sessions',
        sa.Column('recommendations_stale', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('resume_copilot_sessions', 'recommendations_stale')
