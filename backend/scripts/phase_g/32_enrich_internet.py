"""互联网大厂 sub_cat enrich:候选=32 大厂今日岗(绕过金融 GT 闸),复用 enrich_job_sub_cat。
Pass1 路由到 互联网/AI 应用_PM_开发 的写 sub_cat;路由 null(骑手/HR)→ off_target 不进池。
模型走 ENRICH_LLM_*(运行时 env 设 gpt-5.4),不改 enrich 代码。
Usage: PYTHONPATH=. <venv>/python scripts/phase_g/32_enrich_internet.py [--workers 8] [--limit N] [--dry-run]"""
from __future__ import annotations
import argparse, json, logging, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import app.config  # noqa: F401
from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.sub_cat_enricher import enrich_job_sub_cat

MANIFEST = Path("/home/ubuntu/jobradar-sync/out/fanout_manifest.json")
AI_SUBCATS = {"AI PM", "AI算法业务", "Agent工程师", "LLM算法post-train",
              "多模态推理优化", "搜索推荐广告算法", "AI应用开发工程师"}
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("enrich_internet")


def _candidate_ids(limit):
    names = [r["name"] for r in json.loads(MANIFEST.read_text())]
    db = SessionLocal()
    try:
        from sqlalchemy import func
        q = (db.query(Job.id).filter(
            Job.source == "tatawangshen",
            Job.company.in_(names),
            Job.quality_label.in_(["good", "internship_only"]),
            Job.sub_cat_enriched_at.is_(None),
            func.date(Job.scraped_at) == "2026-06-08",
        ).order_by(Job.id))
        if limit:
            q = q.limit(limit)
        return [r[0] for r in q.all()]
    finally:
        db.close()


def _process(job_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, "not_found")
        result = enrich_job_sub_cat(job)
        if result is None:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ids = _candidate_ids(args.limit)
    log.info(f"互联网候选: {len(ids)}")
    if args.dry_run or not ids:
        return 0
    counts, off, errs = Counter(), 0, []
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(_process, j): j for j in ids}
        for n, f in enumerate(as_completed(futs), 1):
            jid, label, err = f.result()
            if err:
                errs.append((jid, err))
            elif label == "off_target":
                off += 1
            else:
                counts[label] += 1
            if n % 200 == 0:
                ai = sum(v for k, v in counts.items() if k in AI_SUBCATS)
                log.info(f"  {n}/{len(ids)} | 写 {sum(counts.values())} (AI {ai}) | off {off} | err {len(errs)}")
    ai_total = sum(v for k, v in counts.items() if k in AI_SUBCATS)
    log.info(f"完成: 写 sub_cat {sum(counts.values())} (AI {ai_total} / 非AI {sum(counts.values())-ai_total}) | off_target {off} | err {len(errs)} | {(time.time()-t0)/60:.1f}min")
    log.info(f"sub_cat 分布: {dict(counts.most_common())}")
    if errs:
        log.warning(f"前5错误: {errs[:5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
