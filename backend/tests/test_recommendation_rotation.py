from app.services.resume_copilot.rotation import next_page


def _pool(n):
    return [{"job_id": f"j{i}"} for i in range(n)]


def test_first_page_excludes_seen():
    page, recycled = next_page(_pool(5), exclude_ids={"j0", "j1"}, page_size=2)
    assert [p["job_id"] for p in page] == ["j2", "j3"]
    assert recycled is False


def test_recycle_when_all_seen():
    page, recycled = next_page(_pool(3), exclude_ids={"j0", "j1", "j2"}, page_size=2)
    assert [p["job_id"] for p in page] == ["j0", "j1"]
    assert recycled is True


def test_empty_pool():
    assert next_page([], exclude_ids=set(), page_size=5) == ([], False)


import json as _json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.models import ResumeCopilotSession, ResumeRecommendationRun
from app.services.resume_copilot import job_state as js


def _client():
    from app.routers import resume_copilot
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sl = sessionmaker(bind=eng); Base.metadata.create_all(bind=eng)
    app = FastAPI(); app.include_router(resume_copilot.router)
    def _ov():
        db = sl()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _ov
    return TestClient(app), sl


def test_next_batch_advances_and_marks_seen(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "RECOMMENDATION_ROTATION_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "ROTATION_PAGE_SIZE", 2, raising=False)
    client, sl = _client()
    db = sl()
    s = ResumeCopilotSession(user_key="u_9", name="t"); db.add(s); db.commit(); db.refresh(s)
    sid = s.id
    pool = [{"job_id": f"j{i}", "company": "C", "job_title": "T", "location": "",
             "detail_url": "", "objective_score": 0, "preference_score": 0,
             "base_job_score": 0, "company_priority_score": 0, "final_score": 50} for i in range(5)]
    db.add(ResumeRecommendationRun(session_id=sid, status="completed",
                                   recommendations_json="[]", pool_json=_json.dumps(pool)))
    db.commit(); db.close()

    r = client.post(f"/api/resume-copilot/sessions/{sid}/recommendations/next-batch", headers={"X-Resume-User-Key": "u_9"})
    assert r.status_code == 200, r.text
    ids1 = [it["job_id"] for it in r.json()["items"]]
    assert ids1 == ["j0", "j1"]
    r2 = client.post(f"/api/resume-copilot/sessions/{sid}/recommendations/next-batch", headers={"X-Resume-User-Key": "u_9"})
    ids2 = [it["job_id"] for it in r2.json()["items"]]
    assert ids2 == ["j2", "j3"]
