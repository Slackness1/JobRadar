"""授权回归: NL 推荐 / 确认页 端点必须做用户↔session 归属校验。

轮次8 安全发现: recommend-chat / working-query(GET+update) / recommend-deepen /
sub-cat-suggestions 这几个 2026-06-04 新加的端点漏了 owner-check —— 不带 key 或拿
别人 key 都能读写他人 session。本测试钉死: 缺/错 key → 403, 本人 key → 放行。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeCopilotSession


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
    # raise_server_exceptions=False: owner-key 放行后会走到真实 LLM(测试环境无 key 会 500),
    # 我们只关心"是否过了 403 鉴权关", 让下游异常成 500 响应而非抛出。
    return TestClient(app, raise_server_exceptions=False), sl


def _seed(sl, user_key="u_owner"):
    db = sl()
    s = ResumeCopilotSession(user_key=user_key, name="t")
    db.add(s); db.commit(); db.refresh(s)
    sid = s.id
    db.close()
    return sid


# 每个端点: (method, path 后缀, body)
_ENDPOINTS = [
    ("post", "/recommend-chat", {"message": "推荐投研"}),
    ("get", "/working-query", None),
    ("post", "/working-query/update", {"sort": "fresh"}),
    ("post", "/recommend-deepen", {"job_ids": ["j1"]}),
    ("post", "/sub-cat-suggestions", {"tracks": ["投研"]}),
]


def _call(client, method, url, body, headers):
    if method == "get":
        return client.get(url, headers=headers)
    return client.post(url, json=body, headers=headers)


def test_recommend_endpoints_reject_missing_key():
    client, sl = _client()
    sid = _seed(sl)
    for method, suffix, body in _ENDPOINTS:
        r = _call(client, method, f"/api/resume-copilot/sessions/{sid}{suffix}", body, {})
        assert r.status_code == 403, f"{suffix} 无 key 应 403, 实际 {r.status_code}"


def test_recommend_endpoints_reject_wrong_user_key():
    client, sl = _client()
    sid = _seed(sl, user_key="u_owner")
    for method, suffix, body in _ENDPOINTS:
        r = _call(client, method, f"/api/resume-copilot/sessions/{sid}{suffix}", body,
                  {"X-Resume-User-Key": "u_attacker"})
        assert r.status_code == 403, f"{suffix} 错 key 应 403, 实际 {r.status_code}"


def test_recommend_endpoints_allow_owner_key():
    """本人 key → 不再 403(放行到业务逻辑; 业务层可能因无数据另返其它码,但绝非 403)。"""
    client, sl = _client()
    sid = _seed(sl, user_key="u_owner")
    for method, suffix, body in _ENDPOINTS:
        r = _call(client, method, f"/api/resume-copilot/sessions/{sid}{suffix}", body,
                  {"X-Resume-User-Key": "u_owner"})
        assert r.status_code != 403, f"{suffix} 本人 key 不应 403, 实际 {r.status_code}"
