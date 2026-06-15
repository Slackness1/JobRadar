"""add resume_versions_json + editor_conversations_json to resume_copilot_sessions

简历编辑器「统一对话 Hub」改版用:
  - resume_versions_json: 简历版本存档(显式保存才记一版, 每版=简历快照+该版打分报告)
  - editor_conversations_json: 编辑器内深度优化对话(最多 3 个 tab, 各自独立消息)

链路说明: down_revision 指向生产/已入仓的当前 head s1emb20260615(merge point), 让本改版
能独立干净上生产(prod 单 head → 本迁移 → 单 head)。dev 库上另有 offshow 的未入仓 dev-only
head(1a6779f115d9), 与本链路并成双 head, 由 dev 本地直接 ALTER 列处理, 不影响 prod 单链。
两列都做幂等检查, 中断重跑安全。
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a4b5c6d7e8"
down_revision = "s1emb20260615"
branch_labels = None
depends_on = None

_TABLE = "resume_copilot_sessions"
_COLS = ("resume_versions_json", "editor_conversations_json")


def upgrade():
    insp = sa.inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns(_TABLE)}
    for col in _COLS:
        if col not in cols:
            op.add_column(_TABLE, sa.Column(col, sa.Text(), nullable=True))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns(_TABLE)}
    for col in _COLS:
        if col in cols:
            op.drop_column(_TABLE, col)
