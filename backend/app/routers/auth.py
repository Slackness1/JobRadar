"""账号系统 HTTP 接口 (alpha-1 内测,邀请码 gated)。

Endpoints:
  POST /api/auth/register            邀请码 + email + 密码 → 创建未验证账号 + 发码
  POST /api/auth/verify-email        user_id + code → 激活账号 + 自动登录
  POST /api/auth/resend-verification user_id (或登录态) → 重发邮箱码
  POST /api/auth/login               email + 密码 → 返回 session token
  POST /api/auth/logout              登录态 → 注销 token
  GET  /api/auth/me                  登录态 → 返回当前用户
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.auth import auth_service, email_sender

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


# ── DI helpers ─────────────────────────────────────────────────────────────


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="缺少登录态")
    user = auth_service.resolve_session(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="登录态已过期,请重新登录")
    return user


# ── Schemas ────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    invite_code: str


class RegisterResponse(BaseModel):
    user_id: int
    email: str
    email_verified: bool
    message: str       # 给前端展示的提示文案


class VerifyEmailRequest(BaseModel):
    user_id: int
    code: str          # 6 位


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthSuccessResponse(BaseModel):
    token: str
    user_id: int
    email: str
    email_verified: bool


class ResendVerificationRequest(BaseModel):
    user_id: int


class MessageResponse(BaseModel):
    message: str


class UserInfoResponse(BaseModel):
    user_id: int
    email: str
    email_verified: bool
    user_key: str
    created_at: datetime
    last_login_at: datetime | None


# ── 工具:发码 + 失败降级 ──────────────────────────────────────────────────


def _send_verification_email(user, code: str) -> bool:
    """返回 True = 邮件发出去; False = 失败 (此时控制台打印了 code,内测可用)"""
    try:
        if email_sender.is_configured():
            email_sender.send_verification_code(to_email=user.email, code=code)
            return True
        else:
            logger.warning("邮件未配置,验证码打印到 console: user=%s code=%s", user.email, code)
            return False
    except Exception as exc:
        logger.warning("邮件发送失败 (%s),验证码打印到 console: user=%s code=%s",
                       type(exc).__name__, user.email, code)
        return False


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # 1. 校验邀请码
    invite_status = auth_service.find_usable_invite_code(db, req.invite_code)
    if not invite_status.ok:
        raise HTTPException(status_code=400, detail=invite_status.reason)

    # 2. 校验密码长度
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    # 3. 检查邮箱是否已存在
    existing = auth_service.find_user_by_email(db, req.email)
    if existing is not None:
        raise HTTPException(status_code=400, detail="该邮箱已注册,请直接登录")

    # 4. 创建未验证 user
    try:
        user = auth_service.create_user(
            db,
            email=req.email,
            password=req.password,
            invite_code_id=invite_status.code.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 5. 消耗邀请码 (绑住该 user 的 user_key,即使下面发邮件失败也不退回)
    user_key = auth_service.user_key_for(user)
    auth_service.consume_invite_code(db, invite_status.code, user_key)

    # 6. 发邮件验证码
    code = auth_service.issue_verification_code(db, user, purpose="register")
    sent_ok = _send_verification_email(user, code)
    db.commit()

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        email_verified=False,
        message=(
            f"注册申请成功! 验证码已发送到 {user.email},请查收 (10 分钟内有效)"
            if sent_ok
            else f"账号已创建,但邮件发送失败,请联系管理员 (验证码已打印到 backend 日志)"
        ),
    )


@router.post("/verify-email", response_model=AuthSuccessResponse)
def verify_email(req: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(auth_service.User).filter_by(id=req.user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.email_verified_at is not None:
        # 已验证,直接发 session token
        sess = auth_service.create_session(
            db, user,
            ua=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
        db.commit()
        return AuthSuccessResponse(
            token=sess.token, user_id=user.id, email=user.email, email_verified=True,
        )

    ok, reason = auth_service.verify_code(db, user.id, req.code, purpose="register")
    if not ok:
        db.commit()  # 写 attempts++
        raise HTTPException(status_code=400, detail=reason)

    auth_service.mark_email_verified(db, user)
    sess = auth_service.create_session(
        db, user,
        ua=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    db.commit()

    return AuthSuccessResponse(
        token=sess.token, user_id=user.id, email=user.email, email_verified=True,
    )


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(req: ResendVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(auth_service.User).filter_by(id=req.user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.email_verified_at is not None:
        return MessageResponse(message="该账号已验证,无需再发码")

    code = auth_service.issue_verification_code(db, user, purpose="register")
    sent_ok = _send_verification_email(user, code)
    db.commit()
    return MessageResponse(
        message=(
            f"验证码已重发到 {user.email}"
            if sent_ok
            else "邮件发送失败,验证码已打印到 backend 日志"
        )
    )


@router.post("/login", response_model=AuthSuccessResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.find_user_by_email(db, req.email)
    if user is None or not auth_service.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    sess = auth_service.create_session(
        db, user,
        ua=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return AuthSuccessResponse(
        token=sess.token,
        user_id=user.id,
        email=user.email,
        email_verified=user.email_verified_at is not None,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    token = _extract_bearer(authorization)
    if token:
        auth_service.revoke_session(db, token)
        db.commit()
    return MessageResponse(message="已注销")


@router.get("/me", response_model=UserInfoResponse)
def me(user=Depends(get_current_user)):
    return UserInfoResponse(
        user_id=user.id,
        email=user.email,
        email_verified=user.email_verified_at is not None,
        user_key=auth_service.user_key_for(user),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("/me/usage")
def me_usage(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """当前账号 token 配额 + 用量快照。exempt=True 代表不限。"""
    from app.services.llm_quota import get_usage_snapshot
    user_key = auth_service.user_key_for(user)
    return get_usage_snapshot(db, user_key)
