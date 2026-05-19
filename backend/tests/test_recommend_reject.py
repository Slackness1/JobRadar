"""Tests for POST /sessions/{id}/recommendations/{job_id}/reject (BE-3, D-2/D-3).

Covers:

- happy path: reject writes account_memory.preference, dedupes
  ResumeCopilotSession.rejected_job_ids_json, and the next call to
  recommend_jobs_for_profile excludes that job;
- dedupe: second POST with the same job_id does not extend
  rejected_job_ids and refreshes (not duplicates) the memory row;
- demo session is read-only (403);
- cross-session id guessing returns 404 (job_id not in *this* session's
  recommendations).
"""
from __future__ import annotations

import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import (
    AccountMemory,
    Job,
    ResumeCopilotSession,
    ResumeRecommendationRun,
)


# Single patch decorator reused across tests — apps in __main__ run with the
# flag default-True, but we guarantee it here so module-level constant patches
# elsewhere in the test suite don't bleed in.
_MEMORY_ON = patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)


def _build_client() -> tuple[TestClient, sessionmaker]:
    from app.routers import resume_copilot

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sl = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(resume_copilot.router)

    def _override_db():
        db = sl()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    client.headers.update({"X-Resume-User-Key": "user-abc"})
    return client, sl


def _seed_session_with_recommendations(
    sl: sessionmaker,
    *,
    user_key: str = "user-abc",
    job_ids: tuple[str, ...] = ("job-1", "job-2", "job-3"),
) -> int:
    db = sl()
    try:
        session = ResumeCopilotSession(
            file_name="r.pdf",
            user_key=user_key,
            status="completed",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        for jid in job_ids:
            db.add(Job(job_id=jid, company=f"Company-{jid}", job_title=f"Role-{jid}"))
        recs = [
            {
                "job_id": jid,
                "company": f"Company-{jid}",
                "job_title": f"Role-{jid}",
                "location": "Shanghai",
                "objective_score": 60,
                "preference_score": 0,
                "base_job_score": 0,
                "final_score": 60,
            }
            for jid in job_ids
        ]
        run = ResumeRecommendationRun(
            session_id=session.id,
            status="completed",
            recommendations_json=json.dumps(recs),
        )
        db.add(run)
        db.commit()
        return int(session.id)
    finally:
        db.close()


def test_reject_writes_preference_memory_and_filters_subsequent_recommendations():
    with _MEMORY_ON:
        client, sl = _build_client()
        session_id = _seed_session_with_recommendations(sl)

        resp = client.post(
            f"/api/resume-copilot/sessions/{session_id}/recommendations/job-2/reject",
            json={"reason": "wrong_track", "note": "其实想做投研"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        assert body["rejected_count"] == 1
        assert body["memory_entry_id"] is not None

        # account_memory.preference written with Chinese reason label
        db = sl()
        try:
            row = (
                db.query(AccountMemory)
                .filter(AccountMemory.user_key == "user-abc")
                .filter(AccountMemory.category == "preference")
                .first()
            )
            assert row is not None
            assert "Company-job-2" in str(row.summary)
            assert "赛道不对" in str(row.summary)
            raw_payload = json.loads(str(row.raw_excerpt or "{}"))
            assert raw_payload["job_id"] == "job-2"
            assert raw_payload["reason"] == "wrong_track"
            assert raw_payload["reason_label"] == "赛道不对"
            assert raw_payload["note"] == "其实想做投研"
            assert raw_payload["company"] == "Company-job-2"
            assert raw_payload["rejected_at"]  # iso string
            # session.rejected_job_ids_json updated
            session = (
                db.query(ResumeCopilotSession)
                .filter(ResumeCopilotSession.id == session_id)
                .first()
            )
            assert session is not None
            assert json.loads(str(session.rejected_job_ids_json or "[]")) == ["job-2"]
        finally:
            db.close()


def test_second_reject_same_job_id_dedupes_session_list_and_refreshes_memory():
    with _MEMORY_ON:
        client, sl = _build_client()
        session_id = _seed_session_with_recommendations(sl)

        # First reject
        resp1 = client.post(
            f"/api/resume-copilot/sessions/{session_id}/recommendations/job-2/reject",
            json={"reason": "company_disliked"},
        )
        assert resp1.status_code == 200, resp1.text
        first_entry_id = resp1.json()["memory_entry_id"]

        # Second reject — same job, same reason → same summary → dispatcher
        # refreshes the existing row instead of inserting a duplicate.
        resp2 = client.post(
            f"/api/resume-copilot/sessions/{session_id}/recommendations/job-2/reject",
            json={"reason": "company_disliked"},
        )
        assert resp2.status_code == 200, resp2.text
        body = resp2.json()
        assert body["rejected_count"] == 1, "second press must not duplicate rejected_job_ids"
        assert body["memory_entry_id"] == first_entry_id

        db = sl()
        try:
            preference_rows = (
                db.query(AccountMemory)
                .filter(AccountMemory.user_key == "user-abc")
                .filter(AccountMemory.category == "preference")
                .all()
            )
            assert len(preference_rows) == 1
            session = db.query(ResumeCopilotSession).get(session_id)
            assert json.loads(str(session.rejected_job_ids_json or "[]")) == ["job-2"]
        finally:
            db.close()


def test_recommend_jobs_for_profile_excludes_rejected_job_ids():
    """End-to-end: after the reject endpoint, recommend_jobs_for_profile
    invoked with the session's rejected list drops that job."""
    from app.schemas_resume_copilot import ResumePreferencePayload, ResumeProfilePayload, ResumeSkillsPayload
    from app.services.resume_copilot.recommendation import recommend_jobs_for_profile

    with _MEMORY_ON:
        client, sl = _build_client()
        session_id = _seed_session_with_recommendations(sl)

        resp = client.post(
            f"/api/resume-copilot/sessions/{session_id}/recommendations/job-2/reject",
            json={"reason": "timing"},
        )
        assert resp.status_code == 200, resp.text

        # Now reproduce the workflow path: read rejected list, pass to recommend.
        db = sl()
        try:
            session = db.query(ResumeCopilotSession).get(session_id)
            rejected = json.loads(str(session.rejected_job_ids_json or "[]"))
            assert rejected == ["job-2"]

            profile = ResumeProfilePayload.model_validate(
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
            preferences = ResumePreferencePayload.model_validate(
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
            items, _used, _err = recommend_jobs_for_profile(
                db,
                profile,
                preferences,
                ai_top_n=0,
                rejected_job_ids=rejected,
                min_score=0,
                top_n=999,
            )
            returned_ids = {item.job_id for item in items}
            assert "job-2" not in returned_ids
            assert "job-1" in returned_ids
            assert "job-3" in returned_ids
        finally:
            db.close()


def test_reject_on_demo_session_returns_403():
    with _MEMORY_ON:
        client, sl = _build_client()
        # Demo session: user_key='__demo__' — owner check allows public read
        # but write must be blocked.
        db = sl()
        try:
            session = ResumeCopilotSession(
                file_name="demo.pdf",
                user_key="__demo__",
                status="completed",
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            db.add(
                ResumeRecommendationRun(
                    session_id=session.id,
                    status="completed",
                    recommendations_json=json.dumps(
                        [{"job_id": "demo-1", "company": "Demo", "job_title": "X",
                          "location": "Shanghai", "objective_score": 0,
                          "preference_score": 0, "base_job_score": 0, "final_score": 0}]
                    ),
                )
            )
            db.commit()
            sid = int(session.id)
        finally:
            db.close()

        # Demo public read does not require X-Resume-User-Key match — but
        # _assert_not_demo blocks the write regardless.
        resp = client.post(
            f"/api/resume-copilot/sessions/{sid}/recommendations/demo-1/reject",
            json={"reason": "other"},
            headers={"X-Resume-User-Key": ""},
        )
        assert resp.status_code == 403, resp.text


def test_reject_across_session_returns_404_when_job_not_in_recommendations():
    """Caller is authenticated as the session owner but ✗'s a job_id that
    never appeared in this session's recommendation_run — possible if they
    guess an id. Returns 404 instead of silently writing memory."""
    with _MEMORY_ON:
        client, sl = _build_client()
        session_id = _seed_session_with_recommendations(
            sl,
            job_ids=("job-1", "job-2"),
        )

        resp = client.post(
            f"/api/resume-copilot/sessions/{session_id}/recommendations/job-not-in-list/reject",
            json={"reason": "wrong_track"},
        )
        assert resp.status_code == 404, resp.text
        assert "JOB_NOT_IN_RECOMMENDATIONS" in resp.text

        # session.rejected_job_ids_json untouched
        db = sl()
        try:
            session = db.query(ResumeCopilotSession).get(session_id)
            assert json.loads(str(session.rejected_job_ids_json or "[]")) == []
            assert (
                db.query(AccountMemory)
                .filter(AccountMemory.user_key == "user-abc")
                .count()
                == 0
            )
        finally:
            db.close()


def test_reject_with_unknown_reason_returns_422():
    with _MEMORY_ON:
        client, sl = _build_client()
        session_id = _seed_session_with_recommendations(sl)
        resp = client.post(
            f"/api/resume-copilot/sessions/{session_id}/recommendations/job-1/reject",
            json={"reason": "not-in-the-five"},
        )
        assert resp.status_code == 422
        assert "INVALID_REJECT_REASON" in resp.text


def test_reject_by_wrong_user_returns_403():
    """Different X-Resume-User-Key from the session owner → 403."""
    with _MEMORY_ON:
        client, sl = _build_client()
        session_id = _seed_session_with_recommendations(sl, user_key="real-owner")
        resp = client.post(
            f"/api/resume-copilot/sessions/{session_id}/recommendations/job-1/reject",
            json={"reason": "wrong_track"},
            headers={"X-Resume-User-Key": "intruder"},
        )
        assert resp.status_code == 403
