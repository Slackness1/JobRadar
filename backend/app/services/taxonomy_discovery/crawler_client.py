"""TikHub + Decodo HTTP 客户端封装。

TikHub: 小红书 search_notes / get_note_detail / get_note_comments
Decodo: 通用 web scraping, 给定 URL 返抓取后的 markdown/html
两个 API 调用都要先过 BudgetTracker; rate limit 10 RPS (TikHub 限制)。

Decodo IP 前置校验:
  每个 CrawlerClient 实例首次调用 decode_fetch_url 时, 先通过 Decodo 抓
  https://ip.decodo.com 确认出口 IP 在中国 (Country code == cn)。
  校验结果缓存在实例上 (_geo_verified), 不重复检查。
"""
from __future__ import annotations

import re
import time
from typing import Any

import requests

from .budget_tracker import BudgetTracker

TIKHUB_BASE = "https://api.tikhub.io/api/v1"
DECODO_BASE = "https://scraper-api.decodo.com/v2/scrape"

TIKHUB_COST = 0.010
DECODE_COST = 0.0015


def _extract_decodo_text(body: dict) -> str:
    """从 Decodo 响应中提取文本内容, 按 markdown → html → content 顺序 fallback。"""
    results = body.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            for key in ("markdown", "html", "content"):
                val = first.get(key)
                if isinstance(val, str) and val:
                    return val
    # top-level fallback (极少见)
    for key in ("markdown", "html", "content"):
        val = body.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _build_decodo_payload(url: str, strategy: str = "xhs-discovery") -> dict:
    """Decodo payload — XHS web 反爬墙是 JS-rendered, 所以 device_type=desktop +
    不传 headless (走纯 HTML 抓取) 才拿得到正文。
    """
    return {
        "url": url,
        "proxy_pool": "premium",
        "geo": "China",
        "locale": "zh-cn",
        "device_type": "desktop",
        "session_id": f"xhs-discovery-{strategy}",
        "markdown": True,
    }


def build_xhs_discovery_url(note_id: str, xsec_token: str) -> str:
    """构造 XHS web 帖子页 URL (discovery/item 路径 + xsec_token, bypass 'open in app' 反爬墙)。

    必须用 search_notes 返回的 xsec_token; 没 token 的话 fallback 到 /explore/<id>
    会被反爬墙挡只返登录提示。
    """
    if not xsec_token:
        return f"https://www.xiaohongshu.com/explore/{note_id}"
    from urllib.parse import quote
    token_q = quote(xsec_token, safe="")
    return (
        f"https://www.xiaohongshu.com/discovery/item/{note_id}"
        f"?xsec_token={token_q}&xsec_source=app_share"
    )


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
        self._geo_verified: bool = False

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def _verify_geo_is_cn(self) -> None:
        """通过 Decodo 抓 ip.decodo.com, 确认出口 IP Country code 为 cn。

        每个 CrawlerClient 实例只校验一次; 通过后设 self._geo_verified = True。
        非中国 IP 时 raise RuntimeError, 节省后续 XHS 抓取费用。
        此次校验本身计费 $0.0015 (同普通 fetch)。
        """
        if not self.budget_tracker.can_afford(DECODE_COST):
            from .budget_tracker import BudgetExceededError
            raise BudgetExceededError(
                f"无余额跑 geo preflight (剩 ${self.budget_tracker.remaining():.4f})"
            )
        self._throttle()
        payload = _build_decodo_payload("https://ip.decodo.com", strategy="geo-check")
        r = requests.post(
            DECODO_BASE,
            json=payload,
            headers={
                "Authorization": f"Basic {self.decode_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        r.raise_for_status()
        self.budget_tracker.charge(DECODE_COST, "decodo_geo_preflight")

        text = _extract_decodo_text(r.json())

        # 从文本中提取 Country code 字段 (格式: "Country code: cn" 或表格形式)
        code_match = re.search(r"Country\s+code[:\s|]+([a-zA-Z]{2})", text, re.IGNORECASE)
        country_match = re.search(r"Country[:\s|]+([^\n|]+)", text, re.IGNORECASE)

        country_code = code_match.group(1).strip().lower() if code_match else ""
        country_name = country_match.group(1).strip() if country_match else ""

        # ip.decodo.com 真实响应只有 "Country: CN" (没单独的 Country code 行),
        # 所以 country_name 也可能是 2 字母码; 一并接纳。
        country_name_norm = country_name.lower()
        if (
            country_code == "cn"
            or country_name_norm in ("china", "中国", "cn")
        ):
            self._geo_verified = True
            return

        raise RuntimeError(
            f"Decodo geo not CN: got country_code={country_code!r} country={country_name!r}. "
            "请检查 Decodo 账户的 geo 配置是否支持中国出口 IP。"
        )

    def search_notes(self, keyword: str, page: int = 1) -> list[dict[str, Any]]:
        """TikHub search_notes — 单次 ~20 results。

        当前 API key scope 限 `/xiaohongshu/app/` 系列;web_v3 / app_v2 等新接口不可用。
        响应结构: response.data.data.items[].note (扁平化后返 dict list, 每条含 id/title 等)。
        """
        if not self.budget_tracker.can_afford(TIKHUB_COST):
            from .budget_tracker import BudgetExceededError
            raise BudgetExceededError(f"无余额跑 search_notes (剩 ${self.budget_tracker.remaining():.4f})")
        self._throttle()
        r = requests.get(
            f"{TIKHUB_BASE}/xiaohongshu/app/search_notes",
            params={"keyword": keyword, "page": page},
            headers={"Authorization": f"Bearer {self.tikhub_key}"},
            timeout=30,
        )
        r.raise_for_status()
        self.budget_tracker.charge(TIKHUB_COST, "tikhub_search")
        body = r.json()
        items = (body.get("data") or {}).get("data", {}).get("items") or []
        notes: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            note = item.get("note") if isinstance(item.get("note"), dict) else item
            if note and isinstance(note, dict):
                notes.append(note)
        return notes

    def decode_fetch_url(self, url: str) -> str:
        """Decodo 抓单 URL, 返回 markdown/html 文本。

        首次调用时先做 IP 地理校验 (_verify_geo_is_cn), 确认出口在中国后才继续。
        """
        if not self._geo_verified:
            self._verify_geo_is_cn()

        if not self.budget_tracker.can_afford(DECODE_COST):
            from .budget_tracker import BudgetExceededError
            raise BudgetExceededError(f"无余额跑 decode_fetch_url (剩 ${self.budget_tracker.remaining():.4f})")
        self._throttle()
        payload = _build_decodo_payload(url)
        r = requests.post(
            DECODO_BASE,
            json=payload,
            headers={
                "Authorization": f"Basic {self.decode_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        r.raise_for_status()
        self.budget_tracker.charge(DECODE_COST, "decodo_fetch")
        return _extract_decodo_text(r.json())
