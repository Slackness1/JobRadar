from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import requests
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

from app.models import Job
from app.services.job_merge import merge_job_fields


PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPANY_TRUTH_PATH = PROJECT_ROOT / "data" / "exports" / "company_truth_spring_master.csv"

SKIP_URL_HOSTS = {
    "mp.weixin.qq.com",
    "docs.qq.com",
    "alidocs.dingtalk.com",
}

SKIP_URL_KEYWORDS = [
    "wjx.cn/",
    "wenjuan.com/",
    "jinshuju.net/",
    "jinshuju.com/",
]

GENERIC_LEGACY_CRAWLER_KEYS = {
    "feishu",
    "app.mokahr.com/campus_apply",
    "app.mokahr.com/campus-recruitment",
}


SOE_GROUP_RULES = [
    {
        "group": "国家电网",
        "tier": "tier1_grid_tobacco_energy",
        "include": ["国家电网", "国网", "sgcc"],
        "exclude": [],
    },
    {
        "group": "南方电网",
        "tier": "tier1_grid_tobacco_energy",
        "include": ["南方电网", "csg"],
        "exclude": [],
    },
    {
        "group": "中烟系统",
        "tier": "tier1_grid_tobacco_energy",
        "include": ["中烟", "烟草", "tobacco"],
        "exclude": [],
    },
    {
        "group": "中国移动",
        "tier": "tier1_operator_core",
        "include": ["中国移动", "chinamobile"],
        "exclude": [],
    },
    {
        "group": "中国电信",
        "tier": "tier1_operator_core",
        "include": ["中国电信", "chinatelecom"],
        "exclude": [],
    },
    {
        "group": "中国联通",
        "tier": "tier1_operator_core",
        "include": ["中国联通", "chinaunicom"],
        "exclude": [],
    },
    {
        "group": "中国石油",
        "tier": "tier1_oil_core",
        "include": ["中国石油", "中石油", "cnpc"],
        "exclude": ["中国石油大学"],
    },
    {
        "group": "中国石化",
        "tier": "tier1_oil_core",
        "include": ["中国石化", "中石化", "sinopec"],
        "exclude": [],
    },
    {
        "group": "中国海油",
        "tier": "tier1_oil_core",
        "include": ["中国海油", "中海油", "cnooc"],
        "exclude": [],
    },
    {
        "group": "中广核",
        "tier": "tier1_nuclear_hydro_energy",
        "include": ["中广核", "cgn"],
        "exclude": [],
    },
    {
        "group": "中核",
        "tier": "tier1_nuclear_hydro_energy",
        "include": ["中核", "中国核工业", "cnnc"],
        "exclude": [],
    },
    {
        "group": "三峡集团",
        "tier": "tier1_nuclear_hydro_energy",
        "include": ["三峡", "中国三峡"],
        "exclude": ["三峡银行"],
    },
    {
        "group": "国家能源集团",
        "tier": "tier1_nuclear_hydro_energy",
        "include": ["国家能源", "国家能源集团", "chnenergy"],
        "exclude": [],
    },
    {
        "group": "中国建筑",
        "tier": "tier2_transport_construction",
        "include": ["中国建筑", "中建", "cscec"],
        "exclude": ["中国建材", "中建材"],
    },
    {
        "group": "中国交建",
        "tier": "tier2_transport_construction",
        "include": ["中国交建", "中交", "ccccltd"],
        "exclude": [],
    },
    {
        "group": "中国中铁",
        "tier": "tier2_transport_construction",
        "include": ["中国中铁", "中铁", "crec"],
        "exclude": ["中铁建", "中国铁建"],
    },
    {
        "group": "中国铁建",
        "tier": "tier2_transport_construction",
        "include": ["中国铁建", "中铁建", "crcc", "crcci"],
        "exclude": [],
    },
    {
        "group": "航空工业",
        "tier": "tier2_defense_research",
        "include": ["航空工业", "中航", "avic"],
        "exclude": [],
    },
    {
        "group": "中国航天科技",
        "tier": "tier2_defense_research",
        "include": ["航天科技", "中国航天科技", "casc"],
        "exclude": [],
    },
    {
        "group": "中国航天科工",
        "tier": "tier2_defense_research",
        "include": ["航天科工", "中国航天科工", "casic"],
        "exclude": [],
    },
    {
        "group": "中国船舶",
        "tier": "tier2_defense_research",
        "include": ["中国船舶", "中船", "cssc", "csic"],
        "exclude": [],
    },
]


@dataclass(frozen=True)
class StateOwnedTarget:
    tier: str
    group: str
    company_id: str
    company: str
    url: str
    target_type: str
    source_field: str
    platform: str
    row_is_crawlable: str


@dataclass
class StateOwnedCrawlResult:
    tier: str
    group: str
    company_id: str
    company: str
    url: str
    status: str
    fetched_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    error: str = ""
    platform: str = ""


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalize_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    parsed = urlparse(text)
    if not parsed.netloc:
        return ""
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "", "", parsed.query, parsed.fragment))


def _is_skipped_url(url: str) -> bool:
    normalized = _normalize_url(url)
    if not normalized:
        return True
    parsed = urlparse(normalized)
    if parsed.netloc.lower() in SKIP_URL_HOSTS:
        return True
    lowered = normalized.lower()
    return any(keyword in lowered for keyword in SKIP_URL_KEYWORDS)


def _detect_platform(url: str) -> str:
    lowered = (url or "").lower()
    if "zhiye.com" in lowered:
        return "Zhiye"
    if "mokahr.com" in lowered:
        return "Moka"
    if "hotjob.cn" in lowered:
        return "HotJob"
    if "51job.com" in lowered or "51jobcdn.com" in lowered:
        return "51job"
    if "zhaopin.com" in lowered:
        return "Zhaopin"
    if "chinahr.com" in lowered:
        return "ChinaHR"
    if "iguopin.com" in lowered:
        return "IGuopin"
    if "liepin.com" in lowered:
        return "Liepin"
    return "Official"


def _row_text(row: dict[str, str]) -> str:
    return " ".join([
        row.get("canonical_name", ""),
        row.get("display_name", ""),
        row.get("aliases_json", ""),
        row.get("entity_members_json", ""),
    ]).lower()


def _match_group(row: dict[str, str]) -> Optional[dict[str, Any]]:
    text = _row_text(row)
    for rule in SOE_GROUP_RULES:
        if any(term.lower() in text for term in rule["exclude"]):
            continue
        if any(term.lower() in text for term in rule["include"]):
            return rule
    return None


def _target_type_from_url(url: str) -> str:
    lowered = (url or "").lower()
    if "intern" in lowered or "实习" in lowered:
        return "internship"
    if "social" in lowered or "society" in lowered:
        return "social"
    return "campus"


def build_state_owned_targets(
    company_truth_path: Path = COMPANY_TRUTH_PATH,
    include_uncrawlable: bool = False,
) -> list[StateOwnedTarget]:
    rows = _read_csv(company_truth_path)
    targets: dict[tuple[str, str], StateOwnedTarget] = {}
    for row in rows:
        rule = _match_group(row)
        if rule is None:
            continue
        if not include_uncrawlable and row.get("is_crawlable") != "True":
            continue
        url = _normalize_url(row.get("best_apply_link", ""))
        if _is_skipped_url(url):
            continue
        key = (row.get("company_id", ""), url)
        targets[key] = StateOwnedTarget(
            tier=rule["tier"],
            group=rule["group"],
            company_id=row.get("company_id", ""),
            company=row.get("canonical_name") or row.get("display_name") or rule["group"],
            url=url,
            target_type=_target_type_from_url(url),
            source_field="best_apply_link",
            platform=_detect_platform(url),
            row_is_crawlable=row.get("is_crawlable", ""),
        )
    return sorted(targets.values(), key=lambda item: (item.tier, item.group, item.company, item.url))


def _configure_legacy_network() -> None:
    proxy_url = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
        or ""
    ).strip()

    from app.services.legacy_crawlers import crawler as legacy

    if proxy_url:
        legacy.PROXY = {"server": proxy_url}
        legacy.REQUEST_PROXIES = {"http": proxy_url, "https": proxy_url}
    else:
        legacy.PROXY = None
        legacy.REQUEST_PROXIES = {}


def _parse_datetime(value: Optional[str]):
    text = (value or "").strip()
    if not text:
        return None
    text = text.replace("/", "-")
    if "T" in text:
        text = text[:19]
    elif len(text) >= 10:
        text = text[:10]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _stable_id(prefix: str, target: StateOwnedTarget, raw_id: str, title: str, detail_url: str) -> str:
    material = "|".join([target.group, target.company_id, target.company, raw_id, title, detail_url])
    digest = hashlib.md5(material.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _map_legacy_job(target: StateOwnedTarget, legacy_job: Any) -> dict[str, Any]:
    raw_id = str(getattr(legacy_job, "id", "") or "").strip()
    title = str(getattr(legacy_job, "title", "") or "").strip()
    detail_url = _normalize_url(str(getattr(legacy_job, "url", "") or target.url))
    job_id = raw_id or _stable_id("soe", target, raw_id, title, detail_url)
    return {
        "job_id": job_id,
        "source": "state_owned_official",
        "company": str(getattr(legacy_job, "company", "") or target.company).strip() or target.company,
        "company_type_industry": "国央企",
        "company_tags": f"{target.tier}|{target.group}",
        "department": str(getattr(legacy_job, "department", "") or "").strip(),
        "job_title": title,
        "location": str(getattr(legacy_job, "location", "") or "").strip() or "未知",
        "major_req": "",
        "job_req": str(getattr(legacy_job, "requirements", "") or "").strip(),
        "job_duty": str(getattr(legacy_job, "description", "") or "").strip(),
        "application_status": "待申请",
        "job_stage": str(getattr(legacy_job, "job_type", "") or target.target_type or "campus").strip(),
        "source_config_id": f"state_owned:{target.tier}:{target.group}:{target.company_id}:{target.url}",
        "publish_date": _parse_datetime(getattr(legacy_job, "publish_date", "")),
        "deadline": _parse_datetime(getattr(legacy_job, "deadline", "")),
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }


def _valid_mapped_job(mapped: dict[str, Any]) -> bool:
    return bool(mapped.get("job_id") and mapped.get("job_title") and mapped.get("detail_url"))


def _select_legacy_crawler(target: StateOwnedTarget):
    from app.services.legacy_crawlers import crawler as legacy

    lowered = target.url.lower()
    for key, func in sorted(legacy.SITE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if key in GENERIC_LEGACY_CRAWLER_KEYS:
            continue
        if key in lowered:
            return func
    if target.platform == "Zhiye":
        return legacy.crawl_zhiye_campus
    return None


def _extract_zhaopin_company_id(html: str) -> str:
    patterns = [
        r"companyid:\s*'([^']+)'",
        r'companyId:"([^"]+)"',
        r'companyId:\\"([^\\"]+)\\"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
    return ""


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "list", "records", "data"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def _crawl_zhaopin_grace(target: StateOwnedTarget, max_pages: Optional[int] = None):
    from app.services.legacy_crawlers import crawler as legacy

    headers = {
        "User-Agent": legacy.UA,
        "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        html_resp = requests.get(
            target.url,
            headers=headers,
            proxies=legacy.REQUEST_PROXIES,
            timeout=30,
        )
        html_resp.raise_for_status()
    except Exception:
        return None

    company_id = _extract_zhaopin_company_id(html_resp.text)
    if not company_id:
        return None

    api_base = "https://fe.zhaopin.com/grace/api"
    jobs: list[Any] = []
    seen_ids: set[str] = set()
    page_limit = max(1, int(max_pages or 20))

    for page_index in range(1, page_limit + 1):
        payload = {
            "orgNumbers": [company_id],
            "jobSource": 2,
            "pageIndex": page_index,
            "pageSize": 20,
        }
        try:
            resp = requests.post(
                f"{api_base}/dsc/search-job-list",
                json=payload,
                headers={**headers, "Content-Type": "application/json;charset=UTF-8", "Referer": target.url},
                proxies=legacy.REQUEST_PROXIES,
                timeout=30,
            )
            data = resp.json()
        except Exception:
            break

        body = data.get("data") or {}
        rows = _as_list(body)
        if not rows:
            break

        page_added = 0
        for item in rows:
            if not isinstance(item, dict):
                continue
            title = str(
                item.get("jobName")
                or item.get("positionName")
                or item.get("name")
                or item.get("title")
                or ""
            ).strip()
            if not title:
                continue
            job_key = str(
                item.get("jobNumber")
                or item.get("jobId")
                or item.get("positionId")
                or item.get("id")
                or ""
            ).strip()
            if job_key in seen_ids:
                continue
            seen_ids.add(job_key)
            detail_url = str(item.get("positionURL") or item.get("positionUrl") or target.url).strip() or target.url
            location = str(
                item.get("cityName")
                or item.get("workCity")
                or item.get("workLocation")
                or item.get("city")
                or ""
            ).strip() or "未知"
            department = str(
                item.get("orgName")
                or item.get("departmentName")
                or item.get("department")
                or ""
            ).strip()
            requirement = str(item.get("jobRequirement") or item.get("requirement") or "").strip()
            description = str(item.get("jobDescription") or item.get("description") or "").strip()
            publish_date = str(item.get("publishDate") or item.get("createDate") or "").strip()
            deadline = str(item.get("endDate") or item.get("deadline") or "").strip()
            jobs.append(legacy.JobInfo(
                id=job_key,
                company=target.company,
                title=title,
                location=location,
                department=department,
                job_type=target.target_type,
                url=detail_url,
                publish_date=publish_date or None,
                deadline=deadline or None,
                description=description or None,
                requirements=requirement or None,
            ))
            page_added += 1

        if page_added == 0:
            break

    if jobs:
        return jobs

    # Grace 站常见情况是 company detail 明确显示在线职位数为 0。
    try:
        detail_resp = requests.post(
            f"{api_base}/dsc/get-company-detail",
            json={"companyNumber": company_id},
            headers={**headers, "Content-Type": "application/json;charset=UTF-8", "Referer": target.url},
            proxies=legacy.REQUEST_PROXIES,
            timeout=30,
        )
        detail_data = detail_resp.json().get("data") or {}
        company_base = detail_data.get("companyBase") or {}
        if int(company_base.get("onlinePositionNumbers") or 0) == 0:
            return []
    except Exception:
        pass

    # 再退一步用 group-by 接口探测是否至少存在岗位标题分组。
    try:
        group_resp = requests.post(
            f"{api_base}/dsc/search-groupby-jobtitle",
            json={"orgNumbers": [company_id], "jobSource": 2},
            headers={**headers, "Content-Type": "application/json;charset=UTF-8", "Referer": target.url},
            proxies=legacy.REQUEST_PROXIES,
            timeout=30,
        )
        group_items = _as_list((group_resp.json().get("data") or {}))
        if not group_items:
            return []
    except Exception:
        pass

    return None


def _crawl_generic(page: Any, target: StateOwnedTarget, max_pages: Optional[int] = None):
    from app.services.legacy_crawlers import crawler as legacy

    parsed = urlparse(target.url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    runtime_target = {
        "name": target.company,
        "url": target.url,
        "type": target.target_type,
    }
    if max_pages:
        runtime_target["max_pages"] = int(max_pages)

    return legacy.crawl_with_pagination(
        page,
        runtime_target,
        target.company,
        base_url,
        selectors=[
            '[class*="job" i]',
            '[class*="position" i]',
            '[class*="post" i]',
            '[class*="list-item" i]',
            '[class*="card" i]',
            'table tbody tr',
            'li',
            'a[href*="job"]',
            'a[href*="position"]',
            'a[href*="post"]',
            'a[href*="detail"]',
        ],
        scroll=True,
        timeout=45000,
        extra_sleep=3,
        response_keywords=["job", "position", "post", "recruit", "campus", "api", "annc"],
        max_pages=max_pages,
    )


def crawl_state_owned_targets(
    db: Session,
    targets: list[StateOwnedTarget],
    dry_run: bool = False,
    max_pages: Optional[int] = None,
) -> list[StateOwnedCrawlResult]:
    _configure_legacy_network()

    from playwright.sync_api import sync_playwright
    from app.services.legacy_crawlers import crawler as legacy

    existing_jobs: dict[str, Job] = {}
    for job in db.query(Job).all():
        if getattr(job, "job_id", ""):
            existing_jobs[job.job_id] = job

    results: list[StateOwnedCrawlResult] = []
    seen_run_jobs: set[tuple[str, str]] = set()
    original_legacy_max_pages = getattr(legacy, "MAX_PAGES", None)
    if max_pages:
        legacy.MAX_PAGES = int(max_pages)

    try:
        with sync_playwright() as playwright:
            browser = legacy.make_browser(playwright)
            try:
                for target in targets:
                    context, page = legacy.new_page(browser)
                    try:
                        zhaopin_jobs = _crawl_zhaopin_grace(target, max_pages=max_pages) if target.platform == "Zhaopin" else None
                        if zhaopin_jobs is not None:
                            legacy_jobs = zhaopin_jobs
                        else:
                            fn = _select_legacy_crawler(target)
                            if fn is not None:
                                runtime_target = {"name": target.company, "url": target.url, "type": target.target_type}
                                if max_pages:
                                    runtime_target["max_pages"] = int(max_pages)
                                legacy_jobs = fn(page, runtime_target)
                            else:
                                legacy_jobs = _crawl_generic(page, target, max_pages=max_pages)

                        fetched_count = 0
                        new_count = 0
                        updated_count = 0
                        for legacy_job in legacy_jobs:
                            mapped = _map_legacy_job(target, legacy_job)
                            if not _valid_mapped_job(mapped):
                                continue
                            dedupe_key = (mapped["job_id"], mapped["detail_url"])
                            if dedupe_key in seen_run_jobs:
                                continue
                            seen_run_jobs.add(dedupe_key)
                            fetched_count += 1

                            existing = existing_jobs.get(mapped["job_id"])
                            if existing is None:
                                existing = db.query(Job).filter(Job.job_id == mapped["job_id"]).first()
                            if existing is None:
                                if not dry_run:
                                    created = Job(**mapped)
                                    db.add(created)
                                    existing_jobs[mapped["job_id"]] = created
                                new_count += 1
                            else:
                                if not dry_run and merge_job_fields(existing, mapped):
                                    updated_count += 1
                                existing_jobs[mapped["job_id"]] = existing

                        if not dry_run:
                            db.commit()

                        results.append(StateOwnedCrawlResult(
                            tier=target.tier,
                            group=target.group,
                            company_id=target.company_id,
                            company=target.company,
                            url=target.url,
                            status="success" if fetched_count else "empty",
                            fetched_count=fetched_count,
                            new_count=new_count,
                            updated_count=updated_count,
                            platform=target.platform,
                        ))
                    except Exception as exc:
                        if not dry_run:
                            db.rollback()
                        results.append(StateOwnedCrawlResult(
                            tier=target.tier,
                            group=target.group,
                            company_id=target.company_id,
                            company=target.company,
                            url=target.url,
                            status="failed",
                            error=str(exc)[:500],
                            platform=target.platform,
                        ))
                    finally:
                        context.close()
            finally:
                browser.close()
    finally:
        if original_legacy_max_pages is not None:
            legacy.MAX_PAGES = original_legacy_max_pages

    return results


def summarize_results(results: list[StateOwnedCrawlResult]) -> dict[str, Any]:
    by_group: dict[str, dict[str, Any]] = {}
    by_company: dict[str, dict[str, Any]] = {}
    for item in results:
        group_entry = by_group.setdefault(item.group, {
            "tier": item.tier,
            "targets": 0,
            "success_targets": 0,
            "failed_targets": 0,
            "empty_targets": 0,
            "fetched_count": 0,
            "new_count": 0,
            "updated_count": 0,
        })
        company_entry = by_company.setdefault(item.company, {
            "tier": item.tier,
            "group": item.group,
            "targets": 0,
            "success_targets": 0,
            "failed_targets": 0,
            "empty_targets": 0,
            "fetched_count": 0,
            "new_count": 0,
            "updated_count": 0,
        })
        for entry in (group_entry, company_entry):
            entry["targets"] += 1
            entry["fetched_count"] += item.fetched_count
            entry["new_count"] += item.new_count
            entry["updated_count"] += item.updated_count
            if item.status == "success":
                entry["success_targets"] += 1
            elif item.status == "empty":
                entry["empty_targets"] += 1
            else:
                entry["failed_targets"] += 1

    return {
        "target_count": len(results),
        "fetched_count": sum(item.fetched_count for item in results),
        "new_count": sum(item.new_count for item in results),
        "updated_count": sum(item.updated_count for item in results),
        "failed_count": sum(1 for item in results if item.status == "failed"),
        "empty_count": sum(1 for item in results if item.status == "empty"),
        "success_count": sum(1 for item in results if item.status == "success"),
        "groups": by_group,
        "companies": by_company,
    }
