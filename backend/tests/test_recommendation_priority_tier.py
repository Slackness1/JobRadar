"""Priority Letter + Tier Label 单元测试。

覆盖:
  - _track_kind_to_tier_label 4 个分支 (hit/null_hit/transferable/ambiguous/mismatch/no_pref)
  - _compute_priority_letter 4 档 (A/B/C/D) × 3 类品牌 (top/mid) × 2 类红线
"""
from __future__ import annotations

import pytest

from app.services.resume_copilot.recommendation import (
    _compute_priority_letter,
    _track_kind_to_tier_label,
)


class TestTrackKindToTierLabel:
    @pytest.mark.parametrize("kind,expected", [
        ('hit', '强匹配'),
        ('null_hit', '强匹配'),
        ('transferable', '可迁移'),
        ('ambiguous', '可迁移'),
        ('mismatch', '有差距'),
        ('no_pref', ''),
    ])
    def test_映射(self, kind, expected):
        assert _track_kind_to_tier_label(kind, None) == expected

    def test_低质量红线优先于track分类(self):
        assert _track_kind_to_tier_label('hit', '柜员') == '有差距'
        assert _track_kind_to_tier_label('transferable', '理财经理') == '有差距'


class TestComputePriorityLetter:
    def test_A_强匹配_顶级品牌_高分(self):
        # 阈值放宽到 80 (2026-05-19 实测分布校准)
        assert _compute_priority_letter('hit', 90, 'securities:tier1', None) == 'A'
        assert _compute_priority_letter('null_hit', 88, 'bank:tier1', None) == 'A'
        assert _compute_priority_letter('hit', 80, 'funds:tier1', None) == 'A'

    def test_B_强匹配_顶级品牌_分数边界以下(self):
        # final<80 但 ≥65 = B
        assert _compute_priority_letter('hit', 75, 'securities:tier1', None) == 'B'

    def test_B_强匹配_中型品牌(self):
        # 不是顶级品牌,即使强匹配也是 B
        assert _compute_priority_letter('hit', 90, 'securities:tier2', None) == 'B'

    def test_B_可迁移_顶级品牌(self):
        assert _compute_priority_letter('transferable', 70, 'bank:tier1', None) == 'B'

    def test_C_强匹配_低分(self):
        # 60 仍 ≥ D 阈值 50 → C (新加 D 兜底:final<50 → D)
        assert _compute_priority_letter('hit', 60, 'securities:tier1', None) == 'C'

    def test_D_强匹配但final过低(self):
        # 新增:无明显错位但 final<50 强制 D 兜底
        assert _compute_priority_letter('hit', 40, 'securities:tier1', None) == 'D'
        assert _compute_priority_letter('hit', 30, 'funds:tier1', None) == 'D'

    def test_C_可迁移_中型品牌(self):
        assert _compute_priority_letter('transferable', 80, 'bank:tier2', None) == 'C'
        assert _compute_priority_letter('transferable', 80, '', None) == 'C'

    def test_C_ambiguous_任意条件(self):
        assert _compute_priority_letter('ambiguous', 90, 'securities:tier1', None) == 'C'

    def test_D_错位(self):
        assert _compute_priority_letter('mismatch', 90, 'securities:tier1', None) == 'D'

    def test_D_红线命中(self):
        # 不管什么 track,红线就是 D
        assert _compute_priority_letter('hit', 95, 'securities:tier1', '柜员') == 'D'
        assert _compute_priority_letter('transferable', 85, 'bank:tier1', '理财经理') == 'D'

    def test_no_pref_退化到分数加品牌(self):
        # no_pref + 顶级品牌 + 高分 → A
        assert _compute_priority_letter('no_pref', 90, 'funds:tier1', None) == 'A'
        # no_pref + 中型 + 中分 → B
        assert _compute_priority_letter('no_pref', 75, 'bank:tier2', None) == 'B'
        # no_pref + 低分 → C
        assert _compute_priority_letter('no_pref', 50, '', None) == 'C'

    def test_tier_大小写兼容(self):
        # 旧 t0/t0.5 命名也算顶级
        assert _compute_priority_letter('hit', 90, 'T0', None) == 'A'
        assert _compute_priority_letter('hit', 90, 't0.5', None) == 'A'
