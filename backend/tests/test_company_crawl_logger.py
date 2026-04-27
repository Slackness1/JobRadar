import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, CompanyCrawlLog
from app.services.company_crawl_logger import company_crawl_log


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_success_path_sets_status_and_counts(db):
    with company_crawl_log(db, source="internet_official", company="腾讯", parent_log_id=42) as log:
        log.fetched_count = 100
        log.new_count = 12

    rows = db.query(CompanyCrawlLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "success"
    assert row.source == "internet_official"
    assert row.company == "腾讯"
    assert row.parent_log_id == 42
    assert row.fetched_count == 100
    assert row.new_count == 12
    assert row.finished_at is not None
    assert row.duration_ms >= 0
    assert row.error_message == ""


def test_exception_path_marks_failed_and_truncates(db):
    long_msg = "boom-" * 200  # 1000 chars

    with pytest.raises(RuntimeError):
        with company_crawl_log(db, source="securities_zhiye", company="中金公司", parent_log_id=None):
            raise RuntimeError(long_msg)

    row = db.query(CompanyCrawlLog).one()
    assert row.status == "failed"
    assert row.error_message.startswith("boom-")
    assert len(row.error_message) == 500
    assert row.finished_at is not None


def test_running_row_visible_before_block_exits(db):
    """During the with-block, status='running' is committed so external readers can see in-flight runs."""
    with company_crawl_log(db, source="internet_official", company="字节跳动", parent_log_id=None) as log:
        # Use a separate session to query — the row should already be committed
        OtherSession = sessionmaker(bind=db.bind)
        other = OtherSession()
        try:
            in_flight = other.query(CompanyCrawlLog).filter_by(company="字节跳动").one()
            assert in_flight.status == "running"
            assert in_flight.finished_at is None
        finally:
            other.close()
        log.fetched_count = 5
        log.new_count = 5
