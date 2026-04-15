#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = Path("/home/chuanbo/projects/JobRadar/backend/data/jobradar.db")
DB_PATH = PROJECT_ROOT / "backend" / "data" / "jobradar.db"
MERGED_JSON = PROJECT_ROOT / "backend" / "data" / "tata_merged_dedup.json"


def main() -> None:
    db_path = DB_PATH if DB_PATH.exists() else DEFAULT_DB_PATH
    with open(MERGED_JSON, encoding="utf-8") as f:
        payload = json.load(f)
    records = payload.get("records", [])
    print(f"读取 merged: {len(records)} 条")

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM jobs WHERE source='tatawangshen'")
    old_tata = cur.fetchone()[0]
    print(f"旧 TATA 条数: {old_tata}")

    cur.execute("SELECT id FROM jobs WHERE source='tatawangshen'")
    tata_ids = [row[0] for row in cur.fetchall()]
    if tata_ids:
        placeholders = ",".join("?" for _ in tata_ids)
        cur.execute(f"DELETE FROM job_scores WHERE job_id IN ({placeholders})", tata_ids)
        cur.execute(f"DELETE FROM job_intel_tasks WHERE job_id IN ({placeholders})", tata_ids)
        cur.execute(f"DELETE FROM job_intel_records WHERE job_id IN ({placeholders})", tata_ids)
        cur.execute(f"DELETE FROM job_intel_snapshots WHERE job_id IN ({placeholders})", tata_ids)
        cur.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", tata_ids)
        conn.commit()

    insert_cols = [
        "job_id", "source", "company", "company_type_industry", "company_tags", "department",
        "job_title", "location", "major_req", "job_req", "job_duty", "application_status",
        "job_stage", "source_config_id", "publish_date", "deadline", "detail_url", "scraped_at",
    ]

    industry_counter: Counter[str] = Counter()
    company_counter: Counter[str] = Counter()

    for i, rec in enumerate(records, 1):
        row = {k: rec.get(k, "") for k in insert_cols if k != "scraped_at"}
        row["scraped_at"] = datetime.now(timezone.utc).isoformat()
        values = [row.get(col, "") for col in insert_cols]
        placeholders = ", ".join("?" for _ in insert_cols)
        cur.execute(f"INSERT INTO jobs ({', '.join(insert_cols)}) VALUES ({placeholders})", values)

        if row.get("company_type_industry"):
            industry_counter[str(row["company_type_industry"])] += 1
        if row.get("company"):
            company_counter[str(row["company"])] += 1

        if i % 2000 == 0:
            conn.commit()
            print(f"已导入 {i}/{len(records)}")

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM jobs WHERE source='tatawangshen'")
    new_tata = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cur.fetchone()[0]

    print("\n✅ 覆盖导入完成")
    print(f"目标 DB: {db_path}")
    print(f"新 TATA 条数: {new_tata}")
    print(f"DB 总条数: {total_jobs}")

    print("\n方向 Top 15:")
    for k, v in industry_counter.most_common(15):
        print(f"  {k}: {v}")

    print("\n公司 Top 15:")
    for k, v in company_counter.most_common(15):
        print(f"  {k}: {v}")

    conn.close()


if __name__ == "__main__":
    main()
