"""Decodo Web Scraping API client — shared helper for SPA rendering.

Use when target site is SPA with client-side routing or heavy anti-bot that
defeats plain requests / curl_cffi from VPS, but Camoufox (Decodo's headless
Firefox) can render.

2026-05-27: 实测 default proxy_pool (无 premium) 就能扛
career.abchina.com / dachengjj.zhiye.com / gffunds.jobs.feishu.cn 三家 SPA
渲染。premium 只在 xhs 这种顶级反爬必用,其它默认池就够,**省 ~5x 成本**。

Usage:
    html = fetch_decodo_spa("https://career.abchina.com/build/index.html#/99")
    if html:
        # parse jobs from rendered DOM
"""
from __future__ import annotations

import os
import time
from typing import Optional

import requests

DECODO_ENDPOINT = "https://scraper-api.decodo.com/v2/scrape"


def _auth() -> Optional[str]:
    """Returns full Authorization header value or None if not configured."""
    return os.environ.get("DECODO_AUTHORIZATION")


def fetch_decodo_spa(
    url: str,
    wait_ms: int = 12000,
    use_premium: bool = False,
    geo: str = "China",
    locale: str = "zh-cn",
    device: str = "desktop",
    timeout: int = 200,
) -> str:
    """Render a SPA URL via Decodo and return the rendered HTML string.

    Returns empty string on any error (caller must handle empty rendering).
    Default `use_premium=False` saves ~5x cost vs premium pool — only enable
    for sites with extreme anti-bot (e.g. xhs).
    """
    auth = _auth()
    if not auth:
        return ""

    payload = {
        "url": url,
        "headless": "html",
        "geo": geo,
        "locale": locale,
        "device_type": device,
        "session_id": f"jobradar-{int(time.time() * 1000)}",
        "wait_for_page_load": True,
        "wait_after_page_load": wait_ms,
    }
    if use_premium:
        payload["proxy_pool"] = "premium"

    try:
        r = requests.post(
            DECODO_ENDPOINT,
            headers={"Authorization": auth, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except Exception:
        return ""

    if r.status_code != 200:
        return ""
    try:
        data = r.json()
    except Exception:
        return ""
    results = data.get("results") or []
    if not results:
        return ""
    return results[0].get("content") or ""
