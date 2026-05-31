"""add source_score + source_platform to xhs_insights"""
from alembic import op
import sqlalchemy as sa

revision = "b1f2a3c4d5e6"
down_revision = "caa730d630f2"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("xhs_insights")}
    if "source_score" not in cols:
        op.add_column("xhs_insights", sa.Column("source_score", sa.Float(), nullable=True))
    if "source_platform" not in cols:
        op.add_column("xhs_insights", sa.Column("source_platform", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("xhs_insights", "source_platform")
    op.drop_column("xhs_insights", "source_score")
