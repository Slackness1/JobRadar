"""小红书平台适配器 - 最小可运行版本。

能力范围（MVP）：
1) 关键词检索：通过 DuckDuckGo HTML 搜索 `site:xiaohongshu.com` 获取候选链接
2) 详情抓取：拉取详情页并提取 title/description/正文片段
3) 统一结构返回：供 orchestrator 入库

说明：
- 该实现不依赖小红书私有 API，不需要签名。
- 公开网页结构可能变化，失败时会回退到 search 摘要。
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

from .base import BaseIntelAdapter

_DDG_HTML_SEARCH_URL = "https://duckduckgo.com/html/"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class XiaohongshuIntelAdapter(BaseIntelAdapter):
    """小红书岗位情报适配器（最小可跑版）。"""

    def __init__(self):
        super().__init__()
        self.platform = "xiaohongshu"
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": _UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )

    async def ensure_session(self) -> None:
        return None

    async def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """通过 DuckDuckGo HTML 搜索小红书链接。"""
        q = f"site:xiaohongshu.com {query}"
        try:
            resp = self._session.get(
                _DDG_HTML_SEARCH_URL,
                params={"q": q, "kl": "cn-zh"},
                timeout=15,
            )
            resp.raise_for_status()
            html_text = resp.text
        except Exception:
            return []

        results: List[Dict[str, Any]] = []

        # DuckDuckGo HTML 结果常见结构：<a class="result__a" href="...">title</a>
        pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            flags=re.IGNORECASE | re.DOTALL,
        )

        for m in pattern.finditer(html_text):
            href = html.unescape(m.group("href") or "")
            title = self._clean_text(html.unescape(m.group("title") or ""))
            real_url = self._resolve_ddg_redirect(href)
            if not real_url:
                continue
            if "xiaohongshu.com" not in real_url:
                continue

            item_id = self._item_id_from_url(real_url)
            results.append(
                {
                    "id": item_id,
                    "title": title or f"小红书结果：{query}",
                    "author": "",
                    "url": real_url,
                    "publish_time": "",
                    "content": "",
                    "summary": title or query,
                    "author_meta": {"source": "ddg_html"},
                    "keywords": ["小红书", "岗位情报"],
                    "tags": ["xiaohongshu", "mvp"],
                    "metrics": {},
                    "entities": {"query": query},
                }
            )
            if len(results) >= limit:
                break

        return results

    async def fetch_detail(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """抓取详情页，提取 title/description/正文片段。"""
        url = item.get("url", "")
        if not url:
            return item

        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            page = resp.text
        except Exception:
            return item

        title = self._extract_first(page, [
            r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
            r'<meta[^>]+name="twitter:title"[^>]+content="([^"]+)"',
            r"<title>(.*?)</title>",
        ])
        desc = self._extract_first(page, [
            r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
            r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
        ])

        # 从 HTML 粗提纯文本，作为 raw_text 的兜底
        text_chunks = re.findall(r">([^<>]{20,})<", page)
        joined = "\n".join(self._clean_text(x) for x in text_chunks if self._clean_text(x))
        joined = joined[:3000]

        merged = dict(item)
        merged["title"] = title or item.get("title", "")
        merged["content"] = desc or joined or item.get("content", "")
        merged["summary"] = (desc or title or item.get("summary", ""))[:300]
        merged["publish_time"] = merged.get("publish_time") or self._extract_publish_time(page)
        return merged

    async def fetch_comments(self, item: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        _ = item, limit
        # MVP 暂不抓评论
        return []

    @staticmethod
    def _resolve_ddg_redirect(href: str) -> str:
        if not href:
            return ""
        if href.startswith("http"):
            # /l/?uddg=... 的完整 URL
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])
            return href
        if href.startswith("/l/?"):
            qs = parse_qs(urlparse(href).query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])
        return ""

    @staticmethod
    def _item_id_from_url(url: str) -> str:
        m = re.search(r"/explore/([A-Za-z0-9]+)", url)
        if m:
            return f"xhs-{m.group(1)}"
        return f"xhs-{abs(hash(url)) % 100000000}"

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text or "")
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _extract_first(page: str, patterns: List[str]) -> str:
        for p in patterns:
            m = re.search(p, page, flags=re.IGNORECASE | re.DOTALL)
            if m:
                return XiaohongshuIntelAdapter._clean_text(m.group(1))
        return ""

    @staticmethod
    def _extract_publish_time(page: str) -> str:
        # 尝试常见日期格式
        m = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})", page)
        if m:
            return m.group(1)
        return ""

    @staticmethod
    def parse_publish_time(v: str) -> Optional[datetime]:
        if not v:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        return None
