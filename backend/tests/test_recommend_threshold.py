"""Tests for the BE-3 (D-6) top-10 + 50-floor + underfilled hint behaviour.

Covers:

- all candidates below 50 → empty result (underfilled);
- 11 candidates clearing 50 → exactly 10 returned (top-N cap);
- mixed: a few above 50, rest below → only the above-50 ones returned, count
  reflects 'underfilled' from caller's perspective.
- caller-side debounce helper (should_debounce_recommend) signals correctly.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job, ResumeCopilotSession
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.recommendation import (
    RECOMMEND_MIN_SCORE,
    RECOMMEND_TOP_N,
    _apply_top_n_with_threshold,
    recommend_jobs_for_profile,
    should_debounce_recommend,
)


def _build_session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sl = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return sl


def _empty_profile() -> ResumeProfilePayload:
    return ResumeProfilePayload.model_validate(
        {
            "basic_info": {"name": "X"},
            "education": [],
            "internships": [],
            "projects": [],
            "skills": ResumeSkillsPayload(technical=[], tools=[], languages=[]),
            "languages": [],
            "awards": [],
            "candidate_summary": "",
            "inferred_roles": [],
            "inferred_tracks": [],
        }
    )


def _skipped_prefs() -> ResumePreferencePayload:
    return ResumePreferencePayload.model_validate(
        {
            "preferred_tracks": [],
            "preferred_locations": [],
            "preferred_roles": [],
            "preferred_company_types": [],
            "accept_relocation": False,
            "accept_internship": False,
            "campus_only": False,
            "social_ok": False,
            "preference_notes": "",
            "all_skipped": True,
        }
    )


def _add_low_score_job(db: Session, job_id: str) -> None:
    """Low signal — no skill match, no preference boost → final_score = 0."""
    db.add(
        Job(
            job_id=job_id,
            company=f"Co-{job_id}",
            job_title="Generalist",
            job_req="generic",
            job_duty="generic",
        )
    )
    db.commit()


def test_all_low_score_returns_empty_and_caller_can_render_underfilled():
    """20 candidates all scoring 0 (< 50 floor) → empty list. Caller detects
    underfilled by ``len(items) < RECOMMEND_TOP_N`` and renders
    '暂无更多优质推荐'."""
    sl = _build_session_factory()
    db = sl()
    try:
        for i in range(20):
            _add_low_score_job(db, f"job-low-{i}")
        items, _used, _err = recommend_jobs_for_profile(
            db,
            _empty_profile(),
            _skipped_prefs(),
            ai_top_n=0,
        )
        assert items == []
        assert len(items) < RECOMMEND_TOP_N  # underfilled signal
    finally:
        db.close()


def test_eleven_above_floor_returns_exactly_ten():
    """Hand-craft 11 ResumeRecommendationItem all at score 80 and verify the
    threshold helper caps to 10. We exercise the helper directly because the
    rule scoring fixtures it takes is hairy to push above 50 without contrived
    skills/preference combos — and the helper *is* the cap logic."""
    from app.schemas_resume_copilot import ResumeRecommendationItem

    items = [
        ResumeRecommendationItem(
            job_id=f"job-{i}",
            company=f"Co-{i}",
            job_title="Role",
            location="Shanghai",
            objective_score=0,
            preference_score=0,
            base_job_score=0,
            final_score=80,
        )
        for i in range(11)
    ]
    capped = _apply_top_n_with_threshold(items, limit=None)
    assert len(capped) == RECOMMEND_TOP_N == 10
    # Order preserved (sort is the caller's responsibility)
    assert [i.job_id for i in capped] == [f"job-{i}" for i in range(10)]


def test_mixed_only_above_floor_passes_threshold():
    from app.schemas_resume_copilot import ResumeRecommendationItem

    items = [
        ResumeRecommendationItem(
            job_id="job-pass-1", company="C", job_title="X", location="S",
            objective_score=0, preference_score=0, base_job_score=0, final_score=80,
        ),
        ResumeRecommendationItem(
            job_id="job-pass-2", company="C", job_title="X", location="S",
            objective_score=0, preference_score=0, base_job_score=0, final_score=50,
        ),
        ResumeRecommendationItem(
            job_id="job-fail-49", company="C", job_title="X", location="S",
            objective_score=0, preference_score=0, base_job_score=0, final_score=49,
        ),
        ResumeRecommendationItem(
            job_id="job-fail-0", company="C", job_title="X", location="S",
            objective_score=0, preference_score=0, base_job_score=0, final_score=0,
        ),
    ]
    capped = _apply_top_n_with_threshold(items, limit=None)
    assert [i.job_id for i in capped] == ["job-pass-1", "job-pass-2"]
    assert len(capped) < RECOMMEND_TOP_N  # underfilled


def test_min_score_constant_matches_design_doc():
    """Tripwire: D-6 fixed the floor at 50 / top-N at 10."""
    assert RECOMMEND_MIN_SCORE == 50
    assert RECOMMEND_TOP_N == 10


def test_limit_argument_caps_top_n_but_cannot_exceed_default():
    """limit < 10 shrinks; limit > 10 has no effect (10 is the product ceiling)."""
    from app.schemas_resume_copilot import ResumeRecommendationItem

    items = [
        ResumeRecommendationItem(
            job_id=f"job-{i}", company="C", job_title="X", location="S",
            objective_score=0, preference_score=0, base_job_score=0, final_score=80,
        )
        for i in range(15)
    ]
    assert len(_apply_top_n_with_threshold(items, limit=5)) == 5
    assert len(_apply_top_n_with_threshold(items, limit=10)) == 10
    assert len(_apply_top_n_with_threshold(items, limit=999)) == 10
    assert _apply_top_n_with_threshold(items, limit=0) == []


def test_should_debounce_recommend_signals_within_window():
    sl = _build_session_factory()
    db = sl()
    try:
        session = ResumeCopilotSession(file_name="r.pdf", user_key="u")
        db.add(session)
        db.commit()
        db.refresh(session)
        # No trigger yet → allow
        assert should_debounce_recommend(session) is False

        # Trigger just now → debounce
        session.last_recommend_trigger_at = datetime.utcnow()
        db.commit()
        assert should_debounce_recommend(session, debounce_seconds=1.5) is True

        # Trigger 3s ago → allow
        session.last_recommend_trigger_at = datetime.utcnow() - timedelta(seconds=3)
        db.commit()
        assert should_debounce_recommend(session, debounce_seconds=1.5) is False
    finally:
        db.close()


def test_should_debounce_recommend_handles_none_session():
    assert should_debounce_recommend(None) is False
