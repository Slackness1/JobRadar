from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Job
from app.services.resume_copilot import job_state as js


def _client():
    from app.routers import resume_copilot
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sl = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI(); app.include_router(resume_copilot.router)
    def _ov():
        db = sl()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _ov
    return TestClient(app), sl


def test_my_jobs_grouped():
    client, sl = _client()
    db = sl()
    db.add(Job(job_id="j1", company="中金", job_title="量化研究员", location="上海", detail_url="http://x/1"))
    db.add(Job(job_id="j2", company="幻方", job_title="策略实习", location="杭州", detail_url="http://x/2"))
    db.commit()
    js.set_explicit_state(db, "u_9", "j1", js.STATE_SAVED)
    js.set_explicit_state(db, "u_9", "j2", js.STATE_APPLIED)
    js.mark_seen(db, "u_9", ["j3"])  # 纯 seen 不进任何组
    db.close()

    r = client.get("/api/resume-copilot/my-jobs", headers={"X-Resume-User-Key": "u_9"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"] == {"saved": 1, "applied": 1, "dismissed": 0}
    assert body["saved"][0]["company"] == "中金"
    assert body["applied"][0]["job_id"] == "j2"
