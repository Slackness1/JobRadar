"""add hub_conversations table (Hub 多对话: 简历是 base, 一份简历下多个对话)

取代 resume_copilot_sessions.hub_conversation_json 单对话槽 —— 单槽下「新对话」
只能清空复用, 再聊就把这份简历之前的对话整段覆盖掉(实测毁过历史)。独立成表后
每个对话有自己的 id / 标题(首句) / 时间, 新对话=插新行, 旧对话原样保留。

数据搬运: 存量非空 hub_conversation_json 各搬成一行(标题取第一条学生发言,
去 HTML 标签截 24 字), 老列保留不再读写。down_revision 指向 f0a1b2c3d4e5
(当前单一 head), chain 线性追加。
"""
import json
import re

from alembic import op
import sqlalchemy as sa

revision = "g1b2c3d4e5f6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None

_TABLE = "hub_conversations"


def _title_from_messages(messages: list) -> str:
    """标题 = 第一条学生发言(去标签截 24 字); 没有学生发言退首条 turn, 再退默认。"""
    def _text(html: str) -> str:
        return re.sub(r"<[^>]+>", "", str(html or "")).strip()

    for m in messages:
        if isinstance(m, dict) and m.get("kind") == "turn" and m.get("who") == "me":
            t = _text(m.get("html", ""))
            if t:
                return t[:24]
    for m in messages:
        if isinstance(m, dict) and m.get("kind") == "turn":
            t = _text(m.get("html", ""))
            if t:
                return t[:24]
    return "对话"


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _TABLE not in insp.get_table_names():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "session_id",
                sa.Integer(),
                sa.ForeignKey("resume_copilot_sessions.id"),
                nullable=False,
            ),
            sa.Column("title", sa.Text(), server_default=""),
            sa.Column("messages_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_hub_conversations_session_id", _TABLE, ["session_id"]
        )
        op.create_index(
            "ix_hub_conversations_updated_at", _TABLE, ["updated_at"]
        )

    # 存量单槽对话 → 各搬一行(幂等: 已有任何行的 session 不重复搬)。
    sess_cols = {c["name"] for c in insp.get_columns("resume_copilot_sessions")}
    if "hub_conversation_json" not in sess_cols:
        return
    rows = bind.execute(
        sa.text(
            "SELECT id, hub_conversation_json, updated_at FROM resume_copilot_sessions "
            "WHERE hub_conversation_json IS NOT NULL AND hub_conversation_json != ''"
        )
    ).fetchall()
    for sid, raw, upd in rows:
        try:
            messages = json.loads(raw)
        except Exception:
            continue
        if not isinstance(messages, list) or not messages:
            continue
        existing = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {_TABLE} WHERE session_id = :sid"),
            {"sid": sid},
        ).scalar()
        if existing:
            continue
        bind.execute(
            sa.text(
                f"INSERT INTO {_TABLE} "
                "(session_id, title, messages_json, created_at, updated_at) "
                "VALUES (:sid, :title, :mj, :ts, :ts)"
            ),
            {
                "sid": sid,
                "title": _title_from_messages(messages),
                "mj": json.dumps(messages, ensure_ascii=False),
                "ts": upd,
            },
        )


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _TABLE in insp.get_table_names():
        op.drop_table(_TABLE)
