#!/usr/bin/env python3
"""
将 tata_full.json 导入 jobradar.db，并统计新增方向。
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
JSON_PATH = PROJECT_ROOT / "backend" / "data" / "tata_full.json"
DB_PATH = PROJECT_ROOT / "backend" / "data" / "jobradar.db"
CONFIG_ID = "687d079c70ccc5e36315f4ba"


def to_text_list(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x)
    return str(value or "")


def map_record(rec: dict[str, object]) -> dict[str, object] | None:
    position_id = str(rec.get("position_id") or "")
    if not position_id:
        return None

    company = str(
        rec.get("main_company_name")
        or rec.get("company_alias")
        or rec.get("company_name")
        or ""
    )

    publish_date = str(rec.get("publish_date") or rec.get("create_time") or "")
    if publish_date and "T" not in publish_date:
        publish_date = publish_date.replace(" ", "T")

    deadline = str(rec.get("expire_date") or "")
    if deadline and "T" not in deadline and " " in deadline:
        deadline = deadline.replace(" ", "T")

    return {
        "job_id": f"tata_{position_id}",
        "source": "tatawangshen",
        "company": company,
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
        "source_config_id": CONFIG_ID,
        "publish_date": publish_date or None,
        "deadline": deadline or None,
        "detail_url": str(rec.get("position_web_url") or ""),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {JSON_PATH}")

    with open(JSON_PATH, encoding="utf-8") as f:
        payload = json.load(f)

    records = payload.get("records", [])
    print(f"读取 JSON: {len(records)} 条")

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT job_id FROM jobs")
    existing_ids = {row[0] for row in cur.fetchall()}

    new_count = 0
    update_count = 0
    skip_count = 0

    new_industry_counter: Counter[str] = Counter()
    new_company_counter: Counter[str] = Counter()

    for idx, raw in enumerate(records, 1):
        mapped = map_record(raw)
        if not mapped:
            skip_count += 1
            continue

        jid = str(mapped["job_id"])
        if jid in existing_ids:
            updates = {k: v for k, v in mapped.items() if k != "job_id" and v not in (None, "")}
            if updates:
                sets = ", ".join(f"{k} = ?" for k in updates)
                vals = list(updates.values()) + [jid]
                cur.execute(f"UPDATE jobs SET {sets} WHERE job_id = ?", vals)
                update_count += 1
            continue

        cols = list(mapped.keys())
        placeholders = ", ".join("?" for _ in cols)
        cur.execute(
            f"INSERT INTO jobs ({', '.join(cols)}) VALUES ({placeholders})",
            [mapped[c] for c in cols],
        )
        existing_ids.add(jid)
        new_count += 1

        industry = str(mapped.get("company_type_industry") or "")
        company = str(mapped.get("company") or "")
        if industry:
            new_industry_counter[industry] += 1
        if company:
            new_company_counter[company] += 1

        if idx % 2000 == 0:
            conn.commit()
            print(f"已处理 {idx}/{len(records)} 条 | 新增 {new_count} | 更新 {update_count}")

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM jobs WHERE source='tatawangshen'")
    tata_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cur.fetchone()[0]

    print("\n✅ 导入完成")
    print(f"新增: {new_count}")
    print(f"更新: {update_count}")
    print(f"跳过: {skip_count}")
    print(f"TATA 总量: {tata_total}")
    print(f"DB 总量: {total_jobs}")

    print("\n新增行业 Top 15:")
    for name, count in new_industry_counter.most_common(15):
        print(f"  {name}: {count}")

    print("\n新增公司 Top 15:")
    for name, count in new_company_counter.most_common(15):
        print(f"  {name}: {count}")

    conn.close()


if __name__ == "__main__":
    main()
