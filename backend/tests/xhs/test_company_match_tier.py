"""TDD: XHS 公司别名感知三态分层 — _company_match_kind + fetch_for_job 分层行为。"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.xhs.context import _company_match_kind, _norm_company, fetch_for_job


# ---------------------------------------------------------------------------
# _norm_company
# ---------------------------------------------------------------------------

class TestNormCompany:
    def test_strips_legal_suffix(self):
        assert _norm_company("中金公司") == "中金"

    def test_strips_parenthetical_location(self):
        assert _norm_company("字节跳动（北京）有限公司") == "字节跳动"

    def test_lowercase_english(self):
        result = _norm_company("ByteDance Ltd")
        assert result == result.lower()

    def test_empty_string(self):
        assert _norm_company("") == ""

    def test_keeps_short_names(self):
        # 短名不被误删
        assert "中金" in _norm_company("中金")


# ---------------------------------------------------------------------------
# _company_match_kind — exact
# ---------------------------------------------------------------------------

class TestCompanyMatchKindExact:
    def test_exact_same_string(self):
        assert _company_match_kind("中金公司", ["中金公司"]) == "exact"

    def test_exact_after_norm_suffix_stripped(self):
        # "中金有限公司" vs "中金公司" → 两者 norm 后都是 "中金"
        assert _company_match_kind("中金有限公司", ["中金公司"]) == "exact"

    def test_exact_identical_norm(self):
        assert _company_match_kind("腾讯", ["腾讯"]) == "exact"


# ---------------------------------------------------------------------------
# _company_match_kind — alias
# ---------------------------------------------------------------------------

class TestCompanyMatchKindAlias:
    def test_alias_substring_job_in_target(self):
        # "中金" ⊂ "中金公司(norm→中金)" — 同 exact 这里,
        # 改用更长变体测 substring 路径
        assert _company_match_kind("中金", ["中金证券"]) == "alias"

    def test_alias_target_in_job(self):
        # "字节跳动" norm→"字节跳动"; target "字节" norm→"字节" → 子串
        assert _company_match_kind("字节跳动", ["字节"]) == "alias"

    def test_alias_via_internet_brand(self):
        # "字节" 和 "抖音" 都归属同一品牌
        assert _company_match_kind("字节", ["抖音"]) == "alias"

    def test_alias_bytedance_vs_bytedance_fullname(self):
        assert _company_match_kind("字节跳动", ["字节跳动有限公司"]) in ("exact", "alias")


# ---------------------------------------------------------------------------
# _company_match_kind — none
# ---------------------------------------------------------------------------

class TestCompanyMatchKindNone:
    def test_none_different_company(self):
        assert _company_match_kind("中金", ["腾讯"]) == "none"

    def test_none_empty_targets(self):
        assert _company_match_kind("中金", []) == "none"

    def test_none_different_finance_firms(self):
        assert _company_match_kind("华泰证券", ["国泰君安"]) == "none"

    def test_none_job_company_empty(self):
        # 空 job_company → norm 为空 → 不匹配
        assert _company_match_kind("", ["中金"]) == "none"


# ---------------------------------------------------------------------------
# fetch_for_job — 分层行为 (monkeypatch retrieve.search)
# ---------------------------------------------------------------------------

_FAKE_INSIGHTS = [
    {
        "insight_id": "ins-1",
        "score": 0.95,
        "type": ["company_anecdote"],
        "role_target": ["分析师"],
        "company_target": ["中金公司"],  # 命中 job_company="中金"
        "sector_target": [],
        "content": "中金面试三轮,最后一轮 MD 压面",
        "source_quote": "",
        "speaker": "author",
        "confidence": "high",
        "corroboration": [],
        "dispute": {},
        "source": {"note_id": "n1", "title": "中金秋招", "author": "user1", "liked": 10, "comments": 2, "url": "", "keywords": []},
    },
    {
        "insight_id": "ins-2",
        "score": 0.80,
        "type": ["role_insight"],
        "role_target": ["分析师"],
        "company_target": ["高盛"],  # 不命中
        "sector_target": [],
        "content": "高盛投行面试非常难",
        "source_quote": "",
        "speaker": "author",
        "confidence": "med",
        "corroboration": [],
        "dispute": {},
        "source": {"note_id": "n2", "title": "高盛面经", "author": "user2", "liked": 5, "comments": 1, "url": "", "keywords": []},
    },
    {
        "insight_id": "ins-3",
        "score": 0.70,
        "type": ["company_anecdote"],
        "role_target": [],
        "company_target": ["中金"],   # exact match (norm→中金)
        "sector_target": [],
        "content": "中金文化非常卷",
        "source_quote": "",
        "speaker": "commenter",
        "confidence": "med",
        "corroboration": [],
        "dispute": {},
        "source": {"note_id": "n3", "title": "中金文化", "author": "user3", "liked": 3, "comments": 0, "url": "", "keywords": []},
    },
    {
        "insight_id": "ins-4",
        "score": 0.60,
        "type": ["industry_trend"],
        "role_target": [],
        "company_target": ["摩根士丹利"],  # 不命中
        "sector_target": [],
        "content": "外资行整体缩招",
        "source_quote": "",
        "speaker": "author",
        "confidence": "med",
        "corroboration": [],
        "dispute": {},
        "source": None,
    },
]


@pytest.fixture
def mock_search(monkeypatch):
    """monkeypatch retrieve.search 返回固定的 4 条假数据。"""
    import app.services.xhs.context as ctx_mod
    monkeypatch.setattr(ctx_mod.retrieve, "search", lambda *a, **kw: list(_FAKE_INSIGHTS))
    return None


class TestFetchForJobTiering:
    def test_company_hits_come_before_none(self, mock_search):
        results = fetch_for_job(None, company="中金", job_title="分析师", k=4)
        kinds = [r["company_match_kind"] for r in results]
        # 所有 exact/alias 出现在 none 之前
        last_hit_idx = max((i for i, k in enumerate(kinds) if k in ("exact", "alias")), default=-1)
        first_none_idx = next((i for i, k in enumerate(kinds) if k == "none"), len(kinds))
        assert last_hit_idx < first_none_idx, f"分层错误: {kinds}"

    def test_every_result_has_match_kind(self, mock_search):
        results = fetch_for_job(None, company="中金", job_title="分析师", k=4)
        for r in results:
            assert "company_match_kind" in r, f"缺 company_match_kind: {r['insight_id']}"
            assert r["company_match_kind"] in ("exact", "alias", "none")

    def test_none_not_discarded(self, mock_search):
        """降级证据不丢弃 — k=4 时全部 4 条都应返回。"""
        results = fetch_for_job(None, company="中金", job_title="分析师", k=4)
        assert len(results) == 4

    def test_tier1_fills_first_when_k_is_small(self, mock_search):
        """k=2: 先填 tier1(命中中金的 ins-1, ins-3),不足才补 tier2。"""
        results = fetch_for_job(None, company="中金", job_title="分析师", k=2)
        assert len(results) == 2
        # 两条都应是 exact/alias
        for r in results:
            assert r["company_match_kind"] in ("exact", "alias"), (
                f"k=2 但取到了 none 的: {r['insight_id']}"
            )

    def test_tier2_fills_when_tier1_insufficient(self, mock_search):
        """k=3 时 tier1 只有 2 条,第 3 条从 tier2 补。"""
        results = fetch_for_job(None, company="中金", job_title="分析师", k=3)
        assert len(results) == 3
        kinds = [r["company_match_kind"] for r in results]
        assert kinds.count("none") == 1  # 一条降级补位

    def test_original_dict_not_mutated(self, mock_search):
        """不修改 retrieve.search 返回的原始 dict。"""
        original_first = _FAKE_INSIGHTS[0]
        assert "company_match_kind" not in original_first, "原始 dict 被污染"
        fetch_for_job(None, company="中金", job_title="分析师", k=2)
        assert "company_match_kind" not in original_first, "fetch_for_job 改了原始 dict"

    def test_empty_query_returns_empty(self):
        """company + job_title 都为空时,不调 search,直接返回空。"""
        results = fetch_for_job(None, company="", job_title="", k=2)
        assert results == []
