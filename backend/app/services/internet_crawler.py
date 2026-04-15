from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse, urlunparse

import yaml
from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_truth_merge import normalize_company_for_matching
from app.services.job_merge import merge_job_fields


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"
TIER_CONFIG_PATH = BACKEND_DIR / "config" / "tiered_internet_companies.yaml"
TARGETS_CONFIG_PATH = BACKEND_DIR / "config" / "targets.yaml"
COMPANY_TRUTH_PATH = PROJECT_ROOT / "data" / "exports" / "company_truth_spring_master.csv"
JOB_TRUTH_PATH = PROJECT_ROOT / "data" / "exports" / "job_truth_spring_master.csv"

SKIP_URL_HOSTS = {
    "mp.weixin.qq.com",
    "docs.qq.com",
    "alidocs.dingtalk.com",
    "www.xiaohongshu.com",
    "xiaohongshu.com",
}

SKIP_URL_KEYWORDS = [
    "wjx.cn/",
    "wenjuan.com/",
    "jinshuju.net/",
    "jinshuju.com/",
]

DETAIL_URL_PATTERNS = [
    re.compile(r"/position/\d+/detail", re.I),
    re.compile(r"/position/[^/?#]+/detail", re.I),
    re.compile(r"/job/[^/?#]+$", re.I),
    re.compile(r"/jobs/detail/", re.I),
    re.compile(r"/campus/detail", re.I),
    re.compile(r"jobdesc\.html", re.I),
    re.compile(r"[?&]positionId=", re.I),
    re.compile(r"[?&]jobId=", re.I),
    re.compile(r"/referral/.*/position/share", re.I),
    re.compile(r"/share-position", re.I),
    re.compile(r"/login\.html", re.I),
    re.compile(r"#/job/", re.I),
]

COMPANY_ALIASES = {
    "腾讯": ["腾讯", "tencent", "qq.com"],
    "字节跳动": ["字节跳动", "bytedance", "toutiao", "抖音", "tiktok"],
    "阿里巴巴": ["阿里巴巴", "alibaba", "阿里云", "淘天"],
    "蚂蚁集团": ["蚂蚁集团", "antgroup", "蚂蚁"],
    "美团": ["美团", "meituan", "三快"],
    "拼多多": ["拼多多", "pdd", "pddglobal"],
    "京东": ["京东", "jd.com", "jdyoung", "tgt", "tet"],
    "百度": ["百度", "baidu"],
    "网易": ["网易", "netease", "163.com", "雷火"],
    "滴滴": ["滴滴", "didiglobal", "小桔"],
    "快手": ["快手", "kuaishou", "达佳"],
    "携程": ["携程", "ctrip", "trip.com"],
    "小红书": ["小红书", "xiaohongshu", "行吟"],
    "BOSS直聘": ["BOSS直聘", "zhipin", "boss"],
    "哔哩哔哩": ["哔哩哔哩", "bilibili", "b站"],
    "米哈游": ["米哈游", "mihoyo"],
    "得物": ["得物", "poizon", "dewu"],
}

COMPANY_CRAWLER_KEYS = {
    "腾讯": "tencent",
    "字节跳动": "bytedance",
    "阿里巴巴": "alibaba",
    "蚂蚁集团": "talent.antgroup.com",
    "美团": "meituan",
    "拼多多": "pddglobalhr",
    "京东": "campus.jd",
    "百度": "baidu",
    "网易": "campus.163.com",
    "滴滴": "didiglobal",
    "快手": "campus.kuaishou.cn",
    "携程": "ctrip",
    "小红书": "xiaohongshu",
    "BOSS直聘": "zhipin.com/campus",
    "哔哩哔哩": "bilibili",
    "米哈游": "jobs.mihoyo.com",
    "得物": "campus.dewu.com",
}

GENERIC_LEGACY_CRAWLER_KEYS = {
    "feishu",
    "app.mokahr.com/campus_apply",
    "app.mokahr.com/campus-recruitment",
}


@dataclass(frozen=True)
class InternetCrawlTarget:
    tier: str
    company: str
    display_name: str
    url: str
    target_type: str
    source: str
    platform: str
    reason: str


@dataclass
class InternetCrawlResult:
    tier: str
    company: str
    display_name: str
    url: str
    status: str
    fetched_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    error: str = ""
    source: str = ""
    platform: str = ""


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_json_list(value: str) -> list[str]:
    try:
        payload = json.loads(value or "[]")
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _normalize_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    parsed = urlparse(text)
    if not parsed.netloc:
        return ""
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or ""
    return urlunparse((scheme, netloc, path, "", parsed.query, parsed.fragment))


def _is_skipped_url(url: str) -> bool:
    normalized = _normalize_url(url)
    if not normalized:
        return True
    parsed = urlparse(normalized)
    if parsed.netloc.lower() in SKIP_URL_HOSTS:
        return True
    lowered = normalized.lower()
    return any(keyword in lowered for keyword in SKIP_URL_KEYWORDS)


def _is_probably_detail_url(url: str) -> bool:
    lowered = (url or "").lower()
    return any(pattern.search(lowered) for pattern in DETAIL_URL_PATTERNS)


def _detect_platform(url: str) -> str:
    lowered = (url or "").lower()
    if "mokahr.com" in lowered or "moka" in lowered:
        return "Moka"
    if "jobs.feishu.cn" in lowered:
        return "Feishu Jobs"
    if "zhiye.com" in lowered:
        return "Zhiye"
    if "hotjob.cn" in lowered:
        return "HotJob"
    if "zhaopin" in lowered:
        return "ZhaoPin"
    if "workday" in lowered:
        return "Workday"
    return "Official"


def _name_matches_company(name: str, company: str) -> bool:
    raw = (name or "").strip()
    if not raw:
        return False
    normalized = normalize_company_for_matching(raw)
    if normalized == company or raw == company:
        return True

    aliases = COMPANY_ALIASES.get(company, [company])
    lowered = raw.lower()
    for alias in aliases:
        alias_text = str(alias).strip()
        if not alias_text:
            continue
        if alias_text.lower() in lowered:
            if company == "京东" and "京东方" in raw:
                continue
            return True
    return False


def _target_type_from_url(url: str) -> str:
    lowered = (url or "").lower()
    if "intern" in lowered or "实习" in lowered:
        return "internship"
    return "campus"


def _add_candidate(
    candidates: dict[tuple[str, str], InternetCrawlTarget],
    *,
    tier: str,
    company: str,
    display_name: str,
    url: str,
    source: str,
    reason: str,
    target_type: str = "",
    allow_detail_url: bool = False,
) -> None:
    normalized = _normalize_url(url)
    if _is_skipped_url(normalized):
        return
    if not allow_detail_url and _is_probably_detail_url(normalized):
        return
    key = (company, normalized)
    existing = candidates.get(key)
    if existing is not None and existing.source == "targets.yaml":
        return
    if existing is not None and source != "targets.yaml":
        return
    candidates[key] = InternetCrawlTarget(
        tier=tier,
        company=company,
        display_name=display_name or company,
        url=normalized,
        target_type=target_type or _target_type_from_url(normalized),
        source=source,
        platform=_detect_platform(normalized),
        reason=reason,
    )


def select_primary_targets(targets: list[InternetCrawlTarget]) -> list[InternetCrawlTarget]:
    grouped: dict[str, list[InternetCrawlTarget]] = {}
    for target in targets:
        grouped.setdefault(target.company, []).append(target)

    selected: list[InternetCrawlTarget] = []
    for company, items in grouped.items():
        kept: list[InternetCrawlTarget] = []
        configured = [item for item in items if item.source == "targets.yaml"]
        if configured:
            kept.extend(configured)
        else:
            kept.extend(sorted(items, key=_target_rank)[:2])

        covered_hosts = {urlparse(item.url).netloc.lower() for item in kept}
        for item in sorted(items, key=_target_rank):
            host = urlparse(item.url).netloc.lower()
            if host in covered_hosts:
                continue
            if item.platform in {"Moka", "Feishu Jobs", "Zhiye", "HotJob"}:
                kept.append(item)
                covered_hosts.add(host)

        selected.extend(kept)

    return sorted(selected, key=lambda item: (item.tier, item.company, _target_rank(item), item.url))


def _target_rank(target: InternetCrawlTarget) -> tuple[int, int, int, int]:
    source_rank = {
        "targets.yaml": 0,
        "company_truth_spring_master.csv": 1,
        "job_truth_spring_master.csv": 2,
    }.get(target.source, 5)
    url = target.url.lower()
    noisy = int(any(token in url for token in ["sessionid=", "sourcetoken=", "recommendcode=", "share", "referral"]))
    specificity = len(url)
    platform_rank = 0 if target.platform == "Official" else 1
    return (source_rank, noisy, platform_rank, specificity)


def load_tier_companies(tiers: Iterable[str] = ("t1", "t2"), config_path: Path = TIER_CONFIG_PATH) -> list[tuple[str, str]]:
    payload = _load_yaml(config_path)
    out: list[tuple[str, str]] = []
    for tier in tiers:
        for company in payload.get(tier, []) or []:
            if company:
                out.append((tier, str(company)))
    return out


def build_internet_targets(
    tiers: Iterable[str] = ("t1", "t2"),
    tier_config_path: Path = TIER_CONFIG_PATH,
    targets_config_path: Path = TARGETS_CONFIG_PATH,
    company_truth_path: Path = COMPANY_TRUTH_PATH,
    job_truth_path: Path = JOB_TRUTH_PATH,
) -> list[InternetCrawlTarget]:
    tier_companies = load_tier_companies(tiers=tiers, config_path=tier_config_path)
    candidates: dict[tuple[str, str], InternetCrawlTarget] = {}

    company_truth_rows = _read_csv(company_truth_path)
    job_truth_rows = _read_csv(job_truth_path)
    targets_payload = _load_yaml(targets_config_path)
    configured_targets = targets_payload.get("targets") or targets_payload.get("sites") or []

    for tier, company in tier_companies:
        for row in company_truth_rows:
            names = [
                row.get("canonical_name", ""),
                row.get("display_name", ""),
                *_parse_json_list(row.get("aliases_json", "")),
                *_parse_json_list(row.get("entity_members_json", "")),
            ]
            if not any(_name_matches_company(name, company) for name in names):
                continue
            for field in ("best_apply_link", "best_announce_link"):
                _add_candidate(
                    candidates,
                    tier=tier,
                    company=company,
                    display_name=row.get("display_name") or row.get("canonical_name") or company,
                    url=row.get(field, ""),
                    source=company_truth_path.name,
                    reason=field,
                )

        for row in job_truth_rows:
            names = [
                row.get("canonical_company_name", ""),
                row.get("parent_company_name", ""),
                row.get("company_name_raw", ""),
                row.get("norm_company_name", ""),
            ]
            if not any(_name_matches_company(name, company) for name in names):
                continue
            _add_candidate(
                candidates,
                tier=tier,
                company=company,
                display_name=row.get("company_name_raw") or company,
                url=row.get("apply_url", ""),
                source=job_truth_path.name,
                reason=f"apply_url:{row.get('link_platform', '')}",
                target_type=row.get("season_normalized") or "",
            )

        for item in configured_targets:
            target_name = str(item.get("name", "")).strip()
            if not _name_matches_company(target_name, company):
                continue
            _add_candidate(
                candidates,
                tier=tier,
                company=company,
                display_name=target_name or company,
                url=str(item.get("url", "") or ""),
                source=targets_config_path.name,
                reason=str(item.get("note", "") or "configured target"),
                target_type=str(item.get("type", "") or ""),
            )

    return sorted(candidates.values(), key=lambda item: (item.tier, item.company, item.source, item.url))


def _configure_legacy_network() -> None:
    proxy_url = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
        or ""
    ).strip()

    # Import lazily so tests can monkeypatch without starting Playwright.
    from app.services.legacy_crawlers import crawler as legacy

    if proxy_url:
        legacy.PROXY = {"server": proxy_url}
        legacy.REQUEST_PROXIES = {"http": proxy_url, "https": proxy_url}
    else:
        legacy.PROXY = None
        legacy.REQUEST_PROXIES = {}


def _select_crawler(company: str, url: str):
    from app.services.legacy_crawlers import crawler as legacy

    lowered = (url or "").lower()
    for key, func in sorted(legacy.SITE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if key in GENERIC_LEGACY_CRAWLER_KEYS:
            continue
        if key in lowered:
            return func

    fallback_key = COMPANY_CRAWLER_KEYS.get(company)
    if fallback_key:
        return legacy.SITE_MAP.get(fallback_key)

    for key, func in sorted(legacy.SITE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if key in lowered:
            return func
    return None


def _parse_datetime(value: Optional[str]):
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19] if "T" in text else text[:10] if len(text) >= 10 else text, fmt)
        except ValueError:
            continue
    return None


def _map_legacy_job(target: InternetCrawlTarget, legacy_job: Any) -> dict[str, Any]:
    job_id = str(getattr(legacy_job, "id", "") or "").strip()
    title = str(getattr(legacy_job, "title", "") or "").strip()
    detail_url = _normalize_url(str(getattr(legacy_job, "url", "") or target.url))
    return {
        "job_id": job_id,
        "source": "internet_official",
        "company": str(getattr(legacy_job, "company", "") or target.company).strip() or target.company,
        "company_type_industry": "互联网",
        "company_tags": target.tier,
        "department": str(getattr(legacy_job, "department", "") or "").strip(),
        "job_title": title,
        "location": str(getattr(legacy_job, "location", "") or "").strip() or "未知",
        "major_req": "",
        "job_req": str(getattr(legacy_job, "requirements", "") or "").strip(),
        "job_duty": str(getattr(legacy_job, "description", "") or "").strip(),
        "application_status": "待申请",
        "job_stage": str(getattr(legacy_job, "job_type", "") or target.target_type or "campus").strip(),
        "source_config_id": f"internet:{target.tier}:{target.company}:{target.url}",
        "publish_date": _parse_datetime(getattr(legacy_job, "publish_date", "")),
        "deadline": _parse_datetime(getattr(legacy_job, "deadline", "")),
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }


def _valid_mapped_job(mapped: dict[str, Any]) -> bool:
    return bool(mapped.get("job_id") and mapped.get("job_title") and mapped.get("detail_url"))


def crawl_internet_targets(
    db: Session,
    targets: list[InternetCrawlTarget],
    dry_run: bool = False,
    max_pages: Optional[int] = None,
) -> list[InternetCrawlResult]:
    _configure_legacy_network()

    from playwright.sync_api import sync_playwright
    from app.services.legacy_crawlers import crawler as legacy

    existing_jobs: dict[str, Job] = {}
    for job in db.query(Job).all():
        if getattr(job, "job_id", ""):
            existing_jobs[job.job_id] = job

    results: list[InternetCrawlResult] = []
    seen_target_jobs: set[tuple[str, str]] = set()
    original_legacy_max_pages = getattr(legacy, "MAX_PAGES", None)
    if max_pages:
        legacy.MAX_PAGES = int(max_pages)

    try:
        with sync_playwright() as playwright:
            browser = legacy.make_browser(playwright)
            try:
                for target in targets:
                    fn = _select_crawler(target.company, target.url)
                    if fn is None:
                        results.append(InternetCrawlResult(
                            tier=target.tier,
                            company=target.company,
                            display_name=target.display_name,
                            url=target.url,
                            status="unsupported",
                            error="No legacy crawler matched target URL",
                            source=target.source,
                            platform=target.platform,
                        ))
                        continue

                    context, page = legacy.new_page(browser)
                    try:
                        runtime_target = {
                            "name": target.display_name,
                            "url": target.url,
                            "type": target.target_type,
                        }
                        if max_pages:
                            runtime_target["max_pages"] = int(max_pages)

                        legacy_jobs = fn(page, runtime_target)
                        fetched_count = 0
                        new_count = 0
                        updated_count = 0

                        for legacy_job in legacy_jobs:
                            mapped = _map_legacy_job(target, legacy_job)
                            if not _valid_mapped_job(mapped):
                                continue
                            dedupe_key = (mapped["job_id"], mapped["detail_url"])
                            if dedupe_key in seen_target_jobs:
                                continue
                            seen_target_jobs.add(dedupe_key)
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

                        results.append(InternetCrawlResult(
                            tier=target.tier,
                            company=target.company,
                            display_name=target.display_name,
                            url=target.url,
                            status="success" if fetched_count else "empty",
                            fetched_count=fetched_count,
                            new_count=new_count,
                            updated_count=updated_count,
                            source=target.source,
                            platform=target.platform,
                        ))
                    except Exception as exc:
                        if not dry_run:
                            db.rollback()
                        results.append(InternetCrawlResult(
                            tier=target.tier,
                            company=target.company,
                            display_name=target.display_name,
                            url=target.url,
                            status="failed",
                            error=str(exc)[:500],
                            source=target.source,
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


def summarize_results(results: list[InternetCrawlResult]) -> dict[str, Any]:
    by_company: dict[str, dict[str, Any]] = {}
    for item in results:
        entry = by_company.setdefault(item.company, {
            "tier": item.tier,
            "targets": 0,
            "success_targets": 0,
            "failed_targets": 0,
            "empty_targets": 0,
            "unsupported_targets": 0,
            "fetched_count": 0,
            "new_count": 0,
            "updated_count": 0,
        })
        entry["targets"] += 1
        entry["fetched_count"] += item.fetched_count
        entry["new_count"] += item.new_count
        entry["updated_count"] += item.updated_count
        if item.status == "success":
            entry["success_targets"] += 1
        elif item.status == "empty":
            entry["empty_targets"] += 1
        elif item.status == "unsupported":
            entry["unsupported_targets"] += 1
        else:
            entry["failed_targets"] += 1

    return {
        "target_count": len(results),
        "fetched_count": sum(item.fetched_count for item in results),
        "new_count": sum(item.new_count for item in results),
        "updated_count": sum(item.updated_count for item in results),
        "failed_count": sum(1 for item in results if item.status == "failed"),
        "empty_count": sum(1 for item in results if item.status == "empty"),
        "unsupported_count": sum(1 for item in results if item.status == "unsupported"),
        "companies": by_company,
    }
