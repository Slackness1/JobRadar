"""Export filtered jobs to CSV/Excel/JSON."""
import csv
import io
import json
from datetime import datetime, timedelta
from typing import Optional

from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.models import Job, Track
from app.services.system_config import get_spring_display_cutoff

DEFAULT_FIELDS = [
    "job_id", "company", "company_type_industry", "department",
    "job_title", "job_stage", "location", "major_req", "publish_date",
    "detail_url", "total_score", "matched_tracks",
]


def _query_jobs(db: Session, search: str = "", tracks_filter: Optional[list[str]] = None,
                min_score: int = 0, days: int = 0, job_stage: str = "all") -> list[dict]:
    all_tracks = db.query(Track).all()
    tracks_by_id = {t.id: t for t in all_tracks}

    query = db.query(Job).options(joinedload(Job.scores))
    cutoff_dt = get_spring_display_cutoff(db)
    if cutoff_dt is not None:
        query = query.filter(Job.publish_date >= cutoff_dt)

    if job_stage == "campus":
        query = query.filter(Job.job_stage.in_(["campus", "both"]))
    elif job_stage == "internship":
        query = query.filter(Job.job_stage.in_(["internship", "both"]))

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Job.job_title.ilike(pattern)) | (Job.company.ilike(pattern))
        )

    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Job.publish_date >= cutoff)

    jobs = query.all()
    results = []

    for job in jobs:
        total = 0
        matched_track_names = []
        for s in job.scores:
            track = tracks_by_id.get(s.track_id)
            if track:
                total += int(s.score * track.weight)
                matched_track_names.append(track.name)

        if tracks_filter:
            job_keys = {tracks_by_id[s.track_id].key for s in job.scores if s.track_id in tracks_by_id}
            if not set(tracks_filter) & job_keys:
                continue

        if min_score > 0 and total < min_score:
            continue

        publish_date = getattr(job, "publish_date", None)
        deadline = getattr(job, "deadline", None)

        row = {
            "job_id": job.job_id,
            "company": job.company,
            "company_type_industry": job.company_type_industry,
            "company_tags": job.company_tags,
            "department": job.department,
            "job_title": job.job_title,
            "job_stage": job.job_stage,
            "location": job.location,
            "major_req": job.major_req,
            "job_req": job.job_req,
            "job_duty": job.job_duty,
            "publish_date": publish_date.strftime("%Y-%m-%d") if isinstance(publish_date, datetime) else "",
            "deadline": deadline.strftime("%Y-%m-%d") if isinstance(deadline, datetime) else "",
            "detail_url": job.detail_url,
            "total_score": total,
            "matched_tracks": "; ".join(matched_track_names),
        }
        results.append(row)

    results.sort(key=lambda x: -x["total_score"])
    return results


def export_csv(db: Session, fields: Optional[list[str]] = None, **filters) -> str:
    rows = _query_jobs(db, **filters)
    if not fields:
        fields = DEFAULT_FIELDS
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def export_excel(db: Session, fields: Optional[list[str]] = None, **filters) -> bytes:
    rows = _query_jobs(db, **filters)
    if not fields:
        fields = DEFAULT_FIELDS
    wb = Workbook()
    ws = wb.active
    if ws is None:
        return b""
    ws.title = "Jobs"
    ws.append(fields)
    for row in rows:
        ws.append([row.get(f, "") for f in fields])
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def export_json(db: Session, fields: Optional[list[str]] = None, **filters) -> str:
    rows = _query_jobs(db, **filters)
    if fields:
        rows = [{k: v for k, v in row.items() if k in fields} for row in rows]
    return json.dumps(rows, ensure_ascii=False, indent=2)
