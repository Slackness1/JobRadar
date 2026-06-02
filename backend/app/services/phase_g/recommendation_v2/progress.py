"""推荐渐进式回调包：dispatcher 在各阶段回吐进度/部分结果，workflow 落库。

默认全部 no-op —— 不传 progress 时（单测 / v1 路径 / 其它 caller）行为字节不变。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas_resume_copilot import ResumeRecommendationItem


@dataclass
class RecommendProgress:
    # 召回完成：命中候选数
    on_recall: Callable[[int], None] = field(default=lambda n: None)
    # 规则排序完成：rule-ranked 部分结果（精排前先给前端铺列表）
    on_ranked: Callable[[list["ResumeRecommendationItem"]], None] = field(default=lambda items: None)
    # 每完成一个精排：已完成数 / 总数 / 该岗一句真推理
    on_rerank_one: Callable[[int, int, str], None] = field(default=lambda done, total, reason: None)
    # 每完成一条理由：已完成数 / 总数
    on_narrative_one: Callable[[int, int], None] = field(default=lambda done, total: None)
