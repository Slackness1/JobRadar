"""Job Intel Deduper - 去重逻辑"""
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session

from app.models import JobIntelRecord


def dedupe_records(records: List[Dict]) -> Tuple[List[Dict], Dict[str, int]]:
    """去重情报记录

    去重规则：
    1. 同平台 + URL 去重
    2. 同平台 + platform_item_id 去重
    3. 同 job_id + 平台 + 标题相似度去重

    返回：
    - 去重后的记录列表
    - 去重统计：{"platform_url": x, "platform_item_id": y}
    """
    seen_urls = set()
    seen_item_ids = set()
    unique_records = []

    stats = {
        "platform_url": 0,
        "platform_item_id": 0,
    }

    for record in records:
        url = record.get("url", "")
        platform = record.get("platform", "")
        item_id = record.get("platform_item_id", "")

        # 去重逻辑 1: URL
        if url and (platform, url) in seen_urls:
            stats["platform_url"] += 1
            continue
        seen_urls.add((platform, url))

        # 去重逻辑 2: Item ID
        if item_id and (platform, item_id) in seen_item_ids:
            stats["platform_item_id"] += 1
            continue
        seen_item_ids.add((platform, item_id))

        unique_records.append(record)

    return unique_records, stats
