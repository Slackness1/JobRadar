"""Top 头部私募 (hedge funds) crawler — Phase 9.

Mirrors funds_crawler.py's dispatcher pattern: load yaml, dispatch to existing
handler primitives (moka_embedded / hotjob / zhiye_beisen_cms / wintalent_sc),
stamp `source='hedge_funds_*'` so the /sites monitor + coverage panel can
distinguish them from 公募基金.

Companies wired this round (2026-05-11 subagent scout):
  - 幻方量化   — Moka embedded   (tenant=high-flyer / board=4605)
  - 九坤投资   — Moka embedded   (tenant=ubiquantrecruit / board=37031)
  - 高毅资产   — hotjob suite    (gyasset)
  - 衍复投资   — Beisen zhiye CMS

Skipped this round (see scout report deferred_reason in coverage_truth.yaml):
  - 明汯投资 (Feishu ATS, new engine family — backlog)
  - 灵均投资 (Moka-CNAME, needs verification — backlog)
  - 景林 / 淡水泉 / 礼仁 / 进化论 (relationship-driven hiring / no public ATS)
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_crawl_logger import company_crawl_log
from app.services.crawler_llm_enrich import enrich_jobs_parallel
from app.services.funds_crawler import (
    crawl_wintalent_sc_target,
    crawl_zhiye_beisen_cms_target,
)
from app.services.securities_crawler import (
    crawl_hotjob_target,
    crawl_moka_embedded_target,
    crawl_zhiye_target,
)


HEDGE_FUNDS_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "hedge_funds_campus.yaml"
)


_KNOWN = {"hotjob", "zhiye", "moka_embedded", "zhiye_beisen_cms", "wintalent_sc"}

_FAMILY_SOURCE_OVERRIDE: Dict[str, str] = {
    "hotjob":            "hedge_funds_hotjob",
    "zhiye":             "hedge_funds_zhiye",
    "moka_embedded":     "hedge_funds_moka_embedded",
    "zhiye_beisen_cms":  "hedge_funds_zhiye_beisen_cms",
    "wintalent_sc":      "hedge_funds_wintalent_sc",
}


def _hash_id(source: str, company: str, key: str) -> str:
    return hashlib.md5(f"{source}|{company}|{key}".encode("utf-8")).hexdigest()[:24]


def _load_targets() -> List[Dict[str, Any]]:
    payload = yaml.safe_load(HEDGE_FUNDS_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return payload.get("sites") or []


def _override_source(records: List[Dict[str, Any]], family: str) -> None:
    """Rewrite source + industry; rebuild job_id so it never collides with
    funds_/securities_ shadow records."""
    new_source = _FAMILY_SOURCE_OVERRIDE.get(family)
    if not new_source:
        return
    for rec in records:
        rec["source"] = new_source
        rec["company_type_industry"] = "私募 (Hedge Fund)"
        sc = rec.get("source_config_id") or ""
        m = re.search(r":([^:]+)$", sc)
        if m:
            rec["job_id"] = _hash_id(new_source, rec["company"], m.group(1))


def crawl_hedge_funds(
    db: Session,
    existing_jobs: Optional[Dict[str, Job]] = None,
    target_names: Optional[List[str]] = None,
    parent_log_id: Optional[int] = None,
) -> Tuple[int, int, Dict[str, int]]:
    """Run all hedge-fund targets. Returns (new_total, fetched_total, per_company)."""
    raw = _load_targets()
    if target_names:
        wanted = set(target_names)
        raw = [t for t in raw if t.get("name") in wanted]

    if existing_jobs is None:
        existing_jobs = {j.job_id: j for j in db.query(Job).all() if j.job_id}

    new_total = 0
    fetched_total = 0
    per_company: Dict[str, int] = {}

    for target in raw:
        family = target.get("ats_family")
        if family not in _KNOWN:
            # Silent skip: 'other' / unknown — never write a fake-success log row.
            continue

        source = _FAMILY_SOURCE_OVERRIDE.get(family) or "hedge_funds_official"
        company = target["name"]

        with company_crawl_log(
            db, source=source, company=company, parent_log_id=parent_log_id
        ) as log:
            try:
                if family == "hotjob":
                    crawled = crawl_hotjob_target(target)
                elif family == "zhiye":
                    crawled = crawl_zhiye_target(target)
                elif family == "moka_embedded":
                    crawled = crawl_moka_embedded_target(target)
                elif family == "zhiye_beisen_cms":
                    crawled = crawl_zhiye_beisen_cms_target(target)
                elif family == "wintalent_sc":
                    crawled = crawl_wintalent_sc_target(target)
                else:
                    crawled = []
            except Exception:
                # Re-raise: company_crawl_log will mark this run failed and
                # the outer loop in scheduler_service will isolate it.
                raise

            _override_source(crawled, family)

            company_new = 0
            new_jobs_for_enrich: list[tuple[Job, str]] = []
            for mapped in crawled:
                jid = mapped.get("job_id")
                if not jid:
                    continue
                exist = existing_jobs.get(jid)
                if exist is None:
                    job = Job(**mapped)
                    db.add(job)
                    existing_jobs[jid] = job
                    company_new += 1
                    duty_blob = (
                        str(mapped.get("job_duty") or "") + "\n"
                        + str(mapped.get("job_req") or "")
                    )
                    new_jobs_for_enrich.append((job, duty_blob))
                else:
                    for field in (
                        "company", "company_tags", "department", "job_title",
                        "location", "job_duty", "job_req", "publish_date",
                        "deadline", "detail_url", "scraped_at",
                    ):
                        val = mapped.get(field)
                        if val is not None and val != "":
                            setattr(exist, field, val)
            db.flush()

            log.fetched_count = len(crawled)
            log.new_count = company_new

            per_company[company] = company_new
            fetched_total += len(crawled)
            new_total += company_new

            # LLM enrichment best-effort (no-op if flag disabled in config)
            if new_jobs_for_enrich:
                try:
                    enrich_jobs_parallel(db, new_jobs_for_enrich)
                except Exception:
                    pass

    return new_total, fetched_total, per_company
