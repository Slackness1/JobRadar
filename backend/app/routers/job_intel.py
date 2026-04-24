"""Job Intel Router - 岗位情报接口"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, JobIntelTask, JobIntelRecord, JobIntelSnapshot
from app.schemas_job_intel import (
    JobIntelSearchRequest,
    JobIntelRefreshRequest,
    JobIntelTaskCreatedOut,
    JobIntelTaskOut,
    JobIntelSummaryOut,
    JobIntelRecordsListOut,
)
from app.services.intel.orchestrator import create_intel_task_for_job, refresh_intel_for_job
from app.services.platform_intel.browser.session_manager import get_platform_auth_status
from app.services.platform_intel.browser.login_bootstrap import bootstrap_login

router = APIRouter(prefix="/api/job-intel", tags=["job-intel"])


@router.post("/jobs/{job_id}/search", response_model=JobIntelTaskCreatedOut)
def search_job_intel(job_id: int, request: JobIntelSearchRequest, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return create_intel_task_for_job(
        db=db,
        job_id=job_id,
        trigger_mode=request.trigger_mode,
        platform_scope=request.platforms,
    )


@router.get("/jobs/{job_id}/summary", response_model=JobIntelSummaryOut)
def get_job_intel_summary(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    latest_task = (
        db.query(JobIntelTask)
        .filter(JobIntelTask.job_id == job_id)
        .order_by(JobIntelTask.created_at.desc())
        .first()
    )
    records_count = db.query(JobIntelRecord).filter(JobIntelRecord.job_id == job_id).count()
    snapshots = (
        db.query(JobIntelSnapshot)
        .filter(JobIntelSnapshot.job_id == job_id)
        .order_by(JobIntelSnapshot.created_at.desc())
        .all()
    )
    return JobIntelSummaryOut(
        job_id=job_id,
        latest_task_id=latest_task.id if latest_task else None,
        latest_task_status=latest_task.status if latest_task else "no_data",
        records_count=records_count,
        snapshots=snapshots,
    )


@router.get("/jobs/{job_id}/records", response_model=JobIntelRecordsListOut)
def get_job_intel_records(
    job_id: int,
    platform: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    query = db.query(JobIntelRecord).filter(JobIntelRecord.job_id == job_id)
    if platform:
        query = query.filter(JobIntelRecord.platform == platform)
    total = query.count()
    records = (
        query.order_by(JobIntelRecord.fetched_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return JobIntelRecordsListOut(
        items=records,
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
    )


@router.get("/jobs/{job_id}/tasks")
def get_job_intel_tasks(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    tasks = (
        db.query(JobIntelTask)
        .filter(JobIntelTask.job_id == job_id)
        .order_by(JobIntelTask.created_at.desc())
        .limit(10)
        .all()
    )
    return {"tasks": [JobIntelTaskOut.model_validate(t) for t in tasks]}


@router.get("/tasks/{task_id}", response_model=JobIntelTaskOut)
def get_job_intel_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(JobIntelTask).filter(JobIntelTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return JobIntelTaskOut.model_validate(task)


@router.post("/jobs/{job_id}/refresh", response_model=JobIntelTaskCreatedOut)
def refresh_job_intel(job_id: int, request: JobIntelRefreshRequest, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return refresh_intel_for_job(db, job_id, force=request.force)


@router.get("/platforms/status")
def get_platforms_status(db: Session = Depends(get_db)):
    _ = db
    return get_platform_auth_status()


@router.post("/platforms/{platform}/bootstrap-login")
async def bootstrap_platform_login(platform: str, db: Session = Depends(get_db)):
    _ = db
    return await bootstrap_login(platform)
