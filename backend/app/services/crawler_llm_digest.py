"""Daily digest of tier-crawl results.

Run once a day shortly after the 09:00 tier crawl finishes. Aggregates
today's company_crawl_logs rows into a small structured summary, asks
DeepSeek V4-Flash to phrase it as a 1-2 sentence Chinese digest, and
persists the result in system_config so the UI can fetch it cheaply.

Cache-friendly: the system prompt + JSON-shape user prompt are stable
across days; only the numbers change. DeepSeek's prefix cache should hit.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import CompanyCrawlLog, SystemConfig
from app.services.crawler_llm import build_flash_client, flash_model_name

logger = logging.getLogger(__name__)

DIGEST_KEY = "sites_daily_digest"

# Mirror the SOURCE_GROUPS in frontend Sites.tsx so labels match.
_SOURCE_GROUP: dict[str, str] = {
    "internet_official": "互联网官网",
    "state_owned_official": "国央企",
    "consumer_foreign_official": "消费外企",
    "securities_zhiye": "券商",
    "securities_zhiye_legacy": "券商",
    "securities_hotjob": "券商",
    "securities_moka_embedded": "券商",
    "bank_official": "银行",
}


def _today_window(now: datetime) -> tuple[datetime, datetime]:
    """Return [start, end) in naive UTC for 'today in Asia/Shanghai'."""
    sh = timezone(timedelta(hours=8))
    now_sh = now.astimezone(sh) if now.tzinfo else (now + timedelta(hours=8)).replace(tzinfo=sh)
    today_sh = now_sh.replace(hour=0, minute=0, second=0, microsecond=0)
    end_sh = today_sh + timedelta(days=1)
    return (
        today_sh.astimezone(timezone.utc).replace(tzinfo=None),
        end_sh.astimezone(timezone.utc).replace(tzinfo=None),
    )


def aggregate_today_stats(db: Session, now: datetime) -> dict:
    """Aggregate today's company_crawl_logs into a small dict for prompting."""
    start, end = _today_window(now)
    rows = (
        db.query(CompanyCrawlLog)
        .filter(CompanyCrawlLog.started_at >= start, CompanyCrawlLog.started_at < end)
        .all()
    )

    by_group: dict[str, int] = {}
    failed: list[str] = []
    successes = 0
    failures = 0
    total_new = 0

    for r in rows:
        total_new += r.new_count or 0
        group = _SOURCE_GROUP.get(r.source or "", r.source or "未分组")
        by_group[group] = by_group.get(group, 0) + (r.new_count or 0)
        if r.status == "success":
            successes += 1
        elif r.status == "failed":
            failures += 1
            failed.append(r.company)

    return {
        "total_companies": len(rows),
        "successes": successes,
        "failures": failures,
        "total_new": int(total_new),
        "failed_companies": failed,
        "by_group": by_group,
    }


_SYSTEM_PROMPT = """你是数据爬取每日简报助手。给定结构化统计，写一条 1-2 句话的 markdown 简报，覆盖：今天跑批的总体情况、失败的公司（如有）、各分组新增、有亮点的方向（如有）。

风格要求：
- 简洁、直陈数据，不要客套话。
- 数字使用阿拉伯数字。
- 不超过 200 字。
- 只输出文字，不要 json 不要 markdown 代码块。"""


def generate_daily_digest(stats: dict) -> Optional[str]:
    """One Flash call. Returns string on success, None on any failure."""
    try:
        client = build_flash_client()
        user_payload = json.dumps(stats, ensure_ascii=False, sort_keys=True)
        resp = client.chat.completions.create(
            model=flash_model_name(),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.3,
            max_tokens=300,
        )
    except Exception as exc:
        logger.debug("crawler_llm_digest.generate_daily_digest failed: %s", exc)
        return None

    try:
        out = resp.choices[0].message.content or ""
    except (IndexError, AttributeError):
        return None

    out = out.strip()
    return out if out else None


def persist_digest(db: Session, text: str) -> None:
    """Upsert digest into system_config with current timestamp."""
    payload = json.dumps(
        {"text": text, "generated_at": datetime.utcnow().isoformat()},
        ensure_ascii=False,
    )
    existing = db.query(SystemConfig).filter_by(key=DIGEST_KEY).first()
    if existing is None:
        db.add(SystemConfig(key=DIGEST_KEY, value=payload, updated_at=datetime.utcnow()))
    else:
        existing.value = payload
        existing.updated_at = datetime.utcnow()
    db.commit()
