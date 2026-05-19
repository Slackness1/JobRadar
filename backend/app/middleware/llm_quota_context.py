"""设 ContextVar `current_user_key` 让 LLM 调用点能记账。

每个请求一次性把 `X-Resume-User-Key` header 设进 ContextVar,响应返回前 reset。
LLM 调用点(分散在 8+ service 文件里)读 ContextVar 就拿到了 user_key,不用
plumb 进 service 层。

BackgroundTask 不继承 request contextvar — 在 task 入口要显式 set 一遍。
"""
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.llm_quota import set_current_user_key, reset_current_user_key


class LlmQuotaContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        user_key = request.headers.get("X-Resume-User-Key", "") or ""
        token = set_current_user_key(user_key.strip())
        try:
            return await call_next(request)
        finally:
            reset_current_user_key(token)
