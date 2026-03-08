from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import CompanyRecrawlQueue, Job
from app.services.company_site_recrawl import crawl_company_site


ACTIVE_STATUSES = {"pending", "running"}


def _normalize_text(value: str) -> str:
    return (value or "").strip()


def _normalize_url(url: str) -> str:
    value = _normalize_text(url)
    if not value:
        return value
    if not value.startswith("http://") and not value.startswith("https://"):
        value = f"https://{value}"
    return value


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def create_recrawl_task(db: Session, company: str, department: str, career_url: str) -> CompanyRecrawlQueue:
    company_text = _normalize_text(company)
    department_text = _normalize_text(department)
    normalized_url = _normalize_url(career_url)
    domain = _extract_domain(normalized_url)

    existing = (
        db.query(CompanyRecrawlQueue)
        .filter(CompanyRecrawlQueue.company == company_text)
        .filter(CompanyRecrawlQueue.department == department_text)
        .filter(CompanyRecrawlQueue.career_url == normalized_url)
        .filter(CompanyRecrawlQueue.status.in_(list(ACTIVE_STATUSES)))
        .order_by(CompanyRecrawlQueue.id.desc())
        .first()
    )
    if existing is not None:
        return existing

    task = CompanyRecrawlQueue(
        company=company_text,
        department=department_text,
        career_url=normalized_url,
        source_domain=domain,
        status="pending",
        attempt_count=0,
        fetched_count=0,
        new_count=0,
        last_error="",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        finished_at=None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_recrawl_tasks(db: Session, status: Optional[str] = None, limit: int = 200) -> tuple[list[CompanyRecrawlQueue], int]:
    query = db.query(CompanyRecrawlQueue)
    if status:
        query = query.filter(CompanyRecrawlQueue.status == status)
    total = query.count()
    items = query.order_by(CompanyRecrawlQueue.id.desc()).limit(limit).all()
    return items, total


def retry_recrawl_task(db: Session, task_id: int) -> Optional[CompanyRecrawlQueue]:
    task = db.get(CompanyRecrawlQueue, task_id)
    if task is None:
        return None

    task.status = "pending"
    task.last_error = ""
    task.finished_at = None
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


def delete_recrawl_task(db: Session, task_id: int) -> bool:
    task = db.get(CompanyRecrawlQueue, task_id)
    if task is None:
        return False
    db.delete(task)
    db.commit()
    return True


def mark_stale_running_tasks_failed(db: Session) -> int:
    stale_tasks = db.query(CompanyRecrawlQueue).filter(CompanyRecrawlQueue.status == "running").all()
    if not stale_tasks:
        return 0

    now = datetime.now(timezone.utc)
    for task in stale_tasks:
        task.status = "failed"
        task.finished_at = now
        task.updated_at = now
        if not task.last_error:
            task.last_error = "Interrupted by service restart"

    db.commit()
    return len(stale_tasks)


def process_company_recrawl_queue(db: Session, existing_jobs: dict[str, Job], limit: int = 20) -> tuple[int, int, list[str]]:
    pending_tasks = (
        db.query(CompanyRecrawlQueue)
        .filter(CompanyRecrawlQueue.status == "pending")
        .order_by(CompanyRecrawlQueue.created_at.asc(), CompanyRecrawlQueue.id.asc())
        .limit(limit)
        .all()
    )

    total_new = 0
    total_fetched = 0
    notes: list[str] = []

    for task in pending_tasks:
        task.status = "running"
        task.attempt_count = int(task.attempt_count or 0) + 1
        task.updated_at = datetime.now(timezone.utc)
        db.commit()

        try:
            records = crawl_company_site(task.career_url, task.company, task.department)
            fetched_count = len(records)
            new_count = 0

            for mapped in records:
                job_id = mapped.get("job_id", "")
                if not job_id:
                    continue

                existing = existing_jobs.get(job_id)
                if existing is not None:
                    continue

                created = Job(**mapped)
                db.add(created)
                existing_jobs[job_id] = created
                new_count += 1

            task.status = "completed"
            task.fetched_count = fetched_count
            task.new_count = new_count
            task.last_error = ""
            task.finished_at = datetime.now(timezone.utc)
            task.updated_at = datetime.now(timezone.utc)

            db.commit()

            total_fetched += fetched_count
            total_new += new_count
        except Exception as exc:
            task.status = "failed"
            task.last_error = str(exc)[:500]
            task.finished_at = datetime.now(timezone.utc)
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            notes.append(f"Company recrawl failed for {task.company}: {task.last_error}")

    return total_new, total_fetched, notes
