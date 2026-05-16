"""账号服务 — 密码 / token / 邀请码 / 邮箱验证。

设计要点:
  - 密码: bcrypt 12 cost
  - session token: secrets.token_urlsafe(32) → ~43 字符,30 天 expires
  - 邀请码: consume 单次,consumed_at + consumed_by_user_key 字段
  - 邮箱验证码: 6 位数字,10 min expires,limit 5 次输入尝试
  - user_key 映射: 登录后用 f"u_{user.id}" 作为 user_key 写到 account_memory 等
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from sqlalchemy.orm import Session

from app.models import EmailVerification, InviteCode, User, UserSession

logger = logging.getLogger(__name__)

SESSION_TTL_DAYS = 30
VERIFICATION_TTL_MINUTES = 10
VERIFICATION_MAX_ATTEMPTS = 5
BCRYPT_COST = 12


# ── user_key 映射 ─────────────────────────────────────────────────────────


def user_key_for(user: User) -> str:
    """登录后 user_key = u_<id>。永久 stable,即使 email 改了 user_key 不变。"""
    return f"u_{user.id}"


# ── 密码 ───────────────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    if not plain or len(plain) < 6:
        raise ValueError("password too short (min 6)")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ── 邀请码 ─────────────────────────────────────────────────────────────────


@dataclass
class InviteCodeStatus:
    ok: bool
    code: Optional[InviteCode] = None
    reason: str = ""


def find_usable_invite_code(db: Session, raw_code: str) -> InviteCodeStatus:
    """查邀请码是否可用 (存在 + 未消耗 + 未过期)。不消耗。"""
    raw_code = (raw_code or "").strip().upper()
    if not raw_code:
        return InviteCodeStatus(ok=False, reason="邀请码不能为空")
    row = db.query(InviteCode).filter(InviteCode.code == raw_code).one_or_none()
    if row is None:
        return InviteCodeStatus(ok=False, reason="邀请码不存在")
    if row.consumed_at is not None:
        return InviteCodeStatus(ok=False, reason="邀请码已被使用")
    if row.expires_at is not None and row.expires_at < datetime.utcnow():
        return InviteCodeStatus(ok=False, reason="邀请码已过期")
    return InviteCodeStatus(ok=True, code=row)


def consume_invite_code(db: Session, code: InviteCode, user_key: str) -> None:
    code.consumed_at = datetime.utcnow()
    code.consumed_by_user_key = user_key
    db.flush()


# ── 邮箱验证码 ─────────────────────────────────────────────────────────────


def issue_verification_code(db: Session, user: User, *, purpose: str = "register") -> str:
    """新建一条 EmailVerification,返回 6 位 code。同 purpose 历史的旧码不删,
    verify_code 只挑 expires_at > now & verified_at IS NULL 的最新一条。"""
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.utcnow()
    row = EmailVerification(
        user_id=user.id,
        code=code,
        purpose=purpose,
        sent_at=now,
        expires_at=now + timedelta(minutes=VERIFICATION_TTL_MINUTES),
        attempts=0,
    )
    db.add(row)
    db.flush()
    return code


def verify_code(db: Session, user_id: int, input_code: str, *, purpose: str = "register") -> tuple[bool, str]:
    """校验邮箱验证码。返回 (ok, reason_if_fail)。"""
    input_code = (input_code or "").strip()
    if not input_code or len(input_code) != 6 or not input_code.isdigit():
        return False, "验证码格式错误 (6 位数字)"

    now = datetime.utcnow()
    # 拿最新一条未验证、未过期的
    row: Optional[EmailVerification] = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.user_id == user_id,
            EmailVerification.purpose == purpose,
            EmailVerification.verified_at.is_(None),
            EmailVerification.expires_at > now,
        )
        .order_by(EmailVerification.sent_at.desc())
        .first()
    )
    if row is None:
        return False, "没有有效的验证码,请重新发送"
    if (row.attempts or 0) >= VERIFICATION_MAX_ATTEMPTS:
        return False, "尝试次数超限,请重新发送验证码"
    row.attempts = (row.attempts or 0) + 1
    if row.code != input_code:
        db.flush()
        return False, "验证码不正确"
    row.verified_at = now
    db.flush()
    return True, ""


# ── 用户 ───────────────────────────────────────────────────────────────────


def find_user_by_email(db: Session, email: str) -> Optional[User]:
    email = (email or "").strip().lower()
    if not email:
        return None
    return db.query(User).filter(User.email == email).one_or_none()


def create_user(db: Session, *, email: str, password: str, invite_code_id: int | None) -> User:
    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        invite_code_id=invite_code_id,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()  # 拿 id
    return user


def mark_email_verified(db: Session, user: User) -> None:
    user.email_verified_at = datetime.utcnow()
    db.flush()


# ── Session ────────────────────────────────────────────────────────────────


def create_session(db: Session, user: User, *, ua: str | None = None, ip: str | None = None) -> UserSession:
    now = datetime.utcnow()
    token = secrets.token_urlsafe(32)
    user.last_login_at = now
    sess = UserSession(
        user_id=user.id,
        token=token,
        created_at=now,
        expires_at=now + timedelta(days=SESSION_TTL_DAYS),
        ua=ua,
        ip=ip,
    )
    db.add(sess)
    db.flush()
    return sess


def resolve_session(db: Session, token: str | None) -> Optional[User]:
    """Bearer token → User (or None if invalid/expired/revoked)。"""
    if not token:
        return None
    now = datetime.utcnow()
    sess = (
        db.query(UserSession)
        .filter(
            UserSession.token == token,
            UserSession.expires_at > now,
            UserSession.revoked_at.is_(None),
        )
        .one_or_none()
    )
    if sess is None:
        return None
    return db.query(User).filter(User.id == sess.user_id).one_or_none()


def revoke_session(db: Session, token: str) -> bool:
    sess = db.query(UserSession).filter(UserSession.token == token).one_or_none()
    if sess is None or sess.revoked_at is not None:
        return False
    sess.revoked_at = datetime.utcnow()
    db.flush()
    return True
