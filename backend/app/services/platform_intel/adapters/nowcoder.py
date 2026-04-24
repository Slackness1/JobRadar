"""牛客平台适配器 - Phase 2 模板实现"""
from typing import List, Dict, Any, Optional
from .base import BaseIntelAdapter


class NowcoderIntelAdapter(BaseIntelAdapter):
    """牛客岗位情报适配器。

    当前仍是模板实现，但已具备统一返回结构，便于后续接入真实搜索页/API。
    """

    def __init__(self):
        super().__init__()
        self.platform = "nowcoder"

    async def ensure_session(self) -> None:
        return None

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return [{
            "id": f"nowcoder-{abs(hash(query)) % 100000}",
            "title": f"牛客搜索结果：{query}",
            "author": "牛客模板用户",
            "url": "https://www.nowcoder.com/discuss/mock-template",
            "publish_time": "2026-03-15",
            "content": f"这是针对查询 {query} 的牛客模板结果，后续替换为真实搜索输出。",
            "summary": f"牛客模板结果：{query}",
            "author_meta": {"source": "template"},
            "keywords": ["面经", "笔试"],
            "tags": ["nowcoder", "template"],
            "metrics": {"like_count": 0, "comment_count": 0},
            "entities": {"query": query},
        }][:limit]

    async def fetch_detail(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return item

    async def fetch_comments(self, item: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        return []
