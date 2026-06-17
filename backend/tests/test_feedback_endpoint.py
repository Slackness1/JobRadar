"""GET /sessions/{id}/feedback — 整体反馈读接口。

轮次8 发现: 该路由后端没注册 → 前端请求落 Next catch-all 返 SPA HTML、
JSON.parse 炸。本测试钉死: 端点存在、返干净 JSON、空态不崩、owner 受保护。
"""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeCopilotSession, ResumeFeedbackRun


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


def _seed(sl, user_key="u_owner", feedback_status="pending"):
    db = sl()
    s = ResumeCopilotSession(user_key=user_key, name="t", feedback_status=feedback_status)
    db.add(s); db.commit(); db.refresh(s)
    sid = s.id
    db.close()
    return sid


def test_feedback_empty_state_returns_clean_json_not_crash():
    """没有 feedback run → 返 200 + 空诊断/改写 + status=session.feedback_status(不再返 HTML)。"""
    client, sl = _client()
    sid = _seed(sl, feedback_status="completed")
    r = client.get(f"/api/resume-copilot/sessions/{sid}/feedback",
                   headers={"X-Resume-User-Key": "u_owner"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"] == sid
    assert body["status"] == "completed"
    assert body["diagnostics"] == []
    assert body["rewrite_examples"] == []


def test_feedback_returns_run_content_when_present():
    client, sl = _client()
    sid = _seed(sl)
    db = sl()
    db.add(ResumeFeedbackRun(
        session_id=sid, status="completed",
        diagnostics_json=json.dumps([{"title": "量化缺失", "description": "结果无数字"}]),
        rewrite_examples_json=json.dumps([
            {"section": "internships.0", "original": "做了运营",
             "improved": "拉新 20%", "rationale": "补量化"}]),
    ))
    db.commit(); db.close()
    r = client.get(f"/api/resume-copilot/sessions/{sid}/feedback",
                   headers={"X-Resume-User-Key": "u_owner"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["diagnostics"][0]["title"] == "量化缺失"
    assert body["rewrite_examples"][0]["improved"] == "拉新 20%"


def test_feedback_owner_guarded():
    client, sl = _client()
    sid = _seed(sl, user_key="u_owner")
    assert client.get(f"/api/resume-copilot/sessions/{sid}/feedback").status_code == 403
    assert client.get(f"/api/resume-copilot/sessions/{sid}/feedback",
                      headers={"X-Resume-User-Key": "u_attacker"}).status_code == 403
