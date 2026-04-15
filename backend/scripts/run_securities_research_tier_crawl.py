#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models import Job
from app.services.securities_crawler import run_configured_securities_crawl


REPORT_DIR = BACKEND_DIR / "data" / "validation_reports"
DB_PATH = BACKEND_DIR / "data" / "jobradar.db"
SECURITIES_CONFIG = BACKEND_DIR / "config" / "securities_campus.yaml"

TIER_COMPANIES = {
    "t0": ["广发证券", "长江证券"],
    "t0.5": ["中信建投", "中金公司"],
    "t1": ["申万宏源", "国泰海通", "兴业证券", "中信证券"],
    "t1.5": ["招商证券", "海通证券", "浙商证券", "东方证券", "华泰证券"],
    "t2": ["天风证券", "中泰证券", "光大证券", "国盛证券", "东吴证券", "方正证券", "华创证券", "国信证券", "民生证券"],
}

ALIASES = {
    "国君": "国泰海通",
    "国泰君安": "国泰海通",
    "海通": "国泰海通",
    "海通证券": "国泰海通",
    "中信": "中信证券",
    "申万": "申万宏源",
}


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _normalize_company(name: str) -> str:
    stripped = name.strip()
    return ALIASES.get(stripped, stripped)


def _load_targets() -> list[dict]:
    payload = yaml.safe_load(SECURITIES_CONFIG.read_text(encoding="utf-8")) or {}
    return payload.get("sites") or []


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl official jobs for securities research tiers T0-T2.")
    parser.add_argument("--tiers", default="t0,t0.5,t1,t1.5,t2", help="Comma-separated tiers to include")
    parser.add_argument("--include-companies", default="", help="Comma-separated company names to include")
    parser.add_argument("--list-targets", action="store_true", help="Only print selected target entries")
    parser.add_argument("--dry-run", action="store_true", help="Run crawlers without committing database changes")
    parser.add_argument("--backup-db", action="store_true", help="Create a database backup before crawling")
    parser.add_argument("--output-prefix", default="", help="Optional output filename prefix")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    tiers = _split_csv(args.tiers) or ["t0", "t0.5", "t1", "t1.5", "t2"]
    requested = []
    for tier in tiers:
        requested.extend(TIER_COMPANIES.get(tier, []))
    requested.extend(_split_csv(args.include_companies))

    normalized_requested = []
    seen_requested = set()
    for company in requested:
        normalized = _normalize_company(company)
        if normalized not in seen_requested:
            seen_requested.add(normalized)
            normalized_requested.append(normalized)

    config_targets = _load_targets()
    selected_targets = [target for target in config_targets if target.get("name") in set(normalized_requested)]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.output_prefix or f"securities_research_tier_{timestamp}"
    target_csv = REPORT_DIR / f"{prefix}_targets.csv"
    result_json = REPORT_DIR / f"{prefix}_results.json"

    _write_csv(target_csv, selected_targets)
    print(f"selected_companies={normalized_requested}")
    print(f"target_entries={len(selected_targets)}")
    print(f"targets_csv={target_csv}")
    for target in selected_targets:
        print(f"{target['name']} | {target.get('ats_family')} | {target.get('entry_url')}")

    if args.list_targets:
        return

    if args.backup_db and DB_PATH.exists():
        backup_path = DB_PATH.with_name(f"{DB_PATH.stem}.before_securities_research_{timestamp}.bak")
        shutil.copy2(DB_PATH, backup_path)
        print(f"backup_db={backup_path}")

    db = SessionLocal()
    try:
        existing_jobs = {job.job_id: job for job in db.query(Job).all()}
        new_count, total_count, company_counts = run_configured_securities_crawl(
            db,
            existing_jobs,
            target_names=normalized_requested,
        )
        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        payload = {
            "generated_at": datetime.now().isoformat(),
            "dry_run": args.dry_run,
            "tiers": tiers,
            "requested_companies": normalized_requested,
            "selected_target_entries": selected_targets,
            "summary": {
                "new_count": new_count,
                "total_count": total_count,
                "company_counts": company_counts,
            },
        }
        result_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"results_json={result_json}")
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
