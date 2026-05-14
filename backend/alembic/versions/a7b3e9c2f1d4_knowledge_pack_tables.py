"""knowledge_pack — 9 tables for public-智库 layer (Tencent recruit pack et al.)

Revision ID: a7b3e9c2f1d4
Revises: f4d2c91a8e3b
Create Date: 2026-05-15 12:00:00.000000

Idempotent on table + indexes (same pattern as f4d2c91a8e3b). Lifespan runs
`Base.metadata.create_all` before `alembic upgrade head`, so tables may already
exist by the time this migration executes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b3e9c2f1d4'
down_revision: Union[str, Sequence[str], None] = 'f4d2c91a8e3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table_name, columns, indexes, unique_constraints)
TABLES = [
    (
        'knowledge_employers',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employer_key', sa.Text(), nullable=False),
            sa.Column('display_name', sa.Text(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('employer_key', name='uq_knowledge_employers_key'),
        ],
        [('ix_knowledge_employers_employer_key', ['employer_key'])],
    ),
    (
        'knowledge_tracks',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employer_key', sa.Text(), nullable=False),
            sa.Column('track_key', sa.Text(), nullable=False),
            sa.Column('display_name', sa.Text(), nullable=True),
            sa.Column('aliases_json', sa.Text(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('employer_key', 'track_key', name='uq_knowledge_track'),
        ],
        [
            ('ix_knowledge_tracks_employer_key', ['employer_key']),
            ('ix_knowledge_tracks_track_key', ['track_key']),
        ],
    ),
    (
        'knowledge_files',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employer_key', sa.Text(), nullable=False),
            sa.Column('file_path', sa.Text(), nullable=False),
            sa.Column('content_md', sa.Text(), nullable=True),
            sa.Column('content_hash', sa.Text(), nullable=True),
            sa.Column('version', sa.Integer(), nullable=True),
            sa.Column('ingested_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('employer_key', 'file_path', name='uq_knowledge_file_path'),
        ],
        [
            ('ix_knowledge_files_employer_key', ['employer_key']),
            ('ix_knowledge_files_content_hash', ['content_hash']),
        ],
    ),
    (
        'track_resume_rubrics',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employer_key', sa.Text(), nullable=False),
            sa.Column('track_key', sa.Text(), nullable=False),
            sa.Column('dimension', sa.Text(), nullable=True),
            sa.Column('high_signal', sa.Text(), nullable=True),
            sa.Column('low_signal', sa.Text(), nullable=True),
            sa.Column('examples_json', sa.Text(), nullable=True),
            sa.Column('source_file', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        ],
        [
            ('ix_track_resume_rubrics_employer_key', ['employer_key']),
            ('ix_track_resume_rubrics_track_key', ['track_key']),
        ],
    ),
    (
        'track_interview_rubrics',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employer_key', sa.Text(), nullable=False),
            sa.Column('track_key', sa.Text(), nullable=False),
            sa.Column('interview_stage', sa.Text(), nullable=True),
            sa.Column('scoring_dimensions_json', sa.Text(), nullable=True),
            sa.Column('rubric_md', sa.Text(), nullable=True),
            sa.Column('source_file', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        ],
        [
            ('ix_track_interview_rubrics_employer_key', ['employer_key']),
            ('ix_track_interview_rubrics_track_key', ['track_key']),
            ('ix_track_interview_rubrics_interview_stage', ['interview_stage']),
        ],
    ),
    (
        'interviewer_quotes',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employer_key', sa.Text(), nullable=False),
            sa.Column('track_key', sa.Text(), nullable=True),
            sa.Column('interview_stage', sa.Text(), nullable=True),
            sa.Column('quote_verbatim', sa.Text(), nullable=False),
            sa.Column('attribution', sa.Text(), nullable=True),
            sa.Column('context_topic', sa.Text(), nullable=True),
            sa.Column('source_file', sa.Text(), nullable=True),
            sa.Column('source_excerpt', sa.Text(), nullable=True),
            sa.Column('quote_hash', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('employer_key', 'quote_hash', name='uq_interviewer_quote_hash'),
        ],
        [
            ('ix_interviewer_quotes_employer_key', ['employer_key']),
            ('ix_interviewer_quotes_track_key', ['track_key']),
            ('ix_interviewer_quotes_interview_stage', ['interview_stage']),
            ('ix_interviewer_quotes_quote_hash', ['quote_hash']),
        ],
    ),
    (
        'track_example_bank',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employer_key', sa.Text(), nullable=False),
            sa.Column('track_key', sa.Text(), nullable=True),
            sa.Column('example_type', sa.Text(), nullable=True),
            sa.Column('title', sa.Text(), nullable=True),
            sa.Column('content_md', sa.Text(), nullable=True),
            sa.Column('rubric_score_json', sa.Text(), nullable=True),
            sa.Column('commentary', sa.Text(), nullable=True),
            sa.Column('source_file', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        ],
        [
            ('ix_track_example_bank_employer_key', ['employer_key']),
            ('ix_track_example_bank_track_key', ['track_key']),
            ('ix_track_example_bank_example_type', ['example_type']),
        ],
    ),
    (
        'output_constraints',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('scope', sa.Text(), nullable=True),
            sa.Column('employer_key', sa.Text(), nullable=True),
            sa.Column('track_key', sa.Text(), nullable=True),
            sa.Column('rule', sa.Text(), nullable=False),
            sa.Column('explanation', sa.Text(), nullable=True),
            sa.Column('softening_phrases_json', sa.Text(), nullable=True),
            sa.Column('forbidden_phrases_json', sa.Text(), nullable=True),
            sa.Column('priority', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        ],
        [
            ('ix_output_constraints_scope', ['scope']),
            ('ix_output_constraints_employer_key', ['employer_key']),
            ('ix_output_constraints_track_key', ['track_key']),
            ('ix_output_constraints_priority', ['priority']),
        ],
    ),
    (
        'sensitive_topics',
        [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employer_key', sa.Text(), nullable=False),
            sa.Column('topic_key', sa.Text(), nullable=False),
            sa.Column('display_name', sa.Text(), nullable=True),
            sa.Column('typical_phrasings_json', sa.Text(), nullable=True),
            sa.Column('response_template', sa.Text(), nullable=True),
            sa.Column('can_say_json', sa.Text(), nullable=True),
            sa.Column('cannot_say_json', sa.Text(), nullable=True),
            sa.Column('severity', sa.Text(), nullable=True),
            sa.Column('source_file', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('employer_key', 'topic_key', name='uq_sensitive_topic'),
        ],
        [
            ('ix_sensitive_topics_employer_key', ['employer_key']),
            ('ix_sensitive_topics_topic_key', ['topic_key']),
            ('ix_sensitive_topics_severity', ['severity']),
        ],
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table_name, columns, indexes in TABLES:
        if table_name not in existing_tables:
            op.create_table(table_name, *columns)
        existing_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}
        for idx_name, cols in indexes:
            if idx_name not in existing_indexes:
                op.create_index(idx_name, table_name, cols, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name, _, indexes in reversed(TABLES):
        if table_name in inspector.get_table_names():
            existing_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}
            for idx_name, _cols in reversed(indexes):
                if idx_name in existing_indexes:
                    op.drop_index(idx_name, table_name=table_name)
            op.drop_table(table_name)
