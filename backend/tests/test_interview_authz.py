"""授权回归: 面试报告 / 会话端点必须做用户↔资源归属校验, 且登录身份不得被 header 冒充。

完整性检查发现 interview.py 与 resume_copilot 用同款可枚举 X-Resume-User-Key header
当身份、不验 token —— 任一登录用户改 header 成 u_<受害者id> 即可越权读他人面试报告 /
会话。本测试钉死: 身份只能由服务端验证的 bearer token 推导, header 不再能冒充登录账号。

owner 校验端点 (本测试覆盖):
  - GET /api/interview/reports/{report_id}        (get_report, row.user_key 比对)
  - GET /api/interview/sessions/{session_id}/turns (_assert_session_owner_or_403)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import InterviewReport, InterviewTurn
from app.services.auth import auth_service


def _client():
    from app.routers import interview
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sl = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(interview.router)

    def _ov():
        db = sl()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _ov
    return TestClient(app, raise_server_exceptions=False), sl


def _make_user_with_token(sl, email: str):
    """建一个真实账号 + 一条合法 session token, 返回 (user_key, token)。"""
    db = sl()
    try:
        user = auth_service.create_user(db, email=email, password="pw123456", invite_code_id=None)
        auth_service.mark_email_verified(db, user)
        sess = auth_service.create_session(db, user)
        db.commit()
        return auth_service.user_key_for(user), sess.token
    finally:
        db.close()


def _seed_report(sl, user_key: str) -> int:
    db = sl()
    try:
        r = InterviewReport(user_key=user_key, target_job="后端开发")
        db.add(r); db.commit(); db.refresh(r)
        rid = r.id
        return rid
    finally:
        db.close()


def _seed_session_turn(sl, user_key: str, session_id: str = "sess-A") -> str:
    db = sl()
    try:
        t = InterviewTurn(session_id=session_id, user_key=user_key, turn_index=0, question="q0")
        db.add(t); db.commit()
        return session_id
    finally:
        db.close()


# ── 越权红线: 登录账号 user_key (u_<id>) 不得被 header 冒充 ────────────────────


def test_interview_cannot_spoof_report_via_header():
    """B 带自己合法 token, 但把 X-Resume-User-Key 伪造成 A 的 u_<id> → 读 A 的报告应 403。

    修复前: get_report 只比 header (== B 伪造的 a_key), 会被当成 A 放行 (漏洞)。
    修复后: 身份取自 B 的 token (= u_<B.id>), 与报告 owner (u_<A.id>) 不符 → 403。
    """
    client, sl = _client()
    a_key, _a_token = _make_user_with_token(sl, "victim_a@example.com")
    b_key, b_token = _make_user_with_token(sl, "attacker_b@example.com")
    assert a_key != b_key

    a_rid = _seed_report(sl, a_key)

    spoof_headers = {
        "Authorization": f"Bearer {b_token}",
        "X-Resume-User-Key": a_key,
    }
    r = client.get(f"/api/interview/reports/{a_rid}", headers=spoof_headers)
    assert r.status_code == 403, f"读报告冒充应 403, 实际 {r.status_code}"


def test_interview_cannot_spoof_session_turns_via_header():
    """B 带合法 token + header 伪造成 A → 读 A 的会话 turns 应 403。"""
    client, sl = _client()
    a_key, _a_token = _make_user_with_token(sl, "victim_a2@example.com")
    b_key, b_token = _make_user_with_token(sl, "attacker_b2@example.com")
    assert a_key != b_key

    sid = _seed_session_turn(sl, a_key, session_id="sess-A2")

    spoof_headers = {
        "Authorization": f"Bearer {b_token}",
        "X-Resume-User-Key": a_key,
    }
    r = client.get(f"/api/interview/sessions/{sid}/turns", headers=spoof_headers)
    assert r.status_code == 403, f"读会话 turns 冒充应 403, 实际 {r.status_code}"


def test_interview_account_key_header_without_token_is_rejected():
    """无 token 时, 账号形 header key (u_<id>) 不被信任 → 越权读 A 的报告应 403。

    最直接的越权口子: 攻击者连 token 都不带, 纯靠改 header 成 u_<受害者id>。"""
    client, sl = _client()
    a_key, _ = _make_user_with_token(sl, "victim_a3@example.com")
    a_rid = _seed_report(sl, a_key)

    r = client.get(
        f"/api/interview/reports/{a_rid}",
        headers={"X-Resume-User-Key": a_key},  # 账号形 key 但无 token 背书
    )
    assert r.status_code == 403, f"无 token 的账号形 header 应 403, 实际 {r.status_code}"


def test_interview_real_owner_with_token_is_allowed():
    """对照: A 用自己合法 token (header 乱传) → 身份取自 token, 放行 (非 403)。"""
    client, sl = _client()
    a_key, a_token = _make_user_with_token(sl, "owner_a@example.com")
    a_rid = _seed_report(sl, a_key)

    r = client.get(
        f"/api/interview/reports/{a_rid}",
        headers={"Authorization": f"Bearer {a_token}", "X-Resume-User-Key": "u_999999"},
    )
    assert r.status_code != 403, f"本人 token 不应 403, 实际 {r.status_code}"
