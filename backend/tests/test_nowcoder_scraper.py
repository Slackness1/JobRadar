import pathlib
from unittest.mock import patch

import pytest

from app.services.interview.nowcoder import scraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures_nowcoder"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_search_extracts_post_metas():
    with patch.object(scraper, "_fetch", return_value=_read("search_sample.html")):
        results = scraper.search("数据分析面经", limit=5)
    assert len(results) >= 2
    pids = [r.pid for r in results]
    assert "873597725214789632" in pids
    titles = {r.pid: r.title for r in results}
    assert titles["873597725214789632"]


def test_search_dedupes_repeated_pids():
    with patch.object(scraper, "_fetch", return_value=_read("search_sample.html")):
        results = scraper.search("anything", limit=20)
    seen = set()
    for r in results:
        assert r.pid not in seen
        seen.add(r.pid)


def test_fetch_post_parses_emoji_template():
    with patch.object(scraper, "_fetch", return_value=_read("post_sample.html")):
        detail = scraper.fetch_post("873597725214789632")
    assert detail.company == "聚智"
    assert detail.interview_date == "26-4-14"
    assert detail.position == "开发实习生"
    assert "单例模式" in detail.questions_text
    assert detail.parse_status == "ok"


def test_fetch_post_returns_failed_on_no_meta():
    html_no_meta = "<html><head></head><body>no meta description here</body></html>"
    with patch.object(scraper, "_fetch", return_value=html_no_meta):
        detail = scraper.fetch_post("000")
    assert detail.parse_status == "failed"
    assert detail.questions_text == ""


@pytest.mark.integration
def test_search_real_nowcoder_smoke():
    """Hits real Nowcoder. Run manually: pytest -m integration."""
    results = scraper.search("数据分析面经", limit=3)
    assert len(results) >= 1
    assert all(r.pid.isdigit() for r in results)
