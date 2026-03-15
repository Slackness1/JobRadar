"""平台浏览器会话管理"""
from typing import Dict, Optional


def get_platform_auth_status() -> Dict[str, Dict[str, str]]:
    """获取所有平台的认证状态

    返回格式：
    {
        "nowcoder": {"status": "not_configured", "last_login_at": None},
        "xiaohongshu": {"status": "not_configured", "last_login_at": None},
        "maimai": {"status": "not_configured", "last_login_at": None},
        "boss": {"status": "not_configured", "last_login_at": None},
        "zhihu": {"status": "not_configured", "last_login_at": None},
    }
    """
    return {
        "nowcoder": {"status": "not_configured", "last_login_at": None},
        "xiaohongshu": {"status": "not_configured", "last_login_at": None},
        "maimai": {"status": "not_configured", "last_login_at": None},
        "boss": {"status": "not_configured", "last_login_at": None},
        "zhihu": {"status": "not_configured", "last_login_at": None},
    }
