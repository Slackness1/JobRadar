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


def _patch_quality():
    """Quality scorer pass-through: every detail scores 3 (high)."""
    return patch(
        "app.services.interview.nowcoder.refresh_job.quality_scorer.score_post_quality",
        return_value=3,
    )


def test_run_refresh_writes_keyword_and_posts(db):
    with (
        patch.object(refresh_job, "_load_keywords", return_value=_KEYWORDS_STUB),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              side_effect=lambda q, limit: [_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post",
              side_effect=lambda pid, title="": _detail(pid)),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword",
              return_value="## summary"),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
        _patch_quality(),
    ):
        stats = refresh_job.run_refresh(db, max_workers=1)

    assert stats.keywords_total == 2
    assert stats.keywords_ok == 2
    # 2 chips × 2 metas = 4 chip-post bindings; pid 100 and 200 are shared
    # across chips, so detail fetch is deduped, but each binding still counts
    # as a post upserted into the chip's own row.
    assert stats.posts_fetched == 4
    assert db.query(InterviewIntelKeyword).count() == 2
    assert db.query(InterviewIntelPost).count() == 4


def test_run_refresh_pid_cache_dedups_detail_fetch_across_chips(db):
    """A pid that appears in multiple chip search results should only hit
    fetch_post once per refresh (cross-chip detail cache)."""
    fetch_calls = []

    def fake_fetch(pid, title=""):
        fetch_calls.append(pid)
        return _detail(pid)

    with (
        patch.object(refresh_job, "_load_keywords", return_value=_KEYWORDS_STUB),
        # Both chips return the SAME pid set
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              side_effect=lambda q, limit: [_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post", side_effect=fake_fetch),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword", return_value="x"),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
        _patch_quality(),
    ):
        refresh_job.run_refresh(db, max_workers=1)

    # 2 chips × 2 pids = 4 bindings, but only 2 unique pids → 2 fetches
    assert sorted(fetch_calls) == ["100", "200"]
    assert db.query(InterviewIntelPost).count() == 4


def test_run_refresh_low_quality_excluded_from_summary(db):
    score_calls = []

    def fake_score(detail):
        # pid=100 → low quality 1 (excluded), pid=200 → 3 (kept)
        score = 1 if detail.pid == "100" else 3
        score_calls.append((detail.pid, score))
        return score

    summarize_p = patch(
        "app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword",
        return_value="ok",
    )
    score_p = patch(
        "app.services.interview.nowcoder.refresh_job.quality_scorer.score_post_quality",
        side_effect=fake_score,
    )
    with (
        patch.object(refresh_job, "_load_keywords", return_value=[_KEYWORDS_STUB[0]]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              return_value=[_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post",
              side_effect=lambda pid, title="": _detail(pid)),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
        summarize_p, score_p,
    ):
        refresh_job.run_refresh(db, max_workers=1)

    # Both posts in DB, but only the high-quality one drove summarization
    assert db.query(InterviewIntelPost).count() == 2
    kw = db.query(InterviewIntelKeyword).filter_by(keyword="产品经理").one()
    assert kw.source_count == 1  # only pid=200 (quality=3) survives the gate
    assert kw.summary_md == "ok"


def test_run_refresh_skips_recently_fetched_posts(db):
    db.add(InterviewIntelPost(
        pid="100", keyword="产品经理", title="cached",
        fetched_at=datetime.utcnow() - timedelta(hours=2),
        parse_status="ok", quality_score=3,
    ))
    db.commit()
    fetch_calls = []

    def fake_fetch(pid, title=""):
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
        _patch_quality(),
    ):
        refresh_job.run_refresh(db, max_workers=1)

    assert fetch_calls == ["200"]  # 100 was skipped (within 24h)


def test_run_refresh_skips_summarize_when_pid_set_unchanged(db):
    """If the ok_posts pid set hashes the same as a previous summary,
    summarize_keyword must NOT be called again (LLM-cost guard)."""
    # First run: posts 100 + 200, summary generated.
    summarize_calls = []

    def fake_summarize(chip, posts):
        summarize_calls.append([p.pid for p in posts])
        return "## summary v1"

    with (
        patch.object(refresh_job, "_load_keywords", return_value=[_KEYWORDS_STUB[0]]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              return_value=[_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post",
              side_effect=lambda pid, title="": _detail(pid)),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword",
              side_effect=fake_summarize),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
        _patch_quality(),
    ):
        refresh_job.run_refresh(db, max_workers=1)

    assert len(summarize_calls) == 1
    kw = db.query(InterviewIntelKeyword).filter_by(keyword="产品经理").one()
    assert kw.posts_hash  # must persist
    first_hash = kw.posts_hash

    # Second run: same pids, but bump fetched_at outside fresh window so
    # search→fetch is exercised. Hash should match → summarize SKIPPED.
    db.query(InterviewIntelPost).update(
        {"fetched_at": datetime.utcnow() - timedelta(hours=48)}
    )
    db.commit()

    with (
        patch.object(refresh_job, "_load_keywords", return_value=[_KEYWORDS_STUB[0]]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              return_value=[_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post",
              side_effect=lambda pid, title="": _detail(pid)),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword",
              side_effect=fake_summarize),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
        _patch_quality(),
    ):
        refresh_job.run_refresh(db, max_workers=1)

    assert len(summarize_calls) == 1, "summarize_keyword should be skipped on hash match"
    kw2 = db.query(InterviewIntelKeyword).filter_by(keyword="产品经理").one()
    assert kw2.posts_hash == first_hash


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
        _patch_quality(),
    ):
        stats = refresh_job.run_refresh(db, max_workers=1)

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
