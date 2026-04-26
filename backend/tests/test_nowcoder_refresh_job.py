from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import InterviewIntelKeyword, InterviewIntelPost
from app.services.interview.nowcoder import refresh_job
from app.services.interview.nowcoder.scraper import PostDetail, PostMeta


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


_KEYWORDS_STUB = [
    {"chip": "产品经理", "query": "产品经理面经"},
    {"chip": "数据分析师", "query": "数据分析面经"},
]


def _meta(pid):
    return PostMeta(pid=pid, title=f"title-{pid}")


def _detail(pid, status="ok"):
    return PostDetail(
        pid=pid, company="A", interview_date="26-4-14", position="P",
        questions_text="Q1; Q2", parse_status=status,
    )


def test_run_refresh_writes_keyword_and_posts(db):
    with (
        patch.object(refresh_job, "_load_keywords", return_value=_KEYWORDS_STUB),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              side_effect=lambda q, limit: [_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post",
              side_effect=lambda pid: _detail(pid)),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword",
              return_value="## summary"),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
    ):
        stats = refresh_job.run_refresh(db)

    assert stats.keywords_total == 2
    assert stats.keywords_ok == 2
    assert stats.posts_fetched == 4  # 2 chips × 2 posts
    assert db.query(InterviewIntelKeyword).count() == 2
    assert db.query(InterviewIntelPost).count() == 4


def test_run_refresh_skips_recently_fetched_posts(db):
    db.add(InterviewIntelPost(
        pid="100", keyword="产品经理", title="cached", fetched_at=datetime.utcnow() - timedelta(hours=2),
        parse_status="ok",
    ))
    db.commit()
    fetch_calls = []

    def fake_fetch(pid):
        fetch_calls.append(pid)
        return _detail(pid)

    with (
        patch.object(refresh_job, "_load_keywords", return_value=[_KEYWORDS_STUB[0]]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              return_value=[_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post", side_effect=fake_fetch),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword",
              return_value="x"),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
    ):
        refresh_job.run_refresh(db)

    assert fetch_calls == ["200"]  # 100 was skipped (within 24h)


def test_run_refresh_keyword_failure_does_not_block_others(db):
    def search_side(query, limit):
        if "产品经理" in query:
            raise RuntimeError("network down")
        return [_meta("777")]

    with (
        patch.object(refresh_job, "_load_keywords", return_value=_KEYWORDS_STUB),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search", side_effect=search_side),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post", return_value=_detail("777")),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword", return_value="ok"),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
    ):
        stats = refresh_job.run_refresh(db)

    assert stats.keywords_failed == 1
    assert stats.keywords_ok == 1
    rows = db.query(InterviewIntelKeyword).all()
    by_kw = {r.keyword: r for r in rows}
    assert by_kw["产品经理"].last_error
    assert by_kw["数据分析师"].summary_md == "ok"


def test_status_helpers_round_trip(db):
    refresh_job._record_status({"last_status": "ok", "keywords_total": 16})
    out = refresh_job.get_last_refresh_status()
    assert out["last_status"] == "ok"
    assert out["keywords_total"] == 16
