"""working_query_json on resume_copilot_sessions

Revision ID: 4e08e67e71bb
Revises: b1f2a3c4d5e6
Create Date: 2026-06-04 02:20:38.048814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '4e08e67e71bb'
down_revision: Union[str, Sequence[str], None] = 'b1f2a3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    cols = [c["name"] for c in insp.get_columns("resume_copilot_sessions")]
    if "working_query_json" not in cols:
        op.add_column("resume_copilot_sessions", sa.Column("working_query_json", sa.Text(), nullable=True))


def downgrade() -> None:
    pass
