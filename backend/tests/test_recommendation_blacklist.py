"""低质量岗位红线词单元测试 — 把 _is_low_quality_role 的契约钉死,
防后面有人乱动 _LOW_QUALITY_ROLE_PATTERNS 把现网推荐打坏。

设计依据: docs/finance-tracks-2026-overview.md "红线" 段 +
2026-05-16 在真实 91465 行 jobs 表上的扫描 + 抽样验证。
"""
from __future__ import annotations

import pytest

from app.services.resume_copilot.recommendation import (
    _LOW_QUALITY_PENALTY,
    _LOW_QUALITY_ROLE_PATTERNS,
    _is_low_quality_role,
)


# (job_title, expected_matched_pattern) — 必须命中
SHOULD_FLAG: list[tuple[str, str]] = [
    ('柜员（建行深圳分行）', '柜员'),
    ('招行远程客户经理', '远程客户经理'),
    ('财富顾问 · 上海营业部', '财富顾问'),
    ('寿险销售代理人', '寿险销售'),
    ('渠道销售 · 公募基金', '渠道销售'),
    ('保险代理人 · 平安', '保险代理'),
    ('理财经理 · 招行支行', '理财经理'),
    ('远程客户经理', '远程客户经理'),
    ('SHEIN · 资深 KOL 营销专员', '营销专员'),
    ('客服代表岗（传统客服方向）', '客服'),
    ('综合营销岗', '营销岗'),
    ('零售客户经理（劳务派遣）', '零售客户经理'),
    ('柜面服务岗', '柜面服务'),
    ('保险顾问 · 太保', '保险顾问'),
    ('FOF销售 · 上海', 'FOF销售'),
    ('美团 · 火石业务中心-深圳-高级产品销售', '产品销售'),
    ('合肥分行运营培训生(综合柜员方向)', '柜员'),
    ('代理人招募 · 中国人寿', '代理人'),
]

# 必须**不**命中 — 误杀关键卡
SHOULD_PASS: list[str] = [
    '行业研究员（消费方向）· 公募基金',
    '量化研究员（中低频）',
    '总行投行部 Analyst',
    '基本面研究员 · 高毅资产',
    'IBD Analyst · 中金',
    '客户经理 · 工行深圳',                 # 单独"客户经理"不触发(歧义,可能是机构对公)
    '机构客户经理 · 中信证券对公',          # 同上
    '产品经理 · 财富科技',                 # "产品"没"产品销售",不触发
    '资管产品经理 · 国联证券',              # 同上
    'PE 投资分析师 · 高瓴',
    'M&A Analyst · 中金 IBD',
    '财富管理 · 私行专户投资经理',          # "财富"≠"财富顾问"
]


@pytest.mark.parametrize('title,expected', SHOULD_FLAG, ids=lambda v: str(v)[:40])
def test_low_quality_role_hits(title: str, expected: str) -> None:
    """命中黑名单 — 返回的具体 pattern 必须等于 expected。"""
    assert _is_low_quality_role(title) == expected


@pytest.mark.parametrize('title', SHOULD_PASS, ids=lambda v: v[:40])
def test_low_quality_role_misses(title: str) -> None:
    """正常岗位 — 必须返 None,不能误杀。"""
    assert _is_low_quality_role(title) is None


def test_patterns_no_duplicates() -> None:
    """防意外重复(改 pattern list 时容易复制粘错)。"""
    assert len(_LOW_QUALITY_ROLE_PATTERNS) == len(set(_LOW_QUALITY_ROLE_PATTERNS))


def test_patterns_not_empty() -> None:
    """空 pattern 直接误大量,显式 guard。"""
    for p in _LOW_QUALITY_ROLE_PATTERNS:
        assert p and len(p) >= 2, f'空/过短 pattern: {p!r}'


def test_empty_input() -> None:
    """边界: 空字符串 / None 必须不抛、返 None。"""
    assert _is_low_quality_role('') is None
    assert _is_low_quality_role(None) is None  # type: ignore[arg-type]


def test_penalty_value_sanity() -> None:
    """_LOW_QUALITY_PENALTY 应当足够大,把命中行拉到正常 score 之下。

    现网正常 SAIF 投研岗 final_score 大致 50-80; 改 penalty 太小(<30) 起不了
    作用, 太大(>200) 会让 risks 顺位漂移到极端. 留个区间防呆。"""
    assert 30 <= _LOW_QUALITY_PENALTY <= 200


def test_no_bare_customer_manager_in_patterns() -> None:
    """显式断言: 单独"客户经理"**不**在 pattern 里 — 它太歧义 (可能是机构对公)
    会大量误杀. 必须始终带限定词(远程/零售/网点/个人)。"""
    assert '客户经理' not in _LOW_QUALITY_ROLE_PATTERNS, \
        '不要单独加"客户经理"到红线 — 歧义太大会误杀机构客户经理'
