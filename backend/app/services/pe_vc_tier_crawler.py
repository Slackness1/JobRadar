"""PE/VC tier crawler — Phase 7 wave-3 (2026-05-10).

30 家头部 PE/VC/私募 探查后实际可爬 4 家（≥1 fetched 即 wire）：
  - 源码资本 (sourcecodecap.com WordPress REST /wp-json/wp/v2/hire-job)
  - 鼎晖投资 (jobs.cdhfund.com /def/api/post/page)  ← API 通但当前 0 岗位
  - 黑石集团 (blackstone.wd1.myworkdayjobs.com Workday CXS, Asia filter)
  - KKR     (boards-api.greenhouse.io 'stage' board, Asia filter)

Out-of-scope (24 家，原因详见 /tmp/pe_vc_patch.py):
  A. 域名死/parked: 启明 / 厚朴 / 国投创新 / 国信资本 / 弘毅
  B. 静态形象官网, 招聘只在 WeChat/LinkedIn: 经纬 / 君联 / 真格 / 蓝驰 /
     高榕 / 北极光 / 晨兴 / 华兴 / 达晨 / 今日资本
  C. WAF/CF/jiasule 拦截: 中信建投 / 凯雷 / 中金主域 (cicc.zhiye.com 已在 securities)
  D. SPA + token 鉴权: IDG (campus.idgcapital.com 全 /api/* 认证失败)
  E. 母公司已被 securities tier 覆盖: 华泰联合 / 中信建投资本 /
     中金资本 (cicc.zhiye.com 368 jobs) / 广发信德
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import requests
from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_crawl_logger import company_crawl_log
from app.services.crawler_llm_enrich import enrich_jobs_parallel
from app.services.job_merge import merge_job_fields


# Asia keywords used to filter global Workday/Greenhouse boards down to
# China + APAC seats (which are the ones a JobRadar user can actually apply to).
_ASIA_LOCATION_KEYWORDS = (
    "china", "中国", "beijing", "北京", "shanghai", "上海",
    "shenzhen", "深圳", "guangzhou", "广州", "hangzhou", "杭州",
    "hong kong", "hongkong", "hk", "香港",
    "singapore", "新加坡", "tokyo", "东京",
    "taipei", "台北", "seoul", "首尔", "sydney", "悉尼",
    "mumbai", "孟买", "asia", "apac",
)


@dataclass(frozen=True)
class PeVcTarget:
    company: str
    handler: str  # 'wp', 'greenhouse', 'workday', 'cdh'
    config: dict
    portal_url: str


ACTIVE_PE_VC: list[PeVcTarget] = [
    PeVcTarget(
        company="源码资本",
        handler="wp",
        config={
            "base": "https://sourcecodecap.com",
            "cpt": "hire-job",
        },
        portal_url="https://sourcecodecap.com/jobs/",
    ),
    PeVcTarget(
        company="鼎晖投资",
        handler="cdh",
        config={
            "endpoint": "https://jobs.cdhfund.com/def/api/post/page",
        },
        portal_url="https://jobs.cdhfund.com/",
    ),
    PeVcTarget(
        company="黑石集团",
        handler="workday",
        config={
            "endpoint": "https://blackstone.wd1.myworkdayjobs.com/wday/cxs/blackstone/Blackstone_Careers/jobs",
            "page_size": 20,
            "max_pages": 25,
        },
        portal_url="https://blackstone.wd1.myworkdayjobs.com/en-US/Blackstone_Careers",
    ),
    PeVcTarget(
        company="KKR",
        handler="greenhouse",
        config={
            "endpoint": "https://boards-api.greenhouse.io/v1/boards/stage/jobs",
        },
        portal_url="https://www.kkr.com/careers/career-opportunities",
    ),
    # 2026-05-26: 新加坡主权基金 GIC — 自建 careers.gic.com.sg server-side
    # HTML,直接 VPS curl_cffi 通,108 unique 真 SAIF 岗 (External Managers /
    # Portfolio Construction / Global Markets / ESG Real Estate 等)。
    # SAIF MBA + MF 投资板块高频投递目标。
    PeVcTarget(
        company="GIC",
        handler="gic_html",
        config={
            "base": "https://careers.gic.com.sg",
            "page_size": 25,
            "max_pages": 8,
        },
        portal_url="https://careers.gic.com.sg/search/",
    ),
]


def _ua_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    }


def _is_asia(location_text: str) -> bool:
    if not location_text:
        return False
    lt = location_text.lower()
    return any(kw in lt for kw in _ASIA_LOCATION_KEYWORDS)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    import re as _re
    text = _re.sub(r"<[^>]+>", " ", text)
    text = _re.sub(r"&nbsp;", " ", text)
    text = _re.sub(r"&amp;", "&", text)
    text = _re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:len(fmt) + 4], fmt)
        except Exception:
            continue
    return None


def _fetch_wp(target: PeVcTarget) -> list[dict[str, Any]]:
    """WordPress REST custom-post-type. Used by 源码资本.
    /wp-json/wp/v2/{cpt}?per_page=100&page=N
    """
    base = target.config["base"]
    cpt = target.config["cpt"]
    out: list[dict[str, Any]] = []
    page = 1
    seen: set[str] = set()
    while page <= 5:
        url = f"{base}/wp-json/wp/v2/{cpt}?per_page=100&page={page}"
        try:
            r = requests.get(url, headers=_ua_headers(), timeout=20)
        except Exception:
            break
        if r.status_code != 200:
            break
        try:
            rows = r.json()
        except Exception:
            break
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            jid = str(row.get("id") or "").strip()
            if not jid or jid in seen:
                continue
            seen.add(jid)
            title_html = (row.get("title") or {}).get("rendered") or ""
            content_html = (row.get("content") or {}).get("rendered") or ""
            link = str(row.get("link") or "").strip()
            mapped = {
                "job_id": f"pevc-srccode-{jid}",
                "source": "pe_vc_official",
                "company": target.company,
                "company_type_industry": "PE/VC",
                "company_tags": "pe_vc",
                "department": "",
                "job_title": _strip_html(title_html) or f"职位 {jid}",
                "location": "北京",
                "major_req": "",
                "job_req": "",
                "job_duty": _strip_html(content_html)[:4000],
                "application_status": "待申请",
                "job_stage": "campus" if "实习" in title_html or "intern" in (title_html or "").lower() else "social",
                "source_config_id": f"pe_vc:wp:{target.company}:{cpt}",
                "publish_date": _parse_dt(row.get("date")),
                "deadline": None,
                "detail_url": link or target.portal_url,
                "scraped_at": datetime.utcnow(),
            }
            out.append(mapped)
        if len(rows) < 100:
            break
        page += 1
    return out


def _fetch_cdh(target: PeVcTarget) -> list[dict[str, Any]]:
    """鼎晖投资 jobs.cdhfund.com /def/api/post/page (axios POST)."""
    out: list[dict[str, Any]] = []
    page = 1
    seen: set[str] = set()
    while page <= 20:
        body = {"title": "", "page": page, "pageSize": 50}
        try:
            r = requests.post(
                target.config["endpoint"],
                json=body,
                headers={
                    **_ua_headers(),
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": "Bearer ",
                    "Origin": "https://jobs.cdhfund.com",
                    "Referer": "https://jobs.cdhfund.com/careers/posts",
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
        if data.get("code") != 200:
            break
        result = data.get("result") or {}
        items = result.get("items") or []
        if not items:
            break
        for it in items:
            jid = str(it.get("id") or "").strip()
            if not jid or jid in seen:
                continue
            seen.add(jid)
            title = str(it.get("name") or "").strip()
            if not title:
                continue
            workplace = str(it.get("workPlaceName") or "").strip() or "未知"
            duty = _strip_html(str(it.get("duty") or ""))[:4000]
            req = _strip_html(str(it.get("require") or ""))[:4000]
            wt = str(it.get("workTypeName") or "").lower()
            stage = "campus" if any(k in wt for k in ("校招", "实习", "campus", "intern")) else "social"
            mapped = {
                "job_id": f"pevc-cdh-{jid}",
                "source": "pe_vc_official",
                "company": target.company,
                "company_type_industry": "PE/VC",
                "company_tags": "pe_vc",
                "department": "",
                "job_title": title,
                "location": workplace,
                "major_req": "",
                "job_req": req,
                "job_duty": duty,
                "application_status": "待申请",
                "job_stage": stage,
                "source_config_id": f"pe_vc:cdh:{target.company}",
                "publish_date": _parse_dt(it.get("createTime") or it.get("updateTime")),
                "deadline": None,
                "detail_url": f"https://jobs.cdhfund.com/careers/post_detail?id={jid}",
                "scraped_at": datetime.utcnow(),
            }
            out.append(mapped)
        if not result.get("hasNextPage"):
            break
        page += 1
    return out


def _fetch_workday(target: PeVcTarget) -> list[dict[str, Any]]:
    """Workday CXS endpoint. Used by 黑石. Filter Asia client-side."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_size = int(target.config.get("page_size", 20))
    max_pages = int(target.config.get("max_pages", 25))
    endpoint = target.config["endpoint"]
    base_origin = endpoint.split("/wday/")[0]
    for p in range(max_pages):
        body = {"limit": page_size, "offset": p * page_size}
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
            detail = f"{base_origin}/en-US{ext_path}" if ext_path.startswith("/") else target.portal_url
            mapped = {
                "job_id": f"pevc-bx-{jid}",
                "source": "pe_vc_official",
                "company": target.company,
                "company_type_industry": "PE/VC",
                "company_tags": "pe_vc",
                "department": "",
                "job_title": title,
                "location": location or "未知",
                "major_req": "",
                "job_req": "",
                "job_duty": "",
                "application_status": "待申请",
                "job_stage": "social",
                "source_config_id": f"pe_vc:workday:{target.company}",
                "publish_date": None,
                "deadline": None,
                "detail_url": detail,
                "scraped_at": datetime.utcnow(),
            }
            out.append(mapped)
        total = int(data.get("total") or 0)
        if total and (p + 1) * page_size >= total:
            break
    return out


def _fetch_greenhouse(target: PeVcTarget) -> list[dict[str, Any]]:
    """Greenhouse boards-api. Used by KKR (board='stage')."""
    out: list[dict[str, Any]] = []
    try:
        r = requests.get(target.config["endpoint"], headers=_ua_headers(), timeout=20)
    except Exception:
        return out
    if r.status_code != 200:
        return out
    try:
        data = r.json()
    except Exception:
        return out
    jobs = data.get("jobs") or []
    seen: set[str] = set()
    for j in jobs:
        location = str((j.get("location") or {}).get("name") or "").strip()
        if not _is_asia(location):
            continue
        jid = str(j.get("id") or "").strip()
        if not jid or jid in seen:
            continue
        seen.add(jid)
        title = str(j.get("title") or "").strip()
        if not title:
            continue
        url = str(j.get("absolute_url") or "").strip() or target.portal_url
        title_l = title.lower()
        stage = "campus" if any(k in title_l for k in (
            "intern", "open day", "student", "campus", "graduate", "校招", "实习",
        )) else "social"
        mapped = {
            "job_id": f"pevc-kkr-{jid}",
            "source": "pe_vc_official",
            "company": target.company,
            "company_type_industry": "PE/VC",
            "company_tags": "pe_vc",
            "department": (j.get("departments") or [{}])[0].get("name", "") if j.get("departments") else "",
            "job_title": title,
            "location": location or "未知",
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": stage,
            "source_config_id": f"pe_vc:greenhouse:{target.company}",
            "publish_date": _parse_dt(j.get("updated_at")),
            "deadline": None,
            "detail_url": url,
            "scraped_at": datetime.utcnow(),
        }
        out.append(mapped)
    return out


def _fetch_gic_html(target: PeVcTarget) -> list[dict[str, Any]]:
    """GIC careers.gic.com.sg — server-side rendered HTML, paginate via startrow.

    2026-05-26 实测: 5 页 (startrow=0/25/50/75/100) 覆盖 108 unique jobs。
    plain requests OK,no curl_cffi 必要。
    """
    import hashlib, re as _re
    base = target.config["base"]
    page_size = int(target.config.get("page_size", 25))
    max_pages = int(target.config.get("max_pages", 8))

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in range(max_pages):
        url = f"{base}/search/?q=&locationsearch=&startrow={p*page_size}"
        try:
            r = requests.get(url, headers={
                **_ua_headers(),
                "Accept": "text/html,application/xhtml+xml",
            }, timeout=20)
        except Exception:
            break
        if r.status_code != 200:
            break
        html = r.text
        # Each job appears as: <a href="/job/<location-title>/<id>/">Title</a>
        # Header link + main link both per row → dedupe by id.
        matches = _re.findall(
            r'<a[^>]+href="(/job/([^"/]+)/(\d+)/[^"]*)"[^>]*>\s*([^<]+?)\s*</a>',
            html,
        )
        if not matches:
            break
        new_in_page = 0
        for href, loc_title_slug, jid, title in matches:
            if jid in seen:
                continue
            seen.add(jid)
            new_in_page += 1
            # Decode location from slug: "Singapore-VP%2C-Foo" → "Singapore"
            from urllib.parse import unquote
            slug_decoded = unquote(loc_title_slug)
            # Location is the leading city before the first comma-or-dash-then-title
            # GIC slug pattern: "<City>-<Title-with-commas>"
            # City is the segment before the first "-" if it's a known city marker,
            # but easier: title text doesn't contain city, so city = slug.split('-')[0]
            city_guess = slug_decoded.split("-")[0].strip()
            # Asia filter — GIC has NY/SF jobs too
            if not _is_asia(city_guess):
                continue
            title_clean = _strip_html(title)
            if not title_clean:
                continue
            job_id = hashlib.md5(f"pe_vc_official|GIC|{jid}".encode()).hexdigest()[:24]
            out.append({
                "job_id": job_id,
                "source": "pe_vc_official",
                "company": "GIC",
                "company_type_industry": "主权基金",
                "company_tags": "sovereign_wealth,singapore,gic",
                "department": "",
                "job_title": title_clean,
                "location": city_guess,
                "major_req": "",
                "job_req": "",
                "job_duty": "",
                "application_status": "待申请",
                "job_stage": "campus" if "intern" in title_clean.lower() or "graduate" in title_clean.lower() else "social",
                "source_config_id": f"pe_vc_official:gic:{jid}",
                "publish_date": None,
                "deadline": None,
                "detail_url": f"{base}{href}",
                "scraped_at": datetime.utcnow(),
            })
        if new_in_page == 0:
            break
    return out


_HANDLERS = {
    "wp": _fetch_wp,
    "cdh": _fetch_cdh,
    "workday": _fetch_workday,
    "greenhouse": _fetch_greenhouse,
    "gic_html": _fetch_gic_html,
}


def _valid(mapped: dict[str, Any]) -> bool:
    return bool(mapped.get("job_id") and mapped.get("job_title") and mapped.get("detail_url"))


def crawl_pe_vc(db: Session, parent_log_id: Optional[int] = None) -> int:
    """Run all active PE/VC crawlers. Returns total new_count.
    Each firm wrapped with company_crawl_log so /sites monitor sees rows.
    No Playwright dependency — all 4 handlers are pure HTTP.
    """
    existing_jobs: dict[str, Job] = {}
    for job in db.query(Job).all():
        if getattr(job, "job_id", ""):
            existing_jobs[job.job_id] = job

    total_new = 0
    seen_target_jobs: set[tuple[str, str]] = set()

    for tgt in ACTIVE_PE_VC:
        handler = _HANDLERS.get(tgt.handler)
        if handler is None:
            continue
        target_exc: Optional[Exception] = None
        try:
            with company_crawl_log(
                db,
                source="pe_vc_official",
                company=tgt.company,
                parent_log_id=parent_log_id,
            ) as log:
                try:
                    rows = handler(tgt)
                except Exception as exc:
                    target_exc = exc
                    rows = []
                fetched = 0
                new_count = 0
                new_jobs_for_enrich: list[tuple[Job, str]] = []
                for mapped in rows:
                    if not _valid(mapped):
                        continue
                    key = (mapped["job_id"], mapped["detail_url"])
                    if key in seen_target_jobs:
                        continue
                    seen_target_jobs.add(key)
                    fetched += 1
                    existing = existing_jobs.get(mapped["job_id"])
                    if existing is None:
                        existing = (
                            db.query(Job)
                            .filter(Job.job_id == mapped["job_id"])
                            .first()
                        )
                    if existing is None:
                        created = Job(**mapped)
                        db.add(created)
                        existing_jobs[mapped["job_id"]] = created
                        new_jobs_for_enrich.append((
                            created,
                            (mapped.get("job_duty") or "") + "\n" + (mapped.get("job_req") or ""),
                        ))
                        new_count += 1
                    else:
                        existing_source = getattr(existing, "source", "") or ""
                        if existing_source not in ("pe_vc_official", "internet_official"):
                            setattr(existing, "source", "pe_vc_official")
                        merge_job_fields(existing, mapped)
                db.commit()
                if new_jobs_for_enrich:
                    try:
                        enrich_jobs_parallel(db, new_jobs_for_enrich)
                        db.commit()
                    except Exception:
                        pass
                log.fetched_count = fetched
                log.new_count = new_count
                total_new += new_count
                if target_exc is not None:
                    raise target_exc
        except Exception:
            pass

    return total_new
