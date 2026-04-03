from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

from app.models import CompanyRecrawlQueue, CrawlLog
from app.services.crawl_taxonomy import CompletenessReport, CrawlEvidence, DetectionReport


def _to_json(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return "{}"


def start_run_context(log: CrawlLog, source: str, target_url: str = "") -> CrawlLog:
    log.source = source
    log.started_at = datetime.utcnow()
    log.status = "running"
    if hasattr(log, "target_url"):
        log.target_url = target_url
    return log


def record_detection(log: CrawlLog, detection: DetectionReport) -> CrawlLog:
    if hasattr(log, "target_url") and detection.target_url:
        log.target_url = detection.target_url
    if hasattr(log, "final_url"):
        log.final_url = detection.final_url
    if hasattr(log, "page_title"):
        log.page_title = detection.page_title
    if hasattr(log, "ats_family"):
        log.ats_family = detection.ats_family
    if hasattr(log, "framework_family"):
        log.framework_family = detection.framework_family
    if hasattr(log, "detection_flags_json"):
        log.detection_flags_json = _to_json(asdict(detection))
    if hasattr(log, "detail_link_count"):
        log.detail_link_count = detection.detail_link_count
    if hasattr(log, "job_signal_count"):
        log.job_signal_count = detection.job_signal_count
    if hasattr(log, "page_claimed_count"):
        log.page_claimed_count = detection.page_claimed_count
    return log


def record_evidence(log: CrawlLog, evidence: CrawlEvidence) -> CrawlLog:
    if hasattr(log, "evidence_json"):
        log.evidence_json = _to_json(asdict(evidence))
    if hasattr(log, "final_url") and evidence.final_url:
        log.final_url = evidence.final_url
    if hasattr(log, "page_title") and evidence.page_title:
        log.page_title = evidence.page_title
    return log


def record_validation(log: CrawlLog, report: CompletenessReport) -> CrawlLog:
    if hasattr(log, "completeness_score"):
        log.completeness_score = report.score
    if hasattr(log, "zero_result_type"):
        log.zero_result_type = report.zero_result_type
    if hasattr(log, "failure_reason"):
        log.failure_reason = report.failure_reasons[0] if report.failure_reasons else ""
    if hasattr(log, "failure_reasons_json"):
        log.failure_reasons_json = _to_json(report.failure_reasons)
    if hasattr(log, "fallback_action"):
        log.fallback_action = report.fallback_action
    return log


def record_failure(log: CrawlLog, reason: str, message: str = "") -> CrawlLog:
    if hasattr(log, "failure_reason"):
        log.failure_reason = reason
    if hasattr(log, "failure_reasons_json"):
        log.failure_reasons_json = _to_json([reason])
    if message:
        log.error_message = message[:2000]
    log.status = "failed"
    log.finished_at = datetime.utcnow()
    return log


def finish_run_context(log: CrawlLog, status: str = "completed") -> CrawlLog:
    log.status = status
    log.finished_at = datetime.utcnow()
    return log


def sync_queue_from_validation(
    task: CompanyRecrawlQueue,
    detection: Optional[DetectionReport] = None,
    evidence: Optional[CrawlEvidence] = None,
    report: Optional[CompletenessReport] = None,
) -> CompanyRecrawlQueue:
    if detection is not None and hasattr(task, "last_detection_json"):
        task.last_detection_json = _to_json(asdict(detection))
    if evidence is not None and hasattr(task, "last_evidence_json"):
        task.last_evidence_json = _to_json(asdict(evidence))
    if report is not None:
        if hasattr(task, "completeness_score"):
            task.completeness_score = report.score
        if hasattr(task, "zero_result_type"):
            task.zero_result_type = report.zero_result_type
        if hasattr(task, "failure_reason"):
            task.failure_reason = report.failure_reasons[0] if report.failure_reasons else ""
        if hasattr(task, "failure_reasons_json"):
            task.failure_reasons_json = _to_json(report.failure_reasons)
        if hasattr(task, "fallback_action"):
            task.fallback_action = report.fallback_action
        if hasattr(task, "priority"):
            task.priority = 100 if report.zero_result_type == "suspect_zero" else 0
    return task
