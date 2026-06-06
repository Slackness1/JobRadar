"""Phase G 验证 — 级联 vs 全量强模型: 成本/质量对照表。

样本 = GT 公司金融岗(有强模型 baseline)。对每个岗跑 cascade_quality_label,
统计: 升级率、与 baseline 一致率、估算成本对比。放量前看这张表。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/27_validate_cascade.py [--limit 50] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.quality_cascade.cascade import cascade_quality_label
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block

BACKEND_ROOT = Path(__file__).resolve().parents[2]
OUT = BACKEND_ROOT / "data" / "_phase_g" / "cascade_validation.json"

# 粗略单价(USD/1M tok), 仅用于相对比较。flash≈$0.14/$0.28, 强模型(中转 gpt-5.5)≈$0.25/$1.50。
_FLASH_PER_CALL = 0.00012   # ~600 tok in + ~80 out 估算
_STRONG_PER_CALL = 0.0009

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("validate_cascade")


def _sample_ids(limit: int) -> list[int]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Job.id)
            .filter(Job.quality_label.in_(("good", "internship_only", "support_role", "low_signal")))
            .order_by(Job.id.desc())
            .limit(limit * 4)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()


def _eval_one(job_id: int) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job or not build_company_kb_block(job.company or ""):
            return None
        ref = (job.quality_label or "").strip().lower()
        jd = {"company": job.company or "", "job_title": job.job_title or "",
              "job_duty": job.job_duty or "", "job_req": job.job_req or ""}
        out = cascade_quality_label(jd, n_votes=3)
        n_flash = 0 if out["route"] == "strong" and out["reason"] != "disagreement" else len(out["votes"])
        return {"id": job_id, "ref": ref, "cascade": out["quality_label"],
                "route": out["route"], "reason": out["reason"],
                "agree": ref == out["quality_label"], "n_flash_calls": n_flash,
                "n_strong_calls": 1 if out["route"] == "strong" else 0}
    except Exception as exc:  # noqa: BLE001
        log.warning("job %s failed: %s", job_id, exc)
        return None
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    ids = _sample_ids(args.limit)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(_eval_one, i) for i in ids]
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results.append(r)
            if len(results) >= args.limit:
                break

    n = len(results)
    n_strong = sum(r["n_strong_calls"] for r in results)
    cascade_cost = sum(r["n_flash_calls"] * _FLASH_PER_CALL + r["n_strong_calls"] * _STRONG_PER_CALL for r in results)
    allstrong_cost = n * _STRONG_PER_CALL
    report = {
        "sample_size": n,
        "agree_rate_vs_baseline": round(sum(r["agree"] for r in results) / max(n, 1), 3),
        "escalation_rate": round(n_strong / max(n, 1), 3),
        "route_breakdown": dict(Counter(r["route"] for r in results)),
        "reason_breakdown": dict(Counter(r["reason"] for r in results)),
        "est_cost_cascade_usd": round(cascade_cost, 5),
        "est_cost_all_strong_usd": round(allstrong_cost, 5),
        "est_savings_pct": round((1 - cascade_cost / max(allstrong_cost, 1e-9)) * 100, 1),
        "disagreements": [
            {"id": r["id"], "ref": r["ref"], "cascade": r["cascade"], "reason": r["reason"]}
            for r in results if not r["agree"]
        ][:30],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("agree=%.1f%% | escalation=%.1f%% | savings=%.1f%% | → %s",
             report["agree_rate_vs_baseline"] * 100, report["escalation_rate"] * 100,
             report["est_savings_pct"], OUT)


if __name__ == "__main__":
    main()
