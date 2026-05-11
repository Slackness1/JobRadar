"""Review queue router.

Surfaces jobs whose LLM enrichment left them ambiguous so a human can
quality-check / re-track / dismiss them.

Selection rule for "needs review":
    quality_label IN ('', 'low_signal') OR
    (track_predicted == '' AND created_at within last 30d)

Approve  -> quality_label = 'good'
Reject   -> quality_label = 'spam'
Retrack  -> track_predicted = <new>; quality_label = 'good'
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job


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

    return {
        "items": items,
        "summary": {
            "FinTech":  {"queue": bucket_counts["FinTech"],  "live": live_counts["FinTech"]},
            "纯金融":   {"queue": bucket_counts["纯金融"],   "live": live_counts["纯金融"]},
            "其他":     {"queue": bucket_counts["其他"],     "live": live_counts["其他"]},
        },
        "total_pending": base.count(),
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
