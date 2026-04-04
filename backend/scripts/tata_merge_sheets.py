#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

from app.services.tata_merge import dedupe_records

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_SHEET0 = Path("/home/chuanbo/projects/JobRadar/backend/data/tata_full.json")
DATA_DIR = PROJECT_ROOT / "backend" / "data"
MERGED_JSON = DATA_DIR / "tata_merged_dedup.json"
MERGED_CSV = DATA_DIR / "tata_merged_dedup.csv"


def to_text_list(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x)
    return str(value or "")


def map_record(rec: dict[str, object]) -> dict[str, object] | None:
    position_id = str(rec.get("position_id") or "")
    if not position_id:
        return None
    return {
        "job_id": f"tata_{position_id}",
        "source": "tatawangshen",
        "company": str(rec.get("main_company_name") or rec.get("company_alias") or rec.get("company_name") or ""),
        "company_type_industry": to_text_list(rec.get("industry")),
        "company_tags": to_text_list(rec.get("org_type")),
        "department": str(rec.get("company_name") or ""),
        "job_title": str(rec.get("job_title") or ""),
        "location": to_text_list(rec.get("address_str")),
        "major_req": to_text_list(rec.get("major_str")),
        "job_req": str(rec.get("raw_position_require") or "")[:2000],
        "job_duty": str(rec.get("responsibility") or "")[:2000],
        "application_status": "待申请",
        "job_stage": "campus",
        "source_config_id": "687d079c70ccc5e36315f4ba",
        "publish_date": str(rec.get("publish_date") or rec.get("create_time") or "").replace(" ", "T"),
        "deadline": str(rec.get("expire_date") or "").replace(" ", "T"),
        "detail_url": str(rec.get("position_web_url") or ""),
    }


def load_raw(path: Path) -> list[dict[str, object]]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("records", [])


def main() -> None:
    raw_files = [
        SOURCE_SHEET0,
        DATA_DIR / "tata_sheet_1.json",
        DATA_DIR / "tata_sheet_2.json",
        DATA_DIR / "tata_sheet_3.json",
    ]

    all_mapped: list[dict[str, object]] = []
    for path in raw_files:
        records = load_raw(path)
        print(f"载入 {path.name}: {len(records)} 条")
        for rec in records:
            mapped = map_record(rec)
            if mapped:
                all_mapped.append(mapped)

    before = len(all_mapped)
    merged = dedupe_records(all_mapped)
    after = len(merged)
    print(f"合并前: {before}")
    print(f"去重后: {after}")
    print(f"去重掉: {before - after}")

    with open(MERGED_JSON, "w", encoding="utf-8") as f:
        json.dump({"total_before": before, "total_after": after, "records": merged}, f, ensure_ascii=False)

    fieldnames = [
        "job_id", "source", "company", "company_type_industry", "company_tags", "department",
        "job_title", "location", "major_req", "job_req", "job_duty", "application_status",
        "job_stage", "source_config_id", "publish_date", "deadline", "detail_url",
    ]
    with open(MERGED_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    print(f"输出 JSON: {MERGED_JSON}")
    print(f"输出 CSV: {MERGED_CSV}")


if __name__ == "__main__":
    main()
