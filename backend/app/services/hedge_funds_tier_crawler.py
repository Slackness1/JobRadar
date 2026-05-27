"""Top 头部私募 (hedge funds) crawler — Phase 9 + Phase 11 海外 elite quants。

Mirrors funds_crawler.py's dispatcher pattern: load yaml, dispatch to existing
handler primitives (moka_embedded / hotjob / zhiye_beisen_cms / wintalent_sc),
stamp `source='hedge_funds_*'` so the /sites monitor + coverage panel can
distinguish them from 公募基金.

Companies wired:
  Phase 9 (2026-05-11):
    - 幻方量化   — Moka embedded
    - 九坤投资   — Moka embedded
    - 高毅资产   — hotjob suite (gyasset)
    - 衍复投资   — Beisen zhiye CMS
  2026-05-17:
    - 鸣石投资   — Beisen zhiye CMS
  Phase 11 (2026-05-23) — 海外 elite quants:
    - Point72    — Greenhouse boards API (~240 jobs global, ~30 Asia)
    - Millennium — Eightfold API (~230 jobs global)
    - Citadel    — wp-admin AJAX (custom WordPress, ~64 jobs, ~7 Asia 全是
                   Quant/SWE — 比例最高的 SAIF 量化梦想清单一家)

Skipped:
  - Two Sigma  — RSS feed only exposes 20 US jobs, 0 Asia visible (backlog)
  - 明汯 / 灵均 / 景林 / 淡水泉 — relationship-driven hiring,无公开 ATS
"""
from __future__ import annotations

import hashlib
import html as _html
import json as _json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from sqlalchemy.orm import Session

# curl_cffi for chrome TLS fingerprint impersonation — needed for Citadel
try:
    from curl_cffi import requests as curl_cffi_requests
except ImportError:
    curl_cffi_requests = None  # type: ignore[assignment]

from app.models import Job
from app.services.company_crawl_logger import company_crawl_log
from app.services.crawler_llm_enrich import enrich_jobs_parallel
from app.services.funds_crawler import (
    crawl_wintalent_sc_target,
    crawl_zhiye_beisen_cms_target,
)
from app.services.pe_vc_tier_crawler import _is_asia, _ua_headers, _parse_dt
from app.services.securities_crawler import (
    crawl_hotjob_target,
    crawl_moka_embedded_target,
    crawl_zhiye_target,
)


HEDGE_FUNDS_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "hedge_funds_campus.yaml"
)


_KNOWN = {
    "hotjob", "zhiye", "moka_embedded", "zhiye_beisen_cms", "wintalent_sc",
    "greenhouse", "eightfold", "citadel_wp_ajax",
    "self_html", "moka_v3",
}

_FAMILY_SOURCE_OVERRIDE: Dict[str, str] = {
    "hotjob":            "hedge_funds_hotjob",
    "zhiye":             "hedge_funds_zhiye",
    "moka_embedded":     "hedge_funds_moka_embedded",
    "zhiye_beisen_cms":  "hedge_funds_zhiye_beisen_cms",
    "wintalent_sc":      "hedge_funds_wintalent_sc",
    "greenhouse":        "hedge_funds_greenhouse",
    "eightfold":         "hedge_funds_eightfold",
    "citadel_wp_ajax":   "hedge_funds_citadel_wp",
    "self_html":         "hedge_funds_self_html",
    "moka_v3":           "hedge_funds_moka_v3",
}


def _fetch_moka_v3_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Moka 新版 campus-recruitment 系列 — init-data 嵌入 HTML, 不需 API.

    2026-05-27 实测淡水泉投资 (app.mokahr.com/campus-recruitment/springscapital
    /151579): HTML 含 <input id="init-data"> 嵌入完整 jobs JSON。format 比
    老 campus_apply 新,job 用 `title` 而非 `name`,location 是 list of dict
    带 `address`,department 是 nested dict。
    """
    import html as _html, json as _json
    company = target["name"]
    entry = target["entry_url"]
    try:
        r = requests.get(entry, headers={**_ua_headers(),"Referer":entry}, timeout=20)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    m = re.search(r'<input id="init-data" type="hidden" value="(.*?)">', r.text, re.S)
    if not m:
        return []
    try:
        payload = _json.loads(_html.unescape(m.group(1)))
    except Exception:
        return []
    jobs = payload.get("jobs") or []
    out: List[Dict[str, Any]] = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        jid = str(j.get("id") or "").strip()
        title = (j.get("title") or "").strip()
        if not jid or not title:
            continue
        if (j.get("status") or "").lower() not in ("open","online","publish","published",""):
            continue
        loc_obj = j.get("location") or {}
        location = (loc_obj.get("address") or loc_obj.get("country") or "未知").strip().replace("\n"," ")
        dept = ((j.get("department") or {}).get("name") or "").strip()
        zhineng = ((j.get("zhineng") or {}).get("name") or "").strip()
        stage = "campus" if any(k in title for k in ("校招","校园","实习","训练营","graduate","intern")) else "social"
        out.append({
            "job_id": _hash_id("hedge_funds_moka_v3", company, jid),
            "source": "hedge_funds_moka_v3",
            "company": company,
            "company_type_industry": "私募 (Hedge Fund) - 国内",
            "company_tags": "hedge_fund_domestic,moka_v3," + (dept or zhineng),
            "department": dept,
            "job_title": title,
            "location": location,
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": stage,
            "source_config_id": f"hedge_funds_moka_v3:{company}:{jid}",
            "publish_date": _parse_dt(j.get("publishedAt") or j.get("openedAt")),
            "deadline": _parse_dt(j.get("closedAt")),
            "detail_url": f"{entry.rstrip('/').split('?')[0]}#/positions/{jid}",
            "scraped_at": datetime.utcnow(),
        })
    return out


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


# ─── self_html handler (P1-quant5b, 2026-05-24) ────────────────────────────
#
# 用于自家服务端渲染 HTML / Next.js SSR 招聘页 — 不需要 Playwright,普通
# requests 就够拿到完整数据。yaml 字段:
#   ats_family: self_html
#   entry_url: <主 listing URL>
#   extra_paths: [<相对 path 1>, ...]   # 可选,会拼到 base_url 后面 (e.g. "/trainee/")
#   base_url: https://example.com        # 默认从 entry_url 派生
#   row_pattern: '<regex with named groups (?P<title>...) and optional (?P<path>...)>'
#   default_location: 上海               # 当 HTML 不含位置信息时的兜底
#
# Pattern 示例:
#   诚奇 cqfunds.com: 'href="(?P<path>/regular/\d+\.html)" title="(?P<title>[^"]+)"'
#   宽德 wizardquant Next.js: '"title":"(?P<title>[^"]+)"'
def _fetch_self_html_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    from urllib.parse import urlparse
    UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )
    company = target["name"]
    entry_url = target["entry_url"]
    parsed = urlparse(entry_url)
    base_url = target.get("base_url") or f"{parsed.scheme}://{parsed.netloc}"
    pattern = re.compile(target["row_pattern"], re.S)
    default_location = target.get("default_location") or "未知"

    urls_to_fetch = [entry_url]
    for extra in target.get("extra_paths") or []:
        url = extra if extra.startswith("http") else base_url.rstrip("/") + "/" + extra.lstrip("/")
        urls_to_fetch.append(url)

    records: List[Dict[str, Any]] = []
    seen_titles: set = set()
    for url in urls_to_fetch:
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Referer": base_url}, timeout=30)
            r.raise_for_status()
        except Exception:
            continue
        for m in pattern.finditer(r.text):
            d = m.groupdict()
            title = _html.unescape((d.get("title") or "").strip())
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            path = (d.get("path") or "").strip()
            if path and not path.startswith("http"):
                detail_url = base_url.rstrip("/") + "/" + path.lstrip("/")
            else:
                detail_url = path or url
            key = path or title
            records.append({
                "job_id": _hash_id("hedge_funds_self_html", company, key),
                "source": "hedge_funds_self_html",
                "company": company,
                "company_type_industry": "私募 (Hedge Fund)",
                "company_tags": "self_html",
                "department": company,
                "job_title": title,
                "location": default_location,
                "major_req": "",
                "job_req": "",
                "job_duty": "",
                "application_status": "待申请",
                "job_stage": "campus" if any(k in title for k in ("实习", "校招", "管培", "Intern", "Graduate")) else "social",
                "source_config_id": f"hedge_funds_self_html:{company}:{key}",
                "publish_date": None,
                "deadline": None,
                "detail_url": detail_url,
                "scraped_at": datetime.utcnow(),
            })
    return records


# ─── 海外 elite quants handlers (Phase 11, 2026-05-23) ─────────────────────

def _fetch_greenhouse_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Greenhouse boards API — `/v1/boards/<slug>/jobs`. 用于 Point72 等公开
    Greenhouse 板。post-hoc Asia 过滤,job_id 用 GH 自带 id。"""
    slug = target.get("greenhouse_slug") or target["name"].lower()
    company = target["name"]
    portal_url = target.get("portal_url") or f"https://boards.greenhouse.io/{slug}"
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            timeout=20, headers=_ua_headers(),
        )
    except Exception:
        return []
    if r.status_code != 200:
        return []
    data = r.json() or {}
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for j in (data.get("jobs") or []):
        jid = str(j.get("id") or "").strip()
        if not jid or jid in seen:
            continue
        title = str(j.get("title") or "").strip()
        if not title:
            continue
        loc = ((j.get("location") or {}).get("name") or "").strip()
        if not _is_asia(loc):
            continue
        seen.add(jid)
        out.append({
            "job_id": "",  # filled by _override_source
            "source": "hedge_funds_greenhouse",
            "company": company,
            "company_type_industry": "私募 (Hedge Fund) - 海外",
            "company_tags": "hedge_fund_overseas",
            "department": "",
            "job_title": title,
            "location": loc or "未知",
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": "campus" if any(k in title.lower() for k in ("intern", "graduate", "campus", "university", "phd")) else "social",
            "source_config_id": f"hedge_funds_api:greenhouse:{slug}:{jid}",
            "publish_date": _parse_dt(j.get("updated_at") or j.get("first_published")),
            "deadline": None,
            "detail_url": str(j.get("absolute_url") or f"{portal_url}/jobs/{jid}"),
            "scraped_at": datetime.utcnow(),
        })
    return out


def _fetch_eightfold_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Eightfold AI `/api/apply/v2/jobs` — 用于 Millennium 等 Eightfold 客户。

    Asia city loop 节流:每 location 拉一页 50 条,合并去重。
    """
    subdomain = target["eightfold_subdomain"]
    domain = target.get("eightfold_domain") or f"{subdomain}.com"
    company = target["name"]
    portal_url = target.get("portal_url") or f"https://{subdomain}.eightfold.ai/careers"
    queries = target.get("search_locations") or ["Hong Kong", "Singapore", "Tokyo", "Shanghai"]
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for loc_query in queries:
        try:
            r = requests.get(
                f"https://{subdomain}.eightfold.ai/api/apply/v2/jobs",
                params={"domain": domain, "start": 0, "num": 50, "location_name": loc_query, "query": ""},
                headers={**_ua_headers(), "Accept": "application/json"},
                timeout=20,
            )
        except Exception:
            continue
        if r.status_code != 200:
            continue
        try:
            data = r.json()
        except Exception:
            continue
        for p in (data.get("positions") or []):
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or p.get("position_id") or "").strip()
            if not pid or pid in seen:
                continue
            title = str(p.get("name") or "").strip()
            if not title:
                continue
            locs = p.get("locations") or []
            if isinstance(locs, list) and locs and isinstance(locs[0], dict):
                loc_text = ", ".join(l.get("name", "") for l in locs if l.get("name"))
            else:
                loc_text = str(p.get("location") or "")
            if not _is_asia(loc_text):
                continue
            seen.add(pid)
            duty_raw = str(p.get("job_description") or p.get("description") or "")
            duty_clean = re.sub(r"<[^>]+>", " ", duty_raw)
            duty_clean = re.sub(r"\s+", " ", duty_clean).strip()
            out.append({
                "job_id": "",  # filled by _override_source
                "source": "hedge_funds_eightfold",
                "company": company,
                "company_type_industry": "私募 (Hedge Fund) - 海外",
                "company_tags": "hedge_fund_overseas",
                "department": str(p.get("department") or ""),
                "job_title": title,
                "location": loc_text or "未知",
                "major_req": "",
                "job_req": "",
                "job_duty": duty_clean[:4000],
                "application_status": "待申请",
                "job_stage": "campus" if any(k in title.lower() for k in ("intern", "graduate", "campus", "university", "phd")) else "social",
                "source_config_id": f"hedge_funds_api:eightfold:{subdomain}:{pid}",
                "publish_date": _parse_dt(p.get("posted_date") or p.get("created_at")),
                "deadline": None,
                "detail_url": f"{portal_url.rstrip('/')}/job/{pid}",
                "scraped_at": datetime.utcnow(),
            })
    return out


_CITADEL_CARD_RE = re.compile(
    r'<a[^>]+href="(https?://[^"]+)"[^>]*data-position="([^"]+)"[^>]*>(.*?)</a>',
    re.S,
)
_CITADEL_LOC_RE = re.compile(
    r'careers-listing-card__location"\s*>\s*(?:&[a-z]+;)?\s*([^<\n\t]+?)\s*<', re.S,
)


def _fetch_citadel_wp_ajax(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Citadel — WordPress wp-admin AJAX action=careers_listing_filter。

    Pagination 实测 current_page/paged 参数被忽略,只能拿首 20 条。但 found_posts
    显示 ~64 total。**这 20 条里 ~7 是 Asia 高度 SAIF 相关**(Quant Research /
    Software Engineer Asia / Intern HK+SG)。pagination 真有需要将来再逆向。

    curl_cffi chrome120 必需,plain requests 触发 403。
    """
    if curl_cffi_requests is None:
        return []
    company = target["name"]
    portal_url = target.get("portal_url") or "https://www.citadel.com/careers/"
    try:
        r = curl_cffi_requests.get(
            "https://www.citadel.com/wp-admin/admin-ajax.php",
            params={"action": "careers_listing_filter", "per_page": 20, "current_page": 1},
            impersonate="chrome120", timeout=15,
        )
    except Exception:
        return []
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    content_html = data.get("content") or ""
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for href, pos, body in _CITADEL_CARD_RE.findall(content_html):
        title = _html.unescape(pos).replace("–", "-").strip()
        if not title or href in seen:
            continue
        # slug = trailing path segment as stable id
        slug = href.rstrip("/").rsplit("/", 1)[-1]
        loc_m = _CITADEL_LOC_RE.search(body)
        loc = loc_m.group(1).strip() if loc_m else ""
        if not _is_asia(loc):
            continue
        seen.add(href)
        out.append({
            "job_id": "",  # filled by _override_source
            "source": "hedge_funds_citadel_wp",
            "company": company,
            "company_type_industry": "私募 (Hedge Fund) - 海外",
            "company_tags": "hedge_fund_overseas",
            "department": "",
            "job_title": title,
            "location": loc or "未知",
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": "campus" if any(k in title.lower() for k in ("intern", "graduate", "campus", "university", "phd")) else "social",
            "source_config_id": f"hedge_funds_api:citadel:{slug}",
            "publish_date": None,
            "deadline": None,
            "detail_url": href,
            "scraped_at": datetime.utcnow(),
        })
    return out


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
                elif family == "greenhouse":
                    crawled = _fetch_greenhouse_target(target)
                elif family == "eightfold":
                    crawled = _fetch_eightfold_target(target)
                elif family == "citadel_wp_ajax":
                    crawled = _fetch_citadel_wp_ajax(target)
                elif family == "self_html":
                    crawled = _fetch_self_html_target(target)
                elif family == "moka_v3":
                    crawled = _fetch_moka_v3_target(target)
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
