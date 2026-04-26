"""Unit tests for _daily_tier_crawl_job — error isolation and CrawlLog creation."""
import pytest

from app.services.scheduler_service import _daily_tier_crawl_job


def test_tier_job_isolates_errors_per_tier(monkeypatch):
    """If internet tier raises, state_owned/securities/consumer_foreign still run."""
    calls = []

    def make_mock(name, raise_=False):
        def fn(*a, **kw):
            calls.append(name)
            if raise_:
                raise RuntimeError(f"{name} failed")
            return []
        return fn

    monkeypatch.setattr(
        "app.services.internet_crawler.crawl_internet_targets",
        make_mock("internet", raise_=True),
    )
    monkeypatch.setattr(
        "app.services.internet_crawler.build_internet_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.internet_crawler.select_primary_targets", lambda x: x
    )
    monkeypatch.setattr(
        "app.services.state_owned_crawler.crawl_state_owned_targets",
        make_mock("state_owned"),
    )
    monkeypatch.setattr(
        "app.services.state_owned_crawler.build_state_owned_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.crawl_consumer_targets",
        make_mock("consumer_foreign"),
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.build_consumer_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.select_primary_targets", lambda x: x
    )
    monkeypatch.setattr(
        "app.services.securities_crawler.run_configured_securities_crawl",
        lambda db, existing, parent_log_id=None: (0, 0, {}),
    )

    # Should not raise even though internet fails
    _daily_tier_crawl_job()

    # All four tiers were attempted
    assert "internet" in calls
    assert "state_owned" in calls
    assert "consumer_foreign" in calls


def test_tier_job_creates_parent_crawllog(monkeypatch):
    """Verify a tier-crawl CrawlLog row is written even with no real work."""
    monkeypatch.setattr(
        "app.services.internet_crawler.build_internet_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.internet_crawler.select_primary_targets", lambda x: x
    )
    monkeypatch.setattr(
        "app.services.internet_crawler.crawl_internet_targets",
        lambda db, targets, parent_log_id=None: [],
    )
    monkeypatch.setattr(
        "app.services.state_owned_crawler.build_state_owned_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.state_owned_crawler.crawl_state_owned_targets",
        lambda db, targets, parent_log_id=None: [],
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.build_consumer_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.select_primary_targets", lambda x: x
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.crawl_consumer_targets",
        lambda db, targets, parent_log_id=None: [],
    )
    monkeypatch.setattr(
        "app.services.securities_crawler.run_configured_securities_crawl",
        lambda db, existing, parent_log_id=None: (0, 0, {}),
    )

    from app.database import SessionLocal
    from app.models import CrawlLog

    db = SessionLocal()
    try:
        before = db.query(CrawlLog).filter(CrawlLog.source == "tier-crawl").count()
        _daily_tier_crawl_job()
        after = db.query(CrawlLog).filter(CrawlLog.source == "tier-crawl").count()
        assert after == before + 1
        # Verify the new row is finalized
        latest = (
            db.query(CrawlLog)
            .filter(CrawlLog.source == "tier-crawl")
            .order_by(CrawlLog.id.desc())
            .first()
        )
        assert latest.status == "success"
        assert latest.finished_at is not None
    finally:
        db.close()


def test_tier_job_marks_failed_status_on_error(monkeypatch):
    """If any tier raises, the parent CrawlLog status is 'failed'."""
    monkeypatch.setattr(
        "app.services.internet_crawler.build_internet_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.internet_crawler.select_primary_targets", lambda x: x
    )
    monkeypatch.setattr(
        "app.services.internet_crawler.crawl_internet_targets",
        lambda db, targets, parent_log_id=None: (_ for _ in ()).throw(
            RuntimeError("internet boom")
        ),
    )
    monkeypatch.setattr(
        "app.services.state_owned_crawler.build_state_owned_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.state_owned_crawler.crawl_state_owned_targets",
        lambda db, targets, parent_log_id=None: [],
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.build_consumer_targets", lambda: []
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.select_primary_targets", lambda x: x
    )
    monkeypatch.setattr(
        "app.services.consumer_foreign_crawler.crawl_consumer_targets",
        lambda db, targets, parent_log_id=None: [],
    )
    monkeypatch.setattr(
        "app.services.securities_crawler.run_configured_securities_crawl",
        lambda db, existing, parent_log_id=None: (0, 0, {}),
    )

    from app.database import SessionLocal
    from app.models import CrawlLog

    db = SessionLocal()
    try:
        _daily_tier_crawl_job()
        latest = (
            db.query(CrawlLog)
            .filter(CrawlLog.source == "tier-crawl")
            .order_by(CrawlLog.id.desc())
            .first()
        )
        assert latest.status == "failed"
        assert latest.error_message is not None
        assert "internet" in latest.error_message
    finally:
        db.close()
