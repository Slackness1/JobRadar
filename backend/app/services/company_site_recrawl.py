import hashlib
import re
from dataclasses import asdict
from datetime import datetime
from html import unescape
from typing import Any, List
from urllib.parse import urljoin, urlparse

import requests

from app.services.crawl_detection import detect_from_html
from app.services.crawl_evidence import build_evidence
from app.services.crawl_validation import score_completeness

_ANCHOR_PATTERN = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_SPACE_PATTERN = re.compile(r"\s+")

_TITLE_KEYWORDS = [
    "job", "jobs", "career", "careers", "position", "opportunity",
    "招聘", "岗位", "职位", "实习", "校招", "应届", "campus", "intern",
]


def _clean_text(raw: str) -> str:
    text = _TAG_PATTERN.sub(" ", raw or "")
    text = unescape(text)
    text = _SPACE_PATTERN.sub(" ", text).strip()
    return text


def _infer_stage(text: str) -> str:
    lowered = (text or "").lower()
    if "intern" in lowered or "实习" in lowered:
        return "internship"
    return "campus"


def _build_job_id(source_domain: str, detail_url: str, title: str) -> str:
    raw = f"{source_domain}|{detail_url}|{title}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"company_site:{source_domain}:{digest}"


def crawl_company_site(career_url: str, company: str, department: str = "", return_diagnostics: bool = False) -> List[dict] | dict[str, Any]:
    response = requests.get(career_url, timeout=25)
    response.raise_for_status()

    html = response.text
    final_url = str(getattr(response, "url", "") or career_url)
    title_match = _TITLE_PATTERN.search(html)
    page_title = _clean_text(title_match.group(1) if title_match else "")
    parsed = urlparse(final_url)
    source_domain = parsed.netloc.lower()

    detection = detect_from_html(url=final_url, html=html, title=page_title)

    jobs: List[dict] = []
    seen_keys = set()

    for href, inner_html in _ANCHOR_PATTERN.findall(html):
        title = _clean_text(inner_html)
        full_url = urljoin(final_url, href.strip())
        combined = f"{title} {full_url}".lower()
        if not title:
            continue
        if not any(keyword in combined for keyword in _TITLE_KEYWORDS):
            continue

        dedupe_key = (title, full_url)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        jobs.append({
            "job_id": _build_job_id(source_domain, full_url, title),
            "source": f"company_site:{source_domain}",
            "company": company,
            "company_type_industry": "",
            "company_tags": "",
            "department": department,
            "job_title": title,
            "location": "",
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": _infer_stage(title),
            "source_config_id": career_url,
            "publish_date": None,
            "deadline": None,
            "detail_url": full_url,
            "scraped_at": datetime.utcnow(),
        })

        if len(jobs) >= 200:
            break

    if not jobs and page_title:
        jobs.append({
            "job_id": _build_job_id(source_domain, final_url, page_title),
            "source": f"company_site:{source_domain}",
            "company": company,
            "company_type_industry": "",
            "company_tags": "",
            "department": department,
            "job_title": page_title,
            "location": "",
            "major_req": "",
            "job_req": "",
            "job_duty": "",
            "application_status": "待申请",
            "job_stage": _infer_stage(page_title),
            "source_config_id": career_url,
            "publish_date": None,
            "deadline": None,
            "detail_url": final_url,
            "scraped_at": datetime.utcnow(),
        })

    evidence = build_evidence(
        final_url=final_url,
        page_title=page_title,
        html_initial=html,
        html_rendered=html,
        dom_count_before=html.count("<a"),
        dom_count_after=len(jobs),
        detected_detail_links=detection.detail_link_samples,
        ats_fingerprint_hits=detection.ats_fingerprints,
    )
    validation = score_completeness(detection=detection, extracted_count=len(jobs))

    if return_diagnostics:
        return {
            "jobs": jobs,
            "detection": asdict(detection),
            "evidence": asdict(evidence),
            "validation": asdict(validation),
        }

    return jobs
