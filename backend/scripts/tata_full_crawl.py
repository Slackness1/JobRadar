#!/usr/bin/env python3
"""
TATA 网申全量拉取脚本

直接用 API 登录（不用 Playwright），分页拉取全量岗位，增量写入 DB。
用法: python3 backend/scripts/tata_full_crawl.py
"""

import json
import random
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── 配置 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "backend" / "data" / "jobradar.db"
DOTENV_PATH = PROJECT_ROOT / ".env"

API_URL = "https://www.tatawangshen.com/api/recruit/position/exclusive"
LOGIN_URL = "https://www.tatawangshen.com/api/user/login"
CONFIG_ID = "687d079c70ccc5e36315f4ba"
PAGE_SIZE = 200


def load_credentials():
    """从 .env 读取 TATA 凭证"""
    creds = {}
    with open(DOTENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TATA_USERNAME="):
                creds["username"] = line.split("=", 1)[1]
            elif line.startswith("TATA_PASSWORD="):
                creds["password"] = line.split("=", 1)[1]
    return creds.get("username", ""), creds.get("password", "")


def login(username: str, password: str) -> str:
    """API 登录获取 token"""
    r = requests.post(LOGIN_URL, json={"username": username, "password": password}, timeout=15)
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"登录失败: {data}")
    return data["data"]["token"]


def map_record(rec: dict) -> dict | None:
    """将 TATA API 记录映射为 Job 表字段"""
    position_id = rec.get("position_id", "")
    if not position_id:
        return None

    # 公司名优先用 main_company_name，其次 company_alias，最后 company_name
    company = rec.get("main_company_name", "") or rec.get("company_alias", "") or rec.get("company_name", "")

    # 行业
    industry_list = rec.get("industry", [])
    industry = ", ".join(industry_list) if isinstance(industry_list, list) else str(industry_list)

    # 性质
    org_type_list = rec.get("org_type", [])
    org_type = ", ".join(org_type_list) if isinstance(org_type_list, list) else str(org_type_list)

    # 地点
    addr_list = rec.get("address_str", [])
    location = ", ".join(addr_list) if isinstance(addr_list, list) else str(addr_list)

    # 岗位类别
    job_title_str = rec.get("job_title_str", [])
    job_title_names = ", ".join(job_title_str) if isinstance(job_title_str, list) else ""

    # 专业要求
    major_str = rec.get("major_str", "")
    if isinstance(major_str, list):
        major_str = ", ".join(major_str)

    # 学历要求
    degree_str = rec.get("degree_str", [])
    if isinstance(degree_str, list):
        degree_str = ", ".join(degree_str)

    # 标签
    tags = rec.get("tags", [])
    tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)

    # 工作职责/要求
    responsibility = rec.get("responsibility", "") or ""
    raw_require = rec.get("raw_position_require", "") or ""
    job_duty = responsibility
    job_req = raw_require

    # 详情 URL
    detail_url = rec.get("position_web_url", "") or ""

    # 招聘人数
    num_hire = rec.get("num_hire", "") or ""

    # 截止日期
    expire_date = rec.get("expire_date", "") or ""

    # 发布日期
    publish_date = rec.get("publish_date", "") or rec.get("create_time", "") or ""
    # 转为 ISO 格式
    if publish_date and "T" not in publish_date:
        publish_date = publish_date.replace(" ", "T")

    return {
        "job_id": f"tata_{position_id}",
        "source": "tatawangshen",
        "company": company,
        "company_type_industry": industry,
        "company_tags": org_type,
        "department": rec.get("company_name", ""),  # 具体部门/业务线
        "job_title": rec.get("job_title", ""),
        "location": location,
        "major_req": major_str,
        "job_req": job_req[:2000] if job_req else "",
        "job_duty": job_duty[:2000] if job_duty else "",
        "application_status": "待申请",
        "job_stage": "campus",
        "source_config_id": CONFIG_ID,
        "publish_date": publish_date,
        "deadline": expire_date,
        "detail_url": detail_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    print("TATA 网申全量拉取")
    print("=" * 50)

    # 1. 加载凭证 & 登录
    username, password = load_credentials()
    if not username or not password:
        print("错误: TATA 凭证未配置")
        sys.exit(1)

    print(f"[1] 登录...")
    token = login(username, password)
    print(f"Token OK: {token[:30]}...")

    # 2. 分页拉取
    print(f"\n[2] 全量拉取 (page_size={PAGE_SIZE})...")
    session = requests.Session()
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.tatawangshen.com",
        "Referer": "https://www.tatawangshen.com/manage?tab=vip",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Authorization": f"Bearer {token}",
    }

    all_records = []
    total_count = None

    for page in range(1, 300):
        body = {
            "position_export_config_id": CONFIG_ID,
            "sheet_index": 0,
            "company_id": "", "job_title": "",
            "major_ids": [], "address_ids": [], "tags": [], "industry": [],
            "org_type": [], "degree_ids": [], "english_ids": [],
            "school_ids": [], "personal_ids": [], "other_ids": [],
            "page": page, "page_size": PAGE_SIZE,
        }

        success = False
        for attempt in range(3):
            try:
                r = session.post(API_URL, headers=headers, json=body, timeout=60)
                if r.status_code == 429:
                    time.sleep((attempt + 1) * 5)
                    continue
                if r.status_code in (401, 403):
                    print(f"Token 过期 (page {page})!")
                    sys.exit(1)
                r.raise_for_status()
                success = True
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep((attempt + 1) * 3)
                else:
                    print(f"Page {page} 失败: {e}")
                    break

        if not success:
            print(f"Page {page} 重试耗尽，停止")
            break

        resp_data = r.json().get("data", {})
        if total_count is None:
            total_count = resp_data.get("count", "?")
            print(f"  API 总数: {total_count}")

        records = resp_data.get("results", [])
        if not records:
            print(f"  Page {page}: 空页，结束")
            break

        all_records.extend(records)

        if page % 30 == 0 or len(records) < PAGE_SIZE:
            print(f"  Page {page}: {len(records)} 条, 累计 {len(all_records)}/{total_count}")

        if len(records) < PAGE_SIZE:
            break

        time.sleep(random.uniform(0.3, 0.8))

    print(f"\n拉取完成: {len(all_records)} 条")

    # 3. 写入 DB
    print(f"\n[3] 写入数据库...")
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # 获取已有 job_id
    cur.execute("SELECT job_id FROM jobs")
    existing_ids = set(r[0] for r in cur.fetchall())

    new_count = 0
    update_count = 0
    skip_count = 0

    for rec in all_records:
        mapped = map_record(rec)
        if not mapped:
            skip_count += 1
            continue

        jid = mapped["job_id"]

        if jid in existing_ids:
            # 更新已有记录
            updates = {k: v for k, v in mapped.items() if k != "job_id" and v}
            if updates:
                sets = ", ".join(f"{k} = ?" for k in updates)
                vals = list(updates.values()) + [jid]
                try:
                    cur.execute(f"UPDATE jobs SET {sets} WHERE job_id = ?", vals)
                    update_count += 1
                except Exception:
                    pass
            continue

        # 新增
        cols = ", ".join(mapped.keys())
        placeholders = ", ".join(["?"] * len(mapped))
        try:
            cur.execute(f"INSERT INTO jobs ({cols}) VALUES ({placeholders})", list(mapped.values()))
            existing_ids.add(jid)
            new_count += 1
        except sqlite3.IntegrityError:
            skip_count += 1
        except Exception:
            skip_count += 1

        if new_count > 0 and new_count % 2000 == 0:
            conn.commit()
            print(f"  已写入 {new_count} 新增...")

    conn.commit()

    # 验证
    cur.execute("SELECT COUNT(*) FROM jobs WHERE source='tatawangshen'")
    tata_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM jobs")
    all_total = cur.fetchone()[0]
    conn.close()

    print(f"\n{'=' * 50}")
    print(f"✅ 完成!")
    print(f"  拉取: {len(all_records)}")
    print(f"  新增: {new_count}")
    print(f"  更新: {update_count}")
    print(f"  跳过: {skip_count}")
    print(f"  TATA 总计: {tata_total}")
    print(f"  DB 总计: {all_total}")


if __name__ == "__main__":
    main()
