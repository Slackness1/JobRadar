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


def test_search_filters_noise_titles():
    html = (
        '<a href="/discuss/1?sourceSSR=search">字节数据分析面经分享</a>'
        '<a href="/discuss/2?sourceSSR=search">中国银行总行信科实习求面经</a>'
        '<a href="/discuss/3?sourceSSR=search">有谁面过腾讯产品岗吗</a>'
        '<a href="/discuss/4?sourceSSR=search">美团数据分析一面 实习面经 20min</a>'
    )
    with patch.object(scraper, "_fetch", return_value=html):
        results = scraper.search("anything", limit=10)
    pids = [r.pid for r in results]
    assert pids == ["1", "4"]


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


def test_fetch_post_falls_back_to_full_meta_when_no_template():
    free_form_meta = (
        "1.分享一段做的比较成功但是又比较有挑战的事情 2.如果这个项目重做一次，"
        "哪里可以做得更好 3.分享一件比较难忘但最终结果可能是失败的事情"
    )
    html_free = f'<html><head><meta name="description" content="{free_form_meta}"/></head></html>'
    with patch.object(scraper, "_fetch", return_value=html_free):
        detail = scraper.fetch_post("999", title="携程产品经理秋招面经（二）")
    assert detail.parse_status == "ok"
    assert "1.分享一段" in detail.questions_text
    assert detail.company == "携程"


def test_fetch_post_short_meta_still_fails():
    html_short = '<html><head><meta name="description" content="太短了"/></head></html>'
    with patch.object(scraper, "_fetch", return_value=html_short):
        detail = scraper.fetch_post("888", title="某公司面经")
    # Short noise meta + no template fields → still failed (not ok),
    # but company may have been extracted from title.
    assert detail.parse_status in ("failed", "partial")
    assert detail.questions_text == ""


def test_parse_company_from_title():
    cases = [
        ("携程产品经理秋招面经（二）", "携程"),
        ("腾讯-微信支付 C++ 二面 面经 分析", "腾讯"),
        ("中金投行部分析师校招面经", "中金投行部"),
        ("上海玄信 量化研究员实习面经", "上海玄信"),
        ("", ""),
    ]
    for title, expected in cases:
        assert scraper.parse_company_from_title(title) == expected, f"failed on {title!r}"


@pytest.mark.integration
def test_search_real_nowcoder_smoke():
    """Hits real Nowcoder. Run manually: pytest -m integration."""
    results = scraper.search("数据分析面经", limit=3)
    assert len(results) >= 1
    assert all(r.pid.isdigit() for r in results)
