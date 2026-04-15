from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse, urlunparse

import requests
import yaml
from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_truth_merge import normalize_company_for_matching
from app.services.job_merge import merge_job_fields


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"
TIER_CONFIG_PATH = BACKEND_DIR / "config" / "tiered_consumer_companies.yaml"
COMPANY_TRUTH_PATH = PROJECT_ROOT / "data" / "exports" / "company_truth_spring_master.csv"
JOB_TRUTH_PATH = PROJECT_ROOT / "data" / "exports" / "job_truth_spring_master.csv"

SKIP_URL_HOSTS = {
    "mp.weixin.qq.com",
    "docs.qq.com",
    "alidocs.dingtalk.com",
    "young.yingjiesheng.com",
    "q.yingjiesheng.com",
    "www.shixiseng.com",
    "shixiseng.com",
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

COMPANY_ALIASES = {
    "宝洁": ["宝洁", "宝洁中国", "procter", "p&g", "pg.com.cn"],
    "联合利华": ["联合利华", "unilever"],
    "欧莱雅": ["欧莱雅", "loreal", "l'oréal"],
    "玛氏": ["玛氏", "玛氏中国", "mars"],
    "雅诗兰黛": ["雅诗兰黛", "雅诗兰黛集团", "estee lauder", "elc"],
    "亿滋": ["亿滋", "mondelez"],
    "雀巢": ["雀巢", "雀巢中国", "nestle"],
    "强生": ["强生", "jnj", "johnson & johnson", "johnson and johnson"],
    "百胜": ["百胜", "百胜中国", "yum", "yum china"],
    "LVMH": ["lvmh"],
    "耐克": ["耐克", "nike"],
    "可口可乐": ["可口可乐", "太古可口可乐", "coca-cola", "coca cola", "swire coca cola"],
    "达能": ["达能", "danone"],
    "资生堂": ["资生堂", "shiseido"],
    "高露洁": ["高露洁", "colgate", "colgate-palmolive", "colpal"],
    "金佰利": ["金佰利", "kimberly", "kimberly-clark", "k-c"],
    "默克": ["默克", "默克中国", "merck"],
    "Wayfair": ["wayfair"],
    "索尼": ["索尼", "sony"],
    "宜家": ["宜家", "ikea"],
    "乐高": ["乐高", "lego"],
    "爱立信": ["爱立信", "ericsson"],
    "沃尔沃": ["沃尔沃", "volvo"],
}

MANUAL_TARGETS = {
    "雀巢": [
        "https://www.nestlecareers.cn/zh-hans/trainee-programme",
    ],
    "百胜": [
        "http://careers.yumchina.com",
        "http://campus.51job.com/yumchina",
    ],
    "LVMH": [
        "https://www.lvmh.cn/job-offers",
        "https://www.lvmh.com/en/join-us/lvmh-graduate-programs/lvmh-china-retail-management-trainee-program",
    ],
    "耐克": ["https://careers.nike.com/zh-cn/"],
    "资生堂": [],
    "默克": [
        "https://careers.merckgroup.com/cn/zh/",
        "https://careers.merckgroup.com/cn/zh/students-and-graduates",
    ],
    "Wayfair": [
        "https://www.wayfair.com/careers/jobs",
        "https://www.aboutwayfair.com/careers/early-talent",
    ],
    "索尼": ["https://www.sony.com.cn/careers/"],
    "宜家": ["https://www.ikea.cn/cn/en/this-is-ikea/work-with-us/"],
    "乐高": ["https://www.lego.com/zh-cn/careers"],
    "沃尔沃": [
        "https://jobs.volvocars.com/",
        "https://www.volvocars.com/intl/careers/graduates/",
    ],
}

MANUAL_OVERRIDE_COMPANIES = {
    "雀巢",
}


@dataclass(frozen=True)
class ConsumerTarget:
    tier: str
    company: str
    display_name: str
    url: str
    target_type: str
    source: str
    platform: str
    reason: str


@dataclass
class ConsumerCrawlResult:
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
    if "mokahr.com" in lowered or "moka" in lowered:
        return "Moka"
    if "jobs.feishu.cn" in lowered:
        return "Feishu Jobs"
    if "zhiye.com" in lowered:
        return "Zhiye"
    if "hotjob.cn" in lowered:
        return "HotJob"
    if "zhaopin" in lowered:
        return "Zhaopin"
    if "51job.com" in lowered or "51job" in lowered:
        return "51job"
    if "moseeker.com" in lowered:
        return "Moseeker"
    if "myworkdayjobs.com" in lowered or "workday" in lowered or "wd1." in lowered:
        return "Workday"
    if "phenom" in lowered or "careers.pg.com.cn" in lowered:
        return "Phenom"
    return "Official"


def _name_matches_company(name: str, company: str) -> bool:
    raw = (name or "").strip()
    if not raw:
        return False
    normalized = normalize_company_for_matching(raw)
    if normalized == company or raw == company:
        return True
    for alias in COMPANY_ALIASES.get(company, [company]):
        alias_text = str(alias).strip().lower()
        if alias_text and alias_text in raw.lower():
            if company == "达能" and "运达" in raw:
                continue
            if company == "爱立信" and "立信" in raw and "爱立信" not in raw:
                continue
            return True
    return False


def _target_type_from_url(url: str) -> str:
    lowered = (url or "").lower()
    if "intern" in lowered or "实习" in lowered:
        return "internship"
    return "campus"


def _add_candidate(
    candidates: dict[tuple[str, str], ConsumerTarget],
    *,
    tier: str,
    company: str,
    display_name: str,
    url: str,
    source: str,
    reason: str,
) -> None:
    normalized = _normalize_url(url)
    if _is_skipped_url(normalized):
        return
    key = (company, normalized)
    if key in candidates:
        return
    candidates[key] = ConsumerTarget(
        tier=tier,
        company=company,
        display_name=display_name or company,
        url=normalized,
        target_type=_target_type_from_url(normalized),
        source=source,
        platform=_detect_platform(normalized),
        reason=reason,
    )


def _target_rank(target: ConsumerTarget) -> tuple[int, int, int]:
    source_rank = {
        "company_truth_spring_master.csv": 0,
        "job_truth_spring_master.csv": 1,
        "manual": 2,
    }.get(target.source, 9)
    if target.source == "manual" and target.company in MANUAL_OVERRIDE_COMPANIES:
        source_rank = -1
    platform_rank = 0 if target.platform == "Official" else 1
    return (source_rank, platform_rank, len(target.url))


def load_tier_companies(
    tiers: Iterable[str] = ("t0", "t1", "shanghai_picks"),
    config_path: Path = TIER_CONFIG_PATH,
) -> list[tuple[str, str]]:
    payload = _load_yaml(config_path)
    out: list[tuple[str, str]] = []
    for tier in tiers:
        for company in payload.get(tier, []) or []:
            out.append((tier, str(company)))
    return out


def build_consumer_targets(
    tiers: Iterable[str] = ("t0", "t1", "shanghai_picks"),
    tier_config_path: Path = TIER_CONFIG_PATH,
    company_truth_path: Path = COMPANY_TRUTH_PATH,
    job_truth_path: Path = JOB_TRUTH_PATH,
) -> list[ConsumerTarget]:
    tier_companies = load_tier_companies(tiers=tiers, config_path=tier_config_path)
    company_truth_rows = _read_csv(company_truth_path)
    job_truth_rows = _read_csv(job_truth_path)
    candidates: dict[tuple[str, str], ConsumerTarget] = {}

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
            )

        for url in MANUAL_TARGETS.get(company, []):
            _add_candidate(
                candidates,
                tier=tier,
                company=company,
                display_name=company,
                url=url,
                source="manual",
                reason="manual target",
            )

    return sorted(candidates.values(), key=lambda item: (item.tier, item.company, _target_rank(item), item.url))


def select_primary_targets(targets: list[ConsumerTarget]) -> list[ConsumerTarget]:
    grouped: dict[str, list[ConsumerTarget]] = {}
    for target in targets:
        grouped.setdefault(target.company, []).append(target)

    selected: list[ConsumerTarget] = []
    for company, items in grouped.items():
        kept: list[ConsumerTarget] = sorted(items, key=_target_rank)[:2]
        covered_hosts = {urlparse(item.url).netloc.lower() for item in kept}
        for item in sorted(items, key=_target_rank):
            host = urlparse(item.url).netloc.lower()
            if host in covered_hosts:
                continue
            if item.platform in {"Moka", "Zhiye", "HotJob", "Workday", "Moseeker"}:
                kept.append(item)
                covered_hosts.add(host)
        selected.extend(kept)
    return sorted(selected, key=lambda item: (item.tier, item.company, _target_rank(item), item.url))


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


def _stable_id(prefix: str, target: ConsumerTarget, raw_id: str, title: str, detail_url: str) -> str:
    material = "|".join([target.tier, target.company, raw_id, title, detail_url])
    digest = hashlib.md5(material.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _map_legacy_job(target: ConsumerTarget, legacy_job: Any) -> dict[str, Any]:
    raw_id = str(getattr(legacy_job, "id", "") or "").strip()
    title = str(getattr(legacy_job, "title", "") or "").strip()
    detail_url = _normalize_url(str(getattr(legacy_job, "url", "") or target.url))
    job_id = raw_id or _stable_id("consumer", target, raw_id, title, detail_url)
    return {
        "job_id": job_id,
        "source": "consumer_foreign_official",
        "company": str(getattr(legacy_job, "company", "") or target.company).strip() or target.company,
        "company_type_industry": "消费/外企",
        "company_tags": target.tier,
        "department": str(getattr(legacy_job, "department", "") or "").strip(),
        "job_title": title,
        "location": str(getattr(legacy_job, "location", "") or "").strip() or "未知",
        "major_req": "",
        "job_req": str(getattr(legacy_job, "requirements", "") or "").strip(),
        "job_duty": str(getattr(legacy_job, "description", "") or "").strip(),
        "application_status": "待申请",
        "job_stage": str(getattr(legacy_job, "job_type", "") or target.target_type or "campus").strip(),
        "source_config_id": f"consumer:{target.tier}:{target.company}:{target.url}",
        "publish_date": _parse_datetime(getattr(legacy_job, "publish_date", "")),
        "deadline": _parse_datetime(getattr(legacy_job, "deadline", "")),
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }


def _valid_mapped_job(mapped: dict[str, Any]) -> bool:
    return bool(mapped.get("job_id") and mapped.get("job_title") and mapped.get("detail_url"))


def _select_legacy_crawler(target: ConsumerTarget):
    from app.services.legacy_crawlers import crawler as legacy

    if target.platform == "HotJob":
        return None
    lowered = target.url.lower()
    for key, func in sorted(legacy.SITE_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if key in GENERIC_LEGACY_CRAWLER_KEYS:
            continue
        if key in lowered:
            return func
    if target.platform == "Zhiye":
        return legacy.crawl_zhiye_campus
    return None


def _crawl_generic(page: Any, target: ConsumerTarget, max_pages: Optional[int] = None):
    from app.services.legacy_crawlers import crawler as legacy

    parsed = urlparse(target.url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    runtime_target = {"name": target.company, "url": target.url, "type": target.target_type}
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
            'a[href*="career"]',
            'a[href*="detail"]',
        ],
        scroll=True,
        timeout=45000,
        extra_sleep=3,
        response_keywords=["job", "position", "post", "recruit", "campus", "career", "api"],
        max_pages=max_pages,
    )


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


def _crawl_zhaopin_grace(target: ConsumerTarget, max_pages: Optional[int] = None):
    from app.services.legacy_crawlers import crawler as legacy

    headers = {
        "User-Agent": legacy.UA,
        "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        html_resp = requests.get(target.url, headers=headers, proxies=legacy.REQUEST_PROXIES, timeout=30)
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
            title = str(item.get("jobName") or item.get("positionName") or item.get("name") or item.get("title") or "").strip()
            if not title:
                continue
            job_key = str(item.get("jobNumber") or item.get("jobId") or item.get("positionId") or item.get("id") or "").strip()
            if job_key in seen_ids:
                continue
            seen_ids.add(job_key)
            jobs.append(legacy.JobInfo(
                id=job_key,
                company=target.company,
                title=title,
                location=str(item.get("cityName") or item.get("workCity") or item.get("workLocation") or "未知").strip() or "未知",
                department=str(item.get("orgName") or item.get("departmentName") or item.get("department") or "").strip(),
                job_type=target.target_type,
                url=str(item.get("positionURL") or item.get("positionUrl") or target.url).strip() or target.url,
                publish_date=str(item.get("publishDate") or item.get("createDate") or "").strip() or None,
                deadline=str(item.get("endDate") or item.get("deadline") or "").strip() or None,
                description=str(item.get("jobDescription") or item.get("description") or "").strip() or None,
                requirements=str(item.get("jobRequirement") or item.get("requirement") or "").strip() or None,
            ))
            page_added += 1
        if page_added == 0:
            break
    if jobs:
        return jobs
    return []


def _crawl_workday_embed(target: ConsumerTarget):
    from app.services.legacy_crawlers import crawler as legacy

    try:
        resp = requests.get(
            target.url,
            headers={"User-Agent": legacy.UA, "Accept": "text/html,application/xhtml+xml"},
            proxies=legacy.REQUEST_PROXIES,
            timeout=30,
        )
        resp.raise_for_status()
    except Exception:
        return None

    text = resp.text
    matches = re.finditer(
        r'"applyUrl":"(?P<apply>https:\\/\\/[^"]+?)".*?"title":"(?P<title>[^"]+?)".*?"locationsText":"(?P<loc>[^"]*?)".*?"postedDate":"(?P<posted>[^"]*?)".*?"bulletFields":(?P<fields>\[[^\]]*\]).*?"reqId":"(?P<req>[^"]+?)"',
        text,
    )
    jobs = []
    seen: set[str] = set()
    for match in matches:
        apply_url = match.group("apply").replace("\\/", "/")
        title = bytes(match.group("title"), "utf-8").decode("unicode_escape")
        location = bytes(match.group("loc"), "utf-8").decode("unicode_escape")
        req_id = match.group("req")
        if req_id in seen:
            continue
        seen.add(req_id)
        jobs.append(legacy.JobInfo(
            id=req_id,
            company=target.company,
            title=title,
            location=location or "未知",
            department="",
            job_type=target.target_type,
            url=apply_url or target.url,
            publish_date=match.group("posted") or None,
            description=None,
            requirements=None,
        ))
    if jobs:
        return jobs
    return None


def _extract_hotjob_suite(target: ConsumerTarget) -> str:
    match = re.search(r"/(SU[0-9a-zA-Z]+)/", target.url)
    if match:
        return match.group(1)
    try:
        resp = requests.get(target.url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception:
        return ""
    html_text = resp.text
    match = re.search(r"(SU[0-9a-zA-Z]{10,})", html_text)
    return match.group(1) if match else ""


def _crawl_hotjob_generic(target: ConsumerTarget, max_pages: Optional[int] = None):
    from app.services.legacy_crawlers import crawler as legacy

    suite = _extract_hotjob_suite(target)
    if not suite:
        return None
    recruit_types = ["1", "3", "2"]
    jobs: list[Any] = []
    seen: set[str] = set()
    page_limit = max(1, int(max_pages or 20))
    for recruit_type in recruit_types:
        total_pages = 1
        current_page = 1
        while current_page <= total_pages and current_page <= page_limit:
            resp = requests.post(
                f"https://wecruit.hotjob.cn/wecruit/positionInfo/listPosition/{suite}",
                headers={
                    "User-Agent": legacy.UA,
                    "Referer": target.url,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                },
                proxies=legacy.REQUEST_PROXIES,
                timeout=30,
                params={"iSaJAx": "isAjax", "request_locale": "zh_CN", "t": int(datetime.utcnow().timestamp() * 1000)},
                data={"isFrompb": "true", "recruitType": recruit_type, "pageSize": "15", "currentPage": str(current_page)},
            )
            data = (resp.json() or {}).get("data") or {}
            page_form = data.get("pageForm") or {}
            rows = page_form.get("pageData") or []
            total_pages = int(page_form.get("totalPage") or 1)
            if not rows:
                break
            for item in rows:
                title = str(item.get("postName") or "").strip()
                if not title:
                    continue
                pid = str(item.get("postId") or item.get("id") or "").strip()
                if pid in seen:
                    continue
                seen.add(pid)
                if recruit_type == "1":
                    detail_url = f"https://wecruit.hotjob.cn/{suite}/pb/school.html#/post?postId={pid}" if pid else target.url
                elif recruit_type == "3":
                    detail_url = f"https://wecruit.hotjob.cn/{suite}/pb/interns.html#/post?postId={pid}" if pid else target.url
                else:
                    detail_url = f"https://wecruit.hotjob.cn/{suite}/pb/social.html#/post?postId={pid}" if pid else target.url
                merged = " ".join([title, str(item.get('postTypeName') or ''), recruit_type])
                job_stage = "internship" if ("实习" in merged or recruit_type == "3") else target.target_type
                jobs.append(legacy.JobInfo(
                    id=pid,
                    company=target.company,
                    title=title,
                    location=str(item.get("workPlaceStr") or "未知").strip() or "未知",
                    department=str(item.get("postTypeName") or item.get("postType") or "").strip(),
                    job_type=job_stage,
                    url=detail_url,
                    publish_date=str(item.get("publishDate") or item.get("publishFirstDate") or "").strip() or None,
                    deadline=str(item.get("endDate") or "").strip() or None,
                    description=str(item.get("responsibility") or item.get("description") or "").strip() or None,
                    requirements=str(item.get("subject") or "").strip() or None,
                ))
            current_page += 1
    return jobs


def crawl_consumer_targets(
    db: Session,
    targets: list[ConsumerTarget],
    dry_run: bool = False,
    max_pages: Optional[int] = None,
) -> list[ConsumerCrawlResult]:
    _configure_legacy_network()

    from playwright.sync_api import sync_playwright
    from app.services.legacy_crawlers import crawler as legacy

    existing_jobs: dict[str, Job] = {}
    for job in db.query(Job).all():
        if getattr(job, "job_id", ""):
            existing_jobs[job.job_id] = job

    results: list[ConsumerCrawlResult] = []
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
                        special_jobs = None
                        if target.platform == "Zhaopin":
                            special_jobs = _crawl_zhaopin_grace(target, max_pages=max_pages)
                        elif target.platform == "HotJob":
                            special_jobs = _crawl_hotjob_generic(target, max_pages=max_pages)
                        elif target.platform == "Workday" or "myworkdayjobs.com" in target.url.lower():
                            special_jobs = _crawl_workday_embed(target)

                        if special_jobs is not None:
                            legacy_jobs = special_jobs
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
                        results.append(ConsumerCrawlResult(
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
                        results.append(ConsumerCrawlResult(
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


def summarize_results(results: list[ConsumerCrawlResult]) -> dict[str, Any]:
    by_tier: dict[str, dict[str, Any]] = {}
    by_company: dict[str, dict[str, Any]] = {}
    for item in results:
        tier_entry = by_tier.setdefault(item.tier, {
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
            "targets": 0,
            "success_targets": 0,
            "failed_targets": 0,
            "empty_targets": 0,
            "fetched_count": 0,
            "new_count": 0,
            "updated_count": 0,
        })
        for entry in (tier_entry, company_entry):
            entry["targets"] += 1
            entry["fetched_count"] += item.fetched_count
            entry["new_count"] += item.new_count
            entry["updated_count"] += item.updated_count
        if item.status == "success":
            tier_entry["success_targets"] += 1
            company_entry["success_targets"] += 1
        elif item.status == "failed":
            tier_entry["failed_targets"] += 1
            company_entry["failed_targets"] += 1
        else:
            tier_entry["empty_targets"] += 1
            company_entry["empty_targets"] += 1

    return {
        "target_count": len(results),
        "fetched_count": sum(item.fetched_count for item in results),
        "new_count": sum(item.new_count for item in results),
        "updated_count": sum(item.updated_count for item in results),
        "failed_count": sum(1 for item in results if item.status == "failed"),
        "empty_count": sum(1 for item in results if item.status == "empty"),
        "success_count": sum(1 for item in results if item.status == "success"),
        "tiers": by_tier,
        "companies": by_company,
    }
