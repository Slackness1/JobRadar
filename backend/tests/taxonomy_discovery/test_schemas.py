"""测 schemas — 主要测能 round-trip JSON 不丢字段 + enum 校验。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.taxonomy_discovery.schemas import (
    StrategyType,
    PostTaxonomyExtract,
    PostKBExtract,
    DualSchemaExtract,
    KBInsightType,
    StrategySignal,
    IndustrySignal,
    InstitutionSignal,
    CompanyRolePair,
    DimensionDistinction,
    KBInsight,
)


def test_strategy_type_enum_values() -> None:
    """6 大策略大类必须齐全 (spec §4.1)。"""
    expected = {
        "基本面权益",
        "量化",
        "固定收益",
        "卖方研究",
        "多资产_FOF_衍生品",
        "相关补充",
    }
    assert {s.value for s in StrategyType} == expected


def test_kb_insight_type_enum_values() -> None:
    """5 类 KB insight 必须齐全 (复用 Pony schema)。"""
    expected = {"role", "interview", "company", "resume", "industry"}
    assert {t.value for t in KBInsightType} == expected


def test_dual_schema_minimal_valid() -> None:
    """空字段帖也能构建 (例如全是噪声的低 relevance 帖)。"""
    extract = DualSchemaExtract(
        post_id="abc123",
        url="https://xhs.com/n/abc123",
        time="2026-05-01T12:00:00",
        author="user1",
        relevance_score=0.1,
        taxonomy=PostTaxonomyExtract(),
        kb=PostKBExtract(),
    )
    assert extract.relevance_score == 0.1
    assert extract.taxonomy.strategy_signals == []
    assert extract.kb.insights == []


def test_dual_schema_full_round_trip() -> None:
    """完整 schema 序列化/反序列化不丢字段。"""
    extract = DualSchemaExtract(
        post_id="abc123",
        url="https://xhs.com/n/abc123",
        time="2026-05-01T12:00:00",
        author="user1",
        relevance_score=0.85,
        taxonomy=PostTaxonomyExtract(
            strategy_signals=[
                StrategySignal(canonical=StrategyType.基本面权益, verbatim_phrase="消费组研究员"),
            ],
            industry_signals=[IndustrySignal(industry="消费", verbatim_phrase="白酒")],
            institution_signals=[
                InstitutionSignal(tier_guess="一线公募", company_name="嘉实基金", verbatim="嘉实消费组"),
            ],
            discovered_sub_categories=["消费组", "白酒研究"],
            company_role_pairs=[
                CompanyRolePair(company="嘉实基金", role_or_dept="消费组研究员", strategy="基本面权益"),
            ],
            dimension_distinctions=[
                DimensionDistinction(axis="institution_tier", x_vs_y="公募 vs 资管子", note="文化差异"),
            ],
        ),
        kb=PostKBExtract(
            insights=[
                KBInsight(
                    type=KBInsightType.company,
                    text="嘉实消费组带新人方式",
                    verbatim_quote="嘉实消费组带新人的方式跟易方达类似",
                    confidence="high",
                ),
            ],
        ),
    )
    j = extract.model_dump_json()
    re = DualSchemaExtract.model_validate_json(j)
    assert re.taxonomy.strategy_signals[0].canonical == StrategyType.基本面权益
    assert re.kb.insights[0].type == KBInsightType.company


def test_relevance_score_bounds() -> None:
    """relevance_score 必须在 [0, 1]。"""
    with pytest.raises(ValidationError):
        DualSchemaExtract(
            post_id="x", url="x", time="x", author="x",
            relevance_score=1.5,
            taxonomy=PostTaxonomyExtract(),
            kb=PostKBExtract(),
        )
