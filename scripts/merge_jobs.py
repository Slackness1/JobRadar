#!/usr/bin/env python3
"""
Normalize the latest JobRadar export CSV into a canonical project-a master CSV.

Canonical inputs/outputs:
- export csv: /home/ubuntu/.openclaw/workspace-projecta/data/exports/jobs_export.csv
- master csv: /home/ubuntu/.openclaw/workspace-projecta/data/jobs_master.csv
- db alias : /home/ubuntu/.openclaw/workspace-projecta/data/jobradar.db
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
WORKSPACE_DIR = SCRIPT_PATH.parents[1]
VENV_PYTHON = WORKSPACE_DIR / "JobRadar" / "venv" / "bin" / "python"

if VENV_PYTHON.exists() and Path(sys.executable) != VENV_PYTHON:
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(SCRIPT_PATH), *sys.argv[1:]])

import pandas as pd

from jobradar_paths import BACKUP_DIR, DB_ALIAS_PATH, EXPORT_CSV_PATH, MASTER_CSV_PATH, ensure_layout

CANONICAL_FIELDS = [
    "job_id",
    "company",
    "company_type_industry",
    "company_tags",
    "department",
    "job_title",
    "job_stage",
    "location",
    "major_req",
    "job_req",
    "job_duty",
    "publish_date",
    "deadline",
    "detail_url",
    "scraped_at",
    "total_score",
    "matched_tracks",
]

FIELD_MAPPING = {
    "job_id": "job_id",
    "company": "company",
    "company_type_industry": "company_type_industry",
    "company_tags": "company_tags",
    "department": "department",
    "job_title": "job_title",
    "title": "job_title",
    "job_stage": "job_stage",
    "job_type": "job_stage",
    "location": "location",
    "major_req": "major_req",
    "job_req": "job_req",
    "requirements": "job_req",
    "job_duty": "job_duty",
    "description": "job_duty",
    "publish_date": "publish_date",
    "deadline": "deadline",
    "detail_url": "detail_url",
    "url": "detail_url",
    "scraped_at": "scraped_at",
    "crawled_at": "scraped_at",
    "total_score": "total_score",
    "matched_tracks": "matched_tracks",
}


def _generate_job_id(row: pd.Series) -> str:
    parts = [
        str(row.get("company", "") or "").strip(),
        str(row.get("job_title", "") or "").strip(),
        str(row.get("detail_url", "") or "").strip(),
    ]
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


def _coerce_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["publish_date", "deadline", "scraped_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _normalize_export(df: pd.DataFrame) -> pd.DataFrame:
    normalized = pd.DataFrame()
    for source, target in FIELD_MAPPING.items():
        if source in df.columns and target not in normalized.columns:
            normalized[target] = df[source]

    for col in CANONICAL_FIELDS:
        if col not in normalized.columns:
            normalized[col] = ""

    normalized = normalized[CANONICAL_FIELDS]
    normalized = _coerce_datetime_columns(normalized)

    text_cols = [
        col
        for col in normalized.columns
        if pd.api.types.is_object_dtype(normalized[col]) or pd.api.types.is_string_dtype(normalized[col])
    ]
    for col in text_cols:
        normalized[col] = normalized[col].fillna("").astype(str).str.strip()

    if "job_id" not in normalized.columns or normalized["job_id"].eq("").all():
        normalized["job_id"] = normalized.apply(_generate_job_id, axis=1)
    else:
        missing = normalized["job_id"].fillna("").eq("")
        normalized.loc[missing, "job_id"] = normalized[missing].apply(_generate_job_id, axis=1)

    normalized = normalized[
        normalized["company"].ne("") & normalized["job_title"].ne("") & normalized["detail_url"].ne("")
    ]
    normalized = normalized.drop_duplicates(subset=["job_id"], keep="last")
    return normalized


def _load_existing_master() -> pd.DataFrame:
    if not MASTER_CSV_PATH.exists():
        return pd.DataFrame(columns=CANONICAL_FIELDS)
    existing = pd.read_csv(MASTER_CSV_PATH)
    return _normalize_export(existing)


def main() -> None:
    ensure_layout()

    if not EXPORT_CSV_PATH.exists():
        raise SystemExit(f"Missing export CSV: {EXPORT_CSV_PATH}")

    export_df = pd.read_csv(EXPORT_CSV_PATH)
    normalized_export = _normalize_export(export_df)
    existing_master = _load_existing_master()

    if not existing_master.empty:
        backup_path = BACKUP_DIR / f"jobs_master_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        MASTER_CSV_PATH.replace(backup_path)
        existing_master = pd.read_csv(backup_path)
        existing_master = _normalize_export(existing_master)

    merged = pd.concat([existing_master, normalized_export], ignore_index=True)
    merged = _normalize_export(merged)
    merged.to_csv(MASTER_CSV_PATH, index=False)

    print(f"export_csv={EXPORT_CSV_PATH}")
    print(f"master_csv={MASTER_CSV_PATH}")
    print(f"db_alias={DB_ALIAS_PATH} exists={DB_ALIAS_PATH.exists()}")
    print(f"rows={len(merged)}")


if __name__ == "__main__":
    main()
