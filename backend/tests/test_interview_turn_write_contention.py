"""A lost analysis write must be retried, and if it stays lost, be visible.

Score / reference answer / voice metrics are produced in parallel and written to
the same interview_turns row from three sessions. Before this guard a lost race
was swallowed as a WARNING and the student saw an analysis that simply never
appeared. These tests pin both halves of the fix: transient conflicts are
retried, and a permanent failure is recorded on the turn.
"""
from __future__ import annotations

import json

from app.models import InterviewTurn
from app.services.interview import orchestrator
from tests._threadsafe_db import make_threadsafe_sessionmaker


def _make_db():
    return make_threadsafe_sessionmaker("jobradar-contention-test-")


def _seed(SessionLocal, *, session_id="s-contention", turn_index=0):
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id=session_id, user_key="u-test", turn_index=turn_index,
        target_job="投研", question="Q0",
    ))
    db.commit()
    db.close()


def _load(SessionLocal, *, session_id="s-contention", turn_index=0) -> InterviewTurn:
    db = SessionLocal()
    try:
        return db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=turn_index
        ).one()
    finally:
        db.close()


def test_transient_write_conflict_is_retried_not_dropped():
    SessionLocal = _make_db()
    _seed(SessionLocal)
    attempts = {"n": 0}

    def flaky(row: InterviewTurn) -> None:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("UPDATE statement expected to update 1 row(s); 0 were matched")
        row.voice_metrics = '{"wpm": 210}'

    ok = orchestrator._persist_turn_field(
        SessionLocal, "s-contention", 0, "voice_metrics", flaky,
    )

    assert ok is True
    assert attempts["n"] == 2
    row = _load(SessionLocal)
    assert row.voice_metrics == '{"wpm": 210}'
    assert not row.analysis_failures, "a retried-and-succeeded write must not be flagged"


def test_permanently_lost_write_is_flagged_on_the_turn():
    SessionLocal = _make_db()
    _seed(SessionLocal)

    def always_fails(row: InterviewTurn) -> None:
        raise RuntimeError("database is locked")

    ok = orchestrator._persist_turn_field(
        SessionLocal, "s-contention", 0, "score", always_fails,
    )

    assert ok is False
    row = _load(SessionLocal)
    assert row.score_json is None
    assert json.loads(row.analysis_failures) == ["score"]


def test_multiple_lost_parts_accumulate_without_duplicates():
    SessionLocal = _make_db()
    _seed(SessionLocal)

    def always_fails(row: InterviewTurn) -> None:
        raise RuntimeError("database is locked")

    for part in ("score", "voice_metrics", "score"):
        orchestrator._persist_turn_field(SessionLocal, "s-contention", 0, part, always_fails)

    assert json.loads(_load(SessionLocal).analysis_failures) == ["score", "voice_metrics"]


def test_compute_failure_is_also_reported_to_the_student():
    """An LLM/analysis exception leaves the same visible marker as a write loss."""
    SessionLocal = _make_db()
    _seed(SessionLocal)

    def boom(*args, **kwargs):
        raise RuntimeError("provider exploded")

    original = orchestrator.compute_voice_metrics
    orchestrator.compute_voice_metrics = boom
    try:
        orchestrator._voice_task(
            SessionLocal, "s-contention", 0,
            {"audio_duration_s": 4.0, "segments": [{"start_s": 0.1, "end_s": 3.5, "text": "答案"}]},
            llm=None,
        )
    finally:
        orchestrator.compute_voice_metrics = original

    assert json.loads(_load(SessionLocal).analysis_failures) == ["voice_metrics"]


def test_turns_endpoint_exposes_the_missing_parts():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.routers import interview as interview_router

    SessionLocal = _make_db()
    _seed(SessionLocal, session_id="s-report")

    db = SessionLocal()
    row = db.query(InterviewTurn).filter_by(session_id="s-report", turn_index=0).one()
    row.user_key = "guest-uuid-abc"
    row.analysis_failures = json.dumps(["score"])
    db.commit()
    db.close()

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(interview_router.router)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    response = client.get(
        "/api/interview/sessions/s-report/turns",
        headers={"X-Resume-User-Key": "guest-uuid-abc"},
    )
    assert response.status_code == 200, response.text
    assert response.json()[0]["analysis_failures"] == ["score"]


def test_healthy_turn_reports_no_missing_parts():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.routers import interview as interview_router

    SessionLocal = _make_db()
    _seed(SessionLocal, session_id="s-ok")
    db = SessionLocal()
    row = db.query(InterviewTurn).filter_by(session_id="s-ok", turn_index=0).one()
    row.user_key = "guest-uuid-ok"
    db.commit()
    db.close()

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(interview_router.router)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    response = client.get(
        "/api/interview/sessions/s-ok/turns",
        headers={"X-Resume-User-Key": "guest-uuid-ok"},
    )
    assert response.status_code == 200
    assert response.json()[0]["analysis_failures"] == []
