"""add expires_at to resume_copilot_sessions

Revision ID: 0002_session_expires_at
Revises: 0001_baseline
Create Date: 2026-04-28 15:14:19.076058

NOTE: alembic --autogenerate also detected significant drift between
``models.py`` and the live SQLite schema (legacy tables/columns left over
from ``schema_patch.py`` runs and the pre-alembic era — ``job_posts``,
``resume_topic_cache``, ``resume_copilot_profiles``, ``resume_copilot_preferences``,
``resume_recommendation_items``, plus stale columns ``source_label`` /
``parse_status`` / ``resume_text`` / ``filename`` on ``resume_copilot_sessions``,
plus missing single-column indexes on ``user_key`` / ``status`` /
``is_guest`` / etc.). All of those drift items are intentionally
filtered out of this migration: they are out of scope for the
"add expires_at" change and reconciling them is tracked separately.
This migration ONLY adds the ``expires_at`` column and its index.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_session_expires_at'
down_revision: Union[str, Sequence[str], None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'resume_copilot_sessions',
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f('ix_resume_copilot_sessions_expires_at'),
        'resume_copilot_sessions',
        ['expires_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_resume_copilot_sessions_expires_at'),
        table_name='resume_copilot_sessions',
    )
    op.drop_column('resume_copilot_sessions', 'expires_at')
