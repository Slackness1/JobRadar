"""测 seed query 清单 — 必须 6 大策略都有, 关键词非空, 候选博主有 25 个。"""
from __future__ import annotations

import pytest

from app.services.taxonomy_discovery.seed_queries import (
    CANDIDATE_BLOGGERS,
    seed_keywords_for_strategy,
    same_company_angles,
)


def test_all_6_strategies_have_seeds() -> None:
    for strategy in [
        "基本面权益", "量化", "固定收益", "卖方研究",
        "多资产_FOF_衍生品", "相关补充",
    ]:
        seeds = seed_keywords_for_strategy(strategy)
        assert len(seeds) >= 5, f"{strategy} seed 不足 5: {seeds}"
        # 关键词不能完全重复
        assert len(set(seeds)) == len(seeds)


@pytest.mark.xfail(reason="待 user 补全 25 候选博主 list", strict=False)
def test_candidate_bloggers_count() -> None:
    """25 个候选博主 (Pony 之前发现的 7 tier1 + 18 tier2 + Pony 自己)。"""
    assert len(CANDIDATE_BLOGGERS) >= 25
    # Pony 必须在 list 里
    pony = [b for b in CANDIDATE_BLOGGERS if "pony" in b["uid"].lower() or "Pony" in b["name"]]
    assert len(pony) >= 1


def test_same_company_angles() -> None:
    """同公司 5 视角 query 模板。"""
    angles = same_company_angles("嘉实基金")
    assert len(angles) == 5
    assert "嘉实基金 面试" in angles
    assert "嘉实基金 实习" in angles
