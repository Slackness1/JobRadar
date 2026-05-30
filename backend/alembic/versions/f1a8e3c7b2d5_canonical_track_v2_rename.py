"""canonical_track v2: 10 → 13 canon 重命名 + 拆分 ambiguous 行设 NULL

Revision ID: f1a8e3c7b2d5
Revises: a7c3e9b1f048
Create Date: 2026-05-24

2026-05-23 重写 canonical taxonomy: 10 个老 canon → 13 个新 canon (拆 二级买方/卖方·S&T/一级市场,
咨询合并再拆)。详见 app/services/taxonomy/canonical.py 注释。

DB 层处理策略:
- in-place rename (unambiguous 1:1 映射):
  · '管理咨询·MBB' → '咨询·MBB+Tier2'
- 拆分位 (1:2 ambiguous,需要 jd / title 信号判定) → 全部设 NULL,等 backfill 脚本二次填:
  · '二级买方·基本面' → 公募/资管·投研 vs 私募·基本面
  · '卖方研究·S&T' → 卖方研究 vs S&T·FICC·衍生品
  · '一级市场' → 投行·并购·资本市场 vs 一级股权·PE/VC
  · '战略咨询' → 咨询·MBB+Tier2 vs 企业战略·管培·实业金融
- 不动 (canon 名未变,只是 alias 重新分流):
  · '量化' / '金融科技' / '大宗·能源' / '银行·总行核心' / '监管·体制内'

为了 backfill 脚本能拿到 old hint,加 jobs.canonical_track_pre_v2 字段,
**只**给被改的行存老值,downgrade 时还原。

Idempotent: 用 inspector 跳过已存在列;rename / NULL 的 WHERE 子句天然不重复触发。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text


revision: str = 'f1a8e3c7b2d5'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9b1f048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AMBIGUOUS_OLD_CANONS = (
    '二级买方·基本面',
    '卖方研究·S&T',
    '一级市场',
    '战略咨询',
)

_RENAME_OLD_CANONS = (
    '管理咨询·MBB',
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c['name'] for c in inspector.get_columns('jobs')}

    if 'canonical_track_pre_v2' not in cols:
        op.add_column(
            'jobs',
            sa.Column('canonical_track_pre_v2', sa.Text(), nullable=True),
        )

    # 1. 快照所有受影响行的 old canonical 到 pre_v2 列 (含 rename + NULL 两类)
    affected_old_values = list(_AMBIGUOUS_OLD_CANONS) + list(_RENAME_OLD_CANONS)
    placeholders = ', '.join(f':v{i}' for i in range(len(affected_old_values)))
    params = {f'v{i}': v for i, v in enumerate(affected_old_values)}
    conn.execute(
        text(
            f'UPDATE jobs SET canonical_track_pre_v2 = canonical_track '
            f'WHERE canonical_track IN ({placeholders}) '
            f'  AND (canonical_track_pre_v2 IS NULL '
            f'       OR canonical_track_pre_v2 <> canonical_track)'
        ),
        params,
    )

    # 2. in-place rename: 管理咨询·MBB → 咨询·MBB+Tier2
    conn.execute(
        text(
            "UPDATE jobs SET canonical_track = '咨询·MBB+Tier2' "
            "WHERE canonical_track = '管理咨询·MBB'"
        )
    )

    # 3. 拆分位 → NULL (let backfill script handle)
    null_placeholders = ', '.join(f':v{i}' for i in range(len(_AMBIGUOUS_OLD_CANONS)))
    null_params = {f'v{i}': v for i, v in enumerate(_AMBIGUOUS_OLD_CANONS)}
    conn.execute(
        text(
            f'UPDATE jobs SET canonical_track = NULL '
            f'WHERE canonical_track IN ({null_placeholders})'
        ),
        null_params,
    )


def downgrade() -> None:
    """从 pre_v2 列恢复 — 不区分 rename/null 来源, pre_v2 IS NOT NULL 全恢复."""
    conn = op.get_bind()
    conn.execute(
        text(
            'UPDATE jobs SET canonical_track = canonical_track_pre_v2 '
            'WHERE canonical_track_pre_v2 IS NOT NULL'
        )
    )
    op.drop_column('jobs', 'canonical_track_pre_v2')
