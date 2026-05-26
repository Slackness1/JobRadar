"""测 saturation 指标 — 各 strategy 大类的阈值 + 饱和判定逻辑。"""
from __future__ import annotations

import pytest

from app.services.taxonomy_discovery.saturation import (
    SaturationConfig,
    SaturationState,
    SaturationStatus,
    check_saturation,
    config_for_strategy,
)


def test_config_for_top_weight() -> None:
    """基本面权益 (顶配) sub_cat_target=6, company_target=15, max_posts=1500。"""
    c = config_for_strategy("基本面权益")
    assert c.sub_cat_target == 6
    assert c.sub_cat_min_mentions == 10
    assert c.company_target == 15
    assert c.company_min_mentions == 5
    assert c.min_posts == 200
    assert c.max_posts == 1500


def test_config_for_low_weight() -> None:
    c = config_for_strategy("多资产_FOF_衍生品")
    assert c.sub_cat_target == 1
    assert c.max_posts == 200


def test_status_continue_below_minimum() -> None:
    """爬不够 min_posts 时永远不停。"""
    c = config_for_strategy("基本面权益")
    state = SaturationState(
        posts_crawled=50,
        unique_sub_cats_with_mentions={"消费组": 10, "TMT组": 8},
        unique_companies_with_mentions={"嘉实基金": 5},
        last_3_batches_new_items=[5, 4, 3],
    )
    assert check_saturation(state, c) == SaturationStatus.CONTINUE


def test_status_saturated_when_thresholds_met(top_config: SaturationConfig) -> None:
    """达标且最近 3 batch 无新东西 → SATURATED。"""
    state = SaturationState(
        posts_crawled=600,
        unique_sub_cats_with_mentions={f"cat{i}": 12 for i in range(6)},
        unique_companies_with_mentions={f"co{i}": 6 for i in range(15)},
        last_3_batches_new_items=[0, 0, 0],
    )
    assert check_saturation(state, top_config) == SaturationStatus.SATURATED


def test_status_scarce_when_signal_dries_up(top_config: SaturationConfig) -> None:
    """连续 3 batch insight 总数 < 5 → SCARCE。"""
    state = SaturationState(
        posts_crawled=250,
        unique_sub_cats_with_mentions={"消费组": 5},
        unique_companies_with_mentions={"嘉实基金": 3},
        last_3_batches_new_items=[1, 1, 1],
        last_3_batches_total_insights=[2, 1, 1],
    )
    assert check_saturation(state, top_config) == SaturationStatus.SCARCE


def test_status_ceiling_at_hard_max(top_config: SaturationConfig) -> None:
    state = SaturationState(
        posts_crawled=1500,
        unique_sub_cats_with_mentions={"消费组": 5},
        unique_companies_with_mentions={"嘉实基金": 3},
        last_3_batches_new_items=[1, 1, 1],
    )
    assert check_saturation(state, top_config) == SaturationStatus.CEILING


@pytest.fixture
def top_config() -> SaturationConfig:
    return config_for_strategy("基本面权益")
