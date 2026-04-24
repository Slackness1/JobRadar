"""BOSS直聘平台适配器 - stub 版本"""
from typing import List, Dict, Any
from .base import BaseIntelAdapter


class BossIntelAdapter(BaseIntelAdapter):
    """BOSS直聘岗位情报适配器"""

    def __init__(self):
        super().__init__()
        self.platform = "boss"

    async def ensure_session(self) -> None:
        """确保登录态可用（当前 stub）"""
        pass

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """执行搜索（当前 stub）"""
        return []

    async def fetch_detail(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取详情（当前 stub）"""
        return None

    async def fetch_comments(self, item: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        """获取评论（当前 stub）"""
        return []
