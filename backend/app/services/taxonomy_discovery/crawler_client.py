"""TikHub + decode HTTP 客户端封装。

TikHub: 小红书 search_notes / get_note_detail / get_note_comments
decode: 通用 web scraping, 给定 URL 返抓取后的 HTML/text
两个 API 调用都要先过 BudgetTracker; rate limit 10 RPS (TikHub 限制)。
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .budget_tracker import BudgetTracker

TIKHUB_BASE = "https://api.tikhub.io/api/v1"
DECODE_BASE = "https://api.web-scraping.dev/v1"  # TODO: 用户确认 decode 实际 endpoint

TIKHUB_COST = 0.010
DECODE_COST = 0.0015


class CrawlerClient:
    def __init__(
        self,
        tikhub_key: str,
        decode_key: str,
        budget_tracker: BudgetTracker,
        rate_limit_qps: int = 10,
    ) -> None:
        self.tikhub_key = tikhub_key
        self.decode_key = decode_key
        self.budget_tracker = budget_tracker
        self._min_interval = 1.0 / rate_limit_qps
        self._last_call: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def search_notes(self, keyword: str, page: int = 1) -> list[dict[str, Any]]:
        """TikHub search_notes — 单次 ~20 results。"""
        if not self.budget_tracker.can_afford(TIKHUB_COST):
            from .budget_tracker import BudgetExceededError
            raise BudgetExceededError(f"无余额跑 search_notes (剩 ${self.budget_tracker.remaining():.4f})")
        self._throttle()
        r = requests.get(
            f"{TIKHUB_BASE}/xiaohongshu/web_v1/search/notes",
            params={"keyword": keyword, "page": page},
            headers={"Authorization": f"Bearer {self.tikhub_key}"},
            timeout=30,
        )
        r.raise_for_status()
        self.budget_tracker.charge(TIKHUB_COST, "tikhub_search")
        notes = r.json().get("data", {}).get("notes", [])
        return notes

    def decode_fetch_url(self, url: str) -> str:
        """decode 抓单 URL, 返回 raw HTML/text。"""
        if not self.budget_tracker.can_afford(DECODE_COST):
            from .budget_tracker import BudgetExceededError
            raise BudgetExceededError(f"无余额跑 decode_fetch_url (剩 ${self.budget_tracker.remaining():.4f})")
        self._throttle()
        r = requests.post(
            f"{DECODE_BASE}/fetch",
            json={"url": url},
            headers={"Authorization": f"Bearer {self.decode_key}"},
            timeout=60,
        )
        r.raise_for_status()
        self.budget_tracker.charge(DECODE_COST, "decode_fetch")
        return r.json().get("html", "")
