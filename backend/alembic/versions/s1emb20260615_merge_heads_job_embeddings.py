"""S1 上线:合并 3 个并列 alembic head + 建 job_embeddings 表

背景(2026-06-15):
  已入库迁移树因多会话并行出现 3 个并列 head:
    - a26052601       (xhs_taxonomy_extracts)
    - b1f2a3c4d5e6    (source_score 列)
    - g1b2c3d4e5f6    (hub_conversations) ← prod 当前停在这
  3 个 head 并列会让 `alembic upgrade head` 报 "multiple heads" 直接失败。
  本迁移把三者合并成单一 head,并顺带把 job_embeddings 纳入正式 Alembic 管理
  (此前由 dense_index.ensure_tables() 懒建)。

  **只合并已入库的 3 个 head;另一会话的 offshow 迁移(d8e9f0a1b2c3)不在本链**
  ——它未入库、且不属于 S1 v1,留给其负责会话单独并链。

幂等:
  - job_embeddings 用 inspector 判存在则跳过(dense_index 懒建过也安全)。
  - 合并本身不产生 DDL,只统一版本图。
  - a26052601 / b1f2a3c4d5e6 若 prod 尚未应用,upgrade head 会先跑它们;
    二者各自的 upgrade 需对 prod 现状幂等(部署前以 prod 库副本 dry-run 验证)。
"""

from alembic import op
import sqlalchemy as sa

revision = "s1emb20260615"
down_revision = ("a26052601", "b1f2a3c4d5e6", "g1b2c3d4e5f6")
branch_labels = None
depends_on = None

_TABLE = "job_embeddings"


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _TABLE in insp.get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("job_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("vector", sa.LargeBinary(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "embedded_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
    )


def downgrade():
    insp = sa.inspect(op.get_bind())
    if _TABLE in insp.get_table_names():
        op.drop_table(_TABLE)
