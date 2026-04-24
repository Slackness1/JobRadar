"""平台登录引导 - stub 版本"""
from typing import Dict


async def bootstrap_login(platform: str) -> Dict[str, str]:
    """为指定平台引导登录（当前 stub）

    返回格式：
    {
        "status": "success" / "auth_required",
        "message": "...",
    }
    """
    return {
        "status": "auth_required",
        "message": f"{platform} 平台登录功能暂未实现，请手动登录后使用 storage_state.py 保存 cookies",
    }
