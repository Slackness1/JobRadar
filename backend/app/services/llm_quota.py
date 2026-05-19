"""LLM token 配额 — alpha-1 试点防滥用。

设计:
- 一行 LlmUsage = 一次 LLM 调用。usage_date 单独存 'YYYY-MM-DD' (Asia/Shanghai),
  方便每日聚合 (索引 user_key + usage_date)。
- 配额绑在 InviteCode 上 (token_limit_total / token_limit_daily),NULL = 不限。
- user_key 跟 InviteCode 关系: `consumed_by_user_key` 直接对应 user_key (u_<id>)。
- 豁免: __demo__ / __guest__ / 空 user_key / 未消耗码的 user (合理:登录态外的 anon
  调用本来就受 throttle,不走 token 配额)。
- 失败安全 (fail-open on errors): record_usage 写库失败不能影响业务 LLM 响应,
  打 warn log;check_quota 查库失败也放行 (避免 DB 抖动整站挂)。

不在这里管:
- /chat/completions 上游 (DeepSeek) 的 rate limit — 那是 API 提供方的事。
- 后台 crawler / digest / diagnose LLM 调用 — 它们没 user_key,不走配额。
"""
from __future__ import annotations

import contextvars
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import InviteCode, LlmUsage

logger = logging.getLogger(__name__)

# ── ContextVar 跟踪当前请求的 user_key ────────────────────────────────────
# FastAPI 在每个请求里自己的 contextvars 隔离,LLM 调用点不需要把 user_key
# 一路 plumb 进去,直接读 _current_user_key.get()。BackgroundTasks 需要在调度
# 前显式 capture user_key (FastAPI 的 BackgroundTask 不保证 context 传递)。
_current_user_key: contextvars.ContextVar[str] = contextvars.ContextVar(
    "llm_quota_current_user_key", default=""
)


def set_current_user_key(user_key: str) -> contextvars.Token:
    return _current_user_key.set(user_key or "")


def reset_current_user_key(token: contextvars.Token) -> None:
    try:
        _current_user_key.reset(token)
    except (ValueError, LookupError):
        pass  # token from a different context, just ignore


def current_user_key() -> str:
    return _current_user_key.get()

# user_key 豁免:demo / guest / 空字符串。这些用户不走配额,也不写 LlmUsage 行
# (省 IO 也省 noise)。如果有人滥用 guest 模式,在 IP-level rate limit 那一层管。
_EXEMPT_USER_KEYS = frozenset({"__demo__", "__guest__", ""})

# Asia/Shanghai = UTC+8。SQLite 存 naive UTC,业务日期统一用 +8h 算 (跟 CLAUDE.md
# "查询用 datetime(col, 'localtime')" 一致)。
_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _today_sh() -> str:
    """Asia/Shanghai 当日 'YYYY-MM-DD'。"""
    return datetime.now(_TZ_SHANGHAI).strftime("%Y-%m-%d")


def is_exempt(user_key: str) -> bool:
    """豁免 user_key:demo / guest / 空。"""
    return not user_key or user_key in _EXEMPT_USER_KEYS


def _find_invite_code_for(db: Session, user_key: str) -> Optional[InviteCode]:
    """user_key → 它注册时消耗的 InviteCode。一个 user_key 只可能对应一个 invite_code。"""
    if is_exempt(user_key):
        return None
    return (
        db.query(InviteCode)
        .filter(InviteCode.consumed_by_user_key == user_key)
        .first()
    )


def get_usage_snapshot(db: Session, user_key: str) -> dict:
    """返当前 user 的配额 + 用量快照。给 /me/usage endpoint 用。

    返字段:
      - exempt: bool
      - total_limit / total_used / total_remaining (limit=None 时 remaining=None)
      - daily_limit / daily_used / daily_remaining
    """
    if is_exempt(user_key):
        return {
            "exempt": True,
            "total_limit": None, "total_used": 0, "total_remaining": None,
            "daily_limit": None, "daily_used": 0, "daily_remaining": None,
        }

    code = _find_invite_code_for(db, user_key)
    total_limit = code.token_limit_total if code else None
    daily_limit = code.token_limit_daily if code else None

    total_used = (
        db.query(func.coalesce(func.sum(LlmUsage.total_tokens), 0))
        .filter(LlmUsage.user_key == user_key)
        .scalar() or 0
    )
    daily_used = (
        db.query(func.coalesce(func.sum(LlmUsage.total_tokens), 0))
        .filter(LlmUsage.user_key == user_key, LlmUsage.usage_date == _today_sh())
        .scalar() or 0
    )

    def _remaining(limit, used):
        if limit is None:
            return None
        return max(0, limit - used)

    return {
        "exempt": False,
        "total_limit": total_limit,
        "total_used": int(total_used),
        "total_remaining": _remaining(total_limit, total_used),
        "daily_limit": daily_limit,
        "daily_used": int(daily_used),
        "daily_remaining": _remaining(daily_limit, daily_used),
    }


def check_quota_or_raise(db: Session, user_key: str) -> None:
    """超额 → HTTPException 429。豁免 / 无 invite_code 关联 / DB 故障都放行。

    用法:重 LLM endpoint 入口调一下,挡在 LLM 之前。
    """
    if is_exempt(user_key):
        return
    try:
        snap = get_usage_snapshot(db, user_key)
    except Exception:
        logger.warning("llm_quota.check_quota_or_raise 查库失败,放行", exc_info=True)
        return

    if snap["total_limit"] is not None and snap["total_used"] >= snap["total_limit"]:
        raise HTTPException(
            status_code=429,
            detail=(
                f"试点配额已用完 (累计 {snap['total_used']:,} / {snap['total_limit']:,} tokens)。"
                "请联系管理员 (cz9z@outlook.com) 申请扩额。"
            ),
        )
    if snap["daily_limit"] is not None and snap["daily_used"] >= snap["daily_limit"]:
        raise HTTPException(
            status_code=429,
            detail=(
                f"今日配额已用完 (当日 {snap['daily_used']:,} / {snap['daily_limit']:,} tokens),"
                "请明天再来。"
            ),
        )


def record_usage(
    db: Session,
    user_key: str,
    feature: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """写一行 LlmUsage。豁免 user_key 不写。失败不抛 (fail-open)。

    feature 取值:'resume_parse' / 'resume_recommend' / 'resume_chat' /
    'resume_quick_enrich' / 'resume_direction' / 'memory_extract' /
    'interview_*' (orchestrator / subagent / scoring 各一种) / 'misc'。
    """
    if is_exempt(user_key):
        return
    p = max(0, int(prompt_tokens or 0))
    c = max(0, int(completion_tokens or 0))
    if p == 0 and c == 0:
        return  # 没拿到 usage 字段,不写空行
    try:
        row = LlmUsage(
            user_key=user_key,
            feature=feature or "misc",
            prompt_tokens=p,
            completion_tokens=c,
            total_tokens=p + c,
            usage_date=_today_sh(),
        )
        db.add(row)
        db.commit()
    except Exception:
        logger.warning(
            "llm_quota.record_usage 写库失败 user_key=%s feature=%s p=%d c=%d",
            user_key, feature, p, c, exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass


def extract_usage_from_response(resp_json: dict) -> tuple[int, int]:
    """从 OpenAI-compatible 响应里抠 (prompt_tokens, completion_tokens)。

    DeepSeek / OpenAI 返 `usage: {prompt_tokens, completion_tokens, total_tokens}`,
    抠不到返 (0, 0)。
    """
    if not isinstance(resp_json, dict):
        return 0, 0
    usage = resp_json.get("usage") or {}
    if not isinstance(usage, dict):
        return 0, 0
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def record_usage_for_current(feature: str, prompt_tokens: int, completion_tokens: int) -> None:
    """从 ContextVar 取当前 user_key,自开 SessionLocal 写一行 LlmUsage。

    LLM 调用点用这个 — 不需要把 db / user_key 一路 plumb 进 service 层。
    """
    user_key = current_user_key()
    if is_exempt(user_key):
        return
    if (prompt_tokens or 0) <= 0 and (completion_tokens or 0) <= 0:
        return
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        record_usage(db, user_key, feature, prompt_tokens, completion_tokens)
    finally:
        db.close()


def record_usage_from_response_for_current(feature: str, resp_json: dict) -> None:
    """从 OpenAI-compatible 响应抠 usage + 记账。LLM 调用点 1 行 wrap。"""
    p, c = extract_usage_from_response(resp_json)
    record_usage_for_current(feature, p, c)
