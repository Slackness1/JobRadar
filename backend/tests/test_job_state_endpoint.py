from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeCopilotSession
from app.services.resume_copilot import job_state as js


def _client():
    from app.routers import resume_copilot
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sl = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(resume_copilot.router)
    def _ov():
        db = sl()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _ov
    return TestClient(app), sl


def _seed_session(sl, user_key="u_9", demo=False):
    db = sl()
    s = ResumeCopilotSession(user_key="__demo__" if demo else user_key, name="t")
    db.add(s); db.commit(); db.refresh(s)
    sid = s.id
    db.close()
    return sid


def test_set_and_clear_state():
    client, sl = _client()
    sid = _seed_session(sl)
    r = client.post(f"/api/resume-copilot/sessions/{sid}/jobs/j1/state", json={"state": "saved"},
                    headers={"X-Resume-User-Key": "u_9"})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "saved"
    db = sl(); assert js.states_map(db, "u_9")["j1"] == "saved"; db.close()
    r2 = client.post(f"/api/resume-copilot/sessions/{sid}/jobs/j1/state", json={"state": ""},
                     headers={"X-Resume-User-Key": "u_9"})
    assert r2.status_code == 200
    db = sl(); assert js.states_map(db, "u_9")["j1"] == "seen"; db.close()


def test_demo_session_forbidden():
    client, sl = _client()
    sid = _seed_session(sl, demo=True)
    r = client.post(f"/api/resume-copilot/sessions/{sid}/jobs/j1/state", json={"state": "saved"},
                    headers={"X-Resume-User-Key": "__demo__"})
    assert r.status_code == 403


def test_bad_state_422():
    client, sl = _client()
    sid = _seed_session(sl)
    r = client.post(f"/api/resume-copilot/sessions/{sid}/jobs/j1/state", json={"state": "loved"},
                    headers={"X-Resume-User-Key": "u_9"})
    assert r.status_code == 422
