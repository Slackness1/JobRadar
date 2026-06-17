"""轮次9 handoff 修复单测 —— 新用户漏斗 + feed 去重 + 规则版"为什么推荐" + 打分 rubric。

覆盖 4 个修:
- FIX-1: chat feed 落库 ResumeRecommendationRun(只对话的新用户也能 GET /recommendations / 深挖);
         不覆盖 generate 的 AI 精排结果(used_ai=1)。
- FIX-2: 同公司同岗位名(两源不同 job_id)feed 去重。
- FIX-4: 快路 feed 卡补规则版"为什么推荐"。
- FIX-3: 打分 completeness rubric 不再把"缺联系方式"当低分信号(联系方式打分前已脱敏)。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, ResumeCopilotSession, ResumeRecommendationRun
from app.schemas_resume_copilot import ResumeRecommendationItem
from app.services.resume_copilot.recommend_search import (
    _dedup_same_posting,
    _rule_why,
    search_candidates,
)
from app.services.resume_copilot.recommend_chat import _persist_feed_to_run
from app.services.resume_copilot.working_query import WorkingQuery


def _sl() -> sessionmaker:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    sl = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return sl


def _add_job(db: Session, *, job_id: str, company: str, title: str, sub_cat: str, days_old: int = 1) -> None:
    db.add(Job(
        job_id=job_id, company=company, job_title=title, job_req="x", job_duty="x",
        sub_category=sub_cat, quality_label="good",
        scraped_at=datetime.utcnow() - timedelta(days=days_old),
    ))


# ── FIX-2: 同岗去重 ──────────────────────────────────────────────────────

def test_dedup_same_posting_drops_duplicate_company_title():
    items = [
        ResumeRecommendationItem(job_id="a1", company="浙商证券", job_title="系统运营专员",
                                 location="", objective_score=0, preference_score=0,
                                 base_job_score=0, final_score=80),
        ResumeRecommendationItem(job_id="a2", company="浙商证券", job_title="系统运营专员",
                                 location="", objective_score=0, preference_score=0,
                                 base_job_score=0, final_score=70),
        ResumeRecommendationItem(job_id="b1", company="中金公司", job_title="研究员",
                                 location="", objective_score=0, preference_score=0,
                                 base_job_score=0, final_score=60),
    ]
    out = _dedup_same_posting(items)
    jids = [it.job_id for it in out]
    assert jids == ["a1", "b1"]  # 同公司同岗位名只保第一条(高分), 不同岗位保留


def test_dedup_same_posting_keeps_distinct_titles_same_company():
    items = [
        ResumeRecommendationItem(job_id="x1", company="中金", job_title="债券研究员",
                                 location="", objective_score=0, preference_score=0,
                                 base_job_score=0, final_score=80),
        ResumeRecommendationItem(job_id="x2", company="中金", job_title="股票研究员",
                                 location="", objective_score=0, preference_score=0,
                                 base_job_score=0, final_score=70),
    ]
    out = _dedup_same_posting(items)
    assert {it.job_id for it in out} == {"x1", "x2"}  # 同公司不同岗位名 → 都留


def test_search_candidates_dedup_same_posting_end_to_end():
    sl = _sl(); db = sl()
    try:
        sub = "公募权益研究员"
        _add_job(db, job_id="dup-1", company="某基金", title="研究员", sub_cat=sub)
        _add_job(db, job_id="dup-2", company="某基金", title="研究员", sub_cat=sub)
        db.commit()
        items = search_candidates(db, WorkingQuery(seed_sub_cats=[sub]), limit=10)
        same = [it for it in items if it.company == "某基金" and it.job_title == "研究员"]
        assert len(same) == 1  # 两个不同 job_id 的同岗只出一次
    finally:
        db.close()


# ── FIX-4: 规则版"为什么推荐" ────────────────────────────────────────────

class _FakeItem:
    def __init__(self, **kw):
        self.tier_label = kw.get("tier_label", "")
        self.matched_track_label = kw.get("matched_track_label", "")
        self.track_match_kind = kw.get("track_match_kind", "")
        self.why_recommended = kw.get("why_recommended", [])
        self.strengths = kw.get("strengths", [])
        self.base_match_score = 0


def test_rule_why_hit_track():
    why = _rule_why(_FakeItem(matched_track_label="公募权益研究员",
                              track_match_kind="hit", tier_label="强匹配"))
    assert any("公募权益研究员" in w for w in why)
    assert any("强匹配" in w for w in why)


def test_rule_why_transferable():
    why = _rule_why(_FakeItem(matched_track_label="量化研究员·中频",
                              track_match_kind="transferable", tier_label="可迁移"))
    assert any("可迁移" in w for w in why)


def test_rule_why_empty_when_no_signal():
    assert _rule_why(_FakeItem()) == []


def test_search_candidates_feed_has_why():
    sl = _sl(); db = sl()
    try:
        sub = "公募权益研究员"
        _add_job(db, job_id="w1", company="华夏基金", title="权益研究员", sub_cat=sub)
        db.commit()
        items = search_candidates(db, WorkingQuery(seed_sub_cats=[sub]), limit=5)
        assert items, "feed 不应为空"
        # 快路无 LLM, 但卡片至少要有规则版"为什么推荐"(不能全空)
        assert any(getattr(it, "why_recommended", None) for it in items)
        assert all(getattr(it, "used_ai", True) is False for it in items)
    finally:
        db.close()


# ── FIX-1: chat feed 落库 ────────────────────────────────────────────────

def _mk_session(db: Session, user_key="u_x") -> ResumeCopilotSession:
    s = ResumeCopilotSession(user_key=user_key, name="t")
    db.add(s); db.commit(); db.refresh(s)
    return s


def _feed(n=2):
    return [
        ResumeRecommendationItem(job_id=f"j{i}", company=f"c{i}", job_title="研究员",
                                 location="", objective_score=0, preference_score=0,
                                 base_job_score=0, final_score=80 - i)
        for i in range(n)
    ]


def test_persist_feed_creates_run_for_chat_only_user():
    sl = _sl(); db = sl()
    try:
        s = _mk_session(db)
        # 修前: chat-only 会话没有 run → GET /recommendations 404
        assert db.query(ResumeRecommendationRun).filter_by(session_id=s.id).first() is None
        _persist_feed_to_run(db, s, _feed(3))
        db.commit()
        run = db.query(ResumeRecommendationRun).filter_by(session_id=s.id).first()
        assert run is not None
        assert run.status == "completed"
        assert int(run.used_ai or 0) == 0
        import json
        assert len(json.loads(run.recommendations_json)) == 3
    finally:
        db.close()


def test_persist_feed_does_not_clobber_ai_generate_run():
    sl = _sl(); db = sl()
    try:
        s = _mk_session(db)
        # 模拟 generate 已跑出 AI 精排结果(used_ai=1, completed, 带叙事)
        run = ResumeRecommendationRun(
            session_id=s.id, status="completed", used_ai=1,
            recommendations_json='[{"ai":"narrated"}]',
        )
        db.add(run); db.commit()
        _persist_feed_to_run(db, s, _feed(2))  # chat 之后不该覆盖
        db.commit()
        run2 = db.query(ResumeRecommendationRun).filter_by(session_id=s.id).first()
        assert int(run2.used_ai or 0) == 1
        assert run2.recommendations_json == '[{"ai":"narrated"}]'  # 原样保留
    finally:
        db.close()


def test_persist_feed_overwrites_prior_chat_run():
    sl = _sl(); db = sl()
    try:
        s = _mk_session(db)
        _persist_feed_to_run(db, s, _feed(2)); db.commit()
        _persist_feed_to_run(db, s, _feed(5)); db.commit()
        import json
        run = db.query(ResumeRecommendationRun).filter_by(session_id=s.id).first()
        assert len(json.loads(run.recommendations_json)) == 5  # 规则 run 之间最新覆盖
    finally:
        db.close()


def test_persist_feed_empty_is_noop():
    sl = _sl(); db = sl()
    try:
        s = _mk_session(db)
        _persist_feed_to_run(db, s, [])
        db.commit()
        assert db.query(ResumeRecommendationRun).filter_by(session_id=s.id).first() is None
    finally:
        db.close()


# ── FIX-3: 打分 rubric 不再误报缺联系方式 ────────────────────────────────

def test_completeness_rubric_drops_contact_signal():
    from app.services.resume_copilot.scoring_rubric import DIMENSIONS
    comp = next(d for d in DIMENSIONS if d["key"] == "completeness")
    # 联系方式打分前已被 redact_profile_for_llm 抹掉 → 不得作为低分信号(恒误报)
    assert "联系方式" not in comp["low_signal"]
    assert "联系方式" not in comp["high_signal"]
