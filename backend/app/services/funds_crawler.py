"""Top-25 公募基金 daily crawler — Phase 6 task #1.

Reuses securities_crawler primitives (hotjob / zhiye / moka_embedded) and adds
ONE new helper for Beisen-CMS-Portal-style zhiye sites where the campus list is
rendered as a simple <table> of <a href="/zpdetail/<id>">title</a>.
"""
from __future__ import annotations

import hashlib
import html
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_crawl_logger import company_crawl_log
from app.services.crawler_llm_enrich import enrich_jobs_parallel
from app.services.scorer import score_all_jobs  # noqa: F401  (reserved)
from app.services.securities_crawler import (
    REQUEST_PROXIES,
    crawl_hotjob_target,
    crawl_moka_embedded_target,
    crawl_zhiye_target,
)

FUNDS_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "funds_campus.yaml"


def _load_targets(config_path: Path = FUNDS_CONFIG_PATH) -> List[Dict[str, Any]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return payload.get("sites") or []


# ---- Beisen-CMS zhiye (table-row HTML) -------------------------------------

_BEISEN_ROW_RE = re.compile(
    r'<a title="([^"]+)" href="(/zpdetail/\d+)"[^>]*>.*?</a>'
    r'.*?<td title="([^"]*)">[^<]*</td>'
    r'.*?<td title="([^"]*)">[^<]*</td>'
    r'.*?<td>([^<]+)</td>',
    re.S,
)

_TOTAL_PAGES_RE = re.compile(r"当前第\d+/(\d+)页")


def _parse_dt(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _hash_id(source: str, company: str, key: str) -> str:
    return hashlib.md5(f"{source}|{company}|{key}".encode("utf-8")).hexdigest()[:24]


def _infer_stage(title: str, ptype: str) -> str:
    blob = f"{title} {ptype}"
    if "实习" in blob:
        return "internship"
    if any(k in blob for k in ("校招", "校园", "应届", "26届", "27届", "26应届", "27应届", "campus")):
        return "campus"
    return "other"


def crawl_zhiye_beisen_cms_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    entry_url = target["entry_url"]
    max_pages = int(target.get("max_pages") or 10)
    base = re.match(r"^(https?://[^/]+)", entry_url).group(1)
    records: List[Dict[str, Any]] = []
    seen: set = set()
    total_pages: Optional[int] = None
    for page_index in range(1, max_pages + 1):
        if total_pages is not None and page_index > total_pages:
            break
        page_url = entry_url if page_index == 1 else f"{entry_url}?PageIndex={page_index}"
        resp = requests.get(
            page_url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": entry_url},
            proxies=REQUEST_PROXIES,
            timeout=30,
        )
        resp.raise_for_status()
        page_html = resp.text
        if total_pages is None:
            tm = _TOTAL_PAGES_RE.search(page_html)
            if tm:
                total_pages = int(tm.group(1))
        rows = _BEISEN_ROW_RE.findall(page_html)
        if not rows:
            break
        added_this_page = 0
        for raw_title, detail_path, ptype, location, pub in rows:
            key_match = re.search(r"/zpdetail/(\d+)", detail_path)
            job_key = key_match.group(1) if key_match else detail_path
            if job_key in seen:
                continue
            seen.add(job_key)
            title = html.unescape(raw_title)
            location = html.unescape(location)
            ptype = html.unescape(ptype)
            detail_url = f"{base}{detail_path}"
            records.append({
                "job_id": _hash_id("funds_zhiye_beisen_cms", target["name"], job_key),
                "source": "funds_zhiye_beisen_cms",
                "company": target["name"],
                "company_type_industry": "公募基金",
                "company_tags": ptype or "校园招聘",
                "department": ptype or target["name"],
                "job_title": title,
                "location": location or "未知",
                "major_req": "",
                "job_req": "",
                "job_duty": "",
                "application_status": "待申请",
                "job_stage": _infer_stage(title, ptype),
                "source_config_id": f"funds_api:{target['name']}:{job_key}",
                "publish_date": _parse_dt(pub),
                "deadline": None,
                "detail_url": detail_url,
                "scraped_at": datetime.utcnow(),
            })
            added_this_page += 1
        if added_this_page == 0:
            break
        time.sleep(0.4)
    return records


# ---- Tagging helpers for source sub-strings --------------------------------

_KNOWN = {"hotjob", "zhiye", "moka_embedded", "zhiye_beisen_cms"}

_FAMILY_SOURCE_OVERRIDE: Dict[str, str] = {
    "hotjob":            "funds_hotjob",
    "zhiye":             "funds_zhiye",
    "moka_embedded":     "funds_moka_embedded",
    "zhiye_beisen_cms":  "funds_zhiye_beisen_cms",
}


def _override_source(records: List[Dict[str, Any]], family: str) -> None:
    """Securities-crawler primitives stamp source='securities_*'; rewrite for funds."""
    new_source = _FAMILY_SOURCE_OVERRIDE.get(family)
    if not new_source:
        return
    for rec in records:
        rec["source"] = new_source
        rec["company_type_industry"] = "公募基金"
        # Rebuild job_id with new source so it does not collide with securities ids
        # (different industry, same job_key would otherwise produce same hash if a
        # company name happened to overlap — unlikely but cheap to harden).
        sc = rec.get("source_config_id") or ""
        # Prefer rebuilding from job_key portion of source_config_id
        # ('securities_api:name:key' or already 'funds_api:...').
        m = re.search(r":([^:]+)$", sc)
        if m:
            rec["job_id"] = _hash_id(new_source, rec["company"], m.group(1))


def crawl_configured_funds_targets(
    target_names: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    targets = _load_targets()
    if target_names:
        wanted = set(target_names)
        targets = [t for t in targets if t.get("name") in wanted]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for target in targets:
        family = target.get("ats_family")
        if family not in _KNOWN:
            continue  # 'other' / unknown → skip silently (no fake-green log)
        if family == "hotjob":
            crawled = crawl_hotjob_target(target)
        elif family == "zhiye":
            crawled = crawl_zhiye_target(target)
        elif family == "moka_embedded":
            crawled = crawl_moka_embedded_target(target)
        elif family == "zhiye_beisen_cms":
            crawled = crawl_zhiye_beisen_cms_target(target)
        else:
            crawled = []
        _override_source(crawled, family)
        bucket = grouped.setdefault(target["name"], [])
        seen = {r.get("job_id") for r in bucket}
        for rec in crawled:
            jid = rec.get("job_id")
            if jid and jid in seen:
                continue
            if jid:
                seen.add(jid)
            bucket.append(rec)
    return grouped


def run_configured_funds_crawl(
    db: Session,
    existing_jobs: Dict[str, Job],
    target_names: Optional[List[str]] = None,
    parent_log_id: Optional[int] = None,
) -> Tuple[int, int, Dict[str, int]]:
    raw = _load_targets()
    if target_names:
        wanted = set(target_names)
        raw = [t for t in raw if t.get("name") in wanted]
    company_source: Dict[str, str] = {
        t["name"]: _FAMILY_SOURCE_OVERRIDE.get(t.get("ats_family", ""), "funds_configured")
        for t in raw
    }

    grouped = crawl_configured_funds_targets(target_names=target_names)
    new_total = 0
    fetched_total = 0
    per_company: Dict[str, int] = {}

    for company, records in grouped.items():
        source = company_source.get(company, "funds_configured")
        with company_crawl_log(db, source=source, company=company, parent_log_id=parent_log_id) as log:
            per_company[company] = len(records)
            fetched_total += len(records)
            new_jobs_for_enrich: list[tuple[Job, str]] = []
            company_new = 0
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
                    new_jobs_for_enrich.append(
                        (job, str(mapped.get("job_duty") or "") + "\n" + str(mapped.get("job_req") or ""))
                    )
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
            log.fetched_count = len(records)
            log.new_count = company_new
            new_total += company_new
            try:
                if new_jobs_for_enrich:
                    enrich_jobs_parallel(db, new_jobs_for_enrich)
            except Exception:
                pass
    db.commit()
    return new_total, fetched_total, per_company
