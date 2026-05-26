"""测 TikHub + Decodo 客户端 — 用 requests_mock 模拟响应。"""
from __future__ import annotations

import pytest

from app.services.taxonomy_discovery.budget_tracker import BudgetTracker
from app.services.taxonomy_discovery.crawler_client import CrawlerClient, DECODO_BASE


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def client(tmp_path) -> CrawlerClient:
    tracker = BudgetTracker(state_file=tmp_path / "b.json", limit_usd=10.0)
    return CrawlerClient(
        tikhub_key="fake_tikhub_key",
        decode_key="fake_decode_key",
        budget_tracker=tracker,
        rate_limit_qps=10,
    )


# --------------------------------------------------------------------------- #
# helper: 构造 Decodo 响应体
# --------------------------------------------------------------------------- #

def _decodo_ip_response(country: str = "China", country_code: str = "cn") -> dict:
    """模拟 ip.decodo.com 通过 Decodo 返回的 markdown 内容。"""
    return {
        "results": [
            {
                "markdown": (
                    f"| Field | Value |\n"
                    f"|---|---|\n"
                    f"| Country | {country} |\n"
                    f"| Country code | {country_code} |\n"
                    f"| IP | 1.2.3.4 |\n"
                )
            }
        ]
    }


def _decodo_xhs_response(content: str = "<html>fake xhs page</html>") -> dict:
    return {
        "results": [
            {"markdown": content}
        ]
    }


# --------------------------------------------------------------------------- #
# TikHub 搜索
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Decodo fetch — 正常路径
# --------------------------------------------------------------------------- #

def test_decode_fetch_charges_budget(client: CrawlerClient, requests_mock) -> None:
    """decode_fetch_url 含 geo preflight: 共扣 2 × $0.0015 = $0.003。

    第一次 POST 到 DECODO_BASE 是 geo preflight (ip.decodo.com)。
    第二次 POST 才是真实 XHS 抓取。
    requests_mock.post 传 list 时按顺序依次响应。
    """
    requests_mock.post(
        DECODO_BASE,
        [
            # 1st call — geo preflight
            {"json": _decodo_ip_response("China", "cn"), "status_code": 200},
            # 2nd call — actual XHS fetch
            {"json": _decodo_xhs_response("fake xhs page"), "status_code": 200},
        ],
    )
    result = client.decode_fetch_url("https://xhs.com/n/abc")
    assert "fake xhs page" in result
    # 2 Decodo calls × $0.0015 each
    assert client.budget_tracker.spent() == pytest.approx(0.003, abs=1e-6)


def test_decode_fetch_geo_verified_only_once(client: CrawlerClient, requests_mock) -> None:
    """geo preflight 只跑一次; 第二次 decode_fetch_url 不再重复校验。

    3 次 POST: preflight + fetch1 + fetch2 → budget = 3 × $0.0015。
    """
    requests_mock.post(
        DECODO_BASE,
        [
            {"json": _decodo_ip_response("China", "cn"), "status_code": 200},
            {"json": _decodo_xhs_response("page 1"), "status_code": 200},
            {"json": _decodo_xhs_response("page 2"), "status_code": 200},
        ],
    )
    r1 = client.decode_fetch_url("https://xhs.com/n/abc1")
    r2 = client.decode_fetch_url("https://xhs.com/n/abc2")
    assert "page 1" in r1
    assert "page 2" in r2
    assert client.budget_tracker.spent() == pytest.approx(0.0045, abs=1e-6)


# --------------------------------------------------------------------------- #
# Decodo fetch — geo 非中国时阻断
# --------------------------------------------------------------------------- #

def test_decode_geo_check_blocks_non_cn(client: CrawlerClient, requests_mock) -> None:
    """geo preflight 返回非中国 (USA/us) 时, 抛 RuntimeError, 且只扣 1 次 preflight 费。"""
    requests_mock.post(
        DECODO_BASE,
        [
            # preflight 返回美国
            {"json": _decodo_ip_response("United States", "us"), "status_code": 200},
        ],
    )
    with pytest.raises(RuntimeError, match="Decodo geo not CN"):
        client.decode_fetch_url("https://xhs.com/n/abc")

    # 只有 preflight 一次调用被计费
    assert client.budget_tracker.spent() == pytest.approx(0.0015, abs=1e-6)


# --------------------------------------------------------------------------- #
# 预算耗尽时阻断
# --------------------------------------------------------------------------- #

def test_budget_exceeded_blocks_call(client: CrawlerClient, requests_mock) -> None:
    """预算用完时调用 raise, 不发请求。"""
    client.budget_tracker.charge(9.999, "test_drain")
    with pytest.raises(Exception):  # BudgetExceededError
        client.search_notes(keyword="x")
