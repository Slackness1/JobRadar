"""Phase G 校准 — flash+KB vs 库里强模型 baseline 的分歧地图(零强模型花费)。

参照 = jobs.quality_label(GT 公司金融岗已由 v3 deepseek-pro 重打, 24/25)。
本脚本只调 flash: 对样本跑 flash+KB, 与参照比, 按先验规则桶 + 命中/未命中
统计分歧率, 导出报告 → 用于验证/修剪 HARD_PATTERNS。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/26_divergence_map.py [--limit 300] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import app.config  # noqa: F401 — 触发 .env.local 加载

from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block
from app.services.phase_g.quality_cascade.cascade import quality_label_flash
from app.services.phase_g.quality_cascade.hard_patterns import is_hard_pattern
from app.services.phase_g.tier_fit.platform_skeleton import gt_companies_for_sub_cat  # noqa: F401

BACKEND_ROOT = Path(__file__).resolve().parents[2]
OUT = BACKEND_ROOT / "data" / "_phase_g" / "divergence_map.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("divergence_map")


def _sample_ids(limit: int) -> list[int]:
    """GT 公司、有强模型 baseline label 的金融岗。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(Job.id)
            .filter(Job.quality_label.in_(("good", "internship_only", "support_role", "low_signal")))
            .order_by(Job.id.desc())
            .limit(limit * 4)  # 多取, 下游再按 GT 命中过滤
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()


def _eval_one(job_id: int) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return None
        company = job.company or ""
        kb = build_company_kb_block(company)
        if not kb:  # 非 GT 公司, 没可信参照, 跳过
            return None
        ref = (job.quality_label or "").strip().lower()
        jd = {"company": company, "job_title": job.job_title or "",
              "job_duty": job.job_duty or "", "job_req": job.job_req or ""}
        flash_label = quality_label_flash(jd, kb_block=kb, temperature=0.3)
        hard, pattern = is_hard_pattern(company=company, title=jd["job_title"],
                                        duty=jd["job_duty"], req=jd["job_req"])
        return {"id": job_id, "ref": ref, "flash": flash_label,
                "agree": ref == flash_label, "hard": hard, "pattern": pattern}
    except Exception as exc:  # noqa: BLE001
        log.warning("job %s failed: %s", job_id, exc)
        return None
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--workers", type=int, default=8)
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

    by_pattern = defaultdict(lambda: {"n": 0, "agree": 0})
    for r in results:
        key = r["pattern"] or ("HARD_other" if r["hard"] else "EASY")
        by_pattern[key]["n"] += 1
        by_pattern[key]["agree"] += int(r["agree"])

    report = {
        "sample_size": len(results),
        "overall_agree_rate": round(sum(r["agree"] for r in results) / max(len(results), 1), 3),
        "by_pattern": {
            k: {
                "n": v["n"],
                "agree_rate": round(v["agree"] / max(v["n"], 1), 3),
                "divergence_rate": round(1 - v["agree"] / max(v["n"], 1), 3),
            }
            for k, v in sorted(by_pattern.items())
        },
        "transitions": dict(Counter(f"{r['ref']}->{r['flash']}" for r in results if not r["agree"]).most_common(20)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("overall agree %.1f%% | report → %s", report["overall_agree_rate"] * 100, OUT)
    for k, v in report["by_pattern"].items():
        log.info("  %-24s n=%-4d divergence=%.1f%%", k, v["n"], v["divergence_rate"] * 100)


if __name__ == "__main__":
    main()
