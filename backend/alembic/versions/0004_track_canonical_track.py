"""add canonical_track to tracks

Revision ID: 0004_track_canonical_track
Revises: c9e3a7d125b8
Create Date: 2026-05-16 23:00:00.000000

Phase F (2026-05-16): 给 Track 表加 canonical_track 字段,值取自
app.services.taxonomy.CANONICAL_FINANCE_TRACKS 中的 8 个 canonical key
(或 NULL — 表示该 tier-scoring 桶不归属任一 canonical)。

字段语义跟 coverage_truth.yaml 的 canonical_tracks 字段一致,但 Track 是
DB 行 + 单值(每个 tier 桶最适合的一个 canonical),coverage 是配置 +
列表(一个 crawler 桶可同时对应多个 canonical,如 hedge_funds = 量化 +
二级买方·基本面)。

Backfill 9 个已有行的映射在 migration 内联,基于 2026-05-16 现网 key
list (internet_tier1/2/3, bank_tier1/2/3, other_fintech, other_state,
other_foreign)。other_foreign 留 NULL — 跨业态太杂不归 canonical 任一项。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_track_canonical_track'
down_revision: Union[str, Sequence[str], None] = 'c9e3a7d125b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BACKFILL = {
    'internet_tier1': '金融科技',
    'internet_tier2': '金融科技',
    'internet_tier3': '金融科技',
    'bank_tier1': '银行·总行核心',
    'bank_tier2': '银行·总行核心',
    'bank_tier3': '银行·总行核心',
    'other_fintech': '金融科技',
    'other_state': '监管·体制内',
    # other_foreign 故意留 NULL —— 外企桶混了消费/科技/IB/咨询,无单一归属
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'tracks' not in inspector.get_table_names():
        return
    existing_cols = {c['name'] for c in inspector.get_columns('tracks')}
    if 'canonical_track' not in existing_cols:
        op.add_column('tracks', sa.Column('canonical_track', sa.Text(), nullable=True))

    for key, canon in _BACKFILL.items():
        bind.execute(
            sa.text("UPDATE tracks SET canonical_track = :c WHERE key = :k AND canonical_track IS NULL"),
            {"c": canon, "k": key},
        )


def downgrade() -> None:
    op.drop_column('tracks', 'canonical_track')
