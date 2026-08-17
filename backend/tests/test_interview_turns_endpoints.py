import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import InterviewTurn


def _build_test_app():
    from app.routers import interview as interview_router
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(interview_router.router)
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def test_get_turns_returns_all_for_session():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add_all([
        InterviewTurn(session_id="s1", user_key="u1", turn_index=0, question="Q0", user_answer="A0"),
        InterviewTurn(session_id="s1", user_key="u1", turn_index=1, question="Q1", user_answer="A1"),
        InterviewTurn(session_id="other", user_key="u1", turn_index=0, question="Other"),
    ])
    db.commit()
    db.close()

    resp = client.get("/api/interview/sessions/s1/turns", headers={"X-Resume-User-Key": "u1"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    assert rows[0]["question"] == "Q0"
    assert rows[1]["question"] == "Q1"


def test_get_turns_rejects_mismatched_user_key():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s2", user_key="owner-A", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get("/api/interview/sessions/s2/turns", headers={"X-Resume-User-Key": "owner-B"})
    assert resp.status_code == 403


def test_get_turns_returns_empty_list_for_unknown_session():
    client, _ = _build_test_app()
    resp = client.get("/api/interview/sessions/nonexistent/turns", headers={"X-Resume-User-Key": "u1"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_latest_score_returns_most_recent_scored_turn():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    score = json.dumps({"overall": 70, "hits": [], "misses": ["量化"], "bonuses": []})
    db.add_all([
        InterviewTurn(session_id="s3", user_key="u1", turn_index=0, question="Q0", score_json=score),
        InterviewTurn(session_id="s3", user_key="u1", turn_index=1, question="Q1"),  # not scored
    ])
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s3/turns/latest-score",
        headers={"X-Resume-User-Key": "u1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["turn_index"] == 0
    assert "量化" in data["hint"]


def test_latest_score_returns_null_when_no_scored_turn():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s4", user_key="u1", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s4/turns/latest-score",
        headers={"X-Resume-User-Key": "u1"},
    )
    assert resp.status_code == 200
    assert resp.json() is None


def test_latest_score_rejects_mismatched_user_key():
    client, SessionLocal = _build_test_app()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s5", user_key="owner-A", turn_index=0, question="Q0"))
    db.commit()
    db.close()

    resp = client.get(
        "/api/interview/sessions/s5/turns/latest-score",
        headers={"X-Resume-User-Key": "owner-B"},
    )
    assert resp.status_code == 403

