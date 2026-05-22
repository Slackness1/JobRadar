"""add jobs.link_status + link_checked_at for L3 dead-link probe

Revision ID: a7c3e9b1f048
Revises: c54e79e50065
Create Date: 2026-05-22

L3 死链探活:每天 10:00 cron HEAD detail_url,把 404/410/5xx 的标 dead,
推荐 SQL 排除。NULL = 未探过(首次部署后由 prober 填),alive / dead / uncertain。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c3e9b1f048'
down_revision: Union[str, Sequence[str], None] = 'c54e79e50065'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('link_status', sa.Text(), nullable=True))
    op.add_column('jobs', sa.Column('link_checked_at', sa.DateTime(), nullable=True))
    op.create_index('ix_jobs_link_status', 'jobs', ['link_status'])


def downgrade() -> None:
    op.drop_index('ix_jobs_link_status', table_name='jobs')
    op.drop_column('jobs', 'link_checked_at')
    op.drop_column('jobs', 'link_status')
