"""Permission control middleware for read-only guest access."""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import base64


READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}

# 允许 guest 访问的 POST 路径（导出功能）
GUEST_ALLOWED_POST_PATHS = {
    "/api/export/csv",
    "/api/export/excel", 
    "/api/export/json",
}


class ReadOnlyGuestMiddleware(BaseHTTPMiddleware):
    """
    Middleware that restricts guest users to read-only access.
    Guest can only use GET requests and export endpoints.
    """
    
    async def dispatch(self, request: Request, call_next):
        # 获取认证用户名
        auth_header = request.headers.get("Authorization", "")
        username = self._extract_username(auth_header)
        
        # 如果是 guest 用户
        if username == "guest":
            method = request.method.upper()
            path = request.url.path
            
            # 允许只读方法
            if method in READ_ONLY_METHODS:
                return await call_next(request)
            
            # 允许导出接口
            if method == "POST" and path in GUEST_ALLOWED_POST_PATHS:
                return await call_next(request)
            
            # 拒绝其他写操作
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Guest users have read-only access. Please contact administrator for write permissions."
                }
            )
        
        # 非 guest 用户，正常放行
        return await call_next(request)
    
    def _extract_username(self, auth_header: str) -> str:
        """Extract username from Basic Auth header."""
        if not auth_header or not auth_header.startswith("Basic "):
            return ""
        
        try:
            # 解码 Basic Auth
            encoded = auth_header.replace("Basic ", "")
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, _ = decoded.split(":", 1)
            return username
        except Exception:
            return ""
