"""集中式会话身份解析 —— 跨路由共享的越权红线依赖。

把"登录账号身份必须由服务端验证的 bearer token 推导、header 不得冒充"这条
不变量做成一个可被多个路由 (resume_copilot / interview / student_kb …) 复用的
FastAPI 依赖, 避免各路由各写一遍鉴权逻辑 (历史上 interview / student_kb 就因为
各自直接信任 X-Resume-User-Key header 而留了同款越权口子)。

行为契约 (与 resume_copilot 历史实现逐字一致, 不得漂移):

  1) 带 bearer token:
       - token 合法 → 用 auth_service.user_key_for(user) 推出权威 u_<id>,
         *忽略* header 里传的值 (即便它跟 token 用户不一致, 以 token 为准);
       - token 非法/过期 → 401。不静默回退 header, 否则攻击者塞个假 token
         就能绕回 header 冒充。
  2) 无 token:
       - header 给的是账号形 key (u_<id>) → 这是可枚举的登录身份, 没有 token
         背书一律不认, 返回空 key (→ 归属校验 403)。这正是堵掉的越权口子。
       - 否则 (guest 随机 UUID / 历史非账号 key) → 沿用 header 值, 保持 guest /
         demo / 历史会话既有行为不变。X-Guest 只作显式 guest 信号, 不改变上面逻辑。
"""
from __future__ import annotations

import re

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import _extract_bearer
from app.services.auth import auth_service


# 登录账号 user_key 形如 u_<自增id> (auth_service.user_key_for)。这个值可枚举,
# 所以它只有在被一个 *服务端验证过的 bearer token* 背书时才可信 — 否则任何登录用户
# 改一下 X-Resume-User-Key header 就能冒充别人。Guest 的 key 是随机 UUID, 不属此形。
_ACCOUNT_USER_KEY_RE = re.compile(r'^u_\d+$')


def resolve_user_key(
    authorization: str | None = Header(default=None),
    x_resume_user_key: str = Header(default=''),
    x_guest: str = Header(default=''),
    db: Session = Depends(get_db),
) -> str:
    """集中式身份解析: 返回一个 **可信** 的 user_key 供归属校验使用。

    详细安全不变量见模块 docstring。
    """
    token = _extract_bearer(authorization)
    if token:
        user = auth_service.resolve_session(db, token)
        if user is None:
            raise HTTPException(status_code=401, detail='登录态已过期,请重新登录')
        return auth_service.user_key_for(user)

    header_key = (x_resume_user_key or '').strip()
    if _ACCOUNT_USER_KEY_RE.match(header_key):
        # 账号形 key 但无 token 背书 — 拒绝冒充, 退化成匿名 (空 key)。
        return ''
    return header_key
