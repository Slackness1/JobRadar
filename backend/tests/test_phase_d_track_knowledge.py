"""Phase D (2026-05-16): 钉死 TrackKnowledgeProvider + tracks.yaml schema 契约。

1) tracks.yaml 结构契约:8 entries / canonical 全在 CANONICAL_FINANCE_TRACKS /
   每条 entry 必须有 employers/roles/high_quality_signals/low_quality_signals/
   star_examples/followup_templates 字段。
2) Provider applies_to 判断准:purpose 不对 / 无 canonical 信号 → False;
   有 canonical signal → True。
3) Provider fetch 输出格式 + 内容:返非空 string,含 canonical 名,含
   typical_employers,含 STAR 字眼,含 follow-up 模板。
4) Resolve canonical 的优先级:preferences > profile > target_job > user_question。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import yaml
from pathlib import Path

from app.services.llm_context.base import (
    PURPOSE_CHAT,
    PURPOSE_INTERVIEW_QUESTION,
    PURPOSE_INTERVIEW_SCORE,
    PURPOSE_RERANK_JOB,
    ContextRequest,
)
from app.services.taxonomy import CANONICAL_FINANCE_TRACKS
from app.services.taxonomy.provider import TrackKnowledgeProvider, _TRACK_INDEX


_TRACKS_YAML = (
    Path(__file__).resolve().parents[1] / "app" / "services" / "taxonomy" / "tracks.yaml"
)


# ── yaml 结构契约 ──────────────────────────────────────────────────────


def test_tracks_yaml_has_all_8_canonical() -> None:
    data = yaml.safe_load(_TRACKS_YAML.read_text(encoding="utf-8"))
    canon_in_yaml = {t["canonical"] for t in data["tracks"]}
    assert canon_in_yaml == set(CANONICAL_FINANCE_TRACKS), (
        f"tracks.yaml 没覆盖所有 canonical。\n"
        f"missing: {set(CANONICAL_FINANCE_TRACKS) - canon_in_yaml}\n"
        f"extra: {canon_in_yaml - set(CANONICAL_FINANCE_TRACKS)}"
    )


_REQUIRED_FIELDS = (
    "typical_employers",
    "typical_roles",
    "high_quality_signals",
    "low_quality_signals",
    "star_examples",
    "followup_templates",
)


@pytest.mark.parametrize("canon", list(CANONICAL_FINANCE_TRACKS))
def test_track_entry_has_required_fields(canon: str) -> None:
    t = _TRACK_INDEX[canon]
    for f in _REQUIRED_FIELDS:
        assert f in t and t[f], f"canonical={canon!r} 缺字段 {f!r} 或字段空"
    # employers / roles / signals 不能过少
    assert len(t["typical_employers"]) >= 5, f"{canon} employers <5"
    assert len(t["high_quality_signals"]) >= 5, f"{canon} high_sig <5"


@pytest.mark.parametrize("canon", list(CANONICAL_FINANCE_TRACKS))
def test_star_examples_have_4_segments(canon: str) -> None:
    """STAR 必须是 context/task/action/result 4 段式。"""
    t = _TRACK_INDEX[canon]
    for i, s in enumerate(t["star_examples"]):
        for k in ("context", "task", "action", "result"):
            assert k in s and s[k], f"{canon} star_examples[{i}] 缺 {k!r}"


# ── Provider applies_to ─────────────────────────────────────────────────


def _mk_req(**kwargs) -> ContextRequest:
    db = MagicMock()
    defaults = dict(purpose=PURPOSE_CHAT, db=db, user_question="", target_job="")
    defaults.update(kwargs)
    return ContextRequest(**defaults)


def test_applies_to_skips_unrelated_purpose() -> None:
    p = TrackKnowledgeProvider()
    req = _mk_req(purpose=PURPOSE_RERANK_JOB, preferences={"preferred_tracks": ["量化"]})
    assert p.applies_to(req) is False, "RERANK_JOB 不应 apply (per-job 路径不走这块)"


def test_applies_to_returns_true_on_preferences() -> None:
    p = TrackKnowledgeProvider()
    req = _mk_req(preferences={"preferred_tracks": ["量化"]})
    assert p.applies_to(req) is True


def test_applies_to_returns_true_on_inferred_tracks() -> None:
    p = TrackKnowledgeProvider()
    req = _mk_req(profile={"inferred_tracks": ["公募基金"]})  # 公募基金 → 二级买方·基本面
    assert p.applies_to(req) is True


def test_applies_to_returns_true_on_target_job_text() -> None:
    p = TrackKnowledgeProvider()
    req = _mk_req(target_job="中信证券 IBD Analyst 投行部")  # IBD → 一级市场
    assert p.applies_to(req) is True


def test_applies_to_returns_false_without_signal() -> None:
    p = TrackKnowledgeProvider()
    req = _mk_req(target_job="生物医药研发岗", user_question="如何转行?")
    assert p.applies_to(req) is False


# ── Resolve canonical 优先级 ────────────────────────────────────────────


def test_preferences_beats_profile() -> None:
    """preferences 比 profile 更接近用户当前意图,优先。"""
    p = TrackKnowledgeProvider()
    req = _mk_req(
        preferences={"preferred_tracks": ["量化"]},
        profile={"inferred_tracks": ["公募基金"]},
    )
    block = p.fetch(req)
    assert "canonical=量化" in block
    assert "二级买方" not in block


def test_profile_beats_target_job() -> None:
    p = TrackKnowledgeProvider()
    req = _mk_req(
        profile={"inferred_tracks": ["量化"]},
        target_job="中信证券 IBD Analyst",
    )
    block = p.fetch(req)
    assert "canonical=量化" in block


# ── fetch 输出格式 ──────────────────────────────────────────────────────


def test_fetch_output_format() -> None:
    p = TrackKnowledgeProvider()
    req = _mk_req(preferences={"preferred_tracks": ["二级买方·基本面"]})
    block = p.fetch(req)

    assert block, "fetch 不应返空"
    assert "track_knowledge" in block, "block header 应含 provider name"
    assert "canonical=二级买方·基本面" in block
    assert "典型雇主" in block
    assert "高质量信号词" in block
    assert "STAR 模板" in block or "STAR" in block
    assert "follow-up" in block.lower() or "提问" in block


def test_fetch_returns_empty_when_no_match() -> None:
    p = TrackKnowledgeProvider()
    req = _mk_req(target_job="生物医药岗")
    assert p.fetch(req) == ""


def test_fetch_block_within_token_budget() -> None:
    """每条 block 不应过长(~300-500 tokens),否则破坏 phase D 的 budget 假设。"""
    p = TrackKnowledgeProvider()
    for canon in CANONICAL_FINANCE_TRACKS:
        req = _mk_req(preferences={"preferred_tracks": [canon]})
        block = p.fetch(req)
        # 中文混合 ~2 chars/token; 1500 chars ≈ 750 tokens — 还在 chat <5% 内
        assert len(block) <= 1500, f"{canon} block {len(block)} 字超出预算"


# ── 注册到 registry ─────────────────────────────────────────────────────


def test_provider_registered_in_bootstrap() -> None:
    """bootstrap() 调用后,track_knowledge 必须出现在 registered_names()。"""
    from app.services.llm_context import bootstrap, registered_names
    bootstrap()
    names = registered_names()
    assert "track_knowledge" in names, f"track_knowledge 应被 bootstrap 注册;现有 {names}"
