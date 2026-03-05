#!/usr/bin/env python3
"""
tata_jobs_export.py - 爬取 tatawangshen.com VIP/专属岗位表格
"""
import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import requests
from requests.exceptions import RequestException

API_URL = "https://www.tatawangshen.com/api/recruit/position/exclusive"
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.tatawangshen.com",
    "Referer": "https://www.tatawangshen.com/manage?tab=vip",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

OUTPUT_FIELDS = [
    "job_id",
    "company",
    "company_type_industry",
    "company_tags",
    "department",
    "job_title",
    "location",
    "major_req",
    "job_req",
    "job_duty",
    "referral_code",
    "publish_date",
    "deadline",
    "detail_url",
    "apply_url",
    "job_stage",
    "source_config_id",
    "scraped_at",
]


def find_records(obj: Any) -> List[Dict]:
    """递归查找返回数据中的记录数组"""
    if isinstance(obj, list):
        if all(isinstance(item, dict) for item in obj):
            return obj
        return []
    if isinstance(obj, dict):
        for key in ["results", "data", "list", "records", "rows", "items", "positions"]:
            if key in obj:
                result = find_records(obj[key])
                if result:
                    return result
        for value in obj.values():
            result = find_records(value)
            if result:
                return result
    return []


def get_nested(obj: Dict, *keys: str, default: Any = "") -> Any:
    """安全获取嵌套字段"""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, {})
        else:
            return default
    return obj if obj not in (None, {}) else default


def generate_job_id(record: Dict) -> str:
    """生成 job_id"""
    for key in ["id", "_id", "position_id", "job_id"]:
        if key in record and record[key]:
            return str(record[key])
    raw = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def join_list(items: Any, sep: str = ",") -> str:
    """将列表或字符串转换为逗号分隔的字符串"""
    if not items:
        return ""
    if isinstance(items, list):
        return sep.join(str(x) for x in items if x)
    return str(items)


def map_record(record: Dict) -> Dict:
    """映射单条记录到输出格式"""
    org_type = record.get("org_type") or []
    industry = record.get("industry") or []
    company_type_industry = "/".join(filter(None, [
        join_list(org_type, "/"),
        join_list(industry, "/")
    ]))
    
    position_req = record.get("position_require_new") or {}
    
    location = join_list(record.get("address_str") or position_req.get("address") or [])
    major_req = join_list(record.get("major_str") or position_req.get("major") or [])
    
    return {
        "job_id": record.get("position_id") or record.get("_id") or generate_job_id(record),
        "company": record.get("company_alias") or record.get("main_company_name") or "",
        "company_type_industry": company_type_industry,
        "company_tags": join_list(record.get("tags") or []),
        "department": record.get("company_name") or "",
        "job_title": record.get("job_title") or "",
        "location": location,
        "major_req": major_req,
        "job_req": record.get("raw_position_require") or "",
        "job_duty": record.get("responsibility") or "",
        "referral_code": "",
        "publish_date": record.get("publish_date") or record.get("spider_time") or "",
        "deadline": record.get("expire_date") or "",
        "detail_url": record.get("position_web_url") or "",
        "apply_url": "",
        "job_stage": "campus",
        "source_config_id": "",
        "scraped_at": datetime.now().isoformat(),
    }


def split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def split_int_csv(value: str) -> List[int]:
    result: List[int] = []
    for item in split_csv(value):
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


def resolve_stage(
    config_id: str,
    sheet_index: int,
    target_index: int,
    total_targets: int,
    internship_ids: Set[str],
    internship_sheet_indexes: Set[int],
) -> str:
    if sheet_index in internship_sheet_indexes:
        return "internship"
    if config_id in internship_ids:
        return "internship"
    if internship_ids or internship_sheet_indexes:
        return "campus"
    if total_targets >= 4 and target_index >= 2:
        return "internship"
    return "campus"


def load_existing_job_ids(filepath: str) -> Set[str]:
    """加载已存在的 job_id 集合"""
    if not os.path.exists(filepath):
        return set()
    job_ids = set()
    try:
        with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "job_id" in row and row["job_id"]:
                    job_ids.add(row["job_id"])
    except Exception as e:
        print(f"[WARN] 读取已有文件失败，将覆盖: {e}")
    return job_ids


def fetch_page(
    session: requests.Session,
    token: str,
    config_id: str,
    sheet_index: int,
    page: int,
    page_size: int,
    job_title: str = "",
    company_id: str = "",
    max_retries: int = 3,
    sleep_range: tuple = (0.5, 1.5),
) -> Optional[Dict]:
    """抓取单页数据"""
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    body = {
        "position_export_config_id": config_id,
        "sheet_index": sheet_index,
        "company_id": company_id,
        "job_title": job_title,
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
        "page_size": page_size,
    }
    
    for attempt in range(max_retries):
        try:
            resp = session.post(API_URL, headers=headers, json=body, timeout=30)
            
            if resp.status_code == 401:
                print("[ERROR] 401 Unauthorized - Token 可能已失效")
                sys.exit(1)
            elif resp.status_code == 403:
                print("[ERROR] 403 Forbidden - 无权限或 Token 失效")
                sys.exit(1)
            elif resp.status_code == 429:
                wait = (attempt + 1) * 5
                print(f"[WARN] 429 Too Many Requests, 等待 {wait}s...")
                time.sleep(wait)
                continue
            elif resp.status_code >= 500:
                wait = (attempt + 1) * 3
                print(f"[WARN] {resp.status_code} Server Error, 等待 {wait}s...")
                time.sleep(wait)
                continue
            
            resp.raise_for_status()
            data = resp.json()
            
            sleep_time = random.uniform(*sleep_range)
            time.sleep(sleep_time)
            
            return data
            
        except RequestException as e:
            print(f"[ERROR] 请求失败 (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON 解析失败: {e}")
            return None
    
    return None


def run_scraper(
    token: str,
    config_ids: List[str],
    sheet_indexes: List[int],
    output_file: str,
    page_size: int = 50,
    max_pages: int = 100,
    job_title: str = "",
    company_id: str = "",
    dry_run: bool = False,
    sleep_range: tuple = (0.5, 1.5),
    internship_ids: Optional[Set[str]] = None,
    internship_sheet_indexes: Optional[Set[int]] = None,
) -> None:
    """运行爬虫"""
    session = requests.Session()
    all_records: List[Dict] = []
    existing_ids = set() if dry_run else load_existing_job_ids(output_file)
    
    internship_ids = internship_ids or set()
    internship_sheet_indexes = internship_sheet_indexes or set()
    config_ids = [item for item in config_ids if item]
    sheet_indexes = [idx for idx in sheet_indexes if isinstance(idx, int) and idx >= 0]
    if not sheet_indexes:
        sheet_indexes = [0]

    crawl_targets: List[tuple[str, int]] = []
    seen_targets = set()
    for current_config_id in config_ids:
        for current_sheet_index in sheet_indexes:
            target = (current_config_id, current_sheet_index)
            if target in seen_targets:
                continue
            seen_targets.add(target)
            crawl_targets.append(target)

    for target_index, (config_id, sheet_index) in enumerate(crawl_targets):
        stage = resolve_stage(
            config_id,
            sheet_index,
            target_index,
            len(crawl_targets),
            internship_ids,
            internship_sheet_indexes,
        )
        print(
            f"[INFO] 抓取分支 {target_index + 1}/{len(crawl_targets)}: "
            f"config={config_id}, sheet={sheet_index} ({stage})"
        )

        for page in range(1, max_pages + 1):
            print(f"[INFO] 抓取第 {page} 页...")

            data = fetch_page(
                session, token, config_id, sheet_index, page, page_size,
                job_title, company_id, sleep_range=sleep_range
            )

            if data is None:
                print("[ERROR] 获取数据失败，停止当前分支抓取")
                break

            records = find_records(data)

            if not records:
                print("[INFO] 没有更多数据")
                break

            if dry_run:
                print("\n[DRY-RUN] 第一页记录数:", len(records))
                if records:
                    print("[DRY-RUN] 第一条记录的 keys:")
                    for key in sorted(records[0].keys()):
                        print(f"  - {key}")
                return

            new_count = 0
            for record in records:
                mapped = map_record(record)
                mapped["job_stage"] = stage
                mapped["source_config_id"] = config_id
                if mapped["job_id"] not in existing_ids:
                    all_records.append(mapped)
                    existing_ids.add(mapped["job_id"])
                    new_count += 1

            print(f"[INFO] 第 {page} 页: {len(records)} 条记录, 新增 {new_count} 条")

            if len(records) < page_size:
                print("[INFO] 已到最后一页")
                break
    
    if not all_records:
        print("[INFO] 没有新数据需要写入")
        return
    
    write_header = not os.path.exists(output_file)
    with open(output_file, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows(all_records)
    
    print(f"[INFO] 写入 {len(all_records)} 条记录到 {output_file}")


def main():
    parser = argparse.ArgumentParser(description="tatawangshen.com 岗位爬虫")
    parser.add_argument("--out", default="jobs.csv", help="输出 CSV 文件路径")
    parser.add_argument("--page-size", type=int, default=50, help="每页记录数")
    parser.add_argument("--max-pages", type=int, default=100, help="最大抓取页数")
    parser.add_argument("--sleep-min", type=float, default=0.5, help="请求间隔最小秒数")
    parser.add_argument("--sleep-max", type=float, default=1.5, help="请求间隔最大秒数")
    parser.add_argument("--job-title", default="", help="按岗位名称筛选")
    parser.add_argument("--company-id", default="", help="按公司 ID 筛选")
    parser.add_argument("--config-ids", default="", help="多个 position_export_config_id，逗号分隔")
    parser.add_argument("--config-id", default="", help="position_export_config_id")
    parser.add_argument("--sheet-indexes", default="", help="多个 sheet_index，逗号分隔")
    parser.add_argument("--token", default="", help="API Token (或使用环境变量 TATA_TOKEN)")
    parser.add_argument("--dry-run", action="store_true", help="只抓第一页并打印字段")
    
    args = parser.parse_args()
    
    token = args.token or os.environ.get("TATA_TOKEN", "")
    raw_config_ids = args.config_ids or os.environ.get("TATA_EXPORT_CONFIG_IDS", "")
    if raw_config_ids:
        config_ids = split_csv(raw_config_ids)
    else:
        fallback = args.config_id or os.environ.get("TATA_EXPORT_CONFIG_ID", "")
        config_ids = split_csv(fallback)

    raw_sheet_indexes = args.sheet_indexes or os.environ.get("TATA_EXPORT_SHEET_INDEXES", "")
    if raw_sheet_indexes:
        sheet_indexes = split_int_csv(raw_sheet_indexes)
    else:
        sheet_indexes = [0]

    internship_ids = set(split_csv(os.environ.get("TATA_INTERNSHIP_CONFIG_IDS", "")))
    internship_sheet_indexes = set(split_int_csv(os.environ.get("TATA_INTERNSHIP_SHEET_INDEXES", "")))
    
    if not token:
        print("[ERROR] 缺少 TATA_TOKEN 环境变量")
        sys.exit(1)
    if not config_ids:
        print("[ERROR] 缺少 TATA_EXPORT_CONFIG_IDS / TATA_EXPORT_CONFIG_ID")
        sys.exit(1)
    
    print(f"[INFO] 开始抓取 -> {args.out}")
    print(f"[INFO] 每页 {args.page_size} 条, 最多 {args.max_pages} 页")
    
    run_scraper(
        token=token,
        config_ids=config_ids,
        sheet_indexes=sheet_indexes,
        output_file=args.out,
        page_size=args.page_size,
        max_pages=args.max_pages,
        job_title=args.job_title,
        company_id=args.company_id,
        dry_run=args.dry_run,
        sleep_range=(args.sleep_min, args.sleep_max),
        internship_ids=internship_ids,
        internship_sheet_indexes=internship_sheet_indexes,
    )


if __name__ == "__main__":
    main()
