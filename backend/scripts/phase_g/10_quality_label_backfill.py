"""T10 — quality_label v2 backfill (~28k recent jobs).

幂等: progress file 跟踪已处理 job id, 中断重跑安全。
并发: ThreadPoolExecutor 12 线程, DeepSeek API 支持。
范围: 最近 30 天 scraped 的 alive (或 link_status NULL) 帖。
成本估算: 28k 帖 × 0.0003 USD/调用 (Pro medium + prefix cache) ≈ $6-8。
跑前确保 DEEPSEEK_API_KEY 有余额 (≥ $10 推荐) — 否则会全 402。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/10_quality_label_backfill.py \
    [--days 30] [--workers 12] [--limit N] [--dry-run] [--reset-progress]
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
from app.services.crawler_llm_enrich import enrich_job_quality_label_v2

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
PROGRESS_FILE = BACKEND_ROOT / "data" / "_phase_g" / "quality_backfill_progress.json"
CHECKPOINT_FILE = BACKEND_ROOT / "data" / "_phase_g" / "quality_backfill_v2_timestamp.txt"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("quality_backfill")


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("progress file corrupt, treating as empty")
    return {"done_job_ids": [], "label_counts": {}, "started_at": None}


def _save_progress(progress: dict) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PROGRESS_FILE)


def _process_job(job_id: int) -> tuple[int, str | None, str | None]:
    """One job: fetch from DB, classify via LLM, write back. Each thread own session.

    Returns (job_id, new_label, error_msg)."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, "not_found")
        result = enrich_job_quality_label_v2({
            "company": job.company or "",
            "job_title": job.job_title or "",
            "job_duty": job.job_duty or "",
            "job_req": job.job_req or "",
        })
        new_label = result["quality_label"]
        if job.quality_label != new_label:
            job.quality_label = new_label
            db.commit()
        return (job_id, new_label, None)
    except Exception as exc:  # noqa: BLE001
        # 让 LLM API 错误冒上来 (e.g. 402 余额耗尽), 主线程统计 fail
        return (job_id, None, str(exc)[:200])
    finally:
        db.close()


def _collect_active_ids(days: int, limit: int | None) -> list[int]:
    db = SessionLocal()
    try:
        q = db.query(Job.id).filter(
            Job.scraped_at > datetime.utcnow() - timedelta(days=days)
        ).filter((Job.link_status == "alive") | (Job.link_status.is_(None)))
        if limit:
            q = q.limit(limit)
        return [r[0] for r in q.all()]
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="只跑最近 N 天 scraped 的帖")
    parser.add_argument("--workers", type=int, default=12, help="并发 LLM 调用线程数")
    parser.add_argument("--limit", type=int, default=None, help="dry-run 用, 只跑前 N 个")
    parser.add_argument("--dry-run", action="store_true", help="只打 todo 数, 不调 LLM")
    parser.add_argument("--reset-progress", action="store_true", help="清除已有 progress 重新开始")
    args = parser.parse_args()

    if args.reset_progress and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        log.info("progress 文件已清空")

    active_ids = _collect_active_ids(args.days, args.limit)
    log.info(f"alive jobs 近 {args.days} 天: {len(active_ids)}")

    progress = _load_progress()
    done_ids = set(progress.get("done_job_ids", []))
    todo = [jid for jid in active_ids if jid not in done_ids]
    label_counts: Counter[str] = Counter(progress.get("label_counts", {}))
    errors: list[tuple[int, str]] = []

    log.info(f"resume: {len(done_ids)} 已完成 / {len(todo)} 待跑")
    if args.dry_run:
        log.info("--dry-run 不调 LLM, 退出")
        return 0

    if not todo:
        log.info("无待跑帖, 退出")
        return 0

    if progress.get("started_at") is None:
        progress["started_at"] = datetime.utcnow().isoformat()

    t0 = time.time()
    consecutive_402 = 0  # 余额耗尽自动 abort
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_process_job, jid): jid for jid in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            jid, label, err = fut.result()
            if err:
                errors.append((jid, err))
                if "402" in err or "Insufficient Balance" in err:
                    consecutive_402 += 1
                    if consecutive_402 >= 5:
                        log.error(
                            f"连续 {consecutive_402} 个 402, 余额耗尽, 中止。已完成 {len(done_ids)}, 待跑 {len(todo) - i}"
                        )
                        for f in futures:
                            f.cancel()
                        break
                else:
                    consecutive_402 = 0
            else:
                consecutive_402 = 0
                label_counts[label] += 1
                done_ids.add(jid)
            if i % 200 == 0:
                progress["done_job_ids"] = list(done_ids)
                progress["label_counts"] = dict(label_counts)
                _save_progress(progress)
                elapsed = time.time() - t0
                rate = i / elapsed
                eta = (len(todo) - i) / rate if rate else 0
                log.info(
                    f"  {i}/{len(todo)} | rate {rate:.1f}/s | eta {eta / 60:.1f}min | "
                    f"top labels: {dict(label_counts.most_common(3))} | errors {len(errors)}"
                )

    progress["done_job_ids"] = list(done_ids)
    progress["label_counts"] = dict(label_counts)
    _save_progress(progress)
    CHECKPOINT_FILE.write_text(datetime.utcnow().isoformat(), encoding="utf-8")

    total_labeled = sum(label_counts.values())
    log.info(f"\n=== T10 backfill summary ===")
    log.info(f"  总成功: {total_labeled}")
    log.info(f"  错误: {len(errors)}")
    log.info(f"  耗时: {(time.time() - t0) / 60:.1f}min")
    log.info(f"  label 分布:")
    for lbl, n in label_counts.most_common():
        pct = n / max(total_labeled, 1) * 100
        log.info(f"    {lbl}: {n} ({pct:.1f}%)")
    if errors:
        log.info(f"\n  错误前 5 个:")
        for jid, msg in errors[:5]:
            log.info(f"    job_id={jid}: {msg}")

    return 0 if not consecutive_402 >= 5 else 2


if __name__ == "__main__":
    sys.exit(main())
