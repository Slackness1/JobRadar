"""外资投行 (Foreign IBs) crawler — Phase 10.

Workday CXS pagination strategy:
  Citi alone has 2000 global jobs at limit=20/page = 100 pages = >200s. To
  stay within scheduler budget, we query Workday with `searchText` filters
  (server-side) for a small set of Asia keywords, paginate within each, then
  dedupe by job_id and post-filter with `_is_asia` to remove noise. Expected
  ~80 requests/company, ~40s.

Companies wired:
  - Citi / Morgan Stanley (plain requests OK)
  - Goldman Sachs (自建 GraphQL `_fetch_goldman_graphql`)
  - UBS (Oracle Taleo SPA `_fetch_ubs_taleo_spa`)
  - Barclays (Workday CXS + curl_cffi chrome120; plain requests→406)
  - Deutsche Bank (Workday wd3/DBWebsite + curl_cffi chrome120; ~92 Asia岗)
  - **JP Morgan** (Oracle Cloud CE REST `_fetch_oracle_ce`; 2026-05-26 解锁,
    原 jpmc.wd5 Workday endpoint 是错的,实际走 jpmc.fa.oraclecloud.com)

Application-layer anti-bot (Workday tenant-level WorkdayDetect+CSRF+session),
**not** ASN/IP block — Decodo residential 实测 422,需 Multilogin 类真指纹浏览器
+ 行为脚本才能解,ROI 偏低,继续 backlog:
  - BofA / BNP / Standard Chartered / Nomura / Daiwa CM / MUFG / Mizuho / Jefferies

True backlog (无明确公开 ATS 入口):
  - HSBC: mycareer.hsbc.com 实测确认是 HSBC Poland 专属 GSC portal,Asia
    portal 公开 entry 不明,backlog
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from sqlalchemy.orm import Session

# curl_cffi for chrome TLS fingerprint impersonation — D-10 备选引擎
try:
    from curl_cffi import requests as curl_cffi_requests
except ImportError:
    curl_cffi_requests = None  # type: ignore[assignment]

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
    tls_impersonate: str = "",
) -> List[Dict[str, Any]]:
    """Pagination with server-side searchText filter — much faster than
    crawling the entire global jobs board.

    `tls_impersonate`: 当 plain requests 触发 406 (TLS fingerprint 被 CDN/WAF
    挡掉) 时,传入 'chrome120' 等让 curl_cffi 仿真 Chrome TLS handshake。
    Barclays 实测必需,Citi/MS 不需要。
    """
    base_origin = endpoint.split("/wday/")[0]
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    use_curl_cffi = bool(tls_impersonate) and curl_cffi_requests is not None

    for query in queries:
        for p in range(max_pages_per_query):
            body = {
                "limit": page_size,
                "offset": p * page_size,
                "searchText": query,
                "appliedFacets": {},
            }
            headers = {
                **_ua_headers(),
                "Content-Type": "application/json",
                "Origin": base_origin,
                "Referer": f"{base_origin}/en-US/",
            }
            try:
                if use_curl_cffi:
                    r = curl_cffi_requests.post(
                        endpoint, json=body, headers=headers,
                        impersonate=tls_impersonate, timeout=20,
                    )
                else:
                    r = requests.post(endpoint, json=body, headers=headers, timeout=20)
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


def _fetch_ubs_taleo_spa(
    company: str,
    portal_url: str,
    site_ids: List[int],
    partner_id: int = 25008,
    link_ids: Optional[List[int]] = None,
    source: str = "foreign_ibs_official",
    industry: str = "外资投行",
    tags: str = "foreign_ib",
) -> List[Dict[str, Any]]:
    """UBS Oracle Taleo TGnewUI — SPA JS-rendered jobs。

    Taleo 不暴露干净 JSON API,initial GET HTML 也没 jobs(SPA hydrate)。用
    Playwright headless 渲染后从 DOM 抽 a[href*=JobDetail] 节点。每个 site
    (5012=Professionals, 5131=Students) 单独抓一次,合并去重。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    import os
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    link_ids = link_ids or [15231]

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                proxy={"server": proxy} if proxy else None,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            try:
                for site_id, link_id in zip(site_ids, link_ids):
                    url = (
                        f"https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad"
                        f"?partnerid={partner_id}&siteid={site_id}"
                        f"&PageType=searchResults&SearchType=linkquery&LinkID={link_id}"
                    )
                    ctx = browser.new_context(user_agent=UA, locale="en-US",
                                              viewport={"width": 1440, "height": 900})
                    page = ctx.new_page()
                    try:
                        page.goto(url, wait_until="networkidle", timeout=45000)
                        page.wait_for_timeout(6000)
                        items = page.eval_on_selector_all(
                            'a[href*="PageType=JobDetails"]',
                            """(els) => els.map(e => {
                                // Climb to the row container that has all 4 fields rendered.
                                let row = e;
                                for (let i = 0; i < 8 && row.parentElement; i++) {
                                    row = row.parentElement;
                                    const txt = (row.innerText || '');
                                    if (txt.length > 60 && txt.split('\\n').length >= 3) break;
                                }
                                return {
                                    href: e.href,
                                    text: (e.innerText || '').trim(),
                                    row_text: (row?.innerText || '').substring(0, 400),
                                };
                            })""",
                        ) or []
                    except Exception:
                        items = []
                    finally:
                        ctx.close()
                    import re as _re
                    for it in items:
                        href = it.get("href") or ""
                        title = (it.get("text") or "").strip()
                        if not href or not title:
                            continue
                        # 提 reqId from URL
                        rid_m = _re.search(r"reqId=(\d+)", href)
                        if not rid_m:
                            rid_m = _re.search(r"(?:JobId|jobId|jobid|reqid)=(\d+)", href)
                        rid = rid_m.group(1) if rid_m else href
                        if rid in seen:
                            continue
                        seen.add(rid)
                        # row_text 结构: Title / Country / Function / Division / Description
                        row_text = it.get("row_text") or ""
                        lines = [ln.strip() for ln in row_text.split("\n") if ln.strip()]
                        location = lines[1] if len(lines) >= 2 else "未知"
                        function = lines[2] if len(lines) >= 3 else ""
                        division = lines[3] if len(lines) >= 4 else ""
                        # Asia 过滤
                        if not _is_asia(location):
                            continue
                        out.append({
                            "job_id": _hash_id(source, company, rid),
                            "source": source,
                            "company": company,
                            "company_type_industry": industry,
                            "company_tags": tags,
                            "department": division or function,
                            "job_title": title,
                            "location": location,
                            "major_req": "",
                            "job_req": "",
                            "job_duty": "",
                            "application_status": "待申请",
                            "job_stage": "campus" if site_id == 5131 else "social",
                            "source_config_id": f"{source}:ubs_taleo:{company}:{rid}",
                            "publish_date": None,
                            "deadline": None,
                            "detail_url": href,
                            "scraped_at": datetime.utcnow(),
                        })
            finally:
                browser.close()
    except Exception:
        return []
    return out


def _fetch_hsbc_eightfold(
    company: str,
    portal_url: str,
    queries: List[str],
    page_size: int = 50,
    max_pages_per_query: int = 6,
    source: str = "foreign_ibs_official",
    industry: str = "外资投行",
    tags: str = "foreign_ib",
) -> List[Dict[str, Any]]:
    """HSBC Asia portal — `portal.careers.hsbc.com` 后台是 Eightfold AI。

    2026-05-27 实测 (替换之前误判 mycareer.hsbc.com=Poland 的结论):
    /api/apply/v2/jobs?domain=hsbc.com&location=<city>&num=50 直接 VPS curl_cffi
    1s 返 200。Asia 总量 (single-keyword totals):
      Mainland China 497 / HK 239 / Shanghai 99 / Taipei 87 / Bangalore 56 /
      Singapore 49 / Beijing 45 / Mumbai 45 / Tokyo 16
    """
    import hashlib
    import re as _re
    base = portal_url.rstrip("/").rsplit("/careers", 1)[0] if "/careers" in portal_url else portal_url.rstrip("/")
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for q in queries:
        for page in range(max_pages_per_query):
            try:
                r = requests.get(
                    f"{base}/api/apply/v2/jobs",
                    params={
                        "domain": "hsbc.com",
                        "location": q,
                        "start": page * page_size,
                        "num": page_size,
                        "pid": "",
                    },
                    headers={**_ua_headers(), "Accept": "application/json",
                             "Referer": f"{base}/careers"},
                    timeout=25,
                )
            except Exception:
                break
            if r.status_code != 200:
                break
            try:
                jd = r.json()
            except Exception:
                break
            positions = jd.get("positions") or []
            if not positions:
                break
            total = jd.get("count") or 0
            for p in positions:
                pid = str(p.get("id") or "").strip()
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                title = (p.get("name") or "").strip()
                if not title:
                    continue
                locs = p.get("locations") or []
                if isinstance(locs, list) and locs and isinstance(locs[0], dict):
                    loc_text = ", ".join(l.get("name", "") for l in locs if l.get("name"))
                else:
                    loc_text = str(p.get("location") or "")
                if not _is_asia(loc_text):
                    continue
                duty_raw = str(p.get("job_description") or p.get("description") or "")
                duty_clean = _re.sub(r"<[^>]+>", " ", duty_raw)
                duty_clean = _re.sub(r"\s+", " ", duty_clean).strip()[:4000]
                out.append({
                    "job_id": _hash_id(source, company, pid),
                    "source": source,
                    "company": company,
                    "company_type_industry": industry,
                    "company_tags": tags,
                    "department": str(p.get("department") or ""),
                    "job_title": title,
                    "location": loc_text or "未知",
                    "major_req": "",
                    "job_req": "",
                    "job_duty": duty_clean,
                    "application_status": "待申请",
                    "job_stage": "campus" if any(k in title.lower() for k in ("intern", "graduate", "campus", "trainee", "associate program")) else "social",
                    "source_config_id": f"{source}:hsbc_eightfold:{company}:{pid}",
                    "publish_date": _parse_dt(p.get("posted_date") or p.get("created_at")),
                    "deadline": None,
                    "detail_url": f"{base}/careers/job/{pid}",
                    "scraped_at": datetime.utcnow(),
                })
            if (page + 1) * page_size >= total:
                break
            if len(positions) < page_size:
                break
    return out


def _fetch_blackrock_sitemap(
    company: str,
    portal_url: str = "https://careers.blackrock.com",
    sitemap_path: str = "/sitemap.xml",
    asia_cities: Optional[List[str]] = None,
    source: str = "foreign_ibs_official",
    industry: str = "资管 (Asset Manager)",
    tags: str = "foreign_am,blackrock",
) -> List[Dict[str, Any]]:
    """BlackRock — careers.blackrock.com SilkRoad TalentBrew.

    2026-05-28 实测: /search-jobs/results JSON API 返 `{filters,results,hasJobs,
    hasContent}` 但需要 session-warmed cookies 才有数据 (results 是 HTML 串)。
    替代方案: sitemap.xml 公开列出全 502 个 jobs,URL pattern
    `/job/<city-slug>/<title-slug>/45831/<job_id>`。直接 parse sitemap 拿 city +
    job_id + title,无需 session。

    Asia 总量 (sitemap.xml 实测): SAIF-core 55 (HK/SG/Shanghai/Tokyo/Taipei) +
    India ops 100+。含 SAIF MF 直击岗: Shanghai Equity & Multi Asset Researcher
    / HK Fundamental Equities Research VP / Tokyo Equity Research Head /
    2028 Full Time Analyst Program APAC。
    """
    import re as _re
    if asia_cities is None:
        asia_cities = [
            "hong-kong", "singapore", "shanghai", "beijing",
            "tokyo", "taipei", "seoul",
            "mumbai", "bangalore", "gurgaon", "hyderabad", "pune", "chennai",
        ]
    try:
        r = requests.get(
            f"{portal_url.rstrip('/')}{sitemap_path}",
            headers=_ua_headers(), timeout=30,
        )
    except Exception:
        return []
    if r.status_code != 200:
        return []
    locs = _re.findall(r"<loc>([^<]+)</loc>", r.text)
    job_url_re = _re.compile(
        r"^https://careers\.blackrock\.com/job/([^/]+)/([^/]+)/(\d+)/(\d+)$"
    )
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for url in locs:
        m = job_url_re.match(url)
        if not m:
            continue
        city_slug, title_slug, _category_id, job_id = m.groups()
        if city_slug not in asia_cities:
            continue
        if job_id in seen:
            continue
        seen.add(job_id)
        title = title_slug.replace("-", " ").title()
        city_label = city_slug.replace("-", " ").title()
        stage = "campus" if any(k in title.lower() for k in (
            "analyst program", "intern", "graduate", "campus", "trainee",
            "rotational", "futurefocus",
        )) else "social"
        out.append({
            "job_id": _hash_id(source, company, job_id),
            "source": source,
            "company": company,
            "company_type_industry": industry,
            "company_tags": tags,
            "department": "",
            "job_title": title,
            "location": city_label,
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": stage,
            "source_config_id": f"{source}:blackrock_sitemap:{job_id}",
            "publish_date": None,
            "deadline": None,
            "detail_url": url,
            "scraped_at": datetime.utcnow(),
        })
    return out


def _fetch_oracle_ce(
    company: str,
    portal_url: str,
    site_number: str,
    queries: List[str],
    page_size: int = 25,
    max_pages_per_query: int = 8,
    source: str = "foreign_ibs_official",
    industry: str = "外资投行",
    tags: str = "foreign_ib",
) -> List[Dict[str, Any]]:
    """Oracle Cloud Candidate Experience REST — `recruitingCEJobRequisitions`.

    2026-05-26 实测 JPM (jpmc.fa.oraclecloud.com siteNumber=CX_1001):VPS plain
    requests 1.1s 返 200,无 IP 限制,server-side keyword filter 正常工作。
    pagination 通过 offset 步进,每页固定 25 条(API 上限)。
    """
    import re as _re
    from urllib.parse import quote
    base = portal_url.rstrip("/")
    if "fa.oraclecloud.com" not in base:
        # entry_url 是 SPA 入口,推导出 hcmRestApi 根
        m = _re.match(r"^(https?://[^/]+)", portal_url)
        if not m:
            return []
        base = m.group(1)
    api_root = base.split("/hcmUI")[0] if "/hcmUI" in base else base
    api_url = f"{api_root}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for q in queries:
        for page in range(max_pages_per_query):
            offset = page * page_size
            url = (
                f"{api_url}?finder=findReqs;siteNumber={site_number}"
                f",keyword={quote(q)}&limit={page_size}&offset={offset}"
                f"&expand=requisitionList&onlyData=true"
            )
            try:
                r = requests.get(url, timeout=25, headers={
                    **_ua_headers(),
                    "Accept": "application/json",
                })
            except Exception:
                break
            if r.status_code != 200:
                break
            try:
                jd = r.json()
            except Exception:
                break
            meta = (jd.get("items") or [{}])[0]
            req_list = meta.get("requisitionList") or []
            if not req_list:
                break
            total = meta.get("TotalJobsCount") or 0
            for it in req_list:
                rid = str(it.get("Id") or it.get("ReqId") or "").strip()
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                title = (it.get("Title") or "").strip()
                if not title:
                    continue
                location = (it.get("PrimaryLocation") or "").strip() or "未知"
                # Asia 过滤,与其它 handler 一致
                if not _is_asia(location):
                    continue
                department = (it.get("Department") or it.get("JobFamily") or "").strip()
                duty_raw = it.get("ExternalDescriptionStr") or it.get("ShortDescription") or ""
                duty_clean = _re.sub(r"<[^>]+>", " ", str(duty_raw))
                duty_clean = _re.sub(r"&nbsp;", " ", duty_clean)
                duty_clean = _re.sub(r"\s+", " ", duty_clean).strip()[:4000]
                qualifications_raw = it.get("ExternalQualificationsStr") or ""
                req_clean = _re.sub(r"<[^>]+>", " ", str(qualifications_raw))
                req_clean = _re.sub(r"\s+", " ", req_clean).strip()[:2000]
                posted = it.get("ExternalPostedStart") or it.get("PostedDate")
                detail = (
                    f"{base.split('/hcmUI')[0]}/hcmUI/CandidateExperience/en/sites/{site_number}/job/{rid}"
                    if rid else ""
                )
                out.append({
                    "job_id": _hash_id(source, company, rid),
                    "source": source,
                    "company": company,
                    "company_type_industry": industry,
                    "company_tags": tags,
                    "department": department,
                    "job_title": title,
                    "location": location,
                    "major_req": "",
                    "job_req": req_clean,
                    "job_duty": duty_clean,
                    "application_status": "待申请",
                    "job_stage": "campus" if "intern" in title.lower() or "campus" in title.lower() else "social",
                    "source_config_id": f"{source}:oracle_ce:{company}:{rid}",
                    "publish_date": _parse_dt(posted),
                    "deadline": None,
                    "detail_url": detail,
                    "scraped_at": datetime.utcnow(),
                })
            # stop early when exhausted
            if offset + len(req_list) >= total:
                break
            if len(req_list) < page_size:
                break
    return out


def _fetch_hsbc_search_html(
    company: str,
    portal_url: str,
    page_size: int = 50,
    source: str = "foreign_ibs_official",
    industry: str = "外资投行",
    tags: str = "foreign_ib",
) -> List[Dict[str, Any]]:
    """HSBC mycareer.hsbc.com SearchJobs portal — server-side-rendered HTML
    with <article class="article article--result"> per job. Direct GET works.
    """
    import re as _re
    url = (
        "https://mycareer.hsbc.com/en_GB/external/SearchJobs/"
        f"?listFilterMode=1&pipelineRecordsPerPage={page_size}"
    )
    try:
        r = requests.get(url, timeout=20, headers={
            **_ua_headers(),
            "Accept-Language": "en-GB,en;q=0.9",
        })
    except Exception:
        return []
    if r.status_code != 200 or not r.text:
        return []
    html = r.text
    out: List[Dict[str, Any]] = []
    arts = _re.findall(
        r'<article class="article article--result[^"]*"[^>]*>(.*?)</article>',
        html, _re.S,
    )
    for art in arts:
        href_m = _re.search(r'href="([^"]*PipelineDetail/[^"]+)"', art)
        title_m = _re.search(r'<a[^>]*PipelineDetail[^>]*>([^<]+)</a>', art)
        # HSBC location 字段:`<span class="location">\s*<Country>\s*</span>`
        loc_m = _re.search(r'class="location">\s*([A-Za-z][A-Za-z\s\-]{1,40})\s*<', art)
        if not href_m or not title_m:
            continue
        href = href_m.group(1)
        title = title_m.group(1).strip()
        if not title:
            continue
        rid_m = _re.search(r"/(\d+)$", href)
        rid = rid_m.group(1) if rid_m else href
        location = (loc_m.group(1).strip() if loc_m else "未知")
        # Asia 过滤 — HSBC 全集 53 条,Asia 区少
        if not _is_asia(location):
            continue
        out.append({
            "job_id": _hash_id(source, company, rid),
            "source": source,
            "company": company,
            "company_type_industry": industry,
            "company_tags": tags,
            "department": "",
            "job_title": title,
            "location": location,
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": "social",
            "source_config_id": f"{source}:hsbc_pipeline:{company}:{rid}",
            "publish_date": None,
            "deadline": None,
            "detail_url": href if href.startswith("http") else f"https://mycareer.hsbc.com{href}",
            "scraped_at": datetime.utcnow(),
        })
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
        if handler not in ("workday", "goldman_graphql", "ubs_taleo_spa", "hsbc_html", "hsbc_eightfold", "oracle_ce", "blackrock_sitemap"):
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
                    tls_impersonate=entry.get("tls_impersonate", ""),
                )
            elif handler == "goldman_graphql":
                records = _fetch_goldman_graphql(
                    company=company,
                    endpoint=entry["endpoint"],
                    portal_url=entry.get("portal_url", ""),
                    queries=queries,
                    page_size=page_size,
                )
            elif handler == "ubs_taleo_spa":
                records = _fetch_ubs_taleo_spa(
                    company=company,
                    portal_url=entry.get("portal_url", ""),
                    site_ids=entry.get("site_ids") or [5012],
                    partner_id=int(entry.get("partner_id", 25008)),
                    link_ids=entry.get("link_ids") or [15231],
                )
            elif handler == "hsbc_html":
                records = _fetch_hsbc_search_html(
                    company=company,
                    portal_url=entry.get("portal_url", ""),
                    page_size=int(entry.get("page_size", 50)),
                )
            elif handler == "oracle_ce":
                records = _fetch_oracle_ce(
                    company=company,
                    portal_url=entry.get("portal_url", ""),
                    site_number=entry.get("site_number", "CX_1001"),
                    queries=queries,
                    page_size=int(entry.get("page_size", 25)),
                    max_pages_per_query=max_pages,
                )
            elif handler == "hsbc_eightfold":
                records = _fetch_hsbc_eightfold(
                    company=company,
                    portal_url=entry.get("portal_url", ""),
                    queries=queries,
                    page_size=int(entry.get("page_size", 50)),
                    max_pages_per_query=max_pages,
                )
            elif handler == "blackrock_sitemap":
                records = _fetch_blackrock_sitemap(
                    company=company,
                    portal_url=entry.get("portal_url", "https://careers.blackrock.com"),
                    asia_cities=entry.get("asia_cities") or None,
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
