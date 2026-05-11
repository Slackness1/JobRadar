"""job_drafts table for teacher quick entry

Revision ID: 744a2a8b79fd
Revises: 0002_session_expires_at
Create Date: 2026-05-11 00:17:25.118723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '744a2a8b79fd'
down_revision: Union[str, Sequence[str], None] = '0002_session_expires_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'job_drafts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_user_key', sa.Text(), nullable=True),
        sa.Column('teacher_name', sa.Text(), nullable=True),
        sa.Column('teacher_dept', sa.Text(), nullable=True),
        sa.Column('source_type', sa.Text(), nullable=True),
        sa.Column('source_payload', sa.Text(), nullable=True),
        sa.Column('parse_confidence', sa.Float(), nullable=True),
        sa.Column('parsed_title', sa.Text(), nullable=True),
        sa.Column('parsed_company', sa.Text(), nullable=True),
        sa.Column('parsed_location', sa.Text(), nullable=True),
        sa.Column('parsed_jd_summary', sa.Text(), nullable=True),
        sa.Column('parsed_deadline', sa.Text(), nullable=True),
        sa.Column('parsed_salary', sa.Text(), nullable=True),
        sa.Column('parsed_detail_url', sa.Text(), nullable=True),
        sa.Column('track', sa.Text(), nullable=True),
        sa.Column('tags_json', sa.Text(), nullable=True),
        sa.Column('teacher_note', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('reject_reason', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_drafts_created_at'), 'job_drafts', ['created_at'], unique=False)
    op.create_index(op.f('ix_job_drafts_status'), 'job_drafts', ['status'], unique=False)
    op.create_index(op.f('ix_job_drafts_teacher_user_key'), 'job_drafts', ['teacher_user_key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_job_drafts_teacher_user_key'), table_name='job_drafts')
    op.drop_index(op.f('ix_job_drafts_status'), table_name='job_drafts')
    op.drop_index(op.f('ix_job_drafts_created_at'), table_name='job_drafts')
    op.drop_table('job_drafts')
