"""add editor_draft_json to resume_copilot_sessions (简历编辑器草稿跨设备持久化)

NOTE(链路): down_revision 指向 d8e9f0a1b2c3 —— 它是另一会话在途(本提交时未跟踪)的
offershow_salaries 迁移, 但已是 dev DB 当前单一 head。chain 在它之后是当下唯一不产生
multi-head(会让 lifespan `alembic upgrade head` 崩)的合法选择。合并到 main 时需确保
d8e9f0a1b2c3 已先行入仓。
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None

_TABLE = "resume_copilot_sessions"
_COL = "editor_draft_json"


def upgrade():
    insp = sa.inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns(_TABLE)}
    if _COL in cols:
        return
    op.add_column(_TABLE, sa.Column(_COL, sa.Text(), nullable=True))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns(_TABLE)}
    if _COL in cols:
        op.drop_column(_TABLE, _COL)
