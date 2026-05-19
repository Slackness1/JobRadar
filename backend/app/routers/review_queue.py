"""Review queue router.

Two parallel sources of "needs review" surface here:

1. Crawler-LLM uncertain jobs (`Job` rows with empty/low_signal quality_label)
   — bucketed FinTech / 纯金融 / 其他 for kanban.
2. Teacher-uploaded drafts (`JobDraft` rows with status='pending') from the
   /teacher OCR/text-paste flow. Reviewed via the proxy endpoints below which
   delegate to /api/teacher-entry/admin/drafts/{id}/{approve|reject}.

Approve  -> quality_label = 'good' (for jobs) or status='approved' + promote
            to jobs (for drafts).
Reject   -> quality_label = 'spam' / status='rejected'.
Retrack  -> track_predicted = <new>; quality_label = 'good' (jobs only).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, JobDraft


router = APIRouter(prefix="/api/review-queue", tags=["review-queue"])


# In the data model `track_predicted` is a freeform string the LLM emitted.
# We re-bucket it to three coarse columns for the kanban view.
FINTECH_KEYS = {"fintech", "FinTech", "互联网金融", "金融科技"}
PURE_FINANCE_KEYS = {
    "banks", "insurance", "securities", "funds", "pe_vc",
    "银行", "保险", "券商", "公募", "PE/VC", "投行",
}


def _bucket(track_predicted: str) -> str:
    if not track_predicted:
        return "其他"
    if track_predicted in FINTECH_KEYS:
        return "FinTech"
    if track_predicted in PURE_FINANCE_KEYS:
        return "纯金融"
    return "其他"


def _serialize(job: Job) -> dict:
    return {
        "id": job.id,
        "job_id": job.job_id,
        "title": job.job_title or "",
        "company": job.company or "",
        "location": job.location or "",
        "source": job.source or "",
        "track_predicted": job.track_predicted or "",
        "track_bucket": _bucket(job.track_predicted or ""),
        "quality_label": job.quality_label or "",
        "publish_date": job.publish_date.isoformat() if job.publish_date else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "detail_url": job.detail_url or "",
        "job_req_excerpt": (job.job_req or "")[:240],
    }


def _serialize_draft(d: JobDraft) -> dict:
    """Teacher-uploaded draft pending admin review."""
    try:
        tags = json.loads(getattr(d, "tags_json", "") or "[]")
    except json.JSONDecodeError:
        tags = []
    return {
        "id": d.id,
        "kind": "draft",
        "teacher_name": d.teacher_name or "",
        "teacher_dept": d.teacher_dept or "",
        "source_type": d.source_type or "",   # link | ocr | text
        "parse_confidence": float(d.parse_confidence or 0),
        "title": d.parsed_title or "",
        "company": d.parsed_company or "",
        "location": d.parsed_location or "",
        "track": d.track or "",
        "tags": tags,
        "jd_excerpt": (d.parsed_jd_summary or "")[:240],
        "deadline": d.parsed_deadline or "",
        "salary": d.parsed_salary or "",
        "detail_url": d.parsed_detail_url or "",
        "status": d.status or "",
        "submitted_at": d.submitted_at.isoformat() if d.submitted_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("")
def list_queue(
    bucket: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> dict:
    """Return jobs needing review + summary counts."""
    cutoff = datetime.utcnow() - timedelta(days=30)
    base = db.query(Job).filter(
        or_(
            Job.quality_label.in_(["", "low_signal"]),
            Job.track_predicted == "",
        ),
        Job.created_at >= cutoff,
    )

    pending_jobs = base.order_by(Job.created_at.desc()).limit(limit).all()
    items = [_serialize(j) for j in pending_jobs]

    if bucket and bucket in {"FinTech", "纯金融", "其他"}:
        items = [it for it in items if it["track_bucket"] == bucket]

    # Tier overview: queue counts + live counts (already-approved good jobs)
    bucket_counts = {"FinTech": 0, "纯金融": 0, "其他": 0}
    for it in items:
        bucket_counts[it["track_bucket"]] = bucket_counts.get(it["track_bucket"], 0) + 1

    live_rows = (
        db.query(Job.track_predicted, func.count(Job.id))
        .filter(Job.quality_label == "good")
        .group_by(Job.track_predicted)
        .all()
    )
    live_counts = {"FinTech": 0, "纯金融": 0, "其他": 0}
    for tp, ct in live_rows:
        live_counts[_bucket(tp or "")] = live_counts.get(_bucket(tp or ""), 0) + int(ct)

    # Teacher-uploaded drafts pending admin review (parallel review surface)
    draft_q = db.query(JobDraft).filter(JobDraft.status == "pending")
    teacher_drafts = [
        _serialize_draft(d)
        for d in draft_q.order_by(
            JobDraft.submitted_at.desc().nullslast(),
            JobDraft.created_at.desc(),
        ).limit(200).all()
    ]
    teacher_pending_total = draft_q.count()

    return {
        "items": items,
        "summary": {
            "FinTech":  {"queue": bucket_counts["FinTech"],  "live": live_counts["FinTech"]},
            "纯金融":   {"queue": bucket_counts["纯金融"],   "live": live_counts["纯金融"]},
            "其他":     {"queue": bucket_counts["其他"],     "live": live_counts["其他"]},
        },
        "total_pending": base.count(),
        "teacher_drafts": teacher_drafts,
        "teacher_pending_total": teacher_pending_total,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


class RetrackBody(BaseModel):
    track_predicted: str
    quality_label: str = "good"


@router.post("/{job_id}/approve")
def approve(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "job not found")
    job.quality_label = "good"
    db.commit()
    return {"id": job_id, "quality_label": job.quality_label}


@router.post("/{job_id}/reject")
def reject(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "job not found")
    job.quality_label = "spam"
    db.commit()
    return {"id": job_id, "quality_label": job.quality_label}


@router.post("/{job_id}/retrack")
def retrack(job_id: int, body: RetrackBody, db: Session = Depends(get_db)) -> dict:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "job not found")
    job.track_predicted = body.track_predicted
    job.quality_label = body.quality_label or "good"
    db.commit()
    return {
        "id": job_id,
        "track_predicted": job.track_predicted,
        "quality_label": job.quality_label,
    }


class BatchBody(BaseModel):
    ids: list[int]
    action: str          # 'approve' | 'reject' | 'retrack'
    track_predicted: Optional[str] = None


@router.post("/batch")
def batch_action(body: BatchBody, db: Session = Depends(get_db)) -> dict:
    if body.action not in ("approve", "reject", "retrack"):
        raise HTTPException(400, "action must be approve|reject|retrack")
    if body.action == "retrack" and not body.track_predicted:
        raise HTTPException(400, "retrack requires track_predicted")

    jobs = db.query(Job).filter(Job.id.in_(body.ids)).all()
    for j in jobs:
        if body.action == "approve":
            j.quality_label = "good"
        elif body.action == "reject":
            j.quality_label = "spam"
        else:
            j.track_predicted = body.track_predicted or j.track_predicted
            j.quality_label = "good"
    db.commit()
    return {"updated": len(jobs), "action": body.action}


# ─── Teacher draft proxies ─────────────────────────────────────────
# These run server-side against the in-process teacher_entry admin code so
# the admin UI doesn't need to manage the TEACHER_ENTRY_ADMIN_TOKEN secret.

class TeacherRejectBody(BaseModel):
    reason: str = ""


@router.post("/teacher-drafts/{draft_id}/approve")
def teacher_draft_approve(draft_id: int, db: Session = Depends(get_db)) -> dict:
    """Approve a teacher-uploaded draft → promote to a Job row.
    Delegates to teacher_entry.admin_approve_draft logic (no token forwarded —
    the admin gate exists for cross-origin clients, not for same-process UI).

    T2 (2026-05-19): 复用 teacher_entry._validate_draft_for_approve 校验必填
    字段, 不让 detail_url 空的 draft 通过 promote。
    """
    from app.routers.teacher_entry import _promote_draft_to_job, _validate_draft_for_approve
    from app.services.scorer import score_all_jobs

    draft = db.query(JobDraft).filter(JobDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(404, f"draft {draft_id} not found")
    cur = draft.status or ""
    if cur not in {"pending", "draft"}:
        raise HTTPException(409, f"draft 当前状态 {cur} 不能 approve")

    # T2: 校验必填字段 (detail_url + company + title)
    _validate_draft_for_approve(draft)

    job = _promote_draft_to_job(db, draft)
    draft.status = "approved"
    draft.reviewed_at = datetime.utcnow()
    draft.updated_at = datetime.utcnow()
    db.commit()

    scores_written = 0
    try:
        scores_written = score_all_jobs(db, job_ids=[int(job.id)])
    except Exception:
        pass

    return {
        "draft_id": draft_id,
        "draft_status": "approved",
        "job_id": int(job.id),
        "job_external_id": str(job.job_id),
        "scores_written": scores_written,
    }


@router.post("/teacher-drafts/{draft_id}/reject")
def teacher_draft_reject(
    draft_id: int, body: TeacherRejectBody, db: Session = Depends(get_db)
) -> dict:
    draft = db.query(JobDraft).filter(JobDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(404, f"draft {draft_id} not found")
    cur = draft.status or ""
    if cur in {"approved", "rejected"}:
        raise HTTPException(409, f"draft 已是终态 {cur}，不能再 reject")
    draft.status = "rejected"
    draft.reject_reason = (body.reason or "")[:500]
    draft.reviewed_at = datetime.utcnow()
    draft.updated_at = datetime.utcnow()
    db.commit()
    return {
        "draft_id": draft_id,
        "draft_status": "rejected",
        "reject_reason": draft.reject_reason,
    }
