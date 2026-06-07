"""Phase G P0 — deepseek-pro 判别人工金标抽检表。

从 good / low_signal / 从没判过(NULL) 三档各抽 N 个 GT 公司活岗,用 deepseek 现场
重判 quality(good/intern 的再打 sub_cat),连同 JD 摘要导成 markdown 表给人工打勾。
目的: 拿到 deepseek-pro 判别的真实"对不对"准确率(我们唯一缺的绝对数)。纯读不写库。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/29_quality_review_sheet.py [--per-bucket 15]
"""
from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job
from app.services.crawler_llm_enrich import enrich_job_quality_label_v3
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block
from app.services.phase_g.sub_cat_enricher import (
    pass1_classify_strategy,
    pass2_classify_subcat,
)
from app.services.phase_g.tier_fit.tier_ladder import _norm_company

BACKEND_ROOT = Path(__file__).resolve().parents[2]
OUT_MD = BACKEND_ROOT / "data" / "_phase_g" / "quality_review_sheet.md"
OUT_JSON = BACKEND_ROOT / "data" / "_phase_g" / "quality_review_sheet.json"
SYNC = Path("/home/ubuntu/jobradar-sync/quality-cascade-2026-06-07")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("review_sheet")

_BUCKETS = {"good": "good", "low_signal": "low_signal", "NULL": None}
_DEAD = {"dead", "404", "gone", "removed", "expired"}


def _sample(per_bucket: int) -> dict[str, list[int]]:
    """每档抽 per_bucket 个 GT 公司活岗 id(按 id 倒序取最近的)。"""
    from app.services.phase_g.quality_cascade.company_kb import load_gt_index
    gt = set(load_gt_index().keys())
    db = SessionLocal()
    out: dict[str, list[int]] = {k: [] for k in _BUCKETS}
    try:
        rows = db.query(Job.id, Job.company, Job.quality_label, Job.link_status).order_by(Job.id.desc()).all()
        for jid, comp, ql, ls in rows:
            if (ls or "").lower() in _DEAD:
                continue
            if _norm_company(comp or "") not in gt:
                continue
            bucket = "NULL" if not (ql or "").strip() else ql
            if bucket in out and len(out[bucket]) < per_bucket:
                out[bucket].append(jid)
            if all(len(v) >= per_bucket for v in out.values()):
                break
        return out
    finally:
        db.close()


def _judge(job_id: int, db_bucket: str) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return None
        jd = {"company": job.company or "", "job_title": job.job_title or "",
              "job_duty": job.job_duty or "", "job_req": job.job_req or ""}
        q = enrich_job_quality_label_v3(jd)
        sub = None
        if q.get("quality_label") in ("good", "internship_only"):
            p1 = pass1_classify_strategy(jd)
            strat = p1.get("strategy_type") if p1.get("confidence", 0) >= 0.5 else None
            if strat:
                p2 = pass2_classify_subcat(jd, strat)
                if p2.get("confidence", 0) >= 0.3:
                    sub = p2.get("sub_category")
        jd_excerpt = (jd["job_duty"] + " | " + jd["job_req"]).strip()[:260].replace("\n", " ")
        return {"id": job_id, "db_bucket": db_bucket, "company": jd["company"],
                "title": jd["job_title"], "jd": jd_excerpt,
                "ds_quality": q.get("quality_label"), "ds_reason": (q.get("reasoning") or "")[:90],
                "ds_subcat": sub}
    except Exception as exc:  # noqa: BLE001
        log.warning("job %s failed: %s", job_id, exc)
        return None
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-bucket", type=int, default=15)
    args = ap.parse_args()

    sample = _sample(args.per_bucket)
    for k, v in sample.items():
        log.info("bucket %-12s sampled %d", k, len(v))
    tasks = [(jid, b) for b, ids in sample.items() for jid in ids]

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(_judge, jid, b) for jid, b in tasks]
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results.append(r)
    results.sort(key=lambda r: (r["db_bucket"], r["id"]))

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# deepseek-pro 判别人工金标抽检",
        "",
        "对每行看 JD,判断 **deepseek 的判定对不对**,在最后两列填 `对`/`错`(+一句为什么)。",
        "- `库里现状` = 这岗当前库里的 quality(NULL=从没判过)。",
        "- `deepseek判定` = 现在用 deepseek 重判的结果。两者不一样的地方最值得看。",
        "",
        "| # | 公司 | 标题 | JD摘要 | 库里现状 | deepseek判定 | deepseek理由 | sub_cat | quality对? | sub_cat对? |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        cell = lambda s: str(s or "").replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {i} | {cell(r['company'])} | {cell(r['title'])} | {cell(r['jd'])} | "
            f"{cell(r['db_bucket'])} | **{cell(r['ds_quality'])}** | {cell(r['ds_reason'])} | "
            f"{cell(r['ds_subcat'])} |  |  |"
        )
    md = "\n".join(lines) + "\n"
    OUT_MD.write_text(md, encoding="utf-8")
    try:
        SYNC.mkdir(parents=True, exist_ok=True)
        (SYNC / OUT_MD.name).write_text(md, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log.warning("sync copy failed: %s", exc)
    log.info("sheet: %d 行 → %s (+ sync)", len(results), OUT_MD)


if __name__ == "__main__":
    main()
