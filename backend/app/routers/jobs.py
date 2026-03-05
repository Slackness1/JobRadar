import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Job, JobScore, Track
from app.schemas import JobOut, JobListOut, JobStatsOut, JobScoreOut, JobApplicationStatusIn
from app.services.scorer import score_all_jobs
from app.services.system_config import get_spring_display_cutoff

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _build_job_out(job: Job, tracks_by_id: dict) -> JobOut:
    scores = []
    total = 0
    for s in job.scores:
        track = tracks_by_id.get(s.track_id)
        scores.append(JobScoreOut(
            track_id=s.track_id,
            track_key=track.key if track else "",
            track_name=track.name if track else "",
            score=s.score,
            matched_keywords=s.matched_keywords,
        ))
        weight = track.weight if track else 1.0
        total += int(s.score * weight)

    out = JobOut.model_validate(job)
    out.total_score = total
    out.scores = scores
    return out


def _apply_spring_cutoff(query, cutoff_dt: Optional[datetime]):
    if cutoff_dt is None:
        return query
    return query.filter(Job.publish_date >= cutoff_dt)


@router.get("/stats", response_model=JobStatsOut)
def job_stats(db: Session = Depends(get_db)):
    cutoff_dt = get_spring_display_cutoff(db)

    base_job_query = _apply_spring_cutoff(db.query(Job), cutoff_dt)

    total_jobs = base_job_query.count()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = base_job_query.filter(Job.created_at >= today_start).count()

    tracks = db.query(Track).all()
    by_track = {}
    for track in tracks:
        track_query = (
            db.query(func.count(JobScore.id))
            .join(Job, JobScore.job_id == Job.id)
            .filter(JobScore.track_id == track.id)
        )
        track_query = _apply_spring_cutoff(track_query, cutoff_dt)
        count = track_query.scalar()
        by_track[track.key] = count

    by_stage = {
        "campus": base_job_query.filter(Job.job_stage.in_(["campus", "both"])).count(),
        "internship": base_job_query.filter(Job.job_stage.in_(["internship", "both"])).count(),
    }

    return JobStatsOut(total_jobs=total_jobs, today_new=today_new, by_track=by_track, by_stage=by_stage)


@router.get("", response_model=JobListOut)
@router.get("/", response_model=JobListOut)
def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = "",
    tracks: str = "",
    min_score: int = 0,
    days: int = 0,
    job_stage: str = "all",
    sort_by: str = "total_score",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    all_tracks = db.query(Track).all()
    tracks_by_id = {t.id: t for t in all_tracks}

    query = db.query(Job).options(joinedload(Job.scores))
    cutoff_dt = get_spring_display_cutoff(db)
    query = _apply_spring_cutoff(query, cutoff_dt)

    if job_stage == "campus":
        query = query.filter(Job.job_stage.in_(["campus", "both"]))
    elif job_stage == "internship":
        query = query.filter(Job.job_stage.in_(["internship", "both"]))

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Job.job_title.ilike(pattern))
            | (Job.company.ilike(pattern))
            | (Job.location.ilike(pattern))
            | (Job.job_req.ilike(pattern))
        )

    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Job.publish_date >= cutoff)

    all_jobs = query.all()

    results = []
    for job in all_jobs:
        job_out = _build_job_out(job, tracks_by_id)

        if tracks:
            wanted_keys = set(tracks.split(","))
            job_track_keys = {s.track_key for s in job_out.scores}
            if not wanted_keys & job_track_keys:
                continue

        if min_score > 0 and job_out.total_score < min_score:
            continue

        results.append(job_out)

    reverse = sort_order == "desc"
    if sort_by == "total_score":
        results.sort(key=lambda x: x.total_score, reverse=reverse)
    elif sort_by == "publish_date":
        results.sort(key=lambda x: x.publish_date or datetime.min, reverse=reverse)
    elif sort_by == "company":
        results.sort(key=lambda x: x.company, reverse=reverse)

    total = len(results)
    start = (page - 1) * page_size
    page_items = results[start: start + page_size]

    return JobListOut(items=page_items, total=total, page=page, page_size=page_size)

@router.get("/company-expand", response_model=JobListOut)
def company_expand_jobs(
    company: str = Query(..., description="Company name to filter"),
    department: str = Query(..., description="Department name to filter"),
    scope: str = Query("current", description="Scope: 'current' for filtered, 'all' for unfiltered"),
    search: str = "",
    tracks: str = "",
    min_score: int = 0,
    days: int = 0,
    job_stage: str = "all",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get jobs for a specific company+department with optional scope filtering."""
    all_tracks = db.query(Track).all()
    tracks_by_id = {t.id: t for t in all_tracks}

    query = db.query(Job).options(joinedload(Job.scores))
    cutoff_dt = get_spring_display_cutoff(db)
    query = _apply_spring_cutoff(query, cutoff_dt)
    
    # Always filter by exact company and department
    query = query.filter(Job.company == company)
    query = query.filter(Job.department == department)
    if job_stage == "campus":
        query = query.filter(Job.job_stage.in_(["campus", "both"]))
    elif job_stage == "internship":
        query = query.filter(Job.job_stage.in_(["internship", "both"]))

    # Apply optional filters only if scope is 'current'
    if scope == "current":
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                (Job.job_title.ilike(pattern))
                | (Job.company.ilike(pattern))
                | (Job.location.ilike(pattern))
                | (Job.job_req.ilike(pattern))
            )

        if days > 0:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Job.publish_date >= cutoff)

    all_jobs = query.all()

    results = []
    for job in all_jobs:
        job_out = _build_job_out(job, tracks_by_id)

        # Apply track and score filters only in current scope
        if scope == "current":
            if tracks:
                wanted_keys = set(tracks.split(","))
                job_track_keys = {s.track_key for s in job_out.scores}
                if not wanted_keys & job_track_keys:
                    continue

            if min_score > 0 and job_out.total_score < min_score:
                continue

        results.append(job_out)

    # Sort by total_score descending
    results.sort(key=lambda x: x.total_score, reverse=True)

    total = len(results)
    start = (page - 1) * page_size
    page_items = results[start: start + page_size]

    return JobListOut(items=page_items, total=total, page=page, page_size=page_size)

@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).options(joinedload(Job.scores)).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    all_tracks = db.query(Track).all()
    tracks_by_id = {t.id: t for t in all_tracks}
    return _build_job_out(job, tracks_by_id)


@router.put("/{job_id}/application-status", response_model=JobOut)
def update_job_application_status(job_id: int, data: JobApplicationStatusIn, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")

    setattr(job, "application_status", data.application_status)
    db.commit()
    db.refresh(job)

    all_tracks = db.query(Track).all()
    tracks_by_id = {t.id: t for t in all_tracks}
    return _build_job_out(job, tracks_by_id)


def _parse_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s[:19] if 'T' in s else s, fmt)
        except ValueError:
            continue
    return None


@router.post("/import")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    existing_ids = set(row[0] for row in db.query(Job.job_id).all())

    imported = 0
    for row in reader:
        jid = row.get("job_id", "")
        if not jid or jid in existing_ids:
            continue
        db.add(Job(
            job_id=jid,
            source="tatawangshen",
            company=row.get("company", ""),
            company_type_industry=row.get("company_type_industry", ""),
            company_tags=row.get("company_tags", ""),
            department=row.get("department", ""),
            job_title=row.get("job_title", ""),
            location=row.get("location", ""),
            major_req=row.get("major_req", ""),
            job_req=row.get("job_req", ""),
            job_duty=row.get("job_duty", ""),
            application_status=row.get("application_status", "待申请") or "待申请",
            job_stage=row.get("job_stage", "campus") or "campus",
            source_config_id=row.get("source_config_id", ""),
            publish_date=_parse_date(row.get("publish_date", "")),
            deadline=_parse_date(row.get("deadline", "")),
            detail_url=row.get("detail_url", ""),
            scraped_at=_parse_date(row.get("scraped_at", "")) or datetime.utcnow(),
        ))
        existing_ids.add(jid)
        imported += 1

    db.commit()

    scored = 0
    if imported > 0:
        scored = score_all_jobs(db)

    return {"imported": imported, "scored": scored}
