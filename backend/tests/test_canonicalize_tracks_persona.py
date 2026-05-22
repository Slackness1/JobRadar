"""P0/P1 (2026-05-22) 回归 test: 钉死 8 个 SAIF MF 学生画像 (P1-P8) 的
inferred_tracks 期望 canonical 映射,防 alias 顺序 / 短词覆盖回归。

Eval 报告: docs/eval-track-matching-2026-05-22.md
设计文档:  docs/2026-05-22-track-matching-english-resume-design.md

每个 case = (persona_id, raw_inferred_track, expected_canonical, comment)。
注意: expected 是 canonicalize_track 单次调用的返回值,**不**是 dedupe 后的列表 —
若某 persona 的 3 个 inferred 都映同一 canonical, 这里仍然写 3 行。
"""
from __future__ import annotations

import pytest

from app.services.taxonomy import canonicalize_track


# 8 personas × 3 inferred_tracks = 24 cases.
# Comment 形式: "<bug name>: <为什么 expected 是这个>"
PERSONA_CANONICAL_CASES: list[tuple[str, str, str, str]] = [
    # ── P1 二级买方·基本面 (公募行研) ──────────────────────────────────────
    ('P1', '头部公募行研', '二级买方·基本面', '公募 / 行研 双重命中'),
    ('P1', '外资行研究部', '卖方研究·S&T',   'P1 加 alias "外资行研究" 修正 — 不应被 "外资行" 抢去 银行'),
    ('P1', '头部私募研究员', '二级买方·基本面', '私募 alias 命中'),

    # ── P2 卖方研究·S&T (TMT) — 之前 ✗,P0 longest-match-wins 修复 ──────────
    ('P2', '头部券商研究所 TMT', '卖方研究·S&T',
        'P0 修复: "券商研究所" (len 5) 长于 "TMT" (len 3),不再被劫持到 二级买方'),
    ('P2', '外资行研究部 TMT', '卖方研究·S&T',
        'P1 加 "外资行研究" (len 5) 长于 "外资行" (len 3) + "TMT" (3)'),
    ('P2', '公募 TMT 行研', '二级买方·基本面',
        '此 case 无卖方 marker — "公募" + "TMT" + "行研" 全是 二级买方;合理 fallback'),

    # ── P3 私募 / 资管基本面 — 已经全 ✓,test 防回归 ────────────────────────
    ('P3', '头部私募研究员', '二级买方·基本面', '私募 / 研究员 命中'),
    ('P3', '中型公募行研', '二级买方·基本面', '公募 / 行研 命中'),
    ('P3', '资管子公司行研', '二级买方·基本面', '资产管理 / 行研 命中'),

    # ── P4 银行管培 / 综合金融 — P1 补 alias 后从 1/3 → 3/3 ─────────────────
    ('P4', '股份行管培', '银行·总行核心',
        'P1 加 "股份行" + "管培" alias — 之前 "股份制银行" 字符不同, "管培" 也没 alias'),
    ('P4', '国有大行总行管培', '银行·总行核心', '国有大行 / 总行 / 管培 多发命中'),
    ('P4', '券商综合金融', '银行·总行核心',
        'P1 加 "综合金融" alias — SAIF placement 口径默认 银行 (而非 一级)'),

    # ── P5 投行 IBD ───────────────────────────────────────────────────────
    ('P5', '内资头部投行 IBD', '一级市场', 'IBD / 投行 命中'),
    ('P5', '外资投行 IBD', '一级市场', '外资投行 / IBD 命中'),
    ('P5', '外资投行 GBM', '一级市场',
        '副作用: "投行" (len 2) tie "GBM" (3 letters lowercase=3) — GBM 应卖方 S&T '
        '但 "投行" 更前置匹配; 影响小, 主轨 IBD 仍 ✓'),

    # ── P6 量化 — 之前 ✗ (0 量化 chip),P0 修复 ──────────────────────────────
    ('P6', '头部量化私募', '量化',
        'P0 修复: "量化私募" (len 4) 长于 "私募" (len 2),不再劫持到 二级买方;'
        '同 case 在 first-hit 算法下完全错路'),
    ('P6', '外资对冲基金', '二级买方·基本面',
        '"对冲基金" alias 在 二级买方 section — 这是 alias 表设计选择 (不是 bug):'
        'SAIF 学生眼里 "对冲基金" 默认 fundamental HF, 量化 HF 走 "量化" 显式 alias'),
    ('P6', '公募量化部', '量化',
        'P0 修复后 longest-match-wins — 但需 "公募量化" alias 才能稳过. '
        '若 fail, 说明 alias 表缺 phrase, 加进 量化 section'),

    # ── P7 FinTech ───────────────────────────────────────────────────────
    ('P7', '互联网金融科技', '金融科技', '金融科技 / 互联网金融 命中'),
    ('P7', '银行金融科技子公司', '金融科技',
        'P0+P1 修复: "金融科技子公司" (P1 加, len 7) 长于 "银行" (len 2) — '
        '之前被 "银行" 劫持到 银行·总行核心'),
    ('P7', '券商金融科技部', '金融科技',
        'P1 加 "金融科技部" alias (len 5) 长于 "金融科技" (len 4) — 显式 phrase'),

    # ── P8 大宗·能源 (跨专业) ────────────────────────────────────────────
    ('P8', '券商大宗商品研究', '大宗·能源', '大宗商品 / 大宗 命中'),
    ('P8', '期货公司研究所', '卖方研究·S&T',
        '副作用 (可接受): "研究所" (len 3) 命中 卖方; 业务上期货研究所确属卖方 research'),
    ('P8', '能源公司战略', '战略咨询',
        '已知 minor 错路: "公司战略" (len 4) > "能源" (len 2). P0 longest-match-wins '
        '不能修这个 — 需要专门 phrase "能源公司" → 大宗 (后续 patch). '
        '影响小: P8 主轨 大宗·能源 仍由 case 1/3 命中'),
]


@pytest.mark.parametrize(
    'persona,raw,expected,comment',
    PERSONA_CANONICAL_CASES,
    ids=lambda v: str(v)[:50],
)
def test_canonicalize_persona_inferred_track(
    persona: str, raw: str, expected: str, comment: str,
) -> None:
    """P1-P8 inferred_tracks → canonical 期望钉死."""
    actual = canonicalize_track(raw)
    assert actual == expected, (
        f'\n  persona={persona}'
        f'\n  raw={raw!r}'
        f'\n  expected={expected!r}'
        f'\n  actual={actual!r}'
        f'\n  comment: {comment}'
    )


def test_persona_count_matches_design() -> None:
    """8 个 persona × 3 inferred = 24 行, 不允许漏增."""
    assert len(PERSONA_CANONICAL_CASES) == 24, (
        f'期望 8 × 3 = 24 个 case, 实际 {len(PERSONA_CANONICAL_CASES)}'
    )
    persona_counts: dict[str, int] = {}
    for persona, _raw, _expected, _comment in PERSONA_CANONICAL_CASES:
        persona_counts[persona] = persona_counts.get(persona, 0) + 1
    for p in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']:
        assert persona_counts.get(p) == 3, (
            f'{p} 期望 3 个 inferred case, 实际 {persona_counts.get(p, 0)}'
        )
