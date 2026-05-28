"""T12 — Multi-pass C sub_cat enrich on ground truth pool (5-8k jobs).

候选筛选 (3 个 AND):
  1. quality_label IN ('good', 'internship_only') — T10 backfill 后才有意义
  2. company IN ground_truth_companies_v1.json 的 119 家公司 (含 alias)
  3. scraped_at > now - 30d AND link_status alive 或 NULL

幂等: sub_cat_enriched_at < now - 7d 或 NULL 才跑;off-target 也写 enriched_at 避免重跑。
并发: 8 线程 (Pass 1+2 = 2 LLM 调用/job, 7-8k jobs × 2 ≈ 14-16k 调用, 8 线程 ~1-2h)。
成本: ~$8-12 (Pro reasoning_effort=high + prefix cache)。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/12_enrich_sub_cat.py \
    [--days 30] [--workers 8] [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.sub_cat_enricher import enrich_job_sub_cat

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
GROUND_TRUTH = BACKEND_ROOT / "data" / "ground_truth_companies_v1.json"
PROGRESS_FILE = BACKEND_ROOT / "data" / "_phase_g" / "sub_cat_enrich_progress.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sub_cat_enrich")


def _build_ground_truth_company_set() -> set[str]:
    """ground_truth 119 家公司名 (含 alias) → 用于 jobs.company IN() 过滤。

    注: company 字段是 raw 名 (e.g. "中信证券股份有限公司"), ground_truth 是 "中信证券"。
    简化用 raw substring 匹配, 跟 T7 audit 同 alias 表 (避免重复维护, 引入)。
    """
    gt = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for cs in gt["ground_truth"].values():
        for c in cs:
            names.add(c["name"])
    return names


def _matching_job_ids(
    gt_names: set[str], days: int, limit: int | None,
) -> list[int]:
    """从 jobs 表拿满足"qualified + ground_truth 公司 + 近 N 天 + 未 enrich"的 job id。

    用 substring matching 找 jobs.company 含 ground_truth 名的, 跟 T7 同思路 (loose
    sub-string match, 接受少量 false positive 优于 false negative — enricher 自己
    Pass 1 还会 reject off-target).
    """
    from sqlalchemy import or_
    db = SessionLocal()
    try:
        skip_cutoff = datetime.utcnow() - timedelta(days=7)
        scrape_cutoff = datetime.utcnow() - timedelta(days=days)
        # OR-list company LIKE for each ground truth name (substring 匹配)
        company_filters = [Job.company.like(f"%{n}%") for n in gt_names]
        q = (
            db.query(Job.id)
            .filter(
                Job.scraped_at > scrape_cutoff,
                (Job.link_status == "alive") | (Job.link_status.is_(None)),
                Job.quality_label.in_(["good", "internship_only"]),
                or_(*company_filters),
                (Job.sub_cat_enriched_at.is_(None))
                | (Job.sub_cat_enriched_at < skip_cutoff),
            )
        )
        if limit:
            q = q.limit(limit)
        return [r[0] for r in q.all()]
    finally:
        db.close()


def _process_job(job_id: int) -> tuple[int, str | None, str | None]:
    """One job: enrich + write back. Each thread own SessionLocal.

    Returns (job_id, result_label, error_msg)。
      result_label = sub_category 名 / 'off_target' / None+err
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, "not_found")
        result = enrich_job_sub_cat(job)
        if result is None:
            # off-target: 仍写 enriched_at 避免下次重复跑
            job.sub_cat_enriched_at = datetime.utcnow()
            db.commit()
            return (job_id, "off_target", None)
        job.sub_category = result["sub_category"]
        job.sub_category_secondary = result.get("sub_category_secondary")
        job.industry_focus = result["industry_focus"]
        job.institution_tier = result["institution_tier"]
        job.sub_cat_confidence = result["sub_cat_confidence"]
        job.sub_cat_reasoning = result["sub_cat_reasoning"]
        job.sub_cat_enriched_at = datetime.utcnow()
        db.commit()
        return (job_id, result["sub_category"], None)
    except Exception as exc:  # noqa: BLE001
        return (job_id, None, str(exc)[:200])
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    gt_names = _build_ground_truth_company_set()
    log.info(f"ground_truth 公司: {len(gt_names)} 家")

    job_ids = _matching_job_ids(gt_names, args.days, args.limit)
    log.info(f"待 enrich jobs (good/internship_only + ground_truth + 近{args.days}d + 未 enriched): {len(job_ids)}")

    if args.dry_run:
        log.info("--dry-run 退出")
        return 0
    if not job_ids:
        log.info("无待跑帖, 退出")
        return 0

    sub_cat_counts: Counter[str] = Counter()
    off_target = 0
    errors: list[tuple[int, str]] = []
    consecutive_402 = 0

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_process_job, jid): jid for jid in job_ids}
        for i, fut in enumerate(as_completed(futures), 1):
            jid, label, err = fut.result()
            if err:
                errors.append((jid, err))
                if "402" in err or "Insufficient Balance" in err:
                    consecutive_402 += 1
                    if consecutive_402 >= 5:
                        log.error(f"连续 {consecutive_402} 个 402, 余额耗尽, 中止")
                        for f in futures:
                            f.cancel()
                        break
            else:
                consecutive_402 = 0
                if label == "off_target":
                    off_target += 1
                else:
                    sub_cat_counts[label] += 1
            if i % 100 == 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                eta = (len(job_ids) - i) / rate if rate else 0
                log.info(
                    f"  {i}/{len(job_ids)} | rate {rate:.1f}/s | eta {eta / 60:.1f}min | "
                    f"sub_cat top: {dict(sub_cat_counts.most_common(3))} | "
                    f"off-target {off_target} | errors {len(errors)}"
                )

    total_enriched = sum(sub_cat_counts.values())
    log.info(f"\n=== T12 enrich summary ===")
    log.info(f"  enriched (sub_cat 写入): {total_enriched}")
    log.info(f"  off-target (Pass1/2 拒): {off_target}")
    log.info(f"  errors: {len(errors)}")
    log.info(f"  耗时: {(time.time() - t0) / 60:.1f}min")
    log.info(f"  sub_cat 分布:")
    for sc, n in sub_cat_counts.most_common():
        log.info(f"    {sc}: {n}")
    if errors:
        log.info(f"  前 5 个 error:")
        for jid, msg in errors[:5]:
            log.info(f"    job_id={jid}: {msg}")

    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps({
            "ran_at": datetime.utcnow().isoformat(),
            "enriched": total_enriched,
            "off_target": off_target,
            "errors": len(errors),
            "sub_cat_counts": dict(sub_cat_counts),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return 0 if consecutive_402 < 5 else 2


if __name__ == "__main__":
    sys.exit(main())
