from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class ATSFamily(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    SMARTRECRUITERS = "smartrecruiters"
    TALEO = "taleo"
    ICIMS = "icims"
    MOKA = "moka"
    BEISEN = "beisen"
    NEXTJS = "nextjs"
    NUXT = "nuxt"
    REACT_SPA = "react_spa"
    STATIC_HTML = "static_html"
    UNKNOWN = "unknown"


class FailureReason(str, Enum):
    NO_JOB_SIGNAL = "NO_JOB_SIGNAL"
    JOB_SIGNAL_BUT_ZERO_EXTRACTED = "JOB_SIGNAL_BUT_ZERO_EXTRACTED"
    HYDRATION_TIMEOUT = "HYDRATION_TIMEOUT"
    NEEDS_INTERACTION = "NEEDS_INTERACTION"
    DETAIL_LINKS_FOUND_LIST_FAILED = "DETAIL_LINKS_FOUND_LIST_FAILED"
    API_FOUND_AUTH_REQUIRED = "API_FOUND_AUTH_REQUIRED"
    BLOCKED_OR_EMPTY_RESPONSE = "BLOCKED_OR_EMPTY_RESPONSE"
    ATS_DETECTED_BUT_ADAPTER_MISSING = "ATS_DETECTED_BUT_ADAPTER_MISSING"
    PAGE_CLAIMS_OPENINGS_BUT_ZERO = "PAGE_CLAIMS_OPENINGS_BUT_ZERO"
    IFRAME_CONTENT_NOT_PARSED = "IFRAME_CONTENT_NOT_PARSED"
    SHADOW_DOM_NOT_PARSED = "SHADOW_DOM_NOT_PARSED"


class ZeroResultType(str, Enum):
    NON_ZERO = "non_zero"
    CONFIRMED_ZERO = "confirmed_zero"
    SUSPECT_ZERO = "suspect_zero"
    UNKNOWN = "unknown"


class FallbackAction(str, Enum):
    NONE = "none"
    RETRY_DETECTION = "retry_detection"
    RETRY_WITH_API = "retry_with_api"
    RETRY_WITH_PLAYWRIGHT = "retry_with_playwright"
    EXTRACT_DETAIL_LINKS_ONLY = "extract_detail_links_only"
    MANUAL_REVIEW = "manual_review"


@dataclass
class DetectionReport:
    target_url: str
    final_url: str = ""
    page_title: str = ""
    ats_family: str = ATSFamily.UNKNOWN.value
    framework_family: str = ATSFamily.UNKNOWN.value
    has_job_signal: bool = False
    job_signal_count: int = 0
    has_detail_links: bool = False
    detail_link_count: int = 0
    detail_link_samples: List[str] = field(default_factory=list)
    has_embedded_json: bool = False
    embedded_json_types: List[str] = field(default_factory=list)
    has_api_clue: bool = False
    api_hosts: List[str] = field(default_factory=list)
    has_ats_fingerprint: bool = False
    ats_fingerprints: List[str] = field(default_factory=list)
    page_claimed_count: int = 0
    has_iframe: bool = False
    has_shadow_dom_hint: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class CrawlEvidence:
    final_url: str = ""
    page_title: str = ""
    first_xhr_urls: List[str] = field(default_factory=list)
    key_text_snippets: List[str] = field(default_factory=list)
    html_initial_snippet: str = ""
    html_rendered_snippet: str = ""
    dom_count_before: int = 0
    dom_count_after: int = 0
    screenshot_path: str = ""
    detected_detail_links: List[str] = field(default_factory=list)
    ats_fingerprint_hits: List[str] = field(default_factory=list)
    failure_reason: str = ""
    notes: List[str] = field(default_factory=list)


@dataclass
class CompletenessReport:
    score: float
    zero_result_type: str = ZeroResultType.UNKNOWN.value
    contradictions: List[str] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)
    fallback_action: str = FallbackAction.NONE.value
    notes: List[str] = field(default_factory=list)
