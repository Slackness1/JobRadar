#!/usr/bin/env python3
"""Crawler health check — auto-detect broken / silently-failing per-company crawlers.

Per (source, company) tuple, computes:
  - jobs_in_db       : total rows in jobs table
  - last_run_status  : status of most recent company_crawl_logs row
  - last_run_fetched : fetched_count of most recent run
  - last_success_at  : when this company most recently had status=success
  - last_7d_runs     : list of (status, fetched_count) for last 7 days
  - anomaly_flags    : list of strings describing why this row is suspicious

Anomaly rules (combined):
  - low_fetch        : fetched_count < 30 on the most recent successful run
                       (we expect ≥ 30 jobs from any internet_official campus portal)
  - stale_success    : last_success_at older than 3 days
  - all_failed_7d    : every run in the last 7 days has status=failed
  - never_succeeded  : no successful run within window
  - never_run        : in registry but no log row at all

Usage:
  python backend/scripts/crawl_health_check.py
  python backend/scripts/crawl_health_check.py --json
  python backend/scripts/crawl_health_check.py --source internet_official
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func

from app.database import SessionLocal
from app.models import CompanyCrawlLog, Job


LOW_FETCH_THRESHOLD = 30
STALE_DAYS = 3
LOOKBACK_DAYS = 7


def _ago_days(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    return (datetime.utcnow() - ts).total_seconds() / 86400.0


def collect_health(db, source_filter: str | None = None) -> list[dict]:
    """Return one dict per (source, company) seen in either logs or jobs."""

    cutoff = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)

    log_q = db.query(CompanyCrawlLog).filter(CompanyCrawlLog.started_at >= cutoff)
    if source_filter:
        log_q = log_q.filter(CompanyCrawlLog.source == source_filter)
    logs_by_pair: dict[tuple[str, str], list[CompanyCrawlLog]] = defaultdict(list)
    for row in log_q.order_by(CompanyCrawlLog.started_at.asc()).all():
        logs_by_pair[(row.source or "", row.company or "")].append(row)

    job_q = db.query(Job.source, Job.company, func.count(Job.id))
    if source_filter:
        job_q = job_q.filter(Job.source == source_filter)
    jobs_count: dict[tuple[str, str], int] = {}
    for src, comp, n in job_q.group_by(Job.source, Job.company).all():
        jobs_count[(src or "", comp or "")] = int(n or 0)

    pairs = set(logs_by_pair.keys()) | set(jobs_count.keys())

    out: list[dict] = []
    now_utc = datetime.utcnow()

    for source, company in pairs:
        log_rows = logs_by_pair.get((source, company), [])
        jobs_total = jobs_count.get((source, company), 0)

        last = log_rows[-1] if log_rows else None
        successes = [r for r in log_rows if r.status == "success"]
        last_success = successes[-1] if successes else None
        last_success_at = last_success.started_at if last_success else None
        last_success_fetched = last_success.fetched_count if last_success else 0

        flags: list[str] = []
        if not log_rows:
            flags.append("never_run")
        else:
            if not successes:
                flags.append("never_succeeded")
            else:
                if (last_success_fetched or 0) < LOW_FETCH_THRESHOLD:
                    flags.append("low_fetch")
                age_d = _ago_days(last_success_at)
                if age_d is not None and age_d > STALE_DAYS:
                    flags.append("stale_success")
            if log_rows and all(r.status == "failed" for r in log_rows):
                flags.append("all_failed_7d")

        out.append({
            "source": source,
            "company": company,
            "jobs_in_db": jobs_total,
            "n_runs_7d": len(log_rows),
            "last_run_status": last.status if last else None,
            "last_run_at": last.started_at.isoformat() if last and last.started_at else None,
            "last_run_fetched": int(last.fetched_count or 0) if last else 0,
            "last_run_new": int(last.new_count or 0) if last else 0,
            "last_success_at": last_success_at.isoformat() if last_success_at else None,
            "last_success_fetched": int(last_success_fetched or 0),
            "anomaly_flags": flags,
        })

    out.sort(key=lambda r: (
        0 if r["anomaly_flags"] else 1,
        -len(r["anomaly_flags"]),
        r["last_success_fetched"],
        r["source"],
        r["company"],
    ))
    return out


def render_text(rows: list[dict]) -> str:
    parts: list[str] = []
    parts.append(
        f"Crawler health — {len(rows)} (source, company) pairs · {LOOKBACK_DAYS}d window\n"
    )
    by_severity: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["anomaly_flags"]:
            by_severity["anomaly"].append(r)
        else:
            by_severity["ok"].append(r)

    if by_severity["anomaly"]:
        parts.append(f"=== {len(by_severity['anomaly'])} anomalies ===")
        parts.append(
            f"  {'company':<22} {'source':<28} {'jobs':>6} {'7d':>3} "
            f"{'last':<10} {'flags'}"
        )
        for r in by_severity["anomaly"]:
            company = r["company"][:22]
            src = r["source"][:28]
            last = (r["last_run_status"] or "—")[:10]
            flags = ",".join(r["anomaly_flags"])
            parts.append(
                f"  {company:<22} {src:<28} {r['jobs_in_db']:>6} {r['n_runs_7d']:>3} "
                f"{last:<10} {flags}"
            )
        parts.append("")

    if by_severity["ok"]:
        parts.append(f"=== {len(by_severity['ok'])} healthy (top 10 by last_success_fetched) ===")
        top_ok = sorted(
            by_severity["ok"], key=lambda r: -r["last_success_fetched"]
        )[:10]
        parts.append(
            f"  {'company':<22} {'source':<28} {'jobs':>6} {'7d':>3} {'last_fetched':>12}"
        )
        for r in top_ok:
            parts.append(
                f"  {r['company'][:22]:<22} {r['source'][:28]:<28} "
                f"{r['jobs_in_db']:>6} {r['n_runs_7d']:>3} "
                f"{r['last_success_fetched']:>12}"
            )

    return "\n".join(parts)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="output JSON instead of text")
    p.add_argument("--source", help="filter by source (e.g. internet_official)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        rows = collect_health(db, source_filter=args.source)
    finally:
        db.close()

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_text(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
