"""add editor_draft_json to resume_copilot_sessions (简历编辑器草稿跨设备持久化)

NOTE(链路, 2026-06-12 改): 原 down_revision 指向另一会话在途未入仓的 offershow_salaries
迁移(d8e9f0a1b2c3),导致本 Hub 改版无法独立上生产(prod 没有那个迁移 → alembic 崩)。
已 re-parent 到生产已有的 c7d8e9f0a1b2(decision_events),让本链路不依赖 offshow,可独立
上线。代价:dev 库上 offshow 文件仍在,会与本链路并成双 head —— dev 用未入仓的本地 merge
迁移收口(zzz_local_merge_*),prod 无 offshow 故单链干净。offshow 那条线将来入仓时由其
会话补一个 merge 迁移把两头并回。
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "c7d8e9f0a1b2"
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
