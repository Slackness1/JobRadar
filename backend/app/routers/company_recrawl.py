from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    CompanyRecrawlQueueCreateIn,
    CompanyRecrawlQueueListOut,
    CompanyRecrawlQueueOut,
)
from app.services.company_recrawl_queue import (
    create_recrawl_task,
    delete_recrawl_task,
    list_recrawl_tasks,
    retry_recrawl_task,
)


router = APIRouter(prefix="/api/recrawl-queue", tags=["company-recrawl"])


@router.post("", response_model=CompanyRecrawlQueueOut)
@router.post("/", response_model=CompanyRecrawlQueueOut)
def create_company_recrawl_task(payload: CompanyRecrawlQueueCreateIn, db: Session = Depends(get_db)):
    task = create_recrawl_task(
        db,
        company=payload.company,
        department=payload.department,
        career_url=payload.career_url,
    )
    return task


@router.get("", response_model=CompanyRecrawlQueueListOut)
@router.get("/", response_model=CompanyRecrawlQueueListOut)
def get_company_recrawl_tasks(
    status: Optional[str] = Query(None, description="pending/running/failed/completed"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    items, total = list_recrawl_tasks(db, status=status, limit=limit)
    return CompanyRecrawlQueueListOut(items=items, total=total)


@router.put("/{task_id}/retry", response_model=CompanyRecrawlQueueOut)
def retry_company_recrawl_task(task_id: int, db: Session = Depends(get_db)):
    task = retry_recrawl_task(db, task_id)
    if task is None:
        raise HTTPException(404, "Queue task not found")
    return task


@router.delete("/{task_id}")
def remove_company_recrawl_task(task_id: int, db: Session = Depends(get_db)):
    deleted = delete_recrawl_task(db, task_id)
    if not deleted:
        raise HTTPException(404, "Queue task not found")
    return {"ok": True}
