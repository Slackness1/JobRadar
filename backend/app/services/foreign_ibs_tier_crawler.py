"""外资投行 (Foreign IBs) crawler — Phase 10.

Workday CXS pagination strategy:
  Citi alone has 2000 global jobs at limit=20/page = 100 pages = >200s. To
  stay within scheduler budget, we query Workday with `searchText` filters
  (server-side) for a small set of Asia keywords, paginate within each, then
  dedupe by job_id and post-filter with `_is_asia` to remove noise. Expected
  ~80 requests/company, ~40s.

Companies wired (Workday CXS verified 200):
  - Citi          (citi.wd5.myworkdayjobs.com/wday/cxs/citi/2/jobs)
  - Morgan Stanley (ms.wd5.myworkdayjobs.com/wday/cxs/ms/External/jobs)

Skipped — all return Workday 422 with our minimal payload (endpoint exists
but rejects request; likely needs per-tenant facets/session prep):
  - Goldman Sachs / JPM / UBS / HSBC / BofA / BNP / Standard Chartered /
    Nomura / Daiwa CM
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_crawl_logger import company_crawl_log
from app.services.crawler_llm_enrich import enrich_jobs_parallel
from app.services.pe_vc_tier_crawler import _is_asia, _ua_headers, _parse_dt


# Default Asia search keywords — covers most of the global IBs' regional hubs.
# Override per-target via yaml `search_queries` if needed.
DEFAULT_ASIA_QUERIES = ["China", "Hong Kong", "Singapore", "Tokyo", "Mumbai"]


FOREIGN_IBS_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "foreign_ibs_campus.yaml"
)


def _hash_id(source: str, company: str, key: str) -> str:
    return hashlib.md5(f"{source}|{company}|{key}".encode("utf-8")).hexdigest()[:24]


def _load_targets() -> List[Dict[str, Any]]:
    payload = yaml.safe_load(FOREIGN_IBS_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return payload.get("sites") or []


def _fetch_workday_filtered(
    company: str,
    endpoint: str,
    portal_url: str,
    queries: List[str],
    page_size: int = 20,
    max_pages_per_query: int = 8,
    source: str = "foreign_ibs_official",
    industry: str = "外资投行",
    tags: str = "foreign_ib",
) -> List[Dict[str, Any]]:
    """Pagination with server-side searchText filter — much faster than
    crawling the entire global jobs board."""
    base_origin = endpoint.split("/wday/")[0]
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    for query in queries:
        for p in range(max_pages_per_query):
            body = {
                "limit": page_size,
                "offset": p * page_size,
                "searchText": query,
                "appliedFacets": {},
            }
            try:
                r = requests.post(
                    endpoint,
                    json=body,
                    headers={
                        **_ua_headers(),
                        "Content-Type": "application/json",
                        "Origin": base_origin,
                        "Referer": f"{base_origin}/en-US/",
                    },
                    timeout=20,
                )
            except Exception:
                break
            if r.status_code != 200:
                break
            try:
                data = r.json()
            except Exception:
                break
            posts = data.get("jobPostings") or []
            if not posts:
                break
            for it in posts:
                location = str(it.get("locationsText") or "").strip()
                # Post-hoc Asia filter (searchText is loose — matches title too)
                if not _is_asia(location):
                    continue
                ext_path = str(it.get("externalPath") or "").strip()
                jid = ext_path.rsplit("/", 1)[-1] if ext_path else ""
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                title = str(it.get("title") or "").strip()
                if not title:
                    continue
                detail = (
                    f"{base_origin}/en-US{ext_path}"
                    if ext_path.startswith("/") else portal_url
                )
                out.append({
                    "job_id": _hash_id(source, company, jid),
                    "source": source,
                    "company": company,
                    "company_type_industry": industry,
                    "company_tags": tags,
                    "department": "",
                    "job_title": title,
                    "location": location or "未知",
                    "major_req": "",
                    "job_req": "",
                    "job_duty": "",
                    "application_status": "待申请",
                    "job_stage": "social",
                    "source_config_id": f"{source}:workday:{company}",
                    "publish_date": _parse_dt(it.get("postedOn")),
                    "deadline": None,
                    "detail_url": detail,
                    "scraped_at": datetime.utcnow(),
                })
            total = int(data.get("total") or 0)
            if total and (p + 1) * page_size >= total:
                break

    return out


def _fetch_goldman_graphql(
    company: str,
    endpoint: str,
    portal_url: str,
    queries: List[str],
    page_size: int = 20,
    source: str = "foreign_ibs_official",
    industry: str = "外资投行",
    tags: str = "foreign_ib",
) -> List[Dict[str, Any]]:
    """高盛 api-higher.gs.com GraphQL endpoint — 公开 schema 无 auth。

    每个 query 关键词(Hong Kong/Singapore/Tokyo...)做一次 search,合并去重。
    """
    GQL = """
    query Search($q: RoleSearchQueryInput!) {
      roleSearch(searchQueryInput: $q) {
        totalCount
        items {
          roleId jobTitle jobFunction division skillset
          shortDescription descriptionHtml lastPostedDate
          locations { city country state }
        }
        page { pageSize pageNumber hasNext }
      }
    }
    """
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for q in queries:
        page = 0
        while page < 10:  # safety cap; rarely > 5 pages per city
            body = {
                "query": GQL,
                "variables": {
                    "q": {
                        "page": {"pageSize": page_size, "pageNumber": page},
                        "experiences": ["EARLY_CAREER", "PROFESSIONAL"],
                        "searchTerm": q,
                    }
                },
            }
            try:
                r = requests.post(
                    endpoint, json=body, timeout=20,
                    headers={
                        **_ua_headers(),
                        "Content-Type": "application/json",
                        "Origin": "https://higher.gs.com",
                        "Referer": "https://higher.gs.com/roles",
                    },
                )
            except Exception:
                break
            if r.status_code != 200:
                break
            try:
                data = r.json()
            except Exception:
                break
            res = (data.get("data") or {}).get("roleSearch") or {}
            items = res.get("items") or []
            for it in items:
                rid = str(it.get("roleId") or "").strip()
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                title = str(it.get("jobTitle") or "").strip()
                if not title:
                    continue
                loc_objs = it.get("locations") or []
                locs = [
                    "/".join(filter(None, [
                        (l.get("city") or "").strip(),
                        (l.get("state") or "").strip(),
                        (l.get("country") or "").strip(),
                    ]))
                    for l in loc_objs if isinstance(l, dict)
                ]
                location_text = ", ".join(filter(None, locs)) or "未知"
                # Asia filter (post-hoc): keep only if any location word matches Asia keywords
                if not _is_asia(location_text):
                    continue
                division = str(it.get("division") or "").strip()
                jf = str(it.get("jobFunction") or "").strip()
                department = division or jf
                duty_raw = str(it.get("descriptionHtml") or it.get("shortDescription") or "")
                import re as _re
                duty_clean = _re.sub(r"<[^>]+>", " ", duty_raw)
                duty_clean = _re.sub(r"&nbsp;", " ", duty_clean)
                duty_clean = _re.sub(r"\s+", " ", duty_clean).strip()
                out.append({
                    "job_id": _hash_id(source, company, rid),
                    "source": source,
                    "company": company,
                    "company_type_industry": industry,
                    "company_tags": tags,
                    "department": department,
                    "job_title": title,
                    "location": location_text,
                    "major_req": str(it.get("skillset") or ""),
                    "job_req": "",
                    "job_duty": duty_clean[:4000],
                    "application_status": "待申请",
                    "job_stage": "campus" if "EARLY_CAREER" in title.upper() else "social",
                    "source_config_id": f"{source}:goldman_gql:{company}",
                    "publish_date": _parse_dt(it.get("lastPostedDate")),
                    "deadline": None,
                    "detail_url": f"{portal_url.rstrip('/')}/role/{rid}" if portal_url else "",
                    "scraped_at": datetime.utcnow(),
                })
            pg = res.get("page") or {}
            if not pg.get("hasNext"):
                break
            page += 1
    return out


def crawl_foreign_ibs(
    db: Session,
    existing_jobs: Optional[Dict[str, Job]] = None,
    target_names: Optional[List[str]] = None,
    parent_log_id: Optional[int] = None,
) -> Tuple[int, int, Dict[str, int]]:
    """Run all foreign IB Workday targets. Returns (new_total, fetched_total, per_company)."""
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
        handler = entry.get("handler", "workday")
        if handler not in ("workday", "goldman_graphql"):
            continue  # only supported handlers

        company = entry["name"]
        queries = entry.get("search_queries") or DEFAULT_ASIA_QUERIES
        page_size = int(entry.get("page_size", 20))
        max_pages = int(entry.get("max_pages_per_query", 8))

        with company_crawl_log(
            db, source="foreign_ibs_official",
            company=company, parent_log_id=parent_log_id,
        ) as log:
            if handler == "workday":
                records = _fetch_workday_filtered(
                    company=company,
                    endpoint=entry["endpoint"],
                    portal_url=entry.get("portal_url") or entry["endpoint"],
                    queries=queries,
                    page_size=page_size,
                    max_pages_per_query=max_pages,
                )
            elif handler == "goldman_graphql":
                records = _fetch_goldman_graphql(
                    company=company,
                    endpoint=entry["endpoint"],
                    portal_url=entry.get("portal_url", ""),
                    queries=queries,
                    page_size=page_size,
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
