"""TrackKnowledgeProvider — 5th ContextProvider (Phase D, 2026-05-16)。

读 `tracks.yaml`(Phase D-0 写的 8 canonical knowledge data),根据 request
判断 user/job 命中哪个 canonical,返回一段紧凑的 prompt block:
  - 典型雇主 (top 5)
  - 高质量信号词 (top 5)
  - 1 个 STAR 示例(选最长的)
  - 2 个 follow-up 模板

适用 purpose:CHAT / INTERVIEW_QUESTION / INTERVIEW_SCORE (RERANK_JOB
单独走 _build_xx_block 保持 per-job 路径轻量)。

Token 预算:每条 block ~600-1000 chars (~300-500 tokens),整体加在 4 个现有
provider 之后,实测仍 <5% context (DeepSeek 64K)。

Canonical 命中优先级:
  1. preferences.preferred_tracks 第一个能 canonicalize 的
  2. profile.inferred_tracks 第一个能 canonicalize 的
  3. target_job + user_question 跑 canonicalize_track 检测
  4. 都没命中 → 不应用 (applies_to 返 False)

注:这个 provider 故意保守 — 命中歧义时(用户 prefs 含 ['二级买方·基本面','量化'])
只取第一个 canonical 不混 block。混 block 会污染 LLM 上下文。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from app.services.llm_context.base import (
    PURPOSE_CHAT,
    PURPOSE_INTERVIEW_QUESTION,
    PURPOSE_INTERVIEW_SCORE,
    ContextRequest,
)
from app.services.taxonomy.canonical import canonicalize_track

logger = logging.getLogger(__name__)


_TRACKS_YAML = Path(__file__).resolve().parent / "tracks.yaml"


def _load_tracks() -> dict[str, dict[str, Any]]:
    """{canonical_name -> track_dict} index for O(1) lookup. Module-load only."""
    raw = yaml.safe_load(_TRACKS_YAML.read_text(encoding="utf-8")) or {}
    return {t["canonical"]: t for t in (raw.get("tracks") or [])}


_TRACK_INDEX: dict[str, dict[str, Any]] = _load_tracks()


_APPLICABLE_PURPOSES = frozenset({
    PURPOSE_CHAT,
    PURPOSE_INTERVIEW_QUESTION,
    PURPOSE_INTERVIEW_SCORE,
})


def _first_canonical_from_list(values: list[str] | None) -> Optional[str]:
    if not values:
        return None
    for v in values:
        if not v:
            continue
        canon = canonicalize_track(v)
        if canon in _TRACK_INDEX:
            return canon
    return None


def _canonical_from_text(text: str | None) -> Optional[str]:
    """从 free text 抓 canonical:把每个空白拆出来跑 canonicalize_track 看命中。

    简化实现:不做 tokenize,直接对整段文本 + 关键词 alias 做子串匹配。
    canonicalize_track 内部已经是子串匹配。
    """
    if not text or not text.strip():
        return None
    canon = canonicalize_track(text)
    return canon if canon in _TRACK_INDEX else None


def _resolve_canonical(req: ContextRequest) -> Optional[str]:
    prefs = req.preferences or {}
    canon = _first_canonical_from_list(prefs.get("preferred_tracks"))
    if canon:
        return canon

    profile = req.profile or {}
    canon = _first_canonical_from_list(profile.get("inferred_tracks"))
    if canon:
        return canon

    canon = _canonical_from_text(req.target_job) or _canonical_from_text(req.user_question)
    return canon


def _format_block(canon: str, track: dict[str, Any]) -> str:
    """紧凑 prompt-ready 输出。Top-5 雇主 + top-5 signals + 1 STAR + 2 followup。"""
    employers = (track.get("typical_employers") or [])[:5]
    high_sig = (track.get("high_quality_signals") or [])[:5]
    stars = track.get("star_examples") or []
    followups = (track.get("followup_templates") or [])[:2]

    star_block = ""
    if stars:
        # 取段落字数最长的 STAR (信息密度更高)
        s = max(stars, key=lambda s: sum(len(str(s.get(k, ''))) for k in ('context', 'task', 'action', 'result')))
        star_block = (
            f"  STAR 模板: 情境={s.get('context','').strip()} | "
            f"任务={s.get('task','').strip()} | "
            f"行动={s.get('action','').strip()} | "
            f"结果={s.get('result','').strip()}"
        )

    lines = [
        f"[track_knowledge · canonical={canon} · 仅供你判断口径,不要原文复述]",
        f"  典型雇主: {' / '.join(employers)}",
        f"  高质量信号词: {' / '.join(high_sig)}",
    ]
    if star_block:
        lines.append(star_block)
    if followups:
        lines.append("  典型 follow-up 提问参考:")
        for fu in followups:
            lines.append(f"    - {fu}")
    return "\n".join(lines)


class TrackKnowledgeProvider:
    """5th ContextProvider — canonical track 的雇主/信号词/STAR/follow-up 模板。"""

    name = "track_knowledge"

    def applies_to(self, req: ContextRequest) -> bool:
        if req.purpose not in _APPLICABLE_PURPOSES:
            return False
        return _resolve_canonical(req) is not None

    def fetch(self, req: ContextRequest) -> str:
        canon = _resolve_canonical(req)
        if not canon:
            return ""
        track = _TRACK_INDEX.get(canon)
        if not track:
            return ""
        return _format_block(canon, track)


__all__ = ["TrackKnowledgeProvider"]
