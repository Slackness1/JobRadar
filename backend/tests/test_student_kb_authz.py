"""授权回归: 学生知识库端点必须做用户↔experience 归属校验, 且登录身份不得被 header 冒充。

完整性检查发现 student_kb.py 与 resume_copilot 用同款可枚举 X-Resume-User-Key header
当身份、不验 token。kb 语义是"仅登录学生可用" (_require_authenticated_user_key 挡 guest/
demo/空 key), 但历史实现里那个 key 直接取自 header —— 任一登录用户改 header 成
u_<受害者id> 即可越权读/改他人 experience。本测试钉死: 身份只能由服务端验证的 token
推导, header 不再能冒充登录账号。

owner 校验端点 (经 _load_owned_experience, 本测试覆盖):
  - PATCH  /api/student-kb/experiences/{exp_id}           (改)
  - POST   /api/student-kb/experiences/{exp_id}/confirm   (读 owned 行)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import StudentExperience
from app.services.auth import auth_service


def _client():
    from app.routers import student_kb
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sl = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(student_kb.router)

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


def _seed_experience(sl, user_key: str) -> int:
    db = sl()
    try:
        e = StudentExperience(user_key=user_key, name="proj", summary="做了个项目")
        db.add(e); db.commit(); db.refresh(e)
        eid = e.id
        return eid
    finally:
        db.close()


# ── 越权红线: 登录账号 user_key (u_<id>) 不得被 header 冒充 ────────────────────


def test_student_kb_cannot_spoof_read_owned_via_header():
    """B 带自己合法 token + header 伪造成 A → 读 A 的 owned experience (confirm) 应 403。

    confirm 端点经 _load_owned_experience 做 owner 比对; 冒充时身份取自 B 的 token,
    与 experience owner (u_<A.id>) 不符 → 403。
    """
    client, sl = _client()
    a_key, _a_token = _make_user_with_token(sl, "kb_victim_a@example.com")
    b_key, b_token = _make_user_with_token(sl, "kb_attacker_b@example.com")
    assert a_key != b_key

    a_eid = _seed_experience(sl, a_key)

    spoof_headers = {
        "Authorization": f"Bearer {b_token}",
        "X-Resume-User-Key": a_key,
    }
    r = client.post(f"/api/student-kb/experiences/{a_eid}/confirm", headers=spoof_headers)
    assert r.status_code == 403, f"读 owned 冒充应 403, 实际 {r.status_code}"


def test_student_kb_cannot_spoof_edit_owned_via_header():
    """B 带自己合法 token + header 伪造成 A → 改 A 的 owned experience (PATCH) 应 403。"""
    client, sl = _client()
    a_key, _a_token = _make_user_with_token(sl, "kb_victim_a2@example.com")
    b_key, b_token = _make_user_with_token(sl, "kb_attacker_b2@example.com")
    assert a_key != b_key

    a_eid = _seed_experience(sl, a_key)

    spoof_headers = {
        "Authorization": f"Bearer {b_token}",
        "X-Resume-User-Key": a_key,
    }
    r = client.patch(
        f"/api/student-kb/experiences/{a_eid}",
        json={"summary": "被攻击者篡改"},
        headers=spoof_headers,
    )
    assert r.status_code == 403, f"改 owned 冒充应 403, 实际 {r.status_code}"


def test_student_kb_account_key_header_without_token_is_rejected():
    """无 token 时, 账号形 header key (u_<id>) 不被信任。

    kb 语义"仅登录学生可用": resolve_user_key 对无 token 的 u_<id> 退化成空 key,
    _require_authenticated_user_key 再把空 key 当未认证 → 401 (不是 403, 但同样挡死越权)。
    """
    client, sl = _client()
    a_key, _ = _make_user_with_token(sl, "kb_victim_a3@example.com")
    a_eid = _seed_experience(sl, a_key)

    r = client.post(
        f"/api/student-kb/experiences/{a_eid}/confirm",
        headers={"X-Resume-User-Key": a_key},  # 账号形 key 但无 token 背书
    )
    # 空 key → _require_authenticated_user_key 抛 401; 无论如何绝不放行 (非 2xx)。
    assert r.status_code in (401, 403), f"无 token 的账号形 header 应被挡 (401/403), 实际 {r.status_code}"
    assert r.status_code != 200


def test_student_kb_real_owner_with_token_is_allowed():
    """对照: A 用自己合法 token (header 乱传) → 身份取自 token, 放行 (非 403/401)。"""
    client, sl = _client()
    a_key, a_token = _make_user_with_token(sl, "kb_owner_a@example.com")
    a_eid = _seed_experience(sl, a_key)

    r = client.post(
        f"/api/student-kb/experiences/{a_eid}/confirm",
        headers={"Authorization": f"Bearer {a_token}", "X-Resume-User-Key": "u_999999"},
    )
    assert r.status_code not in (401, 403), f"本人 token 不应被挡, 实际 {r.status_code}"
