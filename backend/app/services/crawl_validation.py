from __future__ import annotations

from typing import Iterable, List, Optional

from app.services.crawl_taxonomy import (
    CompletenessReport,
    DetectionReport,
    FailureReason,
    FallbackAction,
    ZeroResultType,
)


def detect_contradictions(
    detection: DetectionReport,
    extracted_count: int,
    historical_average_count: Optional[float] = None,
) -> List[str]:
    contradictions: List[str] = []
    if extracted_count == 0 and detection.has_job_signal:
        contradictions.append("page_has_job_signal_but_extracted_zero")
    if extracted_count == 0 and detection.has_detail_links:
        contradictions.append("detail_links_found_but_extracted_zero")
    if extracted_count == 0 and detection.page_claimed_count > 0:
        contradictions.append("page_claimed_openings_but_extracted_zero")
    if historical_average_count and historical_average_count > 0 and extracted_count == 0:
        contradictions.append("historical_average_non_zero_but_current_zero")
    if detection.page_claimed_count > 0 and extracted_count > 0 and extracted_count < detection.page_claimed_count:
        contradictions.append("page_claimed_count_much_higher_than_extracted")
    return contradictions


def classify_zero_result(
    detection: DetectionReport,
    extracted_count: int,
    historical_average_count: Optional[float] = None,
) -> str:
    if extracted_count > 0:
        return ZeroResultType.NON_ZERO.value

    contradictions = detect_contradictions(detection, extracted_count, historical_average_count)
    if contradictions:
        return ZeroResultType.SUSPECT_ZERO.value

    if not detection.has_job_signal and not detection.has_detail_links and not detection.has_api_clue and not detection.has_ats_fingerprint:
        return ZeroResultType.CONFIRMED_ZERO.value

    return ZeroResultType.UNKNOWN.value


def score_completeness(
    detection: DetectionReport,
    extracted_count: int,
    historical_average_count: Optional[float] = None,
    blocked_or_empty_response: bool = False,
    extra_failure_reasons: Optional[Iterable[str]] = None,
) -> CompletenessReport:
    score = 0.0
    failure_reasons: List[str] = list(extra_failure_reasons or [])
    contradictions = detect_contradictions(detection, extracted_count, historical_average_count)

    if detection.has_ats_fingerprint:
        score += 10
    if detection.has_job_signal:
        score += 15
    if detection.has_detail_links:
        score += 20
    if detection.has_embedded_json:
        score += 15
    if detection.has_api_clue:
        score += 20
    if extracted_count > 0:
        score += 20

    if extracted_count == 0 and detection.has_job_signal:
        score -= 35
        failure_reasons.append(FailureReason.JOB_SIGNAL_BUT_ZERO_EXTRACTED.value)
    if extracted_count == 0 and detection.has_detail_links:
        score -= 35
        failure_reasons.append(FailureReason.DETAIL_LINKS_FOUND_LIST_FAILED.value)
    if extracted_count == 0 and detection.page_claimed_count > 0:
        score -= 35
        failure_reasons.append(FailureReason.PAGE_CLAIMS_OPENINGS_BUT_ZERO.value)
    if historical_average_count and historical_average_count > 0 and extracted_count == 0:
        score -= 25
    if detection.page_claimed_count > 0 and extracted_count > 0 and extracted_count < detection.page_claimed_count:
        score -= 20
    if blocked_or_empty_response:
        score -= 30
        failure_reasons.append(FailureReason.BLOCKED_OR_EMPTY_RESPONSE.value)

    if not detection.has_job_signal and extracted_count == 0:
        failure_reasons.append(FailureReason.NO_JOB_SIGNAL.value)

    score = max(0.0, min(100.0, score))
    zero_result_type = classify_zero_result(detection, extracted_count, historical_average_count)

    fallback_action = FallbackAction.NONE.value
    if zero_result_type == ZeroResultType.SUSPECT_ZERO.value:
        if detection.has_detail_links:
            fallback_action = FallbackAction.EXTRACT_DETAIL_LINKS_ONLY.value
        elif detection.has_api_clue:
            fallback_action = FallbackAction.RETRY_WITH_API.value
        else:
            fallback_action = FallbackAction.RETRY_WITH_PLAYWRIGHT.value
    elif blocked_or_empty_response:
        fallback_action = FallbackAction.MANUAL_REVIEW.value

    return CompletenessReport(
        score=score,
        zero_result_type=zero_result_type,
        contradictions=contradictions,
        failure_reasons=sorted(set(failure_reasons)),
        fallback_action=fallback_action,
        notes=[],
    )
