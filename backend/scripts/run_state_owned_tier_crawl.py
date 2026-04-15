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
from app.services.state_owned_crawler import (
    build_state_owned_targets,
    crawl_state_owned_targets,
    summarize_results,
)


REPORT_DIR = BACKEND_DIR / "data" / "validation_reports"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl official campus jobs for SOE / central SOE tier companies.")
    parser.add_argument("--include-groups", default="", help="Comma-separated group names to include")
    parser.add_argument("--include-companies", default="", help="Comma-separated company canonical names to include")
    parser.add_argument("--limit-targets", type=int, default=0, help="Limit targets for smoke testing")
    parser.add_argument("--max-pages", type=int, default=0, help="Override max pages per target")
    parser.add_argument("--list-targets", action="store_true", help="Only build and print target list")
    parser.add_argument("--dry-run", action="store_true", help="Run crawlers but do not write database changes")
    parser.add_argument("--include-uncrawlable", action="store_true", help="Also include rows marked non-crawlable if they have an apply link")
    parser.add_argument("--output-prefix", default="", help="Optional output filename prefix")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    include_groups = set(_split_csv(args.include_groups))
    include_companies = set(_split_csv(args.include_companies))
    targets = build_state_owned_targets(include_uncrawlable=args.include_uncrawlable)
    if include_groups:
        targets = [target for target in targets if target.group in include_groups]
    if include_companies:
        targets = [target for target in targets if target.company in include_companies]
    if args.limit_targets and args.limit_targets > 0:
        targets = targets[: args.limit_targets]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.output_prefix or f"state_owned_tier_crawl_{timestamp}"
    target_csv = REPORT_DIR / f"{prefix}_targets.csv"
    result_json = REPORT_DIR / f"{prefix}_results.json"

    target_rows = [asdict(target) for target in targets]
    _write_csv(target_csv, target_rows)

    print(f"targets={len(targets)}")
    print(f"targets_csv={target_csv}")
    for target in targets[:80]:
        print(f"[{target.tier}] {target.group} | {target.company} | {target.platform} | {target.url}")
    if len(targets) > 80:
        print(f"... {len(targets) - 80} more target(s)")

    if args.list_targets:
        return

    db = SessionLocal()
    try:
        results = crawl_state_owned_targets(
            db,
            targets,
            dry_run=args.dry_run,
            max_pages=args.max_pages or None,
        )
        summary = summarize_results(results)
        payload = {
            "generated_at": datetime.now().isoformat(),
            "dry_run": args.dry_run,
            "include_groups": sorted(include_groups),
            "include_companies": sorted(include_companies),
            "summary": summary,
            "results": [asdict(item) for item in results],
        }
        result_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"results_json={result_json}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
