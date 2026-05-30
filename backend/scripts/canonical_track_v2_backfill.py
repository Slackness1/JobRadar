"""Rule-based v2 backfill: 拆 NULL 后的 4 个 ambiguous 池 → 6 个新 canon。

前置: alembic upgrade head (跑 f1a8e3c7b2d5_canonical_track_v2_rename)。
该 migration 会把这些 canonical_track 设 NULL 并把老值备份到 canonical_track_pre_v2:
  - '二级买方·基本面' → 公募/资管·投研 vs 私募·基本面
  - '卖方研究·S&T' → 卖方研究 vs S&T·FICC·衍生品
  - '一级市场' → 投行·并购·资本市场 vs 一级股权·PE/VC
  - '战略咨询' → 咨询·MBB+Tier2 vs 企业战略·管培·实业金融

本脚本走 rule-based heuristic (no LLM, 几秒跑完), 默认到大头 canon。覆盖 ~85%
后续可加 LLM 二次 pass 处理剩余疑难行 (本脚本不做)。

用法:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/canonical_track_v2_backfill.py --dry-run  # 看 transition 分布
  PYTHONPATH=. .venv/bin/python scripts/canonical_track_v2_backfill.py            # 实际 UPDATE
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Job  # noqa: E402


logger = logging.getLogger(__name__)


def _has(text: str, *keywords: str) -> bool:
    return any(kw in text for kw in keywords)


def _split_buy_side(company: str, title: str, jd: str) -> str:
    """二级买方·基本面 → 公募/资管·投研 vs 私募·基本面"""
    combo = (company + ' ' + title).lower()
    if _has(combo, '私募', '阳光私募', '对冲', 'hedge fund', '长短仓',
            'long-short', 'long/short'):
        return '私募·基本面'
    known_pe = (
        '高毅', '景林', '重阳', '淡水泉', '宁泉', '观砚', '佳期', '启林',
        '进化论', '知行通达', '拾贝', '翼虎',
    )
    if _has(company, *known_pe):
        return '私募·基本面'
    # Default → 公募/资管·投研 (SAIF placement 公募行研最大头)
    return '公募/资管·投研'


def _split_research_st(company: str, title: str, jd: str) -> str:
    """卖方研究·S&T → 卖方研究 vs S&T·FICC·衍生品"""
    combo = (company + ' ' + title).lower()
    if _has(
        combo,
        's&t', 'sales & trading', 'sales and trading', 'ficc',
        'global markets', 'gbm', '销售交易', '机构销售', '债券交易', '外汇交易',
        '衍生品', 'structuring', 'trader', '做市',
    ):
        return 'S&T·FICC·衍生品'
    # Default → 卖方研究 (research 端 SAIF 学生常见)
    return '卖方研究'


def _split_primary(company: str, title: str, jd: str) -> str:
    """一级市场 → 投行·并购·资本市场 vs 一级股权·PE/VC"""
    combo = (company + ' ' + title).lower()
    if _has(
        combo,
        ' pe ', ' vc ', 'pe/vc', 'pe fund', 'vc fund',
        'private equity', 'venture capital', 'buyout', 'growth equity',
        '股权投资', '私募股权', '风险投资', '产业基金', '战略投资',
        'pe投资', 'vc投资', 'pe分析师', 'vc分析师',
    ):
        return '一级股权·PE/VC'
    known_pe_vc = (
        '高瓴', '红杉', '鼎晖', '弘毅', '华平', '凯雷', 'kkr', 'tpg',
        '黑石', '淡马锡', '君联', 'idg', '经纬', '启明', '真格', '高榕',
    )
    if _has(company.lower(), *known_pe_vc):
        return '一级股权·PE/VC'
    # Default → 投行·并购·资本市场 (IBD 大头)
    return '投行·并购·资本市场'


def _split_strategy_consulting(company: str, title: str, jd: str) -> str:
    """战略咨询 → 咨询·MBB+Tier2 vs 企业战略·管培·实业金融"""
    company_l = company.lower()
    title_l = title.lower()
    consulting_firms = (
        '罗兰贝格', 'roland berger', 'oliver wyman', '科尔尼', 'kearney',
        'lek', 'l.e.k', '埃森哲战略', 'accenture strategy', 'ibm 咨询',
        'ibm consulting', '思略特', '德勤 monitor', 'monitor deloitte',
        'ey parthenon', 'ey-parthenon', 'kpmg strategy',
    )
    if _has(company_l, *consulting_firms):
        return '咨询·MBB+Tier2'
    if _has(title_l, '咨询顾问', 'consultant', '战略咨询', 'strategy consulting'):
        return '咨询·MBB+Tier2'
    enterprise_strategy = (
        '阿里', '美团', '字节', '腾讯', '京东', '拼多多', '小米', '华为',
        '快手', '中粮', '中海油', '中远海运', '招商局', '远景', '中国移动',
        '中国联通', '中国电信', '京东战投', '美团战投', '腾讯战略',
    )
    if _has(company_l, *enterprise_strategy):
        return '企业战略·管培·实业金融'
    if _has(title_l, '战略部', '战略组', '战略发展', '战略与投资', '战投',
            'corp dev', 'corporate development', '管培生'):
        return '企业战略·管培·实业金融'
    # Default → 咨询·MBB+Tier2 (老 战略咨询 含 strategy consulting 大头)
    return '咨询·MBB+Tier2'


_SPLITTERS = {
    '二级买方·基本面': _split_buy_side,
    '卖方研究·S&T': _split_research_st,
    '一级市场': _split_primary,
    '战略咨询': _split_strategy_consulting,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='print summary, no DB writes')
    ap.add_argument('--limit', type=int, default=0, help='only first N rows (smoke test)')
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(message)s')
    db = SessionLocal()
    try:
        q = (
            db.query(Job)
            .filter(Job.canonical_track.is_(None))
            .filter(Job.canonical_track_pre_v2.isnot(None))
        )
        if args.limit:
            q = q.limit(args.limit)
        rows = q.all()
        logger.info(
            'Loaded %d rows with NULL canonical_track + non-NULL pre_v2', len(rows)
        )

        transitions: Counter = Counter()
        unknown: Counter = Counter()
        updates: list[tuple[int, str]] = []

        for job in rows:
            old = job.canonical_track_pre_v2
            splitter = _SPLITTERS.get(old)
            if not splitter:
                unknown[old] += 1
                continue
            jd = (job.job_duty or '').lower() if hasattr(job, 'job_duty') else ''
            new = splitter(job.company or '', job.job_title or '', jd)
            transitions[(old, new)] += 1
            updates.append((job.id, new))

        logger.info('\n=== Transitions (pre_v2 → new) ===')
        for (old, new), count in sorted(transitions.items(), key=lambda x: -x[1]):
            logger.info('  %-22s → %-22s : %d', old, new, count)
        if unknown:
            logger.info('\n=== Unknown pre_v2 values (no splitter, skipped) ===')
            for old, count in unknown.most_common():
                logger.info('  %s : %d', old, count)

        if args.dry_run:
            logger.info('\n[dry-run] no DB writes')
            return 0

        # Apply in batches of 500 to avoid massive single transaction
        applied = 0
        for i in range(0, len(updates), 500):
            chunk = updates[i:i + 500]
            for job_id, new in chunk:
                db.query(Job).filter(Job.id == job_id).update(
                    {'canonical_track': new}, synchronize_session=False
                )
            db.commit()
            applied += len(chunk)
            logger.info('  applied %d / %d', applied, len(updates))
        logger.info('\n[applied] updated %d rows', len(updates))
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
