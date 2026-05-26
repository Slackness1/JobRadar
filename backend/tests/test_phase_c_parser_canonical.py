"""Phase C (2026-05-16): 钉死 parser inferred_tracks 自动 canonicalize 契约。

LLM extract 和 heuristic fallback 两条路都必须把 inferred_tracks 跑过
canonicalize_track。不在 13 canonical 的值(e.g. '互联网' 是 tech 不是 finance)
要保留原值,不丢。
"""
from __future__ import annotations

from app.services.resume_copilot.parser import _canonicalize_track_list


def test_canonical_alias_maps_to_canonical() -> None:
    """命中 alias 的就映 canonical。"""
    assert _canonicalize_track_list(['公募基金']) == ['公募/资管·投研']
    # PE/IBD 现已拆: PE → 一级股权·PE/VC; IBD → 投行·并购·资本市场, dedupe 后 2 个
    assert _canonicalize_track_list(['PE', 'IBD']) == ['一级股权·PE/VC', '投行·并购·资本市场']
    assert _canonicalize_track_list(['Quant', '量化']) == ['量化']
    # 2026-05-23: 13 canon 重构 — 管理咨询·MBB + 战略咨询 → 咨询·MBB+Tier2
    assert _canonicalize_track_list(['麦肯锡', '四大']) == ['咨询·MBB+Tier2']


def test_unmapped_pass_through() -> None:
    """非 alias / 未识别的 free-text 保留原值,不丢字段。"""
    # 2026-05-22: 原 case 用 'Finance'/'生物医药' — 但这俩都被 alias 反向命中,
    # 换 truly non-finance 字符串测 pass-through 契约。
    out = _canonicalize_track_list(['AI 工程师', '元宇宙游戏'])
    assert 'AI 工程师' in out
    assert '元宇宙游戏' in out


def test_dedupe_preserves_order() -> None:
    """多个 alias 都映同一个 canonical 时 dedupe;顺序按首次出现。"""
    # 2026-05-23: PE → 一级股权·PE/VC; 老 canon '二级买方·基本面' (backward-compat) → 公募/资管·投研
    assert _canonicalize_track_list(['PE', '二级买方·基本面', 'VC']) == ['一级股权·PE/VC', '公募/资管·投研']


def test_empty_and_falsy_filtered() -> None:
    """空 / None 跳过。空白字符串保留(留给上游 trim)。"""
    assert _canonicalize_track_list([]) == []
    # None 在 list 里 — `if not v` 跳过
    assert _canonicalize_track_list(['', None]) == []  # type: ignore[list-item]


def test_mixed_canonical_and_legacy() -> None:
    """LLM 可能同时返回 canonical 串 + alias + 真正 unmapped free-text,都要 dedupe 且不丢。"""
    out = _canonicalize_track_list(['公募基金', '元宇宙游戏', '量化'])
    assert out == ['公募/资管·投研', '元宇宙游戏', '量化']
