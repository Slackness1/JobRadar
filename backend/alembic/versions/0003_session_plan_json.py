"""add plan_json + plan_status to resume_copilot_sessions

Revision ID: 0003_session_plan_json
Revises: 744a2a8b79fd
Create Date: 2026-05-13 02:00:00.000000

Adds two columns supporting the Plan-mode workflow:
- ``plan_json``: TEXT, holds the full PlanState (see services/resume_copilot/plan.py)
- ``plan_status``: TEXT, indexed, top-level workflow phase
  (idle/drafting_plan/awaiting_plan_approval/clarifying/reviewing/done/paused)

Both default to NULL / 'idle' so existing rows continue to work in the legacy
one-shot recommendation flow without any data migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003_session_plan_json'
# chain off c3f87a1e9b42 (student_experiences) so the linear chain stays valid
# in prod where that migration was already stamped before plan-mode landed.
# c3f87a1e9b42 itself is idempotent (table exists check), so re-running it
# on fresh DBs is safe.
down_revision: Union[str, Sequence[str], None] = 'c3f87a1e9b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'resume_copilot_sessions',
        sa.Column('plan_json', sa.Text(), nullable=True),
    )
    op.add_column(
        'resume_copilot_sessions',
        sa.Column('plan_status', sa.Text(), nullable=False, server_default='idle'),
    )
    op.create_index(
        op.f('ix_resume_copilot_sessions_plan_status'),
        'resume_copilot_sessions',
        ['plan_status'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_resume_copilot_sessions_plan_status'),
        table_name='resume_copilot_sessions',
    )
    op.drop_column('resume_copilot_sessions', 'plan_status')
    op.drop_column('resume_copilot_sessions', 'plan_json')
