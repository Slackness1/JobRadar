"""add hub_conversation_json to resume_copilot_sessions (Hub 对话按简历持久化)

一份简历 = 一段对话; 切回这份简历要能重放之前聊过的记录。confirmed-profile /
editor_draft 都装不下对话流, 单独存。down_revision 指向 e1f2a3b4c5d6(当前单一 head),
chain 线性追加, 不产生 multi-head(否则 lifespan `alembic upgrade head` 会崩)。
"""
from alembic import op
import sqlalchemy as sa

revision = "f0a1b2c3d4e5"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

_TABLE = "resume_copilot_sessions"
_COL = "hub_conversation_json"


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
