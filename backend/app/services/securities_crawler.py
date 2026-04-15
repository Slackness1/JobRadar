"""
券商校园招聘爬虫
基于海投网搜索特定券商的校园招聘岗位
"""
import hashlib
import html
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
import yaml
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from app.models import Job

# 目标券商列表（A档和A-档）
TARGET_COMPANIES = {
    # A档券商
    "中金公司",
    "中信证券",
    "华泰证券",
    "中信建投",
    "国泰君安",
    "海通证券",
    "国泰海通",

    # A-档券商
    "招商证券",
    "申万宏源",
    "广发证券",
    "中国银河",
    "国信证券",

    # B档券商（备用）
    "东方证券",
    "兴业证券",
    "光大证券",
    "中泰证券",
    "国金证券",
    "安信证券",
}

# 海投网搜索URL（支持按公司搜索）
SEARCH_URL = "https://xyzp.haitou.cc/search/"
DETAIL_URL = "https://xyzp.haitou.cc/article/{article_id}.html"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.S,
)
_DATE_RE = re.compile(r"(20\d{2})[.\-/年](\d{1,2})[.\-/月](\d{1,2})")


def extract_next_data_json(page_html: str) -> Dict[str, Any]:
    match = _NEXT_DATA_RE.search(page_html)
    if not match:
        raise ValueError("__NEXT_DATA__ payload not found")
    return json.loads(match.group(1))


def _to_datetime(year: str, month: str, day: str) -> Optional[datetime]:
    try:
        return datetime(int(year), int(month), int(day))
    except ValueError:
        return None


def parse_time_range(time_text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    if not time_text:
        return None, None
    matches = _DATE_RE.findall(time_text)
    if not matches:
        return None, None
    dates = [_to_datetime(y, m, d) for y, m, d in matches]
    dates = [d for d in dates if d is not None]
    if not dates:
        return None, None
    if len(dates) == 1:
        return dates[0], None
    return dates[0], dates[-1]


def _strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", raw_html)
    return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()


def split_job_text(job_text: str) -> Tuple[str, str]:
    text = (job_text or "").replace("\r", "\n")
    text = re.sub(r"\n+", "\n", text).strip()

    duty = ""
    req = ""

    if "岗位要求" in text:
        before, after = text.split("岗位要求", 1)
        req = after.lstrip("：: \n").strip()
        if "岗位职责" in before:
            duty = before.split("岗位职责", 1)[1].lstrip("：: \n").strip()
        else:
            duty = before.strip()
    elif "任职要求" in text:
        before, after = text.split("任职要求", 1)
        req = after.lstrip("：: \n").strip()
        if "岗位职责" in before:
            duty = before.split("岗位职责", 1)[1].lstrip("：: \n").strip()
        else:
            duty = before.strip()
    else:
        if "岗位职责" in text:
            duty = text.split("岗位职责", 1)[1].lstrip("：: \n").strip()
        else:
            duty = text

    return duty, req


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _infer_stage(*texts: str) -> str:
    merged = " ".join(_safe_text(t) for t in texts)
    if "实习" in merged:
        return "internship"
    return "campus"


def _build_job_id(detail_url: str, job_title: str) -> str:
    raw = f"securities_haitou|{detail_url}|{job_title}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:24]


def _is_target_company(company_name: str) -> bool:
    """检查是否是目标券商"""
    company_name = _safe_text(company_name)
    for target in TARGET_COMPANIES:
        if target in company_name or company_name in target:
            return True
    return False


def _fetch_next_data(session: requests.Session, url: str, timeout: int = 30) -> Dict[str, Any]:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return extract_next_data_json(response.text)


def _extract_locations(detail: Dict[str, Any], list_item: Dict[str, Any], detail_job: Dict[str, Any]) -> str:
    city_list = detail_job.get("cityList") or detail.get("cityList") or []
    names = []
    for city in city_list:
        if isinstance(city, dict):
            name = city.get("name")
            if name:
                names.append(str(name).strip())
    if names:
        return ",".join(dict.fromkeys(names))

    fallback = _safe_text(detail.get("invoiceCity")) or _safe_text(list_item.get("city"))
    return fallback


def _build_records_from_detail(
    list_item: Dict[str, Any],
    detail: Dict[str, Any],
    detail_jobs: List[Dict[str, Any]],
    detail_url: str,
) -> List[Dict[str, Any]]:
    time_text = _safe_text(detail.get("time")) or _safe_text(list_item.get("time"))
    start_dt, end_dt = parse_time_range(time_text)

    pub_time = _safe_text(detail.get("pubTime"))
    if pub_time:
        try:
            start_dt = datetime.strptime(pub_time[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            pass

    company = _safe_text(detail.get("coNameS")) or _safe_text(detail.get("coName")) or _safe_text(list_item.get("name"))
    article_tags = _safe_text(detail.get("articleTagStr"))
    detail_id = _safe_text(detail.get("id"))

    records: List[Dict[str, Any]] = []

    if not detail_jobs:
        fallback_title = _safe_text(detail.get("title")) or _safe_text(list_item.get("name"))
        desc_text = _strip_html(_safe_text(detail.get("desc")))
        duty, req = split_job_text(desc_text)
        records.append(
            {
                "job_id": _build_job_id(detail_url, fallback_title),
                "source": "haitou_securities",
                "company": company,
                "company_type_industry": "券商",
                "company_tags": article_tags,
                "department": company,
                "job_title": fallback_title,
                "location": _safe_text(detail.get("invoiceCity")) or _safe_text(list_item.get("city")),
                "major_req": article_tags,
                "job_req": req,
                "job_duty": duty,
                "application_status": "待申请",
                "job_stage": _infer_stage(fallback_title, detail.get("title")),
                "source_config_id": f"securities_haitou:{detail_id}",
                "publish_date": start_dt,
                "deadline": end_dt,
                "detail_url": detail_url,
                "scraped_at": datetime.utcnow(),
            }
        )
        return records

    for detail_job in detail_jobs:
        if not isinstance(detail_job, dict):
            continue

        job_title = _safe_text(detail_job.get("title")) or _safe_text(detail.get("title"))
        job_text = _safe_text(detail_job.get("jobDuty"))
        duty, req = split_job_text(job_text)
        tags = detail_job.get("tags") or []
        major_req = article_tags
        if isinstance(tags, list) and tags:
            major_req = ",".join(str(x).strip() for x in tags if str(x).strip())

        records.append(
            {
                "job_id": _build_job_id(detail_url, job_title),
                "source": "haitou_securities",
                "company": company,
                "company_type_industry": "券商",
                "company_tags": article_tags,
                "department": company,
                "job_title": job_title,
                "location": _extract_locations(detail, list_item, detail_job),
                "major_req": major_req,
                "job_req": req,
                "job_duty": duty,
                "application_status": "待申请",
                "job_stage": _infer_stage(job_title, detail.get("title")),
                "source_config_id": f"securities_haitou:{detail_id}",
                "publish_date": start_dt,
                "deadline": end_dt,
                "detail_url": detail_url,
                "scraped_at": datetime.utcnow(),
            }
        )

    return records


def crawl_securities_records(max_pages: int = 50) -> List[Dict[str, Any]]:
    """爬取券商校园招聘数据"""
    session = requests.Session()
    records: List[Dict[str, Any]] = []
    visited_detail_urls = set()
    all_companies_seen = set()

    for page in range(1, max_pages + 1):
        list_url = f"{SEARCH_URL}p{page}/"
        try:
            list_payload = _fetch_next_data(session, list_url)
        except (RequestException, ValueError, json.JSONDecodeError) as e:
            print(f"获取第{page}页失败: {e}")
            break

        page_props = list_payload.get("props", {}).get("pageProps", {})
        list_jobs = page_props.get("listJob") or []
        if not list_jobs:
            print(f"第{page}页无数据，停止爬取")
            break

        print(f"\n第{page}页共有 {len(list_jobs)} 条招聘信息")

        # 首先收集这一页所有的公司名称
        page_companies = set()
        for list_item in list_jobs:
            if isinstance(list_item, dict):
                company_name = _safe_text(list_item.get("name"))
                if company_name:
                    page_companies.add(company_name)

        print(f"第{page}页公司列表: {sorted(page_companies)}")
        all_companies_seen.update(page_companies)

        # 只处理目标券商
        for list_item in list_jobs:
            if not isinstance(list_item, dict):
                continue

            article_id = list_item.get("id")
            if not article_id:
                continue

            # 检查公司名称是否匹配目标券商
            company_name = _safe_text(list_item.get("name"))
            if not _is_target_company(company_name):
                continue

            print(f"  找到目标券商: {company_name}")

            detail_url = DETAIL_URL.format(article_id=article_id)
            if detail_url in visited_detail_urls:
                continue
            visited_detail_urls.add(detail_url)

            try:
                detail_payload = _fetch_next_data(session, detail_url)
            except (RequestException, ValueError, json.JSONDecodeError) as e:
                print(f"  获取详情失败 {detail_url}: {e}")
                continue

            detail_props = detail_payload.get("props", {}).get("pageProps", {})
            detail = detail_props.get("detail") or {}
            detail_jobs = detail_props.get("listJob") or detail.get("jobList") or []

            detail_records = _build_records_from_detail(list_item, detail, detail_jobs, detail_url)
            records.extend(detail_records)
            time.sleep(0.2)  # 稍微降低频率

            print(f"  已爬取 {company_name} 的岗位，本页新增 {len(detail_records)} 条")

        total = page_props.get("total")
        size = page_props.get("size")
        current_page = page_props.get("page") or page
        try:
            total_int = int(total)
            size_int = int(size)
            current_int = int(current_page)
            if size_int > 0:
                total_pages = (total_int + size_int - 1) // size_int
                print(f"进度: {current_int}/{total_pages} 页")
                if current_int >= total_pages:
                    break
        except (TypeError, ValueError):
            pass

    print(f"\n爬取完成，共看到 {len(all_companies_seen)} 家公司")
    print(f"所有公司: {sorted(all_companies_seen)}")

    return records


def run_securities_crawl(db: Session, existing_jobs: Dict[str, Job], max_pages: int = 50) -> Tuple[int, int]:
    """运行券商爬虫"""
    print("开始爬取券商校园招聘数据...")
    records = crawl_securities_records(max_pages=max_pages)
    total_fetched = len(records)
    new_count = 0

    print(f"共获取 {total_fetched} 条岗位记录")

    for mapped in records:
        job_id = mapped.get("job_id")
        if not job_id:
            continue

        existing = existing_jobs.get(job_id)
        if existing is None:
            job = Job(**mapped)
            db.add(job)
            existing_jobs[job_id] = job
            new_count += 1
            print(f"新增岗位: {mapped.get('company')} - {mapped.get('job_title')}")
        else:
            # 更新已有记录
            for field in [
                "company",
                "company_tags",
                "department",
                "job_title",
                "location",
                "major_req",
                "job_req",
                "job_duty",
                "job_stage",
                "publish_date",
                "deadline",
                "detail_url",
                "scraped_at",
            ]:
                value = mapped.get(field)
                if value not in (None, ""):
                    setattr(existing, field, value)

    print(f"新增 {new_count} 条岗位，更新 {total_fetched - new_count} 条岗位")
    return new_count, total_fetched


_HTTP_PROXY = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
_HTTPS_PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
REQUEST_PROXIES = None
if _HTTP_PROXY or _HTTPS_PROXY:
    REQUEST_PROXIES = {
        "http": _HTTP_PROXY or _HTTPS_PROXY,
        "https": _HTTPS_PROXY or _HTTP_PROXY,
    }
SECURITIES_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "securities_campus.yaml"


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = _safe_text(value)
    if not text or text.startswith("0001-01-01"):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None



def _load_securities_targets(config_path: Path = SECURITIES_CONFIG_PATH) -> List[Dict[str, Any]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return payload.get("sites") or []



def _build_api_job_id(source: str, company: str, job_key: str) -> str:
    return hashlib.md5(f"{source}|{company}|{job_key}".encode("utf-8")).hexdigest()[:24]



def _map_zhiye_record(company: str, category: str, item: Dict[str, Any], detail_url_base: str) -> Dict[str, Any]:
    job_title = _safe_text(item.get("JobAdName"))
    job_key = _safe_text(item.get("Id") or item.get("JobAdId") or job_title)
    detail_url = f"{detail_url_base}/jobs/detail/{job_key}" if job_key else detail_url_base
    return {
        "job_id": _build_api_job_id("securities_zhiye", company, job_key),
        "source": "securities_zhiye",
        "company": company,
        "company_type_industry": "券商",
        "company_tags": _safe_text(category) or "zhiye",
        "department": _safe_text(item.get("ClassificationOne") or item.get("Category") or company),
        "job_title": job_title,
        "location": ",".join(item.get("LocNames") or []) or "未知",
        "major_req": _safe_text(item.get("Category") or ""),
        "job_req": _safe_text(item.get("Require") or ""),
        "job_duty": _safe_text(item.get("Duty") or ""),
        "application_status": "待申请",
        "job_stage": _infer_stage(job_title, category),
        "source_config_id": f"securities_api:{company}:{job_key}",
        "publish_date": _parse_datetime(item.get("PostDate")),
        "deadline": _parse_datetime(item.get("EndTime")),
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }


def _request_with_retries(method: str, url: str, retries: int = 3, **kwargs: Any) -> requests.Response:
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except RequestException as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"request failed without exception: {url}")



def _map_moka_embedded_record(target: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    company = target["name"]
    org_id = _safe_text(item.get("orgId") or target.get("moka_org_id") or ((item.get("org") or {}).get("id")))
    site_id = _safe_text(target.get("moka_site_id") or item.get("siteId") or ((item.get("org") or {}).get("siteId")) or "")
    job_key = _safe_text(item.get("id") or item.get("mjCode") or item.get("title"))
    title = _safe_text(item.get("title"))
    department = _safe_text((item.get("department") or {}).get("name") or company)
    zhineng = _safe_text((item.get("zhineng") or {}).get("name") or "")
    locations = item.get("locations") or []
    location = ",".join(_safe_text(loc.get("address")) for loc in locations if _safe_text(loc.get("address"))) or _safe_text((item.get("location") or {}).get("address")) or "未知"
    detail_url = target["entry_url"]
    detail_tpl = _safe_text(target.get("moka_url_template"))
    if detail_tpl and org_id and site_id and job_key:
        detail_url = detail_tpl.format(org_id=org_id, site_id=site_id, job_key=job_key)
    elif org_id and site_id and job_key:
        detail_url = f"https://app.mokahr.com/campus_apply/{org_id}/{site_id}#/job/{job_key}"
    return {
        "job_id": _build_api_job_id("securities_moka_embedded", company, job_key),
        "source": "securities_moka_embedded",
        "company": company,
        "company_type_industry": "券商",
        "company_tags": zhineng or department or "moka_embedded",
        "department": department,
        "job_title": title,
        "location": location,
        "major_req": zhineng,
        "job_req": _safe_text(item.get("requirement") or ""),
        "job_duty": _safe_text(item.get("description") or ""),
        "application_status": "待申请",
        "job_stage": _infer_stage(title, department, target.get("job_mode") or "campus"),
        "source_config_id": f"securities_api:{company}:{job_key}",
        "publish_date": _parse_datetime(item.get("publishedAt") or item.get("openedAt")),
        "deadline": _parse_datetime(item.get("closedAt")),
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }



def crawl_moka_embedded_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    resp = requests.get(
        target["entry_url"],
        headers={"User-Agent": "Mozilla/5.0", "Referer": target["entry_url"]},
        proxies=REQUEST_PROXIES,
        timeout=30,
    )
    resp.raise_for_status()
    html_text = resp.text
    match = re.search(r'<input id="init-data" type="hidden" value="(.*?)">', html_text, re.S)
    if not match:
        raise ValueError(f"{target['name']} Moka init-data payload not found")
    payload = json.loads(html.unescape(match.group(1)))
    jobs = payload.get("jobs") or []
    records: List[Dict[str, Any]] = []
    seen = set()
    for item in jobs:
        mapped = _map_moka_embedded_record(target, item)
        if mapped["job_id"] in seen:
            continue
        seen.add(mapped["job_id"])
        records.append(mapped)
    return records



def _contains_any_keyword(*values: Any, keywords: Optional[List[str]] = None) -> bool:
    if not keywords:
        return False
    merged = " ".join(_safe_text(v) for v in values)
    return any(keyword and keyword in merged for keyword in keywords)



def crawl_zhiye_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    entry_url = target["entry_url"]
    parsed = urlparse(entry_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    records: List[Dict[str, Any]] = []
    seen = set()
    allowed = set(target.get("categories_filter") or [])
    exclude_title_keywords = target.get("exclude_title_keywords") or []
    max_pages = int(target.get("max_pages") or 20)

    for page_index in range(max_pages):
        payload = {
            "PageIndex": page_index,
            "PageSize": 20,
            "KeyWords": "",
            "SpecialType": 0,
            "PortalId": target.get("portal_id") or "",
            "DisplayFields": ["Category", "Kind", "LocId", "ClassificationOne"],
        }
        resp = requests.post(
            f"{base}/api/Jobad/GetJobAdPageList",
            json=payload,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": entry_url,
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/plain, */*",
            },
            proxies=REQUEST_PROXIES,
            timeout=30,
        )
        resp.raise_for_status()
        rows = (resp.json() or {}).get("Data") or []
        if not rows:
            break
        page_seen = 0
        page_added = 0
        for item in rows:
            category = _safe_text(item.get("Category"))
            title = _safe_text(item.get("JobAdName"))
            if allowed and category not in allowed:
                continue
            page_seen += 1
            if _contains_any_keyword(title, keywords=exclude_title_keywords):
                continue
            mapped = _map_zhiye_record(target["name"], category, item, base)
            if mapped["job_id"] in seen:
                continue
            seen.add(mapped["job_id"])
            records.append(mapped)
            page_added += 1
        if page_seen == 0:
            break
        if page_added == 0 and page_seen < len(rows):
            break
    return records


def _extract_legacy_zhiye_field(html_text: str, label: str) -> str:
    pattern = re.compile(
        rf'<li class="ntitle[^"]*">{re.escape(label)}：</li>\s*'
        rf'<li class="(?:nvalue|nvcity)"[^>]*?(?:title="([^"]*)")?[^>]*>(.*?)</li>',
        re.S,
    )
    match = pattern.search(html_text)
    if not match:
        return ""
    title_value = _safe_text(match.group(1))
    raw_value = _strip_html(match.group(2))
    return title_value or raw_value


def _map_legacy_zhiye_record(
    target: Dict[str, Any],
    title: str,
    detail_url: str,
    location: str,
    detail_html: str,
) -> Dict[str, Any]:
    job_key_match = re.search(r"/zpdetail/(\d+)", detail_url)
    job_key = _safe_text(job_key_match.group(1) if job_key_match else title)
    duty_match = re.search(r'<p class="title">工作职责：</p>\s*<p>(.*?)</p>', detail_html, re.S)
    req_match = re.search(r'<p class="title">任职资格：</p>\s*<p>(.*?)</p>', detail_html, re.S)
    publish_date = _parse_datetime(_extract_legacy_zhiye_field(detail_html, "发布时间"))
    deadline = _parse_datetime(_extract_legacy_zhiye_field(detail_html, "截止时间"))
    return {
        "job_id": _build_api_job_id("securities_zhiye_legacy", target["name"], job_key),
        "source": "securities_zhiye_legacy",
        "company": target["name"],
        "company_type_industry": "券商",
        "company_tags": "校园招聘",
        "department": target["name"],
        "job_title": _safe_text(title),
        "location": _safe_text(location) or _extract_legacy_zhiye_field(detail_html, "工作地点") or "未知",
        "major_req": "",
        "job_req": _strip_html(req_match.group(1)) if req_match else "",
        "job_duty": _strip_html(duty_match.group(1)) if duty_match else "",
        "application_status": "待申请",
        "job_stage": _infer_stage(title, detail_html),
        "source_config_id": f"securities_api:{target['name']}:{job_key}",
        "publish_date": publish_date,
        "deadline": deadline,
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }


def crawl_zhiye_legacy_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    entry_url = target["entry_url"]
    max_pages = int(target.get("max_pages") or 20)
    records: List[Dict[str, Any]] = []
    seen = set()
    total_pages: Optional[int] = None

    for page_index in range(1, max_pages + 1):
        if total_pages is not None and page_index > total_pages:
            break
        page_url = entry_url if page_index == 1 else f"{entry_url}?PageIndex={page_index}"
        resp = _request_with_retries(
            "get",
            page_url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": entry_url},
            proxies=REQUEST_PROXIES,
            timeout=30,
        )
        page_html = resp.text
        if total_pages is None:
            total_match = re.search(r"当前第\d+/(\d+)页", page_html)
            if total_match:
                total_pages = int(total_match.group(1))
        rows = re.findall(
            r'<a title="([^"]+)" href="(/zpdetail/\d+)"[^>]*>.*?</a>\s*</td>\s*<td>(.*?)</td>\s*<td title="([^"]*)">',
            page_html,
            re.S,
        )
        if not rows:
            break
        for raw_title, detail_path, _head_count, raw_location in rows:
            detail_url = urljoin(entry_url, detail_path)
            job_key_match = re.search(r"/zpdetail/(\d+)", detail_path)
            dedupe_key = job_key_match.group(1) if job_key_match else detail_url
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            detail_resp = _request_with_retries(
                "get",
                detail_url,
                headers={"User-Agent": "Mozilla/5.0", "Referer": page_url},
                proxies=REQUEST_PROXIES,
                timeout=30,
            )
            records.append(
                _map_legacy_zhiye_record(
                    target=target,
                    title=html.unescape(raw_title),
                    detail_url=detail_url,
                    location=html.unescape(raw_location),
                    detail_html=detail_resp.text,
                )
            )
    return records



def _infer_hotjob_stage(title: str, post_type_name: str, recruit_type: str) -> str:
    merged = " ".join([title, post_type_name, recruit_type])
    if "实习" in merged or recruit_type == "3":
        return "internship"
    return "campus"



def _map_hotjob_record(target: Dict[str, Any], recruit_type: str, item: Dict[str, Any]) -> Dict[str, Any]:
    suite = target["hotjob_suite"]
    pid = _safe_text(item.get("postId") or item.get("id"))
    post_type_name = _safe_text(item.get("postTypeName") or item.get("postType"))
    if recruit_type == "1":
        detail_url = f"https://wecruit.hotjob.cn/{suite}/pb/school.html#/post?postId={pid}"
    elif recruit_type == "3":
        detail_url = f"https://wecruit.hotjob.cn/{suite}/pb/interns.html#/post?postId={pid}"
    else:
        detail_url = f"https://wecruit.hotjob.cn/{suite}/pb/social.html#/post?postId={pid}"
    return {
        "job_id": _build_api_job_id("securities_hotjob", target["name"], pid),
        "source": "securities_hotjob",
        "company": target["name"],
        "company_type_industry": "券商",
        "company_tags": post_type_name or "hotjob",
        "department": post_type_name or target["name"],
        "job_title": _safe_text(item.get("postName")),
        "location": _safe_text(item.get("workPlaceStr")) or "未知",
        "major_req": _safe_text(item.get("subject") or item.get("major") or ""),
        "job_req": _safe_text(item.get("subject") or ""),
        "job_duty": _safe_text(item.get("responsibility") or item.get("description") or ""),
        "application_status": "待申请",
        "job_stage": _infer_hotjob_stage(_safe_text(item.get("postName")), post_type_name, recruit_type),
        "source_config_id": f"securities_api:{target['name']}:{pid}",
        "publish_date": _parse_datetime(item.get("publishDate") or item.get("publishFirstDate")),
        "deadline": _parse_datetime(item.get("endDate")),
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }



def crawl_hotjob_target(target: Dict[str, Any]) -> List[Dict[str, Any]]:
    suite = target["hotjob_suite"]
    referer = target["entry_url"]
    recruit_types = target.get("recruit_types") or ["1"]
    max_pages = int(target.get("max_pages") or 20)
    records: List[Dict[str, Any]] = []
    seen = set()

    for recruit_type in recruit_types:
        total_pages = 1
        current_page = 1
        while current_page <= total_pages and current_page <= max_pages:
            resp = requests.post(
                f"https://wecruit.hotjob.cn/wecruit/positionInfo/listPosition/{suite}",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": referer,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                },
                proxies=REQUEST_PROXIES,
                timeout=30,
                params={
                    "iSaJAx": "isAjax",
                    "request_locale": "zh_CN",
                    "t": int(time.time() * 1000),
                },
                data={
                    "isFrompb": "true",
                    "recruitType": str(recruit_type),
                    "pageSize": "15",
                    "currentPage": str(current_page),
                },
            )
            resp.raise_for_status()
            data = (resp.json() or {}).get("data") or {}
            page_form = data.get("pageForm") or {}
            rows = page_form.get("pageData") or []
            total_pages = int(page_form.get("totalPage") or 1)
            if not rows:
                break
            for item in rows:
                mapped = _map_hotjob_record(target, str(recruit_type), item)
                if mapped["job_stage"] == "campus" and str(recruit_type) == "2":
                    continue
                if mapped["job_id"] in seen:
                    continue
                seen.add(mapped["job_id"])
                records.append(mapped)
            current_page += 1
    return records



def crawl_configured_securities_targets(target_names: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
    targets = _load_securities_targets()
    if target_names:
        wanted = set(target_names)
        targets = [t for t in targets if t.get("name") in wanted]
    results: Dict[str, List[Dict[str, Any]]] = {}
    for target in targets:
        ats_family = target.get("ats_family")
        company = target["name"]
        if ats_family == "zhiye":
            crawled = crawl_zhiye_target(target)
        elif ats_family == "hotjob":
            crawled = crawl_hotjob_target(target)
        elif ats_family == "moka_embedded":
            crawled = crawl_moka_embedded_target(target)
        elif ats_family == "zhiye_legacy":
            crawled = crawl_zhiye_legacy_target(target)
        else:
            crawled = []
        company_records = results.setdefault(company, [])
        seen_job_ids = {item.get("job_id") for item in company_records}
        for record in crawled:
            job_id = record.get("job_id")
            if job_id and job_id in seen_job_ids:
                continue
            if job_id:
                seen_job_ids.add(job_id)
            company_records.append(record)
    return results



def run_configured_securities_crawl(
    db: Session,
    existing_jobs: Dict[str, Job],
    target_names: Optional[List[str]] = None,
) -> Tuple[int, int, Dict[str, int]]:
    grouped = crawl_configured_securities_targets(target_names=target_names)
    new_count = 0
    total_count = 0
    company_counts: Dict[str, int] = {}

    for company, records in grouped.items():
        company_counts[company] = len(records)
        total_count += len(records)
        for mapped in records:
            job_id = mapped.get("job_id")
            if not job_id:
                continue
            existing = existing_jobs.get(job_id)
            if existing is None:
                job = Job(**mapped)
                db.add(job)
                existing_jobs[job_id] = job
                new_count += 1
            else:
                for field in [
                    "company",
                    "company_tags",
                    "department",
                    "job_title",
                    "location",
                    "major_req",
                    "job_req",
                    "job_duty",
                    "job_stage",
                    "publish_date",
                    "deadline",
                    "detail_url",
                    "scraped_at",
                ]:
                    value = mapped.get(field)
                    if value not in (None, ""):
                        setattr(existing, field, value)
                existing_jobs[job_id] = existing
    return new_count, total_count, company_counts


if __name__ == "__main__":
    from app.database import get_db

    db = next(get_db())
    existing_jobs = {job.job_id: job for job in db.query(Job).all()}
    targets = ["中金公司", "国金证券", "安信证券", "中泰证券"]
    new_count, total_count, company_counts = run_configured_securities_crawl(db, existing_jobs, target_names=targets)
    db.commit()
    print(f"完成！新增 {new_count} 条，共处理 {total_count} 条")
    print(company_counts)
