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
from app.services.auth import auth_service


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


# ── 越权红线: 登录账号 user_key (u_<id>) 不得被 header 冒充 ────────────────────
#
# 修复前: _assert_session_owner 直接信任前端传的 X-Resume-User-Key, 而该 key =
# u_<自增id> 可枚举。任一登录用户 (拿自己的合法 token) 把 header 改成 u_<受害者id>
# 即可越权读改受害者全部会话 (后端从不验同时携带的 bearer token)。
# 修复后: 身份只能由服务端验证的 token 推导, header 不再能冒充登录账号身份。


def _make_user_with_token(sl, email: str):
    """建一个真实账号 + 一条合法 session token, 返回 (user_key, token)。

    照 auth_service 真实建账号/发 token 的路子来 (不是手搓字符串)。"""
    db = sl()
    try:
        user = auth_service.create_user(db, email=email, password="pw123456", invite_code_id=None)
        auth_service.mark_email_verified(db, user)
        sess = auth_service.create_session(db, user)
        db.commit()
        return auth_service.user_key_for(user), sess.token
    finally:
        db.close()


def test_cannot_spoof_other_user_via_header():
    """B 拿自己的合法 token + header 伪造成 A 的 u_<id> → 必须 403 (读 + 写都钉死)。

    修复前: 后端只比 header, B 的请求会被当成 A 放行 (200 = 漏洞)。
    修复后: 身份取自 B 的 token (= u_<B.id>), 与 session owner (u_<A.id>) 不符 → 403。
    """
    client, sl = _client()

    # 两个真实登录用户 + 各自 token
    a_key, _a_token = _make_user_with_token(sl, "victim_a@example.com")
    b_key, b_token = _make_user_with_token(sl, "attacker_b@example.com")
    assert a_key != b_key  # 各自 u_<id> 不同

    # A 名下一条 session
    a_sid = _seed(sl, user_key=a_key)

    # 攻击者 B: 带自己合法 token, 但把 X-Resume-User-Key 伪造成 A 的 u_<id>
    spoof_headers = {
        "Authorization": f"Bearer {b_token}",
        "X-Resume-User-Key": a_key,
    }

    # 读端点: GET /working-query
    r_read = client.get(
        f"/api/resume-copilot/sessions/{a_sid}/working-query", headers=spoof_headers
    )
    assert r_read.status_code == 403, f"读冒充应 403, 实际 {r_read.status_code}"

    # 写端点: POST /working-query/update
    r_write = client.post(
        f"/api/resume-copilot/sessions/{a_sid}/working-query/update",
        json={"sort": "fresh"},
        headers=spoof_headers,
    )
    assert r_write.status_code == 403, f"写冒充应 403, 实际 {r_write.status_code}"


def test_account_key_header_without_token_is_rejected():
    """无 token 时, 账号形 header key (u_<id>) 不被信任 → 越权读 A 的 session 应 403。

    这堵的是最直接的越权口子: 攻击者连 token 都不带, 纯靠改 header 成 u_<受害者id>。"""
    client, sl = _client()
    a_key, _ = _make_user_with_token(sl, "victim2@example.com")
    a_sid = _seed(sl, user_key=a_key)

    r = client.get(
        f"/api/resume-copilot/sessions/{a_sid}/working-query",
        headers={"X-Resume-User-Key": a_key},  # 账号形 key 但无 token 背书
    )
    assert r.status_code == 403, f"无 token 的账号形 header 应 403, 实际 {r.status_code}"


def test_real_owner_with_token_is_allowed():
    """对照: A 用自己合法 token (header 可不传或乱传) → 身份取自 token, 放行 (非 403)。"""
    client, sl = _client()
    a_key, a_token = _make_user_with_token(sl, "owner3@example.com")
    a_sid = _seed(sl, user_key=a_key)

    # 故意把 header 设成别人的值, 验证 token 才是权威源
    r = client.get(
        f"/api/resume-copilot/sessions/{a_sid}/working-query",
        headers={"Authorization": f"Bearer {a_token}", "X-Resume-User-Key": "u_999999"},
    )
    assert r.status_code != 403, f"本人 token 不应 403, 实际 {r.status_code}"
