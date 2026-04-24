from __future__ import annotations

import re
from html import unescape
from typing import Iterable, List
from urllib.parse import urlparse

from app.services.crawl_taxonomy import ATSFamily, DetectionReport


JOB_SIGNAL_PATTERNS = [
    r"\bjobs?\b",
    r"\bopenings?\b",
    r"\bpositions?\b",
    r"\brequisition\b",
    r"招聘",
    r"岗位",
    r"职位",
    r"校招",
    r"实习",
]

DETAIL_LINK_PATTERNS = [
    r"/jobs?/",
    r"/careers?/",
    r"/position/",
    r"/recruit",
    r"\?gh_jid=",
    r"lever\.co/",
    r"workdayjobs\.com/",
    r"mokahr\.com/",
    r"zhiye\.com/",
]

PAGE_COUNT_PATTERNS = [
    re.compile(r"(\d+)\s+(?:openings|positions|jobs)", re.I),
    re.compile(r"共\s*(\d+)\s*个?(?:岗位|职位)"),
]


def _clean_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _unique(items: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        value = (item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def detect_ats_family(url: str, html: str = "", script_srcs: Iterable[str] | None = None) -> str:
    merged = " ".join([url or "", html or "", *(script_srcs or [])]).lower()
    host = urlparse(url).netloc.lower()

    if "greenhouse" in host or "greenhouse.io" in merged:
        return ATSFamily.GREENHOUSE.value
    if "jobs.lever.co" in merged or "lever.co" in host:
        return ATSFamily.LEVER.value
    if "workdayjobs.com" in merged or "myworkdayjobs.com" in merged:
        return ATSFamily.WORKDAY.value
    if "smartrecruiters" in merged:
        return ATSFamily.SMARTRECRUITERS.value
    if "taleo" in merged or "oraclecloud" in merged:
        return ATSFamily.TALEO.value
    if "icims" in merged:
        return ATSFamily.ICIMS.value
    if "mokahr.com" in merged:
        return ATSFamily.MOKA.value
    if "zhiye.com" in merged or "beisen" in merged:
        return ATSFamily.BEISEN.value
    if "_next/static" in merged or "__next_data__" in merged:
        return ATSFamily.NEXTJS.value
    if "/_nuxt/" in merged or "__nuxt__" in merged:
        return ATSFamily.NUXT.value
    if "data-reactroot" in merged or "react" in merged:
        return ATSFamily.REACT_SPA.value
    if html:
        return ATSFamily.STATIC_HTML.value
    return ATSFamily.UNKNOWN.value


def detect_framework_family(url: str, html: str = "", script_srcs: Iterable[str] | None = None) -> str:
    family = detect_ats_family(url=url, html=html, script_srcs=script_srcs)
    if family in {ATSFamily.NEXTJS.value, ATSFamily.NUXT.value, ATSFamily.REACT_SPA.value, ATSFamily.STATIC_HTML.value}:
        return family
    merged = " ".join([html or "", *(script_srcs or [])]).lower()
    if "_next/static" in merged or "__next_data__" in merged:
        return ATSFamily.NEXTJS.value
    if "/_nuxt/" in merged or "__nuxt__" in merged:
        return ATSFamily.NUXT.value
    if "data-reactroot" in merged or "react" in merged:
        return ATSFamily.REACT_SPA.value
    return ATSFamily.UNKNOWN.value


def _collect_detail_links(url: str, html: str) -> List[str]:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html or "", re.I)
    samples = []
    for href in hrefs:
        if any(re.search(pattern, href, re.I) for pattern in DETAIL_LINK_PATTERNS):
            samples.append(href)
    return _unique(samples)[:20]


def _detect_embedded_json_types(html: str) -> List[str]:
    types: List[str] = []
    source = (html or "").lower()
    if "__next_data__" in source:
        types.append("__NEXT_DATA__")
    if "__nuxt__" in source:
        types.append("__NUXT__")
    if "__initial_state__" in source:
        types.append("window.__INITIAL_STATE__")
    if "apollo-state" in source:
        types.append("apollo-state")
    if "application/ld+json" in source:
        types.append("application/ld+json")
    if 'type="application/json"' in source or "type='application/json'" in source:
        types.append("script[type=application/json]")
    return _unique(types)


def _extract_api_hosts(xhr_urls: Iterable[str]) -> List[str]:
    hosts = []
    for url in xhr_urls or []:
        parsed = urlparse(url)
        if parsed.netloc:
            hosts.append(parsed.netloc.lower())
        elif any(token in (url or "").lower() for token in ["/api/", "/graphql", "graphql"]):
            hosts.append(url)
    return _unique(hosts)[:10]


def _page_claimed_count(text: str) -> int:
    for pattern in PAGE_COUNT_PATTERNS:
        match = pattern.search(text or "")
        if match:
            try:
                return int(match.group(1))
            except Exception:
                continue
    return 0


def detect_from_html(url: str, html: str, title: str = "") -> DetectionReport:
    text = _clean_text(html)
    job_signal_count = sum(len(re.findall(pattern, text, re.I)) for pattern in JOB_SIGNAL_PATTERNS)
    detail_links = _collect_detail_links(url, html)
    embedded_json_types = _detect_embedded_json_types(html)
    ats_family = detect_ats_family(url, html)
    framework_family = detect_framework_family(url, html)
    ats_fingerprints = [x for x in [ats_family] if x not in {ATSFamily.UNKNOWN.value, ATSFamily.STATIC_HTML.value}]

    return DetectionReport(
        target_url=url,
        final_url=url,
        page_title=title,
        ats_family=ats_family,
        framework_family=framework_family,
        has_job_signal=job_signal_count > 0,
        job_signal_count=job_signal_count,
        has_detail_links=bool(detail_links),
        detail_link_count=len(detail_links),
        detail_link_samples=detail_links[:5],
        has_embedded_json=bool(embedded_json_types),
        embedded_json_types=embedded_json_types,
        has_api_clue=False,
        api_hosts=[],
        has_ats_fingerprint=bool(ats_fingerprints),
        ats_fingerprints=ats_fingerprints,
        page_claimed_count=_page_claimed_count(text),
        has_iframe="<iframe" in (html or "").lower(),
        has_shadow_dom_hint="shadowroot" in (html or "").lower() or "attachshadow" in (html or "").lower(),
        notes=[],
    )


def detect_from_page_signals(url: str, title: str, html: str, xhr_urls: Iterable[str] | None = None) -> DetectionReport:
    report = detect_from_html(url=url, html=html, title=title)
    api_hosts = _extract_api_hosts(xhr_urls or [])
    report.has_api_clue = bool(api_hosts)
    report.api_hosts = api_hosts
    if title and not report.page_title:
        report.page_title = title
    return report


def merge_detection_reports(*reports: DetectionReport) -> DetectionReport:
    valid_reports = [report for report in reports if report is not None]
    if not valid_reports:
        return DetectionReport(target_url="")

    base = valid_reports[0]
    merged = DetectionReport(target_url=base.target_url)
    for report in valid_reports:
        if report.final_url:
            merged.final_url = report.final_url
        if report.page_title:
            merged.page_title = report.page_title
        if report.ats_family != ATSFamily.UNKNOWN.value:
            merged.ats_family = report.ats_family
        if report.framework_family != ATSFamily.UNKNOWN.value:
            merged.framework_family = report.framework_family
        merged.has_job_signal = merged.has_job_signal or report.has_job_signal
        merged.job_signal_count += report.job_signal_count
        merged.has_detail_links = merged.has_detail_links or report.has_detail_links
        merged.detail_link_count = max(merged.detail_link_count, report.detail_link_count)
        merged.detail_link_samples = _unique(merged.detail_link_samples + report.detail_link_samples)[:5]
        merged.has_embedded_json = merged.has_embedded_json or report.has_embedded_json
        merged.embedded_json_types = _unique(merged.embedded_json_types + report.embedded_json_types)
        merged.has_api_clue = merged.has_api_clue or report.has_api_clue
        merged.api_hosts = _unique(merged.api_hosts + report.api_hosts)[:10]
        merged.has_ats_fingerprint = merged.has_ats_fingerprint or report.has_ats_fingerprint
        merged.ats_fingerprints = _unique(merged.ats_fingerprints + report.ats_fingerprints)
        merged.page_claimed_count = max(merged.page_claimed_count, report.page_claimed_count)
        merged.has_iframe = merged.has_iframe or report.has_iframe
        merged.has_shadow_dom_hint = merged.has_shadow_dom_hint or report.has_shadow_dom_hint
        merged.notes = _unique(merged.notes + report.notes)

    if not merged.final_url:
        merged.final_url = merged.target_url
    return merged
