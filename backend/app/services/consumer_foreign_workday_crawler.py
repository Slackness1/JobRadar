"""消费/医药外企 Workday 补充 crawler — Phase 13.

之前消费外企 (consumer_foreign) 只通过 4 个客制 portal 抓取。
二次探查发现部分医药/消费外企 (如 阿斯利康) 使用 Workday CXS 且 endpoint
公开可访问。复用 `foreign_ibs_tier_crawler._fetch_workday_filtered` 的逻辑，
只是 stamp `source='consumer_foreign_official'` + `company_type_industry='消费外企'`。

当前已 wired:
  - 阿斯利康 (astrazeneca.wd3.myworkdayjobs.com)

Workday 422 仍堵的（同 Goldman/JPM 一墙）:
  - 阿迪达斯 / 霍尼韦尔 — 都标 deferred
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_crawl_logger import company_crawl_log
from app.services.crawler_llm_enrich import enrich_jobs_parallel
from app.services.foreign_ibs_tier_crawler import _fetch_workday_filtered


CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "consumer_foreign_workday.yaml"
)


def _load_targets() -> List[Dict[str, Any]]:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return payload.get("sites") or []


def crawl_consumer_foreign_workday(
    db: Session,
    existing_jobs: Optional[Dict[str, Job]] = None,
    target_names: Optional[List[str]] = None,
    parent_log_id: Optional[int] = None,
) -> Tuple[int, int, Dict[str, int]]:
    raw = _load_targets()
    if target_names:
        wanted = set(target_names)
        raw = [t for t in raw if t.get("name") in wanted]

    if existing_jobs is None:
        existing_jobs = {j.job_id: j for j in db.query(Job).all() if j.job_id}

    new_total = 0
    fetched_total = 0
    per_company: Dict[str, int] = {}

    for entry in raw:
        if entry.get("handler") != "workday":
            continue
        company = entry["name"]
        with company_crawl_log(
            db, source="consumer_foreign_official",
            company=company, parent_log_id=parent_log_id,
        ) as log:
            records = _fetch_workday_filtered(
                company=company,
                endpoint=entry["endpoint"],
                portal_url=entry.get("portal_url") or entry["endpoint"],
                queries=entry.get("search_queries") or ["China"],
                page_size=int(entry.get("page_size", 20)),
                max_pages_per_query=int(entry.get("max_pages_per_query", 8)),
                source="consumer_foreign_official",
                industry="消费外企",
                tags="consumer_foreign",
            )

            company_new = 0
            new_jobs_for_enrich: list[tuple[Job, str]] = []
            for mapped in records:
                jid = mapped.get("job_id")
                if not jid:
                    continue
                exist = existing_jobs.get(jid)
                if exist is None:
                    job = Job(**mapped)
                    db.add(job)
                    existing_jobs[jid] = job
                    company_new += 1
                    new_jobs_for_enrich.append((job, ""))
                else:
                    for field in (
                        "company", "company_tags", "job_title", "location",
                        "publish_date", "detail_url", "scraped_at",
                    ):
                        val = mapped.get(field)
                        if val is not None and val != "":
                            setattr(exist, field, val)
            db.flush()

            log.fetched_count = len(records)
            log.new_count = company_new
            per_company[company] = company_new
            fetched_total += len(records)
            new_total += company_new

            if new_jobs_for_enrich:
                try:
                    enrich_jobs_parallel(db, new_jobs_for_enrich)
                except Exception:
                    pass

    return new_total, fetched_total, per_company
