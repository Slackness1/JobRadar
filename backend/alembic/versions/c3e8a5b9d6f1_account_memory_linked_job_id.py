"""account_memory: linked_job_id (Plan ② Job plan-mode, 2026-05-21)

Revision ID: c3e8a5b9d6f1
Revises: b2d9e5f7a3c4
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e8a5b9d6f1'
down_revision: Union[str, Sequence[str], None] = 'b2d9e5f7a3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = 'account_memory'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return
    existing_cols = {col['name'] for col in inspector.get_columns(TABLE_NAME)}
    if 'linked_job_id' not in existing_cols:
        op.add_column(
            TABLE_NAME,
            sa.Column('linked_job_id', sa.Text, nullable=False, server_default=''),
        )


def downgrade() -> None:
    pass
