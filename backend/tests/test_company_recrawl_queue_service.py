from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Job
from app.services.company_recrawl_queue import create_recrawl_task, process_company_recrawl_queue, retry_recrawl_task


def _new_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return testing_session_local()


def test_create_recrawl_task_dedupes_active_items():
    db = _new_db_session()
    try:
        first = create_recrawl_task(db, "Acme", "Campus", "careers.acme.com/jobs")
        second = create_recrawl_task(db, "Acme", "Campus", "https://careers.acme.com/jobs")
        assert first.id == second.id
    finally:
        db.close()


def test_process_company_recrawl_queue_creates_new_jobs(monkeypatch):
    db = _new_db_session()
    try:
        task = create_recrawl_task(db, "Acme", "Campus", "https://careers.acme.com/jobs")

        def _fake_crawl(career_url: str, company: str, department: str):
            return [
                {
                    "job_id": "company_site:acme:1",
                    "source": "company_site:acme.com",
                    "company": company,
                    "company_type_industry": "",
                    "company_tags": "",
                    "department": department,
                    "job_title": "Data Analyst",
                    "location": "",
                    "major_req": "",
                    "job_req": "",
                    "job_duty": "",
                    "application_status": "待申请",
                    "job_stage": "campus",
                    "source_config_id": career_url,
                    "publish_date": None,
                    "deadline": None,
                    "detail_url": "https://careers.acme.com/jobs/1",
                    "scraped_at": None,
                }
            ]

        monkeypatch.setattr("app.services.company_recrawl_queue.crawl_company_site", _fake_crawl)

        existing_jobs = {}
        new_count, fetched_count, notes = process_company_recrawl_queue(db, existing_jobs)

        db.refresh(task)
        assert task.status == "completed"
        assert new_count == 1
        assert fetched_count == 1
        assert notes == []
        assert db.query(Job).count() == 1
    finally:
        db.close()


def test_retry_recrawl_task_sets_pending():
    db = _new_db_session()
    try:
        task = create_recrawl_task(db, "Acme", "Campus", "https://careers.acme.com/jobs")
        task.status = "failed"
        task.last_error = "boom"
        db.commit()

        retried = retry_recrawl_task(db, task.id)
        assert retried is not None
        assert retried.status == "pending"
        assert retried.last_error == ""
    finally:
        db.close()
