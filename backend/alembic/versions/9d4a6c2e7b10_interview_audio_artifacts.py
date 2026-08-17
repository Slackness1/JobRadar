"""add consented interview audio artifacts

Revision ID: 9d4a6c2e7b10
Revises: f8b1d4c6e2a9
Create Date: 2026-08-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d4a6c2e7b10"
down_revision: Union[str, Sequence[str], None] = "f8b1d4c6e2a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "interview_audio_artifacts" not in inspector.get_table_names():
        op.create_table(
            "interview_audio_artifacts",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("session_id", sa.Text(), nullable=False),
            sa.Column("turn_index", sa.Integer(), nullable=False),
            sa.Column("user_key", sa.Text(), nullable=False),
            sa.Column("consent_version", sa.Text(), nullable=False),
            sa.Column("consented_at", sa.DateTime(), nullable=False),
            sa.Column("content_type", sa.Text(), nullable=False, server_default="audio/wav"),
            sa.Column("storage_path", sa.Text(), nullable=False, server_default=""),
            sa.Column("sha256", sa.Text(), nullable=False, server_default=""),
            sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sample_rate", sa.Integer(), nullable=False, server_default="16000"),
            sa.Column("channels", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0"),
            sa.Column("status", sa.Text(), nullable=False, server_default="uploaded"),
            sa.Column("analyzer_version", sa.Text(), nullable=False, server_default=""),
            sa.Column("features_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("shadow_asr_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("quality_flags_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    inspector = sa.inspect(bind)
    existing = {
        index["name"] for index in inspector.get_indexes("interview_audio_artifacts")
    }
    for column in ("session_id", "turn_index", "user_key", "status", "expires_at"):
        name = f"ix_interview_audio_artifacts_{column}"
        if name not in existing:
            op.create_index(name, "interview_audio_artifacts", [column], unique=False)


def downgrade() -> None:
    op.drop_table("interview_audio_artifacts")
