from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Job


def _new_db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_job_application_status_default_and_update():
    db = _new_db_session()
    try:
        job = Job(
            job_id="test_job_1",
            source="tatawangshen",
            company="TestCo",
            job_title="Test Role",
            detail_url="https://example.com",
            application_status="待申请",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assert getattr(job, "application_status", "") == "待申请"

        setattr(job, "application_status", "已面试")
        db.commit()
        db.refresh(job)

        assert getattr(job, "application_status", "") == "已面试"
    finally:
        db.close()
