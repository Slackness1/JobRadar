"""平台适配器基类"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class BaseIntelAdapter(ABC):
    """Job Intel 平台适配器基类"""

    platform: str

    def __init__(self):
        self.platform = self.__class__.__name__.replace("Adapter", "").lower()

    @abstractmethod
    async def ensure_session(self) -> None:
        """确保登录态可用"""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """执行搜索"""
        pass

    @abstractmethod
    async def fetch_detail(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取详情"""
        pass

    @abstractmethod
    async def fetch_comments(self, item: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        """获取评论"""
        pass

    def normalize_item(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """统一输出格式"""
        return {
            "platform": self.platform,
            "content_type": "post",
            "title": raw_item.get("title", ""),
            "author_name": raw_item.get("author", ""),
            "url": raw_item.get("url", ""),
            "publish_time": raw_item.get("publish_time", ""),
            "raw_text": raw_item.get("content", ""),
            "cleaned_text": raw_item.get("content", ""),
            "summary": raw_item.get("summary", ""),
            "keywords": [],
            "tags": [],
            "metrics": {},
            "entities": {},
        }
