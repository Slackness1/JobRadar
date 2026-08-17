"""stamp realtime voice events with their emit time

voice-facts-v2 latencies are differences between event timestamps. created_at is
the DB insert time, which absorbs the agent's async queueing and the writer
thread hand-off, so every latency computed from it is inflated by our own
backlog. occurred_at is stamped inside the LiveKit callback instead.

Revision ID: d5e8b31a07c2
Revises: c1f7a2d93b64
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e8b31a07c2"
down_revision: Union[str, Sequence[str], None] = "c1f7a2d93b64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "interview_realtime_events"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns(_TABLE)}
    if "occurred_at" not in columns:
        op.add_column(_TABLE, sa.Column("occurred_at", sa.DateTime(), nullable=True))
        op.create_index(f"ix_{_TABLE}_occurred_at", _TABLE, ["occurred_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns(_TABLE)}
    if "occurred_at" in columns:
        indexes = {index["name"] for index in inspector.get_indexes(_TABLE)}
        if f"ix_{_TABLE}_occurred_at" in indexes:
            op.drop_index(f"ix_{_TABLE}_occurred_at", table_name=_TABLE)
        op.drop_column(_TABLE, "occurred_at")
