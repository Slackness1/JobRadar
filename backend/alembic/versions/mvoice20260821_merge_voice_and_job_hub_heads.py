"""merge realtime voice and job hub migration heads

Revision ID: mvoice20260821
Revises: d5e8b31a07c2, jhub20260616
Create Date: 2026-08-21
"""

from collections.abc import Sequence


revision: str = "mvoice20260821"
down_revision: tuple[str, str] = ("d5e8b31a07c2", "jhub20260616")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
