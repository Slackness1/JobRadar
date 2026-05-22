"""Backfill canonical_track for jobs where it's NULL/empty.

Used to clear the historical gap from before CRAWLER_LLM_ENRICH_ENABLED=1.
Targets a configurable company-name allowlist (default = P0 green-19) so
we don't spend LLM quota on the long tail of internet/retail companies
where the 50% canonical ceiling is by design (SAIF prompt scope).

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python scripts/backfill_canonical_track.py --dry-run
    PYTHONPATH=. .venv/bin/python scripts/backfill_canonical_track.py --commit

Cost estimate (DeepSeek V4-Flash, 2026-05 pricing):
    ~284 rows × ¥0.001 / row ≈ ¥0.3 total
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_

from app.database import SessionLocal
from app.models import Job
from app.services.crawler_llm_enrich import enrich_jobs_parallel


P0_GREEN_COMPANIES = [
    # 公募 6
    "南方基金", "中欧基金", "银华基金", "华夏基金", "博时基金", "兴证全球基金",
    # 券商 6
    "中金公司", "华泰证券", "中信建投", "广发证券", "招商证券", "光大证券",
    # 私募 5
    "高毅资产", "九坤投资", "幻方量化", "衍复投资", "鸣石投资",
    # 外资 3
    "Goldman Sachs", "Morgan Stanley", "Citi",
]


def _find_null_rows(db, companies: list[str]) -> list[Job]:
    return (
        db.query(Job)
        .filter(
            Job.company.in_(companies),
            or_(Job.canonical_track.is_(None), Job.canonical_track == ""),
        )
        .all()
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print stats only, no LLM calls")
    ap.add_argument("--commit", action="store_true", help="Actually run enrichment + commit DB")
    ap.add_argument("--companies", nargs="+", default=P0_GREEN_COMPANIES,
                    help="Override company allowlist (default = P0 green-19)")
    args = ap.parse_args()

    if not args.dry_run and not args.commit:
        ap.error("Pass --dry-run or --commit")

    db = SessionLocal()
    try:
        rows = _find_null_rows(db, args.companies)
        print(f"Found {len(rows)} NULL-canonical jobs across {len(args.companies)} companies")
        by_company: dict[str, int] = {}
        for j in rows:
            by_company[j.company] = by_company.get(j.company, 0) + 1
        for c, n in sorted(by_company.items(), key=lambda kv: -kv[1]):
            print(f"  {c:20} {n:5}")

        if args.dry_run:
            return

        # Build (job, raw_text) tuples
        jobs_with_raw = [
            (j, (j.job_duty or "") + "\n" + (j.job_req or "")) for j in rows
        ]
        print(f"\nRunning enrich_jobs_parallel on {len(jobs_with_raw)} rows...")
        n_ok = enrich_jobs_parallel(db, jobs_with_raw)
        db.commit()
        print(f"Enriched {n_ok}/{len(jobs_with_raw)} successfully. DB committed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
