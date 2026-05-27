"""Schema tests for Phase G T5/T6 知识库合成 helpers."""
from __future__ import annotations

from app.services.phase_g.knowledge_synthesis import (
    SUBCAT_TO_STRATEGY,
    _KEYWORD_MAP,
    build_synthesis_user_message,
    compute_data_basis,
    expected_data_confidence,
)
from app.services.phase_g.xhs_classifier import _SUB_CATS_27


def test_all_subcats_mapped_to_strategy():
    missing = [sc for sc in _SUB_CATS_27 if sc not in SUBCAT_TO_STRATEGY]
    assert not missing, f"sub_cats without strategy mapping: {missing}"


def test_strategy_types_only_7():
    strategy_types = set(SUBCAT_TO_STRATEGY.values())
    expected = {
        "基本面权益",
        "量化",
        "固定收益",
        "卖方研究",
        "多资产_FOF_衍生品",
        "相关补充",
        "AI 应用_PM_开发",
    }
    assert strategy_types == expected


def test_all_subcats_have_keyword_map():
    """每个 sub_cat 都该有 keyword 兜底, 否则 SAIF gather 退化成空。"""
    missing = [sc for sc in _SUB_CATS_27 if sc not in _KEYWORD_MAP]
    assert not missing, f"sub_cats without keyword map: {missing}"


def test_build_user_message_includes_all_sections():
    msg = build_synthesis_user_message(
        sub_cat="公募权益研究员",
        strategy_type="基本面权益",
        posts=[
            {
                "source_url": "https://xhs.example/url1",
                "content": "易方达消费组今年招 2 个海外硕士",
                "company_mentions": ["易方达"],
                "verbatim_signals": ["路径清晰"],
                "relevance_score": 0.9,
                "extracted": {},
            }
        ],
        saif_records=[
            {"role_type": "权益研究员", "company": "易方达基金", "year": "2024", "count": 1, "industry": "公募基金"}
        ],
        ground_truth=[
            {"name": "易方达基金", "tier": "一线公募", "must_have": True, "source": ["saif:2024"]}
        ],
    )
    assert "sub_cat: 公募权益研究员" in msg
    assert "strategy_type (固定): 基本面权益" in msg
    assert "易方达" in msg
    assert "Post 1" in msg
    assert "Ground truth" in msg


def test_compute_data_basis_filters_placeholders():
    posts = [
        {"company_mentions": ["易方达", "未明确"]},
        {"company_mentions": ["华夏", "易方达"]},
    ]
    basis = compute_data_basis(posts, saif_records=[])
    assert basis["post_count"] == 2
    assert basis["company_mention_count"] == 2  # 易方达 + 华夏 (未明确 滤掉)
    assert basis["saif_alumni_count"] == 0


def test_expected_data_confidence_thresholds():
    assert expected_data_confidence({"post_count": 30, "company_mention_count": 10, "saif_alumni_count": 3}) == "high"
    assert expected_data_confidence({"post_count": 50, "company_mention_count": 20, "saif_alumni_count": 0}) == "medium"
    assert expected_data_confidence({"post_count": 20, "company_mention_count": 6, "saif_alumni_count": 0}) == "medium"
    assert expected_data_confidence({"post_count": 10, "company_mention_count": 5, "saif_alumni_count": 0}) == "low"
    assert expected_data_confidence({"post_count": 30, "company_mention_count": 3, "saif_alumni_count": 5}) == "low"
