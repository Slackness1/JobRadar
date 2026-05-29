"""T12 v2 (方案 C 第一轮): 用新 Pass 2 prompt + 3 张新 KB 重 enrich 非 AI 候选池 (~543 帖)。

过滤策略:
- ground_truth 公司池 (119 家) — AI 5 sub_cat 关联的 20 家公司 = 非 AI 99 家
- AI 5 sub_cat = AI PM / LLM算法post-train / Agent工程师 / 多模态推理优化 / AI算法业务
- 字节/腾讯/阿里/美团/小红书/DeepSeek/蚂蚁/快手/商汤/华为 等大头公司排除

幂等控制: 强制重 enrich (覆盖现 sub_cat_enriched_at), 因为用了新 Pass 2 prompt + 新 KB。
预算: ~$2 / ~10 min (8 线程)。
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
PROGRESS_FILE = BACKEND_ROOT / "data" / "_phase_g" / "sub_cat_enrich_v2_nonai_progress.json"

AI_SUB_CATS = (
    "AI PM",
    "LLM算法post-train",
    "Agent工程师",
    "多模态推理优化",
    "AI算法业务",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("enrich_v2_nonai")


def _build_non_ai_company_set() -> set[str]:
    gt = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    all_names: set[str] = set()
    ai_names: set[str] = set()
    for sub_cat, lst in gt["ground_truth"].items():
        for c in lst:
            name = c.get("name", "")
            if not name:
                continue
            all_names.add(name)
            if sub_cat in AI_SUB_CATS:
                ai_names.add(name)
    non_ai = all_names - ai_names
    log.info(f"ground_truth 全公司: {len(all_names)} | AI 5 sub_cat 关联: {len(ai_names)} | 非 AI: {len(non_ai)}")
    return non_ai


def _matching_job_ids(non_ai_names: set[str], days: int) -> list[int]:
    from sqlalchemy import or_
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        # 公司 substring match (跟 T7 audit 同口径)
        company_filters = [Job.company.like(f"%{n}%") for n in non_ai_names]
        q = db.query(Job.id).filter(
            Job.scraped_at > cutoff,
            (Job.link_status == "alive") | (Job.link_status.is_(None)),
            Job.quality_label.in_(["good", "internship_only"]),
            or_(*company_filters),
        )
        return [r[0] for r in q.all()]
    finally:
        db.close()


def _process_job(job_id: int) -> tuple[int, str | None, str | None]:
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, "not_found")
        result = enrich_job_sub_cat(job)
        if result is None:
            job.sub_category = None
            job.sub_category_secondary = None
            job.industry_focus = None
            job.institution_tier = None
            job.sub_cat_confidence = None
            job.sub_cat_reasoning = "v2 nonai: Pass1/2 reject"
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

    non_ai = _build_non_ai_company_set()
    job_ids = _matching_job_ids(non_ai, args.days)
    if args.limit:
        job_ids = job_ids[: args.limit]
    log.info(f"非 AI 候选池 (强制重 enrich, 不管 sub_cat_enriched_at): {len(job_ids)}")
    if args.dry_run:
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
                        log.error(f"连续 {consecutive_402} 个 402, 中止")
                        for f in futures:
                            f.cancel()
                        break
            else:
                consecutive_402 = 0
                if label == "off_target":
                    off_target += 1
                else:
                    sub_cat_counts[label] += 1
            if i % 50 == 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                eta = (len(job_ids) - i) / rate if rate else 0
                log.info(
                    f"  {i}/{len(job_ids)} | rate {rate:.1f}/s | eta {eta/60:.1f}min | "
                    f"top: {dict(sub_cat_counts.most_common(3))} | off-target {off_target} | err {len(errors)}"
                )

    total_enriched = sum(sub_cat_counts.values())
    log.info(f"\n=== T12 v2 (非 AI) summary ===")
    log.info(f"  enriched: {total_enriched}")
    log.info(f"  off-target Pass1/2 拒: {off_target}")
    log.info(f"  errors: {len(errors)}")
    log.info(f"  耗时: {(time.time() - t0)/60:.1f}min")
    log.info(f"  sub_cat 分布:")
    for sc, n in sub_cat_counts.most_common():
        log.info(f"    {sc}: {n}")

    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps({
        "ran_at": datetime.utcnow().isoformat(),
        "filter": "non_ai_only (excludes AI 5 sub_cat 20 companies)",
        "enriched": total_enriched,
        "off_target": off_target,
        "errors": len(errors),
        "sub_cat_counts": dict(sub_cat_counts),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
