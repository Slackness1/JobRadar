"""测 TikHub + decode 客户端 — 用 vcrpy 录的 fixture 模拟响应。

注意: vcrpy cassettes 第一次跑时录真实 API, 提交后离线 replay。
为了节省 $0.01, 这里直接写假 cassette。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.taxonomy_discovery.budget_tracker import BudgetTracker
from app.services.taxonomy_discovery.crawler_client import CrawlerClient


@pytest.fixture
def client(tmp_path) -> CrawlerClient:
    tracker = BudgetTracker(state_file=tmp_path / "b.json", limit_usd=10.0)
    return CrawlerClient(
        tikhub_key="fake_tikhub_key",
        decode_key="fake_decode_key",
        budget_tracker=tracker,
        rate_limit_qps=10,
    )


def test_tikhub_search_charges_budget(client: CrawlerClient, requests_mock) -> None:
    """search_notes 调用一次扣 $0.010。"""
    requests_mock.get(
        "https://api.tikhub.io/api/v1/xiaohongshu/web_v1/search/notes",
        json={
            "data": {
                "notes": [
                    {"note_id": "n1", "title": "嘉实消费组实习", "user_id": "u1"},
                    {"note_id": "n2", "title": "易方达 TMT 面经", "user_id": "u2"},
                ]
            }
        },
        status_code=200,
    )
    notes = client.search_notes(keyword="嘉实消费组")
    assert len(notes) == 2
    assert notes[0]["note_id"] == "n1"
    assert client.budget_tracker.spent() == pytest.approx(0.010, abs=1e-6)


def test_decode_fetch_charges_budget(client: CrawlerClient, requests_mock) -> None:
    """decode fetch 一次扣 $0.0015。"""
    requests_mock.post(
        "https://api.web-scraping.dev/v1/fetch",
        json={"html": "<html>fake xhs page</html>", "ok": True},
        status_code=200,
    )
    html = client.decode_fetch_url("https://xhs.com/n/abc")
    assert "fake xhs page" in html
    assert client.budget_tracker.spent() == pytest.approx(0.0015, abs=1e-6)


def test_budget_exceeded_blocks_call(client: CrawlerClient, requests_mock) -> None:
    """预算用完时调用 raise, 不发请求。"""
    client.budget_tracker.charge(9.999, "test_drain")
    with pytest.raises(Exception):  # BudgetExceededError
        client.search_notes(keyword="x")
