"""Phase C (2026-05-16): 钉死 parser inferred_tracks 自动 canonicalize 契约。

LLM extract 和 heuristic fallback 两条路都必须把 inferred_tracks 跑过
canonicalize_track。不在 8 canonical 的值(e.g. '互联网' 是 tech 不是 finance)
要保留原值,不丢。
"""
from __future__ import annotations

from app.services.resume_copilot.parser import _canonicalize_track_list


def test_canonical_alias_maps_to_canonical() -> None:
    """命中 alias 的就映 canonical。"""
    assert _canonicalize_track_list(['公募基金']) == ['二级买方·基本面']
    assert _canonicalize_track_list(['PE', 'IBD']) == ['一级市场']  # 都映 一级市场,dedupe
    assert _canonicalize_track_list(['Quant', '量化']) == ['量化']
    assert _canonicalize_track_list(['麦肯锡', '四大']) == ['金融咨询']


def test_unmapped_pass_through() -> None:
    """非 alias / 未识别的 free-text 保留原值,不丢字段。"""
    out = _canonicalize_track_list(['Finance', '生物医药'])
    assert 'Finance' in out
    assert '生物医药' in out


def test_dedupe_preserves_order() -> None:
    """多个 alias 都映同一个 canonical 时 dedupe;顺序按首次出现。"""
    assert _canonicalize_track_list(['PE', '二级买方·基本面', 'VC']) == ['一级市场', '二级买方·基本面']


def test_empty_and_falsy_filtered() -> None:
    """空 / None 跳过。空白字符串保留(留给上游 trim)。"""
    assert _canonicalize_track_list([]) == []
    # None 在 list 里 — `if not v` 跳过
    assert _canonicalize_track_list(['', None]) == []  # type: ignore[list-item]


def test_mixed_canonical_and_legacy() -> None:
    """LLM 可能同时返回 canonical 串 + alias + 真正 unmapped free-text,都要 dedupe 且不丢。"""
    out = _canonicalize_track_list(['公募基金', '生物医药', '量化'])
    assert out == ['二级买方·基本面', '生物医药', '量化']
