"""search_candidates 后处理纯函数测试 — 置顶/收窄/排除/空偏好 noop。

_v2_items_from_ranked 返回的是 Pydantic ResumeRecommendationItem 对象(不是 dict),
所以 helper 走 getattr;这里用 SimpleNamespace 模拟同形状的 item。
"""
from types import SimpleNamespace

from app.services.resume_copilot.recommend_search import _apply_company_pref, _apply_exclude


def _it(company, title="x", sub="某赛道"):
    return SimpleNamespace(company=company, job_title=title, matched_track_label=sub)


def test_pin_preferred_companies_to_front_keeps_others():
    feed = [_it("A"), _it("B"), _it("字节"), _it("C")]
    out = _apply_company_pref(feed, companies=["字节"], only=False)
    assert [x.company for x in out] == ["字节", "A", "B", "C"]  # 置顶, 不删其余


def test_only_restricts_to_preferred_companies():
    feed = [_it("A"), _it("字节"), _it("B")]
    out = _apply_company_pref(feed, companies=["字节"], only=True)
    assert [x.company for x in out] == ["字节"]  # only → 收窄


def test_exclude_filters_out():
    feed = [_it("国企A"), _it("字节")]
    out = _apply_exclude(feed, exclude=["国企"])
    assert [x.company for x in out] == ["字节"]


def test_empty_company_pref_is_noop():
    feed = [_it("A"), _it("B")]
    assert _apply_company_pref(feed, companies=[], only=False) == feed
