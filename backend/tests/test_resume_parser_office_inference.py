"""P3 (2026-05-22) parser inferred_offices 推断契约。

测 heuristic `_infer_offices_from_resume_text` + `_normalize_offices` 两个新函数,
以及 heuristic profile builder 端到端把 inferred_offices 字段填出来。

设计文档: docs/2026-05-22-track-matching-english-resume-design.md (§ 8)
"""
from __future__ import annotations

import pytest

from app.services.resume_copilot.parser import (
    OFFICE_VALUES,
    _infer_offices_from_resume_text,
    _is_english_dominant_resume,
    _normalize_offices,
    build_heuristic_resume_profile,
)


# ── _is_english_dominant_resume ────────────────────────────────────────────


def test_english_dominant_pure_english() -> None:
    text = 'John Smith\nMcKinsey & Company\nLed strategic projects in Hong Kong office'
    assert _is_english_dominant_resume(text) is True


def test_english_dominant_pure_chinese() -> None:
    text = '张三 上海交通大学 高金硕士 中信证券实习'
    assert _is_english_dominant_resume(text) is False


def test_english_dominant_bilingual_chinese_heavy() -> None:
    """大段中文 + 少量英文技能词(典型 SAIF 中文简历)— 不算 English dominant。"""
    text = (
        '林思远 上海交通大学高级金融学院 金融硕士 中信证券研究所消费组实习'
        ' 易方达基金消费组研究助理 高瓴资本二级研究部 Python SQL Bloomberg'
    )
    assert _is_english_dominant_resume(text) is False


def test_english_dominant_empty() -> None:
    assert _is_english_dominant_resume('') is False


# ── _infer_offices_from_resume_text ────────────────────────────────────────


def test_infer_hk_from_hkust() -> None:
    text = 'Chen Si Yuan, HKUST MBA, summer intern at Citi Hong Kong'
    out = _infer_offices_from_resume_text(text)
    assert 'hk' in out


def test_infer_sg_from_nus() -> None:
    text = 'Lin Mei, NUS Master of Finance, summer intern at JPM Singapore'
    out = _infer_offices_from_resume_text(text)
    assert 'sg' in out


def test_infer_both_hk_and_mainland_for_mixed_signals() -> None:
    """清华本 + Goldman HK 实习 — 两个区域信号都应保留。"""
    text = '林思远 清华大学经济本科 SAIF MF 高盛香港暑期实习 Goldman Sachs Hong Kong'
    out = _infer_offices_from_resume_text(text)
    assert 'hk' in out
    assert 'mainland' in out


def test_infer_global_from_english_resume_without_specific_office() -> None:
    """纯英文简历 + 无港新院校 → global(求海外 mobility 信号)。"""
    text = (
        'John Smith, MIT BSc Economics, Master of Finance candidate. '
        'Goldman Sachs summer analyst, JPMorgan IBD experience. '
        'Open to cross-border placement.'
    )
    out = _infer_offices_from_resume_text(text)
    assert 'global' in out
    assert 'hk' not in out
    assert 'sg' not in out


def test_infer_empty_when_no_signal() -> None:
    """完全无信号(空 / 纯随机文本)→ 空数组, 不强制 fallback 到 mainland。"""
    assert _infer_offices_from_resume_text('') == []
    assert _infer_offices_from_resume_text('元宇宙游戏开发') == []


def test_infer_mainland_only_for_pure_mainland_resume() -> None:
    """清华 + 中信证券 → 只有 mainland, 不应误标 hk/sg/global。"""
    text = '张三 清华大学经济学院本科 中信证券研究所实习 上海交通大学高级金融学院硕士'
    out = _infer_offices_from_resume_text(text)
    assert out == ['mainland']


def test_infer_hk_does_not_default_global() -> None:
    """有 hk 明确信号时, 不应再加 global(意图明确就不要加噪音 chip)。"""
    text = 'Chen, HKUST BBA, Goldman Sachs Hong Kong summer analyst'
    out = _infer_offices_from_resume_text(text)
    assert 'hk' in out
    assert 'global' not in out


# ── _normalize_offices ──────────────────────────────────────────────────────


def test_normalize_accepts_canonical_values() -> None:
    assert _normalize_offices(['hk', 'sg']) == ['hk', 'sg']
    assert _normalize_offices(['mainland', 'global']) == ['mainland', 'global']


def test_normalize_aliases_mapped() -> None:
    """LLM 偶尔输出 'Hong Kong' / '新加坡' / '海外' 而不是 canonical 4 值。"""
    assert _normalize_offices(['Hong Kong', 'Singapore', 'China']) == ['hk', 'sg', 'mainland']
    assert _normalize_offices(['香港', '海外']) == ['hk', 'global']


def test_normalize_dedupes_and_filters_invalid() -> None:
    assert _normalize_offices(['hk', 'HK', 'foo', '']) == ['hk']
    assert _normalize_offices(['random', 'unknown']) == []


def test_normalize_empty_inputs() -> None:
    assert _normalize_offices(None) == []
    assert _normalize_offices([]) == []
    assert _normalize_offices('') == []


def test_normalize_accepts_string_input() -> None:
    assert _normalize_offices('hk') == ['hk']


# ── build_heuristic_resume_profile 端到端 ──────────────────────────────────


def test_heuristic_profile_populates_offices_for_hkust_student() -> None:
    """LLM 不在场时 (heuristic only),inferred_offices 字段应被填出来。"""
    resume = """
    Chen Si Yuan
    Email: chen.si.yuan@hkust.edu.hk

    教育背景
    HKUST MBA 2025
    Citi Hong Kong summer internship 2024

    技能
    Python, SQL, Bloomberg
    """
    profile = build_heuristic_resume_profile(resume)
    assert 'hk' in profile.inferred_offices


def test_heuristic_profile_offices_empty_for_no_signal_resume() -> None:
    resume = """
    技能
    元宇宙游戏开发
    """
    profile = build_heuristic_resume_profile(resume)
    assert profile.inferred_offices == []


def test_office_values_is_4_canonical() -> None:
    """钉死 4 个值, 防误增。"""
    assert OFFICE_VALUES == {'hk', 'sg', 'mainland', 'global'}


# ── _merge_profile_with_heuristics: LLM ∪ heuristic ───────────────────────


def test_merge_takes_union_of_llm_and_heuristic_offices() -> None:
    """LLM 给 hk, heuristic 算出 mainland — 应该 union 并去重。"""
    from app.services.resume_copilot.parser import _merge_profile_with_heuristics
    from app.schemas_resume_copilot import ResumeProfilePayload

    heuristic = ResumeProfilePayload(inferred_offices=['mainland'])
    raw_llm = {'inferred_offices': ['hk']}
    merged = _merge_profile_with_heuristics(raw_llm, heuristic)
    assert set(merged.inferred_offices) == {'hk', 'mainland'}


def test_merge_falls_back_to_heuristic_when_llm_missing_field() -> None:
    """LLM 不输出 inferred_offices — 整个 raw_dict 里没这个 key。"""
    from app.services.resume_copilot.parser import _merge_profile_with_heuristics
    from app.schemas_resume_copilot import ResumeProfilePayload

    heuristic = ResumeProfilePayload(inferred_offices=['sg'])
    raw_llm = {}  # 完全没 inferred_offices 字段
    merged = _merge_profile_with_heuristics(raw_llm, heuristic)
    assert merged.inferred_offices == ['sg']


def test_merge_handles_llm_giving_invalid_office_value() -> None:
    """LLM 出错给了 ['us', 'eu'] — 应该被 _normalize_offices 滤掉, 退到 heuristic。"""
    from app.services.resume_copilot.parser import _merge_profile_with_heuristics
    from app.schemas_resume_copilot import ResumeProfilePayload

    heuristic = ResumeProfilePayload(inferred_offices=['mainland'])
    raw_llm = {'inferred_offices': ['us', 'eu']}
    merged = _merge_profile_with_heuristics(raw_llm, heuristic)
    assert merged.inferred_offices == ['mainland']
