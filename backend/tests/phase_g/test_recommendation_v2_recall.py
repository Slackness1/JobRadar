"""Phase G T14 — recommendation_v2 recall SQL 测试 (内存 SQLite 独立 schema)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Job
from app.services.phase_g.recommendation_v2.recall import recall_candidates


@pytest.fixture
def db():
    """Isolated in-memory SQLite session per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


def _make_job(
    job_id: str,
    *,
    sub_category: str | None = None,
    sub_category_secondary: str | None = None,
    quality_label: str = "good",
    scraped_days_ago: int = 1,
    link_status: str | None = None,
    company: str = "TestCo",
) -> Job:
    return Job(
        job_id=job_id,
        company=company,
        job_title=f"Title-{job_id}",
        sub_category=sub_category,
        sub_category_secondary=sub_category_secondary,
        quality_label=quality_label,
        scraped_at=datetime.utcnow() - timedelta(days=scraped_days_ago),
        link_status=link_status,
    )


def test_recall_excludes_sub_category_null(db):
    """sub_category NULL 的帖永远不进推荐池。"""
    db.add_all([
        _make_job("a", sub_category="量化研究员·中频"),
        _make_job("b", sub_category=None),  # 没 enrich, 不能进
        _make_job("c", sub_category="公募权益研究员"),
    ])
    db.commit()
    results = recall_candidates(db, preferred_sub_cats=())
    ids = {j.job_id for j in results}
    assert ids == {"a", "c"}


def test_recall_excludes_bad_quality_labels(db):
    """support_role / low_pay / spam / low_signal / agency 不进, 即使 sub_category 有。"""
    db.add_all([
        _make_job("a", sub_category="量化研究员·中频", quality_label="good"),
        _make_job("b", sub_category="量化研究员·中频", quality_label="support_role"),
        _make_job("c", sub_category="量化研究员·中频", quality_label="low_pay"),
        _make_job("d", sub_category="量化研究员·中频", quality_label="spam"),
        _make_job("e", sub_category="量化研究员·中频", quality_label="agency"),
        _make_job("f", sub_category="量化研究员·中频", quality_label="low_signal"),
        _make_job("g", sub_category="量化研究员·中频", quality_label="internship_only"),
    ])
    db.commit()
    results = recall_candidates(db)
    ids = {j.job_id for j in results}
    assert ids == {"a", "g"}  # good + internship_only


def test_recall_excludes_stale_jobs(db):
    """超过 freshness_days 的帖被剔除。"""
    db.add_all([
        _make_job("fresh", sub_category="量化·中频", scraped_days_ago=10),
        _make_job("stale", sub_category="量化·中频", scraped_days_ago=45),
    ])
    db.commit()
    results = recall_candidates(db, freshness_days=30)
    assert {j.job_id for j in results} == {"fresh"}


def test_recall_excludes_dead_links(db):
    """link_status='dead' 不进推荐池, alive 或 NULL 可以。"""
    db.add_all([
        _make_job("alive", sub_category="量化·中频", link_status="alive"),
        _make_job("null", sub_category="量化·中频", link_status=None),
        _make_job("dead", sub_category="量化·中频", link_status="dead"),
        _make_job("uncertain", sub_category="量化·中频", link_status="uncertain"),
    ])
    db.commit()
    results = recall_candidates(db)
    # 严格: 只 alive + NULL, dead 和 uncertain 都不进
    assert {j.job_id for j in results} == {"alive", "null"}


def test_recall_matches_primary_or_secondary(db):
    """preferred_sub_cats 命中 primary 或 secondary 都算。"""
    db.add_all([
        _make_job("p_only", sub_category="量化·中频", sub_category_secondary=None),
        _make_job("s_only", sub_category="公募权益", sub_category_secondary="量化·中频"),
        _make_job("none", sub_category="信用研究员", sub_category_secondary="固收交易员"),
    ])
    db.commit()
    results = recall_candidates(db, preferred_sub_cats=["量化·中频"])
    ids = {j.job_id for j in results}
    assert ids == {"p_only", "s_only"}


def test_recall_orders_primary_first_then_recency(db):
    """primary 命中的排在前 (即使 secondary 命中更新), 然后按 scraped_at desc。"""
    db.add_all([
        _make_job("p_old", sub_category="量化·中频", scraped_days_ago=5),
        _make_job("s_new", sub_category="公募权益", sub_category_secondary="量化·中频", scraped_days_ago=0),
        _make_job("p_new", sub_category="量化·中频", scraped_days_ago=0),
    ])
    db.commit()
    results = recall_candidates(db, preferred_sub_cats=["量化·中频"])
    order = [j.job_id for j in results]
    # 期望: 2 primary 排前 (按 scraped_at: p_new 在 p_old 前), 然后 secondary
    assert order == ["p_new", "p_old", "s_new"]


def test_recall_empty_pref_returns_all_enriched(db):
    """preferred_sub_cats 为空时, 返回全部 enriched 帖 (按 scraped_at desc)。"""
    db.add_all([
        _make_job("a", sub_category="量化·中频", scraped_days_ago=2),
        _make_job("b", sub_category="公募权益", scraped_days_ago=0),
        _make_job("c", sub_category="卖方研究员·TMT", scraped_days_ago=5),
    ])
    db.commit()
    results = recall_candidates(db, preferred_sub_cats=())
    order = [j.job_id for j in results]
    assert order == ["b", "a", "c"]


def test_recall_respects_limit(db):
    """limit 起作用。"""
    db.add_all([
        _make_job(f"j{i}", sub_category="量化·中频", scraped_days_ago=i)
        for i in range(10)
    ])
    db.commit()
    results = recall_candidates(db, limit=3)
    assert len(results) == 3
    # 应该是最新 3 个
    assert [j.job_id for j in results] == ["j0", "j1", "j2"]
