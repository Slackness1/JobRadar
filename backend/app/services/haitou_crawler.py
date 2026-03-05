import hashlib
import html
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from app.models import Job


LIST_URL = "https://xyzp.haitou.cc/search/p{page}/"
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
    raw = f"haitou_xyzp|{detail_url}|{job_title}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:24]


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
                "source": "haitou_xyzp",
                "company": company,
                "company_type_industry": "",
                "company_tags": article_tags,
                "department": company,
                "job_title": fallback_title,
                "location": _safe_text(detail.get("invoiceCity")) or _safe_text(list_item.get("city")),
                "major_req": article_tags,
                "job_req": req,
                "job_duty": duty,
                "application_status": "待申请",
                "job_stage": _infer_stage(fallback_title, detail.get("title")),
                "source_config_id": f"haitou:{detail_id}",
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
                "source": "haitou_xyzp",
                "company": company,
                "company_type_industry": "",
                "company_tags": article_tags,
                "department": company,
                "job_title": job_title,
                "location": _extract_locations(detail, list_item, detail_job),
                "major_req": major_req,
                "job_req": req,
                "job_duty": duty,
                "application_status": "待申请",
                "job_stage": _infer_stage(job_title, detail.get("title")),
                "source_config_id": f"haitou:{detail_id}",
                "publish_date": start_dt,
                "deadline": end_dt,
                "detail_url": detail_url,
                "scraped_at": datetime.utcnow(),
            }
        )

    return records


def crawl_haitou_records(max_pages: int = 16) -> List[Dict[str, Any]]:
    session = requests.Session()
    records: List[Dict[str, Any]] = []
    visited_detail_urls = set()

    for page in range(1, max_pages + 1):
        list_url = LIST_URL.format(page=page)
        try:
            list_payload = _fetch_next_data(session, list_url)
        except (RequestException, ValueError, json.JSONDecodeError):
            break

        page_props = list_payload.get("props", {}).get("pageProps", {})
        list_jobs = page_props.get("listJob") or []
        if not list_jobs:
            break

        for list_item in list_jobs:
            if not isinstance(list_item, dict):
                continue

            article_id = list_item.get("id")
            if not article_id:
                continue

            detail_url = DETAIL_URL.format(article_id=article_id)
            if detail_url in visited_detail_urls:
                continue
            visited_detail_urls.add(detail_url)

            try:
                detail_payload = _fetch_next_data(session, detail_url)
            except (RequestException, ValueError, json.JSONDecodeError):
                continue

            detail_props = detail_payload.get("props", {}).get("pageProps", {})
            detail = detail_props.get("detail") or {}
            detail_jobs = detail_props.get("listJob") or detail.get("jobList") or []

            detail_records = _build_records_from_detail(list_item, detail, detail_jobs, detail_url)
            records.extend(detail_records)
            time.sleep(0.1)

        total = page_props.get("total")
        size = page_props.get("size")
        current_page = page_props.get("page") or page
        try:
            total_int = int(total)
            size_int = int(size)
            current_int = int(current_page)
            if size_int > 0:
                total_pages = (total_int + size_int - 1) // size_int
                if current_int >= total_pages:
                    break
        except (TypeError, ValueError):
            pass

    return records


def run_haitou_crawl(db: Session, existing_jobs: Dict[str, Job], max_pages: int = 16) -> Tuple[int, int]:
    records = crawl_haitou_records(max_pages=max_pages)
    total_fetched = len(records)
    new_count = 0

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
            continue

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

    return new_count, total_fetched
