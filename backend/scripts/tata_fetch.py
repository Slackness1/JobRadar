#!/usr/bin/env python3
"""
TATA 全量拉取（支持断点续跑）

功能：
- 直接调用 TATA 登录 API 获取 token（不依赖 Playwright）
- 分页拉取全部岗位
- 每 10 页保存一次 checkpoint
- 支持从上次中断页继续

用法：
  python3 backend/scripts/tata_fetch.py
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "backend" / "data"
OUTPUT_PATH = DATA_DIR / "tata_full.json"
CHECKPOINT_PATH = DATA_DIR / "tata_full.checkpoint.json"

API_URL = "https://www.tatawangshen.com/api/recruit/position/exclusive"
LOGIN_URL = "https://www.tatawangshen.com/api/user/login"
CONFIG_ID = "687d079c70ccc5e36315f4ba"
PAGE_SIZE = 200
SAVE_EVERY_PAGES = 10
MAX_PAGES = 400


def load_credentials() -> tuple[str, str]:
    username = ""
    password = ""
    with open(DOTENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TATA_USERNAME="):
                username = line.split("=", 1)[1]
            elif line.startswith("TATA_PASSWORD="):
                password = line.split("=", 1)[1]
    return username, password


def login(username: str, password: str) -> str:
    r = requests.post(
        LOGIN_URL,
        json={"username": username, "password": password},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"登录失败: {data}")
    return data["data"]["token"]


def build_headers(token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Origin": "https://www.tatawangshen.com",
        "Referer": "https://www.tatawangshen.com/manage?tab=vip",
        "User-Agent": "Mozilla/5.0",
    }


def build_body(page: int) -> dict[str, object]:
    return {
        "position_export_config_id": CONFIG_ID,
        "sheet_index": 0,
        "company_id": "",
        "job_title": "",
        "major_ids": [],
        "address_ids": [],
        "tags": [],
        "industry": [],
        "org_type": [],
        "degree_ids": [],
        "english_ids": [],
        "school_ids": [],
        "personal_ids": [],
        "other_ids": [],
        "page": page,
        "page_size": PAGE_SIZE,
    }


def load_checkpoint() -> tuple[int, list[dict[str, object]], int | None]:
    if not CHECKPOINT_PATH.exists():
        return 1, [], None

    with open(CHECKPOINT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    next_page = int(data.get("next_page", 1))
    records = data.get("records", [])
    api_count = data.get("api_count")
    return next_page, records, api_count


def save_checkpoint(next_page: int, records: list[dict[str, object]], api_count: int | None) -> None:
    tmp_path = CHECKPOINT_PATH.with_suffix(".tmp")
    payload = {
        "next_page": next_page,
        "record_count": len(records),
        "api_count": api_count,
        "records": records,
    }
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    tmp_path.replace(CHECKPOINT_PATH)


def save_final(records: list[dict[str, object]], api_count: int | None) -> None:
    tmp_path = OUTPUT_PATH.with_suffix(".tmp")
    payload = {
        "total": len(records),
        "api_count": api_count,
        "records": records,
    }
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    tmp_path.replace(OUTPUT_PATH)


def fetch_page(session: requests.Session, headers: dict[str, str], page: int) -> dict[str, object] | None:
    body = build_body(page)
    for attempt in range(3):
        try:
            r = session.post(API_URL, headers=headers, json=body, timeout=90)
            if r.status_code == 429:
                time.sleep((attempt + 1) * 5)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt < 2:
                time.sleep((attempt + 1) * 3)
            else:
                return None
    return None


def main() -> None:
    print("TATA 全量拉取（断点续跑）")
    print("=" * 50)

    username, password = load_credentials()
    if not username or not password:
        raise RuntimeError("TATA_USERNAME / TATA_PASSWORD 未配置")

    token = login(username, password)
    headers = build_headers(token)
    session = requests.Session()

    start_page, all_records, total_api = load_checkpoint()
    print(f"从第 {start_page} 页开始，当前已缓存 {len(all_records)} 条")

    for page in range(start_page, MAX_PAGES + 1):
        data = fetch_page(session, headers, page)
        if data is None:
            print(f"Page {page} 失败，已保存 checkpoint，稍后可继续")
            save_checkpoint(page, all_records, total_api)
            return

        payload_obj = data.get("data", {})
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        if total_api is None:
            total_api = payload.get("count")
            print(f"API 总数: {total_api}")

        records = payload.get("results", [])
        if not records:
            print(f"Page {page}: 空页，结束")
            break

        all_records.extend(records)

        if page % SAVE_EVERY_PAGES == 0:
            save_checkpoint(page + 1, all_records, total_api)
            print(f"P{page}: 累计 {len(all_records)}/{total_api}，已保存 checkpoint")

        if len(records) < PAGE_SIZE:
            print(f"Page {page}: 最后一页 {len(records)} 条")
            break

        time.sleep(random.uniform(0.15, 0.35))

    save_final(all_records, total_api)
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    size_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024
    print("\n✅ 拉取完成")
    print(f"总记录数: {len(all_records)}")
    print(f"API 声称总数: {total_api}")
    print(f"输出文件: {OUTPUT_PATH}")
    print(f"文件大小: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
