"""金融 taxonomy 单元测试 — 钉死低质量红线 + canonical 别名映射的契约,
防后面有人乱动 taxonomy 模块把现网推荐打坏。

设计依据: docs/finance-tracks-2026-overview.md "红线" 段 +
2026-05-16 在真实 91465 行 jobs 表上的扫描 + 抽样验证。

Phase A (2026-05-16): 这些符号从 recommendation.py 迁移到 app.services.taxonomy,
import 路径相应更新。
"""
from __future__ import annotations

import pytest

from app.services.taxonomy import (
    CANONICAL_FINANCE_TRACKS,
    LOW_QUALITY_PENALTY,
    LOW_QUALITY_ROLE_PATTERNS,
    canonicalize_track,
    is_low_quality_role,
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
    assert is_low_quality_role(title) == expected


@pytest.mark.parametrize('title', SHOULD_PASS, ids=lambda v: v[:40])
def test_low_quality_role_misses(title: str) -> None:
    """正常岗位 — 必须返 None,不能误杀。"""
    assert is_low_quality_role(title) is None


def test_patterns_no_duplicates() -> None:
    """防意外重复(改 pattern list 时容易复制粘错)。"""
    assert len(LOW_QUALITY_ROLE_PATTERNS) == len(set(LOW_QUALITY_ROLE_PATTERNS))


def test_patterns_not_empty() -> None:
    """空 pattern 直接误大量,显式 guard。"""
    for p in LOW_QUALITY_ROLE_PATTERNS:
        assert p and len(p) >= 2, f'空/过短 pattern: {p!r}'


def test_empty_input() -> None:
    """边界: 空字符串 / None 必须不抛、返 None。"""
    assert is_low_quality_role('') is None
    assert is_low_quality_role(None) is None  # type: ignore[arg-type]


def test_penalty_value_sanity() -> None:
    """LOW_QUALITY_PENALTY 应当足够大,把命中行拉到正常 score 之下。

    现网正常 SAIF 投研岗 final_score 大致 50-80; 改 penalty 太小(<30) 起不了
    作用, 太大(>200) 会让 risks 顺位漂移到极端. 留个区间防呆。"""
    assert 30 <= LOW_QUALITY_PENALTY <= 200


def test_no_bare_customer_manager_in_patterns() -> None:
    """显式断言: 单独"客户经理"**不**在 pattern 里 — 它太歧义 (可能是机构对公)
    会大量误杀. 必须始终带限定词(远程/零售/网点/个人)。"""
    assert '客户经理' not in LOW_QUALITY_ROLE_PATTERNS, \
        '不要单独加"客户经理"到红线 — 歧义太大会误杀机构客户经理'


# ── _canonicalize_track ────────────────────────────────────────────────────


TRACK_CANONICAL_CASES: list[tuple[str, str]] = [
    # 公募/资管·投研 (2026-05-23: 老 二级买方·基本面 拆出 long-only / 资管 端)
    ('公募基金', '公募/资管·投研'),
    ('公募基金/研究', '公募/资管·投研'),
    ('银行理财子', '公募/资管·投研'),
    ('保险资管', '公募/资管·投研'),
    # 私募·基本面 (2026-05-23 新拆出: 阳光私募 / hedge / 长短仓)
    ('阳光私募', '私募·基本面'),
    ('对冲基金', '私募·基本面'),
    # 量化
    ('量化', '量化'),
    ('quantitative research', '量化'),
    ('Quant', '量化'),
    # 投行·并购·资本市场 (2026-05-23 老 一级市场 拆出 IBD/M&A/ECM/DCM 端)
    ('IBD', '投行·并购·资本市场'),
    ('投行', '投行·并购·资本市场'),
    ('M&A', '投行·并购·资本市场'),
    # 一级股权·PE/VC (2026-05-23 老 一级市场 拆出 PE/VC 端)
    ('PE', '一级股权·PE/VC'),
    ('VC', '一级股权·PE/VC'),
    # 卖方研究 (2026-05-23 老 卖方研究·S&T 拆出 research 端)
    ('券商研究所', '卖方研究'),
    ('卖方研究', '卖方研究'),
    # S&T·FICC·衍生品 (2026-05-23 老 卖方研究·S&T 拆出 trading 端)
    ('S&T', 'S&T·FICC·衍生品'),
    ('FICC', 'S&T·FICC·衍生品'),
    # 银行
    ('银行总行', '银行·总行核心'),
    ('总行管培', '银行·总行核心'),
    # 监管体制
    ('证监会', '监管·体制内'),
    ('央行', '监管·体制内'),
    ('国央企', '监管·体制内'),
    # 金融科技
    ('蚂蚁', '金融科技'),
    ('Fintech', '金融科技'),
    ('跨境支付', '金融科技'),
    # 咨询·MBB+Tier2 (2026-05-23: 老 管理咨询·MBB + 战略咨询 合并)
    ('MBB', '咨询·MBB+Tier2'),
    ('麦肯锡', '咨询·MBB+Tier2'),
    ('四大', '咨询·MBB+Tier2'),
    # 企业战略·管培·实业金融 (2026-05-23 新拆出)
    ('字节战略', '企业战略·管培·实业金融'),
    ('corp dev', '企业战略·管培·实业金融'),
]


@pytest.mark.parametrize('raw,canon', TRACK_CANONICAL_CASES, ids=lambda v: str(v)[:30])
def test_canonicalize_track_hits(raw: str, canon: str) -> None:
    assert canonicalize_track(raw) == canon


def test_canonicalize_unmapped_returns_input() -> None:
    """映射不到 — 原样返回,不强制改 (避免误改用户自定义 track)。"""
    assert canonicalize_track('我自创的赛道') == '我自创的赛道'


def test_canonicalize_empty_input() -> None:
    assert canonicalize_track('') == ''
    assert canonicalize_track(None) == ''  # type: ignore[arg-type]


def test_canonical_tracks_no_duplicates() -> None:
    assert len(CANONICAL_FINANCE_TRACKS) == len(set(CANONICAL_FINANCE_TRACKS))


def test_canonical_tracks_count() -> None:
    """2026-05-23: 13 个 — 在 10 基础上拆 二级买方 / 卖方·S&T / 一级市场 各成 2,
    合 管理咨询·MBB + 战略咨询 再拆成 咨询·MBB+Tier2 + 企业战略·管培·实业金融。
    跟代码绑死防意外增删。"""
    assert len(CANONICAL_FINANCE_TRACKS) == 13
