"""phase_g_knowledge_tables

Phase G (T0): 新建 taxonomy_xhs_posts + knowledge_subcategories 两张表。

Revision ID: caa730d630f2
Revises: ca243dc0b213
Create Date: 2026-05-27 21:32:02.589137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'caa730d630f2'
down_revision: Union[str, Sequence[str], None] = 'ca243dc0b213'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if "taxonomy_xhs_posts" not in existing_tables:
        op.create_table(
            'taxonomy_xhs_posts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('sub_cat', sa.Text(), nullable=False),
            sa.Column('source_url', sa.Text(), nullable=False),
            sa.Column('company_mentions', sa.Text(), nullable=True),
            sa.Column('verbatim_signals', sa.Text(), nullable=True),
            sa.Column('raw_content', sa.Text(), nullable=False),
            sa.Column('extracted_fields', sa.Text(), nullable=True),
            sa.Column('relevance_score', sa.Float(), nullable=True),
            sa.Column('scraped_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('source_url'),
        )
        op.create_index('ix_taxonomy_xhs_posts_sub_cat', 'taxonomy_xhs_posts', ['sub_cat'], unique=False)

    if "knowledge_subcategories" not in existing_tables:
        op.create_table(
            'knowledge_subcategories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('sub_cat', sa.Text(), nullable=False),
            sa.Column('sub_cat_slug', sa.Text(), nullable=False),
            sa.Column('strategy_type', sa.Text(), nullable=False),
            sa.Column('payload_json', sa.Text(), nullable=False),
            sa.Column('data_confidence', sa.Text(), nullable=False),
            sa.Column('data_basis_json', sa.Text(), nullable=False),
            sa.Column('hiring_season_json', sa.Text(), nullable=True),
            sa.Column('embedding', sa.LargeBinary(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('sub_cat'),
            sa.UniqueConstraint('sub_cat_slug'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if "knowledge_subcategories" in existing_tables:
        op.drop_table('knowledge_subcategories')
    if "taxonomy_xhs_posts" in existing_tables:
        op.drop_index('ix_taxonomy_xhs_posts_sub_cat', table_name='taxonomy_xhs_posts')
        op.drop_table('taxonomy_xhs_posts')
