"""小红书平台适配器 - Phase 2 模板实现"""
from typing import List, Dict, Any, Optional
from .base import BaseIntelAdapter


class XiaohongshuIntelAdapter(BaseIntelAdapter):
    """小红书岗位情报适配器。

    当前仍是模板实现，但已具备统一返回结构，便于后续接入真实搜索页/API。
    """

    def __init__(self):
        super().__init__()
        self.platform = "xiaohongshu"

    async def ensure_session(self) -> None:
        return None

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return [{
            "id": f"xiaohongshu-{abs(hash(query)) % 100000}",
            "title": f"小红书搜索结果：{query}",
            "author": "小红书模板用户",
            "url": "https://www.xiaohongshu.com/explore/mock-template",
            "publish_time": "2026-03-15",
            "content": f"这是针对查询 {query} 的小红书模板结果，后续替换为真实搜索输出。",
            "summary": f"小红书模板结果：{query}",
            "author_meta": {"source": "template"},
            "keywords": ["薪资", "面经"],
            "tags": ["xiaohongshu", "template"],
            "metrics": {"like_count": 0, "comment_count": 0},
            "entities": {"query": query},
        }][:limit]

    async def fetch_detail(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return item

    async def fetch_comments(self, item: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        return []
