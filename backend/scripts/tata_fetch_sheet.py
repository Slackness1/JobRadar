#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ENV_PATH = Path("/home/chuanbo/projects/JobRadar/.env")
DOTENV_PATH = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "backend" / "data"

API_URL = "https://www.tatawangshen.com/api/recruit/position/exclusive"
LOGIN_URL = "https://www.tatawangshen.com/api/user/login"
CONFIG_ID = "687d079c70ccc5e36315f4ba"
PAGE_SIZE = 200
SAVE_EVERY_PAGES = 10
MAX_PAGES = 400


def load_credentials() -> tuple[str, str]:
    env_path = DOTENV_PATH if DOTENV_PATH.exists() else DEFAULT_ENV_PATH
    username = ""
    password = ""
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TATA_USERNAME="):
                username = line.split("=", 1)[1]
            elif line.startswith("TATA_PASSWORD="):
                password = line.split("=", 1)[1]
    return username, password


def login(username: str, password: str) -> str:
    r = requests.post(LOGIN_URL, json={"username": username, "password": password}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"登录失败: {data}")
    return data["data"]["token"]


def load_checkpoint(checkpoint_path: Path) -> tuple[int, list[dict[str, object]], int | None]:
    if not checkpoint_path.exists():
        return 1, [], None
    with open(checkpoint_path, encoding="utf-8") as f:
        data = json.load(f)
    return int(data.get("next_page", 1)), data.get("records", []), data.get("api_count")


def save_checkpoint(checkpoint_path: Path, next_page: int, records: list[dict[str, object]], api_count: int | None) -> None:
    tmp = checkpoint_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"next_page": next_page, "record_count": len(records), "api_count": api_count, "records": records}, f, ensure_ascii=False)
    tmp.replace(checkpoint_path)


def save_final(output_path: Path, records: list[dict[str, object]], api_count: int | None) -> None:
    tmp = output_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"total": len(records), "api_count": api_count, "records": records}, f, ensure_ascii=False)
    tmp.replace(output_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet-index", type=int, required=True)
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    sheet_index = args.sheet_index
    output_path = Path(args.output) if args.output else DATA_DIR / f"tata_sheet_{sheet_index}.json"
    checkpoint_path = output_path.with_suffix(".checkpoint.json")

    username, password = load_credentials()
    token = login(username, password)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Origin": "https://www.tatawangshen.com",
        "Referer": "https://www.tatawangshen.com/manage?tab=vip",
        "User-Agent": "Mozilla/5.0",
    }

    session = requests.Session()
    start_page, all_records, total_api = load_checkpoint(checkpoint_path)
    print(f"sheet {sheet_index}: 从第 {start_page} 页开始，已缓存 {len(all_records)} 条")

    for page in range(start_page, MAX_PAGES + 1):
        body = {
            "position_export_config_id": CONFIG_ID,
            "sheet_index": sheet_index,
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
        response_json = None
        for attempt in range(3):
            try:
                resp = session.post(API_URL, headers=headers, json=body, timeout=90)
                if resp.status_code == 429:
                    time.sleep((attempt + 1) * 5)
                    continue
                resp.raise_for_status()
                response_json = resp.json()
                break
            except Exception:
                if attempt < 2:
                    time.sleep((attempt + 1) * 3)
        if response_json is None:
            print(f"sheet {sheet_index}: page {page} 失败，保存 checkpoint")
            save_checkpoint(checkpoint_path, page, all_records, total_api)
            return

        payload = response_json.get("data", {}) if isinstance(response_json, dict) else {}
        if total_api is None:
            total_api = payload.get("count") if isinstance(payload, dict) else None
            print(f"sheet {sheet_index}: API 总数 {total_api}")
        records = payload.get("results", []) if isinstance(payload, dict) else []
        if not records:
            break
        all_records.extend(records)
        if page % SAVE_EVERY_PAGES == 0:
            save_checkpoint(checkpoint_path, page + 1, all_records, total_api)
            print(f"sheet {sheet_index}: P{page} -> {len(all_records)}/{total_api}")
        if len(records) < PAGE_SIZE:
            print(f"sheet {sheet_index}: 最后一页 P{page} {len(records)} 条")
            break
        time.sleep(random.uniform(0.15, 0.35))

    save_final(output_path, all_records, total_api)
    if checkpoint_path.exists():
        checkpoint_path.unlink()
    print(f"sheet {sheet_index}: 完成，共 {len(all_records)} 条 -> {output_path}")


if __name__ == "__main__":
    main()
