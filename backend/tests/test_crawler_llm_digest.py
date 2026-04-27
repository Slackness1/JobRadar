from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, CompanyCrawlLog, SystemConfig
from app.services.crawler_llm_digest import (
    DIGEST_KEY,
    aggregate_today_stats,
    generate_daily_digest,
    persist_digest,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _seed(db, company, source, new_count, status, started_at):
    row = CompanyCrawlLog(
        source=source,
        company=company,
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=60),
        status=status,
        fetched_count=new_count * 3 if new_count else 30,
        new_count=new_count,
        error_message="" if status == "success" else "boom",
        parent_log_id=None,
        duration_ms=60000,
    )
    db.add(row)
    db.commit()


def test_aggregate_today_stats_counts_correctly(db):
    today = datetime.utcnow()
    _seed(db, "腾讯", "internet_official", 5, "success", today)
    _seed(db, "阿里巴巴", "internet_official", 7, "success", today)
    _seed(db, "网易", "internet_official", 0, "failed", today)
    _seed(db, "中金", "securities_zhiye", 3, "success", today)

    stats = aggregate_today_stats(db, today)
    assert stats["total_companies"] == 4
    assert stats["successes"] == 3
    assert stats["failures"] == 1
    assert stats["total_new"] == 15
    assert stats["failed_companies"] == ["网易"]
    assert "互联网官网" in stats["by_group"]
    assert stats["by_group"]["互联网官网"] == 12


def test_aggregate_today_stats_excludes_yesterday(db):
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)
    _seed(db, "腾讯", "internet_official", 5, "success", today)
    _seed(db, "阿里巴巴", "internet_official", 7, "success", yesterday)

    stats = aggregate_today_stats(db, today)
    assert stats["total_companies"] == 1
    assert stats["total_new"] == 5


@patch("app.services.crawler_llm_digest.build_flash_client")
def test_generate_daily_digest_returns_string(mock_client):
    fake = MagicMock()
    fake_msg = MagicMock()
    fake_msg.content = "今早 09:00 跑完。"
    fake_choice = MagicMock()
    fake_choice.message = fake_msg
    fake_resp = MagicMock()
    fake_resp.choices = [fake_choice]
    fake.chat.completions.create.return_value = fake_resp
    mock_client.return_value = fake

    out = generate_daily_digest({
        "total_companies": 4,
        "successes": 3,
        "failures": 1,
        "total_new": 15,
        "failed_companies": ["网易"],
        "by_group": {"互联网官网": 12, "券商": 3},
    })
    assert out == "今早 09:00 跑完。"


@patch("app.services.crawler_llm_digest.build_flash_client")
def test_generate_daily_digest_returns_none_on_exception(mock_client):
    mock_client.return_value.chat.completions.create.side_effect = RuntimeError("net")
    out = generate_daily_digest({
        "total_companies": 0,
        "successes": 0,
        "failures": 0,
        "total_new": 0,
        "failed_companies": [],
        "by_group": {},
    })
    assert out is None


def test_persist_digest_upserts(db):
    persist_digest(db, "first text")
    rows = db.query(SystemConfig).filter_by(key=DIGEST_KEY).all()
    assert len(rows) == 1
    assert "first text" in rows[0].value

    persist_digest(db, "second text")
    rows = db.query(SystemConfig).filter_by(key=DIGEST_KEY).all()
    assert len(rows) == 1
    assert "second text" in rows[0].value
