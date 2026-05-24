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

# 汇添富 / 类似租户用 zwlblit span 模板而不是 td。
# Returns (title, category, location, pub_date, jobadid).
_BEISEN_ROW_V2_RE = re.compile(
    r'<span class="zwlbtxt275">([^<]+)</span>'
    r'\s*<span class="zwlbtxt100">([^<]+)</span>'
    r'\s*<span class="zwlbtxt250"[^>]*title="([^"]*)"[^>]*>[^<]*</span>'
    r'\s*<span class="zwlbtxt210">([^<]+)</span>'
    r'.*?jobadid="(\d+)"',
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
        used_v2 = False
        if not rows:
            v2_rows = _BEISEN_ROW_V2_RE.findall(page_html)
            if v2_rows:
                # Normalize to v1 5-tuple: (title, detail_path, ptype, location, pub)
                rows = [
                    (title, f"/Portal/Resume/ResumeItem?jid={jid}", ptype.strip(), loc, pub)
                    for (title, ptype, loc, pub, jid) in v2_rows
                ]
                used_v2 = True
        if not rows:
            break
        added_this_page = 0
        for raw_title, detail_path, ptype, location, pub in rows:
            if used_v2:
                key_match = re.search(r"jid=(\d+)", detail_path)
            else:
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


# ---- Beisen new-CMS SPA (`/campusxq?jobId=...`) ----------------------------
#
# 2026-05-16 实测部分 zhiye 租户（zofund 中欧 / huaan 华安 / csfunds 长盛 等）
# 切到 stc-cms.beisen.com 新一代 CMS：HTML 是 SPA 壳，岗位通过 JS 渲染到一个
# <table><tbody><tr> 表格里，链接形如 `<a href="/campusxq?jobId=621076397">`。
# 旧 `_BEISEN_ROW_RE` 抓 `/zpdetail/` 完全 miss，`/api/Jobad/GetJobAdPageList`
# 也 302 redirect 到 /404（这批租户没在那个 endpoint 上提供 JSON）。
#
# 唯一稳定路径是 Playwright headless 渲染后从 DOM 提取。开销 ~8s/家。
def crawl_zhiye_spa_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    entry_url = target["entry_url"]
    base_match = re.match(r"^(https?://[^/]+)", entry_url)
    if not base_match:
        return []
    base = base_match.group(1)
    company = target["name"]
    # 本机/VPS 都用 mihomo proxy；REQUEST_PROXIES dict for requests, but
    # Playwright takes a single `server` string.
    proxy_url: Optional[str] = None
    if REQUEST_PROXIES:
        proxy_url = REQUEST_PROXIES.get("https") or REQUEST_PROXIES.get("http")

    real_ua = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    rows_raw: List[Dict[str, str]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                proxy={"server": proxy_url} if proxy_url else None,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            try:
                ctx = browser.new_context(
                    user_agent=real_ua,
                    locale="zh-CN",
                    viewport={"width": 1440, "height": 900},
                )
                page = ctx.new_page()
                try:
                    page.goto(entry_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(7000)  # SPA hydrate window
                    # Job rows live in <table tbody tr>; column count differs per
                    # tenant (中欧 6 cols, 华安 5 cols). Extract the header row
                    # labels alongside data rows so the caller can map by name.
                    page_data = page.evaluate(
                        """() => {
                            const table = document.querySelector('table');
                            if (!table) return {headers: [], rows: []};
                            // Header = first row that contains <th>, or the first row overall.
                            const allRows = Array.from(table.querySelectorAll('tr'));
                            const headerRow = allRows.find(r => r.querySelector('th')) || allRows[0];
                            const headers = headerRow
                                ? Array.from(headerRow.querySelectorAll('th,td')).map(c => (c.innerText || '').trim())
                                : [];
                            const rows = allRows.map(tr => {
                                const a = tr.querySelector('a[href*="/campusxq?jobId="]');
                                if (!a) return null;
                                const href = a.getAttribute('href') || '';
                                const tds = Array.from(tr.querySelectorAll('td')).map(td => (td.innerText || '').trim());
                                return {href, title: (a.innerText || '').trim(), cols: tds};
                            }).filter(x => x !== null);
                            return {headers, rows};
                        }"""
                    ) or {}
                    rows_raw = page_data.get("rows") or []
                    headers_raw = page_data.get("headers") or []
                except Exception:
                    rows_raw = []
                    headers_raw = []
                finally:
                    ctx.close()
            finally:
                browser.close()
    except Exception:
        return []

    # Header-based column mapping. Layouts vary by tenant: 中欧 6 cols incl.
    # 部门名称, 华安 5 cols drops 部门. Match by Chinese label substring so we
    # don't depend on positional index.
    def _resolve_col_idx(headers: List[str], *needles: str) -> Optional[int]:
        for i, h in enumerate(headers):
            for needle in needles:
                if needle in h:
                    return i
        return None
    idx_dept = _resolve_col_idx(headers_raw, "部门")
    idx_cat  = _resolve_col_idx(headers_raw, "职位类别", "类别")
    idx_loc  = _resolve_col_idx(headers_raw, "工作地点", "地点")
    idx_pub  = _resolve_col_idx(headers_raw, "发布日期", "发布时间")

    records: List[Dict[str, Any]] = []
    seen: set = set()
    for row in rows_raw:
        href = row.get("href") or ""
        title = (row.get("title") or "").strip()
        cols = row.get("cols") or []
        m = re.search(r"jobId=(\d+)", href)
        if not m or not title:
            continue
        job_key = m.group(1)
        if job_key in seen:
            continue
        seen.add(job_key)
        def _col(i: Optional[int]) -> str:
            if i is None or i >= len(cols):
                return ""
            return (cols[i] or "").strip()
        department = _col(idx_dept)
        category = _col(idx_cat) or department
        location = _col(idx_loc) or "未知"
        publish = _col(idx_pub)
        detail_url = f"{base}/campusxq?jobId={job_key}"
        records.append({
            "job_id": _hash_id("funds_zhiye_spa", company, job_key),
            "source": "funds_zhiye_spa",
            "company": company,
            "company_type_industry": "公募基金",
            "company_tags": category or "校园招聘",
            "department": department or company,
            "job_title": title,
            "location": location,
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": _infer_stage(title, category),
            "source_config_id": f"funds_api:{company}:{job_key}",
            "publish_date": _parse_dt(publish),
            "deadline": None,
            "detail_url": detail_url,
            "scraped_at": datetime.utcnow(),
        })
    return records


# ---- Wintalent (sc.hotjob.cn / sc.wintalent.cn 自助站) ---------------------

WINTALENT_SC_BASE = "https://sc.hotjob.cn"


def _wintalent_hash_id(company: str, post_id: Any, recruit_type: Any) -> str:
    key = f"funds_wintalent_sc|{company}|{post_id}|{recruit_type}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:24]


def _wintalent_parse_dt(s: Optional[str]) -> Optional[datetime]:
    s = (s or "").strip()
    if not s or s.startswith("3000"):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _wintalent_infer_stage(recruit_type: int, title: str, post_type: str) -> str:
    if recruit_type == 12:
        return "internship"
    if recruit_type == 1:
        return "campus"
    blob = f"{title} {post_type}"
    if "实习" in blob:
        return "internship"
    if any(k in blob for k in ("校招", "校园", "应届", "26届", "27届", "campus")):
        return "campus"
    return "other"


def crawl_wintalent_sc_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    """sc.hotjob.cn/wt/<COID>/ 自助站 (Wintalent / 北森自助 ATS)。

    target 必填:
      name, wintalent_coid (站点 slug 如 'bosera', 'AIFMC')
      recruit_types: [1,2,12] 子集；默认 [1,2,12] (校招/社招/实习)
      max_pages: 每个 recruitType 最大翻页数；默认 20
    """
    coid = target["wintalent_coid"]
    recruit_types: List[int] = target.get("recruit_types") or [1, 2, 12]
    max_pages = int(target.get("max_pages") or 20)
    base = f"{WINTALENT_SC_BASE}/wt/{coid}"
    referer = f"{base}/web/index"
    list_url = f"{base}/web/json/position/list"

    records: List[Dict[str, Any]] = []
    seen_post_ids: set = set()

    for rt in recruit_types:
        for page in range(1, max_pages + 1):
            try:
                resp = requests.post(
                    list_url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": referer,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json, text/plain, */*",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    data={
                        "page": str(page),
                        "pageSize": "10",
                        "recruitType": str(rt),
                        "brandCode": "1",
                        "trademark": "1",
                        "lanType": "1",
                    },
                    proxies=REQUEST_PROXIES,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json() or {}
            except Exception:
                break

            posts = data.get("postList") or []
            page_count = int(data.get("pageCount") or 1)
            if not posts:
                break

            added_this_page = 0
            for item in posts:
                post_id = item.get("postId")
                if post_id is None:
                    continue
                key = (post_id, rt)
                if key in seen_post_ids:
                    continue
                seen_post_ids.add(key)

                title = (item.get("postName") or "").strip()
                if not title:
                    continue
                location = (item.get("workPlace") or "").strip() or "未知"
                post_type = (item.get("postType") or "").strip()
                dept = (item.get("deptOrgName") or item.get("orgName") or target["name"]).strip()
                publish = _wintalent_parse_dt(item.get("publishDateTime") or item.get("publishDate"))
                deadline = _wintalent_parse_dt(item.get("endDate"))
                token = item.get("postIdToken") or post_id
                detail_url = f"{base}/web/templates/v1/companyfile/companyfileTemplate.html?postIdEnc={token}"

                records.append({
                    "job_id": _wintalent_hash_id(target["name"], post_id, rt),
                    "source": "funds_wintalent_sc",
                    "company": target["name"],
                    "company_type_industry": "公募基金",
                    "company_tags": post_type or "校园招聘",
                    "department": dept,
                    "job_title": title,
                    "location": location,
                    "major_req": "",
                    "job_req": (item.get("serviceCondition") or "").strip(),
                    "job_duty": (item.get("workContent") or "").strip(),
                    "application_status": "待申请",
                    "job_stage": _wintalent_infer_stage(int(rt), title, post_type),
                    "source_config_id": f"funds_api:{target['name']}:{post_id}:{rt}",
                    "publish_date": publish,
                    "deadline": deadline,
                    "detail_url": detail_url,
                    "scraped_at": datetime.utcnow(),
                })
                added_this_page += 1

            if added_this_page == 0:
                break
            if page >= page_count:
                break
            time.sleep(0.4)

    return records


# ---- Tagging helpers for source sub-strings --------------------------------

_KNOWN = {"hotjob", "zhiye", "moka_embedded", "zhiye_beisen_cms", "zhiye_spa", "wintalent_sc", "phfund_api"}

_FAMILY_SOURCE_OVERRIDE: Dict[str, str] = {
    "hotjob":            "funds_hotjob",
    "zhiye":             "funds_zhiye",
    "moka_embedded":     "funds_moka_embedded",
    "zhiye_beisen_cms":  "funds_zhiye_beisen_cms",
    "zhiye_spa":         "funds_zhiye_spa",
    "wintalent_sc":      "funds_wintalent_sc",
    "phfund_api":        "funds_phfund_api",
}


# ---- 鹏华基金 (job.phfund.com.cn) POST JSON API ---------------------------

def crawl_phfund_api_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    """鹏华基金 job portal: POST /general/demand/listDemandPage with JSON body.

    Returns up to max_pages×page_size records (校招+社招+实习 combined).
    API includes `professionCharacter` field to distinguish stages.
    Detail URL: https://job.phfund.com.cn/#/postdetail?id=<id>
    """
    company = target.get("name", "鹏华基金")
    base = "https://job.phfund.com.cn"
    max_pages = int(target.get("max_pages") or 10)
    page_size = 100
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Referer": f"{base}/",
        "Origin": base,
        "Content-Type": "application/json",
    }
    records: List[Dict[str, Any]] = []
    seen: set = set()
    for page_no in range(1, max_pages + 1):
        try:
            resp = requests.post(
                f"{base}/general/demand/listDemandPage",
                json={"page": page_no, "size": page_size},
                headers=headers,
                timeout=20,
                proxies=REQUEST_PROXIES or None,
            )
        except Exception:
            break
        if resp.status_code != 200:
            break
        data = (resp.json() or {}).get("data") or {}
        items = data.get("list") or []
        if not items:
            break
        total = int(data.get("total") or 0)
        for item in items:
            jid = str(item.get("id") or "").strip()
            if not jid or jid in seen:
                continue
            seen.add(jid)
            char = (item.get("professionCharacter") or "").strip()
            stage = "internship" if char == "实习" else ("campus" if char == "校招" else "social")
            records.append({
                "job_id": _hash_id("funds_phfund_api", company, jid),
                "source": "funds_phfund_api",
                "company": company,
                "company_type_industry": "公募基金",
                "company_tags": "phfund",
                "department": (item.get("entryDep") or "").strip(),
                "job_title": (item.get("jobName") or "").strip(),
                "location": (item.get("workAddress") or "未知").strip(),
                "major_req": "",
                "job_req": (item.get("jobRequirements") or "").strip(),
                "job_duty": (item.get("responsibility") or "").strip(),
                "application_status": "待申请",
                "job_stage": stage,
                "source_config_id": f"funds_phfund_api:{company}:{jid}",
                "publish_date": _parse_dt((item.get("releaseDate") or "").strip()),
                "deadline": _parse_dt((item.get("blockingTime") or "").strip()),
                "detail_url": f"{base}/#/postdetail?id={jid}",
                "scraped_at": datetime.utcnow(),
            })
        if len(records) >= total or page_no * page_size >= total:
            break
    return records


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
        elif family == "zhiye_spa":
            crawled = crawl_zhiye_spa_target(target)
        elif family == "wintalent_sc":
            crawled = crawl_wintalent_sc_target(target)
        elif family == "phfund_api":
            crawled = crawl_phfund_api_target(target)
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
