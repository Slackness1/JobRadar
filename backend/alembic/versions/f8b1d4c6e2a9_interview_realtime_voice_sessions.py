"""add realtime interview sessions, events and heard-text audit fields

Revision ID: f8b1d4c6e2a9
Revises: a7c3e9b1f048
Create Date: 2026-08-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8b1d4c6e2a9"
down_revision: Union[str, Sequence[str], None] = "a7c3e9b1f048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # JobRadar's startup compatibility patch runs before Alembic. Keep this
    # migration idempotent so existing SQLite installs can be stamped safely.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "interview_turns" not in existing_tables:
        op.create_table(
            "interview_turns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Text(), nullable=False),
            sa.Column("user_key", sa.Text(), nullable=True),
            sa.Column("turn_index", sa.Integer(), nullable=False),
            sa.Column("target_job", sa.Text(), nullable=True),
            sa.Column("question", sa.Text(), nullable=True),
            sa.Column("user_answer", sa.Text(), nullable=True),
            sa.Column("asr_transcript", sa.Text(), nullable=True),
            sa.Column("voice_metrics", sa.Text(), nullable=True),
            sa.Column("score_json", sa.Text(), nullable=True),
            sa.Column("reference_answer", sa.Text(), nullable=True),
            sa.Column("question_source", sa.Text(), nullable=True),
            sa.Column("parent_turn_index", sa.Integer(), nullable=True),
            sa.Column("question_heard_text", sa.Text(), nullable=True),
            sa.Column("question_interrupted", sa.Boolean(), nullable=True),
            sa.Column("realtime_transport", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        existing_tables.add("interview_turns")
        inspector = sa.inspect(bind)
    turn_columns = {column["name"] for column in inspector.get_columns("interview_turns")}
    if "question_heard_text" not in turn_columns:
        op.add_column(
            "interview_turns", sa.Column("question_heard_text", sa.Text(), nullable=True)
        )
    if "question_interrupted" not in turn_columns:
        op.add_column(
            "interview_turns",
            sa.Column("question_interrupted", sa.Boolean(), nullable=True, server_default="0"),
        )
    if "realtime_transport" not in turn_columns:
        op.add_column(
            "interview_turns", sa.Column("realtime_transport", sa.Text(), nullable=True)
        )

    if "interview_realtime_sessions" not in existing_tables:
        op.create_table(
            "interview_realtime_sessions",
            sa.Column("context_id", sa.Text(), primary_key=True),
            sa.Column("session_id", sa.Text(), nullable=False),
            sa.Column("room_name", sa.Text(), nullable=False, unique=True),
            sa.Column("participant_identity", sa.Text(), nullable=False),
            sa.Column("user_key", sa.Text(), nullable=False),
            sa.Column("target_job", sa.Text(), nullable=False),
            sa.Column("jd_content", sa.Text(), nullable=True),
            sa.Column("turn_mode", sa.Text(), nullable=False, server_default="manual"),
            sa.Column("interruption_mode", sa.Text(), nullable=False, server_default="vad"),
            sa.Column("status", sa.Text(), nullable=False, server_default="issued"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("connected_at", sa.DateTime(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
        )
    if "interview_realtime_events" not in existing_tables:
        op.create_table(
            "interview_realtime_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "context_id",
                sa.Text(),
                sa.ForeignKey(
                    "interview_realtime_sessions.context_id", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column("session_id", sa.Text(), nullable=False),
            sa.Column("event_type", sa.Text(), nullable=False),
            sa.Column("turn_index", sa.Integer(), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    inspector = sa.inspect(bind)
    index_specs = {
        "interview_turns": {
            "session_id": False,
            "user_key": False,
        },
        "interview_realtime_sessions": {
            "session_id": False,
            "room_name": True,
            "user_key": False,
            "status": False,
            "expires_at": False,
        },
        "interview_realtime_events": {
            "context_id": False,
            "session_id": False,
            "event_type": False,
            "created_at": False,
        },
    }
    for table, columns in index_specs.items():
        existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
        for column, unique in columns.items():
            index_name = f"ix_{table}_{column}"
            if index_name not in existing_indexes:
                op.create_index(index_name, table, [column], unique=unique)


def downgrade() -> None:
    op.drop_table("interview_realtime_events")
    op.drop_table("interview_realtime_sessions")
    op.drop_column("interview_turns", "realtime_transport")
    op.drop_column("interview_turns", "question_interrupted")
    op.drop_column("interview_turns", "question_heard_text")
