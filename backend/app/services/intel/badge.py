"""三维合成 → 徽章 ★数。原则：交叉验证 > 亲历层级 > 单条信源分。"""
from __future__ import annotations


def synth_badge(*, source_score: float, content_tier: str, cross: str, n: int = 1) -> int:
    if cross == "verified":
        return 3
    if content_tier == "high" or (n or 1) >= 3 or (source_score or 0) >= 0.6:
        return 2
    return 1
