"""add decision_events telemetry table

统一决策事件埋点 (fallback / 护栏 / 分支触发的单一落点)。
lifespan 的 create_all 可能先建好这张表, 故 upgrade 做 inspector 幂等检查。

Revision ID: c7d8e9f0a1b2
Revises: 4e08e67e71bb
Create Date: 2026-06-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "4e08e67e71bb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "decision_events" in insp.get_table_names():
        return
    op.create_table(
        "decision_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("hit", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_decision_events_event_name", "decision_events", ["event_name"]
    )
    op.create_index(
        "ix_decision_events_created_at", "decision_events", ["created_at"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "decision_events" not in insp.get_table_names():
        return
    op.drop_index("ix_decision_events_created_at", table_name="decision_events")
    op.drop_index("ix_decision_events_event_name", table_name="decision_events")
    op.drop_table("decision_events")
