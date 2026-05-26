"""Saturation 指标 + 配置 (spec §4.3)。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SaturationStatus(str, Enum):
    CONTINUE = "continue"
    SATURATED = "saturated"
    SCARCE = "scarce"
    CEILING = "ceiling"


@dataclass
class SaturationConfig:
    sub_cat_target: int
    sub_cat_min_mentions: int
    company_target: int
    company_min_mentions: int
    min_posts: int
    max_posts: int


@dataclass
class SaturationState:
    posts_crawled: int
    unique_sub_cats_with_mentions: dict[str, int]
    unique_companies_with_mentions: dict[str, int]
    last_3_batches_new_items: list[int] = field(default_factory=list)  # 每 batch 新出现的 sub_cat+company 数
    last_3_batches_total_insights: list[int] = field(default_factory=list)


_CONFIGS: dict[str, SaturationConfig] = {
    "基本面权益": SaturationConfig(6, 10, 15, 5, 200, 1500),
    "量化": SaturationConfig(4, 8, 10, 5, 100, 800),
    "固定收益": SaturationConfig(3, 5, 6, 3, 60, 500),
    "卖方研究": SaturationConfig(4, 5, 5, 5, 60, 500),
    "多资产_FOF_衍生品": SaturationConfig(1, 5, 3, 3, 20, 200),
    "相关补充": SaturationConfig(1, 2, 2, 2, 10, 100),
}


def config_for_strategy(strategy: str) -> SaturationConfig:
    if strategy not in _CONFIGS:
        raise KeyError(f"未知 strategy: {strategy!r}, 可选 {list(_CONFIGS)}")
    return _CONFIGS[strategy]


def check_saturation(state: SaturationState, config: SaturationConfig) -> SaturationStatus:
    if state.posts_crawled >= config.max_posts:
        return SaturationStatus.CEILING

    if state.posts_crawled < config.min_posts:
        return SaturationStatus.CONTINUE

    # 内容稀缺: 连续 3 batch insight 总和 < 5
    if (len(state.last_3_batches_total_insights) >= 3
            and sum(state.last_3_batches_total_insights[-3:]) < 5):
        return SaturationStatus.SCARCE

    # 达标判定
    qualified_sub_cats = sum(
        1 for n in state.unique_sub_cats_with_mentions.values()
        if n >= config.sub_cat_min_mentions
    )
    qualified_companies = sum(
        1 for n in state.unique_companies_with_mentions.values()
        if n >= config.company_min_mentions
    )
    no_recent_growth = (
        len(state.last_3_batches_new_items) >= 3
        and sum(state.last_3_batches_new_items[-3:]) == 0
    )

    if (qualified_sub_cats >= config.sub_cat_target
            and qualified_companies >= config.company_target
            and no_recent_growth):
        return SaturationStatus.SATURATED

    return SaturationStatus.CONTINUE
