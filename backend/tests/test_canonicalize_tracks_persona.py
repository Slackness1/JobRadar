"""8 个 SAIF MF 学生画像 (P1-P8) 的 inferred_tracks 期望 canonical 映射。
2026-05-23 重写: 适配新 13 canonical (拆 二级买方 / 卖方·S&T / 一级市场, 拆 咨询)。

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
# Comment 形式: "<规则>: <为什么 expected 是这个>"
PERSONA_CANONICAL_CASES: list[tuple[str, str, str, str]] = [
    # ── P1 公募/资管·投研 (公募行研) ────────────────────────────────────────
    ('P1', '头部公募行研', '公募/资管·投研', '公募 / 行研 双重命中'),
    ('P1', '外资行研究部', '卖方研究',
        '"外资行研究" (5字) 长于 "外资行" (3) — 不应被 "外资行" 抢去 银行'),
    ('P1', '头部私募研究员', '私募·基本面',
        '2026-05-23 重构: 私募 系列已独立成 私募·基本面 canon (从老 二级买方·基本面 拆出)'),

    # ── P2 卖方研究 (TMT) ─────────────────────────────────────────────────
    ('P2', '头部券商研究所 TMT', '卖方研究',
        '"券商研究所" (5字) 长于 "TMT" (3字) — 走新 canon "卖方研究"'),
    ('P2', '外资行研究部 TMT', '卖方研究',
        '"外资行研究" (5字) 长于 "外资行" (3) / "TMT" (3)'),
    ('P2', '公募 TMT 行研', '公募/资管·投研',
        '"公募" / "TMT" / "行研" 全 → 公募/资管·投研 (子行业映射默认 buy-side)'),

    # ── P3 私募 / 资管 (公募 + 私募 各自归位) ──────────────────────────────
    ('P3', '头部私募研究员', '私募·基本面', '"私募研究员" (5字) 命中 → 私募·基本面'),
    ('P3', '中型公募行研', '公募/资管·投研', '公募 / 行研 命中'),
    ('P3', '资管子公司行研', '公募/资管·投研', '资管 / 行研 命中'),

    # ── P4 银行管培 / 综合金融 ───────────────────────────────────────────
    ('P4', '股份行管培', '银行·总行核心', '"股份行" (3) + "管培" (2) 命中'),
    ('P4', '国有大行总行管培', '银行·总行核心', '"国有大行" / "总行管培" / "总行" 等多发命中'),
    ('P4', '券商综合金融', '银行·总行核心',
        '"综合金融" (4) 命中 — SAIF placement 口径默认 银行 而非 投行'),

    # ── P5 投行·并购·资本市场 (从老 一级市场 拆出, IBD 端) ─────────────────
    ('P5', '内资头部投行 IBD', '投行·并购·资本市场',
        'IBD / 投行 命中 → 新 canon 投行·并购·资本市场'),
    ('P5', '外资投行 IBD', '投行·并购·资本市场', '外资投行 / IBD 命中'),
    ('P5', '外资投行 GBM', '投行·并购·资本市场',
        '"外资投行" (4) 长于 "GBM" (3) — 主轨 IBD 仍 ✓; '
        '副作用: GBM 应 S&T·FICC·衍生品 但 "外资投行" 抢先, 影响小'),

    # ── P6 量化 / 对冲 (2026-05-23 对冲基金搬到 私募·基本面) ──────────────
    ('P6', '头部量化私募', '量化',
        '"量化私募" (4) 长于 "私募" (2) — longest-match-wins, 走 量化'),
    ('P6', '外资对冲基金', '私募·基本面',
        '2026-05-23 alias 重构: "对冲基金" 从老 二级买方·基本面 搬到 私募·基本面'),
    ('P6', '公募量化部', '量化', '"公募量化" (4) 命中 — 不被 "公募" 抢'),

    # ── P7 金融科技 ───────────────────────────────────────────────────────
    ('P7', '互联网金融科技', '金融科技', '"互联网金融" (5) > "金融科技" (4); 都 → 金融科技'),
    ('P7', '银行金融科技子公司', '金融科技',
        '"金融科技子公司" (7) 长于 "银行" (2) — 不被 "银行" 抢去 银行·总行'),
    ('P7', '券商金融科技部', '金融科技', '"金融科技部" (5) > "金融科技" (4) — explicit phrase'),

    # ── P8 大宗·能源 (跨专业, 已知 minor 错路保留) ─────────────────────────
    ('P8', '券商大宗商品研究', '大宗·能源', '大宗商品 / 大宗 命中'),
    ('P8', '期货公司研究所', '卖方研究',
        '"研究所" (3) 命中 — 业务上期货研究所确属 sell-side research (改名后 卖方研究)'),
    ('P8', '能源公司战略', '企业战略·管培·实业金融',
        '已知 minor 错路: "公司战略" (4) > "能源" (2). 走 2026-05-23 新拆出的 '
        '企业战略·管培·实业金融 (老叫 战略咨询); 主轨 大宗·能源 由 case 1/3 命中'),
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


# 量化信号共现 — 当 label 同时含"明确量化词"(量化/quant/alpha/因子/高频/做市)
# 与"组织词"(私募/对冲基金)时, 量化意图必须压过组织词, 走 量化。
# 这是真实量化学生的自述方式 ("量化私募 / 对冲基金 (中频 + alpha 因子)")。
# 边界: 不含量化词的 "对冲基金" 单独出现仍 → 私募·基本面 (2026-05-23 设计, 见上 P6 case)。
QUANT_COOCCUR_CASES: list[tuple[str, str, str]] = [
    ('量化私募 / 对冲基金 (中频策略 + alpha 因子)', '量化',
        '量化私募 与 对冲基金 同长, 量化信号(量化/alpha/因子)应压过组织词'),
    ('私募量化', '量化', '"私募"(2) 与 "量化"(2) 同长 — 含量化词, 走 量化'),
    ('量化对冲基金', '量化', '含 "量化" — 不被 "对冲基金" 抢去 私募'),
    ('alpha 因子对冲', '量化', 'alpha / 因子 量化信号'),
    ('高频做市私募', '量化', '高频 / 做市 量化信号压过 私募'),
    # 反向守护: 不含量化词的组织词保持原映射, 不被误升为 量化。
    ('外资对冲基金', '私募·基本面', '无量化词 — 保持 2026-05-23 设计 → 私募·基本面'),
    ('头部私募研究员', '私募·基本面', '无量化词 — 基本面私募保持 私募·基本面'),
]


@pytest.mark.parametrize(
    'raw,expected,comment',
    QUANT_COOCCUR_CASES,
    ids=lambda v: str(v)[:50],
)
def test_quant_signal_overrides_org_word(
    raw: str, expected: str, comment: str,
) -> None:
    """量化信号词共现时压过 私募/对冲基金 组织词."""
    actual = canonicalize_track(raw)
    assert actual == expected, (
        f'\n  raw={raw!r}\n  expected={expected!r}'
        f'\n  actual={actual!r}\n  comment: {comment}'
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
