"""resume_copilot_sessions — rejected_job_ids_json + last_recommend_trigger_at

Revision ID: b3f1c8d5a2e9
Revises: e7a9c4d2b5f8
Create Date: 2026-05-20 14:00:00.000000

Phase 1 BE-3 of main-workspace-redesign-2026-05-20 (D-2 / D-3 / D-5):

- ``rejected_job_ids_json`` (TEXT, default '[]') — session-scoped list of
  job_ids the user has explicitly rejected via POST /recommendations/{id}/reject.
  Read by ``recommend_jobs_for_profile`` to filter the candidate pool before
  sort/threshold.
- ``last_recommend_trigger_at`` (DATETIME, nullable) — timestamp of the last
  recommend regeneration trigger. Read by ``should_debounce_recommend`` to
  collapse rapid back-to-back triggers (採纳 / ⭐ / 删 / plan-finalize / ✗) into a
  single rerun.

Idempotent via inspector.get_columns() — safe to re-run on a DB where the
columns already exist (e.g. a fresh test DB built from current SQLAlchemy
models).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3f1c8d5a2e9'
down_revision: Union[str, Sequence[str], None] = 'e7a9c4d2b5f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'resume_copilot_sessions'


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {col['name'] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = _column_names(inspector, TABLE_NAME)

    if TABLE_NAME not in inspector.get_table_names():
        # Table missing — let the SQLAlchemy create_all path own creation;
        # nothing for this migration to do.
        return

    if 'rejected_job_ids_json' not in existing:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                'rejected_job_ids_json',
                sa.Text(),
                nullable=True,
                server_default='[]',
            ),
        )

    if 'last_recommend_trigger_at' not in existing:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                'last_recommend_trigger_at',
                sa.DateTime(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = _column_names(inspector, TABLE_NAME)

    if 'last_recommend_trigger_at' in existing:
        op.drop_column(TABLE_NAME, 'last_recommend_trigger_at')
    if 'rejected_job_ids_json' in existing:
        op.drop_column(TABLE_NAME, 'rejected_job_ids_json')
