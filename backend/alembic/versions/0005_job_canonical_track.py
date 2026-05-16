"""add canonical_track to jobs + backfill from source + job_title

Revision ID: 0005_job_canonical_track
Revises: 0004_track_canonical_track
Create Date: 2026-05-16 23:30:00.000000

Phase B (2026-05-16): 给 99113 行 Job 加 canonical_track,通过 source 1:1 映射
+ job_title alias 推断的方式自动 backfill。

Backfill 策略:
1. 优先 job_title:canonicalize_track 命中(e.g. "量化研究员" → 量化)
2. 兜底 source 1:1 表(e.g. bank_official → 银行·总行核心)
3. 1:N 歧义 source 且 job_title 无信号 → 留 NULL,后续 LLM rerank 或 review_queue 处理

Backfill 跑在 migration 内,分批 commit(每 5000 行)避免单 transaction 撑爆 WAL。
新增 Job 行通过 models.py 的 before_insert/before_update event listener 自动派生。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005_job_canonical_track'
down_revision: Union[str, Sequence[str], None] = '0004_track_canonical_track'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill(bind) -> int:
    """Python-side batch backfill。返回 updated 行数。"""
    from app.services.taxonomy import canonicalize_job

    rows = bind.execute(sa.text(
        "SELECT id, source, job_title FROM jobs WHERE canonical_track IS NULL"
    )).fetchall()
    updated = 0
    batch: list[tuple] = []
    BATCH_SIZE = 5000
    for r in rows:
        canon = canonicalize_job(r.source or '', r.job_title or '')
        if not canon:
            continue
        batch.append((canon, r.id))
        if len(batch) >= BATCH_SIZE:
            bind.execute(
                sa.text("UPDATE jobs SET canonical_track = :c WHERE id = :i"),
                [{"c": c, "i": i} for c, i in batch],
            )
            updated += len(batch)
            batch.clear()
    if batch:
        bind.execute(
            sa.text("UPDATE jobs SET canonical_track = :c WHERE id = :i"),
            [{"c": c, "i": i} for c, i in batch],
        )
        updated += len(batch)
    return updated


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'jobs' not in inspector.get_table_names():
        return
    existing_cols = {c['name'] for c in inspector.get_columns('jobs')}
    existing_idx = {i['name'] for i in inspector.get_indexes('jobs')}

    if 'canonical_track' not in existing_cols:
        op.add_column('jobs', sa.Column('canonical_track', sa.Text(), nullable=True))
    if 'ix_jobs_canonical_track' not in existing_idx:
        op.create_index('ix_jobs_canonical_track', 'jobs', ['canonical_track'])

    updated = _backfill(bind)
    print(f"[phase-B] backfilled canonical_track for {updated} jobs")


def downgrade() -> None:
    op.drop_index('ix_jobs_canonical_track', table_name='jobs')
    op.drop_column('jobs', 'canonical_track')
