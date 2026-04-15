#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.services.internet_crawler import (
    build_internet_targets,
    crawl_internet_targets,
    select_primary_targets,
    summarize_results,
)


REPORT_DIR = BACKEND_DIR / "data" / "validation_reports"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _write_targets_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "tier",
        "company",
        "display_name",
        "url",
        "target_type",
        "source",
        "platform",
        "reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_results_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl official jobs for internet T1/T2 companies.")
    parser.add_argument("--tiers", default="t1,t2", help="Comma-separated tiers, default: t1,t2")
    parser.add_argument("--include-companies", default="", help="Comma-separated company names to include")
    parser.add_argument("--limit-targets", type=int, default=0, help="Limit number of target URLs for smoke testing")
    parser.add_argument("--max-pages", type=int, default=0, help="Override max pages per target")
    parser.add_argument("--list-targets", action="store_true", help="Only build and print target URL list")
    parser.add_argument("--all-candidates", action="store_true", help="Run every truth-layer candidate URL instead of primary list URLs")
    parser.add_argument("--dry-run", action="store_true", help="Run crawlers but do not write database changes")
    parser.add_argument("--output-prefix", default="", help="Optional output filename prefix")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    tiers = _split_csv(args.tiers) or ["t1", "t2"]
    include_companies = set(_split_csv(args.include_companies))
    targets = build_internet_targets(tiers=tiers)
    if not args.all_candidates:
        targets = select_primary_targets(targets)
    if include_companies:
        targets = [target for target in targets if target.company in include_companies]
    if args.limit_targets and args.limit_targets > 0:
        targets = targets[: args.limit_targets]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.output_prefix or f"internet_tier_crawl_{timestamp}"
    target_csv = REPORT_DIR / f"{prefix}_targets.csv"
    result_json = REPORT_DIR / f"{prefix}_results.json"

    target_rows = [asdict(target) for target in targets]
    _write_targets_csv(target_csv, target_rows)

    print(f"targets={len(targets)}")
    print(f"targets_csv={target_csv}")
    for target in targets[:50]:
        print(f"[{target.tier}] {target.company} | {target.platform} | {target.url}")
    if len(targets) > 50:
        print(f"... {len(targets) - 50} more target(s)")

    if args.list_targets:
        return

    db = SessionLocal()
    try:
        results = crawl_internet_targets(
            db,
            targets,
            dry_run=args.dry_run,
            max_pages=args.max_pages or None,
        )
        summary = summarize_results(results)
        payload = {
            "generated_at": datetime.now().isoformat(),
            "dry_run": args.dry_run,
            "tiers": tiers,
            "include_companies": sorted(include_companies),
            "summary": summary,
            "results": [asdict(item) for item in results],
        }
        _write_results_json(result_json, payload)

        print(f"results_json={result_json}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
