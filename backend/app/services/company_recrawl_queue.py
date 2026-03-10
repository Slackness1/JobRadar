from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

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
    parsed = urlparse(value)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = (parsed.path or "/").rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _task_dedupe_key(company: str, department: str, career_url: str) -> tuple[str, str, str]:
    return (_normalize_text(company).lower(), _normalize_text(department).lower(), _normalize_url(career_url))


def _build_existing_jobs_map(db: Session) -> dict[str, Job]:
    mapping: dict[str, Job] = {}
    for job in db.query(Job).all():
        job_id_value = getattr(job, "job_id", "")
        if job_id_value:
            mapping[job_id_value] = job
    return mapping


def _prepare_pending_batch(
    db: Session,
    pending_tasks: list[CompanyRecrawlQueue],
) -> tuple[list[CompanyRecrawlQueue], int, list[str]]:
    unique_tasks: list[CompanyRecrawlQueue] = []
    dedupe_by_key: dict[tuple[str, str, str], CompanyRecrawlQueue] = {}
    deduped_count = 0
    notes: list[str] = []

    for task in pending_tasks:
        key = _task_dedupe_key(task.company, task.department, task.career_url)
        kept = dedupe_by_key.get(key)
        if kept is None:
            dedupe_by_key[key] = task
            unique_tasks.append(task)
            continue

        task.status = "completed"
        task.fetched_count = 0
        task.new_count = 0
        task.last_error = f"Deduplicated with queue task #{kept.id}"
        task.finished_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        deduped_count += 1

    if deduped_count:
        db.commit()
        notes.append(f"Deduplicated {deduped_count} pending duplicate queue task(s)")

    return unique_tasks, deduped_count, notes


def _validate_crawl_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    valid: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()
    seen_urls: set[str] = set()
    dropped = 0

    for item in records:
        job_id = _normalize_text(str(item.get("job_id", "")))
        title = _normalize_text(str(item.get("job_title", "")))
        detail_url = _normalize_url(str(item.get("detail_url", "")))

        if not job_id or not title or len(title) < 2 or not detail_url:
            dropped += 1
            continue

        if job_id in seen_job_ids or detail_url in seen_urls:
            dropped += 1
            continue

        item["job_id"] = job_id
        item["job_title"] = title
        item["detail_url"] = detail_url
        seen_job_ids.add(job_id)
        seen_urls.add(detail_url)
        valid.append(item)

    return valid, dropped


def create_recrawl_task(db: Session, company: str, department: str, career_url: str) -> CompanyRecrawlQueue:
    company_text = _normalize_text(company)
    department_text = _normalize_text(department)
    normalized_url = _normalize_url(career_url)
    domain = _extract_domain(normalized_url)

    candidates = (
        db.query(CompanyRecrawlQueue)
        .filter(CompanyRecrawlQueue.company == company_text)
        .filter(CompanyRecrawlQueue.department == department_text)
        .order_by(CompanyRecrawlQueue.id.desc())
        .all()
    )
    existing: Optional[CompanyRecrawlQueue] = None
    for candidate in candidates:
        if _normalize_url(candidate.career_url) == normalized_url:
            existing = candidate
            break

    if existing is not None:
        if existing.status in ACTIVE_STATUSES:
            return existing

        existing.career_url = normalized_url
        existing.source_domain = domain
        existing.status = "pending"
        existing.last_error = ""
        existing.finished_at = None
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
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


def _process_company_recrawl_queue_internal(
    db: Session,
    existing_jobs: dict[str, Job],
    limit: int = 20,
) -> tuple[int, int, list[str], int, int]:
    pending_tasks = (
        db.query(CompanyRecrawlQueue)
        .filter(CompanyRecrawlQueue.status == "pending")
        .order_by(CompanyRecrawlQueue.created_at.asc(), CompanyRecrawlQueue.id.asc())
        .limit(limit)
        .all()
    )

    total_new = 0
    total_fetched = 0
    failed_count = 0
    notes: list[str] = []

    unique_tasks, deduped_count, dedupe_notes = _prepare_pending_batch(db, pending_tasks)
    notes.extend(dedupe_notes)

    processed_count = deduped_count
    for task in unique_tasks:
        task.status = "running"
        task.attempt_count = int(task.attempt_count or 0) + 1
        task.updated_at = datetime.now(timezone.utc)
        db.commit()

        try:
            records = crawl_company_site(task.career_url, task.company, task.department)
            validated_records, dropped_count = _validate_crawl_records(records)
            fetched_count = len(validated_records)
            if dropped_count > 0:
                notes.append(f"Dropped {dropped_count} invalid/duplicate record(s) for {task.company}")
            if fetched_count == 0:
                raise ValueError("No valid job records extracted from company career page")
            new_count = 0

            for mapped in validated_records:
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

            processed_count += 1

            total_fetched += fetched_count
            total_new += new_count
        except Exception as exc:
            task.status = "failed"
            task.last_error = str(exc)[:500]
            task.finished_at = datetime.now(timezone.utc)
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            processed_count += 1
            failed_count += 1
            notes.append(f"Company recrawl failed for {task.company}: {task.last_error}")

    return total_new, total_fetched, notes, processed_count, failed_count


def process_company_recrawl_queue(
    db: Session,
    existing_jobs: dict[str, Job],
    limit: int = 20,
) -> tuple[int, int, list[str]]:
    total_new, total_fetched, notes, _processed_count, _failed_count = _process_company_recrawl_queue_internal(
        db,
        existing_jobs=existing_jobs,
        limit=limit,
    )
    return total_new, total_fetched, notes


def run_all_pending_recrawls(db: Session, batch_size: int = 20) -> dict[str, Any]:
    size = max(1, int(batch_size or 20))
    requested_pending = db.query(CompanyRecrawlQueue).filter(CompanyRecrawlQueue.status == "pending").count()
    existing_jobs = _build_existing_jobs_map(db)

    total_new = 0
    total_fetched = 0
    total_processed = 0
    total_failed = 0
    notes: list[str] = []

    while True:
        pending_count = db.query(CompanyRecrawlQueue).filter(CompanyRecrawlQueue.status == "pending").count()
        if pending_count <= 0:
            break

        new_count, fetched_count, batch_notes, processed_count, failed_count = _process_company_recrawl_queue_internal(
            db,
            existing_jobs=existing_jobs,
            limit=min(size, pending_count),
        )

        total_new += new_count
        total_fetched += fetched_count
        total_processed += processed_count
        total_failed += failed_count
        notes.extend(batch_notes)

        if processed_count == 0:
            notes.append("Stopped batch recrawl because no queue task was processed")
            break

    return {
        "requested_pending": requested_pending,
        "processed": total_processed,
        "completed": max(0, total_processed - total_failed),
        "failed": total_failed,
        "total_fetched": total_fetched,
        "total_new": total_new,
        "notes": notes[:50],
        "message": "Company recrawl queue finished",
    }
